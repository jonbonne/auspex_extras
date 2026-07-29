from collections import deque
import queue
import rclpy
from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSHistoryPolicy
from std_msgs.msg import String
from sensor_msgs.msg import Image, CompressedImage
import cv2
import numpy as np
from cv_bridge import CvBridge
import torch
from transformers import BlipProcessor, BlipForConditionalGeneration
from PIL import Image as PILImage


class VideoCaptioner(Node):
    def __init__(
        self,
        use_compression=True,
        video_device_idx=0,
        image_rate_hz=10.0,
        caption_rate_sec=2.0,
        caption_model_name="Salesforce/blip-image-captioning-base",
    ):
        super().__init__('video_captioner_node')
        self.use_compression = use_compression

        # Declare parameters to allow overriding via launch
        self.declare_parameter('video_device_idx', video_device_idx)
        self.declare_parameter('image_rate_hz', image_rate_hz)
        self.declare_parameter('caption_rate_sec', caption_rate_sec)

        # Override defaults with parameter values
        video_device_idx = self.get_parameter('video_device_idx').value
        image_rate_hz = self.get_parameter('image_rate_hz').value
        caption_rate_sec = self.get_parameter('caption_rate_sec').value

        # Choose device
        self.device = torch.device(
            "cuda" if torch.cuda.is_available() else "cpu"
        )

        # Initialize processor and model
        self.processor = BlipProcessor.from_pretrained(caption_model_name)
        self.model = (
            BlipForConditionalGeneration.from_pretrained(caption_model_name)
            .to(self.device)
            .eval()
        )

        # callback groups for concurrent timers
        self.image_cb_group = ReentrantCallbackGroup()
        self.caption_cb_group = ReentrantCallbackGroup()

        # how many times the *same* caption may be published within the window
        self.max_repeats = 1
        # window (in seconds) during which repeats are suppressed
        self.window_sec = 30.0

        # history: caption_text -> deque of rclpy Time stamps (oldest at left)
        self.caption_history = {}

        # QoS profiles
        image_qos = QoSProfile(
            reliability=QoSReliabilityPolicy.BEST_EFFORT,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=1
        )
        caption_qos = QoSProfile(
            reliability=QoSReliabilityPolicy.RELIABLE,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=10
        )
        ticker_qos = QoSProfile(
            reliability=QoSReliabilityPolicy.RELIABLE,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=1
        )

        self.frame_queue = queue.Queue(10)

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

        self.caption_publisher_ = self.create_publisher(
            String,
            '~/video_caption',
            caption_qos,
            callback_group=self.caption_cb_group
        )

        # subscriber for scrolling ticker text
        self.ticker_text = ""
        self.ticker_offset = None
        self.ticker_subscriber_ = self.create_subscription(
            String,
            '~/ticker_text',
            self._on_ticker_msg,
            ticker_qos,
            callback_group=self.image_cb_group
        )

        # video capture
        self.cap = cv2.VideoCapture(video_device_idx, cv2.CAP_V4L2)
        self.bridge = CvBridge()

        # timers
        image_timer_period = 1.0 / image_rate_hz
        self.image_timer = self.create_timer(
            image_timer_period,
            self.image_timer_callback,
            callback_group=self.image_cb_group
        )
        self.caption_timer = self.create_timer(
            caption_rate_sec,
            self.caption_timer_callback,
            callback_group=self.caption_cb_group
        )

    def process_image(self, frame):
        # Downscale frame if desired
        #small = frame  # adjust scaling here if needed
        x_scale = 0.75
        y_scale = 0.75
        small = cv2.resize(frame,
                           (int(x_scale * frame.shape[1]), int(y_scale * frame.shape[0])),
                           interpolation=cv2.INTER_AREA)

        # Overlay scrolling ticker
        small = self._overlay_ticker(small)

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

    def process_caption(self, frame):
        # Convert BGR to RGB and to PIL
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_img = PILImage.fromarray(rgb)

        # Prepare inputs and move to device
        inputs = self.processor(
            images=pil_img,
            return_tensors="pt"
        ).to(self.device)

        # Generate caption
        out = self.model.generate(
            **inputs,
            max_new_tokens=30
        )
        caption = self.processor.tokenizer.decode(
            out[0], skip_special_tokens=True
        )

        # Publish only if its fresh
        self.try_publish(caption)

    def try_publish(self, caption: str):
        '''
        Publishes fresher generations, keeps history
        '''
        now = self.get_clock().now()

        # get (or create) the deque of past publish times for this caption
        times = self.caption_history.setdefault(caption, deque())

        # purge any timestamps older than window_sec
        while times and (now - times[0]).nanoseconds * 1e-9 > self.window_sec:
            times.popleft()

        if len(times) < self.max_repeats:
            # it’s fresh enough → publish
            msg = String()
            msg.data = caption
            self.caption_publisher_.publish(msg)
            self.get_logger().debug(f'Published caption: "{caption}"')
            # record this publish time
            times.append(now)
        else:
            # too many repeats in last window_sec → skip
            self.get_logger().debug(
                f'Skipped duplicate caption (published {len(times)}× in past '
                f'{self.window_sec}s): "{caption}"'
            )

    def caption_timer_callback(self):
        try:
            frame = self.frame_queue.get_nowait()
            self.process_caption(frame)
        except queue.Empty:
            return

    def image_timer_callback(self):
        ret, frame = self.cap.read()
        if not ret:
            self.get_logger().debug('Failed to capture frame')
            return
        try:
            self.process_image(frame)
            self.frame_queue.put_nowait(frame)
        except queue.Full:
            self.frame_queue.get_nowait()
            self.frame_queue.put_nowait(frame)

    def _on_ticker_msg(self, msg: String):
        self.ticker_text = msg.data

    def _overlay_ticker(self, frame: np.ndarray) -> np.ndarray:
        h, w = frame.shape[:2]
        if self.ticker_offset is None:
            self.ticker_offset = w

        text = self.ticker_text or ""
        font = cv2.FONT_HERSHEY_SIMPLEX
        scale = 0.7
        thickness = 2
        (text_w, text_h), _ = cv2.getTextSize(text, font, scale, thickness)

        y = h - 10  # 10 px above bottom

        # outline
        cv2.putText(
            frame,
            text,
            (int(self.ticker_offset), y),
            font,
            scale,
            (0, 0, 0),
            thickness + 2,
            cv2.LINE_AA
        )
        # text
        cv2.putText(
            frame,
            text,
            (int(self.ticker_offset), y),
            font,
            scale,
            (255, 255, 255),
            thickness,
            cv2.LINE_AA
        )

        self.ticker_offset -= 2
        if self.ticker_offset < -text_w:
            self.ticker_offset = w

        return frame
