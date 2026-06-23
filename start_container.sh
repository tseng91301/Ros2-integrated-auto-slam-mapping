#!/usr/bin/env bash
set -euo pipefail

IMAGE="cached_isaac_run_dev_image_local:latest"
CONTAINER_NAME="isaac_ros_dev_container"
ISAAC_ROS_WS="/home/ubuntu/workspaces/isaac_ros-dev"

echo "Starting container ${CONTAINER_NAME} using ${IMAGE}..."
docker rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true

args=(
  run -d --rm
  --runtime=nvidia
  --privileged
  --network host
  --ipc=host
  --pid=host
  -e ISAAC_ROS_PLATFORM=arm64-jetpack
  -e ISAAC_ROS_WS=/workspaces/isaac_ros-dev
  -e NVIDIA_VISIBLE_DEVICES=all
  -e NVIDIA_DRIVER_CAPABILITIES=all
  -e USER="ubuntu"
  --workdir /workspaces/isaac_ros-dev
  -v "${ISAAC_ROS_WS}:/workspaces/isaac_ros-dev"
  -v /etc/localtime:/etc/localtime:ro
  -v /tmp:/tmp
  --name "${CONTAINER_NAME}"
  --entrypoint /bin/bash
)

for path in \
  /usr/bin/tegrastats \
  /sys/kernel/debug \
  /usr/lib/aarch64-linux-gnu/tegra \
  /usr/src/jetson_multimedia_api \
  /usr/src/jetson_sipl_api \
  /usr/share/vpi3 \
  /dev/input \
  /dev/bus/usb \
  /dev/video0 \
  /dev/video1 \
  /dev/media0 \
  /dev/media1; do
  if [ -e "$path" ]; then
    args+=( -v "$path:$path" )
  fi
done

args+=( "$IMAGE" -lc 'sleep infinity' )
docker "${args[@]}"

echo "Container ${CONTAINER_NAME} started successfully!"
