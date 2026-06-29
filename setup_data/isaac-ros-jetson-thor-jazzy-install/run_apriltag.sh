#!/usr/bin/env bash
set -euo pipefail

ISAAC_ROS_WS="${ISAAC_ROS_WS:-$HOME/workspaces/isaac_ros-dev}"
ISAAC_ROS_CONTAINER_NAME="${ISAAC_ROS_CONTAINER_NAME:-isaac_ros_dev_container}"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
LAUNCH_FILE_SRC="${SCRIPT_DIR}/apriltag_test.launch.py"
LAUNCH_FILE_DST="${ISAAC_ROS_WS}/apriltag_test.launch.py"

log() { printf '\n[%s] %s\n' "$(date '+%F %T')" "$*"; }
die() { printf '\n[ERROR] %s\n' "$*" >&2; exit 1; }

command -v docker >/dev/null 2>&1 || die "docker not found"
[[ -f "$LAUNCH_FILE_SRC" ]] || die "missing launch file: $LAUNCH_FILE_SRC"
[[ -d "$ISAAC_ROS_WS" ]] || die "missing workspace: $ISAAC_ROS_WS"

docker ps --format '{{.Names}}' | grep -qx "$ISAAC_ROS_CONTAINER_NAME" || die "container not running: $ISAAC_ROS_CONTAINER_NAME"
[[ -e /dev/video0 ]] || die "/dev/video0 not found on host"

log "Copying launch file into workspace"
cp "$LAUNCH_FILE_SRC" "$LAUNCH_FILE_DST"
docker cp "$LAUNCH_FILE_DST" "$ISAAC_ROS_CONTAINER_NAME:/workspaces/isaac_ros-dev/apriltag_test.launch.py"

log "Stopping previous camera/AprilTag processes if present"
docker exec "$ISAAC_ROS_CONTAINER_NAME" bash -lc 'pkill -f "v4l2_camera_node|apriltag_container|component_container_mt|apriltag_test.launch.py" || true'

log "Starting camera + AprilTag pipeline"
docker exec "$ISAAC_ROS_CONTAINER_NAME" bash -lc 'source /opt/ros/jazzy/setup.bash && ros2 launch /workspaces/isaac_ros-dev/apriltag_test.launch.py'
