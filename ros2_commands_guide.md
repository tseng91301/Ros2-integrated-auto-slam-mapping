# 🚀 ROS 2 常用指令與開發工具操作指南 (Docker 環境)

本指南介紹如何在 Isaac ROS Docker 容器內部進行編譯（colcon build）、運行節點（ros2 run/launch）、啟動 GUI 工具（rviz2）以及常見的故障排除。

---

## 💻 1. 進入與準備環境

由於 ROS 2 是分佈式系統，您在執行不同功能（例如：底盤控制、雷達、建圖、遙控）時，通常需要**同時開啟多個終端機視窗**。

每當您在 Host 端開啟一個新終端機，都必須執行以下指令進入容器：
```bash
docker exec -it isaac_ros_dev_container /bin/bash
```

進入容器後，**務必**先載入 ROS 2 與工作空間的環境變數：
```bash
# 1. 載入系統底層 ROS 2 Jazzy 環境
source /opt/ros/jazzy/setup.bash

# 2. 進入工作空間目錄
cd /workspaces/isaac_ros-dev

# 3. 載入工作空間的軟體包環境 (需在編譯過後才可載入)
source install/setup.bash
```

---

## 🔨 2. 編譯工作空間 (colcon build)

在容器內的 `/workspaces/isaac_ros-dev` 目錄下執行編譯：

```bash
# 建立符號連結編譯 (推薦，修改 python 檔或 launch 檔無須重新編譯)
colcon build --symlink-install

# 僅編譯特定軟體包 (加速開發)
colcon build --symlink-install --packages-select base_control_ros2
```

---

## 🏎️ 3. 運行機器人與感測器節點

請在不同的終端機視窗（皆已進入容器並載入環境）分別執行：

### 1. 啟動馬達底盤通訊 (Chassis Node)
```bash
export BASE_TYPE=NanoRobot
ros2 launch base_control_ros2 00_base_control.launch.py
```
*此節點會讀取 `/dev/playrobot_base` 並將速度指令下發至底盤。*

### 2. 啟動雷達驅動 (Lidar Node)
```bash
ros2 launch sllidar_ros2 sllidar_a2m12_launch.py serial_port:=/dev/sllidar_a2m12
```
*此節點會啟動 RPLIDAR A2M12 並發布 `/scan` 點雲資料。*

### 3. 鍵盤遙控車輛 (Keyboard Control)
```bash
ros2 run wheeltec_robot_keyboard wheeltec_keyboard
```
* **控制指令：** `i` (前進)、`,` (後退)、`j` (左轉)、`l` (右轉)、`k` (停止)
* **調整速度：** `q`/`z` 增加/減少最大速度 10%

---

## ⚡ 4. 使用 tmux 腳本一鍵啟動 (推薦)

