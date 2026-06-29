# Jetson Thor Isaac ROS Jazzy + NITROS Install Guide / 安裝指南

This directory now includes both English and Traditional Chinese documentation.
這個資料夾現在同時包含英文與繁體中文版本文件。

## Documents / 文件

- English: `README.en.md`
- 繁體中文: `README.zh-TW.md`

## Quick start / 快速開始

Install / 安裝：

```bash
cd /home/ubuntu/.openclaw/workspace/isaac-ros-jetson-thor-jazzy-install
./install.sh
```

Run AprilTag pipeline / 執行 AprilTag 驗證流程：

```bash
cd /home/ubuntu/.openclaw/workspace/isaac-ros-jetson-thor-jazzy-install
./run_apriltag.sh
```

Verify install / 驗證安裝：

```bash
cd /home/ubuntu/.openclaw/workspace/isaac-ros-jetson-thor-jazzy-install
./verify_install.sh
```

Verify live detection / 驗證即時 detection：

```bash
cd /home/ubuntu/.openclaw/workspace/isaac-ros-jetson-thor-jazzy-install
VERIFY_DETECTION=1 ./verify_install.sh
```

## Files / 檔案

- `README.en.md` — English runbook
- `README.zh-TW.md` — 繁體中文操作手冊
- `install.sh` — installer
- `run_apriltag.sh` — launch the camera + AprilTag pipeline
- `verify_install.sh` — verify packages / topics / detections
- `apriltag_test.launch.py` — validation launch file
