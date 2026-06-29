# Jetson Thor Isaac ROS Jazzy + NITROS 安裝指南

這份文件用來在 Jetson Thor 的 Ubuntu 24.04 上安裝 NVIDIA Isaac ROS，並使用 USB UVC 相機加上 AprilTag 偵測來驗證整個流程是否正常。

## 這份指南包含什麼

- 給 Isaac ROS 使用的 ROS 2 Jazzy 環境
- Isaac ROS apt repository 與 CLI 安裝
- 當 `isaac-ros activate` 不夠穩定時，Jetson Thor 可用的手動 Docker runtime 路線
- 基礎 Isaac ROS 套件安裝
- USB 相機驗證
- AprilTag + NITROS 安裝
- 使用 `/tag_detections` 做端到端驗證

## 前置條件

- Jetson Thor / ARM64 機器
- Ubuntu 24.04 (`noble`)
- 已安裝且可正常使用的 Docker
- 使用者具備 `sudo` 權限
- 建議在安裝 AprilTag/NITROS 前至少保留 35 GB 可用空間

## 快速開始

接近一鍵的安裝方式：

```bash
cd /home/ubuntu/.openclaw/workspace/isaac-ros-jetson-thor-jazzy-install
./install.sh
```

接著啟動 AprilTag 驗證流程：

```bash
cd /home/ubuntu/.openclaw/workspace/isaac-ros-jetson-thor-jazzy-install
./run_apriltag.sh
```

驗證安裝結果：

```bash
cd /home/ubuntu/.openclaw/workspace/isaac-ros-jetson-thor-jazzy-install
./verify_install.sh
```

如果也要檢查即時的 AprilTag detection：

```bash
cd /home/ubuntu/.openclaw/workspace/isaac-ros-jetson-thor-jazzy-install
VERIFY_DETECTION=1 ./verify_install.sh
```

## 內含的輔助腳本

- `install.sh` — 安裝 Isaac ROS CLI、預抓 image、啟動 dev container、安裝基礎 Isaac ROS 套件、相機工具，以及可選的 AprilTag + NITROS。
- `run_apriltag.sh` — 將 launch file 複製到 workspace，並啟動 USB 相機 + AprilTag 驗證流程。
- `verify_install.sh` — 驗證關鍵 ROS 套件、container 狀態，並可選擇檢查 live topic / detection。
- `apriltag_test.launch.py` — 最小可用的驗證 launch file。

常用環境變數：

- `ISAAC_ROS_WS` — 覆寫預設 workspace 路徑。
- `ISAAC_ROS_CONTAINER_NAME` — 覆寫 container 名稱。
- `INSTALL_APRILTAG=0` — 在基礎安裝時跳過較重的 AprilTag/NITROS 安裝。
- `MIN_FREE_GB` — 調整低磁碟空間警告門檻。

## 1. 加入 Isaac ROS apt repository

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

## 2. 建立 workspace

```bash
mkdir -p ~/workspaces/isaac_ros-dev/src
grep -q 'export ISAAC_ROS_WS=' ~/.bashrc || echo 'export ISAAC_ROS_WS="${ISAAC_ROS_WS:-$HOME/workspaces/isaac_ros-dev}"' >> ~/.bashrc
source ~/.bashrc
```

## 3. 初始化 Isaac ROS CLI

```bash
sudo isaac-ros init docker --yes
```

## 4. 檢查 Docker NVIDIA runtime

```bash
docker run --rm hello-world
docker run --rm --runtime=nvidia ubuntu:24.04 bash -lc 'echo "NVIDIA runtime OK"'
```

## 5. 手動啟動 dev container

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

## 6. 安裝基礎 Isaac ROS 套件

```bash
docker exec isaac_ros_dev_container bash -lc 'apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y ros-jazzy-isaac-ros-common ros-jazzy-isaac-ros-examples'
```

## 7. 在 host 上確認 USB 相機

```bash
lsusb
ls -l /dev/video* /dev/media* /dev/v4l* 2>/dev/null
sudo dmesg | grep -iE 'uvc|video|camera|v4l' | tail -100
```

你需要看到 UVC 相機出現在 `lsusb` 中，並且有可用的 `/dev/video0`。

## 8. 重新建立並掛載 camera device 的 container

把 host 上實際看到的 camera device node 掛進 container：

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

## 9. 安裝 camera 工具並驗證串流

```bash
docker exec isaac_ros_dev_container bash -lc 'apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y v4l-utils ros-jazzy-v4l2-camera'
docker exec isaac_ros_dev_container bash -lc 'v4l2-ctl --list-devices'
docker exec isaac_ros_dev_container bash -lc 'source /opt/ros/jazzy/setup.bash && ros2 run v4l2_camera v4l2_camera_node --ros-args -p video_device:=/dev/video0 -p image_size:=[640,480] -p pixel_format:=YUYV -r image_raw:=/camera/image_raw -r camera_info:=/camera/camera_info'
```

另一個 shell 可檢查：

```bash
docker exec isaac_ros_dev_container bash -lc 'source /opt/ros/jazzy/setup.bash && timeout 15 ros2 topic hz /camera/image_raw'
```

預期結果：像 Logitech C922 這類 640x480 模式大約可達 30 FPS。

## 10. 安裝 AprilTag + NITROS

```bash
docker exec isaac_ros_dev_container bash -lc 'apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y ros-jazzy-isaac-ros-apriltag ros-jazzy-isaac-ros-apriltag-interfaces'
```

這一步很大，可能會花不少時間，也可能拉下數 GB 的 CUDA / TensorRT 相依套件。

## 11. 啟動驗證 pipeline

先用提供的模板建立 `~/workspaces/isaac_ros-dev/apriltag_test.launch.py`，然後執行：

```bash
docker cp ~/workspaces/isaac_ros-dev/apriltag_test.launch.py isaac_ros_dev_container:/workspaces/isaac_ros-dev/apriltag_test.launch.py
docker exec isaac_ros_dev_container bash -lc 'source /opt/ros/jazzy/setup.bash && ros2 launch /workspaces/isaac_ros-dev/apriltag_test.launch.py'
```

## 12. 驗證輸出

```bash
docker exec isaac_ros_dev_container bash -lc 'source /opt/ros/jazzy/setup.bash && ros2 topic list | grep -E "camera|tag|nitros" | sort'
docker exec isaac_ros_dev_container bash -lc 'source /opt/ros/jazzy/setup.bash && timeout 15 ros2 topic echo --once /tag_detections'
```

預期應看到：

- `/camera/image_raw`
- `/camera/image_raw/nitros`
- `/tag_detections`
- 含有 tag family 與 id 的有效 detection

## 備註

- 如果 detection 有出來，但 pose 是 `nan`，通常代表 camera calibration 尚未提供。
- 如果 `/dev/video0` 不存在，請先修正 host 端的 camera 層，再回來除錯 Isaac ROS。
- 如果 `isaac-ros activate` 不穩，改用手動 `--runtime=nvidia` 路線是可以接受的，而且已在 Jetson Thor 上驗證過。