為了避免每次都要開啟多個終端機視窗並重複執行 `docker exec` 與環境變數載入，我們為您設計了 All-in-One 的 [ros2_tmux_launcher.sh](file:///home/ubuntu/workspaces/isaac_ros-dev/ros2_tmux_launcher.sh) 腳本。

該腳本運行在 **Host 端**，會自動清理舊的會話，建立統一的 tmux session 名稱 (`ros2_dev`)，並自動把指令派發進 Docker 容器中執行。

### 🚀 模式一：啟動底盤 + 鍵盤遙控 (預載 teleop 組合)
在 **Host 端** 執行：
```bash
cd /home/ubuntu/workspaces/isaac_ros-dev
./ros2_tmux_launcher.sh teleop
```
*此指令會以左右二分割視窗啟動底盤與鍵盤控制，並自動將游標焦點選在鍵盤控制格，您可直接操作。*

### 🗺️ 模式二：啟動底盤 + 雷達 + 建圖 + 鍵盤 + RViz2 (預載 slam_all 組合)
In **Host 端** 執行：
```bash
cd /home/ubuntu/workspaces/isaac_ros-dev
./ros2_tmux_launcher.sh slam_all
```
*此指令會建立網格四分割視窗運行底盤、雷達、SLAM Toolbox 與鍵盤控制；同時會自動新建一個分頁（Window）執行 RViz2 畫面的繪製。*

### 🛠️ 模式三：自訂模組組合
您可以手動指定只開啟哪些模組，腳本會自動為您分割對應數量的窗格：
```bash
# 範例一：只啟動底盤與雷達
./ros2_tmux_launcher.sh chassis lidar

# 範例二：啟動底盤、鍵盤與 RViz2
./ros2_tmux_launcher.sh chassis keyboard rviz
```

> [!TIP]
> **Tmux 常用操作快捷鍵**：
> * **切換分頁 (Window)**：按 `Ctrl + B` 放開，然後按數字鍵 `0` 或 `1`。
> * **切換窗格 (Pane)**：按 `Ctrl + B` 放開，然後按方向鍵 `↑` `↓` `←` `→`。
> * **離開 tmux (背景繼續運行)**：按 `Ctrl + B` 放開，然後按 `D`。
> * **重新連回會話**：`tmux attach-session -t ros2_dev`。
> * **關閉整個會話 (停止程式)**：按 `Ctrl + B` 放開，輸入 `:kill-session` 按 Enter，或直接在 Host 端重新執行腳本。

---

## 🖥️ 5. 啟動視覺化工具 (rviz2) 與 GUI 轉送

要在 Docker 容器中執行 RViz2 等圖形化工具，必須向 Host 端的 X11 顯示服務進行分享。

1. **Host 本機端（尚未進入 Docker）** 的終端機執行一次：
   ```bash
   xhost +local:docker
   ```
2. **Docker 容器內部**的終端機設定環境變數：
   ```bash
   export DISPLAY=:0
   ```
3. **啟動 RViz2**：
   ```bash
   # 啟動預設 RViz2
   rviz2

   # 或者是載入此專案的 SLAM 預設配置檔
   rviz2 -d /workspaces/isaac_ros-dev/wheeltec_slam_toolbox.rviz
   ```

---

## 🛠️ 5. 常用編譯問題排除 (Troubleshooting)

### 問題 1：缺少編譯 realsense-ros 所需的 SDK
* **錯誤**：`Intel RealSense SDK 2.0 is missing, please install it...`
* **解法**：在容器中安裝 RealSense 核心開發庫：
  ```bash
  sudo apt-get update && sudo apt-get install -y ros-jazzy-librealsense2
  ```

### 問題 2：找不到依賴的 Python 套件或目錄
* **錯誤**：`error: package directory 'base_control_ros2' does not exist`
* **原因**：快取目錄混亂。
* **解法**：清除快取並重新完整編譯：
  ```bash
  rm -rf build/ install/ log/
  colcon build --symlink-install
  ```

### 問題 3：編譯 wheeltec_nav2 時缺少 nav2_bringup
* **錯誤**：`CMake Error: By not providing "Findnav2_bringup.cmake" ... project has asked CMake to find a package configuration file provided by "nav2_bringup" ... but CMake did not find one.`
* **原因**：容器內缺少 Navigation 2 與導航啟動所需的相依套件。
* **解法**：在容器中安裝 Navigation 2 及其啟動套件：
  ```bash
  sudo apt-get update && sudo apt-get install -y ros-jazzy-nav2-bringup ros-jazzy-navigation2
  ```

---

## 📊 6. ROS 2 常用指令速查表 (Cheat Sheet)

### 節點與通訊診斷
* **列出活躍節點**：`ros2 node list`
* **查看節點詳細資訊**：`ros2 node info <node_name>`
* **列出所有主題 (Topics)**：`ros2 topic list -t`
* **即時印出主題內容**：`ros2 topic echo <topic_name>`
* **查看主題發布頻率**：`ros2 topic hz <topic_name>`
* **手動發送單次資料**：`ros2 topic pub --once <topic_name> <msg_type> "<yaml_data>"`
  * *範例*：`ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.1, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.0}}"`

### 參數與服務管理
* **列出節點參數**：`ros2 param list`
* **讀取特定參數**：`ros2 param get <node_name> <param_name>`
* **寫入/設定參數**：`ros2 param set <node_name> <param_name> <value>`
* **呼叫服務 (Service)**：`ros2 service call <service_name> <service_type> "<yaml_data>"`
