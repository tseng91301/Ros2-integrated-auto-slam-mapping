import os
from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration

def generate_launch_description():
    # Declare launch arguments
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
        'obstacle_safety_dist', default_value='0.6',
        description='Distance at which obstacle avoidance begins (m)'
    )
    obstacle_critical_dist_arg = DeclareLaunchArgument(
        'obstacle_critical_dist', default_value='0.35',
        description='Distance at which emergency stop/turn triggers (m)'
    )
    robot_radius_arg = DeclareLaunchArgument(
        'robot_radius', default_value='0.25',
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
        'hysteresis_factor', default_value='100.0',
        description='Weight hysteresis factor to prevent sector switching oscillations'
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
        }]
    )

    return LaunchDescription([
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
        explorer_node
    ])
