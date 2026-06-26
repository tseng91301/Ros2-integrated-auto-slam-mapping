// static/js/navigation.js
// WebSocket and Canvas controller for Thor Autonomous Navigation

(function () {
    let ws;
    let wsConnected = false;
    let reconnectTimeout = null;

    // Reusable Map Canvas Controller
    let mapCanvas = null;

    // Navigation target marker state
    let navMarker = null;

    // DOM Elements
    const dot = document.getElementById('status-dot');
    const text = document.getElementById('status-text');

    const valStatus = document.getElementById('val-status');
    const valTarget = document.getElementById('val-target');
    const valPose = document.getElementById('val-pose');

    const mapPlaceholder = document.getElementById('map-placeholder');
    const mapTelemetry = document.getElementById('map-telemetry');

    const mapSelect = document.getElementById('map-select');
    const btnLoadMap = document.getElementById('btn-load-map');

    // Button controls
    const btnStartNav = document.getElementById('btn-start-nav');
    const btnPauseNav = document.getElementById('btn-pause-nav');
    const btnClearTarget = document.getElementById('btn-clear-target');
    const btnEstopNav = document.getElementById('btn-estop-nav');

    // Fetch available maps on backend startup
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
                    // Automatically load the first map if one is present
                    setTimeout(() => {
                        loadMap(data.maps[0]);
                    }, 500);
                } else {
                    const opt = document.createElement('option');
                    opt.value = '';
                    opt.textContent = '-- No Maps Found --';
                    mapSelect.appendChild(opt);
                }
            })
            .catch(err => {
                console.error("Error fetching map list:", err);
            });
    }

    // Trigger map loading on the backend
    function loadMap(mapName) {
        if (!mapName || !wsConnected) return;
        console.log("Loading static map: " + mapName);
        ws.send(JSON.stringify({
            type: 'load_map',
            map_name: mapName
        }));
    }

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
            
            // Set socket mode to navigation
            ws.send(JSON.stringify({
                type: 'set_mode',
                mode: 'navigation'
            }));

            // Fetch maps list once WS is open
            fetchMapList();
            
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
                    if (mapCanvas) mapCanvas.updateMap(msg);
                } else if (msg.type === 'robot_pose') {
                    if (mapCanvas) mapCanvas.updateRobotPose(msg);
                    valPose.textContent = `(${msg.x.toFixed(2)}, ${msg.y.toFixed(2)}) @ ${(msg.yaw * 180 / Math.PI).toFixed(0)}°`;
                } else if (msg.type === 'nav_target') {
                    if (msg.x !== null && msg.x !== undefined && msg.y !== null && msg.y !== undefined) {
                        navMarker = { x: msg.x, y: msg.y };
                        valTarget.textContent = `(${msg.x.toFixed(2)}, ${msg.y.toFixed(2)})`;
                    } else {
                        navMarker = null;
                        valTarget.textContent = 'None';
                    }
                    
                    if (msg.status) {
                        updateNavStatus(msg.status);
                    }
                } else if (msg.type === 'nav_status') {
                    updateNavStatus(msg.status);
                    if (msg.status === 'ARRIVED') {
                        // Automatically clear target marker on arrival
                        navMarker = null;
                        valTarget.textContent = 'None';
                        if (mapCanvas) mapCanvas.draw();
                    }
                }
            } catch (e) {
                console.error('Error parsing WS message:', e);
            }
        };
    }

    function updateNavStatus(status) {
        valStatus.textContent = status;
        if (status === 'NAVIGATING') {
            valStatus.className = 'tel-value text-amber';
        } else if (status === 'ARRIVED') {
            valStatus.textContent = 'ARRIVED';
            valStatus.className = 'tel-value text-green';
        } else if (status === 'PAUSED') {
            valStatus.className = 'tel-value text-cyan';
        } else {
            valStatus.className = 'tel-value';
        }
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

    // Map selection click trigger
    btnLoadMap.addEventListener('click', () => {
        const selectedMap = mapSelect.value;
        if (selectedMap) {
            loadMap(selectedMap);
        } else {
            alert("Please select a map from the dropdown list first.");
        }
    });

    // Navigation triggers
    btnStartNav.addEventListener('click', () => {
        if (!navMarker) {
            alert("Please click on the map to set a navigation target first.");
            return;
        }
        if (wsConnected) {
            ws.send(JSON.stringify({ type: 'start_nav' }));
            updateNavStatus('NAVIGATING');
        }
    });

    btnPauseNav.addEventListener('click', () => {
        if (wsConnected) {
            ws.send(JSON.stringify({ type: 'pause_nav' }));
            updateNavStatus('PAUSED');
        }
    });

    btnClearTarget.addEventListener('click', () => {
        navMarker = null;
        valTarget.textContent = 'None';
        updateNavStatus('IDLE');
        if (wsConnected) {
            ws.send(JSON.stringify({ type: 'clear_nav_target' }));
        }
        if (mapCanvas) mapCanvas.draw();
    });

    btnEstopNav.addEventListener('click', () => {
        navMarker = null;
        valTarget.textContent = 'None';
        updateNavStatus('IDLE');
        if (wsConnected) {
            ws.send(JSON.stringify({ type: 'clear_nav_target' }));
        }
        if (mapCanvas) mapCanvas.draw();
        console.warn("EMERGENCY ESTOP PRESSED.");
    });

    // Startup map canvas setup
    mapCanvas = new MapCanvas('map-canvas', {
        showCentroids: false,
        showTarget: false,
        onDraw: (ctx, canvas) => {
            // Draw navigation target marker if it exists
            if (navMarker) {
                const mx = (navMarker.x - canvas.originX) / canvas.resolution;
                const my = canvas.mapHeight - 1 - (navMarker.y - canvas.originY) / canvas.resolution;
                
                // Pulsing ring animation
                const pulse = 10 + Math.sin(Date.now() / 150) * 3;
                
                // Outer ring
                ctx.beginPath();
                ctx.arc(mx, my, pulse / canvas.zoom, 0, 2 * Math.PI);
                ctx.strokeStyle = 'rgba(245, 158, 11, 0.6)'; // pulsing amber
                ctx.lineWidth = 2.5 / canvas.zoom;
                ctx.stroke();
                
                // Inner solid pin
                ctx.beginPath();
                ctx.arc(mx, my, 5 / canvas.zoom, 0, 2 * Math.PI);
                ctx.fillStyle = '#f59e0b';
                ctx.strokeStyle = '#ffffff';
                ctx.lineWidth = 1 / canvas.zoom;
                ctx.fill();
                ctx.stroke();
            }
        }
    });

    // Map canvas click handling (translate screen clicks to world coords)
    const canvasElement = document.getElementById('map-canvas');
    let isDragging = false;
    let startX, startY;

    canvasElement.addEventListener('mousedown', (e) => {
        isDragging = false;
        startX = e.clientX;
        startY = e.clientY;
    });

    canvasElement.addEventListener('mousemove', (e) => {
        if (Math.hypot(e.clientX - startX, e.clientY - startY) > 5) {
            isDragging = true;
        }
    });

    canvasElement.addEventListener('mouseup', (e) => {
        if (isDragging) return; // ignore dragging behavior

        if (!mapCanvas || !mapCanvas.hasMapData) return;

        // Get click coordinate relative to canvas
        const rect = canvasElement.getBoundingClientRect();
        const clickX = e.clientX - rect.left;
        const clickY = e.clientY - rect.top;

        // Map screen pixels to world coordinates
        const px = (clickX - mapCanvas.offsetX) / mapCanvas.zoom;
        const py = (clickY - mapCanvas.offsetY) / mapCanvas.zoom;

        const wx = px * mapCanvas.resolution + mapCanvas.originX;
        const wy = (mapCanvas.mapHeight - 1 - py) * mapCanvas.resolution + mapCanvas.originY;

        // Click-again check to delete target
        if (navMarker) {
            const dist = Math.hypot(wx - navMarker.x, wy - navMarker.y);
            if (dist < 0.3) {
                navMarker = null;
                valTarget.textContent = 'None';
                updateNavStatus('IDLE');
                if (wsConnected) {
                    ws.send(JSON.stringify({ type: 'clear_nav_target' }));
                }
                mapCanvas.draw();
                return;
            }
        }

        // Place new target coordinate
        navMarker = { x: wx, y: wy };
        valTarget.textContent = `(${wx.toFixed(2)}, ${wy.toFixed(2)})`;
        if (wsConnected) {
            ws.send(JSON.stringify({
                type: 'set_nav_target',
                x: wx,
                y: wy
            }));
        }
        mapCanvas.draw();
    });

    // Touch support (tablets / mobile devices)
    canvasElement.addEventListener('touchstart', (e) => {
        if (e.touches.length === 1) {
            isDragging = false;
            startX = e.touches[0].clientX;
            startY = e.touches[0].clientY;
        }
    });

    canvasElement.addEventListener('touchmove', (e) => {
        if (e.touches.length === 1) {
            if (Math.hypot(e.touches[0].clientX - startX, e.touches[0].clientY - startY) > 5) {
                isDragging = true;
            }
        }
    });

    canvasElement.addEventListener('touchend', (e) => {
        if (isDragging) return;
        if (!mapCanvas || !mapCanvas.hasMapData) return;

        const rect = canvasElement.getBoundingClientRect();
        const touchX = startX - rect.left;
        const touchY = startY - rect.top;

        const px = (touchX - mapCanvas.offsetX) / mapCanvas.zoom;
        const py = (touchY - mapCanvas.offsetY) / mapCanvas.zoom;

        const wx = px * mapCanvas.resolution + mapCanvas.originX;
        const wy = (mapCanvas.mapHeight - 1 - py) * mapCanvas.resolution + mapCanvas.originY;

        if (navMarker) {
            const dist = Math.hypot(wx - navMarker.x, wy - navMarker.y);
            if (dist < 0.3) {
                navMarker = null;
                valTarget.textContent = 'None';
                updateNavStatus('IDLE');
                if (wsConnected) {
                    ws.send(JSON.stringify({ type: 'clear_nav_target' }));
                }
                mapCanvas.draw();
                return;
            }
        }

        navMarker = { x: wx, y: wy };
        valTarget.textContent = `(${wx.toFixed(2)}, ${wy.toFixed(2)})`;
        if (wsConnected) {
            ws.send(JSON.stringify({
                type: 'set_nav_target',
                x: wx,
                y: wy
            }));
        }
        mapCanvas.draw();
    });

    connect();

    // Loop animation frames to keep marker pulse looking smooth
    function animationLoop() {
        if (mapCanvas && mapCanvas.hasMapData) {
            mapCanvas.draw();
        }
        requestAnimationFrame(animationLoop);
    }
    requestAnimationFrame(animationLoop);

})();
