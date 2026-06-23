#!/usr/bin/env bash
# ros2_tmux_launcher.sh
# 使用 tmux 在 Docker 容器內多視窗啟動 ROS 2 常用節點

SESSION_NAME="ros2_dev"

# 顯示說明
show_help() {
    echo "🐳 ROS 2 tmux All-in-One 啟動工具"
    echo "使用方法: $0 [模式 | 模組清單]"
    echo ""
    echo "💡 預設預載組合模式 (Presets):"
    echo "  $0 teleop       - 啟動底盤控制器 + 鍵盤遙控 (雙分割畫面)"
    echo "  $0 slam_all     - 啟動底盤 + 雷達 + SLAM 建圖 + 鍵盤遙控 + RViz2 (多視窗格與分頁)"
    echo "  $0 web_all      - 啟動底盤 + 雷達 + SLAM 建圖 + 網頁遙控 + RViz2 (多視窗格與分頁)"
    echo ""
    echo "🛠️ 自訂模組組合 (Custom Modules):"
    echo "  $0 <模組1> [模組2] [模組3] ..."
    echo "  支援的自訂模組參數:"
    echo "    chassis       - 底盤通訊控制"
    echo "    lidar         - RPLIDAR A2M12 雷達驅動"
    echo "    slam          - SLAM Toolbox 異步建圖"
    echo "    keyboard      - 鍵盤遙控節點"
    echo "    web           - 網頁遙控與實時建圖伺服器"
    echo "    rviz / rviz2  - RViz2 視覺化工具 (載入 SLAM 設定)"
    echo ""
    echo "  自訂範例: $0 chassis lidar        (只啟動底盤與雷達)"
    echo "  自訂範例: $0 chassis keyboard rviz (啟動底盤、鍵盤與 RViz2)"
    echo "  自訂範例: $0 chassis lidar slam web (啟動底盤、雷達、建圖與網頁遙控)"
    echo ""
    exit 0
}

if [ "$#" -lt 1 ] || [ "$1" == "-h" ] || [ "$1" == "--help" ]; then
    show_help
fi

# 1. 確保 Docker 容器正在運行
if ! docker ps --format '{{.Names}}' | grep -q "^isaac_ros_dev_container$"; then
    echo "❌ 錯誤: isaac_ros_dev_container 容器未啟動！請先啟動 Docker 容器。"
    exit 1
fi

# 檢查是否需要啟動 GUI，如果是，先在 Host 本機端執行 xhost 授權 (避免在容器內報錯)
if [[ " $@ " =~ " rviz " ]] || [[ " $@ " =~ " rviz2 " ]] || [[ " $@ " =~ " slam_all " ]]; then
    echo "🖥️ 正在 Host 端授權 X11 顯示存取權 (xhost +local:docker)..."
    xhost +local:docker 2>/dev/null || true
fi

# 2. 清理先前還在運作的 tmux 會話與容器殘留進程
if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    echo "🧹 偵測到舊的 tmux 會話 '${SESSION_NAME}' 正在運行，正將其關閉..."
    tmux kill-session -t "$SESSION_NAME"
fi

# 額外清理容器內可能殘留的 ROS 2 與 Python 節點進程 (避免佔用序列埠或 CPU)
# 注意：使用 rviz2 (不加 -f) 避免匹配到含 'rviz2' 參數的本腳本名稱，導致腳本被 self-kill
echo "🧹 正在清理容器內可能殘留的舊節點進程..."
docker exec isaac_ros_dev_container pkill -9 -f [b]ase_control_node 2>/dev/null || true
docker exec isaac_ros_dev_container pkill -9 -f [b]in/ros2 2>/dev/null || true
docker exec isaac_ros_dev_container pkill -9 -f [j]oint_state_publisher 2>/dev/null || true
docker exec isaac_ros_dev_container pkill -9 -f [w]heeltec_keyboard 2>/dev/null || true
docker exec isaac_ros_dev_container pkill -9 -f [w]eb_server 2>/dev/null || true
docker exec isaac_ros_dev_container pkill -9 rviz2 2>/dev/null || true
sleep 1

# 共用指令前綴
DOCKER_EXEC="docker exec -it isaac_ros_dev_container"
ROS2_SETUP="source /opt/ros/jazzy/setup.bash && source /workspaces/isaac_ros-dev/install/setup.bash"

