#!/usr/bin/env python3

import math
from collections import deque
import json

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy

from geometry_msgs.msg import Twist, Point
from nav_msgs.msg import OccupancyGrid
from sensor_msgs.msg import LaserScan
from std_msgs.msg import String
from visualization_msgs.msg import Marker, MarkerArray
import tf2_ros

def normalize_angle(angle):
    """Normalize angle to [-pi, pi]."""
    while angle > math.pi:
        angle -= 2.0 * math.pi
    while angle < -math.pi:
        angle += 2.0 * math.pi
    return angle

class AutoExplorerNode(Node):
    """
    ROS2 Node for Autonomous Map Exploration.
    Subscribes to:
      - /map (OccupancyGrid)
      - /scan (LaserScan)
      - /exploration_control (String)
    Publishes:
      - /cmd_vel (Twist)
      - /exploration_markers (MarkerArray)
      - /exploration_status (String JSON)
    Listens to:
      - tf from map_frame to robot_frame
    """
    def __init__(self):
        super().__init__('auto_explorer')
        
        # Declare parameters with sensible defaults
        self.declare_parameter('map_frame', 'map')
        self.declare_parameter('robot_frame', 'base_link')
        self.declare_parameter('min_frontier_size', 5)
        self.declare_parameter('linear_speed_max', 0.25)
        self.declare_parameter('angular_speed_max', 0.7)
        self.declare_parameter('obstacle_safety_dist', 0.6)
        self.declare_parameter('obstacle_critical_dist', 0.35)
        self.declare_parameter('min_dist_to_target', 0.4)
        self.declare_parameter('max_target_time', 25.0)  # seconds
        self.declare_parameter('control_rate', 10.0)      # Hz
        self.declare_parameter('robot_radius', 0.30)      # meters (inflates obstacles for frontiers)
        self.declare_parameter('max_exploration_laps', 1)  # number of passes to make before completing
        
        # Get parameters
        self.map_frame = self.get_parameter('map_frame').value
        self.robot_frame = self.get_parameter('robot_frame').value
        self.min_frontier_size = self.get_parameter('min_frontier_size').value
        self.linear_speed_max = self.get_parameter('linear_speed_max').value
        self.angular_speed_max = self.get_parameter('angular_speed_max').value
        self.obstacle_safety_dist = self.get_parameter('obstacle_safety_dist').value
        self.obstacle_critical_dist = self.get_parameter('obstacle_critical_dist').value
        self.min_dist_to_target = self.get_parameter('min_dist_to_target').value
        self.max_target_time = self.get_parameter('max_target_time').value
        self.control_rate = self.get_parameter('control_rate').value
        self.robot_radius = self.get_parameter('robot_radius').value
        self.max_exploration_laps = self.get_parameter('max_exploration_laps').value
        
        self.get_logger().info(
            f"auto_explorer node started with parameters:\n"
            f"  map_frame: {self.map_frame}\n"
            f"  robot_frame: {self.robot_frame}\n"
            f"  min_frontier_size: {self.min_frontier_size}\n"
            f"  linear_speed_max: {self.linear_speed_max} m/s\n"
            f"  angular_speed_max: {self.angular_speed_max} rad/s\n"
            f"  robot_radius (inflation): {self.robot_radius} m\n"
            f"  max_exploration_laps: {self.max_exploration_laps}"
        )
        
        # QoS setup for OccupancyGrid (reliable & transient local)
        map_qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            durability=DurabilityPolicy.TRANSIENT_LOCAL
        )
        
        # QoS setup for LaserScan (best effort)
        scan_qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=5
        )
        
        # TF2 Setup to query robot's current pose in the map frame
        self.tf_buffer = tf2_ros.Buffer()
        self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self)
        
        # Subscriptions
        self.map_sub = self.create_subscription(
            OccupancyGrid, '/map', self.map_callback, map_qos
        )
        self.scan_sub = self.create_subscription(
            LaserScan, '/scan', self.scan_callback, scan_qos
        )
        self.control_sub = self.create_subscription(
            String, '/exploration_control', self.control_callback, 10
        )
        
        # Publishers
        self.cmd_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        self.marker_pub = self.create_publisher(MarkerArray, '/exploration_markers', 10)
        self.status_pub = self.create_publisher(String, '/exploration_status', 10)
        
        # Internal state variables
        self.map_data = None
        self.scan_data = None
        self.centroids = []
        self.current_target = None
        self.cached_path = None
        self.last_path_plan_time = 0.0
        
        # Laps and Paused states
        self.is_paused = True  # Safety default: starts paused
        self.current_lap = 1
        self.exploration_complete = False
        
        # Target timeout & stuck detection variables
        self.blacklist = []  # List of blacklisted targets (x, y)
        self.target_start_time = None
        
        self.last_robot_pos = None
        self.last_robot_yaw = None
        self.last_robot_pos_time = None
        
        # Control loop timer
        self.control_timer = self.create_timer(1.0 / self.control_rate, self.control_loop)
        # Status publish timer (1Hz)
        self.status_timer = self.create_timer(1.0, self.publish_status)

    def map_callback(self, msg):
        """Callback triggered when a new occupancy grid map is published."""
        self.map_data = msg
        self.find_frontiers()

    def scan_callback(self, msg):
        """Callback triggered when a new LaserScan message is published."""
        self.scan_data = msg

    def control_callback(self, msg):
        """Callback to handle commands from the exploration_control topic."""
        cmd = msg.data.strip().lower()
        self.get_logger().info(f"Received control command: '{cmd}'")
        
        if cmd == 'start' or cmd == 'resume':
            self.is_paused = False
            self.exploration_complete = False
            self.get_logger().info("Exploration Started/Resumed.")
        elif cmd == 'pause':
            self.is_paused = True
            self.stop_robot()
            self.get_logger().info("Exploration Paused.")
        elif cmd == 'stop':
            self.is_paused = True
            self.exploration_complete = True
            self.stop_robot()
            self.get_logger().info("Exploration Stopped / Interrupted.")
        elif cmd == 'reset':
            self.is_paused = True
            self.exploration_complete = False
            self.current_lap = 1
            self.blacklist.clear()
            self.current_target = None
            self.cached_path = None
            self.last_path_plan_time = 0.0
            self.last_robot_pos = None
            self.last_robot_yaw = None
            self.stop_robot()
            self.get_logger().info("Exploration Reset.")
        elif cmd.startswith('set_laps:'):
            try:
                laps = int(cmd.split(':')[1])
                self.max_exploration_laps = max(1, laps)
                self.get_logger().info(f"Dynamic lap count set to: {self.max_exploration_laps}")
            except Exception as e:
                self.get_logger().error(f"Failed to parse set_laps command: {e}")
        self.publish_status()

    def publish_status(self):
        """Publishes node state as a JSON string to /exploration_status."""
        try:
            status_json = {
                "is_paused": self.is_paused,
                "current_lap": self.current_lap,
                "max_exploration_laps": self.max_exploration_laps,
                "exploration_complete": self.exploration_complete,
                "blacklist_count": len(self.blacklist),
                "robot_radius": self.robot_radius
            }
            msg = String()
            msg.data = json.dumps(status_json)
            self.status_pub.publish(msg)
        except Exception as e:
            self.get_logger().error(f"Error publishing status: {e}")

    def find_frontiers(self):
        """
        Parses the occupancy grid map to identify frontier cells.
        Groups adjacent frontier cells into clusters and calculates their centroids.
        """
        if self.map_data is None:
            return
            
        grid = self.map_data
        width = grid.info.width
        height = grid.info.height
        resolution = grid.info.resolution
        origin_x = grid.info.origin.position.x
        origin_y = grid.info.origin.position.y
        data = grid.data
        
        # Step 1: Identify free space cells (value == 0)
        free_indices = [i for i, val in enumerate(data) if val == 0]
        
        frontier_cells = []
        
        # Precalculate neighbor offsets on a 1D grid representation
        offsets = [
            -width - 1, -width, -width + 1,
            -1,                  1,
            width - 1,  width,  width + 1
        ]
        
        # Grid cell radius for inflation based on robot footprint
        cell_radius = int(math.ceil(self.robot_radius / resolution))
        
        # Step 2: Extract frontier cells (free cells next to at least one unknown (-1) neighbor)
        # We perform an inflation check to ensure no occupied cells fall within the robot's physical radius
        for idx in free_indices:
            y = idx // width
            x = idx % width
            
            # Skip boundary cells of the grid to prevent out-of-bounds neighbor checks
            if x <= cell_radius or x >= width - 1 - cell_radius or y <= cell_radius or y >= height - 1 - cell_radius:
                continue
                
            has_unknown = False
            near_obstacle = False
            
            # Check 8 neighbors for unknown space first (fast pass)
            for offset in offsets:
                val = data[idx + offset]
                if val == -1:
                    has_unknown = True
                    break
            
            if not has_unknown:
                continue
                
            # Perform radial obstacle inflation check (circle boundary checking)
            for dx in range(-cell_radius, cell_radius + 1):
                for dy in range(-cell_radius, cell_radius + 1):
                    # Keep it strictly inside the circle
                    if dx*dx + dy*dy <= cell_radius*cell_radius:
                        nx = x + dx
                        ny = y + dy
                        if data[ny * width + nx] > 50:
                            near_obstacle = True
                            break
                if near_obstacle:
                    break
                    
            if not near_obstacle:
                frontier_cells.append((x, y))
                
        if not frontier_cells:
            self.centroids = []
            self.publish_markers()
            return
            
        # Step 3: Cluster frontier cells using Breadth-First Search (BFS)
        frontier_set = set(frontier_cells)
        visited = set()
        clusters = []
        
        for cell in frontier_cells:
            if cell in visited:
                continue
                
            cluster = []
            queue = deque([cell])
            visited.add(cell)
            
            while queue:
                curr = queue.popleft()
                cluster.append(curr)
                
                cx, cy = curr
                # Scan 8-connected neighbors
                for dx in [-1, 0, 1]:
                    for dy in [-1, 0, 1]:
                        if dx == 0 and dy == 0:
                            continue
                        neighbor = (cx + dx, cy + dy)
                        if neighbor in frontier_set and neighbor not in visited:
                            visited.add(neighbor)
                            queue.append(neighbor)
                            
            if len(cluster) >= self.min_frontier_size:
                clusters.append(cluster)
                
        # Step 4: Calculate the spatial centroid of each valid cluster (in the map frame)
        new_centroids = []
        for cluster in clusters:
            sum_x = 0.0
            sum_y = 0.0
            for cx, cy in cluster:
                # Convert grid coordinate to world coordinates
                mx = origin_x + (cx + 0.5) * resolution
                my = origin_y + (cy + 0.5) * resolution
                sum_x += mx
                sum_y += my
            new_centroids.append((sum_x / len(cluster), sum_y / len(cluster)))
            
        self.centroids = new_centroids
        self.publish_markers()

    def plan_path(self, start_world, end_world):
        """
        Plans a path from start_world (x, y) to end_world (x, y) using BFS on the map.
        Tries with decreasing inflation radii to ensure a path is found.
        """
        if self.map_data is None:
            return None
            
        grid = self.map_data
        width = grid.info.width
        height = grid.info.height
        resolution = grid.info.resolution
        origin_x = grid.info.origin.position.x
        origin_y = grid.info.origin.position.y
        data = grid.data
        
        # Convert world coordinates to grid coordinates
        def world_to_grid(wx, wy):
            gx = int((wx - origin_x) / resolution)
            gy = int((wy - origin_y) / resolution)
            return gx, gy
            
        def grid_to_world(gx, gy):
            wx = origin_x + (gx + 0.5) * resolution
            wy = origin_y + (gy + 0.5) * resolution
            return wx, wy
            
        start_g = world_to_grid(start_world[0], start_world[1])
        end_g = world_to_grid(end_world[0], end_world[1])
        
        # Check bounds
        if not (0 <= start_g[0] < width and 0 <= start_g[1] < height):
            return None
        if not (0 <= end_g[0] < width and 0 <= end_g[1] < height):
            return None
            
        cell_radius = int(math.ceil(self.robot_radius / resolution))
        
        # Try planning with different inflation radii: full, half, none
        for inflation_radius in [max(1, cell_radius - 1), max(1, cell_radius // 2), 0]:
            # BFS search
            queue = deque([start_g])
            parent = {start_g: None}
            visited = {start_g}
            found = False
            
            while queue:
                curr = queue.popleft()
                if curr == end_g:
                    found = True
                    break
                    
                cx, cy = curr
                for dx, dy in [(-1,0), (1,0), (0,-1), (0,1), (-1,-1), (-1,1), (1,-1), (1,1)]:
                    nx, ny = cx + dx, cy + dy
                    neighbor = (nx, ny)
                    
                    if 0 <= nx < width and 0 <= ny < height and neighbor not in visited:
                        val = data[ny * width + nx]
                        # 0 is free, -1 is unknown. Let's allow <= 50.
                        if val <= 50:
                            # Inflation check
                            near_obstacle = False
                            if inflation_radius > 0:
                                for idx_x in range(-inflation_radius, inflation_radius + 1):
                                    for idx_y in range(-inflation_radius, inflation_radius + 1):
                                        if idx_x*idx_x + idx_y*idx_y <= inflation_radius*inflation_radius:
                                            ox = nx + idx_x
                                            oy = ny + idx_y
                                            if 0 <= ox < width and 0 <= oy < height:
                                                if data[oy * width + ox] > 50:
                                                    near_obstacle = True
                                                    break
                                    if near_obstacle:
                                        break
                                        
                            if not near_obstacle:
                                visited.add(neighbor)
                                parent[neighbor] = curr
                                queue.append(neighbor)
            
            if found:
                # Reconstruct path
                curr = end_g
                path = []
                while curr is not None:
                    path.append(grid_to_world(curr[0], curr[1]))
                    curr = parent[curr]
                path.reverse()
                return path
                
        # If no path found even with 0 inflation, return None
        return None

    def control_loop(self):
        """
        Main control loop running at control_rate.
        Calculates reactive potential field and commands the robot via cmd_vel.
        """
        # Ensure sensor data has arrived
        if self.map_data is None:
            self.get_logger().info("Waiting for map data...", throttle_duration_sec=5.0)
            self.stop_robot()
            return
            
        if self.scan_data is None:
            self.get_logger().info("Waiting for laser scan data...", throttle_duration_sec=5.0)
            self.stop_robot()
            return
            
        # Respect paused state
        if self.is_paused:
            self.get_logger().info("Exploration is PAUSED. Standing by.", throttle_duration_sec=5.0)
            self.stop_robot()
            return

        if self.exploration_complete:
            self.get_logger().info("Exploration complete. Standing by.", throttle_duration_sec=10.0)
            self.stop_robot()
            return

        # Query the robot's current position in the map coordinate frame
        try:
            now = rclpy.time.Time()
            trans = self.tf_buffer.lookup_transform(
                self.map_frame,
                self.robot_frame,
                now,
                timeout=rclpy.duration.Duration(seconds=0.1)
            )
            robot_x = trans.transform.translation.x
            robot_y = trans.transform.translation.y
            
            # Quaternion to yaw
            q = trans.transform.rotation
            siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
            cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
            robot_yaw = math.atan2(siny_cosp, cosy_cosp)
            
        except Exception as e:
            self.get_logger().warn(
                f"TF Lookup failed from {self.map_frame} to {self.robot_frame}: {e}",
                throttle_duration_sec=3.0
            )
            self.stop_robot()
            return

        # Filter out frontier centroids close to blacklisted coordinates
        valid_centroids = []
        for c in self.centroids:
            is_blacklisted = False
            for bx, by in self.blacklist:
                if math.hypot(c[0] - bx, c[1] - by) < 1.0:  # 1.0m blacklist tolerance
                    is_blacklisted = True
                    break
            if not is_blacklisted:
                valid_centroids.append(c)

        # Clear blacklist if all discovered are blacklisted, so we can retry and refine
        if not valid_centroids and self.centroids:
            self.get_logger().info("All discovered frontiers are blacklisted. Clearing blacklist to retry...")
            self.blacklist.clear()
            valid_centroids = self.centroids

        # Handle completion of exploration (or completion of the current lap)
        if not valid_centroids:
            if self.current_lap < self.max_exploration_laps:
                self.get_logger().info(
                    f"Exploration lap {self.current_lap}/{self.max_exploration_laps} complete. "
                    f"Clearing blacklist to start map refinement lap {self.current_lap + 1}..."
                )
                self.current_lap += 1
                self.blacklist.clear()
                self.current_target = None
                self.stop_robot()
                self.publish_markers()
                self.publish_status()
                return
            else:
                self.get_logger().info("Exploration Complete! All laps completed. No frontiers found.", throttle_duration_sec=5.0)
                self.exploration_complete = True
                self.current_target = None
                self.stop_robot()
                self.publish_markers()
                self.publish_status()
                return

        # Select the nearest centroid as the active target
        closest_centroid = None
        min_dist = float('inf')
        for c in valid_centroids:
            dist = math.hypot(c[0] - robot_x, c[1] - robot_y)
            if dist < min_dist:
                min_dist = dist
                closest_centroid = c

        current_time_sec = self.get_clock().now().nanoseconds / 1e9

        # Target change detection & tracking initialization
        if self.current_target is None or math.hypot(self.current_target[0] - closest_centroid[0], self.current_target[1] - closest_centroid[1]) > 0.8:
            self.current_target = closest_centroid
            self.cached_path = None  # Force path replanning
            self.target_start_time = current_time_sec
            self.last_robot_pos = (robot_x, robot_y)
            self.last_robot_yaw = robot_yaw
            self.last_robot_pos_time = current_time_sec
            self.get_logger().info(f"Target selected: ({self.current_target[0]:.2f}, {self.current_target[1]:.2f}) - Distance: {min_dist:.2f}m (Lap {self.current_lap}/{self.max_exploration_laps})")

        # Stuck and Timeout detection
        # 1. Target Timeout
        if current_time_sec - self.target_start_time > self.max_target_time:
            self.get_logger().warn(f"Target timeout! Blacklisting target at ({self.current_target[0]:.2f}, {self.current_target[1]:.2f})")
            self.blacklist.append(self.current_target)
            self.current_target = None
            self.cached_path = None
            self.stop_robot()
            return

        # 2. Stuck detection (no progress made in 3 seconds while trying to reach a target)
        if self.last_robot_pos is not None:
            dt = current_time_sec - self.last_robot_pos_time
            if dt >= 3.0:
                dist_moved = math.hypot(robot_x - self.last_robot_pos[0], robot_y - self.last_robot_pos[1])
                # Calculate angle turned (accounting for wrap-around)
                yaw_diff = abs(robot_yaw - self.last_robot_yaw)
                yaw_diff = min(yaw_diff, 2 * math.pi - yaw_diff)
                
                # Only declare stuck if BOTH translation and rotation are minimal
                if dist_moved < 0.15 and yaw_diff < 0.2:
                    self.get_logger().warn(f"Robot stuck! (Moved {dist_moved:.2f}m, turned {yaw_diff:.2f}rad in {dt:.1f}s). Blacklisting target.")
                    self.blacklist.append(self.current_target)
                    self.current_target = None
                    self.cached_path = None
                    self.stop_robot()
                    return
                self.last_robot_pos = (robot_x, robot_y)
                self.last_robot_yaw = robot_yaw
                self.last_robot_pos_time = current_time_sec

        # Target reached check
        dist_to_target = math.hypot(self.current_target[0] - robot_x, self.current_target[1] - robot_y)
        if dist_to_target < self.min_dist_to_target:
            self.get_logger().info(f"Reached target at ({self.current_target[0]:.2f}, {self.current_target[1]:.2f})!")
            self.blacklist.append(self.current_target)
            self.current_target = None
            self.cached_path = None
            self.stop_robot()
            return

        # --- BFS Path Planning and Look-Ahead Waypoint Selection ---
        # Replan path if cached path is None, or if 1.0s elapsed
        should_replan = (self.cached_path is None or 
                         current_time_sec - self.last_path_plan_time > 1.0)
                         
        if should_replan and self.current_target is not None:
            self.cached_path = self.plan_path((robot_x, robot_y), self.current_target)
            self.last_path_plan_time = current_time_sec
            if self.cached_path is None:
                self.get_logger().warn(f"No path found to target at ({self.current_target[0]:.2f}, {self.current_target[1]:.2f})! Blacklisting it.")
                self.blacklist.append(self.current_target)
                self.current_target = None
                self.stop_robot()
                return

        # Find look-ahead waypoint on the path
        local_target = self.current_target
        if self.cached_path:
            look_ahead_dist = 0.5  # meters
            for pt in self.cached_path:
                if math.hypot(pt[0] - robot_x, pt[1] - robot_y) > look_ahead_dist:
                    local_target = pt
                    break
            else:
                local_target = self.cached_path[-1]

        # --- Artificial Potential Field Calculation ---
        # 1. Attractive force in robot's local frame pointing to local_target
        dx = local_target[0] - robot_x
        dy = local_target[1] - robot_y
        
        # Transform goal vector to robot local frame (X-forward, Y-left)
        local_x = dx * math.cos(robot_yaw) + dy * math.sin(robot_yaw)
        local_y = -dx * math.sin(robot_yaw) + dy * math.cos(robot_yaw)
        
        dist = math.hypot(local_x, local_y)
        if dist > 0.01:
            att_x = local_x / dist
            att_y = local_y / dist
        else:
            att_x = 0.0
            att_y = 0.0

        # 2. Repulsive force in robot's local frame
        rep_x = 0.0
        rep_y = 0.0
        min_forward_range = float('inf')
        
        scan = self.scan_data
        angle_min = scan.angle_min
        angle_increment = scan.angle_increment
        
        for i, r in enumerate(scan.ranges):
            if not math.isfinite(r) or r <= 0.0:
                continue
                
            angle = angle_min + i * angle_increment
            
            # Check forward sector (-45 deg to 45 deg) for emergency stop
            if -math.pi / 4.0 <= angle <= math.pi / 4.0:
                if r < min_forward_range:
                    min_forward_range = r
            
            # Repulsion if obstacle is inside safety distance
            if r < self.obstacle_safety_dist:
                k_rep = 0.05
                mag = k_rep * (1.0 / r - 1.0 / self.obstacle_safety_dist) / (r * r)
                # Force direction away from obstacle
                rep_x += mag * (-math.cos(angle))
                rep_y += mag * (-math.sin(angle))

        # --- Motion Command Selection ---
        twist = Twist()
        
        if min_forward_range < self.obstacle_critical_dist:
            # Safety escape maneuver (obstacle too close in front)
            self.get_logger().warn(
                f"Obstacle critical! Distance: {min_forward_range:.2f}m. Executing backup and turn.",
                throttle_duration_sec=1.0
            )
            
            # Check if we can safely back up (clearance behind the robot)
            min_backward_range = float('inf')
            for i, r in enumerate(scan.ranges):
                if not math.isfinite(r) or r <= 0.0:
                    continue
                angle = angle_min + i * angle_increment
                if angle > 3.0 * math.pi / 4.0 or angle < -3.0 * math.pi / 4.0:
                    if r < min_backward_range:
                        min_backward_range = r
            
            if min_backward_range < self.obstacle_critical_dist:
                twist.linear.x = 0.0  # Cannot back up, rotate in place
            else:
                twist.linear.x = -0.05  # Back up slightly
            
            # Check left vs right average clearance to decide turn direction
            left_ranges = []
            right_ranges = []
            for i, r in enumerate(scan.ranges):
                if not math.isfinite(r) or r <= 0.0:
                    continue
                angle = angle_min + i * angle_increment
                if 0.0 < angle <= math.pi / 3.0:
                    left_ranges.append(r)
                elif -math.pi / 3.0 <= angle < 0.0:
                    right_ranges.append(r)
            
            left_avg = sum(left_ranges) / len(left_ranges) if left_ranges else 0.0
            right_avg = sum(right_ranges) / len(right_ranges) if right_ranges else 0.0
            
            if left_avg > right_avg:
                twist.angular.z = self.angular_speed_max
            else:
                twist.angular.z = -self.angular_speed_max
                
        else:
            # Combine forces
            tot_x = att_x + rep_x
            tot_y = att_y + rep_y
            
            # Target heading angle in local frame
            phi = math.atan2(tot_y, tot_x)
            
            if abs(phi) > math.pi / 2.0:
                # Rotate in place if the target steering direction is behind the robot
                twist.linear.x = 0.0
                twist.angular.z = self.angular_speed_max if phi > 0.0 else -self.angular_speed_max
            else:
                # Drive forward and steer towards target direction
                twist.linear.x = self.linear_speed_max * math.cos(phi)
                
                # Slow down as target is approached
                dist_factor = min(1.0, dist_to_target / 1.0)
                twist.linear.x *= dist_factor
                
                # Slow down when making sharp adjustments
                twist.linear.x *= (1.0 - abs(phi) / (math.pi / 2.0))
                
                # ALSO slow down when obstacles are close in the forward sector!
                if min_forward_range < self.obstacle_safety_dist:
                    # Scale speed down as obstacle gets closer to critical distance
                    range_factor = (min_forward_range - self.obstacle_critical_dist) / (self.obstacle_safety_dist - self.obstacle_critical_dist)
                    range_factor = max(0.0, min(1.0, range_factor))
                    twist.linear.x *= range_factor
                    
                twist.linear.x = max(0.02, twist.linear.x)  # Maintain minimum forward progress
                
                # Proportional steering control
                twist.angular.z = 1.5 * phi
                twist.angular.z = max(-self.angular_speed_max, min(self.angular_speed_max, twist.angular.z))

        self.cmd_pub.publish(twist)
        self.publish_markers()

    def stop_robot(self):
        """Publishes a zero velocity command to bring the robot to a stop."""
        twist = Twist()
        twist.linear.x = 0.0
        twist.angular.z = 0.0
        self.cmd_pub.publish(twist)

    def publish_markers(self):
        """Publishes visualization markers of frontiers and targets for RViz."""
        marker_array = MarkerArray()
        
        # Clear previous markers
        clear_marker = Marker()
        clear_marker.action = Marker.DELETEALL
        marker_array.markers.append(clear_marker)
        
        # 1. Centroids (Green Spheres)
        if self.centroids:
            centroids_marker = Marker()
            centroids_marker.header.frame_id = self.map_frame
            centroids_marker.header.stamp = self.get_clock().now().to_msg()
            centroids_marker.ns = "centroids"
            centroids_marker.id = 0
            centroids_marker.type = Marker.SPHERE_LIST
            centroids_marker.action = Marker.ADD
            centroids_marker.scale.x = 0.25
            centroids_marker.scale.y = 0.25
            centroids_marker.scale.z = 0.25
            centroids_marker.color.r = 0.0
            centroids_marker.color.g = 1.0
            centroids_marker.color.b = 0.0
            centroids_marker.color.a = 0.8
            
            for pt in self.centroids:
                p = Point()
                p.x = pt[0]
                p.y = pt[1]
                p.z = 0.05
                centroids_marker.points.append(p)
                
            marker_array.markers.append(centroids_marker)
            
        # 2. Selected Target Centroid (Large Blue Sphere)
        if self.current_target:
            target_marker = Marker()
            target_marker.header.frame_id = self.map_frame
            target_marker.header.stamp = self.get_clock().now().to_msg()
            target_marker.ns = "target"
            target_marker.id = 1
            target_marker.type = Marker.SPHERE
            target_marker.action = Marker.ADD
            target_marker.pose.position.x = self.current_target[0]
            target_marker.pose.position.y = self.current_target[1]
            target_marker.pose.position.z = 0.15
            target_marker.scale.x = 0.4
            target_marker.scale.y = 0.4
            target_marker.scale.z = 0.4
            target_marker.color.r = 0.0
            target_marker.color.g = 0.5
            target_marker.color.b = 1.0
            target_marker.color.a = 1.0
            
            marker_array.markers.append(target_marker)
            
        self.marker_pub.publish(marker_array)

def main(args=None):
    rclpy.init(args=args)
    node = AutoExplorerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info("Keyboard Interrupt. Shutting down auto_explorer node...")
    finally:
        node.stop_robot()
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
