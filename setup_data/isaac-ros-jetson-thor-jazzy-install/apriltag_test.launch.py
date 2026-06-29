from launch import LaunchDescription
from launch_ros.actions import Node, ComposableNodeContainer
from launch_ros.descriptions import ComposableNode


def generate_launch_description():
    camera_node = Node(
        package='v4l2_camera',
        executable='v4l2_camera_node',
        name='usb_cam',
        namespace='',
        output='screen',
        parameters=[{
            'video_device': '/dev/video0',
            'image_size': [640, 480],
            'pixel_format': 'YUYV',
            'camera_frame_id': 'camera_frame'
        }],
        remappings=[
            ('image_raw', '/camera/image_raw'),
            ('camera_info', '/camera/camera_info'),
        ]
    )

    apriltag_container = ComposableNodeContainer(
        package='rclcpp_components',
        executable='component_container_mt',
        name='apriltag_container',
        namespace='',
        output='screen',
        composable_node_descriptions=[
            ComposableNode(
                package='isaac_ros_apriltag',
                plugin='nvidia::isaac_ros::apriltag::AprilTagNode',
                name='apriltag',
                namespace='',
                parameters=[{
                    'size': 0.05,
                    'max_tags': 64,
                    'tile_size': 4,
                    'tag_family': 'tag36h11',
                    'backends': 'CUDA'
                }],
                remappings=[
                    ('image', '/camera/image_raw'),
                    ('camera_info', '/camera/camera_info')
                ]
            )
        ]
    )

    return LaunchDescription([
        camera_node,
        apriltag_container,
    ])
