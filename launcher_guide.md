# ⚡ ros2_tmux_launcher.sh 啟動腳本使用說明

本專案提供了一套強大的一鍵部署啟動工具：`ros2_tmux_launcher.sh`。該腳本運行在 **Host 本機端**，利用 `tmux` 終端機管理器，自動完成容器確認、硬體裝置掛載、工作空間環境載入，並在單一終端會話中以多分割視窗與分頁啟動多個 ROS 2 節點，大幅降低手動開發的複雜度。

---

## 🗺️ 相關文件連結
- **主入口指南**：[Readme.md](Readme.md)
- **手動操作與常用指令**：[ros2_commands_guide.md](ros2_commands_guide.md)
- **裝置掛載說明**：[docker_device_connection.md](docker_device_connection.md)

---

## 🚀 快速啟動與基本用法

您只需在 **Host 本機端** 的工作空間目錄下執行此腳本，並傳入「預設組合模式 (Presets)」或「自訂模組清單」即可：

```bash
cd /home/ubuntu/workspaces/isaac_ros-dev
chmod +x ros2_tmux_launcher.sh

# 語法格式
./ros2_tmux_launcher.sh <模式 | 模組清單> [參數參數]
```

### 💡 預設組合模式 (Presets)

| 模式名稱 | 適用場景 | 啟動之節點組合 |
| :--- | :--- | :--- |
| **`teleop`** | 實體機器人手動遙控偵錯 | 底盤控制器 + 終端機鍵盤遙控 (雙分割畫面) |
| **`slam_all`** | 實體機器人手動建圖 | 底盤 + 雷達 + SLAM Toolbox + 鍵盤遙控 + RViz2 |
| **`web_all`** / **`explore`** | 實體機器人自主探索建圖 | 底盤 + 雷達 + SLAM Toolbox + Web 遙控伺服器 + 自主探索節點 + RViz2 |
| **`sim_keyboard`** | 虛擬模擬器鍵盤建圖 | Gazebo 模擬器 + SLAM + 鍵盤遙控 + RViz2 |
| **`sim_web_all`** / **`sim_explore`** | 虛擬模擬器自主探索建圖 | Gazebo 模擬器 + SLAM + Web 遙控伺服器 + 自主探索節點 |
| **`terminal`** | 臨時進入 ROS 2 開發環境 | 僅新建一個 source 好環境變數的 Docker 互動終端分頁 |

---

## ⚙️ 全域參數選項 (Options)

啟動腳本支援以下選用參數：

1. **`--domain` 或 `--domain-id <ID>`**
   - **用途**：指定自定義的 `ROS_DOMAIN_ID`，避免在同一個區域網路下與其他人的機器人發生主題衝突。
   - **預設值**：`55`。
   - **範例**：`./ros2_tmux_launcher.sh slam_all --domain 88`
2. **`-kill` 或 `--kill`**
   - **用途**：在啟動前強制清理舊的 tmux 會話與背景殘留節點進程（底盤、雷達、Gazebo、Web 等），防止埠口佔用。
   - **範例**：`./ros2_tmux_launcher.sh explore -kill`

---

## 🛠️ 自訂模組組合 (Custom Modules)

除了預設模式外，您也可以手動挑選要啟動的子模組，腳本會根據您傳入的模組數量，自動進行對應的畫面分割：

```bash
./ros2_tmux_launcher.sh <模組1> [模組2] [模組3] ...
```

### 支援的自訂模組參數：
- **`chassis`**：底盤通訊控制節點 (`base_control_ros2`)。
- **`lidar`**：RPLIDAR A2M12 雷達驅動節點 (`sllidar_ros2`)。
- **`slam`**：SLAM Toolbox 異步建圖服務。
- **`keyboard`**：終端機鍵盤遙控節點。
- **`web`**：網頁遙控與實時建圖 Tornado 伺服器。
- **`explorer`**：邊界自主探索節點 (`auto_explorer`)。
- **`rviz` / `rviz2`**：視覺化工具 RViz2 (載入 SLAM 設定檔)。

### 自訂組合範例：
```bash
# 範例 1：只啟動底盤與雷達
./ros2_tmux_launcher.sh chassis lidar

# 範例 2：啟動底盤、鍵盤與 RViz2
./ros2_tmux_launcher.sh chassis keyboard rviz

# 範例 3：啟動底盤、雷達、建圖與網頁遙控
./ros2_tmux_launcher.sh chassis lidar slam web
```

---

## ⌨️ Tmux 終端管理器操作速查

腳本執行後，會將您的終端機接附 (Attach) 至名為 `ros2_dev` 的 Tmux 會話中。請記住以下常用快捷鍵以方便操作（皆為先按 `Ctrl + B` 放開，再按功能鍵）：

- **🎯 切換視窗格 (Pane)**：按 `Ctrl + B`，然後按方向鍵 `↑` `↓` `←` `→`。
- **📚 切換分頁 (Window)**：按 `Ctrl + B`，然後按數字鍵 `0`（通常為 SLAM/Simulation）或 `1`（通常為 RViz2）。
- **⏸️ 暫時離開 tmux (背景繼續運行)**：按 `Ctrl + B`，然後按 `D`。
  - 離開後若想重新連回會話，可在 Host 終端機輸入：`tmux attach -t ros2_dev`。
- **🛑 關閉整個會話 (停止所有程式)**：按 `Ctrl + B`，然後輸入 `:kill-session` 按 Enter。或者直接在 Host 執行帶有 `-kill` 的啟動腳本。
