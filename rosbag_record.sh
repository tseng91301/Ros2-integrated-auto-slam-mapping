#!/bin/bash

# Setup colors for printing
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTAINER_NAME="isaac_ros_dev_container"
DEFAULT_DOMAIN_ID=55
RECORD_ALL=false
RECORD_CAMERA=false
CUSTOM_NAME=""
DOMAIN_ID=$DEFAULT_DOMAIN_ID

# Default topics to record for mapping exploration
DEFAULT_TOPICS=(
    "/scan"
    "/odom"
    "/odom_combined"
    "/tf"
    "/tf_static"
    "/cmd_vel"
    "/map"
)

# Camera topics (recorded only if --camera is enabled)
CAMERA_TOPICS=(
    "/zed/zed_node/rgb/image_rect_color/compressed"
    "/zed/zed_node/left/image_rect_color/compressed"
    "/zed/zed_node/depth/depth_registered"
)

# Help message
show_help() {
    echo -e "🎥 ${GREEN}ROS 2 Rosbag 記錄工具 (Host 端輔助腳本)${NC}"
    echo "用法: $0 [選項]"
    echo ""
    echo "選項:"
    echo "  -h, --help            顯示本說明文件"
    echo "  -a, --all             錄製所有活躍中的主題 (Topics)"
    echo "  -c, --camera          除了預設主題外，加錄相機影像與深度數據 (壓縮格式)"
    echo "  -o, --output <名稱>   指定錄製資料夾名稱 (預設: rosbag_YYYYMMDD_HHMMSS)"
    echo "  --domain <ID>         指定 ROS_DOMAIN_ID (預設: 55)"
    echo ""
    echo "預設錄製的主題 (適用於建圖與探索):"
    for topic in "${DEFAULT_TOPICS[@]}"; do
        echo "  - $topic"
    done
    echo ""
    exit 0
}

# Parse command line arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        -h|--help) show_help ;;
        -a|--all) RECORD_ALL=true; shift ;;
        -c|--camera) RECORD_CAMERA=true; shift ;;
        -o|--output) CUSTOM_NAME="$2"; shift 2 ;;
        --domain) DOMAIN_ID="$2"; shift 2 ;;
        *) echo -e "${RED}未知參數: $1${NC}"; show_help ;;
    esac
done

# Ensure the container is running
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo -e "${RED}❌ 錯誤: 容器 ${CONTAINER_NAME} 未在運行！${NC}"
    echo "請先使用 ./ros2_tmux_launcher.sh 啟動機器人或模擬器。"
    exit 1
fi

# Prepare output directory
HOST_BAGS_DIR="${SCRIPT_DIR}/rosbags"
CONTAINER_BAGS_DIR="/workspaces/isaac_ros-dev/rosbags"
mkdir -p "$HOST_BAGS_DIR"

# Generate bag name/folder name
if [ -n "$CUSTOM_NAME" ]; then
    BAG_NAME="$CUSTOM_NAME"
else
    TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
    BAG_NAME="rosbag_${TIMESTAMP}"
fi

BAG_PATH="${CONTAINER_BAGS_DIR}/${BAG_NAME}"

# Build recording topics string
CMD_TOPICS=""
if [ "$RECORD_ALL" = true ]; then
    CMD_TOPICS="-a"
    echo -e "${YELLOW}🔔 警告: 將錄製所有活躍的主題，這可能會產生極大的檔案大小！${NC}"
else
    TOPICS_TO_RECORD=("${DEFAULT_TOPICS[@]}")
    if [ "$RECORD_CAMERA" = true ]; then
        TOPICS_TO_RECORD+=("${CAMERA_TOPICS[@]}")
        echo -e "${YELLOW}📸 已包含相機壓縮影像與深度主題進行錄製${NC}"
    fi
    CMD_TOPICS="${TOPICS_TO_RECORD[*]}"
fi

echo -e "${GREEN}🚀 開始在容器中啟動 ros2 bag record...${NC}"
echo -e "📂 儲存路徑 (Host): ${YELLOW}${HOST_BAGS_DIR}/${BAG_NAME}${NC}"
echo -e "🌐 ROS_DOMAIN_ID: ${YELLOW}${DOMAIN_ID}${NC}"
echo -e "📝 錄製主題: ${YELLOW}${CMD_TOPICS}${NC}"
echo -e "🛑 欲停止錄製，請在下方終端機中按下 ${RED}Ctrl + C${NC}"
echo ""

# Execute record command in container
# Using interactive exec so user can view progress and stop with Ctrl+C
docker exec -it "$CONTAINER_NAME" bash -lc "
    export ROS_DOMAIN_ID=$DOMAIN_ID
    source /opt/ros/jazzy/setup.bash
    source /workspaces/isaac_ros-dev/install/setup.bash
    ros2 bag record $CMD_TOPICS -o $BAG_PATH
"
