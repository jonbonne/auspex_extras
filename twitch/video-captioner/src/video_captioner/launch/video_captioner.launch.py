from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument(
            'namespace',
            default_value='',
            description='Namespace to apply to the video_captioner node'
        ),
        DeclareLaunchArgument(
            'name',
            default_value='video_captioner',
            description='Name of the node'
        ),
        DeclareLaunchArgument(
            'video_device',
            default_value='0',
            description='Video device index used for capture'
        ),
        DeclareLaunchArgument(
            'frame_rate',
            default_value='30.0',
            description='Frame rate for image capture (Hz)'
        ),
        DeclareLaunchArgument(
            'caption_rate',
            default_value='1.0',
            description='Caption generation rate (seconds)'
        ),
        Node(
            package='video_captioner',            # ← your ROS2 package name
            executable='video_captioner_node',    # ← your node’s executable name
            name=LaunchConfiguration('name'),               # keeps the node’s name
            namespace=LaunchConfiguration('namespace'),                         # apply the namespace here
            output='screen',
            parameters=[{
                'video_device_idx': LaunchConfiguration('video_device'),
                'image_rate_hz': LaunchConfiguration('frame_rate'),
                'caption_rate_sec': LaunchConfiguration('caption_rate')
            }],
        ),
    ])
