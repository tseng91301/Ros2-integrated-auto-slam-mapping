// static/js/map_canvas.js
// Reusable and Generic Canvas Controller for Map & Robot Visualization in ROS 2.

class MapCanvas {
    constructor(canvasId, options = {}) {
        this.canvas = document.getElementById(canvasId);
        if (!this.canvas) {
            console.error(`Canvas with ID '${canvasId}' not found.`);
            return;
        }
        this.ctx = this.canvas.getContext('2d');
        
        // Configuration Options
        this.options = Object.assign({
            robotColor: 'rgba(239, 68, 68, 0.85)',
            robotStrokeColor: '#fca5a5',
            robotRadiusM: 0.20,
            scaleColor: '#06b6d4',
            obstacleColor: [0, 240, 255, 255],     // Neon Cyan
            freeColor: [10, 15, 26, 255],          // Deep Space Black
            unknownColor: [30, 41, 59, 255],       // Dark Slate Blue
            onDraw: null,                           // Callback after map and before robot (world coordinates)
            mapPlaceholderId: 'map-placeholder',
            mapTelemetryId: 'map-telemetry',
            showCentroids: true,
            showTarget: true,
        }, options);

        // Pan & Zoom state
        this.zoom = 1.0;
        this.offsetX = 0.0;
        this.offsetY = 0.0;
        this.isDragging = false;
        this.startDragX = 0;
        this.startDragY = 0;
        this.touchStartDist = 0;
        this.touchStartZoom = 1.0;

        // Robot State
        this.robotPose = { x: 0.0, y: 0.0, yaw: 0.0, active: false };

        // Map State
        this.mapWidth = 0;
        this.mapHeight = 0;
        this.resolution = 0.0;
        this.originX = 0.0;
        this.originY = 0.0;
        this.hasMapData = false;

        // Exploration features state
        this.centroids = [];
        this.target = null;

        // Offscreen cache canvas
        this.offscreenCanvas = document.createElement('canvas');
        this.offscreenCtx = this.offscreenCanvas.getContext('2d');

        // UI elements
        this.mapPlaceholder = document.getElementById(this.options.mapPlaceholderId);
        this.mapTelemetry = document.getElementById(this.options.mapTelemetryId);

        // Bind events
        this.initEvents();
    }

    /**
     * Decodes and caches the OccupancyGrid map data.
     * @param {Object} mapMsg - The map message received via WebSocket.
     */
    updateMap(mapMsg) {
        const width = mapMsg.width;
        const height = mapMsg.height;
        
        this.mapWidth = width;
        this.mapHeight = height;
        this.resolution = mapMsg.resolution;
        this.originX = mapMsg.origin_x;
        this.originY = mapMsg.origin_y;
        
        if (this.mapTelemetry) {
            this.mapTelemetry.innerText = `Map: ${width}x${height} @ ${this.resolution.toFixed(3)}m/px`;
        }
        if (this.mapPlaceholder) {
            this.mapPlaceholder.classList.add('hidden');
        }
        
        // Decode base64 map data
        const binaryString = atob(mapMsg.data);
        const len = binaryString.length;
        const bytes = new Uint8Array(len);
        for (let i = 0; i < len; i++) {
            bytes[i] = binaryString.charCodeAt(i);
        }
        
        // Setup offscreen canvas
        this.offscreenCanvas.width = width;
        this.offscreenCanvas.height = height;
        
        const imgData = this.offscreenCtx.createImageData(width, height);
        
        // Populate offscreen canvas pixels (vertically flipped for ROS)
        for (let canvas_y = 0; canvas_y < height; canvas_y++) {
            const grid_y = (height - 1) - canvas_y;
            for (let canvas_x = 0; canvas_x < width; canvas_x++) {
                const grid_idx = grid_y * width + canvas_x;
                const canvas_idx = (canvas_y * width + canvas_x) * 4;
                
                const val = bytes[grid_idx];
                let color;
                
                if (val === 127) {
                    color = this.options.unknownColor;
                } else if (val === 255) {
                    color = this.options.freeColor;
                } else {
                    color = this.options.obstacleColor;
                }
                
                imgData.data[canvas_idx]     = color[0];
                imgData.data[canvas_idx + 1] = color[1];
                imgData.data[canvas_idx + 2] = color[2];
                imgData.data[canvas_idx + 3] = color[3];
            }
        }
        this.offscreenCtx.putImageData(imgData, 0, 0);
        
        if (!this.hasMapData) {
            this.hasMapData = true;
            this.resetView();
        } else {
            this.draw();
        }
    }

