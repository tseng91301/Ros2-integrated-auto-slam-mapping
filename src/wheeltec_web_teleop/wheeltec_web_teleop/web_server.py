import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from nav_msgs.msg import OccupancyGrid
from tf2_ros.buffer import Buffer
from tf2_ros.transform_listener import TransformListener
from std_msgs.msg import String
from visualization_msgs.msg import MarkerArray
from sensor_msgs.msg import LaserScan
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
import math
from collections import deque
import yaml
from PIL import Image
from ament_index_python.packages import get_package_share_directory
from slam_toolbox.srv import Reset
from nav2_msgs.action import NavigateToPose
from rclpy.action import ActionClient

# Global variables to store the node and active web socket clients
ros_node = None
websocket_clients = set()
latest_map_data = None  # Cache for map updates
latest_markers_data = None  # Cache for exploration markers
latest_status_data = None  # Cache for exploration status
latest_nav_map_data = None  # Cache for static navigation map
main_loop = None  # Main thread's Tornado IOLoop

def get_map_dir():
    # Try source workspace paths inside container first (writeable and persistent)
    paths = [
        "/workspaces/isaac_ros-dev/src/wheeltec_robot_nav2/map",
        "/home/ubuntu/workspaces/isaac_ros-dev/src/wheeltec_robot_nav2/map"
    ]
    for p in paths:
        if os.path.exists(p) and os.access(p, os.W_OK):
            return p
            
    # Try package share maps folder
    try:
        map_dir = os.path.join(get_package_share_directory('wheeltec_nav2'), 'map')
        if os.path.exists(map_dir) and os.access(map_dir, os.W_OK):
            return map_dir
    except Exception:
        pass
        
    # Default container path
    fallback = "/home/ubuntu/maps"
    os.makedirs(fallback, exist_ok=True)
    return fallback

def get_map_yaml_path(map_name):
    search_dirs = [
        "/workspaces/isaac_ros-dev/src/wheeltec_robot_nav2/map",
        "/home/ubuntu/workspaces/isaac_ros-dev/src/wheeltec_robot_nav2/map",
        "/home/ubuntu/maps"
    ]
    try:
        search_dirs.append(os.path.join(get_package_share_directory('wheeltec_nav2'), 'map'))
    except Exception:
        pass
        
    for d in search_dirs:
        yaml_path = os.path.join(d, f"{map_name}.yaml")
        if os.path.exists(yaml_path):
            return yaml_path
    return None

def load_map_from_disk(yaml_path):
    with open(yaml_path, 'r') as f:
        map_metadata = yaml.safe_load(f)
    image_name = map_metadata['image']
    origin = map_metadata['origin']  # [x, y, yaw]
    resolution = map_metadata['resolution']
    
    yaml_dir = os.path.dirname(yaml_path)
    image_path = os.path.join(yaml_dir, image_name)
    
    img = Image.open(image_path)
    width, height = img.size
    
    # Read pixels (gray) and invert vertically to match ROS /map conventions
    img_arr = np.array(img.convert('L'))
    img_arr = np.flipud(img_arr)
    
    occupied_thresh = map_metadata.get('occupied_thresh', 0.65)
    free_thresh = map_metadata.get('free_thresh', 0.25)
    
    # Pixels: free=255, occupied=0, unknown=127
    pixels = np.full(img_arr.shape, 127, dtype=np.uint8)
    
    occ_max = (1.0 - occupied_thresh) * 255.0
    free_min = (1.0 - free_thresh) * 255.0
    
    pixels[img_arr <= occ_max] = 0
    pixels[img_arr >= free_min] = 255
    
    # Base64 encode
    b64_str = base64.b64encode(pixels.tobytes()).decode('utf-8')
    
    return {
        "type": "map",
        "width": width,
        "height": height,
        "resolution": resolution,
        "origin_x": float(origin[0]),
        "origin_y": float(origin[1]),
        "data": b64_str
    }


def safe_broadcast(message_dict):
    global main_loop, websocket_clients
    if main_loop is None or not websocket_clients:
        return
    msg_str = json.dumps(message_dict)
    def broadcast():
        for client in list(websocket_clients):
            try:
                # Do not broadcast active SLAM map updates to clients in navigation mode
                if message_dict.get("type") == "map" and getattr(client, "mode", "exploration") != "exploration":
                    continue
                client.write_message(msg_str)
            except Exception:
                pass
    main_loop.add_callback(broadcast)

