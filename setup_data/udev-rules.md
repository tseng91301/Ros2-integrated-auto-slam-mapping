# 🛠️ ROS 2 硬體裝置自動命名 (Udev Rules) 設定指南

在 Linux (例如 Jetson Orin) 系統中，當您插拔多個 USB 轉序列埠裝置時，核心分配的名稱（例如 `/dev/ttyUSB0`、`/dev/ttyUSB1` 等）是隨機的。為了解決這個問題，我們可以設定 **udev rules** 來將特定硬體綁定到固定別名（Symlink），以防控制指令「送錯地方」。

本指南整理了您目前機器人系統中的 **Lidar (雷達)** 與 **Motor Control Board (馬達底盤主板)** 的硬體資訊與設定步驟。

---

## 📋 裝置硬體資訊對照表

| 裝置名稱 | 晶片類型 | idVendor | idProduct | Serial (序號) | 固定軟連結別名 (Symlink) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Lidar (雷達)** | CP2102 | `10c4` | `ea60` | `4157d26cd879ca418ca0e378084f3ed7` | `/dev/sllidar_a2m12` |
| **Motor Board (馬達主板)** | CH340 | `1a86` | `7523` | *無唯一序號* | `/dev/playrobot_base` |

> [!NOTE]
> 由於 CH340 晶片沒有唯一的 serial 序號，我們直接使用它的 `idVendor` 與 `idProduct` 來建立唯一的符號連結，這在系統僅有一片 CH340 晶片時非常穩定且安全。

---

## ⚙️ 快速設定步驟

### 步驟 1：寫入 Udev 規則檔
在系統 `/etc/udev/rules.d/99-usb-serial.rules` 中寫入以下規則：

```text
# 1. 雷達 Lidar (CP2102 UART Bridge)
SUBSYSTEM=="tty", ATTRS{idVendor}=="10c4", ATTRS{idProduct}=="ea60", ATTRS{serial}=="4157d26cd879ca418ca0e378084f3ed7", SYMLINK+="sllidar_a2m12"

# 2. 馬達控制底盤主板 (CH340 Serial Converter)
SUBSYSTEM=="tty", ATTRS{idVendor}=="1a86", ATTRS{idProduct}=="7523", SYMLINK+="playrobot_base"
```

您可以直接執行以下指令一鍵寫入：
```bash
echo -e 'SUBSYSTEM=="tty", ATTRS{idVendor}=="10c4", ATTRS{idProduct}=="ea60", ATTRS{serial}=="4157d26cd879ca418ca0e378084f3ed7", SYMLINK+="sllidar_a2m12"\nSUBSYSTEM=="tty", ATTRS{idVendor}=="1a86", ATTRS{idProduct}=="7523", SYMLINK+="playrobot_base"' | sudo tee /etc/udev/rules.d/99-usb-serial.rules
```

---

### 步驟 2：重新載入並應用 Udev 規則
執行以下命令以立即載入新規則，無需重啟電腦：
```bash
sudo udevadm control --reload-rules && sudo udevadm trigger
```

---

### 步驟 3：驗證對應狀態
確認系統是否成功在 `/dev/` 下建立了符號連結：
```bash
ls -l /dev/sllidar_a2m12 /dev/playrobot_base
```

**正確的輸出結果：**
```text
lrwxrwxrwx 1 root root  7 Jun 16 16:30 /dev/sllidar_a2m12 -> ttyUSB0
lrwxrwxrwx 1 root root 12 Jun 16 16:30 /dev/playrobot_base -> ttyCH341USB0
```

---

## 🚀 ROS 2 程式端配合與優勢

透過這套 Udev 機制，我們的 ROS 2 軟體程式碼便可以使用**固定且語意清晰**的裝置路徑：

### 1. 底盤驅動 (`base_control_ros2`)
* 目前已將 [base_control_ros2.py](file:///home/ubuntu/steven_verify_ws/src/base_control_ros2/base_control_ros2/base_control_ros2.py) 中的序列埠讀取設定還原為預設的 `/dev/playrobot_base`。
* 不論您的 USB 序列埠插拔後變成 `ttyCH341USB0` 或其他名稱，驅動都能主動且精準地找到底盤。

### 2. 雷達驅動 (`sllidar_ros2`)
* 在您啟動雷達的 launch 檔時，請將 `serial_port` 參數修改為 `/dev/sllidar_a2m12`。例如：
  ```bash
  ros2 launch sllidar_ros2 sllidar_a2m12_launch.py serial_port:=/dev/sllidar_a2m12
  ```