#!/usr/bin/env python3

from launch import LaunchDescription
from launch_ros.actions import LifecycleNode
from launch_ros.actions import Node
from launch.substitutions import LaunchConfiguration
from launch.actions import DeclareLaunchArgument
import os
from ament_index_python.packages import get_package_share_directory
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource


def generate_launch_description():

    try:
        ROBOT_TYPE = os.environ['BASE_TYPE']
    except:
        ROBOT_TYPE = 'NanoRobot'
        print(f"\033[91m Warning:Please set the correct BASE_TYPE. Now using default: {ROBOT_TYPE}\033[0m")


    if ROBOT_TYPE == 'NanoRobot':
        imu_static_transform_args = ['0', '0', '0', '0', '0', '0', 'base_link', 'imu']              
    else:
        print(f"Unknown ROBOT_TYPE: {ROBOT_TYPE}, using default transform")
    
    camera_launch_path =os.path.expanduser('~/Desktop/innodisk_camera_ws/src/ros2_ev2m-oom1/launch/camera.launch.py')
    camera_launch=IncludeLaunchDescription(
        PythonLaunchDescriptionSource(camera_launch_path)
    )
    Lidar_launch_path =os.path.expanduser('~/Desktop/base_control_ws/src/sllidar_ros2/launch/sllidar_a1_launch.py')
    Lidar_launch=IncludeLaunchDescription(
        PythonLaunchDescriptionSource(Lidar_launch_path)
    )
    
    
    return LaunchDescription([    
                              camera_launch,
                              Lidar_launch,
        LifecycleNode(
            package='base_control_ros2',
            executable='base_control_node',
            name='base_control_ros2',
            output='screen',
            namespace='',
            parameters=[{
            	'pub_sonar': True,
                'filter_sonar': True
            }]
        ),
        Node(
            package='tf2_ros',
            executable='static_transform_publisher',
            name='base_to_link',
            output="screen",
            arguments=[
                '--x', '0', 
                '--y', '0', 
                '--z', '0',
                '--roll', '0', 
                '--pitch', '0', 
                '--yaw', '0',
                '--frame-id', 'base_footprint',
                '--child-frame-id', 'base_link'
            ]
        ),
        Node(
            package='tf2_ros',
            executable='static_transform_publisher',
            name='base_link_to_imu',
            output='screen',
            arguments=[
                '--x', '0.0',
                '--y', '0.0',
                '--z', '0.0',
                '--roll', '0',
                '--pitch', '0',
                '--yaw', '0',
                '--frame-id', 'base_link',
                '--child-frame-id', 'imu_link'
            ]
        ),
        Node(
            package='tf2_ros',
            executable='static_transform_publisher',
            name='base_to_laser',
            output='screen',
            arguments=[
                '--x', '0.08',
                '--y', '0.0',
                '--z', '0.14',
                '--roll', '0',
                '--pitch', '0',
                '--yaw', '0',
                '--frame-id', 'base_link',
                '--child-frame-id', 'laser'
            ]
        ),
        Node(
            package='tf2_ros',
            executable='static_transform_publisher',
            name='base_to_camera',
            output="screen",
            arguments=[
                '--x', '0', 
                '--y', '0', 
                '--z', '0.185',
                '--roll', '0', 
                '--pitch', '0', 
                '--yaw', '0',
                '--frame-id', 'base_link',
                '--child-frame-id', 'camera'
            ]
        ) 
    ])
