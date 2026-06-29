# 🚀 Jetson Thor 機器人 Host 本機環境部署與 Docker 容器安裝指南

本文件說明當您剛拿到 **Advantech AFE-A702 (Jetson Thor)** 機器人時，如何在本機（Host 系統）進行基礎硬體驅動安裝、遠端工具設定、Docker 與 NVIDIA Container Toolkit 部署、以及 NVIDIA Isaac ROS 容器的初始化與套件安裝。

---

## 🗺️ 專案安裝文件導覽
- **Udev 規則設定**：[udev-rules.md](file:///home/ubuntu/setup_data/udev-rules.md) （用以綁定雷達與底盤的固定 USB 序列埠路徑）
- **裝置掛載說明**：[docker_device_connection.md](docker_device_connection.md) （如何將本機裝置掛載進運行中的 Docker 容器）
- **工作空間操作主入口**：[workspaces/isaac_ros-dev/Readme.md](Readme.md) （進入 Docker 容器後的開發與啟動指南）

---

## 📋 Host 本機端基礎驅動與環境安裝

> [!IMPORTANT]
> 以下步驟皆在 **Host 本機的終端機**（非 Docker 容器內）執行。
> 本機系統預設應為 **Ubuntu 24.04 LTS (Noble) + JetPack 6.x**。

### 1. 📡 無線網卡驅動安裝
如果機器人尚未能連接 Wi-Fi 或藍牙，請使用本機驅動原始碼進行編譯安裝：
```bash
cd /home/ubuntu/setup_data/drivers/WiFi_Bluetooth_Drivers
# 執行網卡安裝腳本
chmod +x setup.sh
sudo ./setup.sh
```

### 2. 🔌 CH341 序列埠驅動安裝 (馬達底盤通訊晶片)
機器人馬達控制主板使用 CH340/CH341 序列埠晶片，若核心未內建或需更新，請依序編譯載入模組：
```bash
cd /home/ubuntu/setup_data/drivers/ch341ser_linux
chmod +x setup.sh
# 執行編譯與核心載入腳本
sudo ./setup.sh
```
*載入成功後，插入底盤 USB，本機端應可看見 `/dev/ttyCH341USB0` 裝置節點。*

### 3. 🖥️ 遠端桌面工具 (NoMachine) 安裝
為方便進行圖形化開發（如檢視 RViz2），建議安裝 NoMachine：
```bash
cd /home/ubuntu/setup_data
# 安裝本地 NoMachine ARM64 安裝包
sudo dpkg -i nomachine-arm64.deb
```
*(若無安裝包，可至官方下載：`wget https://www.nomachine.com/free/arm/v8/deb -O nomachine-arm64.deb`)*

### 4. 📷 ZED X 相機 GMSL 驅動與 SDK 安裝 (若配備 ZED 相機)
```bash
sudo apt update
sudo apt install -y libqt5core5a zstd
# 依據 Stereolabs ZED SDK 官方指引，執行對應 L4T 版本之安裝檔

# 給當前使用者獲取影像的完整權限
sudo usermod -a -G video $USER
```

### 5. 🐳 Docker 引擎與 NVIDIA Toolkit 設定
```bash
# 1. 安裝 Docker 引擎
curl -fsSL https://get.docker.com -o get-docker.sh
sudo bash get-docker.sh && rm get-docker.sh
sudo usermod -aG docker $USER

# 2. 註冊 NVIDIA Runtime 並重啟 Docker 服務
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

---

## 🐳 NVIDIA Isaac ROS 容器初始化與啟動

### 1. 新增 NVIDIA 套件庫並安裝 Isaac ROS CLI 工具
在 Host 端終端機執行：
```bash
sudo apt update
sudo apt install -y locales curl gnupg software-properties-common
sudo locale-gen en_US en_US.UTF-8
sudo update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8
export LANG=en_US.UTF-8

sudo add-apt-repository universe -y

# 下載並寫入 GPG 金鑰
k="/usr/share/keyrings/nvidia-isaac-ros.gpg"
curl -fsSL https://isaac.download.nvidia.com/isaac-ros/repos.key | sudo gpg --dearmor | sudo tee "$k" > /dev/null

# 新增 NVIDIA Isaac ROS 4.4 軟體源
f="/etc/apt/sources.list.d/nvidia-isaac-ros.list"
sudo touch "$f"
s="deb [signed-by=$k] https://isaac.download.nvidia.com/isaac-ros/release-4.4 noble-jetpack main"
grep -qxF "$s" "$f" || echo "$s" | sudo tee -a "$f"

sudo apt update
sudo apt install -y isaac-ros-cli
```

### 2. 初始化 Isaac ROS CLI
```bash
# 建立 ROS 2 開發工作空間
mkdir -p ~/workspaces/isaac_ros-dev/src
export ISAAC_ROS_WS="$HOME/workspaces/isaac_ros-dev"

# 初始化 Isaac ROS CLI 設定 (建立 docker-compose 設定檔)
sudo isaac-ros init docker --yes
```

### 3. 一鍵啟動容器並載入環境
本專案已在 `setup_data` 中提供了為 Jetson Thor 最佳化的啟動安裝腳本：
```bash
cd /home/ubuntu/setup_data/isaac-ros-jetson-thor-jazzy-install
chmod +x install.sh
./install.sh
```
*該腳本會自動檢驗 Docker 環境、拉取 NVIDIA Isaac ROS Jazzy 映像檔、建立並背景啟動 `isaac_ros_dev_container`，同時自動在容器中配置基本套件。*

---

## 📦 ROS 2 Docker 容器內必要/會安裝之套件清單

本專案的所有功能包（底盤控制、Lidar 雷達、SLAM 建圖、網頁遙控、自主探索、RViz2 視覺化等）在編譯與執行時，依賴以下套件。

以下套件**已整合至一鍵部署腳本中**，當您執行 `./install.sh` 時會自動在容器內裝妥。若您使用自建容器，可手動在容器內執行安裝：

### ⚙️ 容器手動一鍵安裝指令
若有套件遺失，可在 Host 端執行以下指令，直接將套件寫入正運行中的容器：
```bash
docker exec -it isaac_ros_dev_container bash -lc '
apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y \
  build-essential python3-colcon-common-extensions python3-rosdep python3-serial \
  python3-matplotlib python3-tornado python3-requests python3-tqdm \
  ros-jazzy-librealsense2 ros-jazzy-realsense2-camera ros-jazzy-realsense2-camera-msgs \
  ros-jazzy-cv-bridge ros-jazzy-v4l2-camera v4l-utils ros-jazzy-theora-image-transport \
  ros-jazzy-compressed-image-transport ros-jazzy-image-transport-plugins \
  ros-jazzy-navigation2 ros-jazzy-nav2-bringup ros-jazzy-nav2-common \
  ros-jazzy-nav2-simple-commander ros-jazzy-slam-toolbox ros-jazzy-xacro \
  ros-jazzy-tf-transformations ros-jazzy-rviz2 ros-jazzy-ros-gz \
  ros-jazzy-ros-gz-sim-demos ros-jazzy-gz-ros2-control
'

# 安裝 ZED 在 ROS2 上面的相關依賴庫
docker exec isaac_ros_dev_container apt-get install -y libusb-1.0-0-dev
docker exec isaac_ros_dev_container apt-get install -y libturbojpeg libturbojpeg0-dev
```
*安裝完成後，若要將此環境保存，避免 Docker 容器重建時被刪除，請參閱 [docker_device_connection.md](docker_device_connection.md) 內的 Docker Commit 說明進行固化。*