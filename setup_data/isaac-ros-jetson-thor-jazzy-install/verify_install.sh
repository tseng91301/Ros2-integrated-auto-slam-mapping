#!/usr/bin/env bash
set -euo pipefail

ISAAC_ROS_WS="${ISAAC_ROS_WS:-$HOME/workspaces/isaac_ros-dev}"
ISAAC_ROS_CONTAINER_NAME="${ISAAC_ROS_CONTAINER_NAME:-isaac_ros_dev_container}"
VERIFY_TOPICS="${VERIFY_TOPICS:-1}"
VERIFY_DETECTION="${VERIFY_DETECTION:-0}"
TOPIC_TIMEOUT="${TOPIC_TIMEOUT:-10}"
DETECTION_TIMEOUT="${DETECTION_TIMEOUT:-15}"

log() { printf '\n[%s] %s\n' "$(date '+%F %T')" "$*"; }
warn() { printf '\n[WARN] %s\n' "$*" >&2; }
die() { printf '\n[ERROR] %s\n' "$*" >&2; exit 1; }

command -v docker >/dev/null 2>&1 || die "docker not found"
[[ -d "$ISAAC_ROS_WS" ]] || die "workspace not found: $ISAAC_ROS_WS"

docker ps --format '{{.Names}}' | grep -qx "$ISAAC_ROS_CONTAINER_NAME" || die "container not running: $ISAAC_ROS_CONTAINER_NAME"

container_exec() {
  docker exec "$ISAAC_ROS_CONTAINER_NAME" bash -lc "$*"
}

check_pkg() {
  local pkg="$1"
  container_exec "source /opt/ros/jazzy/setup.bash && ros2 pkg prefix ${pkg}" >/dev/null
  printf '  [ok] %s\n' "$pkg"
}

log "Checking core ROS / Isaac ROS packages"
for pkg in \
  isaac_ros_common \
  isaac_ros_examples \
  v4l2_camera \
  isaac_ros_apriltag; do
  check_pkg "$pkg"
done

log "Checking workspace files"
[[ -f "$ISAAC_ROS_WS/apriltag_test.launch.py" ]] && echo "  [ok] launch file present in workspace" || warn "launch file not found in workspace: $ISAAC_ROS_WS/apriltag_test.launch.py"

if [[ "$VERIFY_TOPICS" == "1" ]]; then
  log "Checking ROS topics if pipeline is running"
  TOPICS="$(container_exec "source /opt/ros/jazzy/setup.bash && timeout ${TOPIC_TIMEOUT} ros2 topic list" || true)"

  if [[ -z "$TOPICS" ]]; then
    warn "No ROS topics found. If you have not started the pipeline yet, run ./run_apriltag.sh first."
  else
    echo "$TOPICS" | sed 's/^/  /'

    for topic in /camera/image_raw /camera/camera_info /camera/image_raw/nitros /tag_detections; do
      if echo "$TOPICS" | grep -qx "$topic"; then
        printf '  [ok] topic present: %s\n' "$topic"
      else
        warn "topic missing: $topic"
      fi
    done
  fi
fi

if [[ "$VERIFY_DETECTION" == "1" ]]; then
  log "Checking one AprilTag detection"
  DETECTION="$(container_exec "source /opt/ros/jazzy/setup.bash && timeout ${DETECTION_TIMEOUT} ros2 topic echo --once /tag_detections" || true)"
  if [[ -z "$DETECTION" ]]; then
    warn "No detection received from /tag_detections within ${DETECTION_TIMEOUT}s"
  else
    echo "$DETECTION" | sed 's/^/  /'
    if echo "$DETECTION" | grep -q 'family:' && echo "$DETECTION" | grep -q 'id:'; then
      echo "  [ok] detection payload received"
    else
      warn "detection payload did not contain expected family/id fields"
    fi
  fi
fi

cat <<EOF

Verification finished.

Useful commands:
  Start pipeline:  ./run_apriltag.sh
  Verify packages: ./verify_install.sh
  Verify detection: VERIFY_DETECTION=1 ./verify_install.sh

EOF
