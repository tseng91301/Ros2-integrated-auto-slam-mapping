from ament_index_python.packages import get_package_share_directory
import os
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, TimerAction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node

def generate_launch_description():
    bringup_dir = get_package_share_directory('base_control_ros2')
    slam_config_dir = get_package_share_directory('wheeltec_slam_toolbox')
    launch_dir = os.path.join(bringup_dir, 'launch')
    slidar_dir=get_package_share_directory('sllidar_ros2')
    lidar_dir=os.path.join(slidar_dir, 'launch')

    # 啟動 base 控制與 IMU
    wheeltec_robot = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(launch_dir, '00_base_control.launch.py')),
    )

    # 啟動雷射雷達
    wheeltec_lidar = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(lidar_dir, 'sllidar_a2m12_launch.py')),
    )

    # SLAM Toolbox
    slam_toolbox_node = Node(
        package='slam_toolbox',
        executable='async_slam_toolbox_node',
        name='slam_toolbox',
        output='screen',
        parameters=[os.path.join(slam_config_dir, 'config', 'mapper_params_online_async.yaml')],
        remappings=[('odom', 'odom_combined')]
    )

    # 自動打開 RViz2
    rviz_config_file = os.path.join('/home/ubuntu/steven_verify_ws/wheeltec_slam_toolbox.rviz')  # 使用工作空間的 RViz 設定檔
    open_rviz2 = TimerAction(
        period=2.0,  # 延遲 2 秒打開
        actions=[
            Node(
                package='rviz2',
                executable='rviz2',
                name='rviz2',
                arguments=['-d', rviz_config_file],
                remappings=[
                    ('/tf', 'tf'),
                    ('/tf_static', 'tf_static'),
                    ('/goal_pose', 'goal_pose'),
                    ('/clicked_point', 'clicked_point'),
                    ('/initialpose', 'initialpose'),
                ],
                output='screen'
            )
        ]
    )

    return LaunchDescription([
        wheeltec_robot,
        wheeltec_lidar,
        slam_toolbox_node,
        open_rviz2
    ])
