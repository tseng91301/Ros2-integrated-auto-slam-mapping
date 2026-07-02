import os
import yaml
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration

def generate_launch_description():
    # Load robot parameters from YAML to determine use_sim_time default
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

    # Declare launch arguments
    map_yaml_arg = DeclareLaunchArgument(
        'map',
        # default to a fallback map inside the workspace
        default_value='/workspaces/isaac_ros-dev/src/wheeltec_robot_nav2/map/map_1750318412.yaml',
        description='Full path to map yaml file to load'
    )

    use_sim_time_arg = DeclareLaunchArgument(
        'use_sim_time',
        default_value='true' if is_sim else 'false',
        description='Use simulation (Gazebo) clock if true'
    )

    bringup_dir = get_package_share_directory('nav2_bringup')
    
    # 1. Localization (map_server + AMCL)
    localization_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(bringup_dir, 'launch', 'localization_launch.py')),
        launch_arguments={
            'use_sim_time': LaunchConfiguration('use_sim_time'),
            'map': LaunchConfiguration('map'),
            'params_file': generated_params_path,
            'autostart': 'true'
        }.items()
    )

    # 2. Navigation (planners, controllers, behavior trees, etc.)
    navigation_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(bringup_dir, 'launch', 'navigation_launch.py')),
        launch_arguments={
            'use_sim_time': LaunchConfiguration('use_sim_time'),
            'params_file': generated_params_path,
            'autostart': 'true'
        }.items()
    )

    return LaunchDescription([
        map_yaml_arg,
        use_sim_time_arg,
        localization_launch,
        navigation_launch
    ])
