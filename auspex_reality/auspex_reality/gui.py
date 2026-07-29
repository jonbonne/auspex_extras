import sys
import time
import pygame
import traceback

import rclpy
from rclpy.node import Node

from sensor_msgs.msg import JointState

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
BLUE = (0, 0, 255)

class ServoBotGui(Node):
    """ROS2 gui to publish JointState messages."""
    def __init__(self, name):
        super().__init__(name, namespace='gizmos')
        #self._pygame_clock = pygame.time.Clock()

        # Setup the Pygame window
        pygame.display.set_caption("ServoBot: Joint Angle Control")

        # parameters
        self.declare_parameters(
            namespace='',
            parameters=[
                ("rate", 30),
                ("cmd_topic", "joint_states"),
                ("size", [400, 600]),
                ("slider_height", 30),
                ("slider_width", 300),
                ("slider_spacing", 70),
                ("slider_names", [""]),
            ]
        )

    def initialize(self):

        self._rate = self.get_parameter("rate").value
        self.get_logger().info(f"[ServoBotGui] Found 'rate' value: {self._rate}")
        self._size = self.get_parameter("size").value
        self.get_logger().info(f"[ServoBotGui] Found 'size' value: {self._size}")
        self._screen = pygame.display.set_mode((self._size[0], self._size[1]))
        
        self._slider_height = self.get_parameter("slider_height").value
        self.get_logger().info(f"[ServoBotGui] Found 'slider_height' value: {self._slider_height}")
        self._slider_width = self.get_parameter("slider_width").value
        self.get_logger().info(f"[ServoBotGui] Found 'slider_width' value: {self._slider_width}")
        self._slider_spacing = self.get_parameter("slider_spacing").value
        self.get_logger().info(f"[ServoBotGui] Found 'slider_spacing' value: {self._slider_spacing}")
        self._slider_names = self.get_parameter("slider_names").value
        self.get_logger().info(f"[ServoBotGui] Found 'slider_names' value: {self._slider_names}")
 
        # Create a list of slider values representing joint angles (initially 0 degrees)
        self._slider_values = [90] * len(self._slider_names)  # Midpoint (90 degrees) for each slider
       
        cmd_topic = self.get_parameter("cmd_topic").value
        self._joint_cmd_pub = self.create_publisher(JointState, cmd_topic, 10)
        self.get_logger().info(f"[ServoBotGui] Found 'cmd_topic' value: {cmd_topic}")
        
        #self._timer = self.create_timer(0.1, self.__publish_joint_states__)  # Publish every 0.1 seconds

        return True

    def __publish_joint_states__(self):
        msg = JointState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.name = self._slider_names
        msg.position = [value * (3.14159 / 180) for value in self._slider_values]  # Convert to radians
        msg.velocity = []
        msg.effort = []
        self._joint_cmd_pub.publish(msg)
        self.get_logger().info(f'Published JointState: {self._slider_values}')

    def __handle_slider_event__(self, slider_idx, mouse_x, slider_x):
        """Update the slider value based on the mouse position."""
        if slider_x <= mouse_x <= slider_x + self._slider_width:
            # Map mouse position to slider value (0-180 degrees)
            slider_value = int((mouse_x - slider_x) / self._slider_width * 180)
            self._slider_values[slider_idx] = slider_value

    def __draw_slider__(self, x, y, value, min_value=0, max_value=180):
        """Draw a horizontal slider."""
        pygame.draw.rect(self._screen, BLACK, (x, y, self._slider_width, self._slider_height), 2)
        handle_x = int(x + (value - min_value) / (max_value - min_value) * self._slider_width)
        pygame.draw.rect(self._screen, BLUE, (handle_x - 5, y, 10, self._slider_height))

    def update(self, pygame_events):
   
        try:
            self._screen.fill(WHITE)
            
            # Event handling
            for event in pygame_events:
                if event.type == pygame.QUIT:
                    running = False
                if event.type == pygame.MOUSEBUTTONDOWN:
                    mouse_x, mouse_y = pygame.mouse.get_pos()
                    for i in range(len(self._slider_names)):
                        slider_x = 50
                        slider_y = 50 + i * self._slider_spacing
                        if slider_y <= mouse_y <= slider_y + self._slider_height:
                            self.__handle_slider_event__(i, mouse_x, slider_x)
    
            # Draw sliders
            for i in range(len(self._slider_names)):
                slider_x = 50
                slider_y = 50 + i * self._slider_spacing
                self.__draw_slider__(slider_x, slider_y, self._slider_values[i])
                # Display the angle value near the slider
                font = pygame.font.Font(None, 36)
                text = font.render(f'{self._slider_values[i]}°', True, BLACK)
                self._screen.blit(text, (slider_x + self._slider_width + 20, slider_y))
    
            # Update the screen
            pygame.display.flip()

            # publish cmd
            self.__publish_joint_states__()

        except Exception as err:
            self.get_logger().error(f"[ServoBotGui] {err} | {traceback.format_exc()}")

        # Limit FPS
        #self._pygame_clock.tick(self._rate)
