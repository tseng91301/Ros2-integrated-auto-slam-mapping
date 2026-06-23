import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from nav_msgs.msg import OccupancyGrid
from tf2_ros.buffer import Buffer
from tf2_ros.transform_listener import TransformListener
import threading
import tornado.ioloop
import tornado.web
import tornado.websocket
import json
import base64
import numpy as np
import os
import subprocess
import zipfile
import io
from PIL import Image
from ament_index_python.packages import get_package_share_directory

# Global variables to store the node and active web socket clients
ros_node = None
websocket_clients = set()
latest_map_data = None  # Cache for map updates

class TeleopNode(Node):
    def __init__(self):
        super().__init__('web_teleop_node')
        self.pub = self.create_publisher(Twist, 'cmd_vel', 10)
        self.sub_map = self.create_subscription(
            OccupancyGrid,
            'map',
            self.map_callback,
            10
        )
        # Transform listener to query robot pose
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)
        # Create a timer to broadcast robot pose at 10Hz
        self.create_timer(0.1, self.update_robot_pose)
        self.get_logger().info("Web Teleop ROS 2 Node initialized with TF listener.")

    def map_callback(self, msg):
        global latest_map_data
        # Map OccupancyGrid data using numpy for speed
        width = msg.info.width
        height = msg.info.height
        resolution = msg.info.resolution
        origin_x = msg.info.origin.position.x
        origin_y = msg.info.origin.position.y
        
        try:
            grid_arr = np.array(msg.data, dtype=np.int8)
            # Map values:
            # 0 (free) -> 255
            # 100 (occupied) -> 0
            # -1 (unknown) -> 127
            pixels = np.full(grid_arr.shape, 127, dtype=np.uint8)
            pixels[grid_arr == 0] = 255
            pixels[grid_arr == 100] = 0
            
            # Base64 encode
            b64_str = base64.b64encode(pixels.tobytes()).decode('utf-8')
            
            latest_map_data = {
                "type": "map",
                "width": width,
                "height": height,
                "resolution": resolution,
                "origin_x": origin_x,
                "origin_y": origin_y,
                "data": b64_str
            }
            
            # Broadcast to all websocket clients
            for client in websocket_clients:
                try:
                    client.write_message(json.dumps(latest_map_data))
                except Exception as e:
                    pass
        except Exception as e:
            self.get_logger().error(f"Error processing map: {str(e)}")

    def update_robot_pose(self):
        global websocket_clients
        if not websocket_clients:
            return
        try:
            # Lookup latest transform map -> base_footprint (or fallback to base_link)
            try:
                trans = self.tf_buffer.lookup_transform('map', 'base_footprint', rclpy.time.Time())
            except Exception:
                trans = self.tf_buffer.lookup_transform('map', 'base_link', rclpy.time.Time())
                
            x = trans.transform.translation.x
            y = trans.transform.translation.y
            q = trans.transform.rotation
            
            # Convert quaternion to yaw angle
            siny_cosp = 2 * (q.w * q.z + q.x * q.y)
            cosy_cosp = 1 - 2 * (q.y * q.y + q.z * q.z)
            yaw = np.arctan2(siny_cosp, cosy_cosp)
            
            pose_data = {
                "type": "robot_pose",
                "x": x,
                "y": y,
                "yaw": yaw
            }
            
            # Broadcast pose
            for client in websocket_clients:
                try:
                    client.write_message(json.dumps(pose_data))
                except Exception:
                    pass
        except Exception:
            # Normal to fail if TF tree is not complete yet
            pass

    def publish_twist(self, x, y, th):
        twist = Twist()
        twist.linear.x = float(x)
        twist.linear.y = float(y)
        twist.linear.z = 0.0
        twist.angular.x = 0.0
        twist.angular.y = 0.0
        twist.angular.z = float(th)
        self.pub.publish(twist)

class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.render("index.html")

