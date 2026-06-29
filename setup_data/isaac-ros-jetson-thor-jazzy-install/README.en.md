# Jetson Thor Isaac ROS Jazzy + NITROS Install Guide

This runbook installs NVIDIA Isaac ROS on Jetson Thor running Ubuntu 24.04, then validates the stack with a USB UVC camera and AprilTag detection.

## What this guide covers

- ROS 2 Jazzy environment for Isaac ROS
- Isaac ROS apt repository and CLI
- Manual Docker runtime path for Jetson Thor when `isaac-ros activate` is not enough
- Base Isaac ROS packages
- USB camera validation
- AprilTag + NITROS installation
- End-to-end verification using `/tag_detections`

## Prerequisites

- Jetson Thor / ARM64 machine
- Ubuntu 24.04 (`noble`)
- Docker installed and working
- User has `sudo`
- Recommended free disk: at least 35 GB before AprilTag/NITROS install

## Quick start

One-command-ish install:

```bash
cd /home/ubuntu/.openclaw/workspace/isaac-ros-jetson-thor-jazzy-install
./install.sh
```

Then run the AprilTag validation pipeline:

```bash
cd /home/ubuntu/.openclaw/workspace/isaac-ros-jetson-thor-jazzy-install
./run_apriltag.sh
```

Verify the install:

```bash
cd /home/ubuntu/.openclaw/workspace/isaac-ros-jetson-thor-jazzy-install
./verify_install.sh
```

To also check a live AprilTag detection:

```bash
cd /home/ubuntu/.openclaw/workspace/isaac-ros-jetson-thor-jazzy-install
VERIFY_DETECTION=1 ./verify_install.sh
```

## Included helper scripts

- `install.sh` — installs Isaac ROS CLI, primes the image, starts the dev container, installs base Isaac ROS packages, camera tools, and optionally AprilTag + NITROS.
- `run_apriltag.sh` — copies the launch file into the workspace and starts the USB camera + AprilTag validation pipeline.
- `verify_install.sh` — verifies key ROS packages, container state, and optionally live topics/detections.
- `apriltag_test.launch.py` — minimal validation launch file.

Useful environment variables:

- `ISAAC_ROS_WS` — override default workspace path.
- `ISAAC_ROS_CONTAINER_NAME` — override the container name.
- `INSTALL_APRILTAG=0` — skip the heavy AprilTag/NITROS install during base setup.
- `MIN_FREE_GB` — change the low-disk warning threshold.

## 1. Add Isaac ROS apt repository

```bash
sudo apt update
sudo apt install -y locales curl gnupg software-properties-common
sudo locale-gen en_US en_US.UTF-8
sudo update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8
export LANG=en_US.UTF-8

sudo add-apt-repository universe -y

k="/usr/share/keyrings/nvidia-isaac-ros.gpg"
curl -fsSL https://isaac.download.nvidia.com/isaac-ros/repos.key | sudo gpg --dearmor | sudo tee "$k" > /dev/null

f="/etc/apt/sources.list.d/nvidia-isaac-ros.list"
sudo touch "$f"

s="deb [signed-by=$k] https://isaac.download.nvidia.com/isaac-ros/release-4.4 noble-jetpack main"
grep -qxF "$s" "$f" || echo "$s" | sudo tee -a "$f"

sudo apt update
sudo apt install -y isaac-ros-cli
```

## 2. Create workspace

```bash
mkdir -p ~/workspaces/isaac_ros-dev/src
grep -q 'export ISAAC_ROS_WS=' ~/.bashrc || echo 'export ISAAC_ROS_WS="${ISAAC_ROS_WS:-$HOME/workspaces/isaac_ros-dev}"' >> ~/.bashrc
source ~/.bashrc
```

## 3. Initialize Isaac ROS CLI

```bash
sudo isaac-ros init docker --yes
```

## 4. Check Docker NVIDIA runtime

```bash
docker run --rm hello-world
docker run --rm --runtime=nvidia ubuntu:24.04 bash -lc 'echo "NVIDIA runtime OK"'
```

## 5. Start dev container manually

```bash
docker rm -f isaac_ros_dev_container >/dev/null 2>&1 || true
IMAGE=$(docker images --format '{{.Repository}}:{{.Tag}}' | grep 'nvcr.io/nvidia/isaac/ros:isaac_ros_' | tail -1)

docker run -d --rm \
  --runtime=nvidia \
  --privileged \
  --network host \
  --ipc=host \
  --pid=host \
  -e ISAAC_ROS_PLATFORM=arm64-jetpack \
  -e ISAAC_ROS_WS=/workspaces/isaac_ros-dev \
  -e NVIDIA_VISIBLE_DEVICES=all \
  -e NVIDIA_DRIVER_CAPABILITIES=all \
  -e USER=$USER \
  --workdir /workspaces/isaac_ros-dev \
  -v $HOME/workspaces/isaac_ros-dev:/workspaces/isaac_ros-dev \
  -v /etc/localtime:/etc/localtime:ro \
  -v /usr/bin/tegrastats:/usr/bin/tegrastats \
  -v /sys/kernel/debug:/sys/kernel/debug:ro \
  -v /tmp:/tmp \
  -v /usr/lib/aarch64-linux-gnu/tegra:/usr/lib/aarch64-linux-gnu/tegra \
  -v /usr/src/jetson_multimedia_api:/usr/src/jetson_multimedia_api \
  -v /usr/src/jetson_sipl_api:/usr/src/jetson_sipl_api \
  -v /usr/share/vpi3:/usr/share/vpi3 \
  -v /dev/input:/dev/input \
  -v /dev/bus/usb:/dev/bus/usb \
  --name isaac_ros_dev_container \
  --entrypoint /bin/bash \
  "$IMAGE" -lc 'sleep infinity'
```

