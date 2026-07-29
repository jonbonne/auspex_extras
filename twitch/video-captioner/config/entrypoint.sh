#!/bin/bash
set -e

# Source ROS and workspace
source /opt/ros/iron/setup.bash

if [ -f /ros2_ws/install/setup.bash ]; then
    echo "[entrypoint] Sourcing install space..."
    source /ros2_ws/install/setup.bash
fi

# Source venv
if [ -n "$VIRTUAL_ENV" ]; then
    echo "[entrypoint] Activating virtualenv at $VIRTUAL_ENV"
    export PATH="$VIRTUAL_ENV/bin:$PATH"
    export PYTHONPATH="$VIRTUAL_ENV/lib/python3.12/site-packages:$PYTHONPATH"
fi

# DDS config
unset CYCLONE_DDS_URI
if [ "$RMW_IMPLEMENTATION" = "rmw_cyclonedds_cpp" ]; then

    # first, start RouDi in background
    # make sure /etc/iceoryx/iox_config.toml is in /etc/iceoryx
    iox-roudi -c /etc/iceoryx/iox_config.toml &   # :contentReference[oaicite:0]{index=0}

    export CYCLONE_DDS_URI="$(cat /cyclone-dds.xml)"
    echo "CYCLONE_DDS_URI:\n$CYCLONE_DDS_URI\n"
fi

if [ "$RMW_IMPLEMENTATION" = "rmw_fastrtps_cpp" ]; then
    export FASTDDS_DEFAULT_PROFILES_FILE=/fastdds-config.xml
    echo "FASTDDS_DEFAULT_PROFILES_FILE:\n$FASTDDS_DEFAULT_PROFILES_FILE\n"
fi

# Source bash aliases
[ -f ~/.bash_aliases ] && source ~/.bash_aliases

exec "$@"
