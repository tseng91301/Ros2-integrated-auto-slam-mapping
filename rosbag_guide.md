# 🎥 ROS 2 Rosbag 建圖數據記錄與回放操作指南

本指南將為您說明如何使用 `rosbag2` 工具記錄您在進行地圖探索與建圖 (SLAM) 時的所有重要數據，包含需要安裝的套件、架構說明、操作步驟，以及如何回放數據重新建圖。

---

## 🗺️ 相關連結
- **一鍵啟動腳本**：[ros2_tmux_launcher.sh](ros2_tmux_launcher.sh)
- **快捷錄製工具**：[rosbag_record.sh](rosbag_record.sh)

---

## ❓ 常見問答 (FAQ)

### 1. 我需要安裝什麼套件 (Packages) 嗎？
**答案：不需要額外安裝。**
本專案的 Docker 容器環境（基於 ROS 2 Jazzy）已經預先安裝並配置好了 `rosbag2` 及其命令列工具 `ros2 bag`。您可以直接在容器內執行相關指令，或是在 Host 端利用我們寫好的輔助腳本直接進行操作。

### 2. 需要為此做一個新的 ROS 2 Package 或 Node 嗎？
**答案：不需要。**
ROS 2 提供內建的 `ros2 bag` 工具，其功能完全覆蓋了記錄與回放的需求。為了簡化操作，我們已在工作空間中為您建立了兩個整合方案，您無需額外撰寫程式碼或建立 Node：
*   **輔助腳本 `rosbag_record.sh`**：能讓您直接從 Host 端下指令，自動在容器內錄製指定的主題。
*   **Tmux 啟動器模組 `rosbag`**：能在一鍵啟動 SLAM 的同時，自動在新分割的終端窗格中開啟背景錄製。

---

## 🛠️ 如何操作

預設所有錄製好的數據將會以「資料夾」形式，儲存在您的工作空間目錄 **`rosbags/`** 下（對應 Host 本機端與 Docker 容器內的 `/workspaces/isaac_ros-dev/rosbags/`）。這可以確保資料永久保存。

### 核心錄製主題說明
為防止硬碟空間被過大的相機影像檔案撐爆，預設錄製僅包含 SLAM 建圖與路徑規劃最核心的數據：
*   `/scan`：雷達點雲測距資料。
*   `/odom`：模擬模式 (Simulation) 下模擬器發布的里程計數據。
*   `/odom_combined`：實體機器人模式下底盤發布的融合里程計數據。
*   `/tf`：動態座標轉換（例如 map -> odom -> base_footprint 等）。
*   `/tf_static`：靜態座標轉換（雷達相對於車體的安裝位置）。
*   `/cmd_vel`：遙控或自動探索發出的速度控制指令。
*   `/map`：建好的佔有格柵地圖。

---

## 🚀 錄製操作方法

### 方法 A：使用 `rosbag_record.sh` 腳本 (推薦，最靈活)
您可以在 Host 端（容器外）的專案目錄下執行此腳本，它會自動呼叫容器內的 rosbag 進行錄製。

#### 1. 預設錄製 (僅錄製核心 SLAM 主題)：
```bash
cd /home/ubuntu/workspaces/isaac_ros-dev
./rosbag_record.sh
```
*此指令會在 `rosbags/` 目錄下產生一個以時間戳記命名的資料夾，例如 `rosbag_20260629_120000`。*

#### 2. 自訂錄製資料夾名稱：
```bash
./rosbag_record.sh -o my_exploration_bag
```

#### 3. 包含相機影像數據（加錄壓縮影像與深度圖）：
```bash
./rosbag_record.sh -c
# 或自訂名稱：
./rosbag_record.sh -c -o my_camera_bag
```

#### 4. 錄製所有活躍主題：
```bash
./rosbag_record.sh -a
```

> [!TIP]
> 欲**停止錄製**，只需在該終端視窗中按下 **`Ctrl + C`** 即可安全結束並寫入後設資料。

---

### 方法 B：整合至 Tmux 一鍵啟動 (最方便)
如果您希望在啟動建圖的同時自動開始錄製，只需在自訂模組參數中加上 `rosbag`：

```bash
# 範例 1：啟動實體車底盤、雷達、建圖、鍵盤遙控，並同時在背景錄製核心數據
./ros2_tmux_launcher.sh chassis lidar slam keyboard rosbag

# 範例 2：一鍵啟動建圖、RViz2 視覺化，並同時錄製
./ros2_tmux_launcher.sh chassis lidar slam rviz rosbag
```

