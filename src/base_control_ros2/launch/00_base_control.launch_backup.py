#!/usr/bin/env python3

from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import GroupAction
import os
from ament_index_python.packages import get_package_share_directory
from launch_ros.actions import PushRosNamespace
import launch_ros.actions
from pathlib import Path
from launch.conditions import UnlessCondition
from launch.substitutions import LaunchConfiguration, PythonExpression

def generate_launch_description():

    try:
        ROBOT_TYPE = os.environ['BASE_TYPE']
    except:
        ROBOT_TYPE = 'NanoRobot'
        print(f"\033[91m Warning:Please set the correct BASE_TYPE. Now using default: {ROBOT_TYPE}\033[0m")

    # imu_static_transform_args = ['0', '0', '0', '0', '0', '0', 'base_link', 'sensor_link']
    # if ROBOT_TYPE == 'NanoRobot':
    #     imu_static_transform_args = ['0', '0', '0', '0', '0', '0', 'base_link', 'imu']              
    # else:
    #     print(f"Unknown ROBOT_TYPE: {ROBOT_TYPE}, using default transform")

    # Group robot URDF and static TFs
    playerrobot_base = GroupAction([
        Node(
            package='robot_state_publisher', 
            executable='robot_state_publisher', 
            name='robot_state_publisher',
            arguments=[os.path.join(get_package_share_directory('wheeltec_robot_urdf'), 'urdf', 'playrobot.urdf')],
            output='screen'
        ),
        Node(
            package='joint_state_publisher',
            executable='joint_state_publisher',
            name='joint_state_publisher',
            output='screen'
        )
        # ),
        # Node(
        #     package='tf2_ros',
        #     executable='static_transform_publisher',
        #     name='lidar_tf',
        #     arguments=['0.0', '0', '0.22', '0', '3.14159', '3.14159', 'base_footprint', 'laser'],
        #     output='screen'
        # )
        # ),
        # Node(
        #     package='tf2_ros',
        #     executable='static_transform_publisher',
        #     name='camera_tf',
        #     arguments=['0.195', '0', '0.25', '0', '0', '0', 'base_footprint', 'camera_link'],
        #     output='screen'
        # )
    ])

    ekf_config = os.path.join(get_package_share_directory('turn_on_wheeltec_robot'),'config','ekf.yaml')
    carto_slam = LaunchConfiguration('carto_slam', default='false')
    robot_ekf = launch_ros.actions.Node(
        condition=UnlessCondition(carto_slam),
        package='robot_localization', 
        executable='ekf_node', 
        parameters=[ekf_config],
        remappings=[("odometry/filtered", "odom_combined")]
        )


    base_control_ros2 = launch_ros.actions.Node(
            package='base_control_ros2',
            executable='base_control_node',
            name='base_control_ros2',
            output='screen',
            parameters=[{
                'pub_sonar': True,
                'filter_sonar': True
            }]
    )

    # base_link_tf = launch_ros.actions.Node(
    #         package='tf2_ros',
    #         executable='static_transform_publisher',
    #         name='base_link_tf',
    #         arguments=['0', '0', '0', '0', '0', '0', 'base_footprint', 'base_link'],
    #         output='screen'
    # )
    # gyro_tf = launch_ros.actions.Node(
    #         package='tf2_ros',
    #         executable='static_transform_publisher',
    #         name='gyro_tf',
    #         arguments=['0', '0', '0', '0', '0', '0', 'base_footprint', 'gyro_link'],
    #         output='screen'
    # )

    ld = LaunchDescription()
    ld.add_action(playerrobot_base)
    ld.add_action(base_control_ros2)
    # ld.add_action(base_link_tf)
    # ld.add_action(gyro_tf)
    ld.add_action(robot_ekf)

    return ld
