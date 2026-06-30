# 1. 基本變數設定
ROS_DOMAIN_ID_VAL="55"
CONTAINER_DISPLAY=":0"
DOCKER_EXEC="docker exec -it"
CONTAINER_NAME="isaac_ros_dev_container"

# 2. 決定你要執行的指令（可以隨時切換這兩行）
COMMAND="colcon build --packages-select wheeltec_web_teleop --symlink-install"
# COMMAND="bash" 

# 3. 核心邏輯：將 ROS 2 環境設定包裝成一個啟動檔
# 使用 -e 注入環境變數，並透過 bash 載入環境後執行特定指令
$DOCKER_EXEC \
  -e ROS_DOMAIN_ID="${ROS_DOMAIN_ID_VAL}" \
  -e DISPLAY="${CONTAINER_DISPLAY}" \
  $CONTAINER_NAME \
  bash --rcfile <(echo "source /opt/ros/jazzy/setup.bash && source /workspaces/isaac_ros-dev/install/setup.bash") -c "${COMMAND}"