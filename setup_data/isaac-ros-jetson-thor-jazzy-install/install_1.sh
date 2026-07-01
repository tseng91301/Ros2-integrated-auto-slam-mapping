#!/usr/bin/env bash
set -euo pipefail

ISAAC_ROS_RELEASE="${ISAAC_ROS_RELEASE:-release-4.4}"
ISAAC_ROS_REPO_SUFFIX="${ISAAC_ROS_REPO_SUFFIX:-noble-jetpack}"
ISAAC_ROS_WS="${ISAAC_ROS_WS:-$HOME/workspaces/isaac_ros-dev}"
ISAAC_ROS_CONTAINER_NAME="${ISAAC_ROS_CONTAINER_NAME:-isaac_ros_dev_container}"
INSTALL_APRILTAG="${INSTALL_APRILTAG:-1}"
MIN_FREE_GB="${MIN_FREE_GB:-35}"

log() { printf '\n[%s] %s\n' "$(date '+%F %T')" "$*"; }
warn() { printf '\n[WARN] %s\n' "$*" >&2; }
die() { printf '\n[ERROR] %s\n' "$*" >&2; exit 1; }
need_cmd() { command -v "$1" >/dev/null 2>&1 || die "missing command: $1"; }

for cmd in curl gpg grep awk sed tee df uname dpkg docker; do
  need_cmd "$cmd"
done

if [[ ! -f /etc/os-release ]]; then
  die "/etc/os-release not found"
fi
source /etc/os-release

[[ "${ID:-}" == "ubuntu" ]] || die "This script expects Ubuntu"
[[ "${VERSION_CODENAME:-}" == "noble" ]] || die "This script expects Ubuntu 24.04 (noble)"
[[ "$(dpkg --print-architecture)" == "arm64" ]] || die "This script expects arm64"

if ! sudo -v; then
  die "sudo access is required"
fi

FREE_GB=$(df --output=avail -BG / | tail -1 | tr -dc '0-9')
if [[ -n "$FREE_GB" ]] && (( FREE_GB < MIN_FREE_GB )); then
  warn "Only ${FREE_GB}G free on /. Recommended before AprilTag/NITROS install: ${MIN_FREE_GB}G+"
fi

if docker info >/dev/null 2>&1; then
  DOCKER=(docker)
elif sudo docker info >/dev/null 2>&1; then
  DOCKER=(sudo docker)
else
  die "docker is installed but not usable. Join docker group or allow sudo docker."
fi

run_docker() {
  "${DOCKER[@]}" "$@"
}

ensure_repo() {
  log "Adding Isaac ROS apt repository and CLI"
  sudo apt update
  sudo apt install -y locales curl gnupg software-properties-common
  sudo locale-gen en_US en_US.UTF-8
  sudo update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8
  export LANG=en_US.UTF-8
  sudo add-apt-repository universe -y

  local keyring="/usr/share/keyrings/nvidia-isaac-ros.gpg"
  local list_file="/etc/apt/sources.list.d/nvidia-isaac-ros.list"
  local source_line="deb [signed-by=${keyring}] https://isaac.download.nvidia.com/isaac-ros/${ISAAC_ROS_RELEASE} ${ISAAC_ROS_REPO_SUFFIX} main"

  curl -fsSL https://isaac.download.nvidia.com/isaac-ros/repos.key | sudo gpg --dearmor | sudo tee "$keyring" >/dev/null
  sudo touch "$list_file"
  if ! grep -qxF "$source_line" "$list_file"; then
    echo "$source_line" | sudo tee -a "$list_file" >/dev/null
  fi

  sudo apt update
  sudo apt install -y isaac-ros-cli
}

setup_workspace() {
  log "Creating workspace at ${ISAAC_ROS_WS}"
  mkdir -p "${ISAAC_ROS_WS}/src"
  if ! grep -q 'export ISAAC_ROS_WS=' "$HOME/.bashrc"; then
    echo 'export ISAAC_ROS_WS="${ISAAC_ROS_WS:-$HOME/workspaces/isaac_ros-dev}"' >> "$HOME/.bashrc"
  fi
}

init_cli() {
  log "Initializing Isaac ROS CLI"
  sudo isaac-ros init docker --yes || true
}

check_docker_runtime() {
  log "Checking Docker and NVIDIA runtime"
  run_docker run --rm hello-world >/dev/null
  run_docker run --rm --runtime=nvidia ubuntu:24.04 bash -lc 'echo NVIDIA runtime OK' >/dev/null
}

prime_image() {
  if run_docker images --format '{{.Repository}}:{{.Tag}}' | grep -q '^nvcr.io/nvidia/isaac/ros:isaac_ros_'; then
    return
  fi

  log "No Isaac ROS image present. Priming image via isaac-ros activate (non-fatal if runtime launch fails afterward)"
  timeout 1800 bash -lc "export ISAAC_ROS_WS='${ISAAC_ROS_WS}'; isaac-ros activate" || true

  run_docker images --format '{{.Repository}}:{{.Tag}}' | grep -q '^nvcr.io/nvidia/isaac/ros:isaac_ros_' || \
    die "No Isaac ROS image found after priming. Try running 'export ISAAC_ROS_WS=${ISAAC_ROS_WS}; isaac-ros activate' manually once."
}

