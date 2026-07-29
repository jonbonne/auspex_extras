# file: launch/video_captioner_launch.py
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

def generate_launch_description():
    # allow user to pass in a namespace at launch time (default: empty)
    declare_ns = DeclareLaunchArgument(
        'namespace',
        default_value='',
        description='Namespace to apply to the video_captioner node'
    )
    ns = LaunchConfiguration('namespace')

    return LaunchDescription([
        declare_ns,

        Node(
            package='video_captioner',
            executable='video_streamer_node',
            name='video_streamer',
            namespace=ns,
            output='screen',
        ),
    ])
