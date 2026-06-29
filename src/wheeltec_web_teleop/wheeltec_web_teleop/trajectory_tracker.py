import rclpy
from rclpy.node import Node
from nav_msgs.msg import Odometry
from std_msgs.msg import String
from std_srvs.srv import Trigger
from tf2_ros.buffer import Buffer
from tf2_ros.transform_listener import TransformListener
import json
import math
import time

class TrajectoryTracker(Node):
    def __init__(self):
        super().__init__('trajectory_tracker')
        
        # Publisher for trajectory path
        self.pub_trajectory = self.create_publisher(String, '/robot_trajectory', 10)
        
        # Subscriber for odom to get speed
        self.latest_speed = 0.0
        self.sub_odom = self.create_subscription(
            Odometry,
            'odom',
            self.odom_callback,
            10
        )
        
        # Transform listener to query robot pose
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)
        
        # Trajectory storage: list of (timestamp, x, y, speed)
        self.trajectory = []
        
        # Distance threshold to add new point (avoid duplicate points when robot is static)
        self.min_dist_threshold = 0.05  # 5 cm
        
        # Service to export trajectory
        self.srv_export = self.create_service(Trigger, '/export_trajectory', self.export_callback)
        
        # Service to reset trajectory
        self.srv_reset = self.create_service(Trigger, '/reset_trajectory', self.reset_callback)
        
        # Timer to update trajectory (5Hz)
        self.create_timer(0.2, self.update_trajectory)
        
        # Timer to publish trajectory (1Hz) to reduce network load
        self.create_timer(1.0, self.publish_trajectory)
        
        self.get_logger().info("Trajectory Tracker Node initialized.")

    def odom_callback(self, msg):
        vx = msg.twist.twist.linear.x
        vy = msg.twist.twist.linear.y
        self.latest_speed = math.sqrt(vx**2 + vy**2)

    def update_trajectory(self):
        try:
            # Lookup latest transform map -> base_footprint (or base_link)
            try:
                trans = self.tf_buffer.lookup_transform('map', 'base_footprint', rclpy.time.Time())
            except Exception:
                try:
                    trans = self.tf_buffer.lookup_transform('map', 'base_link', rclpy.time.Time())
                except Exception:
                    return
            
            x = trans.transform.translation.x
            y = trans.transform.translation.y
            
            # Check if robot has moved enough
            if self.trajectory:
                last_pt = self.trajectory[-1]
                dist = math.hypot(x - last_pt[1], y - last_pt[2])
                # Only add if moved at least 5cm OR speed is non-zero and enough time passed
                if dist < self.min_dist_threshold:
                    return
            
            timestamp = time.time()
            # Maintain maximum trajectory size of 3000 to prevent performance degradation
            if len(self.trajectory) >= 3000:
                self.trajectory.pop(0)
                
            self.trajectory.append((timestamp, x, y, self.latest_speed))
            
        except Exception as e:
            pass

    def publish_trajectory(self):
        if not self.trajectory:
            return
        # Prepare list for Web UI: [x, y, speed] to keep JSON small
        pts = [[pt[1], pt[2], pt[3]] for pt in self.trajectory]
        msg = String()
        msg.data = json.dumps(pts)
        self.pub_trajectory.publish(msg)

    def export_callback(self, request, response):
        self.get_logger().info("Export trajectory service called.")
        try:
            # Generate CSV string
            csv_lines = ["timestamp,x,y,speed"]
            for pt in self.trajectory:
                csv_lines.append(f"{pt[0]:.2f},{pt[1]:.4f},{pt[2]:.4f},{pt[3]:.4f}")
            csv_content = "\n".join(csv_lines)
            
            response.success = True
            response.message = csv_content
        except Exception as e:
            response.success = False
            response.message = f"Error generating trajectory file: {str(e)}"
        return response

    def reset_callback(self, request, response):
        self.get_logger().info("Reset trajectory service called.")
        try:
            self.trajectory = []
            # Publish empty trajectory to update web canvas immediately
            msg = String()
            msg.data = json.dumps([])
            self.pub_trajectory.publish(msg)
            response.success = True
            response.message = "Trajectory reset successful."
        except Exception as e:
            response.success = False
            response.message = f"Error resetting trajectory: {str(e)}"
        return response

def main(args=None):
    rclpy.init(args=args)
    node = TrajectoryTracker()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
