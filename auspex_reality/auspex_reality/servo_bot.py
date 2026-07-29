import traceback

import rclpy
from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup, ReentrantCallbackGroup
from ament_index_python.packages import get_package_share_directory

from auspex_util.functions import generate_guid128

from sensor_msgs.msg import JointState
from adafruit_servokit import ServoKit

class ServoBot(Node):

    def __init__(self, name):
        '''
        Constructor
        '''
        super().__init__(name, namespace='/gizmos')
        self._configured = False
        self._guid = generate_guid128()
        self._joint_cmd = None
        self._executor = None

        # AdaFruit
        self._servo_kit = None
        self._servo_angles = None
        self._servo_sps = None

        # Callback Groups
        self._process_group = MutuallyExclusiveCallbackGroup()

        # parameters
        self.declare_parameters(
            namespace='',
            parameters=[
                ("num_threads", 2),
                ("num_servos", 0),
                ("servo_channels", [""]),
                ("servo_mins", [0]),
                ("servo_maxs", [180]),
                ("cmd_topic", "joint_cmd"),
            ]
        )


    def initialize(self) -> bool:
        '''
        Initialization
        '''
        if not self._configured:

            self._num_threads = self.get_parameter("num_threads").value
            self.get_logger().info(f"[Auspex] Found 'num_threads' value: {self._num_threads}")

            self._num_servos = self.get_parameter("num_servos").value
            self.get_logger().info(f"[Auspex] Found 'num_servos' value: {self._num_servos}")

            servo_list = self.get_parameter("servo_channels").value
            self._servo_channels = {srv: i for i, srv in enumerate(servo_list)}
            self._servo_angles = {srv: 90 for srv in servo_list}
            self._servo_sps = {srv: 90 for srv in servo_list}
            self.get_logger().info(f"[Auspex] Found 'servo_channels' value: {servo_list}")

            servo_mins = self.get_parameter("servo_mins").value
            servo_maxs = self.get_parameter("servo_maxs").value
            self._servo_limits = {servo_list[i]: (lims[0], lims[1]) for i, lims in enumerate(zip(servo_mins, servo_maxs))}

            # Initialize the ServoKit instance for the PCA9685 servo controller (assuming a 16-channel driver)
            self._servo_kit = ServoKit(channels=16)

            cmd_topic = self.get_parameter("cmd_topic").value
            self._joint_cmd = self.create_subscription(JointState, cmd_topic, self.__cmd_cb__, 1, callback_group=self._process_group)

            self._executor = MultiThreadedExecutor(self._num_threads)
            self._executor.add_node(self)

            self._configured = True;

        return self._configured

    def teardown(self):
        '''
        Teardown
        '''
        if self._configured:
            self._executor.remove_node(self)
            self.destroy_subscription(self._joint_cmd)
            self._configured = False

    def update(self):
        '''
        Update
        '''
        #start = get_current_milliseconds()
        try:
            for joint_name in self._servo_channels:
                if (self._servo_angles[joint_name] - self._servo_sps[joint_name]) < -2:
                    self._servo_angles[joint_name] += 2
                elif (self._servo_angles[joint_name] - self._servo_sps[joint_name]) > 2:
                    self._servo_angles[joint_name] -= 2

                servo_channel = self._servo_channels[joint_name]
                self.set_servo_angle(servo_channel, self._servo_angles[joint_name])
            self._executor.spin_once(timeout_sec=0.01)
            #print(f"??? updated in {get_current_milliseconds() - start}ms")
        except Exception as err:
            self.get_logger().error(f"[Auspex] {err} | {traceback.format_exc()}")

    def __cmd_cb__(self, msg: JointState):
        """Callback function to handle incoming JointState messages."""
        joint_names = msg.name
        joint_positions = msg.position  # Positions in radians

        # save new setpoint and approach over time
        for i, joint_name in enumerate(joint_names):
            if joint_name in self._servo_channels:
                servo_channel = self._servo_channels[joint_name]
                self._servo_sps[joint_name] = self.radians_to_degrees(joint_positions[i], joint_name)

    def radians_to_degrees(self, radians, joint_name):
        """Convert radians to degrees within the servo's physical angle limits."""
        angle = radians * (180.0 / 3.14159)  # Convert radians to degrees
        min_angle, max_angle = self._servo_limits[joint_name]
        return max(min(angle, max_angle), min_angle)

    def set_servo_angle(self, channel, angle):
        """Set the servo angle for the given channel."""
        self._servo_kit.servo[channel].angle = angle
        self.get_logger().debug(f'Set channel {channel} to angle {angle} degrees')

