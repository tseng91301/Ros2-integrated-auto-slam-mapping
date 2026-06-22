# 🔌 Isaac ROS Docker 裝置掛載與串接指南

本指南說明如何將 Host 端（Jetson 本機）的 USB 序列埠裝置（例如：雷達與馬達底盤）掛載進正在運行或準備啟動的 Isaac ROS Docker 容器中。

---

## 📋 1. Host 端裝置驗證

在進行掛載前，請確認 Host 端已套用 [udev-rules.md](file:///home/ubuntu/setup_data/udev-rules.md) 規則，且裝置正常連結：

```bash
ls -l /dev/sllidar_a2m12 /dev/playrobot_base
```
* **預期輸出：**
  * `/dev/sllidar_a2m12 -> ttyUSB0`
  * `/dev/playrobot_base -> ttyCH341USB0`

---

## ⚡ 2. 動態掛載：免重啟容器將裝置掛載進現有容器 (推薦)

如果您不想中斷、重新編譯或刪除目前正在運行的容器，可以使用動態掛載腳本。

### 🚀 腳本使用範例
我們可以使用工作空間底下的 [attach_devices.sh](file:///home/ubuntu/workspaces/isaac_ros-dev/attach_devices.sh) 腳本。該腳本支援透過引數傳入多個裝置路徑：

```bash
# 切換到工作空間
cd /home/ubuntu/workspaces/isaac_ros-dev

# 動態掛載雷達與馬達底盤裝置
./attach_devices.sh /dev/playrobot_base /dev/sllidar_a2m12
```

**執行輸出結果：**
```text
🔄 開始為運行中的容器 isaac_ros_dev_container 掛載裝置...
📍 發現裝置 /dev/playrobot_base -> 主設備號: 169, 次設備號: 0
✅ 成功掛載 /dev/playrobot_base 到容器內部！
📍 發現裝置 /dev/sllidar_a2m12 -> 主設備號: 188, 次設備號: 0
✅ 成功掛載 /dev/sllidar_a2m12 到容器內部！
🎉 裝置掛載完成。您可以在容器內部存取這些裝置了！
```

### 🔍 手動 mknod 指令說明
此腳本背後的原理是利用 `--privileged` 容器可以直接透過 `mknod` 建立裝置節點的能力：
```bash
# 1. 查詢 Host 端的 Major, Minor 號碼
ls -L -l /dev/playrobot_base

# 2. 進入容器內部或使用 docker exec 建立節點 (範例為 Major 169, Minor 0)
docker exec -u root isaac_ros_dev_container mknod /dev/playrobot_base c 169 0
docker exec -u root isaac_ros_dev_container chmod 666 /dev/playrobot_base
```

---

## ⚙️ 3. 靜態掛載：修改啟動腳本一勞永逸

若要讓每次重新建立容器時都自動掛載這些裝置，可以直接修改容器的初始化與啟動腳本。

1. 開啟 [install.sh](file:///home/ubuntu/setup_data/isaac-ros-jetson-thor-jazzy-install/install.sh)。
2. 尋找 `start_container()` 函式（約在第 136-150 行）。
3. 將 `/dev/sllidar_a2m12` 與 `/dev/playrobot_base` 新增至掛載循環中：

```diff
   for path in \
     /usr/bin/tegrastats \
     /sys/kernel/debug \
     /usr/lib/aarch64-linux-gnu/tegra \
     /usr/src/jetson_multimedia_api \
     /usr/src/jetson_sipl_api \
     /usr/share/vpi3 \
     /dev/input \
     /dev/bus/usb \
     /dev/video0 \
     /dev/video1 \
     /dev/media0 \
-    /dev/media1; do
+    /dev/media1 \
+    /dev/sllidar_a2m12 \
+    /dev/playrobot_base; do
     [[ -e "$path" ]] && args+=( -v "$path:$path" )
   done
```

> [!IMPORTANT]
> **Docker 掛載 Symlink 說明**：
> Docker 使用 `-v` 掛載時，會自動將 Host 端之 Symlink 解析為實體字元裝置並掛載進容器中。因此容器內會直接產生 `/dev/playrobot_base` 的實體設備，無需擔心容器內缺乏 `ttyCH341USB0` 檔案的問題。

---

## 🔬 4. 驗證容器內裝置狀態

掛載成功後，在 Host 端執行以下指令，檢查容器內是否存在該裝置且具備讀寫權限：

```bash
docker exec -it isaac_ros_dev_container ls -l /dev/sllidar_a2m12 /dev/playrobot_base
```

**正確的裝置狀態輸出（應有 `crw-rw-rw-` 或類似的字元裝置權限）：**
```text
crw-rw-rw- 1 root root 169, 0 Jun 22 05:40 /dev/playrobot_base
crw-rw-rw- 1 root root 188, 0 Jun 22 05:40 /dev/sllidar_a2m12
```
