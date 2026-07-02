import os
import yaml
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, EmitEvent, RegisterEventHandler
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import LifecycleNode
from launch_ros.event_handlers import OnStateTransition
from launch_ros.events.lifecycle import ChangeState
from lifecycle_msgs.msg import Transition
from launch.events import matches_action

def generate_launch_description():
    # Load robot parameters from YAML
    robot_params = {}
    params_path = '/workspaces/isaac_ros-dev/robot_params.yaml'
    if os.path.exists(params_path):
        try:
            with open(params_path, 'r') as f:
                robot_params = yaml.safe_load(f)
        except Exception as e:
            print(f"Error loading {params_path}: {e}")

    is_sim_val = robot_params.get('simulation', {}).get('is_sim', False)
    is_sim = str(is_sim_val).lower() == 'true'
    radius = robot_params.get('robot', {}).get('radius', 0.22)
    inflation = robot_params.get('navigation', {}).get('inflation_radius', 0.70)

    # Dynamically generate Nav2 parameters with correct odom frames
    try:
        template_path = os.path.join(get_package_share_directory('wheeltec_nav2'), 'param', 'wheeltec_param', 'nav2_params_with_slam.yaml')
        with open(template_path, 'r') as f:
            params_data = yaml.safe_load(f)

        odom_frame = "odom" if is_sim else "odom_combined"
        odom_topic = "/odom" if is_sim else "/odom_combined"

        def update_nested(d):
            for k, v in list(d.items()):
                if isinstance(v, dict):
                    update_nested(v)
                elif k == 'robot_radius':
                    d[k] = radius
                elif k == 'inflation_radius':
                    d[k] = inflation
                elif k in ['odom_frame_id', 'odom_frame']:
                    d[k] = odom_frame
                elif k in ['global_frame', 'local_frame', 'fixed_frame'] and v == 'odom':
                    d[k] = odom_frame
                elif k == 'odom_topic':
                    if v in ['/odom', 'odom']:
                        d[k] = odom_topic

        update_nested(params_data)

        import tempfile
        fd, generated_params_path = tempfile.mkstemp(prefix='nav2_params_', suffix='.yaml')
        with os.fdopen(fd, 'w') as f:
            yaml.safe_dump(params_data, f)
    except Exception as e:
        print(f"Failed to generate dynamic params: {e}")

    use_sim_time = LaunchConfiguration('use_sim_time', default='true' if is_sim else 'false')

    # SLAM Toolbox Lifecycle Node
    slam_toolbox_node = LifecycleNode(
        package='slam_toolbox',
        executable='async_slam_toolbox_node',
        name='slam_toolbox',
        output='screen',
        namespace='',
        parameters=[
            os.path.join(get_package_share_directory('wheeltec_slam_toolbox'), 'config', 'mapper_params_online_async.yaml'),
            {
                'use_lifecycle_manager': False,
                'use_sim_time': use_sim_time,
                'odom_frame': 'odom' if is_sim else 'odom_combined'
            }
        ],
        remappings=[] if is_sim else [('odom', 'odom_combined')]
    )

    configure_event = EmitEvent(
        event=ChangeState(
            lifecycle_node_matcher=matches_action(slam_toolbox_node),
            transition_id=Transition.TRANSITION_CONFIGURE
        )
    )

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

    # Nav2 Navigation
    navigation_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(get_package_share_directory('nav2_bringup'), 'launch', 'navigation_launch.py')
        ),
        launch_arguments={
            'use_sim_time': use_sim_time,
            'params_file': generated_params_path,
            'autostart': 'true'
        }.items()
    )

    # Auto Exploration
    auto_exploration_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(get_package_share_directory('auto_explorer'), 'launch', 'auto_exploration.launch.py')
        ),
        launch_arguments={
            'use_sim_time': use_sim_time
        }.items()
    )

    return LaunchDescription([
        DeclareLaunchArgument(
            'use_sim_time',
            default_value='true' if is_sim else 'false',
            description='Use simulation (Gazebo) clock if true'
        ),
        slam_toolbox_node,
        configure_event,
        activate_event,
        navigation_launch,
        auto_exploration_launch
    ])
