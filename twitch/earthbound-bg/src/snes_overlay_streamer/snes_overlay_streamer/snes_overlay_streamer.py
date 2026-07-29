import rclpy
from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSHistoryPolicy
from rclpy.parameter_client import AsyncParameterClient
from rclpy.parameter import Parameter
from rcl_interfaces.msg import ParameterEvent

import pygame
from std_msgs.msg import String
from sensor_msgs.msg import Image, CompressedImage
from cv_bridge import CvBridge
import cv2

from snes_overlay_streamer.psychedelic_background import PsychedelicBackground

def getParam(node, other_node, other_node_param_client, param_name):

    some_param = None
    # ———————— STEP 2: wait for the service ————————
    ready = other_node_param_client.wait_for_services(timeout_sec=2.0)
    if not ready:
        node.get_logger().error(f'{other_node} parameter service not available – continuing with defaults')
        some_param = None
    else:
        # ———————— STEP 3: request the parameter ——————
        future = other_node_param_client.get_parameters([param_name])
        rclpy.spin_until_future_complete(node, future)
        resp = future.result()
        if resp is None or not resp.values:
            node.get_logger().warn(f'no value returned for /{other_node}/{param_name}')
            some_param = None
        else:
            val = resp.values[0]
            # ———————— STEP 4: type‐check & store ————————
            if val.type == Parameter.Type.STRING.value:
                some_param = val.string_value
            elif val.type == Parameter.Type.INTEGER.value:
                some_param = val.integer_value
            else:
                node.get_logger().warn(f'unsupported type for {param_name}: {val.type}')
                some_param = None
    return some_param

