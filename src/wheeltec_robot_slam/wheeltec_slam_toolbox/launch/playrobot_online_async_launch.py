from ament_index_python.packages import get_package_share_directory
import os
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, TimerAction, EmitEvent, RegisterEventHandler
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import LifecycleNode
from launch_ros.event_handlers import OnStateTransition
from launch_ros.events.lifecycle import ChangeState
from lifecycle_msgs.msg import Transition
from launch.events import matches_action

def generate_launch_description():
    bringup_dir = get_package_share_directory('base_control_ros2')
    slam_config_dir = get_package_share_directory('wheeltec_slam_toolbox')
    launch_dir = os.path.join(bringup_dir, 'launch')
    slidar_dir=get_package_share_directory('sllidar_ros2')
    lidar_dir=os.path.join(slidar_dir, 'launch')

    # SLAM Toolbox (Jazzy/ROS 2 uses lifecycle managed node)
    slam_toolbox_node = LifecycleNode(
        package='slam_toolbox',
        executable='async_slam_toolbox_node',
        name='slam_toolbox',
        output='screen',
        namespace='',
        parameters=[
            os.path.join(slam_config_dir, 'config', 'mapper_params_online_async.yaml'),
            {
                'use_lifecycle_manager': False,
                'use_sim_time': False
            }
        ],
        remappings=[('odom', 'odom_combined')]
    )

    # Configure event to transition the lifecycle state of slam_toolbox from unconfigured to inactive
    configure_event = EmitEvent(
        event=ChangeState(
            lifecycle_node_matcher=matches_action(slam_toolbox_node),
            transition_id=Transition.TRANSITION_CONFIGURE
        )
    )

    # Activate event handler to transition the state from inactive to active once configuration is complete
    activate_event = RegisterEventHandler(
        OnStateTransition(
            target_lifecycle_node=slam_toolbox_node,
            start_state="configuring",
            goal_state="inactive",
            entities=[
                EmitEvent(event=ChangeState(
                    lifecycle_node_matcher=matches_action(slam_toolbox_node),
                    transition_id=Transition.TRANSITION_ACTIVATE
                ))
            ]
        )
    )

    return LaunchDescription([
        slam_toolbox_node,
        configure_event,
        activate_event
    ])