class TeleopNode(Node):
    def __init__(self):
        super().__init__('web_teleop_node')
        
        # Publisher for velocity commands (Teleop)
        self.pub = self.create_publisher(Twist, 'cmd_vel', 10)
        
        # Subscriber for lidar scan (for collision avoidance / safeguard)
        self.latest_scan = None
        self.sub_scan = self.create_subscription(
            LaserScan,
            'scan',
            self.scan_callback,
            10
        )
        
        # Subscriber for map updates
        self.sub_map = self.create_subscription(
            OccupancyGrid,
            'map',
            self.map_callback,
            10
        )
        
        # Subscriber for heatmap updates
        self.latest_heatmap = None
        self.sub_heatmap = self.create_subscription(
            OccupancyGrid,
            '/heatmap',
            self.heatmap_callback,
            10
        )
        
        # Subscriber for frontier centroids and active target coordinates (from auto_explorer)
        self.sub_markers = self.create_subscription(
            MarkerArray,
            '/exploration_markers',
            self.markers_callback,
            10
        )
        
        # Publisher for exploration control commands
        self.explorer_pub = self.create_publisher(
            String,
            '/exploration_control',
            10
        )
        
        # Subscriber for exploration status topic
        self.sub_status = self.create_subscription(
            String,
            '/exploration_status',
            self.status_callback,
            10
        )
        
        # Transform listener to query robot pose
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)
        
        # Create client for slam_toolbox reset service
        self.reset_cli = self.create_client(Reset, '/slam_toolbox/reset')
        
        # Create a timer to broadcast robot pose at 10Hz
        self.create_timer(0.1, self.update_robot_pose)
        
        # Navigation parameters and clients
        self.nav_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        self.nav_target = None  # (x, y) in world coordinates
        self.nav_state = 'IDLE'  # 'IDLE', 'NAVIGATING', 'PAUSED'
        self.nav_path = []  # list of (x, y)
        self.nav_waypoint_idx = 0
        self.nav_goal_handle = None
        
        # Create a timer for fallback navigation control loop (10Hz)
        self.create_timer(0.1, self.navigation_control_step)
        
        self.get_logger().info("Web Teleop & Explorer ROS 2 Node initialized with Navigation support.")

    def call_reset_map(self):
        if not self.reset_cli.service_is_ready():
            self.get_logger().warn("SLAM Toolbox reset service not ready. Fallback to CLI subprocess.")
            cmd = ["ros2", "service", "call", "/slam_toolbox/reset", "slam_toolbox/srv/Reset", "{}"]
            subprocess.Popen(cmd)
            return
        
        req = Reset.Request()
        future = self.reset_cli.call_async(req)
        future.add_done_callback(self.reset_map_done_callback)

    def reset_map_done_callback(self, future):
        try:
            future.result()
            self.get_logger().info("SLAM Toolbox reset service call successful.")
        except Exception as e:
            self.get_logger().error(f"SLAM Toolbox reset service call failed: {e}")

    def scan_callback(self, msg):
        self.latest_scan = msg
        try:
            ranges = np.array(msg.ranges)
            # Replace inf/nan with large numbers
            ranges = np.nan_to_num(ranges, nan=10.0, posinf=10.0, neginf=10.0)
            
            num_readings = len(ranges)
            if num_readings > 0:
                angles = msg.angle_min + np.arange(num_readings) * msg.angle_increment
                # Normalize angles to [-pi, pi]
                angles = (angles + np.pi) % (2 * np.pi) - np.pi
                
                # Obstacle threshold distance (0.35m)
                threshold = 0.35
                
                # Sectors:
                # Front sector: |angle| < 45 deg (pi/4)
                front_mask = (np.abs(angles) < np.pi / 4) & (ranges < threshold)
                # Rear sector: |angle| > 135 deg (3*pi/4)
                rear_mask = (np.abs(angles) > 3 * np.pi / 4) & (ranges < threshold)
                # Left sector: 45 to 135 deg
                left_mask = (angles >= np.pi / 4) & (angles <= 3 * np.pi / 4) & (ranges < threshold)
                # Right sector: -135 to -45 deg
                right_mask = (angles <= -np.pi / 4) & (angles >= -3 * np.pi / 4) & (ranges < threshold)
                
                collision_detected = np.any(front_mask) or np.any(rear_mask) or np.any(left_mask) or np.any(right_mask)
                
                collision_msg = {
                    "type": "collision",
                    "collision": bool(collision_detected),
                    "front": bool(np.any(front_mask)),
                    "rear": bool(np.any(rear_mask)),
                    "left": bool(np.any(left_mask)),
                    "right": bool(np.any(right_mask))
                }
                
                # Broadcast collision state to all websocket clients
                safe_broadcast(collision_msg)
        except Exception as e:
            self.get_logger().error(f"Error in scan processing: {e}")

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
            
            # Blend heatmap into free space pixels
            free_mask = (grid_arr == 0)
            
            if (self.latest_heatmap is not None 
                    and self.latest_heatmap.info.width == width 
                    and self.latest_heatmap.info.height == height):
                # Load heatmap data
                heat_arr = np.array(self.latest_heatmap.data, dtype=np.int8)
                temp_scaled = (heat_arr * 2.5).astype(np.uint8)
                temp_scaled = np.clip(temp_scaled, 1, 254)
                
                # Apply heat values to free cells
                has_heat = (heat_arr > 0)
                pixels[free_mask] = 255
                heat_free_mask = free_mask & has_heat
                pixels[heat_free_mask] = temp_scaled[heat_free_mask]
            else:
                pixels[free_mask] = 255
                
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
            safe_broadcast(latest_map_data)
        except Exception as e:
            self.get_logger().error(f"Error processing map: {str(e)}")

    def heatmap_callback(self, msg):
        self.latest_heatmap = msg

    def markers_callback(self, msg):
        """Processes centroids and active exploration targets and sends them to WebSocket clients."""
        global websocket_clients, latest_markers_data
        
        centroids = []
        target = None
        
        for marker in msg.markers:
            # If marker action is DELETEALL, it indicates map/frontiers are being reset
            if marker.action == 3:  # DELETEALL
                continue
            if marker.ns == "centroids":
                for pt in marker.points:
                    centroids.append({"x": pt.x, "y": pt.y})
            elif marker.ns == "target":
                target = {"x": marker.pose.position.x, "y": marker.pose.position.y}
                
        latest_markers_data = {
            "type": "exploration_status",
            "centroids": centroids,
            "target": target
        }
        
        # Broadcast status to Web clients
        safe_broadcast(latest_markers_data)

    def status_callback(self, msg):
        """Processes the exploration status and forwards it to WebSocket clients."""
        global websocket_clients, latest_status_data
        try:
            data = json.loads(msg.data)
            latest_status_data = {
                "type": "exploration_node_status",
                "is_paused": data.get("is_paused"),
                "current_lap": data.get("current_lap"),
                "max_exploration_laps": data.get("max_exploration_laps"),
                "exploration_complete": data.get("exploration_complete"),
                "blacklist_count": data.get("blacklist_count"),
                "robot_radius": data.get("robot_radius", 0.20),
                "is_recovering": data.get("is_recovering", False)
            }
            safe_broadcast(latest_status_data)
        except Exception as e:
            pass

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
            safe_broadcast(pose_data)
        except Exception as e:
            # Log TF lookup error for diagnostic purposes
            self.get_logger().error(f"TF lookup failed: {str(e)}")
            pass

    def publish_twist(self, x, y, th):
        safe_x = float(x)
        safe_y = float(y)
        
        if self.latest_scan is not None:
            try:
                ranges = np.array(self.latest_scan.ranges)
                # Replace inf/nan with large numbers
                ranges = np.nan_to_num(ranges, nan=10.0, posinf=10.0, neginf=10.0)
                
                num_readings = len(ranges)
                if num_readings > 0:
                    angles = self.latest_scan.angle_min + np.arange(num_readings) * self.latest_scan.angle_increment
                    # Normalize angles to [-pi, pi]
                    angles = (angles + np.pi) % (2 * np.pi) - np.pi
                    
                    # Obstacle threshold distance (e.g. 0.35m)
                    threshold = 0.35
                    
                    # Front sector: |angle| < 45 deg (pi/4)
                    front_mask = (np.abs(angles) < np.pi / 4) & (ranges < threshold)
                    # Rear sector: |angle| > 135 deg (3*pi/4)
                    rear_mask = (np.abs(angles) > 3 * np.pi / 4) & (ranges < threshold)
                    # Left sector: 45 to 135 deg
                    left_mask = (angles >= np.pi / 4) & (angles <= 3 * np.pi / 4) & (ranges < threshold)
                    # Right sector: -135 to -45 deg
                    right_mask = (angles <= -np.pi / 4) & (angles >= -3 * np.pi / 4) & (ranges < threshold)
                    
                    if safe_x > 0 and np.any(front_mask):
                        self.get_logger().warn("⚠️ Obstacle detected in FRONT. Blocking forward motion!")
                        safe_x = 0.0
                    elif safe_x < 0 and np.any(rear_mask):
                        self.get_logger().warn("⚠️ Obstacle detected in REAR. Blocking backward motion!")
                        safe_x = 0.0
                        
                    if safe_y > 0 and np.any(left_mask):
                        self.get_logger().warn("⚠️ Obstacle detected on LEFT. Blocking left motion!")
                        safe_y = 0.0
                    elif safe_y < 0 and np.any(right_mask):
                        self.get_logger().warn("⚠️ Obstacle detected on RIGHT. Blocking right motion!")
                        safe_y = 0.0
            except Exception as e:
                self.get_logger().error(f"Error in collision safety check: {str(e)}")

        twist = Twist()
        twist.linear.x = safe_x
        twist.linear.y = safe_y
        twist.linear.z = 0.0
        twist.angular.x = 0.0
        twist.angular.y = 0.0
        twist.angular.z = float(th)
        self.pub.publish(twist)

    def get_robot_pose(self):
        try:
            try:
                trans = self.tf_buffer.lookup_transform('map', 'base_footprint', rclpy.time.Time())
            except Exception:
                trans = self.tf_buffer.lookup_transform('map', 'base_link', rclpy.time.Time())
                
            x = trans.transform.translation.x
            y = trans.transform.translation.y
            q = trans.transform.rotation
            
            siny_cosp = 2 * (q.w * q.z + q.x * q.y)
            cosy_cosp = 1 - 2 * (q.y * q.y + q.z * q.z)
            yaw = np.arctan2(siny_cosp, cosy_cosp)
            return x, y, yaw
        except Exception:
            return None

    def start_navigation(self, x, y):
        self.nav_target = (x, y)
        self.nav_state = 'NAVIGATING'
        self.get_logger().info(f"Starting navigation to target: ({x}, {y})")
        
        # Try Nav2 Action Client first
        if self.nav_client.wait_for_server(timeout_sec=0.5):
            self.get_logger().info("Nav2 server is available. Sending goal via ActionClient.")
            goal_msg = NavigateToPose.Goal()
            goal_msg.pose.header.frame_id = 'map'
            goal_msg.pose.header.stamp = self.get_clock().now().to_msg()
            goal_msg.pose.pose.position.x = float(x)
            goal_msg.pose.pose.position.y = float(y)
            goal_msg.pose.pose.orientation.w = 1.0
            
            self.cancel_nav_goal()
            
            send_goal_future = self.nav_client.send_goal_async(goal_msg)
            send_goal_future.add_done_callback(self.nav_goal_response_callback)
        else:
            self.get_logger().info("Nav2 server not ready. Sourcing direct path-follower fallback...")
            self.plan_fallback_path()

    def cancel_nav_goal(self):
        if self.nav_goal_handle is not None:
            self.get_logger().info("Cancelling current Nav2 goal...")
            self.nav_goal_handle.cancel_goal_async()
            self.nav_goal_handle = None

    def nav_goal_response_callback(self, future):
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().info("Nav2 Goal rejected by server.")
            self.nav_state = 'IDLE'
            return
            
        self.get_logger().info("Nav2 Goal accepted by server.")
        self.nav_goal_handle = goal_handle
        
        get_result_future = goal_handle.get_result_async()
        get_result_future.add_done_callback(self.nav_result_callback)

    def nav_result_callback(self, future):
        result = future.result()
        status = result.status
        self.get_logger().info(f"Nav2 navigation finished with status: {status}")
        self.nav_goal_handle = None
        self.nav_state = 'ARRIVED'
        safe_broadcast({"type": "nav_status", "status": "ARRIVED"})

    def plan_fallback_path(self):
        global latest_nav_map_data
        
        robot_pose = self.get_robot_pose()
        if robot_pose is None:
            self.get_logger().error("Cannot get robot pose for navigation planning.")
            self.nav_state = 'IDLE'
            return
            
        robot_x, robot_y, robot_yaw = robot_pose
        
        if latest_nav_map_data is None:
            self.nav_path = [self.nav_target]
            self.nav_waypoint_idx = 0
            return
            
        width = latest_nav_map_data["width"]
        height = latest_nav_map_data["height"]
        resolution = latest_nav_map_data["resolution"]
        origin_x = latest_nav_map_data["origin_x"]
        origin_y = latest_nav_map_data["origin_y"]
        
        # Decode base64 to 2D numpy array
        raw_data = base64.b64decode(latest_nav_map_data["data"])
        grid = np.frombuffer(raw_data, dtype=np.uint8).reshape((height, width))
        
        def world_to_grid(wx, wy):
            gx = int((wx - origin_x) / resolution)
            gy = int((wy - origin_y) / resolution)
            return gx, gy
            
        def grid_to_world(gx, gy):
            wx = origin_x + (gx + 0.5) * resolution
            wy = origin_y + (gy + 0.5) * resolution
            return wx, wy
            
        start_g = world_to_grid(robot_x, robot_y)
        goal_g = world_to_grid(self.nav_target[0], self.nav_target[1])
        
        if not (0 <= start_g[0] < width and 0 <= start_g[1] < height) or \
           not (0 <= goal_g[0] < width and 0 <= goal_g[1] < height):
            self.nav_path = [self.nav_target]
            self.nav_waypoint_idx = 0
            return
            
        # BFS Path planning
        queue = deque([start_g])
        parent = {start_g: None}
        visited = {start_g}
        found = False
        
        while queue:
            curr = queue.popleft()
            if curr == goal_g:
                found = True
                break
                
            cx, cy = curr
            for dx, dy in [(-1,0), (1,0), (0,-1), (0,1), (-1,-1), (-1,1), (1,-1), (1,1)]:
                nx, ny = cx + dx, cy + dy
                neighbor = (nx, ny)
                if 0 <= nx < width and 0 <= ny < height and neighbor not in visited:
                    # Treat anything other than free space (255) as obstacle
                    if grid[ny, nx] == 255:
                        visited.add(neighbor)
                        parent[neighbor] = curr
                        queue.append(neighbor)
                        
        if found:
            path = []
            curr = goal_g
            while curr is not None:
                path.append(grid_to_world(curr[0], curr[1]))
                curr = parent[curr]
            path.reverse()
            # Downsample path
            self.nav_path = path[::5]
            if not self.nav_path or self.nav_path[-1] != self.nav_target:
                self.nav_path.append(self.nav_target)
            self.nav_waypoint_idx = 0
            self.get_logger().info(f"Planned BFS path with {len(self.nav_path)} waypoints.")
        else:
            self.get_logger().warn("BFS path not found. Falling back to straight-line path.")
            self.nav_path = [self.nav_target]
            self.nav_waypoint_idx = 0

    def navigation_control_step(self):
        if self.nav_state != 'NAVIGATING':
            return
            
        # If Nav2 action is running, wait for it or verify distance
        if self.nav_goal_handle is not None:
            robot_pose = self.get_robot_pose()
            if robot_pose is not None:
                rx, ry, _ = robot_pose
                tx, ty = self.nav_target
                dist = math.hypot(tx - rx, ty - ry)
                if dist < 0.25:
                    self.get_logger().info("Arrived at target (Nav2 tracking)!")
                    self.cancel_nav_goal()
                    self.nav_state = 'ARRIVED'
                    safe_broadcast({"type": "nav_status", "status": "ARRIVED"})
            return
            
        # Fallback controller driving along waypoints
        if not self.nav_path or self.nav_waypoint_idx >= len(self.nav_path):
            self.get_logger().info("Arrived at final waypoint!")
            self.nav_state = 'ARRIVED'
            self.publish_twist(0.0, 0.0, 0.0)
            safe_broadcast({"type": "nav_status", "status": "ARRIVED"})
            return
            
        robot_pose = self.get_robot_pose()
        if robot_pose is None:
            return
            
        rx, ry, ryaw = robot_pose
        wx, wy = self.nav_path[self.nav_waypoint_idx]
        
        dist = math.hypot(wx - rx, wy - ry)
        is_last = (self.nav_waypoint_idx == len(self.nav_path) - 1)
        threshold = 0.2 if is_last else 0.4
        
        if dist < threshold:
            if is_last:
                self.get_logger().info("Arrived at target waypoint!")
                self.nav_state = 'ARRIVED'
                self.publish_twist(0.0, 0.0, 0.0)
                safe_broadcast({"type": "nav_status", "status": "ARRIVED"})
                return
            else:
                self.nav_waypoint_idx += 1
                wx, wy = self.nav_path[self.nav_waypoint_idx]
                dist = math.hypot(wx - rx, wy - ry)
                
        # Steering angle to waypoint
        angle = math.atan2(wy - ry, wx - rx)
        yaw_err = angle - ryaw
        yaw_err = (yaw_err + math.pi) % (2 * math.pi) - math.pi
        
        # P-controller for steering and speed
        angular_vel = 1.2 * yaw_err
        angular_vel = max(-0.6, min(0.6, angular_vel))
        
        # Only move forward if heading error is small
        if abs(yaw_err) < 0.5:
            linear_vel = 0.15 * math.cos(yaw_err)
            linear_vel = max(0.0, min(0.18, linear_vel))
        else:
            linear_vel = 0.0
            
        self.publish_twist(linear_vel, 0.0, angular_vel)

