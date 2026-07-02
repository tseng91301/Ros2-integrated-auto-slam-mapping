#!/usr/bin/env bash
# run_web_controller_nodes.sh
#
# This script launches the background simulation/hardware nodes from web_controller.launch.py
# (excluding the web server and trajectory tracker).

ROS_DOMAIN_ID_VAL="55"
DOCKER_CONTAINER="isaac_ros_dev_container"
PREFIX="docker exec -it ${DOCKER_CONTAINER} bash -lc 'export ROS_DOMAIN_ID=${ROS_DOMAIN_ID_VAL} && source /opt/ros/jazzy/setup.bash && source /workspaces/isaac_ros-dev/install/setup.bash && export DISPLAY=:0 &&"

show_help() {
    echo "================================================================="
    echo "🧭 ROS 2 Web Controller Support Node Launcher"
    echo "================================================================="
    echo "This script runs the simulation/physical hardware nodes from"
    echo "web_controller.launch.py (excluding the web server nodes)."
    echo ""
    echo "Usage:"
    echo "  $0 list-sim       - Show copy-pasteable commands for Simulation support nodes"
    echo "  $0 list-phys      - Show copy-pasteable commands for Physical support nodes"
    echo "  $0 run-sim <step> - Run a specific simulation support step directly"
    echo "  $0 run-phys <step>- Run a specific physical hardware step directly"
    echo ""
}

case "$1" in
    list-sim)
        echo "=== Simulation Mode Support Nodes ==="
        echo ""
        echo "[Step 1: Setup Temp World SDF]"
        echo "  ${PREFIX} exec cp /workspaces/isaac_ros-dev/worlds/virtual/my-nav-map/my-nav-map.sdf /tmp/gz_world.sdf'"
        echo ""
        echo "[Step 2: Gazebo Sim Server (Headless/xvfb)]"
        echo "  ${PREFIX} exec xvfb-run -a gz sim -r -s /tmp/gz_world.sdf'"
        echo ""
        echo "[Step 3: Robot State Publisher]"
        echo "  ${PREFIX} exec ros2 run robot_state_publisher robot_state_publisher --ros-args -p use_sim_time:=true -p robot_description:=\"\$(cat /opt/ros/jazzy/share/nav2_minimal_tb3_sim/urdf/turtlebot3_waffle.urdf)\" --remap /tf:=tf --remap /tf_static:=tf_static'"
        echo ""
        echo "[Step 4: ROS-GZ Parameter Bridge]"
        echo "  ${PREFIX} exec ros2 run ros_gz_bridge parameter_bridge --ros-args -p config_file:=/opt/ros/jazzy/share/nav2_minimal_tb3_sim/configs/turtlebot3_waffle_bridge.yaml -p expand_gz_topic_names:=true -p use_sim_time:=true'"
        echo ""
        echo "[Step 5: Spawn Turtlebot3 Waffle in Gazebo]"
        echo "  ${PREFIX} export GZ_SIM_RESOURCE_PATH=/opt/ros/jazzy/share/nav2_minimal_tb3_sim/models:/opt/ros/jazzy/share:\$GZ_SIM_RESOURCE_PATH && exec ros2 run ros_gz_sim create -name turtlebot3_waffle -string \"\$(xacro /opt/ros/jazzy/share/nav2_minimal_tb3_sim/urdf/gz_waffle.sdf.xacro)\" -x -3.0 -y -1.5 -z 0.01'"
        echo ""
        ;;

    list-phys)
        echo "=== Physical Robot Mode Support Nodes ==="
        echo ""
        echo "[Step 1: Base Control (Motor & Odom)]"
        echo "  ${PREFIX} export BASE_TYPE=NanoRobot && exec ros2 launch base_control_ros2 00_base_control.launch.py pub_sonar:=True filter_sonar:=True'"
        echo ""
        echo "[Step 2: RPLIDAR A2M12 Lidar Driver]"
        echo "  ${PREFIX} exec ros2 launch sllidar_ros2 sllidar_a2m12_launch.py serial_port:=/dev/sllidar_a2m12'"
        echo ""
        ;;

    run-sim)
        case "$2" in
            1)
                echo "Running Step 1: Setup Temp World SDF..."
                eval "${PREFIX} exec cp /workspaces/isaac_ros-dev/worlds/virtual/my-nav-map/my-nav-map.sdf /tmp/gz_world.sdf'"
                ;;
            2)
                echo "Running Step 2: Gazebo Sim Server..."
                eval "${PREFIX} exec xvfb-run -a gz sim -r -s /tmp/gz_world.sdf'"
                ;;
            3)
                echo "Running Step 3: Robot State Publisher..."
                eval "${PREFIX} exec ros2 run robot_state_publisher robot_state_publisher --ros-args -p use_sim_time:=true -p robot_description:=\"\$(cat /opt/ros/jazzy/share/nav2_minimal_tb3_sim/urdf/turtlebot3_waffle.urdf)\" --remap /tf:=tf --remap /tf_static:=tf_static'"
                ;;
            4)
                echo "Running Step 4: ROS-GZ Parameter Bridge..."
                eval "${PREFIX} exec ros2 run ros_gz_bridge parameter_bridge --ros-args -p config_file:=/opt/ros/jazzy/share/nav2_minimal_tb3_sim/configs/turtlebot3_waffle_bridge.yaml -p expand_gz_topic_names:=true -p use_sim_time:=true'"
                ;;
            5)
                echo "Running Step 5: Spawn Turtlebot3 Waffle..."
                eval "${PREFIX} export GZ_SIM_RESOURCE_PATH=/opt/ros/jazzy/share/nav2_minimal_tb3_sim/models:/opt/ros/jazzy/share:\$GZ_SIM_RESOURCE_PATH && exec ros2 run ros_gz_sim create -name turtlebot3_waffle -string \"\$(xacro /opt/ros/jazzy/share/nav2_minimal_tb3_sim/urdf/gz_waffle.sdf.xacro)\" -x -3.0 -y -1.5 -z 0.01'"
                ;;
            *)
                echo "Invalid Simulation step: $2 (Available: 1-5)"
                ;;
        esac
        ;;

    run-phys)
        case "$2" in
            1)
                echo "Running Step 1: Base Control..."
                eval "${PREFIX} export BASE_TYPE=NanoRobot && exec ros2 launch base_control_ros2 00_base_control.launch.py pub_sonar:=True filter_sonar:=True'"
                ;;
            2)
                echo "Running Step 2: RPLIDAR A2M12 Lidar..."
                eval "${PREFIX} exec ros2 launch sllidar_ros2 sllidar_a2m12_launch.py serial_port:=/dev/sllidar_a2m12'"
                ;;
            *)
                echo "Invalid Physical step: $2 (Available: 1-2)"
                ;;
        esac
        ;;

    *)
        show_help
        ;;
esac
