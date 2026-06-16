# ROS 2 常用指令速查表 (Humble)

本文件整理了 ROS 2 (以 Humble 版本為主) 在日常開發與除錯中，最常用到的指令分類與語法。

---

## 1. 工作區編譯與環境設定

### 設定環境變數
每次開啟新的終端機，都必須先載入環境：
```bash
# 載入 ROS 2 底層環境
source /opt/ros/humble/setup.bash

# 載入個人工作區環境 (在工作區根目錄執行)
source install/setup.bash
```

### 使用 colcon 編譯
```bash
# 編譯工作區內所有的功能包
colcon build

# 僅編譯指定的功能包 (省時推薦)
colcon build --packages-select <package_name>

# 建立符號連結 (修改 Python 代碼或設定檔後，不需重新 colcon build 即可生效)
colcon build --symlink-install
```

---

## 2. 運行節點與 Launch 啟動

### 啟動單一節點 (Node)
```bash
ros2 run <package_name> <executable_name>
```

### 啟動多節點包 (Launch)
```bash
ros2 launch <package_name> <launch_file_name>
```
* **傳入參數範例**：
  ```bash
  ros2 launch sllidar_ros2 sllidar_a3_launch.py serial_port:=/dev/ttyUSB0
  ```

---

## 3. Node (節點) 指令

```bash
# 列出目前所有正在運行的節點
ros2 node list

# 查看特定節點的詳細資訊 (包含發布/訂閱的主題、服務、參數等)
ros2 node info <node_name>
# 範例：ros2 node info /sllidar_node
```

---

## 4. Topic (主題) 指令

```bash
# 列出目前活躍中的所有主題
ros2 topic list

# 列出所有主題，並顯示其訊息類型 (Message Type)
ros2 topic list -t

# 即時印出特定主題的資料內容
ros2 topic echo <topic_name>
# 範例：ros2 topic echo /scan

# 查看特定主題的詳細資訊 (例如誰在 Publish，誰在 Subscribe)
ros2 topic info <topic_name>

# 檢查特定主題的發布頻率 (Hz)
ros2 topic hz <topic_name>

# 檢查特定主題的頻寬佔用狀況 (Bandwidth)
ros2 topic bw <topic_name>

# 手動發布單次資料到指定主題
ros2 topic pub --once <topic_name> <msg_type> "<data>"
# 範例：ros2 topic pub --once /chatter std_msgs/msg/String "{data: 'Hello World'}"
```

---

## 5. Param (參數) 指令

```bash
# 列出所有節點目前擁有的參數列表
ros2 param list

# 取得特定節點的某個參數值
ros2 param get <node_name> <parameter_name>
# 範例：ros2 param get /simple_pub my_parameter

# 設定/修改特定節點的某個參數值
ros2 param set <node_name> <parameter_name> <value>
# 範例：ros2 param set /simple_pub my_parameter "David"

# 將特定節點目前的參數全部備份匯出成 yaml 檔案
ros2 param dump <node_name> > params.yaml
```

---

## 6. Service (服務) 指令

```bash
# 列出目前可用的所有服務
ros2 service list

# 查看服務所使用的介面類型
ros2 service type <service_name>

# 手動呼叫某個服務並傳入請求資料
ros2 service call <service_name> <service_type> "<request_data>"
# 範例：ros2 service call /clear std_srvs/srv/Empty "{}"
```

---

## 7. Interface (介面/訊息結構) 指令

用於查看 Topic Message (`msg`) 或 Service (`srv`) 的內部資料格式定義。
```bash
# 查看特定訊息/服務的詳細欄位結構
ros2 interface show <interface_name>
# 範例：ros2 interface show sensor_msgs/msg/LaserScan
```

---

## 8. Bag (錄製與回放) 指令

用於錄製感測器數據以方便後續離線測試。
```bash
# 錄製指定主題的資料到名為 my_bag 的資料夾
ros2 bag record -o my_bag /scan /tf

# 回放錄好的數據包
ros2 bag play my_bag
```

---

## 9. 圖形化視覺化工具

```bash
# 啟動 3D 視覺化視窗 (主要用來看雷達點雲、機器人模型、地圖、路徑等)
rviz2

# 啟動整合型除錯工具 (可選取多種外掛，如繪製曲線圖、發送主題等)
rqt

# 產生目前的節點關係圖 (Node Graph)，可用於理清節點與主題之間的連接關係
rqt_graph
```
