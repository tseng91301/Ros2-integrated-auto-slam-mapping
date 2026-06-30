#!/usr/bin/env bash
# ros2_tmux_launcher.sh
# 使用 tmux 在 Docker 容器內多視窗啟動 ROS 2 常用節點

SESSION_NAME="ros2_dev"

# 預設 GUI 顯示器位置 (若連線失敗，可視情況修改為 :0、:1 或 :1001)
CONTAINER_DISPLAY=":0"

# 預設 ROS_DOMAIN_ID
ROS_DOMAIN_ID_VAL="55"

# 取得腳本所在的目錄 (絕對路徑)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Helper function to read parameters from robot_params.yaml
get_yaml_param() {
    python3 -c "import yaml; print(yaml.safe_load(open('${SCRIPT_DIR}/robot_params.yaml'))$1)" 2>/dev/null
}

CHASSIS_PORT=$(get_yaml_param "['robot']['chassis_port']")
LIDAR_PORT=$(get_yaml_param "['robot']['lidar_port']")
SIM_WORLD_PATH=$(get_yaml_param "['simulation']['world_path']")
IS_SIM=$(get_yaml_param "['simulation']['is_sim']")

# Fallbacks if YAML reading fails
[ -z "$CHASSIS_PORT" ] && CHASSIS_PORT="/dev/playrobot_base"
[ -z "$LIDAR_PORT" ] && LIDAR_PORT="/dev/sllidar_a2m12"
[ -z "$SIM_WORLD_PATH" ] && SIM_WORLD_PATH="/opt/ros/jazzy/share/nav2_minimal_tb3_sim/worlds/tb3_sandbox.sdf.xacro"
[ -z "$IS_SIM" ] && IS_SIM="false"

# Generate the dynamic Nav2 parameter file with values from robot_params.yaml
python3 -c "
import yaml, os
try:
    with open('${SCRIPT_DIR}/robot_params.yaml') as f:
        config = yaml.safe_load(f)
    with open('${SCRIPT_DIR}/src/wheeltec_robot_nav2/param/wheeltec_param/nav2_params_with_slam.yaml') as f:
        params = yaml.safe_load(f)
    
    radius = config.get('robot', {}).get('radius', 0.22)
    inflation = config.get('navigation', {}).get('inflation_radius', 0.70)
    
    def update_nested(d):
        for k, v in d.items():
            if isinstance(v, dict):
                update_nested(v)
            elif k == 'robot_radius':
                d[k] = radius
            elif k == 'inflation_radius':
                d[k] = inflation
                
    update_nested(params)
    
    with open('/tmp/nav2_params_with_slam_generated.yaml', 'w') as f:
        yaml.safe_dump(params, f)
except Exception as e:
    print('Failed to generate modified nav2 params:', e)