    /**
     * Updates the robot chassis pose coordinates.
     * @param {Object} poseMsg - The robot pose message.
     */
    updateRobotPose(poseMsg) {
        this.robotPose.x = poseMsg.x;
        this.robotPose.y = poseMsg.y;
        this.robotPose.yaw = poseMsg.yaw;
        this.robotPose.active = true;
        this.draw();
    }

    /**
     * Updates centroids (frontier clusters).
     * @param {Array} centroids - Array of {x, y} objects in world coordinates.
     */
    updateCentroids(centroids) {
        this.centroids = centroids || [];
        this.draw();
    }

    /**
     * Updates the active exploration target.
     * @param {Object|null} target - The target {x, y} object in world coordinates.
     */
    updateTarget(target) {
        this.target = target || null;
        this.draw();
    }

    /**
     * Resets the viewport zoom and pans map to center.
     */
    resetView() {
        if (!this.hasMapData) return;
        
        const rect = this.canvas.getBoundingClientRect();
        this.canvas.width = Math.floor(rect.width);
        this.canvas.height = Math.floor(rect.height);

        const scaleX = this.canvas.width / this.mapWidth;
        const scaleY = this.canvas.height / this.mapHeight;
        this.zoom = Math.min(scaleX, scaleY) * 0.95;
        
        this.offsetX = (this.canvas.width - this.mapWidth * this.zoom) / 2;
        this.offsetY = (this.canvas.height - this.mapHeight * this.zoom) / 2;
        
        this.draw();
    }

    zoomIn() {
        const midX = this.canvas.width / 2;
        const midY = this.canvas.height / 2;
        const worldX = (midX - this.offsetX) / this.zoom;
        const worldY = (midY - this.offsetY) / this.zoom;
        this.zoom = Math.min(this.zoom * 1.3, 15.0);
        this.offsetX = midX - worldX * this.zoom;
        this.offsetY = midY - worldY * this.zoom;
        this.draw();
    }

    zoomOut() {
        const midX = this.canvas.width / 2;
        const midY = this.canvas.height / 2;
        const worldX = (midX - this.offsetX) / this.zoom;
        const worldY = (midY - this.offsetY) / this.zoom;
        this.zoom = Math.max(this.zoom / 1.3, 0.1);
        this.offsetX = midX - worldX * this.zoom;
        this.offsetY = midY - worldY * this.zoom;
        this.draw();
    }

    /**
     * Renders the current frame.
     */
    draw() {
        if (!this.hasMapData) return;

        // Sync drawing buffer dimensions with CSS layout
        const rect = this.canvas.getBoundingClientRect();
        if (this.canvas.width !== Math.floor(rect.width) || this.canvas.height !== Math.floor(rect.height)) {
            this.canvas.width = Math.floor(rect.width);
            this.canvas.height = Math.floor(rect.height);
        }

        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

        this.ctx.save();
        // Translate and Scale (Zoom/Pan)
        this.ctx.translate(this.offsetX, this.offsetY);
        this.ctx.scale(this.zoom, this.zoom);

        // Draw cached map
        this.ctx.drawImage(this.offscreenCanvas, 0, 0);

        // Draw exploration features (centroids & target)
        this.drawExplorationFeatures();

        // Execute callback for custom application drawings (Centroids, paths, targets)
        if (this.options.onDraw) {
            this.options.onDraw(this.ctx, this);
        }

        // Draw robot pointer beacon
        if (this.robotPose.active) {
            this.drawRobot();
        }

        this.ctx.restore();

        // Draw Scale bar in screen coordinate space
        this.drawScaleBar();
    }