class OverlayNode(Node):
    def __init__(self, use_compression=True):
        super().__init__('snes_overlay_streamer')
        self.use_compression = use_compression

        self.model_name = "unknown"
        self.model_role = "unknown"
        self.vox_target = "/unknown"

        # Callback groups for concurrent subscriptions
        self.caption_cb_group = ReentrantCallbackGroup()
        self.image_cb_group = ReentrantCallbackGroup()

        # QoS profiles matching publisher
        self.caption_qos = QoSProfile(
            reliability=QoSReliabilityPolicy.RELIABLE,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=10
        )
        self.image_qos = QoSProfile(
            reliability=QoSReliabilityPolicy.BEST_EFFORT,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=1
        )
        self.param_event_qos = QoSProfile(
            reliability=QoSReliabilityPolicy.RELIABLE,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=10
        )

        # params for grid
        #line_opacity=0.25, circuit_speed=1.5, line_thickness=9.0, grid_spread=20)
        self.declare_parameter('line_opacity', 0.1)
        self.declare_parameter('circuit_speed', 15.0)
        self.declare_parameter('line_thickness', 4.0)
        self.declare_parameter('grid_spread', 16)
        self.declare_parameter('pan_speed', 0.05)

    def __init_parameters__(self):

        # parameter clients to facilitate param lookups below
        self.param_clients = {
                '/chatter': AsyncParameterClient(self, 'chatter'),
                '/speaker': AsyncParameterClient(self, 'speaker'),
                '/snes_overlay_streamer': AsyncParameterClient(self, 'snes_overlay_streamer'),
        }

        # Parameters to display from other nodes
        self.vox_target = getParam(self, 'speaker', self.param_clients['/speaker'], 'copy_voice_target')
        self.get_logger().info(f"[OverlayNode] Found '/speaker/copy_voice_target': {self.vox_target}")

        self.model_name = getParam(self, 'chatter', self.param_clients['/chatter'], 'model')
        self.get_logger().info(f"[OverlayNode] Found '/chatter/model': {self.model_name}")

        self.model_role = getParam(self, 'chatter', self.param_clients['/chatter'], 'role')
        self.get_logger().info(f"[OverlayNode] Found '/chatter/role': {self.model_role}")

        self.line_opacity = self.get_parameter('line_opacity').value
        self.circuit_speed = self.get_parameter('circuit_speed').value
        self.line_thickness = self.get_parameter('line_thickness').value
        self.grid_spread = self.get_parameter('grid_spread').value
        self.pan_speed = self.get_parameter('pan_speed').value

        return True

    def initialize(self, screen):

        if not self.__init_parameters__():
            return False

        # PsychedelicBackground has several modes now:
        # 1 - Horizontal+Vertical wave (original)
        # 2 - Swirl vortex
        # 3 - Perspective stripe (Mode7-like)
        # 4 - Radial ripples
        # 5 - Star Field
        init_mode = 5
        self.declare_parameter('bg_mode', init_mode)
        init_mode = self.get_parameter('bg_mode').value
        W, H = screen.get_size()
        self.psyche_bg = PsychedelicBackground(9 * W // 10, 9 * H // 10,
                                               mode=init_mode,
                                               star_count=250, seed=42,
                                               sparkle_count=100,
                                               pan_speed=self.pan_speed,
                                               line_opacity=self.line_opacity,
                                               circuit_speed=self.circuit_speed,
                                               line_thickness=self.line_thickness,
                                               grid_spread=self.grid_spread)

        self.last_top_ticker_event = self.get_clock().now()
        self.last_bottom_ticker_event = self.get_clock().now()

        # Subscribers for captions
        self.top_ticker_text = "-_-   zZz   "
        self.create_subscription(
            String,
            '/chatter/info_text/simple',
            self.top_ticker_cb,
            qos_profile=self.caption_qos,
            callback_group=self.caption_cb_group
        )
        self.bottom_ticker_text = "waiting for captions..."
        self.create_subscription(
            String,
            '/video_captioner/video_caption',
            self.bottom_ticker_cb,
            qos_profile=self.caption_qos,
            callback_group=self.caption_cb_group
        )

        # Good Image subscriber
        self.bridge = CvBridge()
        self.latest_image = None
        self.latest_camera_image = None
        if self.use_compression:
            self.create_subscription(
                CompressedImage,
                '/video_captioner/video_image/compressed',
                self.compressed_img_cb,
                qos_profile=self.image_qos,
                callback_group=self.image_cb_group
            )

            self.create_subscription(
                CompressedImage,
                '/camera_captioner/video_image/compressed',
                self.camera_compressed_img_cb,
                qos_profile=self.image_qos,
                callback_group=self.image_cb_group
            )

        else:
            self.create_subscription(
                Image,
                '/video_captioner/video_image',
                self.image_cb,
                qos_profile=self.image_qos,
                callback_group=self.image_cb_group
            )
            self.create_subscription(
                Image,
                '/camera_captioner/video_image',
                self.camera_image_cb,
                qos_profile=self.image_qos,
                callback_group=self.image_cb_group
            )

        # Subscribe to parameter updates
        self.create_subscription(
            ParameterEvent,
            '/parameter_events',
            self.__params_cb__,
            qos_profile=self.param_event_qos,
            callback_group=self.caption_cb_group
        )

        # todo: need custom msg
        ### subscribe to billboard updates
        ###self._bbsub = self.create_subscription(
        ###    StringVector,
        ###    'string_list_topic',
        ###    self.listener_callback,
        ###    10)

        return True

    def top_ticker_cb(self, msg: String):
        """Caption callback for top ticker"""
        self.last_top_ticker_event = self.get_clock().now()
        self.top_ticker_text = msg.data

    def bottom_ticker_cb(self, msg: String):
        """Caption callback for bottom ticker"""
        self.last_bottom_ticker_event = self.get_clock().now()
        self.bottom_ticker_text = msg.data

    def image_cb(self, msg: Image):
        """Raw Image callback"""
        try:
            bgr = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
            self.latest_image = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        except Exception as e:
            self.get_logger().error(f"Image conversion failed: {e}")

    def compressed_img_cb(self, msg: CompressedImage):
        """Compressed Image callback"""
        try:
            bgr = self.bridge.compressed_imgmsg_to_cv2(
                msg, desired_encoding='bgr8'
            )
            self.latest_image = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        except Exception as e:
            self.get_logger().error(f"Decompression failed: {e}")

    def camera_image_cb(self, msg: Image):
        """Raw Image callback"""
        try:
            bgr = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
            self.latest_camera_image = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        except Exception as e:
            self.get_logger().error(f"Image conversion failed: {e}")

    def camera_compressed_img_cb(self, msg: CompressedImage):
        """Compressed Image callback"""
        try:
            bgr = self.bridge.compressed_imgmsg_to_cv2(
                msg, desired_encoding='bgr8'
            )
            self.latest_camera_image = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        except Exception as e:
            self.get_logger().error(f"Decompression failed: {e}")

    def __params_cb__(self, event: ParameterEvent):
        """Callback for handling parameter changes"""
        try:
            # Only react to changes from the relevant node
            if event.node not in self.param_clients.keys():
                return
            for param in event.changed_parameters:
                if param.name == 'model':
                    self.model_name = param.value.string_value
                    self.get_logger().info(f"Model parameter 'model_name' updated: {self.model_name}")
                if param.name == 'role':
                    self.model_role = param.value.string_value
                    self.get_logger().info(f"Model parameter 'model_role' updated: {self.model_role}")
                if param.name == 'copy_voice_target':
                    self.vox_target = param.value.string_value
                    self.get_logger().info(f"Model parameter 'copy_voice_target' updated: {self.vox_target}")
                if param.name == 'line_opacity':
                    self.psyche_bg.line_opacity = param.value.double_value
                    self.get_logger().info(f"Model parameter 'line_opacity' updated: {self.psyche_bg.line_opacity}")
                if param.name == 'circuit_speed':
                    self.psyche_bg.circuit_speed = param.value.double_value
                    self.get_logger().info(f"Model parameter 'circuit_speed' updated: {self.psyche_bg.circuit_speed}")
                if param.name == 'line_thickness':
                    self.psyche_bg.line_thickness = param.value.double_value
                    self.get_logger().info(f"Model parameter 'line_thickness' updated: {self.psyche_bg.line_thickness}")
                if param.name == 'grid_spread':
                    self.psyche_bg.grid_spread = param.value.integer_value
                    self.get_logger().info(f"Model parameter 'grid_spread' updated: {self.psyche_bg.grid_spread}")
                if param.name == 'pan_speed':
                    self.psyche_bg.pan_speed = param.value.double_value
                    self.get_logger().info(f"Model parameter 'pan_speed' updated: {self.psyche_bg.pan_speed}")

                if param.name == 'bg_mode':
                    try:
                        self.psyche_bg.set_mode(param.value.integer_value)
                        self.get_logger().info(f"Model parameter 'bg_mode' updated: {self.psyche_bg.mode}")
                    except ValueError:
                        self.get_logger().warn(f"Model parameter 'bg_mode' was invalid!")

        except Exception as e:
            self.get_logger().error(f"Params cb failed: {e}")

    def render_bg(self, screen):
        # background animation (earthbound style)
        W, H = screen.get_size()
        screen.blit(self.psyche_bg.render(), (H // 20, W // 20))

    def get_raw_surface(self) -> pygame.Surface | None:
        """
        Returns:
          A pygame.Surface built from the latest_image (RGB), or
          None if no image has arrived yet.
        """
        if self.latest_image is None:
            return None

        h, w, _ = self.latest_image.shape
        return pygame.image.frombuffer(
            self.latest_image.tobytes(), (w, h), 'RGB'
        )

    def get_raw_camera_surface(self) -> pygame.Surface | None:
        """
        Returns:
          A pygame.Surface built from the latest_image (RGB), or
          None if no image has arrived yet.
        """
        if self.latest_camera_image is None:
            return None

        h, w, _ = self.latest_camera_image.shape
        return pygame.image.frombuffer(
            self.latest_camera_image.tobytes(), (w, h), 'RGB'
        )

    def update_billboard(self, pd_x, pd_y):
        '''
        redefine the text
        TODO: use a topic to update
        '''

        # billboard_entries = {
        #     'model_name': tuple([lambda: f"model: {self.model_name}", (pd_x + 10, pd_y)]),
        #     'vox_target': tuple([lambda: f"vox_target: {self.vox_target.split('/')[-1]}", (pd_x + 10, pd_y + 25)]),
        #     #'model_role': tuple([lambda: self.model_role, (pd_x + 10, pd_y + 60)]),
        # }
        X_OFFSET_TEMP = 50

        # 10/22/25
        #item_list = [
        #    "GAMES:",
        #    "- Clean up in metroid zero mission? 100% ???",
        #    "- nah. 100% later.",
        #    "- mystery genesis box??",
        #    "- golf????",
        #    "MISC:",
        #    "  history of federalism",
        #    "    vs anti-federalism",
        #    "          (SIEG ZEON!)"]

        # 10/22/25
        item_list = [
            "Coding:",
            "- hobby framework",
            "- ???",
            "MISC:",
            "- ultramarines successor chapter:",
            "    The Order of the 13th Circuit"
        ]

        billboard_entries = []
        for n, it in enumerate(item_list):
          print(f"??? {n}|{it}")
          pval = tuple([f"{item_list[n]}", (pd_x + X_OFFSET_TEMP, pd_y + 25*n)])
          billboard_entries.append(pval)

        return billboard_entries

