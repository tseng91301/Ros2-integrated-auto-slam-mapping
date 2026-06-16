# ROS2 Colcon 編譯問題修復與優化筆記 (Build Troubleshooting & Fix Notes)

本文件整理了工作空間 `steven_verify_ws` 在進行 `colcon build` 時遇到的錯誤原因及相應的修復方法，以便日後維護與參考。

---

## 📋 錯誤總覽與解決方案

| 順序 | 錯誤訊息 | 根本原因 (Root Cause) | 修復步驟 (Action taken) |
| :--- | :--- | :--- | :--- |
| **1** | `error: package directory 'base_control_ros2' does not exist` | `base_control_ros2` 包的 Python 原始檔被錯誤打包在 `build/` 中，而非 `src/` 中。執行清理編譯後原始碼隨之遺失。 | 從備份壓縮包中還原 Python 原始碼至正確的源碼路徑 `src/base_control_ros2/base_control_ros2/`。 |
| **2** | `Failed to find .../install/serial/share/serial/package.sh` | 依賴包 `serial`（在 `src/depend/serial_ros2`）尚未編譯，而編譯命令僅指定單獨編譯 `base_control_ros2`。 | 使用 `--packages-up-to` 參數進行連同依賴包一起編譯，或進行全工作空間編譯。 |
| **3** | `Intel RealSense SDK 2.0 is missing, please install it...` | 系統缺少編譯 `realsense2_camera` 所需的 Intel RealSense 核心開發庫 (`librealsense2`)。 | 使用系統套件管理工具安裝 `ros-humble-librealsense2` 及其相關依賴。 |
| **4** | `FileNotFoundError: .../src/build/wheeltec_robot_keyboard/package.xml` | `src/` 底下殘留了錯誤生成的 `build/` 與 `install/` 快取目錄，干擾了 `rosdep` 的依賴掃描。 | 清理 `src/` 目錄下的 `build`、`install` 和 `log` 等不應存在於源碼目錄的資料夾。 |

---

## 🔍 詳細修正說明

### 🛠️ 問題一：`base_control_ros2` Python 原始碼遺失與目錄不符
* **問題現象**：
  在清理完 `build/` 與 `install/` 目錄後，執行 `colcon build` 報錯：
  ```text
  error: package directory 'base_control_ros2' does not exist
  ```
* **根本原因**：
  此包為 ROS2 Python 套件（使用 `setup.py`）。其設定聲明了包含的 python 模組為 `base_control_ros2`：
  ```python
  packages=['base_control_ros2']
  ```
  但在 `src/base_control_ros2/` 底下並無 `base_control_ros2/` 的子目錄，原始代碼在封裝時被錯放在 `build/` 快取目錄中。一旦清除快取，原始碼即消失。
* **修正方法**：
  1. 創建原始碼子目錄：
     ```bash
     mkdir -p src/base_control_ros2/base_control_ros2
     ```
  2. 從備份中提取並還原以下四個核心檔案至該目錄中：
     * `__init__.py` (模組宣告)
     * `base_control_ros2.py` (主控制邏輯)
     * `test_node.py` (測試節點)
     * `loopqueue.py` (佇列輔助工具)

---

### 🛠️ 問題二：`serial` 依賴包缺失與編譯指令優化
* **問題現象**：
  ```text
  Failed to find the following files:
  - /home/ubuntu/steven_verify_ws/install/serial/share/serial/package.sh
  Check that the following packages have been built:
  - serial
  ```
* **根本原因**：
  `base_control_ros2` 的 `package.xml` 聲明了 `<exec_depend>serial</exec_depend>`。在使用 `--packages-select base_control_ros2` 時，`colcon` 不會主動編譯其依賴的 `serial` 包。
* **修正方法**：
  改用 `--packages-up-to` 參數，讓編譯器自動先編譯所有上游依賴項：
  ```bash
  colcon build --symlink-install --packages-up-to base_control_ros2
  ```

---

### 🛠️ 問題三：`realsense2_camera` 編譯時缺少 RealSense SDK 2.0
* **問題現象**：
  ```text
  CMake Error at CMakeLists.txt:129 (message):
    Intel RealSense SDK 2.0 is missing, please install it...
  ```
* **根本原因**：
  ROS2 系統環境中未安裝 Intel RealSense 的底層 C++ 開發庫 `librealsense2`。
* **修正方法**：
  利用系統套件管理工具安裝對應 ROS2 Humble 版本的 RealSense SDK：
  ```bash
  sudo apt-get update
  sudo apt-get install -y ros-humble-librealsense2 ros-humble-launch-pytest python3-tqdm
  ```

---

### 🛠️ 問題四：`src/` 目錄中殘留編譯快取導致依賴掃描出錯
* **問題現象**：
  在執行 `rosdep` 掃描或編譯時，出現尋找 `src/build/.../package.xml` 失敗的錯誤。
* **根本原因**：
  可能之前誤在 `src/` 子目錄中執行了 `colcon build`，導致編譯產生的 `build/`、`install/`、`log/` 被建在 `src/` 內部，混淆了 ROS2 的套件尋找機制。
* **修正方法**：
  清除 `src/` 目錄下的多餘編譯快取資料夾：
  ```bash
  rm -rf src/build/ src/install/ src/log/
  ```

---

## 🚀 成果驗證 (Verification Results)

經上述修正後，執行乾淨的全工作空間編譯已能順利通過：

```bash
# 清理所有最外層編譯快取
sudo rm -rf build/ install/ log/

# 重新進行全工作空間編譯
colcon build --symlink-install
```

**編譯輸出結果**：
```text
Summary: 14 packages finished [1min 54s]
  1 package had stderr output: wheeltec_robot_keyboard (僅為 setuptools 警告，非錯誤)
```
此時，包含底層控制 `base_control_ros2`、相機 `realsense2_camera`、雷達 `sllidar_ros2` 在內的所有 14 個 ROS2 功能包皆已編譯成功，工作空間狀態健全。