    /**
     * Draws green centroids and cyan active targets with pulsing crosshairs.
     */
    drawExplorationFeatures() {
        if (this.options.showCentroids && this.centroids && this.centroids.length > 0) {
            this.centroids.forEach(c => {
                const cx = (c.x - this.originX) / this.resolution;
                const cy = this.mapHeight - 1 - (c.y - this.originY) / this.resolution;
                
                const outerRadius = 5 / this.zoom;
                const innerRadius = 1.5 / this.zoom;
                const strokeWidth = 1 / this.zoom;
                
                this.ctx.beginPath();
                this.ctx.arc(cx, cy, outerRadius, 0, 2 * Math.PI);
                this.ctx.fillStyle = '#22c55e'; // Green
                this.ctx.strokeStyle = '#86efac';
                this.ctx.lineWidth = strokeWidth;
                this.ctx.fill();
                this.ctx.stroke();
                
                this.ctx.beginPath();
                this.ctx.arc(cx, cy, innerRadius, 0, 2 * Math.PI);
                this.ctx.fillStyle = '#ffffff';
                this.ctx.fill();
            });
        }

        if (this.options.showTarget && this.target) {
            const tx = (this.target.x - this.originX) / this.resolution;
            const ty = this.mapHeight - 1 - (this.target.y - this.originY) / this.resolution;
            
            // Pulse outer ring
            const pulse = (12 + Math.sin(Date.now() / 150) * 4) / this.zoom;
            this.ctx.beginPath();
            this.ctx.arc(tx, ty, pulse, 0, 2 * Math.PI);
            this.ctx.strokeStyle = 'rgba(6, 182, 212, 0.5)';
            this.ctx.lineWidth = 2 / this.zoom;
            this.ctx.stroke();
            
            // Center ring
            this.ctx.beginPath();
            this.ctx.arc(tx, ty, 8 / this.zoom, 0, 2 * Math.PI);
            this.ctx.strokeStyle = '#06b6d4';
            this.ctx.lineWidth = 2 / this.zoom;
            this.ctx.stroke();
            
            // Crosshairs
            this.ctx.beginPath();
            this.ctx.moveTo(tx - 14 / this.zoom, ty);
            this.ctx.lineTo(tx + 14 / this.zoom, ty);
            this.ctx.moveTo(tx, ty - 14 / this.zoom);
            this.ctx.lineTo(tx, ty + 14 / this.zoom);
            this.ctx.strokeStyle = '#06b6d4';
            this.ctx.lineWidth = 1.5 / this.zoom;
            this.ctx.stroke();
        }
    }

    /**
     * Draws the robot chassis beacon.
     */
    drawRobot() {
        const rx = (this.robotPose.x - this.originX) / this.resolution;
        const ry = this.mapHeight - 1 - (this.robotPose.y - this.originY) / this.resolution;
        const ryaw = this.robotPose.yaw;

        this.ctx.save();
        this.ctx.translate(rx, ry);
        this.ctx.rotate(-ryaw); // Negative rotation due to flipped Y-coordinates

        // Calculate robot chassis radius in pixel dimensions on map
        let robotRadiusPx = 7;
        if (this.resolution > 0) {
            robotRadiusPx = this.options.robotRadiusM / this.resolution;
        }

        // Pulsing safety ring (scales with chassis size)
        const pulse = robotRadiusPx * (1.3 + Math.sin(Date.now() / 150) * 0.2);
        this.ctx.beginPath();
        this.ctx.arc(0, 0, pulse, 0, 2 * Math.PI);
        this.ctx.strokeStyle = 'rgba(239, 68, 68, 0.4)';
        this.ctx.lineWidth = 2 / this.zoom;
        this.ctx.stroke();

        // Robot core chassis representation
        this.ctx.beginPath();
        this.ctx.arc(0, 0, robotRadiusPx, 0, 2 * Math.PI);
        this.ctx.fillStyle = this.options.robotColor;
        this.ctx.strokeStyle = this.options.robotStrokeColor;
        this.ctx.lineWidth = 1.5 / this.zoom;
        this.ctx.fill();
        this.ctx.stroke();

        // Steering heading arrow
        const arrowLength = robotRadiusPx;
        this.ctx.beginPath();
        this.ctx.moveTo(arrowLength, 0);
        this.ctx.lineTo(-arrowLength * 0.5, -arrowLength * 0.5);
        this.ctx.lineTo(-arrowLength * 0.15, 0);
        this.ctx.lineTo(-arrowLength * 0.5, arrowLength * 0.5);
        this.ctx.closePath();
        this.ctx.fillStyle = '#ffffff';
        this.ctx.fill();

        this.ctx.restore();
    }

