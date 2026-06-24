# 🗺️ Jetson Thor 機器人網頁控制與實時建圖操作指南

本指南說明如何啟動與使用本專案新增的 **網頁遙控器與實時地圖圖傳系統 (`wheeltec_web_teleop` 功能包)**。該系統提供專為手機與電腦設計的類空拍機遙控器介面，讓您能在瀏覽器中實時遙控機器人、查看 SLAM 建圖畫面並直接下載地圖。

---

## 🚀 1. 如何啟動網頁控制

您可以選擇使用 tmux 腳本「一鍵啟動」完整建圖與網頁遙控，或在 Docker 容器內「獨立啟動」網頁服務。

### 模式 A：一鍵啟動建圖 + 網頁遙控 (推薦)
此模式會同時啟動：底盤通訊、雷達驅動、SLAM 建圖、網頁遙控伺服器及 RViz2 視覺化工具。

1. 在 **Host 本機端** (不要進入 Docker 容器) 的終端機執行：
   ```bash
   cd /home/ubuntu/workspaces/isaac_ros-dev
   
   # 1. 確保硬體序列埠已掛載至 Docker 容器內
   ./attach_devices.sh /dev/playrobot_base /dev/sllidar_a2m12
   
   # 2. 啟動 web_all 模式
   ./ros2_tmux_launcher.sh web_all
   ```
2. 系統會自動建立 tmux 會話，並在後端分割窗格運行各節點，隨後開啟 RViz2 視窗。

### 模式 B：獨立啟動網頁控制服務
若您已透過其他方式啟動了機器人底盤、雷達與建圖節點，可以單獨啟動網頁伺服器：

1. 進入 Docker 容器並載入環境變數：
   ```bash
   docker exec -it isaac_ros_dev_container /bin/bash
   source /opt/ros/jazzy/setup.bash
   cd /workspaces/isaac_ros-dev
   source install/setup.bash
   ```
2. 啟動網頁遙控節點：
   ```bash
   ros2 launch wheeltec_web_teleop web_teleop.launch.py
   ```

---

## 📡 2. 如何連線與開啟 Web 介面

網頁伺服器啟動後會監聽在 Jetson Thor 的 **`8080`** 連接埠。

1. **取得機器人 IP 位址**：
   在 Jetson 終端機執行 `hostname -I`，例如取得 `192.168.1.108`。
2. **開啟瀏覽器**：
   將您的**手機**或**電腦**連接至與機器人相同的 Wi-Fi 網路，打開瀏覽器並輸入網址：
   ```text
   http://<機器人IP>:8080
   # 例如: http://192.168.1.108:8080 (若在機器人本機測試可輸入 http://localhost:8080)
   ```
3. **連線狀態確認**：
   * 右上角狀態指示燈顯示 <span style="color:#22c55e; font-weight:bold;">● ONLINE</span> 代表 WebSocket 連線成功。
   * 中間地圖螢幕的載入雷達掃描動畫會消失，並開始繪製掃描到的地圖。

---

## 🕹️ 3. Web 介面使用與遙控說明

介面採用類似**空拍機遙控器**的左右對稱佈局，以確保觸控與單手操作的便利度。

### 🕹️ 搖桿與按鈕控制區
* **左側搖桿/按鈕 (線性速度控制 - 前進/後退/平移)**：
  - 向上推/按前進：前進。
  - 向下推/按後退：後退。
  - 向左/右推 (需啟用 **Holonomic Mode**)：控制麥克納姆輪向左或向右側向橫移 (Strafing)。
* **右側搖桿/按鈕 (角速度控制 - 自轉轉向)**：
  - 向左推/按左轉：原地逆時針自轉。
  - 向右推/按右轉：原地順時針自轉。
* **搖桿與按鈕模式切換**：
  - 左右控制區上方設有 `JOYSTICK` 與 `D-PAD` 切換開關。
  - **JOYSTICK**：虛擬類比搖桿，支援觸控滑動或滑鼠拖曳，推得越遠速度越快。
  - **D-PAD**：九宮格方向按鈕，點擊並按住可控制移動，放開即停止。

