import os
import xacro
from pathlib import Path
from launch import LaunchDescription
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory

def generate_launch_description():

    # --- Get Paths ---
    # This launch file assumes it is in a folder with 'humanoid.urdf'
    # and 'default.rviz'
    current_dir = get_package_share_directory("auspex_reality")
    
    xacro_file_path = os.path.join(current_dir, 'urdf', 'humanoid.urdf.xacro')
    rviz_config_file = os.path.join(current_dir, 'config', 'default.rviz')

    try:
        robot_description_xml = xacro.process_file(xacro_file_path).toxml()
    except xacro.XacroException as e:
        print(f"Xacro processing failed: {e}")
        return LaunchDescription() # Return empty LaunchDescription on failure

    # --- Nodes to Launch ---

    # 1. Robot State Publisher
    # Takes the URDF and publishes the robot's structure (TF)
    robot_state_publisher_node = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='screen',
        parameters=[{
            'robot_description': robot_description_xml,
            'use_sim_time': False # Use real time
        }]
    )

    # 2. Joint State Publisher GUI
    # Provides sliders to "move" the robot's joints
    joint_state_publisher_gui_node = Node(
        package='joint_state_publisher_gui',
        executable='joint_state_publisher_gui',
        name='joint_state_publisher_gui',
    )

    # 2. **NEW: Static Transform Publisher**
    # This node creates the "odom" frame and links "base_link" to it,
    # placing the robot at the origin (0, 0, 0) of the world.
    static_tf_publisher = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='static_broadcaster',
        output='screen',
        arguments=[
            '0', '0', '0', # x, y, z translation
            '0', '0', '0', # roll, pitch, yaw rotation (all zero)
            '--frame-id', 'odom',      # Parent frame (the world root)
            '--child-frame-id', 'base_link' # Child frame (the robot's root)
            ]
    )

    # 3. RViz (visualization)
    # Opens RViz with the specified config file
    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        output='screen',
        arguments=['-d', rviz_config_file]
    )
    
    # --- Create Launch Description ---
    return LaunchDescription([
        joint_state_publisher_gui_node,
        robot_state_publisher_node,
        static_tf_publisher,
        rviz_node
    ])