    /**
     * Draws the visual map distance scale bar.
     */
    drawScaleBar() {
        if (this.resolution <= 0) return;
        
        const targetWidthPx = 80;
        const realDistance = (targetWidthPx * this.resolution) / this.zoom;
        const niceDistances = [100, 50, 20, 10, 5, 2, 1, 0.5, 0.2, 0.1, 0.05, 0.02, 0.01];
        
        let selectedDist = niceDistances[niceDistances.length - 1];
        for (let i = 0; i < niceDistances.length; i++) {
            if (niceDistances[i] <= realDistance) {
                selectedDist = niceDistances[i];
                break;
            }
        }
        
        const scaleWidthPx = (selectedDist * this.zoom) / this.resolution;
        const x = 20;
        const y = this.canvas.height - 20;

        this.ctx.save();
        this.ctx.strokeStyle = this.options.scaleColor;
        this.ctx.lineWidth = 2;
        this.ctx.beginPath();
        this.ctx.moveTo(x, y);
        this.ctx.lineTo(x + scaleWidthPx, y);
        this.ctx.moveTo(x, y - 5);
        this.ctx.lineTo(x, y + 5);
        this.ctx.moveTo(x + scaleWidthPx, y - 5);
        this.ctx.lineTo(x + scaleWidthPx, y + 5);
        this.ctx.stroke();

        this.ctx.fillStyle = this.options.scaleColor;
        this.ctx.font = 'bold 10px Orbitron, sans-serif';
        this.ctx.textAlign = 'center';
        const label = selectedDist >= 1 ? `${selectedDist} m` : `${Math.round(selectedDist * 100)} cm`;
        this.ctx.fillText(label, x + scaleWidthPx / 2, y - 8);
        this.ctx.restore();
    }

    /**
     * Registers pointer pan, wheel zoom and touch gesture zoom event listeners on the canvas.
     */
    initEvents() {
        // Drag/Pan handlers
        this.canvas.addEventListener('mousedown', (e) => {
            this.isDragging = true;
            this.startDragX = e.clientX - this.offsetX;
            this.startDragY = e.clientY - this.offsetY;
        });

        document.addEventListener('mousemove', (e) => {
            if (this.isDragging) {
                this.offsetX = e.clientX - this.startDragX;
                this.offsetY = e.clientY - this.startDragY;
                this.draw();
            }
        });

        document.addEventListener('mouseup', () => {
            this.isDragging = false;
        });

        // Wheel Zoom handler
        this.canvas.addEventListener('wheel', (e) => {
            e.preventDefault();
            const zoomFactor = 1.15;
            const mouseX = e.offsetX;
            const mouseY = e.offsetY;

            const worldX = (mouseX - this.offsetX) / this.zoom;
            const worldY = (mouseY - this.offsetY) / this.zoom;

            if (e.deltaY < 0) {
                this.zoom *= zoomFactor;
            } else {
                this.zoom /= zoomFactor;
            }
            this.zoom = Math.max(0.1, Math.min(this.zoom, 15.0));

            this.offsetX = mouseX - worldX * this.zoom;
            this.offsetY = mouseY - worldY * this.zoom;
            this.draw();
        });

        // Touch event handlers (for tablet/mobile devices)
        this.canvas.addEventListener('touchstart', (e) => {
            if (e.touches.length === 1) {
                this.isDragging = true;
                this.startDragX = e.touches[0].clientX - this.offsetX;
                this.startDragY = e.touches[0].clientY - this.offsetY;
            } else if (e.touches.length === 2) {
                this.isDragging = false;
                this.touchStartDist = Math.hypot(
                    e.touches[0].clientX - e.touches[1].clientX,
                    e.touches[0].clientY - e.touches[1].clientY
                );
                this.touchStartZoom = this.zoom;
            }
        });

        this.canvas.addEventListener('touchmove', (e) => {
            if (this.isDragging && e.touches.length === 1) {
                this.offsetX = e.touches[0].clientX - this.startDragX;
                this.offsetY = e.touches[0].clientY - this.startDragY;
                this.draw();
                e.preventDefault();
            } else if (e.touches.length === 2) {
                const dist = Math.hypot(
                    e.touches[0].clientX - e.touches[1].clientX,
                    e.touches[0].clientY - e.touches[1].clientY
                );
                const factor = dist / this.touchStartDist;
                const midX = (e.touches[0].clientX + e.touches[1].clientX) / 2;
                const midY = (e.touches[0].clientY + e.touches[1].clientY) / 2;

                const rect = this.canvas.getBoundingClientRect();
                const canvasMidX = midX - rect.left;
                const canvasMidY = midY - rect.top;

                const worldX = (canvasMidX - this.offsetX) / this.zoom;
                const worldY = (canvasMidY - this.offsetY) / this.zoom;

                this.zoom = Math.max(0.1, Math.min(this.touchStartZoom * factor, 15.0));
                this.offsetX = canvasMidX - worldX * this.zoom;
                this.offsetY = canvasMidY - worldY * this.zoom;
                this.draw();
                e.preventDefault();
            }
        }, { passive: false });

        this.canvas.addEventListener('touchend', () => {
            this.isDragging = false;
        });

        // Resize handler
        window.addEventListener('resize', () => {
            this.draw();
        });
    }
}

window.MapCanvas = MapCanvas;
