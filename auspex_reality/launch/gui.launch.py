from launch import LaunchDescription
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution

def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('name', default_value="servobot_gui", description="Node Name"),
        DeclareLaunchArgument('log_level', default_value="INFO", description="Logging level"),
        Node(
            package='auspex_reality',
            executable='servobot-gui',
            name=LaunchConfiguration("name"),
            output='screen',
            emulate_tty=True,
            parameters=[PathJoinSubstitution([FindPackageShare('auspex_reality'), 'config', 'gui.yaml'])],
            remappings=[],
            arguments=['--ros-args', '--log-level', LaunchConfiguration("log_level")]
        )
    ])

