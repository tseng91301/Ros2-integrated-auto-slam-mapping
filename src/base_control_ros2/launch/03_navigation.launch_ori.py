#!/usr/bin/env python3

from launch import LaunchDescription
from launch_ros.actions import LifecycleNode
from launch_ros.actions import Node
from launch.substitutions import LaunchConfiguration
from launch.actions import DeclareLaunchArgument
import os
from ament_index_python.packages import get_package_share_directory
from launch.actions import TimerAction
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource


def generate_launch_description():
    use_sim_time = LaunchConfiguration('use_sim_time', default='false')
    nav2_launch_file_dir = os.path.join(get_package_share_directory('base_control_ros2'), 'launch')
    

    return LaunchDescription([
        DeclareLaunchArgument(
            'map',
            default_value='map.yaml',
            description='Full path to map file to load'),

        DeclareLaunchArgument(
            'params_file',
            default_value='nav2_params.yaml',
            description='Full path to param file to load'),

        # DeclareLaunchArgument(
        #     'use_sim_time',
        #     default_value='false',
        #     description='Use simulation (Gazebo) clock if true'),
            
        IncludeLaunchDescription(PythonLaunchDescriptionSource([nav2_launch_file_dir, '/setup_navigation.launch.py'])),

        IncludeLaunchDescription(
            PythonLaunchDescriptionSource([nav2_launch_file_dir, '/bringup_launch.py']),
            launch_arguments={
                'map': '/home/ae/Desktop/base_control_ws/src/base_control_ros2/launch/map.yaml',
                # 'use_sim_time': use_sim_time,
                'params_file': '/home/ae/Desktop/base_control_ws/src/base_control_ros2/launch/nav2_params.yaml'}.items(),
        ),
        
        Node(
            package='rviz2',
            executable='rviz2',
            arguments=['-d', 'slam_and_nav.rviz'],
            remappings=[('/tf', 'tf'),
                        ('/tf_static', 'tf_static'),
                        ('/goal_pose', 'goal_pose'),
                        ('/clicked_point', 'clicked_point'),
                        ('/initialpose', 'initialpose')])

    ])