## 6. Install base Isaac ROS packages

```bash
docker exec isaac_ros_dev_container bash -lc 'apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y ros-jazzy-isaac-ros-common ros-jazzy-isaac-ros-examples'
```

## 7. Confirm USB camera on host

```bash
lsusb
ls -l /dev/video* /dev/media* /dev/v4l* 2>/dev/null
sudo dmesg | grep -iE 'uvc|video|camera|v4l' | tail -100
```

You want a UVC camera to appear in `lsusb` and a usable `/dev/video0`.

## 8. Recreate container with camera devices mounted

Add the actual camera device nodes seen on the host:

```bash
docker rm -f isaac_ros_dev_container >/dev/null 2>&1 || true
IMAGE=$(docker images --format '{{.Repository}}:{{.Tag}}' | grep 'nvcr.io/nvidia/isaac/ros:isaac_ros_' | tail -1)

docker run -d --rm \
  --runtime=nvidia \
  --privileged \
  --network host \
  --ipc=host \
  --pid=host \
  -e ISAAC_ROS_PLATFORM=arm64-jetpack \
  -e ISAAC_ROS_WS=/workspaces/isaac_ros-dev \
  -e NVIDIA_VISIBLE_DEVICES=all \
  -e NVIDIA_DRIVER_CAPABILITIES=all \
  -e USER=$USER \
  --workdir /workspaces/isaac_ros-dev \
  -v $HOME/workspaces/isaac_ros-dev:/workspaces/isaac_ros-dev \
  -v /etc/localtime:/etc/localtime:ro \
  -v /usr/bin/tegrastats:/usr/bin/tegrastats \
  -v /sys/kernel/debug:/sys/kernel/debug:ro \
  -v /tmp:/tmp \
  -v /usr/lib/aarch64-linux-gnu/tegra:/usr/lib/aarch64-linux-gnu/tegra \
  -v /usr/src/jetson_multimedia_api:/usr/src/jetson_multimedia_api \
  -v /usr/src/jetson_sipl_api:/usr/src/jetson_sipl_api \
  -v /usr/share/vpi3:/usr/share/vpi3 \
  -v /dev/input:/dev/input \
  -v /dev/bus/usb:/dev/bus/usb \
  -v /dev/video0:/dev/video0 \
  -v /dev/video1:/dev/video1 \
  -v /dev/media0:/dev/media0 \
  -v /dev/media1:/dev/media1 \
  --name isaac_ros_dev_container \
  --entrypoint /bin/bash \
  "$IMAGE" -lc 'sleep infinity'
```

## 9. Install camera tools and verify streaming

```bash
docker exec isaac_ros_dev_container bash -lc 'apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y v4l-utils ros-jazzy-v4l2-camera'
docker exec isaac_ros_dev_container bash -lc 'v4l2-ctl --list-devices'
docker exec isaac_ros_dev_container bash -lc 'source /opt/ros/jazzy/setup.bash && ros2 run v4l2_camera v4l2_camera_node --ros-args -p video_device:=/dev/video0 -p image_size:=[640,480] -p pixel_format:=YUYV -r image_raw:=/camera/image_raw -r camera_info:=/camera/camera_info'
```

In another shell:

```bash
docker exec isaac_ros_dev_container bash -lc 'source /opt/ros/jazzy/setup.bash && timeout 15 ros2 topic hz /camera/image_raw'
```

Expected: roughly 30 FPS for a 640x480 Logitech C922-style camera.

## 10. Install AprilTag + NITROS

```bash
docker exec isaac_ros_dev_container bash -lc 'apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y ros-jazzy-isaac-ros-apriltag ros-jazzy-isaac-ros-apriltag-interfaces'
```

This step is large and can take a long time. It may pull many GB of CUDA/TensorRT dependencies.

## 11. Launch validation pipeline

Create `~/workspaces/isaac_ros-dev/apriltag_test.launch.py` from the provided template, then run:

```bash
docker cp ~/workspaces/isaac_ros-dev/apriltag_test.launch.py isaac_ros_dev_container:/workspaces/isaac_ros-dev/apriltag_test.launch.py
docker exec isaac_ros_dev_container bash -lc 'source /opt/ros/jazzy/setup.bash && ros2 launch /workspaces/isaac_ros-dev/apriltag_test.launch.py'
```

## 12. Validate outputs

```bash
docker exec isaac_ros_dev_container bash -lc 'source /opt/ros/jazzy/setup.bash && ros2 topic list | grep -E "camera|tag|nitros" | sort'
docker exec isaac_ros_dev_container bash -lc 'source /opt/ros/jazzy/setup.bash && timeout 15 ros2 topic echo --once /tag_detections'
```

Expected:

- `/camera/image_raw`
- `/camera/image_raw/nitros`
- `/tag_detections`
- A valid detection containing tag family and id

## Notes

- If detection works but pose is `nan`, camera calibration is missing.
- If `/dev/video0` does not exist, fix the host camera layer before debugging Isaac ROS.
- If `isaac-ros activate` fails, the manual `--runtime=nvidia` path is acceptable and was validated on Jetson Thor.