" 2>/dev/null


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
    echo "🐳 ROS 2 Tmux All-in-One Launcher"
    echo "Usage: $0 [mode | custom modules list] [--domain <ID>] [-kill]"
    echo ""
    echo "💡 Preset Modes:"
    echo "  $0 teleop       - Launch chassis controller + keyboard teleop (dual panes)"
    echo "  $0 slam_all     - Launch chassis + LIDAR + SLAM mapping + keyboard teleop + RViz2 (multi-panes/windows)"
    echo "  $0 web_all      - Launch chassis + LIDAR + SLAM mapping + web teleop + auto explorer + RViz2 (one-click physical deployment)"
    echo "  $0 explore      - Same as web_all"
    echo "  $0 sim_web_all  - Launch Gazebo simulator + SLAM mapping + web teleop + auto explorer (one-click simulation)"
    echo "  $0 sim_explore  - Same as sim_web_all"
    echo "  $0 sim_keyboard - Launch Gazebo simulator + SLAM mapping + keyboard teleop + RViz2 (simulation with keyboard control)"
    echo "  $0 terminal     - Launch a raw ROS 2 Docker interactive terminal with environment sourced (use -kill to clear processes)"
    echo ""
    echo "⚙️ Options:"
    echo "  --domain / --domain-id <ID>  - Specify a custom ROS_DOMAIN_ID (default: 55)"
    echo "  -kill / --kill               - Force kill previous tmux sessions and background processes before launching"
    echo ""
    echo "🛠️ Custom Modules:"
    echo "  $0 <module1> [module2] [module3] ..."
    echo "  Supported custom modules:"
    echo "    chassis       - Chassis serial communication control"
    echo "    lidar         - RPLIDAR A2M12 LIDAR driver"
    echo "    slam          - SLAM Toolbox asynchronous mapping"
    echo "    keyboard      - Keyboard teleop node"
    echo "    web           - Web teleop & real-time mapping server"
    echo "    explorer      - Frontier-based autonomous explorer node"
    echo "    rviz / rviz2  - RViz2 visualization tool (loads SLAM config)"
    echo "    rosbag        - Rosbag2 recording tool (records mapping data)"
    echo ""
    echo "  Custom Examples:"
    echo "    $0 chassis lidar        (Launch chassis and LIDAR only)"
    echo "    $0 chassis keyboard rviz (Launch chassis, keyboard, and RViz2)"
    echo "    $0 chassis lidar slam web (Launch chassis, LIDAR, SLAM, and Web Server)"
    echo "    $0 chassis lidar slam rviz rosbag (Launch mapping and record data)"
    echo ""
    exit 0
}

if [ "$#" -lt 1 ] || [ "$1" == "-h" ] || [ "$1" == "--help" ]; then
    show_help
fi

# 1. 確保 Docker 容器正在運行，若未運行則自動啟動
if ! docker ps --format '{{.Names}}' | grep -q "^isaac_ros_dev_container$"; then
    echo "🔄 偵測到 isaac_ros_dev_container 容器未啟動，正在為您啟動容器..."
    if [ -f "${SCRIPT_DIR}/start_container.sh" ]; then
        chmod +x "${SCRIPT_DIR}/start_container.sh"
        "${SCRIPT_DIR}/start_container.sh"
        sleep 2
    else
        echo "❌ 錯誤: 找不到 ${SCRIPT_DIR}/start_container.sh，無法自動啟動容器！"
        exit 1
    fi
fi

# 2. 自動執行裝置掛載
if [ "$IS_SIM" != "true" ] && [ "$IS_SIM" != "True" ]; then
    if [ -f "${SCRIPT_DIR}/attach_devices.sh" ]; then
        echo "🔄 正在自動掛載硬體裝置..."
        chmod +x "${SCRIPT_DIR}/attach_devices.sh"
        "${SCRIPT_DIR}/attach_devices.sh" "$CHASSIS_PORT" "$LIDAR_PORT" || true
    else
        echo "⚠️ 警告: 找不到 ${SCRIPT_DIR}/attach_devices.sh，跳過裝置掛載。"
    fi
else
    echo "ℹ️ 模擬模式已啟用，跳過硬體裝置掛載。"
fi

