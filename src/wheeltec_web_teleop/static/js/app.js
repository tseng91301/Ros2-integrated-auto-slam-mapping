// Thor Remote Front-end Logic
document.addEventListener('DOMContentLoaded', () => {
    // STATE VARIABLES
    let ws = null;
    let reconnectTimeout = null;
    let wsConnected = false;

    // Limits
    let limitLinear = 0.50;
    let limitAngular = 1.00;
    let isHolonomic = false;

    // Current Input Values
    let inputVx = 0.0;
    let inputVy = 0.0;
    let inputWz = 0.0;

    // Command loop interval
    let commandInterval = null;
    let isMoving = false;
    let stopCommandsSent = 0; // Send stop command a few times then go idle

    // Reusable Map Canvas Controller
    let mapCanvas = null;

    // HTML ELEMENTS
    const dot = document.getElementById('status-dot');
    const text = document.getElementById('status-text');

    const valLimitLinear = document.getElementById('val-limit-linear');
    const valLimitAngular = document.getElementById('val-limit-angular');
    const valVx = document.getElementById('val-vx');
    const valWz = document.getElementById('val-wz');

    const sliderLinear = document.getElementById('slider-linear');
    const sliderAngular = document.getElementById('slider-angular');
    const valSliderLinear = document.getElementById('val-slider-linear');
    const valSliderAngular = document.getElementById('val-slider-angular');

    const checkHolonomic = document.getElementById('check-holonomic');
    const leftModeIndicator = document.getElementById('left-mode-indicator');

    const canvas = document.getElementById('map-canvas');
    const ctx = canvas.getContext('2d');
    const mapPlaceholder = document.getElementById('map-placeholder');
    const mapTelemetry = document.getElementById('map-telemetry');

    // Collision elements
    const collisionAlert = document.getElementById('collision-alert');
    const collisionSectors = document.getElementById('collision-sectors');
    const monitorScreen = document.querySelector('.monitor-screen');

    // Grips switches
    const toggleLeft = document.getElementById('toggle-left-control');
    const leftJoystickContainer = document.getElementById('left-joystick-container');
    const leftDpad = document.getElementById('left-dpad');

    const toggleRight = document.getElementById('toggle-right-control');
    const rightJoystickContainer = document.getElementById('right-joystick-container');
    const rightDpad = document.getElementById('right-dpad');

    // Actions
    const btnSaveRobot = document.getElementById('btn-save-robot');
    const btnResetMap = document.getElementById('btn-reset-map');
    const btnDownloadPng = document.getElementById('btn-download-png');
    const btnDownloadRos = document.getElementById('btn-download-ros');
    const btnEstop = document.getElementById('btn-estop');

    // Modal
    const helpToggle = document.getElementById('help-toggle');
    const helpModal = document.getElementById('help-modal');
    const modalClose = document.getElementById('modal-close');

    // WEBSOCKET COMMUNICATION
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

            // Retry connection
            reconnectTimeout = setTimeout(connect, 2000);
        };

        ws.onerror = (err) => {
            console.error('WebSocket error:', err);
        };

        ws.onmessage = (event) => {
            try {
                const msg = JSON.parse(event.data);
                if (msg.type === 'map') {
                    if (mapCanvas) mapCanvas.updateMap(msg);
                } else if (msg.type === 'robot_pose') {
                    if (mapCanvas) mapCanvas.updateRobotPose(msg);
                } else if (msg.type === 'collision') {
                    handleCollisionAlert(msg);
                }
            } catch (e) {
                console.error('Error parsing WS message:', e);
            }
        };
    }

    // Collision Alert Handler
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

    // MAP PROCESSING
    // Map Zoom button event listeners
    document.getElementById('btn-zoom-in').addEventListener('click', () => {
        if (mapCanvas) mapCanvas.zoomIn();
    });

    document.getElementById('btn-zoom-out').addEventListener('click', () => {
        if (mapCanvas) mapCanvas.zoomOut();
    });

    document.getElementById('btn-zoom-reset').addEventListener('click', () => {
        if (mapCanvas) mapCanvas.resetView();
    });

    // TRANSMIT SPEED COMMANDS
    function sendCommand() {
        if (!wsConnected || ws.readyState !== WebSocket.OPEN) return;

        // Determine if robot is active
        const hasInput = (Math.abs(inputVx) > 0.01 || Math.abs(inputVy) > 0.01 || Math.abs(inputWz) > 0.01);

        if (hasInput) {
            isMoving = true;
            stopCommandsSent = 0;

            // Apply scale limits
            const x = inputVx * limitLinear;
            const y = inputVy * limitLinear;
            const th = inputWz * limitAngular;

            ws.send(JSON.stringify({
                type: 'cmd_vel',
                x: x,
                y: y,
                th: th
            }));

            // Update HUD
            valVx.textContent = `${(x).toFixed(2)} m/s`;
            valWz.textContent = `${(th).toFixed(2)} rad/s`;
        } else {
            if (isMoving) {
                // Send zero velocities a few times to ensure the robot stops
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

    // JOYSTICK LOGIC HELPER
    function makeJoystick(containerId, handleId, onUpdate) {
        const container = document.getElementById(containerId);
        const handle = document.getElementById(handleId);

        let dragActive = false;
        let startX, startY;
        let limit = 50; // Drag boundary radius in px

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

            // Normalized values -1.0 to 1.0
            const normX = deltaX / limit;
            const normY = deltaY / limit;

            onUpdate(normX, normY);
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

    // INITIALIZE JOYSTICKS
    // Left Joystick: Controls Linear translation X (Forward/Backward) and Y (Strafing left/right)
    makeJoystick('left-joystick-container', 'left-joystick-handle', (nx, ny) => {
        inputVx = -ny; // Dragging up yields negative ny -> positive vx
        if (isHolonomic) {
            inputVy = -nx; // Dragging left yields negative nx -> positive vy
        } else {
            inputVy = 0.0;
        }
    });

    // Right Joystick: Controls Angular Steering Z (Rotate left/right)
    makeJoystick('right-joystick-container', 'right-joystick-handle', (nx, ny) => {
        inputWz = -nx; // Dragging left yields negative nx -> positive wz (rotate CCW)
    });

    // CONTROL TOGGLES (JOYSTICK / DPAD SWITCH)
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

    // D-PAD BUTTON EVENTS
    // Left D-pad (Linear translations)
    setupDpadButton('btn-linear-forward', () => { inputVx = 1.0; }, () => { inputVx = 0.0; });
    setupDpadButton('btn-linear-backward', () => { inputVx = -1.0; }, () => { inputVx = 0.0; });
    setupDpadButton('btn-linear-left', () => { if (isHolonomic) inputVy = 1.0; }, () => { inputVy = 0.0; });
    setupDpadButton('btn-linear-right', () => { if (isHolonomic) inputVy = -1.0; }, () => { inputVy = 0.0; });
    document.getElementById('btn-linear-stop').addEventListener('click', () => {
        resetVelocityInputs();
    });

    // Right D-pad (Angular steering)
    setupDpadButton('btn-turn-left', () => { inputWz = 1.0; }, () => { inputWz = 0.0; });
    setupDpadButton('btn-turn-right', () => { inputWz = -1.0; }, () => { inputWz = 0.0; });
    document.getElementById('btn-angular-stop').addEventListener('click', () => {
        inputWz = 0.0;
    });

    function setupDpadButton(id, onStart, onEnd) {
        const btn = document.getElementById(id);

        btn.addEventListener('mousedown', onStart);
        btn.addEventListener('mouseup', onEnd);
        btn.addEventListener('mouseleave', onEnd);

        btn.addEventListener('touchstart', (e) => {
            onStart();
            e.preventDefault();
        }, { passive: false });
        btn.addEventListener('touchend', onEnd);
    }

    // LIMIT SLIDERS
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

    // HOLONOMIC SELECTOR
    checkHolonomic.addEventListener('change', (e) => {
        isHolonomic = e.target.checked;
        leftModeIndicator.textContent = isHolonomic ? "Mode: Holonomic (Strafing)" : "Mode: Non-Holonomic";
        resetVelocityInputs();
    });

    // EMERGENCY STOP
    btnEstop.addEventListener('click', () => {
        resetVelocityInputs();
        if (wsConnected && ws.readyState === WebSocket.OPEN) {
            // Force zero velocities immediately
            ws.send(JSON.stringify({ type: 'cmd_vel', x: 0.0, y: 0.0, th: 0.0 }));
        }
        valVx.textContent = `0.00 m/s`;
        valWz.textContent = `0.00 rad/s`;

        // Animate screen shake or warning
        canvas.style.animation = 'none';
        setTimeout(() => {
            canvas.style.animation = 'shake 0.3s';
        }, 10);

        console.warn('EMERGENCY STOP PRESSED.');
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

    // ACTIONS (SAVE / RESET / DOWNLOAD)
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
            // Clear current map states
            hasMapData = false;
            robotPose.active = false;
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            mapPlaceholder.classList.remove('hidden');
            mapTelemetry.textContent = 'Map: Resetting...';
        }
    });

    btnDownloadPng.addEventListener('click', () => {
        if (!hasMapData) {
            alert("No active map data available to download.");
            return;
        }
        const link = document.createElement('a');
        link.download = 'robot_map.png';
        link.href = canvas.toDataURL('image/png');
        link.click();
    });

    btnDownloadRos.addEventListener('click', () => {
        if (confirm("Generate and download ROS 2 map files (PGM + YAML) ZIP package?")) {
            window.location.href = '/api/download_map';
        }
    });

    // KEYBOARD REMOTE CONTROL BINDINGS (Original keyboard keys mapping)
    // Keys mapping: i (forward), , (backward), j (left), l (right), u (f-left), o (f-right), m (b-left), . (b-right)
    // Holonomic Shift bindings: I, <, J, L, U, O, M, >
    const activeKeys = {};

    window.addEventListener('keydown', (e) => {
        if (e.target.tagName === 'INPUT') return; // Ignore inputs

        activeKeys[e.key] = true;
        updateKeyboardInput();

        // Prevent default browser scrolling
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

        // Forward/backward
        if (activeKeys['i'] || activeKeys['I'] || activeKeys['ArrowUp']) {
            x = 1.0;
        } else if (activeKeys[','] || activeKeys['<'] || activeKeys['ArrowDown']) {
            x = -1.0;
        }

        // Steering or Slide depending on Holonomic/Shift
        if (isShift || isHolonomic) {
            // Holonomic slide mode
            if (activeKeys['j'] || activeKeys['J'] || activeKeys['ArrowLeft']) {
                y = 1.0;
            } else if (activeKeys['l'] || activeKeys['L'] || activeKeys['ArrowRight']) {
                y = -1.0;
            }

            // Diagonals in slide mode
            if (activeKeys['u'] || activeKeys['U']) {
                x = 1.0; y = 1.0;
            } else if (activeKeys['o'] || activeKeys['O']) {
                x = 1.0; y = -1.0;
            } else if (activeKeys['m'] || activeKeys['M']) {
                x = -1.0; y = 1.0;
            } else if (activeKeys['.'] || activeKeys['>']) {
                x = -1.0; y = -1.0;
            }
        } else {
            // Non-holonomic turn mode
            if (activeKeys['j'] || activeKeys['ArrowLeft']) {
                th = 1.0;
            } else if (activeKeys['l'] || activeKeys['ArrowRight']) {
                th = -1.0;
            }

            // Diagonals in non-holonomic mode (curve turns)
            if (activeKeys['u']) {
                x = 1.0; th = 1.0;
            } else if (activeKeys['o']) {
                x = 1.0; th = -1.0;
            } else if (activeKeys['m']) {
                x = -1.0; th = -1.0;
            } else if (activeKeys['.']) {
                x = -1.0; th = 1.0;
            }
        }

        // Stop buttons
        if (activeKeys['k'] || activeKeys['K'] || activeKeys[' ']) {
            x = 0.0;
            y = 0.0;
            th = 0.0;
        }

        // Assign to global inputs
        inputVx = x;
        inputVy = y;
        inputWz = th;
    }

    // MODAL DIALOG TOGGLE
    helpToggle.addEventListener('click', () => {
        helpModal.classList.remove('hidden');
    });

    modalClose.addEventListener('click', () => {
        helpModal.classList.add('hidden');
    });

    window.addEventListener('click', (e) => {
        if (e.target === helpModal) {
            helpModal.classList.add('hidden');
        }
    });

    // STARTUP SYSTEM
    mapCanvas = new MapCanvas('map-canvas');
    connect();

    // Command sending loop runs every 100ms
    commandInterval = setInterval(sendCommand, 100);

    // Redraw loop for pulsing animations
    function animate() {
        if (mapCanvas && mapCanvas.hasMapData) {
            mapCanvas.draw();
        }
        requestAnimationFrame(animate);
    }
    requestAnimationFrame(animate);
});
