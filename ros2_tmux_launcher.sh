#!/usr/bin/env bash
# ros2_tmux_launcher.sh
# 使用 tmux 在 Docker 容器內多視窗啟動 ROS 2 常用節點

SESSION_NAME="ros2_dev"

# 預設 ROS_DOMAIN_ID
ROS_DOMAIN_ID_VAL="55"

# 預設模擬器地圖路徑 (Gazebo Simulation World Path)
# 預設使用優化後免連網下載 Fuel 資源的本地 Warehouse 地圖
# 若要切換成系統預設的 Sandbox 地圖，可改為空值，或指定 "/opt/ros/jazzy/share/nav2_minimal_tb3_sim/worlds/tb3_sandbox.sdf.xacro"
# SIM_WORLD_PATH="/workspaces/isaac_ros-dev/src/auto_explorer/config/warehouse_local.sdf"
SIM_WORLD_PATH="/opt/ros/jazzy/share/nav2_minimal_tb3_sim/worlds/tb3_sandbox.sdf.xacro"

# 解析自定義參數與選項
FORCE_KILL="false"
NEW_ARGS=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --domain|--domain-id)
            if [ -n "$2" ] && [[ "$2" =~ ^[0-9]+$ ]]; then
                ROS_DOMAIN_ID_VAL="$2"
                shift 2
            else
                echo "❌ 錯誤: --domain / --domain-id 後需指定一個數字！"
                exit 1
            fi
            ;;
        -kill|--kill)
            FORCE_KILL="true"
            shift 1
            ;;
        *)
            NEW_ARGS+=("$1")
            shift 1
            ;;
    esac
done
# 重新將過濾掉 --domain 的參數設定為 $@
set -- "${NEW_ARGS[@]}"