class WSHandler(tornado.websocket.WebSocketHandler):
    def check_origin(self, origin):
        return True

    def open(self):
        websocket_clients.add(self)
        ros_node.get_logger().info("WebSocket client connected.")
        # Immediately send cached map data if available
        if latest_map_data is not None:
            self.write_message(json.dumps(latest_map_data))

    def on_message(self, message):
        try:
            data = json.loads(message)
            msg_type = data.get("type")
            
            if msg_type == "cmd_vel":
                x = data.get("x", 0.0)
                y = data.get("y", 0.0)
                th = data.get("th", 0.0)
                ros_node.publish_twist(x, y, th)
            elif msg_type == "save_map":
                # Trigger robot-side map save
                filename = data.get("filename", "map")
                save_dir = "/home/ubuntu/maps"
                os.makedirs(save_dir, exist_ok=True)
                filepath = os.path.join(save_dir, filename)
                
                # Executing command to save the map
                cmd = ["ros2", "run", "nav2_map_server", "map_saver_cli", "-f", filepath]
                subprocess.Popen(cmd) # Run in background so we don't block
                ros_node.get_logger().info(f"Saving map to {filepath}...")
            elif msg_type == "reset_map":
                # Call slam_toolbox reset service asynchronously
                cmd = ["ros2", "service", "call", "/slam_toolbox/reset", "slam_toolbox/srv/Reset", "{}"]
                subprocess.Popen(cmd)
                ros_node.get_logger().info("Reset map command sent to slam_toolbox.")
        except Exception as e:
            ros_node.get_logger().error(f"Error handling WS message: {str(e)}")

    def on_close(self):
        websocket_clients.remove(self)
        ros_node.get_logger().info("WebSocket client disconnected.")

class DownloadMapHandler(tornado.web.RequestHandler):
    def get(self):
        try:
            # We will use map_saver_cli to save a temporary map
            temp_dir = "/tmp/map_download"
            os.makedirs(temp_dir, exist_ok=True)
            temp_path = os.path.join(temp_dir, "map")
            
            # Remove old temp files
            for ext in [".yaml", ".pgm", ".png"]:
                if os.path.exists(temp_path + ext):
                    os.remove(temp_path + ext)
            
            # Execute map saver cli synchronously (wait up to 5 seconds)
            cmd = ["ros2", "run", "nav2_map_server", "map_saver_cli", "-f", temp_path]
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
            
            if proc.returncode != 0:
                self.set_status(500)
                self.write(f"Failed to generate map files: {proc.stderr}")
                return
                
            yaml_file = temp_path + ".yaml"
            pgm_file = temp_path + ".pgm"
            
            if not os.path.exists(yaml_file) or not os.path.exists(pgm_file):
                self.set_status(500)
                self.write("Map saver finished but map files were not created.")
                return
            
            # Convert PGM to PNG for convenience
            png_file = temp_path + ".png"
            try:
                img = Image.open(pgm_file)
                img.save(png_file)
            except Exception as e:
                ros_node.get_logger().error(f"Failed to convert map to PNG: {str(e)}")
                png_file = None
            
            # Create a zip archive in memory
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
                zip_file.write(yaml_file, "map.yaml")
                zip_file.write(pgm_file, "map.pgm")
                if png_file and os.path.exists(png_file):
                    zip_file.write(png_file, "map.png")
            
            # Set response headers
            self.set_header("Content-Type", "application/zip")
            self.set_header("Content-Disposition", "attachment; filename=map_files.zip")
            self.write(zip_buffer.getvalue())
            
        except Exception as e:
            self.set_status(500)
            self.write(f"Error saving map: {str(e)}")

def main():
    global ros_node
    rclpy.init()
    ros_node = TeleopNode()
    
    # Spin ROS 2 in a separate thread
    spin_thread = threading.Thread(target=rclpy.spin, args=(ros_node,), daemon=True)
    spin_thread.start()
    
    # Get share directory paths
    share_dir = get_package_share_directory('wheeltec_web_teleop')
    template_path = os.path.join(share_dir, 'templates')
    static_path = os.path.join(share_dir, 'static')
    
    app = tornado.web.Application([
        (r"/", MainHandler),
        (r"/ws", WSHandler),
        (r"/api/download_map", DownloadMapHandler),
        (r"/static/(.*)", tornado.web.StaticFileHandler, {"path": static_path}),
    ], template_path=template_path)
    
    # Start web server on port 8080 (listens on all interfaces)
    app.listen(8080)
    ros_node.get_logger().info("Web server started at http://0.0.0.0:8080")
    
    try:
        tornado.ioloop.IOLoop.current().start()
    except KeyboardInterrupt:
        pass
    finally:
        rclpy.shutdown()
        spin_thread.join()

if __name__ == '__main__':
    main()
