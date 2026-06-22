# 🐳 Isaac ROS Docker 環境安裝與啟動指南

本指南說明如何在 Jetson Thor (Ubuntu 24.04 + Jetpack) 上安裝、初始化並管理 Isaac ROS Docker 開發環境。

> [!IMPORTANT]
> **專案開發必備相依套件**：
> 為了成功編譯和執行您的底盤（`wheeltec_nav2` 等）與相機（`realsense2_camera`），容器內部必須安裝以下核心套件：
> * `ros-jazzy-librealsense2` (Intel RealSense SDK 2.0 支援)
> * `ros-jazzy-nav2-bringup` (Navigation 2 啟動包)
> * `ros-jazzy-navigation2` (Navigation 2 核心包)
> * `python3-matplotlib` (底盤控制 Python 模組)
> * `python3-serial` (底盤序列埠通訊模組)
> * `ros-jazzy-rviz2` (RViz2 視覺化工具)
> 
> 這些套件**已整合至 `install.sh` 啟動指令中**，在一鍵部署時會自動完成安裝。若您使用現有容器，亦可手動進入容器安裝（詳見下文）。

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
