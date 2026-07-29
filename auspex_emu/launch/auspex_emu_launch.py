import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

def generate_launch_description():

    package_name = 'auspex_emu'
    config = os.path.join(get_package_share_directory(package_name), 'config', 'auspex_emu.yaml')

    return LaunchDescription([
        DeclareLaunchArgument('name', default_value="auspex_emu", description="Name of the emulator."),
        DeclareLaunchArgument('log_level', default_value="INFO", description="Logging level"),
        Node(
            package=package_name,
            executable='auspex_emu_node',
            name=LaunchConfiguration("name"),
            output='screen',
            emulate_tty=True,
            parameters=[config],
            arguments=['--ros-args', '--log-level', LaunchConfiguration("log_level")]
        ),
    ])
