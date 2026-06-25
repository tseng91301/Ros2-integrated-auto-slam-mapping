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
        'linear_speed_max', default_value='0.25',
        description='Maximum linear speed of the robot (m/s)'
    )
    angular_speed_max_arg = DeclareLaunchArgument(
        'angular_speed_max', default_value='0.7',
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
    min_frontier_size_arg = DeclareLaunchArgument(
        'min_frontier_size', default_value='5',
        description='Minimum number of cells to form a valid frontier cluster'
    )
    use_sim_time_arg = DeclareLaunchArgument(
        'use_sim_time', default_value='false',
        description='Use simulation clock if true'
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
            'min_frontier_size': LaunchConfiguration('min_frontier_size'),
            'use_sim_time': LaunchConfiguration('use_sim_time'),
        }]
    )

    return LaunchDescription([
        map_frame_arg,
        robot_frame_arg,
        linear_speed_max_arg,
        angular_speed_max_arg,
        obstacle_safety_dist_arg,
        obstacle_critical_dist_arg,
        min_frontier_size_arg,
        use_sim_time_arg,
        explorer_node
    ])
