# 🐳 Isaac ROS Docker 環境安裝與啟動指南

本指南說明如何在 Jetson Thor (Ubuntu 24.04 + Jetpack) 上安裝、初始化並管理 Isaac ROS Docker 開發環境。

> [!IMPORTANT]
> **專案開發與執行必備 Apt 套件清單**：
> 為了成功編譯和執行此工作空間中的所有 ROS 2 功能包（如底盤控制、雷達、SLAM、網頁遙控、RealSense 相機等），Docker 容器內部必須安裝以下套件。
> 
> 這些套件**已整合至 `install.sh` 啟動指令中**，在一鍵部署時會自動完成安裝。若您使用現有或自建容器，可使用下方提供的安裝指令手動安裝。
> 
> #### 1. 核心開發與編譯工具
> * `build-essential`：基礎 C/C++ 編譯器與工具。
> * `python3-colcon-common-extensions`：ROS 2 專案編譯工具（`colcon build` 必需）。
> * `python3-rosdep`：相依套件安裝與管理工具。
> 
> #### 2. 機器人底盤與 Python 通訊模組
> * `python3-serial`：底盤序列埠通訊（馬達驅動板 CH340 通訊必備）。
> * `python3-matplotlib`：底盤控制節點繪圖與數據分析模組。
> * `python3-tornado`：網頁遙控與實時地圖伺服器（Web Teleop Server）。
> * `python3-requests`、`python3-tqdm`：Python 網路與進度條輔助庫。
> 
> #### 3. 相機、圖像與傳輸套件
> * `ros-jazzy-librealsense2`：Intel RealSense SDK 2.0 核心庫（`realsense2_camera` 編譯相依套件）。
> * `ros-jazzy-realsense2-camera` 與 `ros-jazzy-realsense2-camera-msgs`：RealSense 相機驅動與自訂消息。
> * `ros-jazzy-cv-bridge`：ROS 圖像格式與 OpenCV 的轉換接口。
> * `ros-jazzy-v4l2-camera` 與 `v4l-utils`：標準 UVC USB 相機驅動與調試工具。
> * `ros-jazzy-theora-image-transport`、`ros-jazzy-compressed-image-transport`、`ros-jazzy-image-transport-plugins`：網頁遙控圖像壓縮與傳輸插件。
> 
> #### 4. 導航與 SLAM 建圖套件
> * `ros-jazzy-navigation2` 與 `ros-jazzy-nav2-bringup`：Navigation 2 導航框架與啟動套件。
> * `ros-jazzy-nav2-common` 與 `ros-jazzy-nav2-simple-commander`：Nav2 常用工具與 API。
> * `ros-jazzy-slam-toolbox`：SLAM 建圖工具（`wheeltec_slam_toolbox` 的核心依賴）。
> 
> #### 5. 機器人描述、坐標變換與仿真
> * `ros-jazzy-xacro`：機器人 URDF/Xacro 模型描述解析器。
> * `ros-jazzy-tf-transformations`：Python 版三維坐標變換與姿態運算套件。
> * `ros-jazzy-ros-gz`：Gazebo / Ignition 模擬器整合接口。
> 
> #### 6. NVIDIA Isaac ROS 加速套件 (可選)
> * `ros-jazzy-isaac-ros-common` 與 `ros-jazzy-isaac-ros-examples`：Isaac ROS 核心基礎與範例。
> * `ros-jazzy-isaac-ros-apriltag` 與 `ros-jazzy-isaac-ros-apriltag-interfaces`：GPU 加速的 AprilTag 偵測套件。
> #### 7. Gazebo 地圖模擬插件
> * `ros-jazzy-ros-gz`
> * `ros-jazzy-ros-gz-sim-demos ros-jazzy-gz-ros2-control`
> 
> ---
> 
> **💡 手動一鍵安裝指令（在 Host 端執行以寫入運作中的容器）：**
> ```bash
> docker exec -it isaac_ros_dev_container bash -lc '
> apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y \
>   build-essential \
>   python3-colcon-common-extensions \
>   python3-rosdep \
>   python3-serial \
>   python3-matplotlib \
>   python3-tornado \
>   python3-requests \
>   python3-tqdm \
>   ros-jazzy-librealsense2 \
>   ros-jazzy-realsense2-camera \
>   ros-jazzy-realsense2-camera-msgs \
>   ros-jazzy-cv-bridge \
>   ros-jazzy-v4l2-camera \
>   v4l-utils \
>   ros-jazzy-theora-image-transport \
>   ros-jazzy-compressed-image-transport \
>   ros-jazzy-image-transport-plugins \
>   ros-jazzy-navigation2 \
>   ros-jazzy-nav2-bringup \
>   ros-jazzy-nav2-common \
>   ros-jazzy-nav2-simple-commander \
>   ros-jazzy-slam-toolbox \
>   ros-jazzy-xacro \
>   ros-jazzy-tf-transformations \
>   ros-jazzy-rviz2 \
>   ros-jazzy-ros-gz \
>   ros-jazzy-ros-gz-sim-demos \
>   ros-jazzy-gz-ros2-control\
> '
> ```