latest_image() {
  run_docker images --format '{{.Repository}}:{{.Tag}}' | grep '^nvcr.io/nvidia/isaac/ros:isaac_ros_' | tail -1
}

start_container() {
  local image
  image="$(latest_image)"
  [[ -n "$image" ]] || die "Unable to determine Isaac ROS image"

  log "Starting container ${ISAAC_ROS_CONTAINER_NAME} using ${image}"
  run_docker rm -f "${ISAAC_ROS_CONTAINER_NAME}" >/dev/null 2>&1 || true

  local args=(
    run -d --rm
    --runtime=nvidia
    --privileged
    --network host
    --ipc=host
    --pid=host
    -e ISAAC_ROS_PLATFORM=arm64-jetpack
    -e ISAAC_ROS_WS=/workspaces/isaac_ros-dev
    -e NVIDIA_VISIBLE_DEVICES=all
    -e NVIDIA_DRIVER_CAPABILITIES=all
    -e USER="$USER"
    --workdir /workspaces/isaac_ros-dev
    -v "$ISAAC_ROS_WS:/workspaces/isaac_ros-dev"
    -v /etc/localtime:/etc/localtime:ro
    -v /tmp:/tmp
    --name "$ISAAC_ROS_CONTAINER_NAME"
    --entrypoint /bin/bash
  )

  for path in \
    /usr/bin/tegrastats \
    /sys/kernel/debug \
    /usr/lib/aarch64-linux-gnu/tegra \
    /usr/src/jetson_multimedia_api \
    /usr/src/jetson_sipl_api \
    /usr/share/vpi3 \
    /usr/local/zed \
    /usr/local/cuda \
    /usr/local/cuda-13 \
    /usr/local/cuda-13.0 \
    /dev/input \
    /dev/bus/usb \
    /dev/video0 \
    /dev/video1 \
    /dev/media0 \
    /dev/media1; do
    [[ -e "$path" ]] && args+=( -v "$path:$path" )
  done

  args+=( "$image" -lc 'sleep infinity' )
  run_docker "${args[@]}" >/dev/null
}

container_exec() {
  run_docker exec "$ISAAC_ROS_CONTAINER_NAME" bash -lc "$*"
}

install_inside_container() {
  log "Installing base Isaac ROS and project packages inside container"

  # 必要安裝套件清單 (可在此處新增或修改套件)
  local PACKAGES=(
    # 核心工具與編譯依賴
    "build-essential"
    "python3-colcon-common-extensions"
    "python3-rosdep"
    "ros-jazzy-rviz2"
    "ros-jazzy-isaac-ros-common"
    "ros-jazzy-isaac-ros-examples"

    # 感測器與相機驅動
    "v4l-utils"
    "ros-jazzy-v4l2-camera"
    "ros-jazzy-librealsense2"
    "ros-jazzy-realsense2-camera"
    "ros-jazzy-realsense2-camera-msgs"
    "ros-jazzy-cv-bridge"
    "ros-jazzy-theora-image-transport"
    "ros-jazzy-compressed-image-transport"
    "ros-jazzy-image-transport-plugins"

    # ZED 開發與運行相依庫 (修復 ZED 套件編譯失敗問題)
    "libusb-1.0-0-dev"
    "libturbojpeg"
    "libturbojpeg0-dev"
    "tensorrt"

    # 導航與 SLAM 套件
    "ros-jazzy-navigation2"
    "ros-jazzy-nav2-bringup"
    "ros-jazzy-nav2-common"
    "ros-jazzy-nav2-simple-commander"
    "ros-jazzy-slam-toolbox"
    "ros-jazzy-xacro"
    "ros-jazzy-tf-transformations"

    # 模擬與通訊工具
    "ros-jazzy-ros-gz"
    "ros-jazzy-ros-gz-sim-demos"
    "ros-jazzy-gz-ros2-control"
    "python3-serial"
    "python3-matplotlib"
    "python3-tornado"
    "python3-requests"
    "python3-tqdm"
  )

  if [[ "$INSTALL_APRILTAG" == "1" ]]; then
    log "Installing AprilTag + NITROS stack inside container (this can take a long time)"
    container_exec "apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y ros-jazzy-isaac-ros-apriltag ros-jazzy-isaac-ros-apriltag-interfaces"
  fi
}

verify_install() {
  log "Verifying installed packages"
  container_exec "source /opt/ros/jazzy/setup.bash && ros2 pkg prefix isaac_ros_common && ros2 pkg prefix isaac_ros_examples"
  if [[ "$INSTALL_APRILTAG" == "1" ]]; then
    container_exec "source /opt/ros/jazzy/setup.bash && ros2 pkg prefix isaac_ros_apriltag"
  fi
}

print_summary() {
  cat <<EOF

Install complete.

Workspace: ${ISAAC_ROS_WS}
Container: ${ISAAC_ROS_CONTAINER_NAME}
README:    $(dirname "$0")/README.md
Launch:    $(dirname "$0")/apriltag_test.launch.py

Next steps:
  1. Plug in a UVC USB camera.
  2. Run: $(dirname "$0")/run_apriltag.sh

EOF
}

ensure_repo
setup_workspace
init_cli
check_docker_runtime
prime_image
start_container
install_inside_container
verify_install
print_summary
