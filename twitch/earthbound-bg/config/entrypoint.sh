#!/usr/bin/env bash
set -e

# DDS config
unset CYCLONE_DDS_URI
if [ "$RMW_IMPLEMENTATION" = "rmw_cyclonedds_cpp" ]; then

    # first, start RouDi in background
    # make sure /etc/iceoryx/iox_config.toml is in /etc/iceoryx
    #iox-roudi -c /etc/iceoryx/iox_config.toml &   # :contentReference[oaicite:0]{index=0}

    export CYCLONE_DDS_URI="$(cat /cyclone-dds.xml)"
    echo "CYCLONE_DDS_URI:\n$CYCLONE_DDS_URI\n"
fi

if [ "$RMW_IMPLEMENTATION" = "rmw_fastrtps_cpp" ]; then
    export FASTDDS_DEFAULT_PROFILES_FILE=/fastdds-config.xml
    echo "FASTDDS_DEFAULT_PROFILES_FILE:\n$FASTDDS_DEFAULT_PROFILES_FILE\n"
fi

# 1) Source the ROS 2 environment
source /opt/ros/${ROS_DISTRO}/setup.bash

# 2) Source your built workspace (if present)
if [ -f /ros2_ws/install/setup.bash ]; then
  echo "[entrypoint] Sourcing install space..."
  source /ros2_ws/install/setup.bash
fi

# 3) Source your aliases
if [ -f ~/.bash_aliases ]; then
  echo "[entrypoint] Sourcing ~/.bash_aliases"
  source ~/.bash_aliases
fi

# 4) Exec whatever was passed (e.g. `ros2 run …`)
exec "$@"