# ==================== 預設模式 1: teleop ====================
if [ "$1" == "teleop" ]; then
    echo "🚀 正在以 [teleop] 模式啟動底盤及鍵盤遙控..."
    
    # 建立會話
    tmux new-session -d -s "$SESSION_NAME" -n "Teleop"
    
    # 左窗格 (0.0): 啟動底盤
    tmux send-keys -t "$SESSION_NAME:0.0" "$DOCKER_EXEC bash -lc '$ROS2_SETUP && export BASE_TYPE=NanoRobot && ros2 launch base_control_ros2 00_base_control.launch.py'" C-m
    
    # 分割為右窗格 (0.1): 鍵盤遙控
    tmux split-window -h -t "$SESSION_NAME:0"
    tmux send-keys -t "$SESSION_NAME:0.1" "$DOCKER_EXEC bash -lc '$ROS2_SETUP && ros2 run wheeltec_robot_keyboard wheeltec_keyboard'" C-m
    
    # 選定鍵盤遙控窗格方便使用者直接輸入
    tmux select-pane -t "$SESSION_NAME:0.1"
    tmux attach-session -t "$SESSION_NAME"
    exit 0
fi

# ==================== 預設模式 2: slam_all ====================
if [ "$1" == "slam_all" ]; then
    echo "🚀 正在以 [slam_all] 模式啟動底盤、雷達、建圖、遙控與 RViz2..."
    
    # 建立會話，第一個分頁命名為 SLAM
    tmux new-session -d -s "$SESSION_NAME" -n "SLAM"
    
    # 1. 啟動底盤 (左上角) - 寫入當前活動的 pane 0
    tmux send-keys -t "$SESSION_NAME" "$DOCKER_EXEC bash -lc '$ROS2_SETUP && export BASE_TYPE=NanoRobot && ros2 launch base_control_ros2 00_base_control.launch.py'" C-m
    
    # 左右分割：右側 (新分割出的活動 pane 1)
    tmux split-window -h -t "$SESSION_NAME"
    # 右上角: SLAM 建圖
    tmux send-keys -t "$SESSION_NAME" "$DOCKER_EXEC bash -lc '$ROS2_SETUP && ros2 launch wheeltec_slam_toolbox playrobot_online_async_launch.py'" C-m
    
    # 選擇左側窗格 (索引 0)
    tmux select-pane -t 0
    # 上下分割左側：左下角 (新分割出的活動 pane 1，原右側變為 2)
    tmux split-window -v -t "$SESSION_NAME"
    # 左下角: 雷達
    tmux send-keys -t "$SESSION_NAME" "$DOCKER_EXEC bash -lc '$ROS2_SETUP && ros2 launch sllidar_ros2 sllidar_a2m12_launch.py serial_port:=/dev/sllidar_a2m12'" C-m
    
    # 選擇右側右上窗格 (此時索引已變為 2)
    tmux select-pane -t 2
    # 上下分割右側：右下角 (新分割出的活動 pane 3)
    tmux split-window -v -t "$SESSION_NAME"
    # 右下角: 鍵盤遙控
    tmux send-keys -t "$SESSION_NAME" "$DOCKER_EXEC bash -lc '$ROS2_SETUP && ros2 run wheeltec_robot_keyboard wheeltec_keyboard'" C-m
    
    # 2. 新開一個 tmux 視窗分頁 (Window 1) 來單獨執行 RViz2 (避免終端畫面太亂)
    tmux new-window -t "$SESSION_NAME" -n "RViz2"
    tmux send-keys -t "$SESSION_NAME:1" "$DOCKER_EXEC bash -lc '$ROS2_SETUP && export DISPLAY=:0 && rviz2 -d /workspaces/isaac_ros-dev/wheeltec_slam_toolbox.rviz'" C-m
    
    # 回到第一個分頁並選取鍵盤控制格 (此時索引為 3)，方便直接操作
    tmux select-window -t "$SESSION_NAME:0"
    tmux select-pane -t 3
    tmux attach-session -t "$SESSION_NAME"
    exit 0
fi

