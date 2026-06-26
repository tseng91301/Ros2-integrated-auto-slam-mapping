import os
from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration

def generate_launch_description():
    # Load robot parameters
    import yaml
    robot_params = {}
    for path in ['/workspaces/isaac_ros-dev/robot_params.yaml', './robot_params.yaml']:
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    robot_params = yaml.safe_load(f)
                break
            except Exception as e:
                print(f"Error loading {path}: {e}")

    # Set parameter defaults from YAML
    radius_val = str(robot_params.get('robot', {}).get('radius', 0.22))
    safety_dist_val = str(robot_params.get('exploration', {}).get('obstacle_safety_dist', 
                          robot_params.get('navigation', {}).get('obstacle_safety_dist', 0.6)))
    critical_dist_val = str(robot_params.get('exploration', {}).get('obstacle_critical_dist', 
                            robot_params.get('navigation', {}).get('obstacle_critical_dist', 0.35)))
    is_sim_val = str(robot_params.get('simulation', {}).get('is_sim', False)).lower()

    # Declare launch arguments
    use_sim_time_arg = DeclareLaunchArgument(
        'use_sim_time', default_value=is_sim_val,
        description='Use simulation (Gazebo) clock if true'
    )
    map_frame_arg = DeclareLaunchArgument(
        'map_frame', default_value='map',
        description='The coordinate frame of the map'
    )
    robot_frame_arg = DeclareLaunchArgument(
        'robot_frame', default_value='base_link',
        description='The coordinate frame of the robot base'
    )
    linear_speed_max_arg = DeclareLaunchArgument(
        'linear_speed_max', default_value='0.20',
        description='Maximum linear speed of the robot (m/s)'
    )
    angular_speed_max_arg = DeclareLaunchArgument(
        'angular_speed_max', default_value='0.6',
        description='Maximum angular speed of the robot (rad/s)'
    )
    obstacle_safety_dist_arg = DeclareLaunchArgument(
        'obstacle_safety_dist', default_value=safety_dist_val,
        description='Distance at which obstacle avoidance begins (m)'
    )
    obstacle_critical_dist_arg = DeclareLaunchArgument(
        'obstacle_critical_dist', default_value=critical_dist_val,
        description='Distance at which emergency stop/turn triggers (m)'
    )
    robot_radius_arg = DeclareLaunchArgument(
        'robot_radius', default_value=radius_val,
        description='Robot physical safety radius (m)'
    )
    max_exploration_laps_arg = DeclareLaunchArgument(
        'max_exploration_laps', default_value='1',
        description='Maximum number of exploration loops'
    )
    thumbtack_spacing_arg = DeclareLaunchArgument(
        'thumbtack_spacing', default_value='0.5',
        description='Minimum spacing between thumbtacks (m)'
    )
    local_search_radius_arg = DeclareLaunchArgument(
        'local_search_radius', default_value='3.0',
        description='Radius for local sector search (m)'
    )
    hysteresis_factor_arg = DeclareLaunchArgument(
        'hysteresis_factor', default_value='1.25',
        description='Weight hysteresis factor to prevent sector switching oscillations'
    )
    sector_lock_cycles_arg = DeclareLaunchArgument(
        'sector_lock_cycles', default_value='10',
        description='Minimum cycles to lock onto a sector (at 10Hz, 10 cycles = 1s)'
    )
    stuck_temp_threshold_arg = DeclareLaunchArgument(
        'stuck_temp_threshold', default_value='80.0',
        description='Heatmap temperature threshold to trigger recovery mode'
    )
    heatmap_decay_rate_arg = DeclareLaunchArgument(
        'heatmap_decay_rate', default_value='0.05',
        description='Heatmap cooling decay per control loop cycle'
    )
    heatmap_heat_increment_arg = DeclareLaunchArgument(
        'heatmap_heat_increment', default_value='2.0',
        description='Heatmap increment added per cycle at robot position'
    )

    # Explorer node
    explorer_node = Node(
        package='auto_explorer',
        executable='explorer_node',
        name='explorer_node',
        output='screen',
        parameters=[{
            'map_frame': LaunchConfiguration('map_frame'),
            'robot_frame': LaunchConfiguration('robot_frame'),
            'linear_speed_max': LaunchConfiguration('linear_speed_max'),
            'angular_speed_max': LaunchConfiguration('angular_speed_max'),
            'obstacle_safety_dist': LaunchConfiguration('obstacle_safety_dist'),
            'obstacle_critical_dist': LaunchConfiguration('obstacle_critical_dist'),
            'robot_radius': LaunchConfiguration('robot_radius'),
            'max_exploration_laps': LaunchConfiguration('max_exploration_laps'),
            'thumbtack_spacing': LaunchConfiguration('thumbtack_spacing'),
            'local_search_radius': LaunchConfiguration('local_search_radius'),
            'hysteresis_factor': LaunchConfiguration('hysteresis_factor'),
            'sector_lock_cycles': LaunchConfiguration('sector_lock_cycles'),
            'stuck_temp_threshold': LaunchConfiguration('stuck_temp_threshold'),
            'heatmap_decay_rate': LaunchConfiguration('heatmap_decay_rate'),
            'heatmap_heat_increment': LaunchConfiguration('heatmap_heat_increment'),
            'use_sim_time': LaunchConfiguration('use_sim_time'),
        }]
    )

    return LaunchDescription([
        use_sim_time_arg,
        map_frame_arg,
        robot_frame_arg,
        linear_speed_max_arg,
        angular_speed_max_arg,
        obstacle_safety_dist_arg,
        obstacle_critical_dist_arg,
        robot_radius_arg,
        max_exploration_laps_arg,
        thumbtack_spacing_arg,
        local_search_radius_arg,
        hysteresis_factor_arg,
        sector_lock_cycles_arg,
        stuck_temp_threshold_arg,
        heatmap_decay_rate_arg,
        heatmap_heat_increment_arg,
        explorer_node
    ])
