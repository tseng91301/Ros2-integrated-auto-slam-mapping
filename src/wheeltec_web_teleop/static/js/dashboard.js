// Thor Unified Robot Dashboard Javascript Controller
document.addEventListener('DOMContentLoaded', () => {
    // STATE VARIABLES
    let ws = null;
    let reconnectTimeout = null;
    let wsConnected = false;
    let activeMode = 'teleop'; // 'teleop', 'explorer', 'navigation'

    // Limits for teleop
    let limitLinear = 0.50;
    let limitAngular = 1.00;
    let isHolonomic = false;

    // Current Input Velocities (Teleop)
    let inputVx = 0.0;
    let inputVy = 0.0;
    let inputWz = 0.0;
    let isMoving = false;
    let stopCommandsSent = 0;
    let commandInterval = null;

    // Exploration Mode status
    let explorePaused = true;
    let exploreLap = 1;
    let exploreMaxLaps = 1;
    let exploreComplete = false;
    let robotRadiusM = 0.20;

    // Navigation Mode state
    let navMarker = null;

    // Reusable Map Canvas Controller
    let mapCanvas = null;

    // --- DOM ELEMENTS ---
    const rootContainer = document.getElementById('app-root-container');
    const layout = document.getElementById('main-layout');

    // Header HUD Indicators
    const dot = document.getElementById('status-dot');
    const text = document.getElementById('status-text');
    const collisionAlert = document.getElementById('collision-alert');
    const collisionSectors = document.getElementById('collision-sectors');
    const monitorScreen = document.querySelector('.monitor-screen');

    // HUD Dynamic Values
    const valLimitLinear = document.getElementById('val-limit-linear');
    const valLimitAngular = document.getElementById('val-limit-angular');
    const valVx = document.getElementById('val-vx');
    const valWz = document.getElementById('val-wz');

    const valExploreStatus = document.getElementById('val-explore-status');
    const valExploreGoal = document.getElementById('val-explore-goal');
    const valExploreLaps = document.getElementById('val-explore-laps');
    const valExploreFrontiers = document.getElementById('val-explore-frontiers');

    const valNavStatus = document.getElementById('val-nav-status');
    const valNavTarget = document.getElementById('val-nav-target');
    const valNavPose = document.getElementById('val-nav-pose');

    // Map Canvas
    const canvas = document.getElementById('map-canvas');
    const mapPlaceholder = document.getElementById('map-placeholder');
    const mapTelemetry = document.getElementById('map-telemetry');
    const mapLoadingText = document.getElementById('map-loading-text');

    // Sliders & Checks (Teleop)
    const sliderLinear = document.getElementById('slider-linear');
    const sliderAngular = document.getElementById('slider-angular');
    const valSliderLinear = document.getElementById('val-slider-linear');
    const valSliderAngular = document.getElementById('val-slider-angular');
    const checkHolonomic = document.getElementById('check-holonomic');
    const leftModeIndicator = document.getElementById('left-mode-indicator');

    // Control toggles for grips
    const toggleLeft = document.getElementById('toggle-left-control');
    const leftJoystickContainer = document.getElementById('left-joystick-container');
    const leftDpad = document.getElementById('left-dpad');

    const toggleRight = document.getElementById('toggle-right-control');
    const rightJoystickContainer = document.getElementById('right-joystick-container');
    const rightDpad = document.getElementById('right-dpad');

    // Navigation Map elements
    const mapSelect = document.getElementById('map-select');
    const btnLoadMap = document.getElementById('btn-load-map');

    // Explore Config
    const lapInput = document.getElementById('lap-input');

    // Modal elements
    const helpToggle = document.getElementById('help-toggle');
    const helpModal = document.getElementById('help-modal');
    const modalClose = document.getElementById('modal-close');

    // --- MODE SWITCHER LOGIC ---
    function switchMode(newMode) {
        activeMode = newMode;
        console.log(`Switching mode to: ${newMode}`);

        // Update URL path dynamically
        window.history.pushState({ mode: newMode }, '', `/${newMode}`);

        // Update top navbar tabs style
        document.querySelectorAll('.btn-mode').forEach(btn => {
            if (btn.getAttribute('data-mode') === newMode) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });

        // Toggle visual grid columns
        if (newMode === 'teleop') {
            layout.classList.remove('two-cols');
        } else {
            layout.classList.add('two-cols');
        }

        // Hide/Show Sidebars
        document.querySelectorAll('.mode-sidebar').forEach(sidebar => {
            if (sidebar.id === `sidebar-${newMode}`) {
                sidebar.classList.remove('hidden');
            } else {
                sidebar.classList.add('hidden');
            }
        });

        // Hide/Show Telemetry HUD columns
        document.querySelectorAll('.hud-telemetry').forEach(hud => {
            if (hud.id === `telemetry-${newMode}`) {
                hud.classList.remove('hidden');
            } else {
                hud.classList.add('hidden');
            }
        });

        // Update Map monitor header text
        const mapTitle = document.getElementById('map-title-terminal');
        if (newMode === 'teleop') {
            mapTitle.textContent = 'SYS.MAP.ACTIVE - SLAM_TOOLBOX';
            mapLoadingText.textContent = 'CONNECTING TO ROS2 MAP DATA...';
        } else if (newMode === 'explorer') {
            mapTitle.textContent = 'SYS.EXPLORATION.MONITOR';
            mapLoadingText.textContent = 'CONNECTING TO ROS2 ENVIRONMENT...';
        } else if (newMode === 'navigation') {
            mapTitle.textContent = 'SYS.NAVIGATION.MONITOR';
            mapLoadingText.textContent = 'LOADING DESIGNATED STATIC MAP...';
        }

        // Canvas drawing flags adjustment
        if (mapCanvas) {
            if (newMode === 'explorer') {
                mapCanvas.options.showCentroids = true;
                mapCanvas.options.showTarget = true;
            } else {
                mapCanvas.options.showCentroids = false;
                mapCanvas.options.showTarget = false;
            }
            mapCanvas.draw();
        }

        // Notify backend of mode switch
        if (wsConnected && ws.readyState === WebSocket.OPEN) {
            const socketMode = (newMode === 'teleop' || newMode === 'explorer') ? 'exploration' : 'navigation';
            ws.send(JSON.stringify({
                type: 'set_mode',
                mode: socketMode
            }));

            // Fetch map selector data if entering navigation
            if (newMode === 'navigation') {
                fetchMapList();
            }
        }
    }

    // Bind tab clicks
    document.querySelectorAll('.btn-mode').forEach(btn => {
        btn.addEventListener('click', () => {
            switchMode(btn.getAttribute('data-mode'));
        });
    });

    // --- WEBSOCKET CONNECTION ---
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

            // Sync current active mode on open
            const socketMode = (activeMode === 'teleop' || activeMode === 'explorer') ? 'exploration' : 'navigation';
            ws.send(JSON.stringify({
                type: 'set_mode',
                mode: socketMode
            }));

            if (activeMode === 'navigation') {
                fetchMapList();
            }

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

                // 1. Shared Telemetry Messages
                if (msg.type === 'map') {
                    if (mapCanvas) mapCanvas.updateMap(msg);
                } else if (msg.type === 'robot_pose') {
                    if (mapCanvas) mapCanvas.updateRobotPose(msg);
                    if (activeMode === 'navigation') {
                        valNavPose.textContent = `(${msg.x.toFixed(2)}, ${msg.y.toFixed(2)}) @ ${(msg.yaw * 180 / Math.PI).toFixed(0)}°`;
                    }
                } else if (msg.type === 'trajectory') {
                    if (mapCanvas) mapCanvas.updateTrajectory(msg.data);
                } else if (msg.type === 'collision') {
                    handleCollisionAlert(msg);
                }

                // 2. Exploration-Specific Messages
                else if (msg.type === 'exploration_status') {
                    const centroids = msg.centroids || [];
                    const target = msg.target || null;

                    valExploreFrontiers.textContent = `${centroids.length} clusters`;
                    if (target) {
                        valExploreGoal.textContent = `(${target.x.toFixed(2)}, ${target.y.toFixed(2)})`;
                    } else {
                        valExploreGoal.textContent = 'None';
                    }

                    if (mapCanvas) {
                        mapCanvas.updateCentroids(centroids);
                        mapCanvas.updateTarget(target);
                    }
                } else if (msg.type === 'exploration_node_status') {
                    explorePaused = msg.is_paused;
                    exploreLap = msg.current_lap;
                    exploreMaxLaps = msg.max_exploration_laps;
                    exploreComplete = msg.exploration_complete;
                    const isRecovering = msg.is_recovering || false;

                    if (msg.robot_radius !== undefined) {
                        robotRadiusM = msg.robot_radius;
                        if (mapCanvas) {
                            mapCanvas.options.robotRadiusM = robotRadiusM;
                        }
                    }
                    if (mapCanvas) {
                        mapCanvas.isRecovering = isRecovering;
                    }

                    lapInput.value = exploreMaxLaps;
                    valExploreLaps.textContent = `${exploreLap} / ${exploreMaxLaps}`;

                    if (exploreComplete) {
                        valExploreStatus.textContent = 'COMPLETE';
                        valExploreStatus.className = 'tel-value text-cyan';
                    } else if (isRecovering) {
                        valExploreStatus.textContent = 'RECOVERING';
                        valExploreStatus.className = 'tel-value text-amber';
                    } else if (explorePaused) {
                        valExploreStatus.textContent = 'PAUSED';
                        valExploreStatus.className = 'tel-value';
                    } else {
                        valExploreStatus.textContent = 'EXPLORING';
                        valExploreStatus.className = 'tel-value text-green';
                    }
                }

                // 3. Navigation-Specific Messages
                else if (msg.type === 'nav_target') {
                    if (msg.x !== null && msg.x !== undefined && msg.y !== null && msg.y !== undefined) {
                        navMarker = { x: msg.x, y: msg.y };
                        valNavTarget.textContent = `(${msg.x.toFixed(2)}, ${msg.y.toFixed(2)})`;
                    } else {
                        navMarker = null;
                        valNavTarget.textContent = 'None';
                    }

                    if (msg.status) {
                        updateNavStatus(msg.status);
                    }
                } else if (msg.type === 'nav_status') {
                    updateNavStatus(msg.status);
                    if (msg.status === 'ARRIVED') {
                        navMarker = null;
                        valNavTarget.textContent = 'None';
                        if (mapCanvas) mapCanvas.draw();
                    }
                }
            } catch (e) {
                console.error('Error parsing WS message:', e);
            }
        };
    }

    function updateNavStatus(status) {
        valNavStatus.textContent = status;
        if (status === 'NAVIGATING') {
            valNavStatus.className = 'tel-value text-amber';
        } else if (status === 'ARRIVED') {
            valNavStatus.className = 'tel-value text-green';
        } else if (status === 'PAUSED') {
            valNavStatus.className = 'tel-value text-cyan';
        } else {
            valNavStatus.className = 'tel-value';
        }
    }

    function handleCollisionAlert(msg) {
        if (!collisionAlert || !collisionSectors) return;
        if (msg.collision) {
            collisionAlert.classList.remove('hidden');
            let sectors = [];
            if (msg.front) sectors.push('FRONT');
            if (msg.rear) sectors.push('REAR');
            if (msg.left) sectors.push('LEFT');
            if (msg.right) sectors.push('RIGHT');
            collisionSectors.textContent = `[${sectors.join(', ')}]`;

            if (monitorScreen) {
                monitorScreen.classList.add('collision-flash');
            }
        } else {
            collisionAlert.classList.add('hidden');
            collisionSectors.textContent = '';
            if (monitorScreen) {
                monitorScreen.classList.remove('collision-flash');
            }
        }
    }

    // --- ZOOM CONTROLS ---
    document.getElementById('btn-zoom-in').addEventListener('click', () => {
        if (mapCanvas) mapCanvas.zoomIn();
    });

    document.getElementById('btn-zoom-out').addEventListener('click', () => {
        if (mapCanvas) mapCanvas.zoomOut();
    });

    document.getElementById('btn-zoom-reset').addEventListener('click', () => {
        if (mapCanvas) mapCanvas.resetView();
    });

    // --- TELEOP JOYSTICKS & COMMAND LOOP ---
    function sendCommand() {
        if (!wsConnected || ws.readyState !== WebSocket.OPEN) return;
        if (activeMode !== 'teleop') return;

        const hasInput = (Math.abs(inputVx) > 0.01 || Math.abs(inputVy) > 0.01 || Math.abs(inputWz) > 0.01);

        if (hasInput) {
            isMoving = true;
            stopCommandsSent = 0;

            const x = inputVx * limitLinear;
            const y = inputVy * limitLinear;
            const th = inputWz * limitAngular;

            ws.send(JSON.stringify({
                type: 'cmd_vel',
                x: x,
                y: y,
                th: th
            }));

            valVx.textContent = `${x.toFixed(2)} m/s`;
            valWz.textContent = `${th.toFixed(2)} rad/s`;
        } else {
            if (isMoving) {
                if (stopCommandsSent < 3) {
                    ws.send(JSON.stringify({
                        type: 'cmd_vel',
                        x: 0.0,
                        y: 0.0,
                        th: 0.0
                    }));
                    stopCommandsSent++;
                    valVx.textContent = `0.00 m/s`;
                    valWz.textContent = `0.00 rad/s`;
                } else {
                    isMoving = false;
                }
            }
        }
    }

    // Joystick Factory
    function makeJoystick(containerId, handleId, onUpdate) {
        const container = document.getElementById(containerId);
        const handle = document.getElementById(handleId);
        if (!container || !handle) return;

        let dragActive = false;
        let startX, startY;
        let limit = 50;

        function handleStart(e) {
            dragActive = true;
            handle.style.transition = 'none';

            const clientX = e.touches ? e.touches[0].clientX : e.clientX;
            const clientY = e.touches ? e.touches[0].clientY : e.clientY;

            const rect = container.getBoundingClientRect();
            startX = rect.left + rect.width / 2;
            startY = rect.top + rect.height / 2;

            e.preventDefault();
        }

        function handleMove(e) {
            if (!dragActive) return;

            const clientX = e.touches ? e.touches[0].clientX : e.clientX;
            const clientY = e.touches ? e.touches[0].clientY : e.clientY;

            let deltaX = clientX - startX;
            let deltaY = clientY - startY;
            const distance = Math.sqrt(deltaX * deltaX + deltaY * deltaY);

            if (distance > limit) {
                deltaX = (deltaX / distance) * limit;
                deltaY = (deltaY / distance) * limit;
            }

            handle.style.transform = `translate(${deltaX}px, ${deltaY}px)`;
            onUpdate(deltaX / limit, deltaY / limit);
            e.preventDefault();
        }

        function handleEnd() {
            if (!dragActive) return;
            dragActive = false;

            handle.style.transition = 'transform 0.2s ease-out';
            handle.style.transform = 'translate(0px, 0px)';
            onUpdate(0, 0);
        }

        container.addEventListener('mousedown', handleStart);
        document.addEventListener('mousemove', handleMove);
        document.addEventListener('mouseup', handleEnd);

        container.addEventListener('touchstart', handleStart, { passive: false });
        document.addEventListener('touchmove', handleMove, { passive: false });
        document.addEventListener('touchend', handleEnd);
    }

    // Instantiate Joysticks
    makeJoystick('left-joystick-container', 'left-joystick-handle', (nx, ny) => {
        inputVx = -ny;
        inputVy = isHolonomic ? -nx : 0.0;
    });

    makeJoystick('right-joystick-container', 'right-joystick-handle', (nx, ny) => {
        inputWz = -nx;
    });

    // Control toggles
    toggleLeft.addEventListener('change', (e) => {
        if (e.target.checked) {
            leftJoystickContainer.classList.add('hidden');
            leftDpad.classList.remove('hidden');
        } else {
            leftJoystickContainer.classList.remove('hidden');
            leftDpad.classList.add('hidden');
        }
        resetVelocityInputs();
    });

    toggleRight.addEventListener('change', (e) => {
        if (e.target.checked) {
            rightJoystickContainer.classList.add('hidden');
            rightDpad.classList.remove('hidden');
        } else {
            rightJoystickContainer.classList.remove('hidden');
            rightDpad.classList.add('hidden');
        }
        resetVelocityInputs();
    });

    function resetVelocityInputs() {
        inputVx = 0.0;
        inputVy = 0.0;
        inputWz = 0.0;
    }

    // D-PAD Helpers
    function setupDpadButton(id, onStart, onEnd) {
        const btn = document.getElementById(id);
        if (!btn) return;
        btn.addEventListener('mousedown', onStart);
        btn.addEventListener('mouseup', onEnd);
        btn.addEventListener('mouseleave', onEnd);
        btn.addEventListener('touchstart', (e) => {
            onStart();
            e.preventDefault();
        }, { passive: false });
        btn.addEventListener('touchend', onEnd);
    }

    setupDpadButton('btn-linear-forward', () => { inputVx = 1.0; }, () => { inputVx = 0.0; });
    setupDpadButton('btn-linear-backward', () => { inputVx = -1.0; }, () => { inputVx = 0.0; });
    setupDpadButton('btn-linear-left', () => { if (isHolonomic) inputVy = 1.0; }, () => { inputVy = 0.0; });
    setupDpadButton('btn-linear-right', () => { if (isHolonomic) inputVy = -1.0; }, () => { inputVy = 0.0; });
    
    const btnLinearStop = document.getElementById('btn-linear-stop');
    if (btnLinearStop) btnLinearStop.addEventListener('click', resetVelocityInputs);

    setupDpadButton('btn-turn-left', () => { inputWz = 1.0; }, () => { inputWz = 0.0; });
    setupDpadButton('btn-turn-right', () => { inputWz = -1.0; }, () => { inputWz = 0.0; });
    
    const btnAngularStop = document.getElementById('btn-angular-stop');
    if (btnAngularStop) btnAngularStop.addEventListener('click', () => { inputWz = 0.0; });

    // Speed Sliders
    sliderLinear.addEventListener('input', (e) => {
        limitLinear = parseFloat(e.target.value);
        valSliderLinear.textContent = limitLinear.toFixed(2);
        valLimitLinear.textContent = `${limitLinear.toFixed(2)} m/s`;
    });

    sliderAngular.addEventListener('input', (e) => {
        limitAngular = parseFloat(e.target.value);
        valSliderAngular.textContent = limitAngular.toFixed(2);
        valLimitAngular.textContent = `${limitAngular.toFixed(2)} rad/s`;
    });

    // Drive holonomic toggler
    checkHolonomic.addEventListener('change', (e) => {
        isHolonomic = e.target.checked;
        leftModeIndicator.textContent = isHolonomic ? "Mode: Holonomic (Strafing)" : "Mode: Non-Holonomic";
        resetVelocityInputs();
    });

    // --- KEYBOARD CONTROLS FOR MANUAL ---
    const activeKeys = {};
    window.addEventListener('keydown', (e) => {
        if (e.target.tagName === 'INPUT') return;
        if (activeMode !== 'teleop') return;

        activeKeys[e.key] = true;
        updateKeyboardInput();

        if (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', ' '].includes(e.key)) {
            e.preventDefault();
        }
    });

    window.addEventListener('keyup', (e) => {
        if (e.target.tagName === 'INPUT') return;
        activeKeys[e.key] = false;
        updateKeyboardInput();
    });

    function updateKeyboardInput() {
        let x = 0.0;
        let y = 0.0;
        let th = 0.0;

        const isShift = activeKeys['Shift'];

        if (activeKeys['i'] || activeKeys['I'] || activeKeys['ArrowUp']) {
            x = 1.0;
        } else if (activeKeys[','] || activeKeys['<'] || activeKeys['ArrowDown']) {
            x = -1.0;
        }

        if (isShift || isHolonomic) {
            if (activeKeys['j'] || activeKeys['J'] || activeKeys['ArrowLeft']) {
                y = 1.0;
            } else if (activeKeys['l'] || activeKeys['L'] || activeKeys['ArrowRight']) {
                y = -1.0;
            }

            if (activeKeys['u'] || activeKeys['U']) { x = 1.0; y = 1.0; }
            else if (activeKeys['o'] || activeKeys['O']) { x = 1.0; y = -1.0; }
            else if (activeKeys['m'] || activeKeys['M']) { x = -1.0; y = 1.0; }
            else if (activeKeys['.'] || activeKeys['>']) { x = -1.0; y = -1.0; }
        } else {
            if (activeKeys['j'] || activeKeys['ArrowLeft']) {
                th = 1.0;
            } else if (activeKeys['l'] || activeKeys['ArrowRight']) {
                th = -1.0;
            }

            if (activeKeys['u']) { x = 1.0; th = 1.0; }
            else if (activeKeys['o']) { x = 1.0; th = -1.0; }
            else if (activeKeys['m']) { x = -1.0; th = -1.0; }
            else if (activeKeys['.']) { x = -1.0; th = 1.0; }
        }

        if (activeKeys['k'] || activeKeys['K'] || activeKeys[' ']) {
            x = 0.0; y = 0.0; th = 0.0;
        }

        inputVx = x;
        inputVy = y;
        inputWz = th;
    }

    // Modal Handlers
    helpToggle.addEventListener('click', () => helpModal.classList.remove('hidden'));
    modalClose.addEventListener('click', () => helpModal.classList.add('hidden'));
    window.addEventListener('click', (e) => {
        if (e.target === helpModal) helpModal.classList.add('hidden');
    });

    // --- AUTO EXPLORER CONTROLLER ---
    function sendExplorationCmd(command) {
        if (!wsConnected) return;
        ws.send(JSON.stringify({
            type: 'exploration_cmd',
            command: command
        }));
    }

    document.getElementById('btn-start-explore').addEventListener('click', () => {
        sendExplorationCmd('start');
        valExploreStatus.textContent = 'EXPLORING';
        valExploreStatus.className = 'tel-value text-green';
    });

    document.getElementById('btn-pause-explore').addEventListener('click', () => {
        sendExplorationCmd('pause');
        valExploreStatus.textContent = 'PAUSED';
        valExploreStatus.className = 'tel-value';
    });

    document.getElementById('btn-resume-explore').addEventListener('click', () => {
        sendExplorationCmd('resume');
        valExploreStatus.textContent = 'EXPLORING';
        valExploreStatus.className = 'tel-value text-green';
    });

    document.getElementById('btn-reset-explore').addEventListener('click', () => {
        if (confirm("Reset the exploration progress and target blacklist?")) {
            sendExplorationCmd('reset');
            if (mapCanvas) {
                mapCanvas.updateCentroids([]);
                mapCanvas.updateTarget(null);
            }
            valExploreFrontiers.textContent = '0 clusters';
            valExploreGoal.textContent = 'None';
            valExploreStatus.textContent = 'PAUSED';
            valExploreStatus.className = 'tel-value';
        }
    });

    document.getElementById('btn-set-laps').addEventListener('click', () => {
        const laps = parseInt(lapInput.value);
        if (isNaN(laps) || laps < 1) {
            alert("Please enter a valid number of laps (1 or more).");
            return;
        }
        sendExplorationCmd(`set_laps:${laps}`);
        valExploreLaps.textContent = `${exploreLap} / ${laps}`;
    });

    // --- AUTO NAVIGATION CONTROLLER ---
    function fetchMapList() {
        fetch('/api/list_maps')
            .then(res => res.json())
            .then(data => {
                mapSelect.innerHTML = '';
                if (data.maps && data.maps.length > 0) {
                    data.maps.forEach(map => {
                        const opt = document.createElement('option');
                        opt.value = map;
                        opt.textContent = map;
                        mapSelect.appendChild(opt);
                    });
                    // Automatically load the first map after populating
                    setTimeout(() => {
                        loadStaticMap(data.maps[0]);
                    }, 500);
                } else {
                    const opt = document.createElement('option');
                    opt.value = '';
                    opt.textContent = '-- No Maps Found --';
                    mapSelect.appendChild(opt);
                }
            })
            .catch(err => console.error("Error fetching map list:", err));
    }

    function loadStaticMap(mapName) {
        if (!mapName || !wsConnected) return;
        console.log("Loading static map: " + mapName);
        ws.send(JSON.stringify({
            type: 'load_map',
            map_name: mapName
        }));
    }

    btnLoadMap.addEventListener('click', () => {
        const selectedMap = mapSelect.value;
        if (selectedMap) {
            loadStaticMap(selectedMap);
        } else {
            alert("Please select a map from the dropdown list first.");
        }
    });

    document.getElementById('btn-start-nav').addEventListener('click', () => {
        if (!navMarker) {
            alert("Please click on the map to set a navigation target first.");
            return;
        }
        if (wsConnected) {
            ws.send(JSON.stringify({ type: 'start_nav' }));
            updateNavStatus('NAVIGATING');
        }
    });

    document.getElementById('btn-pause-nav').addEventListener('click', () => {
        if (wsConnected) {
            ws.send(JSON.stringify({ type: 'pause_nav' }));
            updateNavStatus('PAUSED');
        }
    });

    document.getElementById('btn-clear-target').addEventListener('click', () => {
        navMarker = null;
        valNavTarget.textContent = 'None';
        updateNavStatus('IDLE');
        if (wsConnected) {
            ws.send(JSON.stringify({ type: 'clear_nav_target' }));
        }
        if (mapCanvas) mapCanvas.draw();
    });

    // --- MAP MANAGEMENT & DOWNLOADS ---
    function saveMapRobot() {
        if (!wsConnected) return;
        const filename = prompt("Enter file name to save map on the Robot:", "map");
        if (filename) {
            ws.send(JSON.stringify({
                type: 'save_map',
                filename: filename
            }));
            alert(`Map saving command sent to robot as '${filename}'`);
        }
    }

    function resetSlamMap() {
        if (!wsConnected) return;
        if (confirm("⚠️ 注意：確定要重置 SLAM 地圖數據嗎？這會清除當前已掃描的所有資料！")) {
            ws.send(JSON.stringify({ type: 'reset_map' }));
            if (mapCanvas) {
                mapCanvas.centroids = [];
                mapCanvas.target = null;
                mapCanvas.robotPose.active = false;
                mapCanvas.hasMapData = false;
                mapCanvas.ctx.clearRect(0, 0, mapCanvas.canvas.width, mapCanvas.canvas.height);
            }
            mapPlaceholder.classList.remove('hidden');
            mapTelemetry.textContent = 'Map: Resetting...';
            valExploreFrontiers.textContent = '0 clusters';
            valExploreGoal.textContent = 'None';
        }
    }

    function downloadMapPng() {
        if (!mapCanvas || !mapCanvas.hasMapData) {
            alert("No active map data available to download.");
            return;
        }
        const link = document.createElement('a');
        link.download = 'robot_map.png';
        link.href = mapCanvas.canvas.toDataURL('image/png');
        link.click();
    }

    function downloadMapRos() {
        if (confirm("Generate and download ROS 2 map files (PGM + YAML) ZIP package?")) {
            window.location.href = '/api/download_map';
        }
    }

    function downloadTrajectory() {
        window.location.href = '/api/download_trajectory';
    }

    // --- RESET TRAJECTORY HANDLER ---
    function resetTrajectory() {
        if (!wsConnected) return;
        if (confirm("⚠️ 確定要重置路徑軌跡（Trajectory）嗎？這會清除目前的行駛路徑線。")) {
            ws.send(JSON.stringify({
                type: 'reset_trajectory'
            }));
        }
    }

    // Bind action listeners (all buttons duplicated per mode layout)
    document.getElementById('btn-save-robot-teleop').addEventListener('click', saveMapRobot);
    document.getElementById('btn-save-robot-explore').addEventListener('click', saveMapRobot);

    document.getElementById('btn-reset-map-teleop').addEventListener('click', resetSlamMap);
    document.getElementById('btn-reset-map-explore').addEventListener('click', resetSlamMap);

    document.getElementById('btn-download-png-teleop').addEventListener('click', downloadMapPng);
    document.getElementById('btn-download-png-explore').addEventListener('click', downloadMapPng);

    document.getElementById('btn-download-ros-teleop').addEventListener('click', downloadMapRos);
    document.getElementById('btn-download-ros-explore').addEventListener('click', downloadMapRos);

    document.getElementById('btn-download-trajectory-teleop').addEventListener('click', downloadTrajectory);
    document.getElementById('btn-download-trajectory-explore').addEventListener('click', downloadTrajectory);
    document.getElementById('btn-download-trajectory-nav').addEventListener('click', downloadTrajectory);

    // Reset trajectory buttons binding
    document.getElementById('btn-reset-trajectory-teleop').addEventListener('click', resetTrajectory);
    document.getElementById('btn-reset-trajectory-explore').addEventListener('click', resetTrajectory);
    document.getElementById('btn-reset-trajectory-nav').addEventListener('click', resetTrajectory);

    // --- EMERGENCY STOP (GLOBAL) ---
    function estopGlobal() {
        // Send command twists immediately to stop motors
        resetVelocityInputs();
        if (wsConnected && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'cmd_vel', x: 0.0, y: 0.0, th: 0.0 }));
            // Stop exploration node
            ws.send(JSON.stringify({ type: 'exploration_cmd', command: 'stop' }));
            // Clear navigation targets
            ws.send(JSON.stringify({ type: 'clear_nav_target' }));
        }

        // Reset HUD status values
        valVx.textContent = `0.00 m/s`;
        valWz.textContent = `0.00 rad/s`;
        valExploreStatus.textContent = 'STOPPING...';
        valExploreStatus.className = 'tel-value text-red';
        navMarker = null;
        valNavTarget.textContent = 'None';
        updateNavStatus('IDLE');

        // Shake map monitor
        if (canvas) {
            canvas.style.animation = 'none';
            setTimeout(() => { canvas.style.animation = 'shake 0.3s'; }, 10);
        }

        console.warn('GLOBAL EMERGENCY ESTOP PRESSED.');
    }

    document.querySelectorAll('[id^="btn-estop-global"]').forEach(btn => {
        btn.addEventListener('click', estopGlobal);
    });

    // Add keyframes for shake dynamically
    const styleSheet = document.createElement('style');
    styleSheet.innerText = `
        @keyframes shake {
            0% { transform: translate(1px, 1px) rotate(0deg); }
            10% { transform: translate(-1px, -2px) rotate(-1deg); }
            20% { transform: translate(-3px, 0px) rotate(1deg); }
            30% { transform: translate(0px, 2px) rotate(0deg); }
            40% { transform: translate(1px, -1px) rotate(1deg); }
            50% { transform: translate(-1px, 2px) rotate(-1deg); }
            60% { transform: translate(-3px, 1px) rotate(0deg); }
            70% { transform: translate(2px, 1px) rotate(-1deg); }
            80% { transform: translate(-1px, -1px) rotate(1deg); }
            90% { transform: translate(2px, 2px) rotate(0deg); }
            100% { transform: translate(1px, -2px) rotate(0deg); }
        }
    `;
    document.head.appendChild(styleSheet);

    // --- MAP INTERACTION (CLICK TO NAV GOAL) ---
    function onCanvasClick(e, isTouch = false) {
        if (activeMode !== 'navigation') return;
        if (!mapCanvas || !mapCanvas.hasMapData) return;

        const rect = canvas.getBoundingClientRect();
        const clientX = isTouch ? e.touches[0].clientX : e.clientX;
        const clientY = isTouch ? e.touches[0].clientY : e.clientY;

        const clickX = clientX - rect.left;
        const clickY = clientY - rect.top;

        // Convert click screen coordinates to map canvas pixels
        const px = (clickX - mapCanvas.offsetX) / mapCanvas.zoom;
        const py = (clickY - mapCanvas.offsetY) / mapCanvas.zoom;

        // Convert map pixels to world coordinates (in meters)
        const wx = px * mapCanvas.resolution + mapCanvas.originX;
        const wy = (mapCanvas.mapHeight - 1 - py) * mapCanvas.resolution + mapCanvas.originY;

        // Click-again to delete target
        if (navMarker) {
            const dist = Math.hypot(wx - navMarker.x, wy - navMarker.y);
            if (dist < 0.3) {
                navMarker = null;
                valNavTarget.textContent = 'None';
                updateNavStatus('IDLE');
                if (wsConnected) {
                    ws.send(JSON.stringify({ type: 'clear_nav_target' }));
                }
                mapCanvas.draw();
                return;
            }
        }

        // Set target marker
        navMarker = { x: wx, y: wy };
        valNavTarget.textContent = `(${wx.toFixed(2)}, ${wy.toFixed(2)})`;
        if (wsConnected) {
            ws.send(JSON.stringify({
                type: 'set_nav_target',
                x: wx,
                y: wy
            }));
        }
        mapCanvas.draw();
    }

    // Mouse and Touch Canvas Click handling
    let isDragging = false;
    let startX, startY;

    canvas.addEventListener('mousedown', (e) => {
        isDragging = false;
        startX = e.clientX;
        startY = e.clientY;
    });

    canvas.addEventListener('mousemove', (e) => {
        if (Math.hypot(e.clientX - startX, e.clientY - startY) > 5) {
            isDragging = true;
        }
    });

    canvas.addEventListener('mouseup', (e) => {
        if (!isDragging) {
            onCanvasClick(e);
        }
    });

    canvas.addEventListener('touchstart', (e) => {
        if (e.touches.length === 1) {
            isDragging = false;
            startX = e.touches[0].clientX;
            startY = e.touches[0].clientY;
        }
    });

    canvas.addEventListener('touchmove', (e) => {
        if (e.touches.length === 1) {
            if (Math.hypot(e.touches[0].clientX - startX, e.touches[0].clientY - startY) > 5) {
                isDragging = true;
            }
        }
    });

    canvas.addEventListener('touchend', (e) => {
        if (!isDragging) {
            onCanvasClick({ touches: [{ clientX: startX, clientY: startY }] }, true);
        }
    });

    // --- SETUP SYSTEM ---
    mapCanvas = new MapCanvas('map-canvas', {
        showCentroids: false,
        showTarget: false,
        onDraw: (ctx, cv) => {
            // Draw navigation target marker
            if (activeMode === 'navigation' && navMarker) {
                const mx = (navMarker.x - cv.originX) / cv.resolution;
                const my = cv.mapHeight - 1 - (navMarker.y - cv.originY) / cv.resolution;
                const pulse = 10 + Math.sin(Date.now() / 150) * 3;

                // Pulsing ring
                ctx.beginPath();
                ctx.arc(mx, my, pulse / cv.zoom, 0, 2 * Math.PI);
                ctx.strokeStyle = 'rgba(245, 158, 11, 0.6)';
                ctx.lineWidth = 2.5 / cv.zoom;
                ctx.stroke();

                // Core pin
                ctx.beginPath();
                ctx.arc(mx, my, 5 / cv.zoom, 0, 2 * Math.PI);
                ctx.fillStyle = '#f59e0b';
                ctx.strokeStyle = '#ffffff';
                ctx.lineWidth = 1 / cv.zoom;
                ctx.fill();
                ctx.stroke();
            }
        }
    });

    // Load initial mode from server template injection
    const initMode = rootContainer ? rootContainer.getAttribute('data-initial-mode') : 'teleop';
    switchMode(initMode || 'teleop');

    // Start WebSocket
    connect();

    // Start Teleop Command loop (10Hz)
    commandInterval = setInterval(sendCommand, 100);

    // Start UI Animation Loop (smooth rendering & pulses)
    function animationLoop() {
        if (mapCanvas && mapCanvas.hasMapData) {
            mapCanvas.draw();
        }
        requestAnimationFrame(animationLoop);
    }
    requestAnimationFrame(animationLoop);
});
