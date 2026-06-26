# 🚀 Jetson Thor ROS 2 開發工作空間指南 (Workspace README)

歡迎使用本 ROS 2 工作空間！此工作空間已掛載於 NVIDIA Isaac ROS Docker 開發容器內部。本專案整合了馬達底盤驅動、RPLIDAR A2M12 雷達驅動、SLAM 異步建圖、網頁圖傳遙控器、以及邊界自主探索演算法。

本文件為 **工作空間操作說明的主入口**。為了保持排版簡潔與資訊易讀，所有功能已細分為獨立子指南。

---

## 🗺️ 開發與操作指南目錄 (Table of Contents)

請點擊以下相對路徑連結，閱讀對應的技術細節與操作手冊：

| 順序 | 指南名稱 | 內容說明 | 連結檔案路徑 |
| :---: | :--- | :--- | :--- |
| **0** | **🔌 Host 本機安裝與部署** | 剛拿到機器人的本機驅動安裝與容器初始化步驟 | [../../setup_data/Readme.md](file:///home/ubuntu/setup_data/Readme.md) |
| **1** | **🐳 Docker 裝置掛載與串接** | 如何動態或靜態地將雷達與底盤硬體節點掛載至 Docker 容器內 | [docker_device_connection.md](file:///home/ubuntu/workspaces/isaac_ros-dev/docker_device_connection.md) |
| **2** | **💻 ROS 2 常用指令與環境準備** | 進入 Docker 容器、工作空間編譯、手動運行單一節點與 GUI (X11) 顯示設定 | [ros2_commands_guide.md](file:///home/ubuntu/workspaces/isaac_ros-dev/ros2_commands_guide.md) |
| **3** | **⚡ 一鍵啟動 (Tmux 腳本說明)** | 使用 `ros2_tmux_launcher.sh` 腳本一鍵部署實體/模擬遙控與探索 | [launcher_guide.md](file:///home/ubuntu/workspaces/isaac_ros-dev/launcher_guide.md) |
| **4** | **🌐 Web 網頁控制與實時建圖** | 手機/電腦瀏覽器遠端搖桿遙控、地圖下載、地圖重置與 UI 介面說明 | [web_control_guide.md](file:///home/ubuntu/workspaces/isaac_ros-dev/web_control_guide.md) |
| **5** | **🧭 邊界自主探索與避障原理** | 基於 Frontier-Based Clustering & APF 避障的四階段自動建圖演算法運作機制 | [working_principles.md](file:///home/ubuntu/workspaces/isaac_ros-dev/working_principles.md) |
| **6** | **⚙️ 參數設定檔使用指南** | 解釋 `robot_params.yaml` 對底盤、雷達、導航、避障、與模擬參數的動態映射 | [config_guide.md](file:///home/ubuntu/workspaces/isaac_ros-dev/config_guide.md) |

---

## 📂 專案核心功能包簡介
工作空間的軟體包皆位於 `src/` 目錄下：
- **`base_control_ros2`**：底盤控制節點，負責與 CH340 序列晶片通訊，將 `/cmd_vel` 速度指令轉換為馬達驅動訊號，並發布里程計 (`/odom`)。
- **`sllidar_ros2`**：RPLIDAR A2M12 雷達驅動節點，讀取光電雷達資料並發布 `/scan` 點雲數據。
- **`wheeltec_slam_toolbox`**：SLAM Toolbox 整合配置包，用以提供高精度的二維地圖異步構建服務。
- **`wheeltec_robot_keyboard`**：經典的 ROS 2 終端機鍵盤遙控工具。
- **`wheeltec_web_teleop`**：後端 Tornado Web 伺服器與前端 Web UI，包含即時 Websocket 傳輸、動態比例尺地圖 Canvas、及虛擬搖桿與動作指令路由。
- **`auto_explorer`**：自主建圖探索演算法核心包，包含邊界檢索、無人引導路徑規劃、APF 避障與 Nav2 行動中繼控制器。