*執行後，Tmux 會自動建立一個新窗格（Pane）來執行 `ros2 bag record`。當您想結束時，選取該窗格並按下 `Ctrl + C`，隨後即可使用 `Ctrl + B` 然後按 `D` 退出 Tmux 會話。*

---

## 📊 如何檢查與分析錄製檔

錄製完成後，您可以透過以下指令檢查錄製檔的詳細資訊，確認主題與數據數量是否正確。

1. **進入 Docker 容器內部**：
   ```bash
   docker exec -it isaac_ros_dev_container /bin/bash
   source /opt/ros/jazzy/setup.bash
   source /workspaces/isaac_ros-dev/install/setup.bash
   ```
2. **檢查 Bag 資訊**：
   ```bash
   ros2 bag info /workspaces/isaac_ros-dev/rosbags/<您的錄製資料夾名稱>
   ```

**預期輸出範例：**
```text
Files:             rosbag_20260629_120000.db3
Bag size:          12.4 MiB
Storage id:        sqlite3
Duration:          45.123s
Start:             Jun 29 2026 12:00:00.123 (1782782400.123)
End:               Jun 29 2026 12:00:45.246 (1782782445.246)
Messages:          4856
Topic information: Topic: /scan | Type: sensor_msgs/msg/LaserScan | Count: 450 | Serialization Format: cdr
                   Topic: /odom_combined | Type: nav_msgs/msg/Odometry | Count: 900 | Serialization Format: cdr
                   Topic: /tf | Type: tf2_msgs/msg/TFMessage | Count: 2350 | Serialization Format: cdr
                   ...
```

---

## 🔄 數據回放與離線建圖

Rosbag 最強大的功能之一是「**離線回放與重建模擬**」。您可以在不連接實體機器人的情況下，利用錄製好的雷達與里程計數據重新跑一次 SLAM，調校建圖參數。

### 步驟 1：啟動 SLAM 與 RViz2 (使用模擬時間)
為了讓 SLAM Toolbox 能夠同步回放數據的時間，我們必須啟動 SLAM，並告訴它使用模擬時間（`use_sim_time:=true`）。

1. 啟動一個 raw 終端進入容器：
   ```bash
   ./ros2_tmux_launcher.sh terminal
   ```
2. 在容器內啟動 SLAM Toolbox（傳入模擬時間參數）：
   ```bash
   ros2 launch wheeltec_slam_toolbox playrobot_online_async_launch.py use_sim_time:=true
   ```
3. 在 Host 本機端啟動 RViz2 觀察：
   ```bash
   # Host 端
   xhost +local:docker
   docker exec -it isaac_ros_dev_container bash -lc "source /opt/ros/jazzy/setup.bash && source /workspaces/isaac_ros-dev/install/setup.bash && export DISPLAY=:0 && rviz2 -d /workspaces/isaac_ros-dev/wheeltec_slam_toolbox.rviz"
   ```

### 步驟 2：開始播放 Rosbag (同步發布時鐘)
在另一個容器終端機視窗中，播放您的 rosbag，且必須加上 **`--clock`** 參數以發布 `/clock` 主題，讓系統時鐘對齊 bag 檔案：

```bash
ros2 bag play /workspaces/isaac_ros-dev/rosbags/<您的錄製資料夾名稱> --clock
```

*此時，您會在 RViz2 畫面上看見雷達點雲隨車子軌跡移動，並且 SLAM 演算法開始即時計算並重建地圖！*

---

## ⚠️ 疑難排解 (Troubleshooting)

### 1. 播放時 RViz2 沒有地圖或 TF 報錯？
- **原因**：沒有使用模擬時間，或是沒有播放時鐘。
- **解法**：請確保 SLAM 節點啟動時有設定 `use_sim_time:=true`，且播放時有帶上 `--clock` 參數。

### 2. 錄製時檔案太大？
- **原因**：錄製了相機的未壓縮原始影像（每秒數百 MB）。
- **解法**：預設的錄製主題不包含影像，非常節省空間。如果需要影像，請使用 `-c` 選項以記錄壓縮後的影像（`/compressed` 主題），切勿使用 `-a` 錄製所有主題，除非您有極大的硬碟空間。
