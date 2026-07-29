# -------- Base stage with common dependencies --------
FROM ros:iron-ros-base AS base

# Install system and ROS 2 dependencies
RUN apt-get update && apt-get install -y \
    python3-pip \
    python3-venv \
    python3-opencv \
    ros-iron-ament-cmake-python \
    ros-iron-cv-bridge \
    ros-iron-sensor-msgs \
    ros-iron-std-msgs \
    ros-iron-rmw-cyclonedds-cpp \
    libv4l-dev \
    v4l-utils \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-libav \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
RUN python3 -m venv --system-site-packages $VIRTUAL_ENV && \
    $VIRTUAL_ENV/bin/pip install --no-cache-dir \
    catkin_pkg \
    transformers \
    torch \
    torchvision

# -------- Build stage --------
FROM base AS builder

WORKDIR /ros2_ws
COPY ./src ./src

RUN . /opt/ros/iron/setup.sh && \
    colcon build --packages-select video_captioner && \
    . install/setup.sh

# -------- Runtime stage --------
FROM base AS runtime

COPY --from=builder /ros2_ws/install /ros2_ws/install

# Optional: .bash_aliases and entrypoint
COPY ./config/bash_aliases /root/.bash_aliases
COPY ./config/entrypoint.sh /entrypoint.sh
COPY ./config/fastdds-config.xml /fastdds-config.xml
COPY ./config/cyclone-dds.xml /cyclone-dds.xml
COPY ./config/iox_config.toml /etc/iceoryx/iox_config.toml
RUN chmod +x /entrypoint.sh

WORKDIR /ros2_ws
ENTRYPOINT ["/entrypoint.sh"]
CMD ["bash"]
