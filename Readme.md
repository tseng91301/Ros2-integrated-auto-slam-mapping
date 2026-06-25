# 🚀 Jetson Thor 機器人環境部署與開發指南 (General Readme)

歡迎使用本專案！本工作空間整合了 **Advantech AFE-A702 (Jetson Thor)** 硬體驅動、**Docker (NVIDIA Isaac ROS)** 容器環境，以及 **ROS 2** 機器人控制軟體包（包含馬達底盤驅動與 RPLIDAR A2M12 雷達）。

本文件為專案的 **主入口說明文件**。為使結構清晰，具體之技術細節與指令已被拆分至獨立的子指南中。

---

## 🗺️ 專案指南目錄 (Table of Contents)

請根據您目前的開發進度，點擊以下連結閱讀專屬的設定與操作指南：

| 順序 | 指南名稱 | 內容說明 | 連結檔案路徑 |
| :---: | :--- | :--- | :--- |
| **1** | **🔌 硬體命名與 Udev 規則** | 設定雷達CP2102與底盤CH340之硬體串行埠固定名稱 | [udev-rules.md](file:///home/ubuntu/setup_data/udev-rules.md) |
| **2** | **📦 Docker 裝置掛載與串接** | 如何將雷達與底盤硬體節點動態/靜態地掛載進運行中的 Docker 容器 | [docker_device_connection.md](file:///home/ubuntu/workspaces/isaac_ros-dev/docker_device_connection.md) |
| **3** | **🐳 Isaac ROS 容器啟動與安裝** | 初始化 Isaac ROS CLI、拉取容器鏡像、啟動容器與安裝 NITROS / AprilTag 套件 | [isaac_ros_setup.md](file:///home/ubuntu/workspaces/isaac_ros-dev/isaac_ros_setup.md) |
| **4** | **🚀 ROS 2 常用指令與開發工具** | 工作空間編譯（colcon build）、運行節點（run/launch）、X11 圖形轉送（rviz2）與指令速查 | [ros2_commands_guide.md](file:///home/ubuntu/workspaces/isaac_ros-dev/ros2_commands_guide.md) |
| **5** | **📡 網頁遙控與實時建圖指南** | 手機/電腦瀏覽器實時搖桿遙控、地圖顯示與地圖下載操作說明 | [web_teleop_guide.md](file:///home/ubuntu/workspaces/isaac_ros-dev/web_teleop_guide.md) |

---

## 📋 Host 本機端基礎驅動與環境安裝

> [!IMPORTANT]
> 以下步驟皆在 **Host 端的本機終端機** 執行，非 Docker 容器內部。本機系統必須使用 Ubuntu 24.04 (Noble) + Jetpack。

### 1. 📡 無線網卡驅動安裝
如果您的系統尚未能連接 Wi-Fi 或藍芽，請使用原始碼編譯驅動程式：
```bash
cd /home/ubuntu/setup_data/drivers/WiFi_Bluetooth_Drivers
# 執行網卡安裝腳本
chmod +x setup.sh
./setup.sh
```

### 2. 🔌 CH341 序列埠驅動安裝 (馬達底盤通訊晶片)
馬達控制主板使用 CH340/341 晶片，核心編譯安裝步驟如下：
```bash
cd /home/ubuntu/setup_data/drivers/ch341ser_linux
chmod +x setup.sh
# 執行編譯與載入模組腳本
./setup.sh
```
*載入成功後，插入底盤 USB，Host 端應可看見 `/dev/ttyCH341USB0` 裝置節點。*

### 3. 🖥️ 遠端桌面工具 (NoMachine) 安裝
```bash
# 下載 NoMachine ARM64 官方安裝包
wget https://www.nomachine.com/free/arm/v8/deb -O nomachine-arm64.deb
# 執行安裝
sudo dpkg -i nomachine-arm64.deb
```

### 4. 📷 ZED X 相機 GMSL 驅動與 SDK 安裝
```bash
sudo apt update
sudo apt install -y libqt5core5a zstd
# 接著依據 ZED SDK 官方指示安裝對應的 Tegra L4T 驅動
```

### 5. 🐳 Docker 引擎與 NVIDIA Toolkit 設定
```bash
# 安裝基礎 Docker 引擎
curl -fsSL https://get.docker.com -o get-docker.sh
sudo bash get-docker.sh && rm get-docker.sh
sudo usermod -aG docker $USER

# 註冊 NVIDIA Runtime 並重啟 Docker 服務
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

---

## 📦 ROS 2 Docker 容器內必要 Apt 套件清單

本專案的所有功能包（包含底盤控制、雷達、SLAM、網頁遙控、相機驅動等）在 Docker 容器內編譯與執行時，依賴以下核心套件。若您使用現有或自建的 Docker 容器，請務必手動或透過指令安裝這些相依庫：

- **核心開發工具**：`build-essential`, `python3-colcon-common-extensions`, `python3-rosdep`
- **底盤序列通訊與 Python**：`python3-serial`, `python3-matplotlib`, `python3-tornado`
- **相機與圖像傳輸**：`ros-jazzy-librealsense2`, `ros-jazzy-realsense2-camera`, `ros-jazzy-v4l2-camera`, `ros-jazzy-cv-bridge`, `ros-jazzy-theora-image-transport`
- **導航與 SLAM**：`ros-jazzy-navigation2`, `ros-jazzy-nav2-bringup`, `ros-jazzy-slam-toolbox`
- **加速與偵測 (NVIDIA Isaac ROS)**：`ros-jazzy-isaac-ros-apriltag`, `ros-jazzy-isaac-ros-common`

詳細的套件說明與一鍵手動安裝指令，請參閱：[Docker 容器啟動與相依套件安裝指南 (isaac_ros_setup.md)](file:///home/ubuntu/workspaces/isaac_ros-dev/isaac_ros_setup.md)。

---

## 📂 專案目錄結構說明

```text
/home/ubuntu/
├── setup_data/                      # Host 本機設定與驅動包
│   ├── Readme.md                    # 本主入口說明文件
│   ├── udev-rules.md                # Udev 命名設定指南
│   ├── drivers/                     # 網卡與序列埠驅動原始碼
│   └── isaac-ros-jetson-thor-jazzy-install/  # Docker 初始化啟動腳本與驗證包
│
└── workspaces/
    └── isaac_ros-dev/               # 主要 ROS 2 工作空間 (已掛載至 Docker 內)
        ├── src/                     # ROS 2 功能包原始碼
        ├── attach_devices.sh        # ⚡ 動態裝置掛載輔助腳本
        ├── docker_device_connection.md # 裝置掛載指南
        ├── isaac_ros_setup.md       # 容器啟動指南
        └── ros2_commands_guide.md   # 指令與編譯指南
```

如有任何硬體驅動或軟體編譯上的疑慮，請優先點擊閱讀對應的 `.md` 文件。