### ⚙️ 參數設定與輔助功能
* **LINEAR (X/Y) 與 ANGULAR (Z) 速度限制滑桿**：
  - 位於網頁左下方。您可以調整滑動條來限制輸出最大速度。
  - 線性速度上限調小能確保機器人安全地在狹窄空間移動。
* **Enable Holonomic Mode (Strafing) 勾選框**：
  - 啟用後，左側搖桿/按鈕將支援全向橫移控制 (左右側移)。若未勾選，則只支援前後移動。
* **EMERGENCY STOP (紅色緊急停止鈕)**：
  - 位於網頁右下方。在遇到危險時點擊，系統會立即下發 `0` 速度指令，地圖視窗會觸發震動警告。
* **Keyboard Control Help (鍵盤操作支援)**：
  - 在電腦瀏覽器上操作時，支援使用鍵盤按鍵進行操作（按鍵對應與原有的 `wheeltec_keyboard` 節點一致）：
    - **`i` / `ArrowUp`**：前進 | **`,` / `ArrowDown`**：後退。
    - **`j` / `ArrowLeft`**：左轉 | **`l` / `ArrowRight`**：右轉。
    - **`u` / `o` / `m` / `.`**：斜向控制與弧形彎道控制。
    - **`k` / `Space`**：即時制動停止。
    - **按住 `Shift` 鍵**：臨時進入全向側移 (Strafing) 模式。

### 📱 手機瀏覽器佈局滾動
* 當手機垂直使用或螢幕高度較短時，系統會自動在**畫面左邊緣**生成一條極細且精緻的**霓虹青色滾動條**。
* 這是為手機操作專門設計的防誤觸通道。拖曳此滾動條或滑動左側區塊即可上下滾動網頁，訪問底部的速度限制滑桿或緊急停止按鈕，而不會誤觸到搖桿或地圖的拖曳手勢。

---

## 🗺️ 4. 實時地圖、縮放、定位與比例尺說明

中間的地圖顯示螢幕整合了先進的 HUD 視覺化特性：

### 🔍 地圖互動手勢
* **縮放 (Zoom)**：
  - 電腦端：使用滑鼠滾輪，會以滑鼠指針為中心進行縮放。
  - 手機端：使用雙指進行捏合 (Pinch-to-zoom) 手勢。
  - 快捷按鈕：地圖右上方設有浮動按鈕：`+` 放大、`-` 縮小、`⟲` 自動重設並置中視角。
* **拖曳平移 (Pan)**：
  - 使用滑鼠左鍵或單指在畫面上按住拖曳，可移動地圖視角。

### 📏 機器人定位與比例尺
* **機器人位置信標 (Robot Beacon)**：
  - 地圖中會以一個**紅色圓形外圈搭配白色箭頭**代表機器人的即時位置。
  - 紅色外圈會持續進行呼吸脈動（Pulsing）動畫，白色箭頭所指方向即為機器人的實際朝向 (Yaw)。
  - 此資訊由後端 node 自動解析 `/tf` 座標變換樹 (`map -> base_footprint`) 後傳送至前端。
* **動態比例尺 (Scale Bar)**：
  - 地圖左下角設有動態比例尺（例如 `1 m` 或 `50 cm` 刻度線）。
  - 該比例尺會隨著您放大或縮小地圖時自動重新計算並即時更新線段長度，方便您視覺化評估機器人與障礙物的相對距離。

### 🎨 地圖顏色區分說明
為提升可讀性與現代科技感，掃描區域進行了高對比度色彩設計：
* <span style="background-color:#1e293b; color:#ffffff; padding:2px 6px; border-radius:4px; font-weight:bold;">石板藍灰 (Slate Blue-Gray)</span>：**未掃描區域 (Unknown Area)**，代表雷達尚未探測到的未知空間。
* <span style="background-color:#0a0f1a; color:#ffffff; padding:2px 6px; border-radius:4px; font-weight:bold;">深藍近黑 (Dark Slate)</span>：**已探測空白區域 (Free Space)**，代表雷達已確認無障礙物、安全可行走的開闊空間。
* <span style="background-color:#00f0ff; color:#000000; padding:2px 6px; border-radius:4px; font-weight:bold;">霓虹青藍 (Neon Cyan)</span>：**牆壁與障礙物 (Occupied Area)**，代表探測到的障礙邊界。

