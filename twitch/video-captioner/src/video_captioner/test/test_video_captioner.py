import os
import launch
import launch_ros.actions
import launch_testing
import pytest
import rclpy
from std_msgs.msg import String

def generate_test_description():
    node = launch_ros.actions.Node(
        package='video_captioner',
        executable='video_captioner_node',
        name='video_captioner_test_node',
        output='screen'
    )

    return launch.LaunchDescription([
        node,
        launch_testing.actions.ReadyToTest(),
    ]), {
        'video_captioner_node': node
    }

@pytest.mark.rostest
def test_caption_published(launch_service, video_captioner_node, proc_output):
    rclpy.init()
    node = rclpy.create_node('test_node')
    msgs = []

    def listener_callback(msg):
        msgs.append(msg.data)
        node.get_logger().info(f"Received caption: {msg.data}")

    sub = node.create_subscription(String, 'video_caption', listener_callback, 10)

    # Give the node time to publish a few messages
    end_time = node.get_clock().now().to_msg().sec + 10
    while rclpy.ok() and node.get_clock().now().to_msg().sec < end_time:
        rclpy.spin_once(node, timeout_sec=0.5)
        if msgs:
            break

    sub.destroy()
    node.destroy_node()
    rclpy.shutdown()

    assert len(msgs) > 0, "No caption messages received"
