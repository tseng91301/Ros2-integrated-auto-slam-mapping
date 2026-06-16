#!/usr/bin/env python3

from launch import LaunchDescription
from launch_ros.actions import LifecycleNode
from launch_ros.actions import Node
from launch.substitutions import LaunchConfiguration
from launch.actions import DeclareLaunchArgument
import os
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():

    try:
        ROBOT_TYPE = os.environ['BASE_TYPE']
    except:
        ROBOT_TYPE = 'NanoRobot'
        print(f"\033[91m Warning:Please set the correct BASE_TYPE. Now using default: {ROBOT_TYPE}\033[0m")

    imu_static_transform_args = ['0', '0', '0', '0', '0', '0', 'base_link', 'sensor_link']
    if ROBOT_TYPE == 'NanoRobot':
        imu_static_transform_args = ['0', '0', '0', '0', '0', '0', 'base_link', 'imu']              
    else:
        print(f"Unknown ROBOT_TYPE: {ROBOT_TYPE}, using default transform")
    base_footprint_static_transform_args = ['0.0', '0.0', '0.0', '0.0', '0.0', '0.0', 'base_footprint', 'base_link'] 

    rviz_config_dir = os.path.join(
            get_package_share_directory('sllidar_ros2'),
            'rviz',
            'sllidar_ros2.rviz')
    
    
    return LaunchDescription([      
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
            name='base_link_to_imu',
            arguments=imu_static_transform_args,  # set tf transform data
            output='log'
        ),      
        Node(
            package='tf2_ros',
            executable='static_transform_publisher',
            name='base_link_to_footprint',
            arguments=base_footprint_static_transform_args,  # set tf transform data
            output='log'
        ),
        Node(
            package='sllidar_ros2',
            executable='sllidar_node',
            name='sllidar_node',
            parameters=[{'channel_type':'serial',
                         'serial_port': '/dev/rplidar', 
                         'serial_baudrate': 115200, 
                         'frame_id': 'laser',
                         'inverted': False, 
                         'angle_compensate': True, 
                         'scan_mode': 'Sensitivity'}],
            output='screen'),
         Node(
            package='rviz2',
            executable='rviz2',
            name='rviz2',
            arguments=['-d', rviz_config_dir],
            output='screen'),       
    ])
