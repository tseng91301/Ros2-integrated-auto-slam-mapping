# 🚀 Wheeltec ROS 2 常用指令集合 (Command Cheat Sheet)

本文件整理了此工作空間常用功能所需的指令。所有指令均以 **「剛進入此專案，尚未開啟任何終端機與節點」** 的狀態為前提設計。

> [!IMPORTANT]
> 在開啟任何**新的終端機視窗/分頁**後，請務必先執行以下環境變數載入指令：
> ```bash
> cd /home/ubuntu/steven_verify_ws
> source install/setup.bash
> ```

---

## 📋 核心功能指令集

### 1. 🏎️ 底盤開啟 (Chassis Control)
啟動底盤的通訊與編碼器回傳，讓機器人可以接收 `/cmd_vel` 移動指令：
```bash
ros2 launch turn_on_wheeltec_robot turn_on_wheeltec_robot.launch.py
# For this bot
ros2 launch base_control_ros2 00_base_control.launch.py
```

### 2. ⌨️ 鍵盤控制機器人移動 (Keyboard Control)
啟動鍵盤控制節點，利用鍵盤遙控車輛：
```bash
ros2 run wheeltec_robot_keyboard wheeltec_keyboard
```
*   **控制按鍵**：`i` (前進)、`,` (後退)、`j` (左轉)、`l` (右轉)、`k` (停止)
*   **調整速度**：`q`/`z` 增加/減少最大速度 10%

### 3. 📡 打開 Lidar 節點 (Lidar Driver)
單獨啟動雷射雷達，使雷達轉動並發布 `/scan` 點雲資料 (目前配置為 RPLIDAR A2M12)：
```bash
ros2 launch sllidar_ros2 sllidar_a2m12_launch.py
```

### 4. 🗺️ 建立地圖 (SLAM Toolbox Only)
單獨啟動 SLAM Toolbox 異步建圖節點 (適合自行播放 rosbag 點雲或單獨測試建圖演算法時使用)：
```bash
ros2 launch wheeltec_slam_toolbox playrobot_online_async_launch.py
```

---

## 🧭 遙控建圖完整流程 (Manual SLAM Mapping)

這是您要進行「手動控制車輛並同時建立地圖」時，最標準且最常使用的指令流程。請依序開啟不同的終端機視窗並載入環境變數：

### 步驟 1：啟動主控與建圖程式 (包含底盤 + 雷達 + SLAM + RViz2)
在**第一個終端機**執行以下指令。此指令會整合啟動底盤、雷達、SLAM，並自動打開 RViz2 呈現地圖與掃描紅線：
```bash
ros2 launch wheeltec_slam_toolbox online_async_launch.py
```

### 步驟 2：啟動鍵盤遙控節點
在**第二個終端機**執行以下指令，並保持在此視窗中，使用鍵盤操作車輛在環境中移動以掃描地圖：
```bash
ros2 run wheeltec_robot_keyboard wheeltec_keyboard
```

### 步驟 3：儲存地圖 (建圖完成後)
當您滿意 RViz2 畫面上建立出來的地圖後，開啟**第三個終端機**執行儲存指令：
```bash
ros2 run nav2_map_server map_saver_cli -f ~/map
```
*   地圖將儲存在您的家目錄，包含：`~/map.pgm` (地圖圖檔) 與 `~/map.yaml` (地圖資訊定義檔)。

---

## 🧩 分步啟動流程 (Step-by-Step / One-by-One Startup)

如果您不希望使用整合式的啟動檔，而是想一個一個節點獨立啟動與除錯，請依序在**不同的終端機分頁**中執行以下指令（皆須先執行環境變數載入）：

### 1. 啟動底盤控制與 EKF (Chassis & Odom)
```bash
export BASE_TYPE=NanoRobot
source /home/ubuntu/steven_verify_ws/install/setup.bash
ros2 launch base_control_ros2 00_base_control.launch.py
```

### 2. 啟動雷達節點 (Lidar)
```bash
source /home/ubuntu/steven_verify_ws/install/setup.bash
ros2 launch sllidar_ros2 sllidar_a2m12_launch.py
```

### 3. 啟動 SLAM 建圖演算法節點 (SLAM Toolbox)
```bash
source /home/ubuntu/steven_verify_ws/install/setup.bash
ros2 launch wheeltec_slam_toolbox playrobot_online_async_launch.py
```

### 4. 啟動視覺化介面 (RViz2)
```bash
source /home/ubuntu/steven_verify_ws/install/setup.bash
ros2 run rviz2 rviz2 -d /home/ubuntu/steven_verify_ws/wheeltec_slam_toolbox.rviz
# or
rviz2
```

### 5. 啟動鍵盤遙控節點 (Keyboard Control)
```bash
source /home/ubuntu/steven_verify_ws/install/setup.bash
ros2 run wheeltec_robot_keyboard wheeltec_keyboard
```

### 6. 儲存地圖 (Save Map)
```bash
source /home/ubuntu/steven_verify_ws/install/setup.bash
ros2 run nav2_map_server map_saver_cli -f ~/map
```

---

## 📷 ZED 相機驅動指令 (ZED Camera)

啟動 ZED 深度相機節點。請依據您的相機型號 (如 `zed`, `zed2`, `zed2i`, `zedx` 等) 調整 `camera_model` 參數：
```bash
ros2 launch zed_wrapper zed_camera.launch.py camera_model:=zedx
```
*   *(常用型號參數值包括：`zed`, `zedm`, `zed2`, `zed2i`, `zedx`, `zedxm` 等)*

---

## ⚙️ 系統編譯與硬體設定

### 🔨 重新編譯整個工作空間
若修改了任何程式碼或啟動檔，請先清除快取並重新編譯：
```bash
cd /home/ubuntu/steven_verify_ws
rm -rf build/ install/ log/
colcon build --symlink-install
```

### 🔌 硬體連接埠別名設定 (Udev Rules)
若重新安裝系統或插拔 USB 連接埠後無法讀取設備，請重新應用 Udev 規則：
```bash
# 寫入設定規則檔
echo -e 'SUBSYSTEM=="tty", ATTRS{idVendor}=="10c4", ATTRS{idProduct}=="ea60", ATTRS{serial}=="4157d26cd879ca418ca0e378084f3ed7", SYMLINK+="sllidar_a2m12"\nSUBSYSTEM=="tty", ATTRS{idVendor}=="1a86", ATTRS{idProduct}=="7523", SYMLINK+="playrobot_base"' | sudo tee /etc/udev/rules.d/99-usb-serial.rules

# 重新載入規則
sudo udevadm control --reload-rules && sudo udevadm trigger
```