---

## 📋 1. 前置需求與套件庫安裝

在 Host 端執行以新增 NVIDIA Isaac ROS 套件庫並安裝 CLI 管理工具：

```bash
sudo apt update
sudo apt install -y locales curl gnupg software-properties-common
sudo locale-gen en_US en_US.UTF-8
sudo update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8
export LANG=en_US.UTF-8

sudo add-apt-repository universe -y

# 下載並寫入 GPG Key
k="/usr/share/keyrings/nvidia-isaac-ros.gpg"
curl -fsSL https://isaac.download.nvidia.com/isaac-ros/repos.key | sudo gpg --dearmor | sudo tee "$k" > /dev/null

# 新增軟體源
f="/etc/apt/sources.list.d/nvidia-isaac-ros.list"
sudo touch "$f"
s="deb [signed-by=$k] https://isaac.download.nvidia.com/isaac-ros/release-4.4 noble-jetpack main"
grep -qxF "$s" "$f" || echo "$s" | sudo tee -a "$f"

sudo apt update
sudo apt install -y isaac-ros-cli
```

---

## 🛠️ 2. 初始化與工作空間準備

```bash
# 1. 建立 ROS 2 工作空間
mkdir -p ~/workspaces/isaac_ros-dev/src
export ISAAC_ROS_WS="$HOME/workspaces/isaac_ros-dev"

# 2. 初始化 Isaac ROS CLI
sudo isaac-ros init docker --yes
```

---

## 🚀 3. 一鍵部署與啟動容器

您可以使用我們為 Jetson Thor 最佳化的安裝腳本：

```bash
cd /home/ubuntu/setup_data/isaac-ros-jetson-thor-jazzy-install
chmod +x install.sh
./install.sh
```

### `install.sh` 主要執行的步驟：
1. 驗證 Docker 及 NVIDIA Container Runtime。
2. 下載最新的 Isaac ROS Docker 鏡像。
3. 建立並以背景模式啟動 `isaac_ros_dev_container` 容器。
4. 在容器中自動安裝基礎與專案開發所需之 ROS 2 套件：
   - `ros-jazzy-isaac-ros-common` 與 `ros-jazzy-isaac-ros-examples`
   - `ros-jazzy-v4l2-camera`
   - `ros-jazzy-librealsense2` *(相機編譯相依套件)*
   - `ros-jazzy-nav2-bringup` 與 `ros-jazzy-navigation2` *(導航編譯相依套件)*
   - `python3-matplotlib` *(底盤控制節點繪圖相依套件)*
   - `python3-serial` *(底盤序列埠通訊相依套件)*
   - `ros-jazzy-rviz2` *(RViz2 視覺化分析工具)*

---

## 📦 4. 安裝與驗證進階功能套件 (可選)

若您需要進行 AprilTag 偵測與加速模組 (NITROS)，請於容器啟動後在 Host 端執行：

```bash
# 安裝 AprilTag 與其加速接口
docker exec isaac_ros_dev_container bash -lc 'apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y ros-jazzy-isaac-ros-apriltag ros-jazzy-isaac-ros-apriltag-interfaces'
```

### 驗證套件安裝狀態
```bash
docker exec isaac_ros_dev_container bash -lc 'source /opt/ros/jazzy/setup.bash && ros2 pkg prefix isaac_ros_apriltag'
```

---

## ⏹️ 5. 容器管理常用指令

### 停止與移除容器
```bash
docker rm -f isaac_ros_dev_container
```

### 重啟容器
```bash
docker restart isaac_ros_dev_container
```

### 檢查容器狀態與日誌
```bash
docker ps -a --filter name=isaac_ros_dev_container
docker logs isaac_ros_dev_container
```
