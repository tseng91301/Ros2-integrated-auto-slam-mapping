// static/js/explorer.js
// WebSocket and Canvas controller for Thor Autonomous Exploration

(function () {
    let ws;
    let wsConnected = false;
    let reconnectTimeout = null;

    // Reusable Map Canvas Controller
    let mapCanvas = null;

    // Exploration state
    let isPaused = true;
    let currentLap = 1;
    let maxExplorationLaps = 1;
    let explorationComplete = false;
    let robotRadiusM = 0.20;

    // DOM Elements
    const dot = document.getElementById('status-dot');
    const text = document.getElementById('status-text');

    const valStatus = document.getElementById('val-status');
    const valGoal = document.getElementById('val-goal');
    const valLaps = document.getElementById('val-laps');
    const valFrontiers = document.getElementById('val-frontiers');

    const mapPlaceholder = document.getElementById('map-placeholder');
    const mapTelemetry = document.getElementById('map-telemetry');

    const lapInput = document.getElementById('lap-input');

    // Button controls
    const btnStart = document.getElementById('btn-start');
    const btnPause = document.getElementById('btn-pause');
    const btnResume = document.getElementById('btn-resume');
    const btnResetExplore = document.getElementById('btn-reset-explore');
    const btnSetLaps = document.getElementById('btn-set-laps');

    const btnSaveRobot = document.getElementById('btn-save-robot');
    const btnResetMap = document.getElementById('btn-reset-map');
    const btnDownloadPng = document.getElementById('btn-download-png');
    const btnDownloadRos = document.getElementById('btn-download-ros');
    const btnEstop = document.getElementById('btn-estop');

    // WebSocket connection
    function connect() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;

        ws = new WebSocket(wsUrl);

        ws.onopen = () => {
            wsConnected = true;
            dot.className = 'status-indicator online';
            text.textContent = 'ONLINE';
            text.style.color = '#22c55e';
            console.log('WebSocket connected.');
            if (reconnectTimeout) clearTimeout(reconnectTimeout);
        };

        ws.onclose = () => {
            wsConnected = false;
            dot.className = 'status-indicator offline';
            text.textContent = 'OFFLINE';
            text.style.color = '#ef4444';
            mapPlaceholder.classList.remove('hidden');
            mapTelemetry.textContent = 'Map: Offline';
            console.log('WebSocket closed. Retrying in 2 seconds...');
            reconnectTimeout = setTimeout(connect, 2000);
        };

        ws.onerror = (err) => {
            console.error('WebSocket error:', err);
        };

        ws.onmessage = (event) => {
            try {
                const msg = JSON.parse(event.data);
                console.log("Received Message: ", msg.type)
                if (msg.type === 'map') {
                    if (mapCanvas) mapCanvas.updateMap(msg);
                } else if (msg.type === 'robot_pose') {
                    if (mapCanvas) mapCanvas.updateRobotPose(msg);
                } else if (msg.type === 'exploration_status') {
                    const centroids = msg.centroids || [];
                    const target = msg.target || null;

                    valFrontiers.textContent = `${centroids.length} clusters`;
                    if (target) {
                        valGoal.textContent = `(${target.x.toFixed(2)}, ${target.y.toFixed(2)})`;
                    } else {
                        valGoal.textContent = 'None';
                    }

                    if (mapCanvas) {
                        mapCanvas.updateCentroids(centroids);
                        mapCanvas.updateTarget(target);
                    }
                } else if (msg.type === 'exploration_node_status') {
                    isPaused = msg.is_paused;
                    currentLap = msg.current_lap;
                    maxExplorationLaps = msg.max_exploration_laps;
                    explorationComplete = msg.exploration_complete;
                    if (msg.robot_radius !== undefined) {
                        robotRadiusM = msg.robot_radius;
                        if (mapCanvas) {
                            mapCanvas.options.robotRadiusM = robotRadiusM;
                        }
                    }

                    // Update lapInput value to match the node parameter dynamically
                    lapInput.value = maxExplorationLaps;
                    valLaps.textContent = `${currentLap} / ${maxExplorationLaps}`;

                    if (explorationComplete) {
                        valStatus.textContent = 'COMPLETE';
                        valStatus.className = 'tel-value text-cyan';
                    } else if (isPaused) {
                        valStatus.textContent = 'PAUSED';
                        valStatus.className = 'tel-value';
                    } else {
                        valStatus.textContent = 'EXPLORING';
                        valStatus.className = 'tel-value text-green';
                    }
                }
            } catch (e) {
                console.error('Error parsing WS message:', e);
            }
        };
    }

    // Zoom buttons listener configuration
    document.getElementById('btn-zoom-in').addEventListener('click', () => {
        if (mapCanvas) mapCanvas.zoomIn();
    });

    document.getElementById('btn-zoom-out').addEventListener('click', () => {
        if (mapCanvas) mapCanvas.zoomOut();
    });

    document.getElementById('btn-zoom-reset').addEventListener('click', () => {
        if (mapCanvas) mapCanvas.resetView();
    });

    // --- EXPLORATION CONTROL COMMANDS ---
    function sendExplorationCmd(command) {
        if (!wsConnected) return;
        ws.send(JSON.stringify({
            type: 'exploration_cmd',
            command: command
        }));
    }

    btnStart.addEventListener('click', () => {
        sendExplorationCmd('start');
        valStatus.textContent = 'EXPLORING';
        valStatus.className = 'tel-value text-green';
    });

    btnPause.addEventListener('click', () => {
        sendExplorationCmd('pause');
        valStatus.textContent = 'PAUSED';
        valStatus.className = 'tel-value';
    });

    btnResume.addEventListener('click', () => {
        sendExplorationCmd('resume');
        valStatus.textContent = 'EXPLORING';
        valStatus.className = 'tel-value text-green';
    });

    btnResetExplore.addEventListener('click', () => {
        if (confirm("Reset the exploration progress and target blacklist?")) {
            sendExplorationCmd('reset');
            if (mapCanvas) {
                mapCanvas.updateCentroids([]);
                mapCanvas.updateTarget(null);
            }
            valFrontiers.textContent = '0 clusters';
            valGoal.textContent = 'None';
            valStatus.textContent = 'PAUSED';
            valStatus.className = 'tel-value';
        }
    });

    btnSetLaps.addEventListener('click', () => {
        const laps = parseInt(lapInput.value);
        if (isNaN(laps) || laps < 1) {
            alert("Please enter a valid number of laps (1 or more).");
            return;
        }
        sendExplorationCmd(`set_laps:${laps}`);
        valLaps.textContent = `${currentLap} / ${laps}`;
    });

    btnEstop.addEventListener('click', () => {
        // Send emergency stop commands
        sendExplorationCmd('stop');
        valStatus.textContent = 'STOPPING...';
        valStatus.className = 'tel-value text-red';
        console.warn("EMERGENCY STOP COMMAND SENT.");
    });

    // --- MAP OPERATIONS ---
    btnSaveRobot.addEventListener('click', () => {
        if (!wsConnected) return;
        const filename = prompt("Enter file name to save map on the Robot:", "map");
        if (filename) {
            ws.send(JSON.stringify({
                type: 'save_map',
                filename: filename
            }));
            alert(`Map saving command sent to robot as '${filename}'`);
        }
    });

    btnResetMap.addEventListener('click', () => {
        if (!wsConnected) return;
        if (confirm("⚠️ 注意：確定要重置 SLAM 地圖數據嗎？這會清除當前已掃描的所有資料！")) {
            ws.send(JSON.stringify({
                type: 'reset_map'
            }));
            if (mapCanvas) {
                mapCanvas.centroids = [];
                mapCanvas.target = null;
                mapCanvas.robotPose.active = false;
                mapCanvas.hasMapData = false;
                mapCanvas.ctx.clearRect(0, 0, mapCanvas.canvas.width, mapCanvas.canvas.height);
            }
            mapPlaceholder.classList.remove('hidden');
            mapTelemetry.textContent = 'Map: Resetting...';
            valFrontiers.textContent = '0 clusters';
            valGoal.textContent = 'None';
        }
    });

    btnDownloadPng.addEventListener('click', () => {
        if (!mapCanvas || !mapCanvas.hasMapData) {
            alert("No active map data available to download.");
            return;
        }
        const link = document.createElement('a');
        link.download = 'robot_map.png';
        link.href = mapCanvas.canvas.toDataURL('image/png');
        link.click();
    });

    btnDownloadRos.addEventListener('click', () => {
        if (confirm("Generate and download ROS 2 map files (PGM + YAML) ZIP package?")) {
            window.location.href = '/api/download_map';
        }
    });

    // Startup System
    mapCanvas = new MapCanvas('map-canvas');
    connect();

    // Run animation frames for pulsing animations on target beacon
    function animationLoop() {
        if (mapCanvas && mapCanvas.hasMapData) {
            mapCanvas.draw();
        }
        requestAnimationFrame(animationLoop);
    }
    requestAnimationFrame(animationLoop);

})();
