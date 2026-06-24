// static/js/explorer.js
// WebSocket and Canvas controller for Thor Autonomous Exploration

(function() {
    let ws;
    let wsConnected = false;
    let reconnectTimeout = null;

    // Canvas state variables
    let zoom = 1.0;
    let offsetX = 0.0;
    let offsetY = 0.0;
    let isDragging = false;
    let startDragX = 0;
    let startDragY = 0;
    let touchStartDist = 0;
    let touchStartZoom = 1.0;

    // Robot state cache
    const robotPose = {
        x: 0.0,
        y: 0.0,
        yaw: 0.0,
        active: false
    };

    // Map cache variables
    let mapWidth = 0;
    let mapHeight = 0;
    let resolution = 0.0;
    let originX = 0.0;
    let originY = 0.0;
    let hasMapData = false;

    // Exploration data cache
    let explorationCentroids = [];
    let explorationTarget = null;
    let isPaused = true;
    let currentLap = 1;
    let maxExplorationLaps = 1;
    let explorationComplete = false;
    let robotRadiusM = 0.20;

    // Offscreen Canvas for caching static map rendering
    const offscreenCanvas = document.createElement('canvas');
    const offscreenCtx = offscreenCanvas.getContext('2d');

    // DOM Elements
    const dot = document.getElementById('status-dot');
    const text = document.getElementById('status-text');
    
    const valStatus = document.getElementById('val-status');
    const valGoal = document.getElementById('val-goal');
    const valLaps = document.getElementById('val-laps');
    const valFrontiers = document.getElementById('val-frontiers');
    
    const canvas = document.getElementById('map-canvas');
    const ctx = canvas.getContext('2d');
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
                if (msg.type === 'map') {
                    renderMap(msg);
                } else if (msg.type === 'robot_pose') {
                    robotPose.x = msg.x;
                    robotPose.y = msg.y;
                    robotPose.yaw = msg.yaw;
                    robotPose.active = true;
                    draw();
                } else if (msg.type === 'exploration_status') {
                    explorationCentroids = msg.centroids || [];
                    explorationTarget = msg.target || null;
                    
                    valFrontiers.textContent = `${explorationCentroids.length} clusters`;
                    if (explorationTarget) {
                        valGoal.textContent = `(${explorationTarget.x.toFixed(2)}, ${explorationTarget.y.toFixed(2)})`;
                    } else {
                        valGoal.textContent = 'None';
                    }
                    draw();
                } else if (msg.type === 'exploration_node_status') {
                    isPaused = msg.is_paused;
                    currentLap = msg.current_lap;
                    maxExplorationLaps = msg.max_exploration_laps;
                    explorationComplete = msg.exploration_complete;
                    if (msg.robot_radius !== undefined) {
                        robotRadiusM = msg.robot_radius;
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

    // Map Processing & Cache Generation
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
        
        // Populate offscreen canvas (vertical flip since ROS map starts bottom-left)
        for (let canvas_y = 0; canvas_y < height; canvas_y++) {
            const grid_y = (height - 1) - canvas_y;
            for (let canvas_x = 0; canvas_x < width; canvas_x++) {
                const grid_idx = grid_y * width + canvas_x;
                const canvas_idx = (canvas_y * width + canvas_x) * 4;
                
                const val = bytes[grid_idx];
                
                if (val === 127) {
                    // Unknown: Dark slate blue
                    imgData.data[canvas_idx]     = 30;
                    imgData.data[canvas_idx + 1] = 41;
                    imgData.data[canvas_idx + 2] = 59;
                    imgData.data[canvas_idx + 3] = 255;
                } else if (val === 255) {
                    // Explored free area: Pitch black / deep space
                    imgData.data[canvas_idx]     = 10;
                    imgData.data[canvas_idx + 1] = 15;
                    imgData.data[canvas_idx + 2] = 26;
                    imgData.data[canvas_idx + 3] = 255;
                } else {
                    // Obstacles: Neon Cyan glow
                    imgData.data[canvas_idx]     = 0;
                    imgData.data[canvas_idx + 1] = 240;
                    imgData.data[canvas_idx + 2] = 255;
                    imgData.data[canvas_idx + 3] = 255;
                }
            }
        }
        offscreenCtx.putImageData(imgData, 0, 0);
        
        if (!hasMapData) {
            hasMapData = true;
            resetView();
        } else {
            draw();
        }
    }

    // Main Draw Call (Map Rendering Pipeline)
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
        // Translate and Scale (Zoom/Pan)
        ctx.translate(offsetX, offsetY);
        ctx.scale(zoom, zoom);

        // Draw cached map
        ctx.drawImage(offscreenCanvas, 0, 0);

        // Draw exploration features (frontiers & target)
        drawFrontiers();

        // Draw robot pointer
        if (robotPose.active) {
            drawRobot();
        }

        ctx.restore();

        // Draw scale bar in screen space
        drawScaleBar();
    }

    // Draw Robot Beacon
    function drawRobot() {
        const rx = (robotPose.x - originX) / resolution;
        const ry = mapHeight - 1 - (robotPose.y - originY) / resolution;
        const ryaw = robotPose.yaw;

        ctx.save();
        ctx.translate(rx, ry);
        ctx.rotate(-ryaw); // Negative rotation due to flipped Y-coordinates

        // Calculate robot radius in grid cell coordinates (pixels on map)
        let robotRadiusPx = 7;
        if (resolution > 0) {
            robotRadiusPx = robotRadiusM / resolution;
        }

        // Pulsing safety ring (scales with physical radius)
        const pulse = robotRadiusPx * (1.3 + Math.sin(Date.now() / 150) * 0.2);
        ctx.beginPath();
        ctx.arc(0, 0, pulse, 0, 2 * Math.PI);
        ctx.strokeStyle = 'rgba(239, 68, 68, 0.4)';
        ctx.lineWidth = 2 / zoom; // constant line width in screen space
        ctx.stroke();

        // Robot core (represents the physical chassis footprint)
        ctx.beginPath();
        ctx.arc(0, 0, robotRadiusPx, 0, 2 * Math.PI);
        ctx.fillStyle = 'rgba(239, 68, 68, 0.85)';
        ctx.strokeStyle = '#fca5a5';
        ctx.lineWidth = 1.5 / zoom; // constant line width in screen space
        ctx.fill();
        ctx.stroke();

        // Direction Arrow (scales with physical radius)
        const arrowLength = robotRadiusPx;
        ctx.beginPath();
        ctx.moveTo(arrowLength, 0);
        ctx.lineTo(-arrowLength * 0.5, -arrowLength * 0.5);
        ctx.lineTo(-arrowLength * 0.15, 0);
        ctx.lineTo(-arrowLength * 0.5, arrowLength * 0.5);
        ctx.closePath();
        ctx.fillStyle = '#ffffff';
        ctx.fill();

        ctx.restore();
    }

    // Draw Frontiers & Exploration Target
    function drawFrontiers() {
        // Render centroids (Green circles)
        if (explorationCentroids && explorationCentroids.length > 0) {
            explorationCentroids.forEach(c => {
                const cx = (c.x - originX) / resolution;
                const cy = mapHeight - 1 - (c.y - originY) / resolution;
                
                const outerRadius = 5 / zoom;
                const innerRadius = 1.5 / zoom;
                const strokeWidth = 1 / zoom;
                
                ctx.beginPath();
                ctx.arc(cx, cy, outerRadius, 0, 2 * Math.PI);
                ctx.fillStyle = '#22c55e'; // Green
                ctx.strokeStyle = '#86efac';
                ctx.lineWidth = strokeWidth;
                ctx.fill();
                ctx.stroke();
                
                ctx.beginPath();
                ctx.arc(cx, cy, innerRadius, 0, 2 * Math.PI);
                ctx.fillStyle = '#ffffff';
                ctx.fill();
            });
        }

        // Render active target crosshairs (Cyan glow)
        if (explorationTarget) {
            const tx = (explorationTarget.x - originX) / resolution;
            const ty = mapHeight - 1 - (explorationTarget.y - originY) / resolution;
            
            // Pulse outer ring
            const pulse = 12 + Math.sin(Date.now() / 150) * 4;
            ctx.beginPath();
            ctx.arc(tx, ty, pulse, 0, 2 * Math.PI);
            ctx.strokeStyle = 'rgba(6, 182, 212, 0.5)';
            ctx.lineWidth = 2;
            ctx.stroke();
            
            // Center ring
            ctx.beginPath();
            ctx.arc(tx, ty, 8, 0, 2 * Math.PI);
            ctx.strokeStyle = '#06b6d4';
            ctx.lineWidth = 2;
            ctx.stroke();
            
            // Crosshairs
            ctx.beginPath();
            ctx.moveTo(tx - 14, ty);
            ctx.lineTo(tx + 14, ty);
            ctx.moveTo(tx, ty - 14);
            ctx.lineTo(tx, ty + 14);
            ctx.strokeStyle = '#06b6d4';
            ctx.lineWidth = 1.5;
            ctx.stroke();
        }
    }

    // Draw scale bar in screen space
    function drawScaleBar() {
        if (resolution <= 0) return;
        const targetWidthPx = 80;
        const realDistance = (targetWidthPx * resolution) / zoom;
        const niceDistances = [100, 50, 20, 10, 5, 2, 1, 0.5, 0.2, 0.1, 0.05, 0.02, 0.01];
        let selectedDist = niceDistances[niceDistances.length - 1];
        for (let i = 0; i < niceDistances.length; i++) {
            if (niceDistances[i] <= realDistance) {
                selectedDist = niceDistances[i];
                break;
            }
        }
        const scaleWidthPx = (selectedDist * zoom) / resolution;
        const x = 20;
        const y = canvas.height - 20;

        ctx.save();
        ctx.strokeStyle = '#06b6d4';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(x, y);
        ctx.lineTo(x + scaleWidthPx, y);
        ctx.moveTo(x, y - 5);
        ctx.lineTo(x, y + 5);
        ctx.moveTo(x + scaleWidthPx, y - 5);
        ctx.lineTo(x + scaleWidthPx, y + 5);
        ctx.stroke();

        ctx.fillStyle = '#06b6d4';
        ctx.font = 'bold 10px Orbitron, sans-serif';
        ctx.textAlign = 'center';
        const label = selectedDist >= 1 ? `${selectedDist} m` : `${Math.round(selectedDist * 100)} cm`;
        ctx.fillText(label, x + scaleWidthPx / 2, y - 8);
        ctx.restore();
    }

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

    // Pan and Zoom Event Listeners (Mouse & Touch)
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

    canvas.addEventListener('wheel', (e) => {
        e.preventDefault();
        const zoomFactor = 1.15;
        const mouseX = e.offsetX;
        const mouseY = e.offsetY;

        const worldX = (mouseX - offsetX) / zoom;
        const worldY = (mouseY - offsetY) / zoom;

        if (e.deltaY < 0) {
            zoom *= zoomFactor;
        } else {
            zoom /= zoomFactor;
        }
        zoom = Math.max(0.1, Math.min(zoom, 15.0));

        offsetX = mouseX - worldX * zoom;
        offsetY = mouseY - worldY * zoom;
        draw();
    });

    // Touch controls for mobile
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
            explorationCentroids = [];
            explorationTarget = null;
            valFrontiers.textContent = '0 clusters';
            valGoal.textContent = 'None';
            valStatus.textContent = 'PAUSED';
            valStatus.className = 'tel-value';
            draw();
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
            hasMapData = false;
            robotPose.active = false;
            explorationCentroids = [];
            explorationTarget = null;
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            mapPlaceholder.classList.remove('hidden');
            mapTelemetry.textContent = 'Map: Resetting...';
            valFrontiers.textContent = '0 clusters';
            valGoal.textContent = 'None';
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

    // Start WebSocket Loop
    connect();

    // Trigger canvas redraw dynamically on browser resize
    window.addEventListener('resize', () => {
        if (hasMapData) draw();
    });

    // Run animation frames for pulsing animations on target beacon
    function animationLoop() {
        if (hasMapData) {
            draw();
        }
        requestAnimationFrame(animationLoop);
    }
    requestAnimationFrame(animationLoop);

})();
