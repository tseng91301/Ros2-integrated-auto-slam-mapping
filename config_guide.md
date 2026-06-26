# ⚙️ 參數設定檔使用指南 (robot_params.yaml)

為了簡化設定，本專案在工作空間根目錄下設計了統一的設定檔 **`robot_params.yaml`**。所有關鍵的硬體埠口、避障距離、導航膨脹半徑、以及模擬模式切換，皆可在該檔案中一次設定完成，無需修改複雜的 ROS 2 Launch 檔或 XML 設定檔。

---

## 🗺️ 相關文件連結
- **主入口指南**：[Readme.md](file:///home/ubuntu/workspaces/isaac_ros-dev/Readme.md)
- **一鍵啟動 (Tmux 腳本)**：[launcher_guide.md](file:///home/ubuntu/workspaces/isaac_ros-dev/launcher_guide.md)
- **自主探索與避障原理**：[working_principles.md](file:///home/ubuntu/workspaces/isaac_ros-dev/working_principles.md)

---

## 1. 設定檔參數詳解

開啟 [robot_params.yaml](file:///home/ubuntu/workspaces/isaac_ros-dev/robot_params.yaml)：

```yaml
robot:
  radius: 0.22                  # 機器人的物理定義半徑 (米)
  chassis_port: "/dev/playrobot_base"  # 機器人底盤序列埠連接位置 (綁定 udev 後之路徑)
  lidar_port: "/dev/sllidar_a2m12"      # Lidar 雷達序列埠連接位置

navigation:
  inflation_radius: 0.75        # 導航寬限膨脹半徑 (機器人需與牆壁保持之最小距離) (米)
  obstacle_critical_dist: 0.6  # 導航模式下：緊急避障停止臨界距離 (米)
  obstacle_safety_dist: 0.35     # 導航模式下：開始修正避障之安全警戒距離 (米)
  
exploration:
  obstacle_critical_dist: 0.6  # 自主探索模式下：緊急避障後退並轉向之臨界距離 (米)
  obstacle_safety_dist: 0.3     # 自主探索模式下：開始產生排斥力修正朝向之安全距離 (米)

simulation:
  is_sim: false                 # 是否啟用 Gazebo 模擬模式 (true/false)
  world_path: "/workspaces/isaac_ros-dev/src/auto_explorer/config/my-nav-map.sdf"  # 模擬器載入的世界地圖路徑
```

### 📋 參數功能說明與調參建議

#### A. 機器人物理與硬體設定 (`robot`)
- **`radius`** (預設 `0.22`)：機器人本身的旋轉半徑。會被動態注入至 Nav2 代價地圖 (Costmap) 作為碰撞半徑，以及自主探索 node 作為邊界檢索膨脹半徑。若調得過小，機器人可能會擦撞牆壁；過大則會使機器人不敢進入狹窄的門口。
- **`chassis_port` & `lidar_port`**：通訊埠路徑。配合 [udev-rules.md](file:///home/ubuntu/setup_data/udev-rules.md) 將硬體符號連結別名填寫於此。

#### B. 導航參數 (`navigation`)
- **`inflation_radius`** (預設 `0.75`)：膨脹半徑。地圖中牆壁障礙物周圍會生成此半徑範圍的致命/警告代價區。**建議值為機器人半徑的 2.5 ~ 3.5 倍**。若機器人行進時常因靠近牆壁而頻繁重新規劃 (Replanning)，可適度調小此值。
- **`obstacle_critical_dist` & `obstacle_safety_dist`**：控制人工勢能場在導航模式下的觸發時機。

#### C. 自主探索參數 (`exploration`)
- **`obstacle_safety_dist`** (預設 `0.3`)：當雷達量測到障礙物小於此距離時，人工勢能場（APF）演算法會對機器人施加一個指向相反方向的斥力，促使機器人邊前進邊轉彎繞開障礙。
- **`obstacle_critical_dist`** (預設 `0.6`)：當機器人前方的障礙物小於此臨界值時，將立即觸發**緊急避障後退並自轉轉彎**，避免直接撞上死角。

#### D. 模擬器控制 (`simulation`)
- **`is_sim`** (預設 `false`)：**核心切換開關**。
  - 當設定為 `false`，一鍵啟動腳本會執行實體底盤控制與雷達驅動，並將資料發送至實體機器人。
  - 當設定為 `true`，一鍵啟動腳本會**自動忽略實體序列埠掛載**，自動以模擬預設模式啟動 Gazebo 虛擬模擬器與 SLAM，並為所有運行節點自動加上 `use_sim_time:=true` 參數。
- **`world_path`**：模擬載入的世界地圖。專案內置了多個三維地圖（如 `tb3_sandbox.sdf` 或倉庫地圖），可直接修改路徑進行更換。

---

## 2. 參數如何被動態載入與套用？

設定檔的套用是全自動的。當您執行 `ros2_tmux_launcher.sh` 啟動程式時，背後會觸發以下動作：

1. **動態產生 Nav2 設定檔**：
   啟動腳本會在背景啟動一個 Python parser，讀取 `robot_params.yaml` 中的 `robot.radius` 與 `navigation.inflation_radius` 參數值，然後覆寫 `auto_explorer` 預設的 YAML 設定，生成一份動態設定檔：`nav2_params_with_slam_generated.yaml`。
2. **自動映射 Launch 參數**：
   啟動 `auto_explorer` 節點與 Lidar 節點時，腳本會自動將 YAML 中讀出的 `lidar_port` 等值作為引數傳遞給 Launch 檔。
3. **自動切換模擬時間**：
   若 `is_sim` 為 `true`，Tmux 派發的所有 ROS 2 指令都會自動附加 `use_sim_time:=true`，確保時間戳記與 Gazebo 模擬時鐘同步，防止 TF 變換因時間差報錯。
