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

    // Map Rendering & Navigation State
    const offscreenCanvas = document.createElement('canvas');
    const offscreenCtx = offscreenCanvas.getContext('2d');
    let originX = 0.0;
    let originY = 0.0;
    let resolution = 0.0;
    let mapWidth = 0;
    let mapHeight = 0;
    let hasMapData = false;

    // Zoom & Pan offset
    let zoom = 1.0;
    let offsetX = 0.0;
    let offsetY = 0.0;
    let isDragging = false;
    let startDragX = 0.0;
    let startDragY = 0.0;

    // Robot Pose beacon
    let robotPose = {
        x: 0.0,
        y: 0.0,
        yaw: 0.0,
        active: false
    };

    // Mobile Pinch-to-zoom state
    let touchStartDist = 0;
    let touchStartZoom = 1.0;

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
                    renderMap(msg);
                } else if (msg.type === 'robot_pose') {
                    robotPose.x = msg.x;
                    robotPose.y = msg.y;
                    robotPose.yaw = msg.yaw;
                    robotPose.active = true;
                    draw();
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
    function renderMap(mapMsg) {
        const width = mapMsg.width;
        const height = mapMsg.height;
        
        mapWidth = width;
        mapHeight = height;
        resolution = mapMsg.resolution;
        originX = mapMsg.origin_x;
        originY = mapMsg.origin_y;
        
        mapTelemetry.innerText = `Map: ${width}x${height} @ ${resolution.toFixed(3)}m/px`;
        mapPlaceholder.classList.add('hidden');
        
        // Decode base64 map data
        const binaryString = atob(mapMsg.data);
        const len = binaryString.length;
        const bytes = new Uint8Array(len);
        for (let i = 0; i < len; i++) {
            bytes[i] = binaryString.charCodeAt(i);
        }
        
        // Setup offscreen canvas
        offscreenCanvas.width = width;
        offscreenCanvas.height = height;
        
        const imgData = offscreenCtx.createImageData(width, height);
        
        // Populate offscreen canvas with vertically-flipped pixels (ROS has origin bottom-left)
        for (let canvas_y = 0; canvas_y < height; canvas_y++) {
            const grid_y = (height - 1) - canvas_y;
            for (let canvas_x = 0; canvas_x < width; canvas_x++) {
                const grid_idx = grid_y * width + canvas_x;
                const canvas_idx = (canvas_y * width + canvas_x) * 4;
                
                const val = bytes[grid_idx];
                
                if (val === 127) {
                    // Unknown area: Clear Slate Blue (medium tone)
                    imgData.data[canvas_idx]     = 30;  // R
                    imgData.data[canvas_idx + 1] = 41;  // G
                    imgData.data[canvas_idx + 2] = 59;  // B
                    imgData.data[canvas_idx + 3] = 255; // A
                } else if (val === 255) {
                    // Explored free area: Pitch Black / Extremely Dark Slate
                    imgData.data[canvas_idx]     = 10;  // R
                    imgData.data[canvas_idx + 1] = 15;  // G
                    imgData.data[canvas_idx + 2] = 26;  // B
                    imgData.data[canvas_idx + 3] = 255; // A
                } else {
                    // Obstacles / Occupied: Glowing Neon Cyan
                    imgData.data[canvas_idx]     = 0;   // R
                    imgData.data[canvas_idx + 1] = 240; // G
                    imgData.data[canvas_idx + 2] = 255; // B
                    imgData.data[canvas_idx + 3] = 255; // A
                }
            }
        }
        offscreenCtx.putImageData(imgData, 0, 0);
        
        // Auto-center on first receive
        if (!hasMapData) {
            hasMapData = true;
            resetView();
        } else {
            draw();
        }
    }

    // MAIN DRAW CALL (Map Canvas Rendering)
    function draw() {
        if (!hasMapData) return;

        // Auto-resize canvas buffer to match client display dimensions
        const rect = canvas.getBoundingClientRect();
        if (canvas.width !== Math.floor(rect.width) || canvas.height !== Math.floor(rect.height)) {
            canvas.width = Math.floor(rect.width);
            canvas.height = Math.floor(rect.height);
        }

        ctx.clearRect(0, 0, canvas.width, canvas.height);

        ctx.save();
        // Apply Pan and Zoom transforms
        ctx.translate(offsetX, offsetY);
        ctx.scale(zoom, zoom);

        // Draw offscreen map buffer
        ctx.drawImage(offscreenCanvas, 0, 0);

        // Draw robot position pointer/beacon if pose is active
        if (robotPose.active) {
            drawRobot();
        }

        ctx.restore();

        // Draw scale bar in screen coordinates (not affected by zoom)
        drawScaleBar();
    }

    // DRAW ROBOT BEACON
    function drawRobot() {
        // Calculate grid coords from real-world (x, y) coordinates
        const rx = (robotPose.x - originX) / resolution;
        const ry = mapHeight - 1 - (robotPose.y - originY) / resolution;
        const ryaw = robotPose.yaw;

        ctx.save();
        ctx.translate(rx, ry);
        ctx.rotate(-ryaw); // Rotate by negative yaw due to vertically flipped grid coords

        // 1. Draw glowing outer pulsing ring
        const pulse = 10 + Math.sin(Date.now() / 120) * 3;
        ctx.beginPath();
        ctx.arc(0, 0, pulse, 0, 2 * Math.PI);
        ctx.strokeStyle = 'rgba(239, 68, 68, 0.45)';
        ctx.lineWidth = 2.5;
        ctx.stroke();

        // 2. Draw robot core circle
        ctx.beginPath();
        ctx.arc(0, 0, 7, 0, 2 * Math.PI);
        ctx.fillStyle = '#ef4444'; // Glowing Red
        ctx.strokeStyle = '#fca5a5';
        ctx.lineWidth = 1.5;
        ctx.fill();
        ctx.stroke();

        // 3. Draw direction pointer arrow pointing towards positive X axis (0 deg yaw)
        ctx.beginPath();
        ctx.moveTo(7, 0);
        ctx.lineTo(-4, -5);
        ctx.lineTo(-1, 0);
        ctx.lineTo(-4, 5);
        ctx.closePath();
        ctx.fillStyle = '#ffffff';
        ctx.fill();

        ctx.restore();
    }

    // DRAW DYNAMIC SCALE BAR
    function drawScaleBar() {
        if (resolution <= 0) return;

        // Target bar width on screen (~80px)
        const targetWidthPx = 80;
        // Compute real-world distance in meters that fits targetWidthPx at current zoom
        const realDistance = (targetWidthPx * resolution) / zoom;

        // Choose a clean rounded scale distance
        const niceDistances = [100, 50, 20, 10, 5, 2, 1, 0.5, 0.2, 0.1, 0.05, 0.02, 0.01];
        let selectedDist = niceDistances[niceDistances.length - 1];
        for (let i = 0; i < niceDistances.length; i++) {
            if (niceDistances[i] <= realDistance) {
                selectedDist = niceDistances[i];
                break;
            }
        }

        // Calculate exact scale width on canvas in pixels for selectedDist
        const scaleWidthPx = (selectedDist * zoom) / resolution;

        const x = 20;
        const y = canvas.height - 20;

        ctx.save();
        ctx.strokeStyle = '#06b6d4'; // Cyan
        ctx.lineWidth = 2;

        // Draw horizontal line with edge ticks
        ctx.beginPath();
        ctx.moveTo(x, y);
        ctx.lineTo(x + scaleWidthPx, y);
        ctx.moveTo(x, y - 5);
        ctx.lineTo(x, y + 5);
        ctx.moveTo(x + scaleWidthPx, y - 5);
        ctx.lineTo(x + scaleWidthPx, y + 5);
        ctx.stroke();

        // Draw scale label
        ctx.fillStyle = '#06b6d4';
        ctx.font = 'bold 10px Orbitron, sans-serif';
        ctx.textAlign = 'center';

        const label = selectedDist >= 1 ? `${selectedDist} m` : `${Math.round(selectedDist * 100)} cm`;
        ctx.fillText(label, x + scaleWidthPx / 2, y - 8);

        ctx.restore();
    }

    // RESET ZOOM / PAN AUTO-CENTER
    function resetView() {
        const rect = canvas.getBoundingClientRect();
        canvas.width = Math.floor(rect.width);
        canvas.height = Math.floor(rect.height);

        const scaleX = canvas.width / mapWidth;
        const scaleY = canvas.height / mapHeight;
        zoom = Math.min(scaleX, scaleY) * 0.95;
        
        offsetX = (canvas.width - mapWidth * zoom) / 2;
        offsetY = (canvas.height - mapHeight * zoom) / 2;
        
        draw();
    }

    // MOUSE DRAG/PAN EVENTS ON CANVAS
    canvas.addEventListener('mousedown', (e) => {
        isDragging = true;
        startDragX = e.clientX - offsetX;
        startDragY = e.clientY - offsetY;
    });

    document.addEventListener('mousemove', (e) => {
        if (isDragging) {
            offsetX = e.clientX - startDragX;
            offsetY = e.clientY - startDragY;
            draw();
        }
    });

    document.addEventListener('mouseup', () => {
        isDragging = false;
    });

    // MOUSE WHEEL ZOOM EVENT
    canvas.addEventListener('wheel', (e) => {
        e.preventDefault();
        const zoomFactor = 1.15;
        const mouseX = e.offsetX;
        const mouseY = e.offsetY;

        // Compute world coordinates before zooming
        const worldX = (mouseX - offsetX) / zoom;
        const worldY = (mouseY - offsetY) / zoom;

        if (e.deltaY < 0) {
            zoom *= zoomFactor;
        } else {
            zoom /= zoomFactor;
        }
        zoom = Math.max(0.1, Math.min(zoom, 15.0));

        // Adjust offsets to zoom centered on mouse pointer
        offsetX = mouseX - worldX * zoom;
        offsetY = mouseY - worldY * zoom;

        draw();
    });

    // TOUCH PAN & PINCH-TO-ZOOM (Mobile)
    canvas.addEventListener('touchstart', (e) => {
        if (e.touches.length === 1) {
            isDragging = true;
            startDragX = e.touches[0].clientX - offsetX;
            startDragY = e.touches[0].clientY - offsetY;
        } else if (e.touches.length === 2) {
            isDragging = false;
            touchStartDist = Math.hypot(
                e.touches[0].clientX - e.touches[1].clientX,
                e.touches[0].clientY - e.touches[1].clientY
            );
            touchStartZoom = zoom;
        }
    });

    canvas.addEventListener('touchmove', (e) => {
        if (isDragging && e.touches.length === 1) {
            offsetX = e.touches[0].clientX - startDragX;
            offsetY = e.touches[0].clientY - startDragY;
            draw();
            e.preventDefault();
        } else if (e.touches.length === 2) {
            const dist = Math.hypot(
                e.touches[0].clientX - e.touches[1].clientX,
                e.touches[0].clientY - e.touches[1].clientY
            );
            const factor = dist / touchStartDist;

            // Target coordinates centered between two fingers
            const midX = (e.touches[0].clientX + e.touches[1].clientX) / 2;
            const midY = (e.touches[0].clientY + e.touches[1].clientY) / 2;

            const rect = canvas.getBoundingClientRect();
            const canvasMidX = midX - rect.left;
            const canvasMidY = midY - rect.top;

            const worldX = (canvasMidX - offsetX) / zoom;
            const worldY = (canvasMidY - offsetY) / zoom;

            zoom = Math.max(0.1, Math.min(touchStartZoom * factor, 15.0));
            offsetX = canvasMidX - worldX * zoom;
            offsetY = canvasMidY - worldY * zoom;

            draw();
            e.preventDefault();
        }
    }, { passive: false });

    canvas.addEventListener('touchend', () => {
        isDragging = false;
    });

    // FLOATING ZOOM BUTTON EVENTS
    document.getElementById('btn-zoom-in').addEventListener('click', () => {
        const midX = canvas.width / 2;
        const midY = canvas.height / 2;
        const worldX = (midX - offsetX) / zoom;
        const worldY = (midY - offsetY) / zoom;
        
        zoom = Math.min(zoom * 1.3, 15.0);
        offsetX = midX - worldX * zoom;
        offsetY = midY - worldY * zoom;
        draw();
    });

    document.getElementById('btn-zoom-out').addEventListener('click', () => {
        const midX = canvas.width / 2;
        const midY = canvas.height / 2;
        const worldX = (midX - offsetX) / zoom;
        const worldY = (midY - offsetY) / zoom;

        zoom = Math.max(zoom / 1.3, 0.1);
        offsetX = midX - worldX * zoom;
        offsetY = midY - worldY * zoom;
        draw();
    });

    document.getElementById('btn-zoom-reset').addEventListener('click', () => {
        resetView();
    });

    // WINDOW RESIZE
    window.addEventListener('resize', () => {
        draw();
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
    setupDpadButton('btn-linear-left', () => { if(isHolonomic) inputVy = 1.0; }, () => { inputVy = 0.0; });
    setupDpadButton('btn-linear-right', () => { if(isHolonomic) inputVy = -1.0; }, () => { inputVy = 0.0; });
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
    connect();
    
    // Command sending loop runs every 100ms
    commandInterval = setInterval(sendCommand, 100);
    
    // Redraw loop on a regular interval to support beacon pulsing animation
    setInterval(() => {
        if (robotPose.active) {
            draw();
        }
    }, 150);
});
