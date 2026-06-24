# 🧭 Thor Autonomous Map Exploration User Guide (自主地圖探索使用指南)

本指南說明如何啟動與使用 **Autonomous Map Exploration (自主地圖探索)** 功能。此功能包含後端的邊界偵測與連通區域分群 (Frontier-Based Clustering) 演算法、人工勢能場 (Artificial Potential Field, APF) 避障控制，以及前端的即時地圖與控制網頁。

---

## 🚀 1. 快速啟動 (使用 Tmux 一鍵部署)

我們已將所有相依節點（底盤、雷達、SLAM 建圖、網頁伺服器、自主探索節點及 RViz2）整合至 `ros2_tmux_launcher.sh` 啟動指令中。

### 步驟 1: 連線至 Host 主機
在您的終端機，切換到工作空間路徑：
```bash
cd ~/workspaces/isaac_ros-dev
```

### 步驟 2: 執行一鍵啟動腳本
執行以下指令以 `explore` 預設模式啟動：
```bash
./ros2_tmux_launcher.sh explore
```
*(提示：若先前有殘留的舊會話或節點，您可以加上 `-kill` 參數進行強制清理再啟動：`./ros2_tmux_launcher.sh explore -kill`)*

#### 執行效果：
* 腳本將會自動啟動 Docker 開發容器並載入 ROS 2 Jazzy 環境。
* 在 Tmux 中以五分割畫面啟動：
  1. **底盤通訊控制** (`base_control_ros2`)
  2. **SLAM Toolbox 建圖** (`wheeltec_slam_toolbox`)
  3. **Lidar 雷達驅動** (`sllidar_ros2`)
  4. **網頁伺服器** (`wheeltec_web_teleop`)
  5. **自主探索節點** (`auto_explorer`)
* 在新視窗分頁中開啟 **RViz2 視覺化工具**（展示 SLAM 地圖與探索標記）。
* 您會被附著在 Tmux 會話中，並自動選取第 5 個窗格（自動探索節點）方便查看輸出日誌。

---

## 💻 2. 手動啟動方式 (逐步執行)

若您想在不同的終端機手動控制各個節點，請參照以下指令：

### 步驟 1: 進入 Docker 容器並編譯 (若有修改)
```bash
docker exec -it isaac_ros_dev_container /bin/bash
# 進入容器後編譯工作空間
cd /workspaces/isaac_ros-dev
colcon build --packages-select auto_explorer wheeltec_web_teleop
source install/setup.bash
```

### 步驟 2: 啟動網頁伺服器 (包含控制路由)
```bash
source /opt/ros/jazzy/setup.bash
source /workspaces/isaac_ros-dev/install/setup.bash
ros2 launch wheeltec_web_teleop web_teleop.launch.py
```

### 步驟 3: 啟動自主探索節點
```bash
source /opt/ros/jazzy/setup.bash
source /workspaces/isaac_ros-dev/install/setup.bash
ros2 launch auto_explorer auto_exploration.launch.py
```
*(預設參數：`robot_radius:=0.20` 避障半徑膨脹、`max_exploration_laps:=1` 探索圈數)*

---

## 🌐 3. Web UI 介面操作指南

啟動完成後，您可以使用與機器人同一個區域網路的電腦或手機開啟瀏覽器存取網頁。

### 步驟 1: 進入入口門戶 (Portal)
打開瀏覽器輸入：
```text
http://<機器人_IP>:8080/
```
您將會看到 **THOR ROBOTICS 門戶選單**：
1. **Manual Remote (手動控制)**：進入原有的 `/teleop` 路徑，進行鍵盤、搖桿遙控。
2. **Auto Explorer (自主探索)**：進入 `/explorer` 路徑，進入自主探索控制中心。

### 步驟 2: 進入自主探索頁面 (`/explorer`)
點選 **Explore Mode**，即可進入自主探索頁面：

#### 📊 即時遙測 HUD 資訊欄：
* **STATUS (當前狀態)**: 
  * `PAUSED` (已暫停/初始安全狀態)
  * `EXPLORING` (正在探索中)
  * `COMPLETE` (探索已完成)
