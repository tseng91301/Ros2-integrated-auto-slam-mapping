#!/usr/bin/env python3

from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import GroupAction, DeclareLaunchArgument
import os
from ament_index_python.packages import get_package_share_directory
import launch_ros.actions
from launch.conditions import UnlessCondition
from launch.substitutions import LaunchConfiguration

def generate_launch_description():

    try:
        ROBOT_TYPE = os.environ['BASE_TYPE']
    except:
        ROBOT_TYPE = 'NanoRobot'
        print(f"\033[91m Warning:Please set the correct BASE_TYPE. Now using default: {ROBOT_TYPE}\033[0m")

    # Load robot_params.yaml
    robot_params = {}
    for path in ['/workspaces/isaac_ros-dev/robot_params.yaml', './robot_params.yaml']:
        if os.path.exists(path):
            try:
                import yaml
                with open(path, 'r') as f:
                    robot_params = yaml.safe_load(f)
                break
            except Exception as e:
                print(f"Error loading {path}: {e}")

    chassis_port = robot_params.get('robot', {}).get('chassis_port', '/dev/playrobot_base')

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
    ])

    # EKF node
    ekf_config = os.path.join(get_package_share_directory('turn_on_wheeltec_robot'),'config','ekf.yaml')
    carto_slam = LaunchConfiguration('carto_slam', default='false')
    robot_ekf = launch_ros.actions.Node(
        condition=UnlessCondition(carto_slam),
        package='robot_localization', 
        executable='ekf_node', 
        parameters=[ekf_config],
        remappings=[("odometry/filtered", "odom_combined")]
    )

    # Declare sonar arguments (來自第二份程式の優點)
    pub_sonar_arg = DeclareLaunchArgument(
        name='pub_sonar',
        default_value='True',
        description='Whether to publish sonar_x topic'
    )

    filter_sonar_arg = DeclareLaunchArgument(
        name='filter_sonar',
        default_value='True',
        description='Whether to filter the raw sonar data'
    )

    # Base control node with sonar params (用 LaunchConfiguration)
    base_control_ros2 = launch_ros.actions.Node(
        package='base_control_ros2',
        executable='base_control_node',
        name='base_control_ros2',
        output='screen',
        parameters=[{
            'pub_sonar': LaunchConfiguration('pub_sonar'),
            'filter_sonar': LaunchConfiguration('filter_sonar'),
            'device_port': chassis_port
        }]
    )

    ld = LaunchDescription()
    ld.add_action(pub_sonar_arg)
    ld.add_action(filter_sonar_arg)
    ld.add_action(playerrobot_base)
    ld.add_action(base_control_ros2)
    ld.add_action(robot_ekf)

    return ld