# 顯示說明
show_help() {
    echo "🐳 ROS 2 tmux All-in-One 啟動工具"
    echo "使用方法: $0 [模式 | 模組清單] [--domain <ID>] [-kill]"
    echo ""
    echo "💡 預設預載組合模式 (Presets):"
    echo "  $0 teleop       - 啟動底盤控制器 + 鍵盤遙控 (雙分割畫面)"
    echo "  $0 slam_all     - 啟動底盤 + 雷達 + SLAM 建圖 + 鍵盤遙控 + RViz2 (多視窗格與分頁)"
    echo "  $0 web_all      - 啟動底盤 + 雷達 + SLAM 建圖 + 網頁遙控 + 自主探索 + RViz2 (一鍵部署實體建圖、遙控與探索)"
    echo "  $0 explore      - 同 web_all"
    echo "  $0 sim_web_all  - 啟動 Gazebo 模擬器 + SLAM 建圖 + 網頁遙控 + 自主探索 (一鍵部署模擬建圖與探索)"
    echo "  $0 sim_explore  - 同 sim_web_all"
    echo "  $0 sim_keyboard - 啟動 Gazebo 模擬器 + SLAM 建圖 + 鍵盤遙控 + RViz2 (電腦鍵盤控制並在螢幕上顯示)"
    echo "  $0 terminal     - 單純開啟一個 source 好環境的 ROS 2 Docker 互動終端機 (加 -kill 強制清理舊進程)"
    echo ""
    echo "⚙️ 全局參數選項 (Options):"
    echo "  --domain / --domain-id <ID>  - 指定自定義的 ROS_DOMAIN_ID (預設為 30)"
    echo "  -kill / --kill               - 啟動前強制清理舊的 tmux 會話與背景進程"
    echo ""
    echo "🛠️ 自訂模組組合 (Custom Modules):"
    echo "  $0 <模組1> [模組2] [模組3] ..."
    echo "  支援的自訂模組參數:"
    echo "    chassis       - 底盤通訊控制"
    echo "    lidar         - RPLIDAR A2M12 雷達驅動"
    echo "    slam          - SLAM Toolbox 異步建圖"
    echo "    keyboard      - 鍵盤遙控節點"
    echo "    web           - 網頁遙控與實時建圖伺服器"
    echo "    explorer      - 邊界自主探索節點 (Frontier Auto Explorer)"
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

# 1. 確保 Docker 容器正在運行，若未運行則自動啟動
if ! docker ps --format '{{.Names}}' | grep -q "^isaac_ros_dev_container$"; then
    echo "🔄 偵測到 isaac_ros_dev_container 容器未啟動，正在為您啟動容器..."
    if [ -f "./start_container.sh" ]; then
        chmod +x ./start_container.sh
        ./start_container.sh
        sleep 2
    else
        echo "❌ 錯誤: 找不到 ./start_container.sh，無法自動啟動容器！"
        exit 1
    fi
fi

# 2. 自動執行裝置掛載
if [ -f "./attach_devices.sh" ]; then
    echo "🔄 正在自動掛載硬體裝置..."
    chmod +x ./attach_devices.sh
    ./attach_devices.sh /dev/playrobot_base /dev/sllidar_a2m12 || true
else
    echo "⚠️ 警告: 找不到 ./attach_devices.sh，跳過裝置掛載。"
fi

# 檢查是否需要啟動 GUI，如果是，先在 Host 本機端執行 xhost 授權 (避免在容器內報錯)
if [[ " $@ " =~ " rviz " ]] || [[ " $@ " =~ " rviz2 " ]] || [[ " $@ " =~ " slam_all " ]] || [[ " $@ " =~ " sim_web_all " ]] || [[ " $@ " =~ " sim_explore " ]] || [[ " $@ " =~ " sim_keyboard " ]]; then
    echo "🖥️ 正在 Host 端授權 X11 顯示存取權 (xhost +local:docker)..."
    xhost +local:docker 2>/dev/null || true
fi

# 3. 判斷是否需要清理先前還在運作的 tmux 會話與容器殘留進程
# (terminal 模式預設不清理，除非指定了 -kill 參數)
SHOULD_CLEAN="true"
if [ "$1" == "terminal" ]; then
    SHOULD_CLEAN="false"
fi
if [ "$FORCE_KILL" == "true" ]; then
    SHOULD_CLEAN="true"
fi

if [ "$SHOULD_CLEAN" == "true" ]; then
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
    docker exec isaac_ros_dev_container pkill -9 -f [g]z 2>/dev/null || true
    docker exec isaac_ros_dev_container pkill -9 -f [r]uby 2>/dev/null || true
    docker exec isaac_ros_dev_container pkill -9 rviz2 2>/dev/null || true
    sleep 1
else
    echo "ℹ️ 跳過清理舊進程與會話 (若要強制清理，請加上 -kill 參數)"
fi

# 共用指令前綴
DOCKER_EXEC="docker exec -it isaac_ros_dev_container"
ROS2_SETUP="export ROS_DOMAIN_ID=${ROS_DOMAIN_ID_VAL} && source /opt/ros/jazzy/setup.bash && source /workspaces/isaac_ros-dev/install/setup.bash"

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

# ==================== 預設模式 3.5: web_all / explore ====================
if [ "$1" == "web_all" ] || [ "$1" == "explore" ] || [ "$1" == "explorer" ]; then
    echo "🚀 正在以 [web_all / explore] 模式啟動底盤、雷達、建圖、網頁監控、自動探索與 RViz2..."
    
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
    # 右下角: 網頁遙控與伺服器
    tmux send-keys -t "$SESSION_NAME" "$DOCKER_EXEC bash -lc '$ROS2_SETUP && ros2 launch wheeltec_web_teleop web_teleop.launch.py'" C-m
    
    # 選擇網頁遙控窗格 (此時索引為 3)
    tmux select-pane -t 3
    # 上下分割右下角：右下偏下 (新分割出的活動 pane 4)
    tmux split-window -v -t "$SESSION_NAME"
    # 最右下角: 自動探索節點
    tmux send-keys -t "$SESSION_NAME" "$DOCKER_EXEC bash -lc '$ROS2_SETUP && ros2 launch auto_explorer auto_exploration.launch.py'" C-m
    
    # 2. 新開一個 tmux 視窗分頁 (Window 1) 來單獨執行 RViz2
    tmux new-window -t "$SESSION_NAME" -n "RViz2"
    tmux send-keys -t "$SESSION_NAME:1" "$DOCKER_EXEC bash -lc '$ROS2_SETUP && export DISPLAY=:0 && rviz2 -d /workspaces/isaac_ros-dev/wheeltec_slam_toolbox.rviz'" C-m
    
    # 回到第一個分頁並選取自動探索窗格 (此時索引為 4)
    tmux select-window -t "$SESSION_NAME:0"
    tmux select-pane -t 4
    tmux attach-session -t "$SESSION_NAME"
    exit 0
fi

# ==================== 預設模式 3.6: sim_web_all / sim_explore ====================
if [ "$1" == "sim_web_all" ] || [ "$1" == "sim_explore" ] || [ "$1" == "sim_explorer" ]; then
    echo "🚀 正在以 [sim_web_all / sim_explore] 模式啟動 Gazebo 模擬器、SLAM 建圖、網頁監控、自動探索與 RViz2..."
    
    # 建立會話，第一個分頁命名為 Simulation
    tmux new-session -d -s "$SESSION_NAME" -n "Simulation"
    
    # 1. 啟動 Gazebo 模擬器與 SLAM 項目 (use_rviz:=False)
    tmux send-keys -t "$SESSION_NAME" "$DOCKER_EXEC bash -lc '$ROS2_SETUP && export DISPLAY=:0 && ros2 launch nav2_bringup tb3_simulation_launch.py slam:=True use_rviz:=False headless:=False params_file:=/workspaces/isaac_ros-dev/src/auto_explorer/config/nav2_params_with_slam.yaml world:=\"$SIM_WORLD_PATH\"'" C-m
    
    # 左右分割：右側 (新分割出的活動 pane 1)
    tmux split-window -h -t "$SESSION_NAME"
    # 右上角: 網頁遙控與伺服器 (啟用 use_sim_time:=true)
    tmux send-keys -t "$SESSION_NAME" "$DOCKER_EXEC bash -lc '$ROS2_SETUP && ros2 launch wheeltec_web_teleop web_teleop.launch.py use_sim_time:=true'" C-m
    
    # 選擇右側窗格 (索引 1)
    tmux select-pane -t 1
    # 上下分割右側：右下角 (新分割出的活動 pane 2)
    tmux split-window -v -t "$SESSION_NAME"
    # 右下角: 自動探索節點 (啟用 use_sim_time:=true)
    tmux send-keys -t "$SESSION_NAME" "$DOCKER_EXEC bash -lc '$ROS2_SETUP && ros2 launch auto_explorer auto_exploration.launch.py use_sim_time:=true'" C-m
    
    # 回到第一個分頁並選取自動探索窗格 (索引 2)
    tmux select-window -t "$SESSION_NAME:0"
    tmux select-pane -t 2
    tmux attach-session -t "$SESSION_NAME"
    exit 0
fi

# ==================== 預設模式 3.8: sim_keyboard ====================
if [ "$1" == "sim_keyboard" ]; then
    echo "🚀 正在以 [sim_keyboard] 模式啟動 Gazebo 模擬器、SLAM 建圖、鍵盤遙控與 RViz2..."
    
    # 建立會話，第一個分頁命名為 Simulation
    tmux new-session -d -s "$SESSION_NAME" -n "Simulation"
    
    # 1. 啟動 Gazebo 模擬器與 SLAM 項目
    tmux send-keys -t "$SESSION_NAME" "$DOCKER_EXEC bash -lc '$ROS2_SETUP && export DISPLAY=:0 && ros2 launch nav2_bringup tb3_simulation_launch.py slam:=True use_rviz:=True headless:=False rviz_config:=/workspaces/isaac_ros-dev/wheeltec_slam_toolbox.rviz params_file:=/workspaces/isaac_ros-dev/src/auto_explorer/config/nav2_params_with_slam.yaml world:=\"$SIM_WORLD_PATH\"'" C-m
    
    # 左右分割：右側 (新分割出的活動 pane 1)
    tmux split-window -h -t "$SESSION_NAME"
    # 右側: 鍵盤遙控
    tmux send-keys -t "$SESSION_NAME" "$DOCKER_EXEC bash -lc '$ROS2_SETUP && ros2 run wheeltec_robot_keyboard wheeltec_keyboard --ros-args -p use_sim_time:=true'" C-m
    
    # 回到第一個分頁並選取鍵盤控制窗格 (索引 1)
    tmux select-window -t "$SESSION_NAME:0"
    tmux select-pane -t 1
    tmux attach-session -t "$SESSION_NAME"
    exit 0
fi

# ==================== 預設模式 4: terminal ====================
if [ "$1" == "terminal" ]; then
    echo "🚀 正在啟動包含 ROS 2 環境變數 (ROS_DOMAIN_ID=${ROS_DOMAIN_ID_VAL}) 的 Docker 互動終端機..."
    
    # 檢查會話是否已經存在
    if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
        echo "ℹ️ 偵測到已有運作中的 tmux 會話 '${SESSION_NAME}'，正在新增一個分頁..."
        # 尋找尚未被佔用的 Terminal-<ID> 視窗名稱
        ID=1
        while tmux list-windows -t "$SESSION_NAME" -F "#W" 2>/dev/null | grep -q "^Terminal-${ID}$"; do
            ID=$((ID + 1))
        done
        WINDOW_NAME="Terminal-${ID}"

        # 建立新視窗並啟動進入 Docker 的互動終端機
        tmux new-window -t "$SESSION_NAME" -n "$WINDOW_NAME"
        tmux send-keys -t "$SESSION_NAME:$WINDOW_NAME" "$DOCKER_EXEC bash -lc '$ROS2_SETUP && exec bash'" C-m
        tmux select-window -t "$SESSION_NAME:$WINDOW_NAME"
    else
        # 建立全新會話
        WINDOW_NAME="Terminal-1"
        tmux new-session -d -s "$SESSION_NAME" -n "$WINDOW_NAME"
        tmux send-keys -t "$SESSION_NAME:0.0" "$DOCKER_EXEC bash -lc '$ROS2_SETUP && exec bash'" C-m
    fi
    
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
        explorer)
            commands+=("ros2 launch auto_explorer auto_exploration.launch.py")
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