---

## 💾 5. 地圖儲存、重置與下載說明

地圖螢幕底部提供了四種地圖控制功能：

| 功能按鈕 | 行為說明 | 檔案格式與下載位置 |
| :--- | :--- | :--- |
| **SAVE MAP** | 將建圖結果**儲存在 Jetson Thor 機器人本機**磁碟。點擊後輸入檔名即可儲存。 | **儲存路徑**：`/home/ubuntu/maps/`<br>會生成 `map.yaml` 與 `map.pgm`。 |
| **RESET MAP** | 向 `slam_toolbox` 發送地圖重置指令，**重新清除並重置整個 SLAM 建圖數據**。 | 會呼叫 `/slam_toolbox/reset` 服務。<br>地圖畫面會重新清空並重啟掃描。 |
| **DOWNLOAD PNG** | 直接將瀏覽器 Canvas 當前所渲染的地圖畫面**下載至手機/電腦**中，適合預覽與分享。 | **格式**：`robot_map.png`<br>直接下載到瀏覽器預設下載資料夾。 |
| **DOWNLOAD ROS** | 即時在後端封裝 ROS 建圖所需的標準導航格式，並**下載 ZIP 壓縮包到手機/電腦**。 | **格式**：`map_files.zip`<br>解壓後包含 `map.yaml`, `map.pgm` 以及 `map.png`。 |

> [!TIP]
> **地圖格式說明**：
> * `map.pgm`：黑白像素地圖（0 為可行走區域，255 為未知，100 為障礙物/牆壁）。
> * `map.yaml`：描述地圖的解析度（Resolution）、地圖原點座標（Origin）以及關聯 the pgm 檔案路徑。

---

## 📦 6. 依賴套件與疑難排解 (Dependencies & Troubleshooting)

本專案功能包依賴於部分特定的系統套件與 Python 程式庫。如果您的 Docker 容器在初始化或重建後，遇到程式崩潰或缺少套件的錯誤（例如 `ModuleNotFoundError` 或 CMake 找不到套件），請參考以下統一的修復指引：

### ⚠️ 常見的缺失套件錯誤：
* **Python 套件缺失**：`ModuleNotFoundError: No module named 'tornado'` 或 `ModuleNotFoundError: No module named 'quaternion'`。
* **ROS 2 套件或 Message 缺失**：無法導入 `cv_bridge`、`realsense2_camera_msgs`，或是編譯時提示找不到 `nav2_bringup` 套件。

### 🛠️ 統一安裝與固化解決方案：

1. **進入運作中的 Docker 容器內部**：
   ```bash
   docker exec -it isaac_ros_dev_container /bin/bash
   ```

2. **在容器內部一鍵安裝所有缺失套件**：
   ```bash
   # 更新套件清單並安裝 ROS 2 與系統級套件
   sudo apt-get update && sudo apt-get install -y \
     ros-jazzy-cv-bridge \
     ros-jazzy-nav2-common \
     ros-jazzy-nav2-simple-commander \
     ros-jazzy-navigation2 \
     ros-jazzy-nav2-bringup \
     ros-jazzy-xacro \
     ros-jazzy-tf-transformations \
     ros-jazzy-theora-image-transport \
     ros-jazzy-realsense2-camera \
     ros-jazzy-realsense2-camera-msgs \
     ros-jazzy-librealsense2 \
     python3-tornado \
     python3-pip \
     python3-matplotlib \
     python3-requests \
     python3-serial \
     python3-tqdm

   # 使用 pip 安裝 Python 特有依賴（需突破系統套件限制）
   pip3 install numpy-quaternion pyrealsense2 --break-system-packages
   ```

3. **固化變更以防容器重啟後遺失**：
   為防止 Docker 容器在重新建立（如執行 `./start_container.sh`）時，因 `--rm` 參數將變更抹除，請於 **Host 端** 執行以下指令，將運行中容器的狀態固化回 Docker 鏡像：
   ```bash
   docker commit isaac_ros_dev_container cached_isaac_run_dev_image_local:latest
   ```


