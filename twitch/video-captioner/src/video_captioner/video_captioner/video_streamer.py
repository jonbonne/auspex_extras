import rclpy
from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSHistoryPolicy
from sensor_msgs.msg import Image, CompressedImage
import cv2
import numpy as np
from cv_bridge import CvBridge


class VideoStreamer(Node):
    def __init__(
        self,
        use_compression=True,
        image_rate_hz=10.0
    ):
        super().__init__('video_streamer_node')
        self.use_compression = use_compression

        # callback groups for concurrent timers
        self.image_cb_group = ReentrantCallbackGroup()

        # QoS profiles
        image_qos = QoSProfile(
            reliability=QoSReliabilityPolicy.BEST_EFFORT,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=1
        )

        # publishers
        if self.use_compression:
            self.compr_publisher_ = self.create_publisher(
                CompressedImage,
                '~/video_image/compressed',
                image_qos,
                callback_group=self.image_cb_group
            )
        else:
            self.image_publisher_ = self.create_publisher(
                Image,
                '~/video_image',
                image_qos,
                callback_group=self.image_cb_group
            )

        # video capture
        self.cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
        self.bridge = CvBridge()

        # timers
        image_timer_period = 1.0 / image_rate_hz
        self.image_timer = self.create_timer(
            image_timer_period,
            self.image_timer_callback,
            callback_group=self.image_cb_group
        )

    def process_image(self, frame):
        # Downscale frame if desired
        #small = frame  # adjust scaling here if needed
        x_scale = 1.0
        y_scale = 1.0
        small = cv2.resize(frame,
                           (int(x_scale * frame.shape[1]), int(y_scale * frame.shape[0])),
                           interpolation=cv2.INTER_AREA)

        if self.use_compression:
            ret, buf = cv2.imencode(
                '.jpg', small, [int(cv2.IMWRITE_JPEG_QUALITY), 70]
            )
            if not ret:
                self.get_logger().error('JPEG encoding failed')
            else:
                msg = CompressedImage()
                msg.header.stamp = self.get_clock().now().to_msg()
                msg.format = 'jpeg'
                msg.data = np.array(buf).tobytes()
                self.compr_publisher_.publish(msg)
        else:
            msg = self.bridge.cv2_to_imgmsg(small, encoding='bgr8')
            self.image_publisher_.publish(msg)

    def image_timer_callback(self):
        ret, frame = self.cap.read()
        if not ret:
            self.get_logger().debug('Failed to capture frame')
            return
        try:
            self.process_image(frame)
        except Exception as err:
            self.get_logger().error(f'Error: {err}')