# 檢查是否需要啟動 GUI 或可能呼叫 GPU/EGL 的交互終端，在 Host 本機端執行 xhost 授權 (避免在容器內報錯)
if [[ " $@ " =~ " rviz " ]] || [[ " $@ " =~ " rviz2 " ]] || [[ " $@ " =~ " slam_all " ]] || [[ " $@ " =~ " sim_web_all " ]] || [[ " $@ " =~ " sim_explore " ]] || [[ " $@ " =~ " sim_keyboard " ]] || [[ " $@ " =~ " terminal " ]]; then
    echo "🖥️ 正在 Host 端授權 X11 顯示存取權 (xhost +local:docker)..."
    
    # 確保在 ssh/tmux 等無 display 環境變數的終端下也能正確找到 X 伺服器進行授權
    local_disp="${DISPLAY:-:0}"
    local_auth="${XAUTHORITY:-}"
    if [ -z "$local_auth" ]; then
        if [ -f "/run/user/1000/gdm/Xauthority" ]; then
            local_auth="/run/user/1000/gdm/Xauthority"
        elif [ -f "$HOME/.Xauthority" ]; then
            local_auth="$HOME/.Xauthority"
        fi
    fi
    
    DISPLAY="$local_disp" XAUTHORITY="$local_auth" xhost +local:docker 2>/dev/null || true
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
    echo "🧹 正在清理容器內可能殘留的舊節點進程..."
    
    # 1. 結束系統安裝與工作空間的所有 ROS 2 C++/Python 進程 (比對安裝與環境路徑)
    docker exec isaac_ros_dev_container pkill -9 -f /opt/ros/ 2>/dev/null || true
    docker exec isaac_ros_dev_container pkill -9 -f /workspaces/isaac_ros-dev/install/ 2>/dev/null || true

    # 2. 清理常見的組件容器、狀態發布器與相機驅動節點 (防止 ZED / Realsense 鎖定裝置)
    docker exec isaac_ros_dev_container pkill -9 -f [c]omponent_container 2>/dev/null || true
    docker exec isaac_ros_dev_container pkill -9 -f [r]obot_state_publisher 2>/dev/null || true
    docker exec isaac_ros_dev_container pkill -9 -f [z]ed 2>/dev/null || true
    docker exec isaac_ros_dev_container pkill -9 -f [r]ealsense 2>/dev/null || true

    # 3. 清理模擬器、遙控器與通訊伺服器
    docker exec isaac_ros_dev_container pkill -9 -f [w]heeltec 2>/dev/null || true
    docker exec isaac_ros_dev_container pkill -9 -f [w]eb_server 2>/dev/null || true
    docker exec isaac_ros_dev_container pkill -9 -f [g]z 2>/dev/null || true
    docker exec isaac_ros_dev_container pkill -9 -f [r]uby 2>/dev/null || true
    docker exec isaac_ros_dev_container pkill -9 -f [t]ornado 2>/dev/null || true
    docker exec isaac_ros_dev_container pkill -9 rviz2 2>/dev/null || true
    
    sleep 1
else
    echo "ℹ️ 跳過清理舊進程與會話 (若要強制清理，請加上 -kill 參數)"
fi

# 共用指令前綴
DOCKER_EXEC="docker exec -it isaac_ros_dev_container"
ROS2_SETUP="export ROS_DOMAIN_ID=${ROS_DOMAIN_ID_VAL} && source /opt/ros/jazzy/setup.bash && source /workspaces/isaac_ros-dev/install/setup.bash"

# Check if simulation mode is configured in YAML and adjust preset accordingly
if [ "$IS_SIM" == "true" ] || [ "$IS_SIM" == "True" ]; then
    if [ "$1" == "teleop" ]; then
        echo "⚠️ 偵測到 robot_params.yaml 已啟用模擬模式，自動切換至 sim_keyboard 模式..."
        set -- "sim_keyboard" "${@:2}"
    elif [ "$1" == "slam_all" ]; then
        echo "⚠️ 偵測到 robot_params.yaml 已啟用模擬模式，自動切換至 sim_keyboard 模式..."
        set -- "sim_keyboard" "${@:2}"
    elif [ "$1" == "web_all" ] || [ "$1" == "explore" ] || [ "$1" == "explorer" ]; then
        echo "⚠️ 偵測到 robot_params.yaml 已啟用模擬模式，自動切換至 sim_web_all 模式..."
        set -- "sim_web_all" "${@:2}"
    fi
else
    if [ "$1" == "sim_keyboard" ]; then
        echo "⚠️ 偵測到 robot_params.yaml 未啟用模擬模式，自動切換至 teleop 模式..."
        set -- "teleop" "${@:2}"
    elif [ "$1" == "sim_web_all" ] || [ "$1" == "sim_explore" ] || [ "$1" == "sim_explorer" ]; then
        echo "⚠️ 偵測到 robot_params.yaml 未啟用模擬模式，自動切換至 web_all 模式..."
        set -- "web_all" "${@:2}"
    fi
