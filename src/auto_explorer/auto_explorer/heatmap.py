import numpy as np
import math
from nav_msgs.msg import OccupancyGrid

class HeatmapManager:
    def __init__(self, decay_rate=0.05, heat_increment=2.0, max_temp=100.0, min_temp=0.0, robot_radius_m=0.25):
        self.decay_rate = decay_rate
        self.heat_increment = heat_increment
        self.max_temp = max_temp
        self.min_temp = min_temp
        self.robot_radius_m = robot_radius_m
        
        self.heatmap = None
        self.width = 0
        self.height = 0
        self.resolution = 0.0
        self.origin_x = 0.0
        self.origin_y = 0.0
        
    def update_map_size(self, width, height, resolution, origin_x, origin_y):
        if self.heatmap is None or self.width != width or self.height != height:
            new_heatmap = np.zeros((height, width), dtype=np.float32)
            if self.heatmap is not None:
                # Align old heatmap onto the new one using origins
                dx = int(round((self.origin_x - origin_x) / resolution))
                dy = int(round((self.origin_y - origin_y) / resolution))
                
                # Slices for source (old) and destination (new)
                src_x_start = max(0, -dx)
                src_y_start = max(0, -dy)
                src_x_end = min(self.width, width - dx)
                src_y_end = min(self.height, height - dy)
                
                dest_x_start = max(0, dx)
                dest_y_start = max(0, dy)
                dest_x_end = min(width, self.width + dx)
                dest_y_end = min(height, self.height + dy)
                
                if (src_x_end > src_x_start) and (src_y_end > src_y_start):
                    new_heatmap[dest_y_start:dest_y_end, dest_x_start:dest_x_end] = \
                        self.heatmap[src_y_start:src_y_end, src_x_start:src_x_end]
            
            self.heatmap = new_heatmap
            self.width = width
            self.height = height
            self.resolution = resolution
            self.origin_x = origin_x
            self.origin_y = origin_y

    def add_heat(self, robot_x, robot_y):
        if self.heatmap is None:
            return
        
        # Convert world coordinates to grid coordinates
        gx = int((robot_x - self.origin_x) / self.resolution)
        gy = int((robot_y - self.origin_y) / self.resolution)
        
        if 0 <= gx < self.width and 0 <= gy < self.height:
            # Heat up area within robot radius
            r_cells = int(math.ceil(self.robot_radius_m / self.resolution))
            y_min = max(0, gy - r_cells)
            y_max = min(self.height, gy + r_cells + 1)
            x_min = max(0, gx - r_cells)
            x_max = min(self.width, gx + r_cells + 1)
            
            # Generate meshgrid for distance calculation
            Y, X = np.ogrid[y_min:y_max, x_min:x_max]
            dist_sq = (X - gx) ** 2 + (Y - gy) ** 2
            mask = dist_sq <= r_cells ** 2
            
            self.heatmap[y_min:y_max, x_min:x_max][mask] = np.minimum(
                self.max_temp,
                self.heatmap[y_min:y_max, x_min:x_max][mask] + self.heat_increment
            )
            
    def decay(self):
        if self.heatmap is None:
            return
        self.heatmap = np.maximum(self.min_temp, self.heatmap - self.decay_rate)
        
    def get_temperature(self, robot_x, robot_y):
        if self.heatmap is None:
            return 0.0
        gx = int((robot_x - self.origin_x) / self.resolution)
        gy = int((robot_y - self.origin_y) / self.resolution)
        if 0 <= gx < self.width and 0 <= gy < self.height:
            return float(self.heatmap[gy, gx])
        return 0.0

    def generate_occupancy_grid(self, header):
        grid = OccupancyGrid()
        grid.header = header
        grid.info.resolution = self.resolution
        grid.info.width = self.width
        grid.info.height = self.height
        grid.info.origin.position.x = self.origin_x
        grid.info.origin.position.y = self.origin_y
        grid.info.origin.position.z = 0.0
        grid.info.origin.orientation.w = 1.0
        
        # Scale 0.0-100.0 directly to integer 0-100
        temp_int = np.clip(self.heatmap, 0.0, 100.0).astype(np.int8)
        grid.data = temp_int.flatten().tolist()
        return grid

    def reset(self):
        self.heatmap = None
        self.width = 0
        self.height = 0
        self.resolution = 0.0
        self.origin_x = 0.0
        self.origin_y = 0.0
