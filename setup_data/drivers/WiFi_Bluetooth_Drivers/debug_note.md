# Wi-Fi 與藍牙驅動問題排查與解決筆記

## 1. 系統環境與硬體資訊收集
* **核心版本 (Kernel)**: `6.8.12-tegra-ubuntu24.04_aarch64` (Jetson Tegra 平台)
* **Wi-Fi 晶片 (PCIe)**: `Realtek Semiconductor Co., Ltd. RTL8852BE PCIe 802.11ax Wireless Network Controller`
* **藍牙晶片 (USB)**: `Realtek Semiconductor Corp. Bluetooth Radio` (USB ID `0bda:b85b`)

---

## 2. 故障排除步驟與執行指令

### 步驟 2.1: 檢查裝置 Block 狀態與核心日誌
我們首先執行了以下指令來檢查裝置是否被軟體或硬體關閉 (rfkill)，以及檢查核心中是否有相關的錯誤訊息：
```bash
rfkill list
systemctl status bluetooth
ip a
nmcli device
```

**發現問題：**
* `rfkill list` 顯示 `phy1 (Wireless LAN)` 與 `hci0 (Bluetooth)` 均處於 **Soft blocked: yes** 狀態，這會導致 Wi-Fi 和藍牙功能被系統停用。

  ```bash
  sudo rfkill unblock all
  ```

---

### 步驟 2.2: 解決藍牙韌體載入失敗問題
在檢查 `dmesg` 核心日誌時，發現了藍牙驅動載入韌體的錯誤訊息：
```text
usb 1-3.4: Direct firmware load for rtl8852bu_config failed with error -2
usb 1-3.4: Direct firmware load for rtl8852bu_fw failed with error -2
rtk_btusb: load firmware failed!
```

**發現問題：**
* Realtek 藍牙驅動程式 `rtk_btusb` 在載入時，尋找的韌體路徑與檔名是直接位於 `/lib/firmware/` 目錄下的 `rtl8852bu_fw` 與 `rtl8852bu_config`，**並且不帶 `.bin` 副檔名**。
* 原先的 `setup.sh` 只有將韌體解壓縮為 `/lib/firmware/rtl_bt/rtl8852bu_fw.bin` 且沒有建立合適的軟連結，導致驅動程式回報找不到檔案（Error -2，即 ENOENT）。

**採取的行動：**
* 建立正確路徑與不帶 `.bin` 的軟連結：
  ```bash
  sudo ln -sf /lib/firmware/rtl_bt/rtl8852bu_fw.bin /lib/firmware/rtl8852bu_fw
  sudo ln -sf /lib/firmware/rtl_bt/rtl8852bu_config.bin /lib/firmware/rtl8852bu_config
  ```
* 重新載入藍牙驅動模組，並重啟藍牙服務：
  ```bash
  sudo modprobe -r rtk_btusb btusb
  sudo modprobe rtk_btusb
  sudo modprobe btusb
  sudo systemctl restart bluetooth
  ```
* **結果：** 藍牙韌體成功載入 (`load_firmware done`)，且藍牙功能已被成功啟用 (`Powered: yes`)。

---

### 步驟 2.3: 解決 Wi-Fi 節電設定未生效與連線問題
我們檢查了 Wi-Fi 驅動核心參數狀態：
```bash
cat /sys/module/rtw89core/parameters/disable_ps_mode
```
結果輸出為 **N**，表示節電模式並未成功停用，因此即使能搜尋到網路，也可能因節電或不穩定的 PCI 狀態而無法順利建立連線。

**發現問題：**
* 雖然 `/etc/modprobe.d/rtw89.conf` 內已經寫入了 `disable_ps_mode=y`，但因為舊的 `setup.sh` 在安裝驅動後，僅重新載入了最上層的 `rtw_8852be` 模組，而其所依賴的底層核心模組 `rtw89core` 與 `rtw89pci` 並未被卸載重新載入，因此並未讀取到新寫入的參數。

**採取的行動：**
* 完整卸載所有關聯的 rtw89 核心模組並重新載入，以套用新的節電停用設定：
  ```bash
  sudo modprobe -r rtw_8852be
  sudo modprobe -r rtw_8852b
  sudo modprobe -r rtw89pci
  sudo modprobe -r rtw89core
  sudo modprobe rtw_8852be
  ```
* **結果：** 再次檢查 `disable_ps_mode` 狀態已成功變為 **Y**，設定成功生效。此時 Wi-Fi 介面 `wlP1p1s0` 的狀態完全正常，已解除封鎖並能夠正常進行掃描與連接認證。

---

## 3. 指令指令檔 `setup.sh` 的修改對照 (Diff)
為了防止日後再次執行該安裝指令檔時遇到同樣的問題，我們已將解決方案整合進 `[setup.sh](file:///home/ubuntu/setup_data/drivers/WiFi_Bluetooth_Drivers/setup.sh)`：

1. **修正藍牙韌體解壓後的連結建立**：
   在解壓完韌體後，自動建立不帶 `.bin` 的軟連結：
   ```bash
   sudo ln -sf rtl_bt/rtl8852bu_fw.bin /lib/firmware/rtl8852bu_fw 2>/dev/null || true
   sudo ln -sf rtl_bt/rtl8852bu_config.bin /lib/firmware/rtl8852bu_config 2>/dev/null || true
   ```
2. **修正核心模組載入機制**：
   在載入驅動前，先完整卸載 `rtw_8852be`、`rtw_8852b`、`rtw89pci`、`rtw89core`，確保所有的 `rtw89.conf` 選項生效：
   ```bash
   sudo modprobe -r rtw_8852be 2>/dev/null || true
   sudo modprobe -r rtw_8852b 2>/dev/null || true
   sudo modprobe -r rtw89pci 2>/dev/null || true
   sudo modprobe -r rtw89core 2>/dev/null || true
   sudo modprobe rtw_8852be
   ```
3. **新增解除封鎖步驟**：
   在指令檔結尾自動執行：
   ```bash
   sudo rfkill unblock all
   ```

