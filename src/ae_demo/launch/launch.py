from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([

        Node(
            package='ae_demo',
            namespace='',
            executable='node_pub',
            name='node_pub',
        ),

        Node(
            package='ae_demo',
            namespace='',
            executable='node_sub',
            name='node_sub',
        ),

    ])
