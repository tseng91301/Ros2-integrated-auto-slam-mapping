#!/usr/bin/env python3

import math
from collections import deque
import json
import random
import subprocess
import os
import numpy as np

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy
from rclpy.action import ActionClient

from geometry_msgs.msg import Twist, Point, PoseStamped
from nav_msgs.msg import OccupancyGrid
from sensor_msgs.msg import LaserScan
from std_msgs.msg import String
from visualization_msgs.msg import Marker, MarkerArray
from nav2_msgs.action import NavigateToPose
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
    ROS2 Node for Autonomous Map Exploration implementing a 4-phase algorithm.
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
        self.declare_parameter('linear_speed_max', 0.20)
        self.declare_parameter('angular_speed_max', 0.6)
        self.declare_parameter('obstacle_safety_dist', 0.6)
        self.declare_parameter('obstacle_critical_dist', 0.35)
        self.declare_parameter('min_dist_to_target', 0.5)
        self.declare_parameter('control_rate', 10.0)      # Hz
        self.declare_parameter('robot_radius', 0.25)      # meters (inflates obstacles)
        self.declare_parameter('max_exploration_laps', 1)  # number of passes to make before completing
        self.declare_parameter('thumbtack_spacing', 0.5)   # meters
        self.declare_parameter('local_search_radius', 3.0) # meters
        
        # Get parameters
        self.map_frame = self.get_parameter('map_frame').value
        self.robot_frame = self.get_parameter('robot_frame').value
        self.linear_speed_max = self.get_parameter('linear_speed_max').value
        self.angular_speed_max = self.get_parameter('angular_speed_max').value
        self.obstacle_safety_dist = self.get_parameter('obstacle_safety_dist').value
        self.obstacle_critical_dist = self.get_parameter('obstacle_critical_dist').value
        self.min_dist_to_target = self.get_parameter('min_dist_to_target').value
        self.control_rate = self.get_parameter('control_rate').value
        self.robot_radius = self.get_parameter('robot_radius').value
        self.max_exploration_laps = self.get_parameter('max_exploration_laps').value
        self.thumbtack_spacing = self.get_parameter('thumbtack_spacing').value
        self.local_search_radius = self.get_parameter('local_search_radius').value
        
        self.get_logger().info(
            f"auto_explorer node started with 4-phase algorithm parameters:\n"
            f"  map_frame: {self.map_frame}\n"
            f"  robot_frame: {self.robot_frame}\n"
            f"  linear_speed_max: {self.linear_speed_max} m/s\n"
            f"  angular_speed_max: {self.angular_speed_max} rad/s\n"
            f"  robot_radius (inflation): {self.robot_radius} m\n"
            f"  thumbtack_spacing: {self.thumbtack_spacing} m\n"
            f"  local_search_radius: {self.local_search_radius} m"
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
        
        # Nav2 action client
        self.nav_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        
        # Internal algorithm states
        # States: 'INIT' (Phase 1), 'EXPLORE' (Phase 2), 'BACKTRACK' (Phase 3), 'COMPLETE' (Phase 4)
        self.state = 'INIT'
        self.thumbtack_pool = []
        
        self.map_data = None
        self.frontier_mask = None
        self.scan_data = None
        self.current_target = None
        
        # Navigating state for Phase 3
        self.is_navigating = False
        self.nav_goal_handle = None
        self.nav_goal_status = 'NONE' # 'NONE', 'PENDING', 'EXECUTING', 'FALLBACK'
        self.backtrack_target = None
        self.cached_path = None
        
        # Laps and Paused states
        self.is_paused = True  # Safety default: starts paused
        self.current_lap = 1
        self.exploration_complete = False
        
        # Control loop timer
        self.control_timer = self.create_timer(1.0 / self.control_rate, self.control_loop)
        # Status publish timer (1Hz)
        self.status_timer = self.create_timer(1.0, self.publish_status)

    def map_callback(self, msg):
        """Callback triggered when a new occupancy grid map is published."""
        self.map_data = msg
        
        # Process the map to populate and update the thumbtack pool
        width = msg.info.width
        height = msg.info.height
        resolution = msg.info.resolution
        origin_x = msg.info.origin.position.x
        origin_y = msg.info.origin.position.y
        data = msg.data
        
        map_np = np.array(data, dtype=np.int8).reshape((height, width))
        
        # Find new/all (0, -1) boundaries using fast numpy shifting
        free_mask = (map_np == 0)
        unknown_mask = (map_np == -1)
        
        any_unknown_neighbor = np.zeros_like(free_mask)
        any_unknown_neighbor[:-1, :] |= unknown_mask[1:, :]
        any_unknown_neighbor[1:, :] |= unknown_mask[:-1, :]
        any_unknown_neighbor[:, :-1] |= unknown_mask[:, 1:]
        any_unknown_neighbor[:, 1:] |= unknown_mask[:, :-1]
        
        frontier_mask = free_mask & any_unknown_neighbor
        self.frontier_mask = frontier_mask
        
        # Phase 1 / Real-time clearing: remove any thumbtack that is no longer on a frontier boundary
        updated_pool = []
        for tx, ty in self.thumbtack_pool:
            gx = int((tx - origin_x) / resolution)
            gy = int((ty - origin_y) / resolution)
            if 0 <= gx < width and 0 <= gy < height:
                if frontier_mask[gy, gx]:  # Keep if it is still a frontier
                    updated_pool.append((tx, ty))
            else:
                # Keep out-of-bounds thumbtacks just in case, or discard. Let's discard.
                pass
        self.thumbtack_pool = updated_pool
        
        gy_indices, gx_indices = np.where(frontier_mask)
        
        if len(gx_indices) > 0:
            wx = origin_x + (gx_indices + 0.5) * resolution
            wy = origin_y + (gy_indices + 0.5) * resolution
            
            candidates = list(zip(wx, wy))
            
            # Spatial downsampling using grid binning (cell size = thumbtack_spacing)
            spacing = self.thumbtack_spacing
            bins = {}
            for cx, cy in candidates:
                bin_key = (int(cx / spacing), int(cy / spacing))
                if bin_key not in bins:
                    bins[bin_key] = (cx, cy)
            downsampled_candidates = list(bins.values())
            
            # Safety obstacle check
            cell_radius = int(math.ceil(self.robot_radius / resolution))
            occupied = (map_np == 100)
            
            for cx, cy in downsampled_candidates:
                cgx = int((cx - origin_x) / resolution)
                cgy = int((cy - origin_y) / resolution)
                
                is_safe = True
                if 0 <= cgx < width and 0 <= cgy < height:
                    y_min = max(0, cgy - cell_radius)
                    y_max = min(height, cgy + cell_radius + 1)
                    x_min = max(0, cgx - cell_radius)
                    x_max = min(width, cgx + cell_radius + 1)
                    if np.any(occupied[y_min:y_max, x_min:x_max]):
                        is_safe = False
                else:
                    is_safe = False
                    
                if not is_safe:
                    continue
                    
                # Check distance to existing thumbtacks in pool
                too_close = False
                for tx, ty in self.thumbtack_pool:
                    if math.hypot(cx - tx, cy - ty) < spacing:
                        too_close = True
                        break
                if not too_close:
                    self.thumbtack_pool.append((cx, cy))
                    
        # State transitions out of INIT
        if self.state == 'INIT' and len(self.thumbtack_pool) > 0:
            self.state = 'EXPLORE'
            self.get_logger().info(f"Phase 1 complete. Initial thumbtack pool populated with {len(self.thumbtack_pool)} thumbtacks.")

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
            if self.state == 'COMPLETE':
                self.state = 'INIT'
            self.get_logger().info("Exploration Started/Resumed.")
        elif cmd == 'pause':
            self.is_paused = True
            self.stop_robot()
            self.cancel_nav_goal()
            self.get_logger().info("Exploration Paused.")
        elif cmd == 'stop':
            self.is_paused = True
            self.exploration_complete = True
            self.stop_robot()
            self.cancel_nav_goal()
            self.get_logger().info("Exploration Stopped / Interrupted.")
        elif cmd == 'reset':
            self.is_paused = True
            self.exploration_complete = False
            self.current_lap = 1
            self.thumbtack_pool.clear()
            self.current_target = None
            self.backtrack_target = None
            self.cached_path = None
            self.state = 'INIT'
            self.cancel_nav_goal()
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
                "blacklist_count": len(self.thumbtack_pool),  # mapped to pool size for UI count
                "robot_radius": self.robot_radius
            }
            msg = String()
            msg.data = json.dumps(status_json)
            self.status_pub.publish(msg)
        except Exception as e:
            self.get_logger().error(f"Error publishing status: {e}")

    def plan_path_to_nearest_thumbtack(self, robot_x, robot_y):
        """
        Finds the closest thumbtack in the pool and returns (target_thumbtack, path).
        Returns (None, None) if no reachable thumbtack is found.
        """
        if not self.thumbtack_pool or self.map_data is None:
            return None, None

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

        robot_g = world_to_grid(robot_x, robot_y)
        
        # Check bounds
        if not (0 <= robot_g[0] < width and 0 <= robot_g[1] < height):
            return None, None

        # Map thumbtack coordinates to grid coordinates and keep a reverse mapping
        thumbtack_grids = {}
        for tx, ty in self.thumbtack_pool:
            tg = world_to_grid(tx, ty)
            if 0 <= tg[0] < width and 0 <= tg[1] < height:
                thumbtack_grids[tg] = (tx, ty)

        if not thumbtack_grids:
            return None, None

        # Load occupancy data as 2D numpy array
        map_np = np.array(data, dtype=np.int8).reshape((height, width))

        # BFS search with varying inflation safety radii
        cell_radius = int(math.ceil(self.robot_radius / resolution))

        for inflation_radius in [max(1, cell_radius - 1), max(1, cell_radius // 2), 0]:
            # Generate traversability mask
            occupied = (map_np > 50)
            # Dilate obstacles
            if inflation_radius > 0:
                unsafe = occupied.copy()
                r = inflation_radius
                for dy in range(-r, r + 1):
                    for dx in range(-r, r + 1):
                        if dx*dx + dy*dy <= r*r:
                            if dy < 0:
                                y_src, y_dst = slice(-dy, None), slice(None, dy)
                            elif dy > 0:
                                y_src, y_dst = slice(None, -dy), slice(dy, None)
                            else:
                                y_src, y_dst = slice(None), slice(None)

                            if dx < 0:
                                x_src, x_dst = slice(-dx, None), slice(None, dx)
                            elif dx > 0:
                                x_src, x_dst = slice(None, -dx), slice(dx, None)
                            else:
                                x_src, x_dst = slice(None), slice(None)
                            unsafe[y_dst, x_dst] |= occupied[y_src, x_src]
            else:
                unsafe = occupied

            # Start BFS
            queue = deque([robot_g])
            parent = {robot_g: None}
            visited = {robot_g}
            found_tg = None

            while queue:
                curr = queue.popleft()
                if curr in thumbtack_grids:
                    found_tg = curr
                    break

                cx, cy = curr
                # 8 neighbors
                for dx, dy in [(-1,0), (1,0), (0,-1), (0,1), (-1,-1), (-1,1), (1,-1), (1,1)]:
                    nx, ny = cx + dx, cy + dy
                    neighbor = (nx, ny)

                    if 0 <= nx < width and 0 <= ny < height and neighbor not in visited:
                        # Cell must be free and not unsafe
                        if map_np[ny, nx] == 0 and not unsafe[ny, nx]:
                            visited.add(neighbor)
                            parent[neighbor] = curr
                            queue.append(neighbor)

            if found_tg is not None:
                # Reconstruct path
                path = []
                curr = found_tg
                while curr is not None:
                    path.append(grid_to_world(curr[0], curr[1]))
                    curr = parent[curr]
                path.reverse()
                return thumbtack_grids[found_tg], path

        return None, None

    def cancel_nav_goal(self):
        """Cancels any active Nav2 navigation action goal."""
        if self.nav_goal_handle is not None:
            self.get_logger().info("Cancelling active Nav2 goal...")
            try:
                self.nav_goal_handle.cancel_goal_async()
            except Exception as e:
                self.get_logger().error(f"Failed to cancel Nav2 goal: {e}")
            self.nav_goal_handle = None
        self.is_navigating = False
        self.nav_goal_status = 'NONE'

    def nav_goal_response_callback(self, future):
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().warn("Nav2 backtracking goal was rejected by action server. Falling back to BFS path follower.")
            self.nav_goal_status = 'FALLBACK'
            return
        self.get_logger().info("Nav2 backtracking goal accepted.")
        self.nav_goal_handle = goal_handle
        self.nav_goal_status = 'EXECUTING'
        
        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(self.nav_result_callback)

    def nav_result_callback(self, future):
        status = future.result().status
        self.get_logger().info(f"Nav2 goal finished with status code: {status}")
        self.is_navigating = False
        self.nav_goal_handle = None
        
        # Status code 4 represents SUCCEEDED. If failed or canceled, return to explore/select new
        if status != 4:
            self.get_logger().warn(f"Nav2 goal failed (status code: {status}). Removing target from pool.")
            if self.backtrack_target in self.thumbtack_pool:
                try:
                    self.thumbtack_pool.remove(self.backtrack_target)
                except ValueError:
                    pass
            self.backtrack_target = None
            self.current_target = None
            self.state = 'EXPLORE'

    def control_loop(self):
        """Main control loop executing at control_rate."""
        # Ensure sensor data has arrived
        if self.map_data is None:
            self.get_logger().info("Waiting for map data...", throttle_duration_sec=5.0)
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

        # Calculate Sector Weights (Phase 2 & Phase 3 Re-takeover Check)
        grid = self.map_data
        width = grid.info.width
        height = grid.info.height
        resolution = grid.info.resolution
        origin_x = grid.info.origin.position.x
        origin_y = grid.info.origin.position.y
        data = grid.data
        
        map_np = np.array(data, dtype=np.int8).reshape((height, width))
        
        # Fast local extraction of frontier cells from cached mask
        wx_local = np.array([])
        wy_local = np.array([])
        if self.frontier_mask is not None:
            gy_indices, gx_indices = np.where(self.frontier_mask)
            wx = origin_x + (gx_indices + 0.5) * resolution
            wy = origin_y + (gy_indices + 0.5) * resolution
            
            # Filter by local search radius
            dists = np.hypot(wx - robot_x, wy - robot_y)
            in_range = (dists <= self.local_search_radius)
            wx_local = wx[in_range]
            wy_local = wy[in_range]
        
        weights = [0] * 12
        sector_blocked = [False] * 12
        
        # 1. Backwards filter: restrict heading sectors to forward 180 deg
        # Sectors 3, 4, 5, 6, 7, 8 are generally forward or sideways
        for k in range(12):
            if k not in [3, 4, 5, 6, 7, 8]:
                sector_blocked[k] = True
                
        # 2. Obstacle filter: check map and laserscan for close obstacles
        gx_robot = int((robot_x - origin_x) / resolution)
        gy_robot = int((robot_y - origin_y) / resolution)
        coll_r_cells = int(self.obstacle_critical_dist / resolution) + 1
        
        y_min = max(0, gy_robot - coll_r_cells)
        y_max = min(height, gy_robot + coll_r_cells + 1)
        x_min = max(0, gx_robot - coll_r_cells)
        x_max = min(width, gx_robot + coll_r_cells + 1)
        
        local_occupied = (map_np[y_min:y_max, x_min:x_max] == 100)
        oy, ox = np.where(local_occupied)
        
        wx_occ = origin_x + (ox + x_min + 0.5) * resolution
        wy_occ = origin_y + (oy + y_min + 0.5) * resolution
        
        for cx, cy in zip(wx_occ, wy_occ):
            d = math.hypot(cx - robot_x, cy - robot_y)
            if d < self.obstacle_critical_dist:
                angle_local = normalize_angle(math.atan2(cy - robot_y, cx - robot_x) - robot_yaw)
                k = int((angle_local + math.pi) / (math.pi / 6.0)) % 12
                sector_blocked[k] = True
                
        # Supplement obstacle block using real-time LaserScan readings
        if self.scan_data is not None:
            scan = self.scan_data
            for i, r in enumerate(scan.ranges):
                if math.isfinite(r) and r > 0.0:
                    if r < self.obstacle_critical_dist:
                        angle_local = normalize_angle(scan.angle_min + i * scan.angle_increment)
                        k = int((angle_local + math.pi) / (math.pi / 6.0)) % 12
                        sector_blocked[k] = True
                        
        # 3. Unknown sniffing scoring
        for wx, wy in zip(wx_local, wy_local):
            angle_local = normalize_angle(math.atan2(wy - robot_y, wx - robot_x) - robot_yaw)
            k = int((angle_local + math.pi) / (math.pi / 6.0)) % 12
            if not sector_blocked[k]:
                weights[k] += 1
                    
        max_weight = max(weights)

        # STATE MACHINE STATE HANDLING
        if self.state == 'INIT':
            self.stop_robot()
            return
            
        elif self.state == 'EXPLORE':
            if max_weight == 0:
                # Dead-end escape mode: transition to Phase 3
                self.state = 'BACKTRACK'
                self.stop_robot()
                self.is_navigating = False
                self.backtrack_target = None
                self.current_target = None
                self.get_logger().info("Dead end reached (all sector weights are 0). Switching to Phase 3 (Backtracking)...")
            else:
                # Phase 2: Local steer and drive
                best_sectors = [k for k in range(12) if weights[k] == max_weight]
                k_target = random.choice(best_sectors)
                
                # Target center local angle
                phi = (k_target * 30.0 - 180.0 + 15.0) * math.pi / 180.0
                
                # Heading steering controller
                angular_vel = 1.3 * phi
                angular_vel = max(-self.angular_speed_max, min(self.angular_speed_max, angular_vel))
                
                # Advance controller
                linear_vel = self.linear_speed_max * math.cos(phi)
                linear_vel = max(0.0, linear_vel)
                
                # Obstacle safety speed-down check
                min_front_r = float('inf')
                if self.scan_data is not None:
                    scan = self.scan_data
                    for i, r in enumerate(scan.ranges):
                        if math.isfinite(r) and r > 0.0:
                            angle_local = normalize_angle(scan.angle_min + i * scan.angle_increment)
                            if -math.pi / 6.0 <= angle_local <= math.pi / 6.0:
                                if r < min_front_r:
                                    min_front_r = r
                                    
                if min_front_r < self.obstacle_safety_dist:
                    factor = (min_front_r - self.obstacle_critical_dist) / (self.obstacle_safety_dist - self.obstacle_critical_dist)
                    factor = max(0.0, min(1.0, factor))
                    linear_vel *= factor
                    
                twist = Twist()
                twist.linear.x = float(linear_vel)
                twist.angular.z = float(angular_vel)
                self.cmd_pub.publish(twist)
                
                # Set dynamic visualization target to closest thumbtack in this sector
                self.current_target = None
                min_t_dist = float('inf')
                for tx, ty in self.thumbtack_pool:
                    angle_local = normalize_angle(math.atan2(ty - robot_y, tx - robot_x) - robot_yaw)
                    k = int((angle_local + math.pi) / (math.pi / 6.0)) % 12
                    if k == k_target:
                        d = math.hypot(tx - robot_x, ty - robot_y)
                        if d < min_t_dist:
                            min_t_dist = d
                            self.current_target = (tx, ty)
                            
        elif self.state == 'BACKTRACK':
            # Phase 3 Re-takeover Check: if we detect unknown space nearby again, hand back control to Phase 2
            if max_weight > 0:
                self.get_logger().info("Sectors re-detected unknown cells nearby. Re-taking control (returning to Phase 2)...")
                self.cancel_nav_goal()
                self.state = 'EXPLORE'
                return
                
            # If we reached the backtracking target, cancel and return to Phase 2
            if self.backtrack_target is not None:
                d_to_target = math.hypot(self.backtrack_target[0] - robot_x, self.backtrack_target[1] - robot_y)
                if d_to_target < self.min_dist_to_target:
                    self.get_logger().info("Approached target thumbtack. Re-taking control (returning to Phase 2)...")
                    self.cancel_nav_goal()
                    self.state = 'EXPLORE'
                    return
                    
            # If not currently navigating, search for nearest thumbtack
            if not self.is_navigating:
                target_thumbtack, path = self.plan_path_to_nearest_thumbtack(robot_x, robot_y)
                
                if target_thumbtack is None:
                    # Phase 4 Termination: thumbtack pool size is 0 or unreachable
                    self.get_logger().info("No reachable thumbtacks left! Transitioning to Phase 4 (Termination)...")
                    self.state = 'COMPLETE'
                    self.stop_robot()
                    self.trigger_map_save()
                    return
                    
                self.backtrack_target = target_thumbtack
                self.current_target = target_thumbtack
                self.cached_path = path
                
                # Send goal to Nav2
                if self.nav_client.wait_for_server(timeout_sec=0.5):
                    self.get_logger().info(f"Navigating to closest backtracking thumbtack: {self.backtrack_target}")
                    goal_msg = NavigateToPose.Goal()
                    goal_msg.pose.header.frame_id = self.map_frame
                    goal_msg.pose.header.stamp = self.get_clock().now().to_msg()
                    goal_msg.pose.pose.position.x = float(self.backtrack_target[0])
                    goal_msg.pose.pose.position.y = float(self.backtrack_target[1])
                    goal_msg.pose.pose.orientation.w = 1.0
                    
                    self.nav_goal_status = 'PENDING'
                    send_goal_future = self.nav_client.send_goal_async(goal_msg)
                    send_goal_future.add_done_callback(self.nav_goal_response_callback)
                    self.is_navigating = True
                else:
                    # Fallback to local BFS path-following
                    self.get_logger().info("Nav2 server not ready. Sourcing path-follower fallback...")
                    self.is_navigating = True
                    self.nav_goal_status = 'FALLBACK'
                    
            # Fallback path follower execution
            if self.nav_goal_status == 'FALLBACK' and self.cached_path:
                # Find look-ahead point
                look_ahead = 0.5
                wp = self.cached_path[-1]
                for pt in self.cached_path:
                    if math.hypot(pt[0] - robot_x, pt[1] - robot_y) > look_ahead:
                        wp = pt
                        break
                        
                # Steer towards look-ahead point
                dx = wp[0] - robot_x
                dy = wp[1] - robot_y
                wp_angle = normalize_angle(math.atan2(dy, dx) - robot_yaw)
                
                angular_vel = 1.3 * wp_angle
                angular_vel = max(-self.angular_speed_max, min(self.angular_speed_max, angular_vel))
                
                # Scale linear velocity based on alignment
                linear_vel = self.linear_speed_max * math.cos(wp_angle)
                linear_vel = max(0.0, linear_vel)
                
                # Check collision stop
                if self.scan_data is not None:
                    scan = self.scan_data
                    min_front_r = float('inf')
                    for i, r in enumerate(scan.ranges):
                        if math.isfinite(r) and r > 0.0:
                            angle_local = normalize_angle(scan.angle_min + i * scan.angle_increment)
                            if -math.pi / 6.0 <= angle_local <= math.pi / 6.0:
                                if r < min_front_r:
                                    min_front_r = r
                    if min_front_r < self.obstacle_safety_dist:
                        factor = (min_front_r - self.obstacle_critical_dist) / (self.obstacle_safety_dist - self.obstacle_critical_dist)
                        factor = max(0.0, min(1.0, factor))
                        linear_vel *= factor
                        
                twist = Twist()
                twist.linear.x = float(linear_vel)
                twist.angular.z = float(angular_vel)
                self.cmd_pub.publish(twist)
                
        elif self.state == 'COMPLETE':
            self.get_logger().info("Exploration complete status active. Stop command locked.", throttle_duration_sec=10.0)
            self.stop_robot()
            
        self.publish_markers()

    def stop_robot(self):
        """Publishes a zero velocity command to bring the robot to a stop."""
        twist = Twist()
        twist.linear.x = 0.0
        twist.angular.z = 0.0
        self.cmd_pub.publish(twist)

    def trigger_map_save(self):
        """Saves the final map to /home/ubuntu/maps/final_map using map_saver_cli."""
        self.get_logger().info("🏁 EXPLORATION TERMINATED successfully. Saving final map...")
        self.exploration_complete = True
        self.publish_status()
        
        save_dir = "/home/ubuntu/maps"
        os.makedirs(save_dir, exist_ok=True)
        filepath = os.path.join(save_dir, "final_map")
        
        cmd = ["ros2", "run", "nav2_map_server", "map_saver_cli", "-f", filepath]
        try:
            subprocess.Popen(cmd)
            self.get_logger().info(f"Final map saving execution launched: {filepath}")
        except Exception as e:
            self.get_logger().error(f"Failed to trigger map_saver_cli: {e}")

    def publish_markers(self):
        """Publishes visual representation of thumbtacks and goals to RViz."""
        marker_array = MarkerArray()
        
        # Clear previous markers
        clear_marker = Marker()
        clear_marker.action = Marker.DELETEALL
        marker_array.markers.append(clear_marker)
        
        # 1. Thumbtacks (Green Spheres)
        if self.thumbtack_pool:
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
            
            for pt in self.thumbtack_pool:
                p = Point()
                p.x = pt[0]
                p.y = pt[1]
                p.z = 0.05
                centroids_marker.points.append(p)
                
            marker_array.markers.append(centroids_marker)
            
        # 2. Backtracking Goal Target (Large Blue Sphere)
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
