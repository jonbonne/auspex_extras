#!/usr/bin/env bash
set -euo pipefail

LOOP_IDX=10
LOOP_DEV="/dev/video${LOOP_IDX}"
REAL_DEV="/dev/video0"

# 1) Ensure v4l2loopback is loaded at index 10
if ! ls "${LOOP_DEV}" &>/dev/null; then
  echo "[loopback] Loading /dev/video${LOOP_IDX}..."
  sudo modprobe v4l2loopback \
    devices=1 \
    video_nr=${LOOP_IDX} \
    card_label="OBS Loopback" \
    exclusive_caps=0
  sleep 1
fi

# 2) (Re)start ffmpeg bridge if needed
if ! pgrep -f "ffmpeg.*${REAL_DEV}.*${LOOP_DEV}" &>/dev/null; then
  echo "[loopback] Starting ffmpeg ${REAL_DEV} → ${LOOP_DEV}..."
  nohup ffmpeg -f v4l2 -i "${REAL_DEV}" -codec copy -f v4l2 "${LOOP_DEV}" \
    > /tmp/obs-loopback.log 2>&1 &
  sleep 1
fi

# 3) Launch your container with /dev/video10 mapped as /dev/video0
echo "[docker] Bringing up container..."
docker compose up --build