class MainHandler(tornado.web.RequestHandler):
    """Serves the portal page containing choices for Manual Teleop or Auto Exploration."""
    def get(self):
        self.render("index.html")

class TeleopHandler(tornado.web.RequestHandler):
    """Serves the Manual Teleop interface."""
    def get(self):
        self.render("teleop.html")

class ExplorerHandler(tornado.web.RequestHandler):
    """Serves the Autonomous Exploration monitor interface."""
    def get(self):
        self.render("explorer.html")

class NavigationHandler(tornado.web.RequestHandler):
    """Serves the Auto Navigation interface."""
    def get(self):
        self.render("navigation.html")

class ListMapsHandler(tornado.web.RequestHandler):
    """API endpoint to list maps on the server."""
    def get(self):
        search_dirs = [
            "/workspaces/isaac_ros-dev/src/wheeltec_robot_nav2/map",
            "/home/ubuntu/workspaces/isaac_ros-dev/src/wheeltec_robot_nav2/map",
            "/home/ubuntu/maps"
        ]
        try:
            search_dirs.append(os.path.join(get_package_share_directory('wheeltec_nav2'), 'map'))
        except Exception:
            pass

        maps = set()
        for d in search_dirs:
            if os.path.exists(d):
                for file in os.listdir(d):
                    if file.endswith(".yaml"):
                        maps.add(file[:-5])  # Remove .yaml
        self.write(json.dumps({"maps": sorted(list(maps))}))


