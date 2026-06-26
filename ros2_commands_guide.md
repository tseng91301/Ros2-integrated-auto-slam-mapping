# 💻 ROS 2 常用指令與環境準備指南

本指南介紹如何在 Isaac ROS Docker 容器內部進行專案編譯（colcon build）、手動運行單一節點（底盤、雷達、鍵盤遙控）、啟動 GUI 視覺化工具（rviz2）以及 ROS 2 常用偵錯指令。

---

## 🗺️ 相關文件連結
- **主入口指南**：[Readme.md](file:///home/ubuntu/workspaces/isaac_ros-dev/Readme.md)
- **一鍵啟動 (Tmux 腳本)**：[launcher_guide.md](file:///home/ubuntu/workspaces/isaac_ros-dev/launcher_guide.md) （推薦使用，免去手動開啟多個視窗的繁瑣步驟）
- **裝置掛載說明**：[docker_device_connection.md](file:///home/ubuntu/workspaces/isaac_ros-dev/docker_device_connection.md)

---

## 1. 進入與準備 Docker 容器環境

由於 ROS 2 是分散式架構，當您手動偵錯或分開執行各個節點時，需要開啟多個 Host 終端機視窗，並且每個視窗都必須進入 Docker 容器內部。

### 步驟 1：在 Host 本機端進入容器
```bash
docker exec -it isaac_ros_dev_container /bin/bash
```

### 步驟 2：在容器內部載入 ROS 2 與工作空間環境
進入容器後，**必須**先載入 ROS 2 系統變數以及本專案編譯後的環境設定：
```bash
# 1. 載入 ROS 2 Jazzy 系統環境變數
source /opt/ros/jazzy/setup.bash

# 2. 切換至工作空間目錄
cd /workspaces/isaac_ros-dev

# 3. 載入工作空間的軟體包環境 (需在編譯過後才可載入)
source install/setup.bash
```

---

## 2. 編譯工作空間 (colcon build)

在容器內的 `/workspaces/isaac_ros-dev` 目錄下進行編譯：

```bash
# 1. 符號連結編譯 (推薦：修改 Python 程式碼或 Launch 設定時，無須重新編譯即可生效)
colcon build --symlink-install

# 2. 僅編譯特定軟體包 (大幅縮短編譯時間)
colcon build --symlink-install --packages-select base_control_ros2

# 3. 清理快取並重新完整編譯 (編譯異常或目錄混亂時使用)
rm -rf build/ install/ log/
colcon build --symlink-install
```

---

## 3. 手動運行機器人與感測器節點

請在不同的終端機視窗（皆已進入容器並載入環境）分別執行：

### A. 啟動馬達底盤通訊 (Chassis Node)
```bash
export BASE_TYPE=NanoRobot
ros2 launch base_control_ros2 00_base_control.launch.py
```
*此節點會讀取 `/dev/playrobot_base` 序列埠，將 `/cmd_vel` 速度指令發送至底盤馬達，並發布 `/odom` 里程計。*

### B. 啟動雷達驅動 (Lidar Node)
```bash
ros2 launch sllidar_ros2 sllidar_a2m12_launch.py serial_port:=/dev/sllidar_a2m12
```
*此節點會驅動 RPLIDAR A2M12，並發布 `/scan` 點雲測距資料。*

### C. 終端機鍵盤遙控 (Keyboard Control)
```bash
ros2 run wheeltec_robot_keyboard wheeltec_keyboard
```
- **控制按鍵**：`i` (前進)、`,` (後退)、`j` (左旋自轉)、`l` (右旋自轉)、`k` (停止)。
- **速度調整**：`q`/`z` 增加/減少最大速度 10%。

---

## 4. 啟動視覺化工具 (rviz2) 與 GUI 轉送

要在 Docker 容器中執行 RViz2 等圖形化工具，必須向 Host 端的 X11 顯示服務進行分享。

1. **Host 本機端（尚未進入 Docker）** 的終端機執行一次：
   ```bash
   xhost +local:docker
   ```
2. **Docker 容器內部**的終端機設定顯示埠號（通常為 `:0`、`:1` 或 `:10.0`）：
   ```bash
   export DISPLAY=:0   # 請根據實際情況調整 (例如 :1)
   ```
3. **啟動 RViz2**：
   ```bash
   # 啟動並載入本專案預設的 SLAM 視覺化配置文件
   rviz2 -d /workspaces/isaac_ros-dev/wheeltec_slam_toolbox.rviz
   ```

---

## 📊 5. ROS 2 常用指令速查表 (Cheat Sheet)

### 節點與通訊診斷
- **列出活躍中的節點**：`ros2 node list`
- **查看節點詳細資訊**：`ros2 node info <node_name>`
- **列出所有活躍的主題 (Topics)**：`ros2 topic list -t`
- **即時印出主題數據**：`ros2 topic echo <topic_name>`
- **查看主題發布頻率 (Hz)**：`ros2 topic hz <topic_name>`
- **查看主題傳輸頻寬**：`ros2 topic bw <topic_name>`
- **手動發送速度指令**：
  ```bash
  ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.1, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.0}}"
  ```

### 參數與服務管理
- **列出所有節點參數**：`ros2 param list`
- **讀取特定參數值**：`ros2 param get <node_name> <param_name>`
- **寫入/變更動態參數**：`ros2 param set <node_name> <param_name> <value>`
- **列出所有活躍的服務 (Services)**：`ros2 service list`
- **呼叫服務**：
  ```bash
  # 重置 SLAM Toolbox 建圖
  ros2 service call /slam_toolbox/reset std_srvs/srv/Empty {}
  ```