fi

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
    tmux send-keys -t "$SESSION_NAME" "$DOCKER_EXEC bash -lc '$ROS2_SETUP && ros2 launch sllidar_ros2 sllidar_a2m12_launch.py serial_port:=\"$LIDAR_PORT\"'" C-m
    
    # 選擇右側右上窗格 (此時索引已變為 2)
    tmux select-pane -t 2
    # 上下分割右側：右下角 (新分割出的活動 pane 3)
    tmux split-window -v -t "$SESSION_NAME"
    # 右下角: 鍵盤遙控
    tmux send-keys -t "$SESSION_NAME" "$DOCKER_EXEC bash -lc '$ROS2_SETUP && ros2 run wheeltec_robot_keyboard wheeltec_keyboard'" C-m
    
    # 2. 新開一個 tmux 視窗分頁 (Window 1) 來單獨執行 RViz2 (避免終端畫面太亂)
    tmux new-window -t "$SESSION_NAME" -n "RViz2"
    tmux send-keys -t "$SESSION_NAME:1" "$DOCKER_EXEC bash -lc '$ROS2_SETUP && export DISPLAY=${CONTAINER_DISPLAY} && rviz2 -d /workspaces/isaac_ros-dev/wheeltec_slam_toolbox.rviz'" C-m
    
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
    tmux send-keys -t "$SESSION_NAME" "$DOCKER_EXEC bash -lc '$ROS2_SETUP && ros2 launch sllidar_ros2 sllidar_a2m12_launch.py serial_port:=\"$LIDAR_PORT\"'" C-m
    
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
    tmux send-keys -t "$SESSION_NAME:1" "$DOCKER_EXEC bash -lc '$ROS2_SETUP && export DISPLAY=${CONTAINER_DISPLAY} && rviz2 -d /workspaces/isaac_ros-dev/wheeltec_slam_toolbox.rviz'" C-m
    
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
    tmux send-keys -t "$SESSION_NAME" "$DOCKER_EXEC bash -lc '$ROS2_SETUP && export DISPLAY=${CONTAINER_DISPLAY} && ros2 launch nav2_bringup tb3_simulation_launch.py slam:=True use_rviz:=False headless:=True params_file:=/tmp/nav2_params_with_slam_generated.yaml world:=\"$SIM_WORLD_PATH\"'" C-m
    
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
    tmux send-keys -t "$SESSION_NAME" "$DOCKER_EXEC bash -lc '$ROS2_SETUP && export DISPLAY=${CONTAINER_DISPLAY} && ros2 launch nav2_bringup tb3_simulation_launch.py slam:=True use_rviz:=True headless:=False rviz_config:=/workspaces/isaac_ros-dev/wheeltec_slam_toolbox.rviz params_file:=/tmp/nav2_params_with_slam_generated.yaml world:=\"$SIM_WORLD_PATH\"'" C-m
    
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
        tmux send-keys -t "$SESSION_NAME:$WINDOW_NAME" "$DOCKER_EXEC bash -lc '$ROS2_SETUP && export DISPLAY=${CONTAINER_DISPLAY} && exec bash'" C-m
        tmux select-window -t "$SESSION_NAME:$WINDOW_NAME"
    else
        # 建立全新會話
        WINDOW_NAME="Terminal-1"
        tmux new-session -d -s "$SESSION_NAME" -n "$WINDOW_NAME"
        tmux send-keys -t "$SESSION_NAME:0.0" "$DOCKER_EXEC bash -lc '$ROS2_SETUP && export DISPLAY=${CONTAINER_DISPLAY} && exec bash'" C-m
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
            commands+=("ros2 launch sllidar_ros2 sllidar_a2m12_launch.py serial_port:=\"$LIDAR_PORT\"")
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
            commands+=("export DISPLAY=${CONTAINER_DISPLAY} && rviz2 -d /workspaces/isaac_ros-dev/wheeltec_slam_toolbox.rviz")
            ;;
        rosbag)
            commands+=("mkdir -p /workspaces/isaac_ros-dev/rosbags && ros2 bag record /scan /odom /odom_combined /tf /tf_static /cmd_vel /map -o /workspaces/isaac_ros-dev/rosbags/rosbag_\$(date +%Y%m%d_%H%M%S)")
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