* **ACTIVE GOAL (目標坐標)**: 顯示當前機器人正朝向的邊界群集中心的世界坐標 `(X, Y)`，若無目標則顯示 `None`。
* **LAP PROGRESS (探索圈數)**: 顯示當前進度與設定的最大圈數 (例如 `1 / 3`)。
* **FRONTIERS (邊界群集數)**: 顯示目前地圖上偵測到的有效邊界點群數。

#### 🗺️ 實時地圖顯示與標記說明：
* **網格地圖**: 深藍色區域為未探測 (Unknown)，黑色區域為已探測空曠區 (Free)，亮青色線條與區塊為障礙物/牆面 (Occupied)。
* **機器人信標**: 紅色實心圓圈與方向箭頭，代表機器人當前位置與朝向。周圍的外圈紅色波紋表示即時的雷達掃描與避障檢測。
* **邊界質心 (Frontier Centroids)**: **綠色小圓點**，代表演算法偵測到有未知區域與自由區域交界的探索候選點。
* **當前目標 (Active Target)**: **藍色瞄準十字標記**，代表機器人當前的導航目標點（通常是距離最近的綠色質心）。
* **地圖操作**: 可以使用鼠標滾輪進行縮放、左鍵拖動平移，或點選右下角的 `+`、`-`、`⟲` 按鈕調整視角。

#### ⚙️ 自主探索控制器功能按鈕 (Explorer Controller)：
1. **START EXPLORATION (開始探索)**：解除安全暫停狀態，啟動自動導航。
2. **PAUSE (暫停)**：立即停止機器人移動，並暫停目標搜索。
3. **RESUME (繼續)**：繼續以當前的地圖進度進行探索。
4. **RESET EXPLORATOR (重置探索狀態)**：重置內部 Lap 圈數並清空目標黑名單，讓機器人重新規劃探索。
5. **LOOP SETTINGS (圈數設定)**：
   * 在輸入框調整圈數（預設為 1，代表探索完所有邊界即停止）。
   * 點選 **SET** 套用。
   * **提高精度建議**：若設定為 2 或 3，當第一輪探索完成後，節點會自動清除黑名單，讓機器人開往剩下的細小區域，這會**強制 SLAM 進行閉環檢測 (Loop Closure)**，大幅提升建圖的閉合與準確度。

#### 💾 地圖管理功能按鈕 (Map Management)：
1. **SAVE MAP (ROBOT)**：發送指令至機器人，將當前地圖保存至機器人的本地儲存空間（`/home/ubuntu/maps/`）。
2. **RESET SLAM MAP**：清空 SLAM Toolbox 中已構建的所有地圖資料，並重新開始建圖。
3. **DOWNLOAD PNG**：將瀏覽器 Canvas 畫布上的即時地圖匯出並下載為 PNG 圖像檔案。
4. **DOWNLOAD ZIP**：發送指令調用 ROS 2 `map_saver_cli` 產生標準的 `map.pgm` 與 `map.yaml` 設定檔，並包裝成 ZIP 檔案直接下載至您的電腦，可用於後續 Nav2 導航部署。

#### 🚨 緊急停機 (EMERGENCY STOP)：
* 點選最下方的紅色 **EMERGENCY STOP** 按鈕，會立即發送暫停中斷命令並發送零速控制命令，確保機器人停機安全。

---

## 🛠️ 4. 常見問題與調參說明

1. **機器人卡住或無法到達藍色目標點？**
   * **原因**：藍色目標點可能位於狹窄通道、障礙物邊緣，或受雷達雜訊影響。
   * **解決方案**：`auto_explorer` 節點內置了**防卡死與超時黑名單機制**。若機器人在 3 秒內移動距離小於 0.15 米，或前往同一個目標超過 25 秒，系統會自動將該目標點列入黑名單，並自動尋找下一個最近的邊界質心。

2. **如何調整避障靈敏度與安全距離？**
   * 您可以在 `/explorer` 啟動時修改 Launch 參數：
     * `robot_radius` (預設 `0.20`m)：控制邊界質心與牆壁的最小安全防護膨脹距離。
     * `obstacle_safety_dist` (預設 `0.6`m)：在此距離內雷達會產生排斥力 (Repulsive Force) 修正朝向。
     * `obstacle_critical_dist` (預設 `0.35`m)：在此距離內會觸發緊急後退並轉彎避障。