class WSHandler(tornado.websocket.WebSocketHandler):
    def check_origin(self, origin):
        return True

    def open(self):
        self.mode = "exploration"  # default mode
        websocket_clients.add(self)
        ros_node.get_logger().info("WebSocket client connected.")
        # Immediately send cached map data if available
        if latest_map_data is not None:
            self.write_message(json.dumps(latest_map_data))
        # Immediately send cached markers data if available
        if latest_markers_data is not None:
            self.write_message(json.dumps(latest_markers_data))
        # Immediately send cached status data if available
        if latest_status_data is not None:
            self.write_message(json.dumps(latest_status_data))

    def on_message(self, message):
        global latest_nav_map_data
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
                save_dir = get_map_dir()
                filepath = os.path.join(save_dir, filename)
                
                # Executing command to save the map
                cmd = ["ros2", "run", "nav2_map_server", "map_saver_cli", "-f", filepath]
                subprocess.Popen(cmd)  # Run in background so we don't block
                ros_node.get_logger().info(f"Saving map to {filepath}...")
            elif msg_type == "reset_map":
                # Clear cached map and markers data immediately
                global latest_map_data, latest_markers_data
                latest_map_data = None
                latest_markers_data = None
                
                # Reset exploration node first by publishing reset command
                msg = String()
                msg.data = "reset"
                ros_node.explorer_pub.publish(msg)
                ros_node.get_logger().info("Sent reset command to exploration node.")
                
                # Call slam_toolbox reset service natively
                ros_node.call_reset_map()
                ros_node.get_logger().info("Reset map command sent to slam_toolbox.")
            elif msg_type == "exploration_cmd":
                # Send control commands to explorer node
                command = data.get("command")
                msg = String()
                msg.data = str(command)
                ros_node.explorer_pub.publish(msg)
                ros_node.get_logger().info(f"Published exploration command: '{command}'")
            elif msg_type == "set_mode":
                self.mode = data.get("mode", "exploration")
                ros_node.get_logger().info(f"WebSocket client mode set to: {self.mode}")
                if self.mode == "navigation":
                    if latest_nav_map_data is not None:
                        self.write_message(json.dumps(latest_nav_map_data))
                    # Send current target and state
                    if ros_node.nav_target is not None:
                        self.write_message(json.dumps({
                            "type": "nav_target",
                            "x": ros_node.nav_target[0],
                            "y": ros_node.nav_target[1],
                            "status": ros_node.nav_state
                        }))
            elif msg_type == "load_map":
                map_name = data.get("map_name")
                yaml_path = get_map_yaml_path(map_name)
                ros_node.get_logger().info(f"Request to load static map: {yaml_path}")
                if yaml_path and os.path.exists(yaml_path):
                    try:
                        latest_nav_map_data = load_map_from_disk(yaml_path)
                        # Broadcast map to all navigation clients
                        for client in list(websocket_clients):
                            if getattr(client, "mode", "exploration") == "navigation":
                                client.write_message(json.dumps(latest_nav_map_data))
                    except Exception as e:
                        ros_node.get_logger().error(f"Error loading map from disk: {e}")
            elif msg_type == "set_nav_target":
                x = data.get("x")
                y = data.get("y")
                ros_node.nav_target = (x, y)
                ros_node.plan_fallback_path()
                # Broadcast target to all navigation clients
                safe_broadcast({
                    "type": "nav_target",
                    "x": x,
                    "y": y,
                    "status": ros_node.nav_state
                })
            elif msg_type == "clear_nav_target":
                ros_node.nav_target = None
                ros_node.cancel_nav_goal()
                ros_node.nav_state = 'IDLE'
                ros_node.publish_twist(0.0, 0.0, 0.0)
                safe_broadcast({
                    "type": "nav_target",
                    "x": None,
                    "y": None,
                    "status": "IDLE"
                })
            elif msg_type == "start_nav":
                if ros_node.nav_target is not None:
                    ros_node.start_navigation(ros_node.nav_target[0], ros_node.nav_target[1])
                    safe_broadcast({
                        "type": "nav_target",
                        "x": ros_node.nav_target[0],
                        "y": ros_node.nav_target[1],
                        "status": "NAVIGATING"
                    })
            elif msg_type == "pause_nav":
                ros_node.nav_state = 'PAUSED'
                ros_node.cancel_nav_goal()
                ros_node.publish_twist(0.0, 0.0, 0.0)
                safe_broadcast({
                    "type": "nav_target",
                    "x": ros_node.nav_target[0] if ros_node.nav_target else None,
                    "y": ros_node.nav_target[1] if ros_node.nav_target else None,
                    "status": "PAUSED"
                })
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
    global ros_node, main_loop
    main_loop = tornado.ioloop.IOLoop.current()
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
        (r"/teleop", TeleopHandler),
        (r"/explorer", ExplorerHandler),
        (r"/navigation", NavigationHandler),
        (r"/ws", WSHandler),
        (r"/api/download_map", DownloadMapHandler),
        (r"/api/list_maps", ListMapsHandler),
        (r"/static/(.*)", tornado.web.StaticFileHandler, {"path": static_path}),
    ], template_path=template_path)
    
    # Start web server on port 8080 (listens on all interfaces)
    app.listen(8080)
    ros_node.get_logger().info("Web server started at http://0.0.0.0:8080")
    
    try:
        main_loop.start()
    except KeyboardInterrupt:
        pass
    finally:
        rclpy.shutdown()
        spin_thread.join()

if __name__ == '__main__':
    main()
