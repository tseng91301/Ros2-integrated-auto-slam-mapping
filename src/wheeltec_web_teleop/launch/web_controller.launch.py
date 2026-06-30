import os
import yaml
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, ExecuteProcess, RegisterEventHandler, OpaqueFunction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch.conditions import IfCondition, UnlessCondition
from launch_ros.actions import Node
from launch.event_handlers import OnShutdown
import tempfile

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

    # Determine simulation vs physical
    is_sim_val = robot_params.get('simulation', {}).get('is_sim', False)
    is_sim = str(is_sim_val).lower() == 'true'
    
    chassis_port = robot_params.get('robot', {}).get('chassis_port', '/dev/playrobot_base')
    lidar_port = robot_params.get('robot', {}).get('lidar_port', '/dev/sllidar_a2m12')
    world_path = robot_params.get('simulation', {}).get('world_path', '/opt/ros/jazzy/share/nav2_minimal_tb3_sim/worlds/tb3_sandbox.sdf.xacro')

    ld = LaunchDescription()

    # Common Web Server nodes
    web_teleop_dir = get_package_share_directory('wheeltec_web_teleop')
    web_teleop_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(web_teleop_dir, 'launch', 'web_teleop.launch.py')),
        launch_arguments={'use_sim_time': 'true' if is_sim else 'false'}.items()
    )
    ld.add_action(web_teleop_launch)

    if is_sim:
        # Simulation Mode
        sim_dir = get_package_share_directory('nav2_minimal_tb3_sim')
        
        # 1. World SDF creation synchronously in Python to prevent race conditions & name collision with pkill
        import subprocess
        import shutil
        # Create temp file without "nav2_" prefix to prevent matching pkill patterns
        world_sdf = tempfile.mktemp(prefix='gz_world_', suffix='.sdf')
        try:
            if world_path.endswith('.xacro'):
                subprocess.run(['xacro', '-o', world_sdf, 'headless:=True', world_path], check=True)
            else:
                shutil.copyfile(world_path, world_sdf)
        except Exception as e:
            print(f"Error copying/processing world file: {e}")
            # Fallback
            fallback_xacro = os.path.join(sim_dir, 'worlds', 'tb3_sandbox.sdf.xacro')
            subprocess.run(['xacro', '-o', world_sdf, 'headless:=True', fallback_xacro], check=True)
        
        # 2. Gazebo Server
        gazebo_server = ExecuteProcess(
            cmd=['gz', 'sim', '-r', '-s', world_sdf],
            output='screen'
        )
        
        # 3. Clean up temp SDF
        remove_temp_sdf_file = RegisterEventHandler(event_handler=OnShutdown(
            on_shutdown=[
                OpaqueFunction(function=lambda _: os.remove(world_sdf) if os.path.exists(world_sdf) else None)
            ]))
            
        # 4. Robot Description and State Publisher
        urdf = os.path.join(sim_dir, 'urdf', 'turtlebot3_waffle.urdf')
        with open(urdf, 'r') as infp:
            robot_description = infp.read()
            
        robot_state_publisher = Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            name='robot_state_publisher',
            output='screen',
            parameters=[{'use_sim_time': True, 'robot_description': robot_description}],
            remappings=[('/tf', 'tf'), ('/tf_static', 'tf_static')]
        )
        
        # 5. Spawn TB3 robot in Gazebo
        gz_robot = IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(sim_dir, 'launch', 'spawn_tb3.launch.py')),
            launch_arguments={
                'use_sim_time': 'true',
                'robot_name': 'turtlebot3_waffle',
                'robot_sdf': os.path.join(sim_dir, 'urdf', 'gz_waffle.sdf.xacro'),
                'x_pose': '-2.0' if 'tb3_sandbox' in world_path else ('-3.0' if 'my-nav-map' in world_path else '0.0'),
                'y_pose': '-0.5' if 'tb3_sandbox' in world_path else ('-1.5' if 'my-nav-map' in world_path else '0.0'),
                'z_pose': '0.01'
            }.items()
        )
        
        ld.add_action(remove_temp_sdf_file)
        ld.add_action(gazebo_server)
        ld.add_action(robot_state_publisher)
        ld.add_action(gz_robot)
        
    else:
        # Physical Robot Mode
        base_control_dir = get_package_share_directory('base_control_ros2')
        lidar_dir = get_package_share_directory('sllidar_ros2')
        
        # 1. Base control
        base_control = IncludeLaunchDescription(
            PythonLaunchDescriptionSource(os.path.join(base_control_dir, 'launch', '00_base_control.launch.py')),
            launch_arguments={
                'pub_sonar': 'True',
                'filter_sonar': 'True'
            }.items()
        )
        
        # 2. Lidar
        lidar = IncludeLaunchDescription(
            PythonLaunchDescriptionSource(os.path.join(lidar_dir, 'launch', 'sllidar_a2m12_launch.py')),
            launch_arguments={'serial_port': lidar_port}.items()
        )
        
        ld.add_action(base_control)
        ld.add_action(lidar)

    return ld
