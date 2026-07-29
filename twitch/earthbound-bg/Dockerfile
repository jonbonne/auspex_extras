ARG ROS_DISTRO=jazzy

# ─────────── Base Stage ───────────
FROM ros:${ROS_DISTRO}-ros-base AS base

# Install system & ROS2 build/runtime deps
RUN apt-get update && apt-get install -y \
    python3-pip \
    python3-opencv \
    python3-pygame \
    python3-numpy \
    python3-colcon-common-extensions \
    ros-${ROS_DISTRO}-ament-cmake-python \
    ros-${ROS_DISTRO}-rclpy \
    ros-${ROS_DISTRO}-cv-bridge \
    ros-${ROS_DISTRO}-std-msgs \
    ros-${ROS_DISTRO}-sensor-msgs \
    ros-${ROS_DISTRO}-rmw-cyclonedds-cpp \
 && rm -rf /var/lib/apt/lists/*

SHELL ["/bin/bash", "-lc"]

# ─────────── Builder Stage ───────────
FROM base AS builder
WORKDIR /ros2_ws
# Copy your ROS2 workspace src
COPY ./src ./src

# Build only the overlay package
RUN . /opt/ros/${ROS_DISTRO}/setup.bash \
 && colcon build --packages-select snes_overlay_streamer

# ─────────── Runtime Stage ───────────
FROM base AS runtime
WORKDIR /ros2_ws

# Copy only the install space from builder
COPY --from=builder /ros2_ws/install /ros2_ws/install

# Copy your bash aliases and entrypoint
COPY ./config/bash_aliases /root/.bash_aliases
COPY ./config/entrypoint.sh /entrypoint.sh
COPY ./config/fastdds-config.xml /fastdds-config.xml
COPY ./config/cyclone-dds.xml /cyclone-dds.xml
COPY ./config/iox_config.toml /etc/iceoryx/iox_config.toml
COPY ./config/fonts /fonts
RUN chmod +x /entrypoint.sh

# Entrypoint will source ROS & your aliases, then exec the cmd
ENTRYPOINT ["/entrypoint.sh"]
