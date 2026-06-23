from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        Node(
            package='wheeltec_web_teleop',
            executable='web_server',
            name='web_teleop_node',
            output='screen',
        )
    ])