# ==================== 預設模式 3: web_all ====================
if [ "$1" == "web_all" ]; then
    echo "🚀 正在以 [web_all] 模式啟動底盤、雷達、建圖、網頁遙控與 RViz2..."
    
    # 建立會話，第一個分頁命名為 SLAM
    tmux new-session -d -s "$SESSION_NAME" -n "SLAM"
    
    # 1. 啟動底盤 (左上角) - 寫入當前活動的 pane 0
    tmux send-keys -t "$SESSION_NAME" "$DOCKER_EXEC bash -lc '$ROS2_SETUP && export BASE_TYPE=NanoRobot && ros2 launch base_control_ros2 00_base_control.launch.py'" C-m
    
    # 左右分割：右側 (新分割出的活動 pane 1)
    tmux split-window -h -t "$SESSION_NAME"
    # 右上角: SLAM 建圖
    tmux send-keys -t "$SESSION_NAME" "$DOCKER_EXEC bash -lc '$ROS2_SETUP && ros2 launch wheeltec_slam_toolbox playrobot_online_async_launch.py'" C-m
    
    # 選擇左側窗格 (索引 0)
    tmux select-pane -t 0
    # 上下分割左側：左下角 (新分割出的活動 pane 1)
    tmux split-window -v -t "$SESSION_NAME"
    # 左下角: 雷達
    tmux send-keys -t "$SESSION_NAME" "$DOCKER_EXEC bash -lc '$ROS2_SETUP && ros2 launch sllidar_ros2 sllidar_a2m12_launch.py serial_port:=/dev/sllidar_a2m12'" C-m
    
    # 選擇右側右上窗格 (此時索引已變為 2)
    tmux select-pane -t 2
    # 上下分割右側：右下角 (新分割出的活動 pane 3)
    tmux split-window -v -t "$SESSION_NAME"
    # 右下角: 網頁遙控
    tmux send-keys -t "$SESSION_NAME" "$DOCKER_EXEC bash -lc '$ROS2_SETUP && ros2 launch wheeltec_web_teleop web_teleop.launch.py'" C-m
    
    # 2. 新開一個 tmux 視窗分頁 (Window 1) 來單獨執行 RViz2
    tmux new-window -t "$SESSION_NAME" -n "RViz2"
    tmux send-keys -t "$SESSION_NAME:1" "$DOCKER_EXEC bash -lc '$ROS2_SETUP && export DISPLAY=:0 && rviz2 -d /workspaces/isaac_ros-dev/wheeltec_slam_toolbox.rviz'" C-m
    
    # 回到第一個分頁並選取網頁遙控窗格 (此時索引為 3)
    tmux select-window -t "$SESSION_NAME:0"
    tmux select-pane -t 3
    tmux attach-session -t "$SESSION_NAME"
    exit 0
fi

# ==================== 自訂組合模式 ====================
echo "🚀 正在解析自訂模組清單: $@"

commands=()
for arg in "$@"; do
    case "$arg" in
        chassis)
            commands+=("export BASE_TYPE=NanoRobot && ros2 launch base_control_ros2 00_base_control.launch.py")
            ;;
        lidar)
            commands+=("ros2 launch sllidar_ros2 sllidar_a2m12_launch.py serial_port:=/dev/sllidar_a2m12")
            ;;
        slam)
            commands+=("ros2 launch wheeltec_slam_toolbox playrobot_online_async_launch.py")
            ;;
        keyboard)
            commands+=("ros2 run wheeltec_robot_keyboard wheeltec_keyboard")
            ;;
        web)
            commands+=("ros2 launch wheeltec_web_teleop web_teleop.launch.py")
            ;;
        rviz|rviz2)
            commands+=("export DISPLAY=:0 && rviz2 -d /workspaces/isaac_ros-dev/wheeltec_slam_toolbox.rviz")
            ;;
        *)
            echo "⚠️ 未知模組: $arg (將被忽略)"
            ;;
    esac
done

num_cmds=${#commands[@]}
if [ "$num_cmds" -eq 0 ]; then
    echo "❌ 沒有指定任何有效的模組項目！"
    exit 1
fi

# 建立會話
tmux new-session -d -s "$SESSION_NAME" -n "ROS2_Custom"

for ((i=0; i<num_cmds; i++)); do
    cmd="${commands[i]}"
    docker_run_cmd="$DOCKER_EXEC bash -lc '$ROS2_SETUP && $cmd'"
    
    if [ "$i" -eq 0 ]; then
        # 第一個窗格
        tmux send-keys -t "$SESSION_NAME:0.0" "$docker_run_cmd" C-m
    else
        # 動態分割窗格 (奇數水平分割，偶數垂直分割)
        if [ $((i % 2)) -eq 1 ]; then
            tmux split-window -h -t "$SESSION_NAME:0"
        else
            tmux split-window -v -t "$SESSION_NAME:0"
        fi
        # 取得剛被分割出來的最後一個窗格索引並寫入指令
        last_pane_idx=$(tmux list-panes -t "$SESSION_NAME:0" | wc -l)
        last_pane_idx=$((last_pane_idx - 1))
        tmux send-keys -t "$SESSION_NAME:0.$last_pane_idx" "$docker_run_cmd" C-m
    fi
done

# 重新佈局窗格並附著會話
tmux select-layout -t "$SESSION_NAME:0" tiled
tmux attach-session -t "$SESSION_NAME"
