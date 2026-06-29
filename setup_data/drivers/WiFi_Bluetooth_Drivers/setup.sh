#!/bin/bash

# 1. 修正核心編譯軟連結
sudo ln -sfn /usr/src/linux-headers-6.8.12-tegra-ubuntu24.04_aarch64/3rdparty/canonical/linux-noble /lib/modules/$(uname -r)/build

# 2. 下載並編譯 Wi-Fi 驅動
mkdir -p drivers
cd drivers
if [ ! -d "rtw89" ]; then
    git clone https://github.com/lwfinger/rtw89.git
fi
cd rtw89
make
sudo make install
cd ../..

# 3. 解壓 Wi-Fi 與藍芽韌體檔案 (解決 Jetson 不支援 .zst 壓縮韌體的問題)
sudo zstd -d --keep /lib/firmware/rtw89/rtw8852b_fw.bin.zst 2>/dev/null || true
sudo zstd -d --keep /lib/firmware/rtw89/rtw8852b_fw-1.bin.zst 2>/dev/null || true
sudo zstd -d --keep /lib/firmware/rtl_bt/rtl8852bu_fw.bin.zst 2>/dev/null || true
sudo zstd -d --keep /lib/firmware/rtl_bt/rtl8761bu_config.bin.zst 2>/dev/null || true
sudo ln -sf rtl8761bu_config.bin /lib/firmware/rtl_bt/rtl8852bu_config.bin 2>/dev/null || true
# 修正 RTL8852BU 藍芽驅動尋找的韌體檔名與路徑 (不帶 .bin 且位於 /lib/firmware/)
sudo ln -sf rtl_bt/rtl8852bu_fw.bin /lib/firmware/rtl8852bu_fw 2>/dev/null || true
sudo ln -sf rtl_bt/rtl8852bu_config.bin /lib/firmware/rtl8852bu_config 2>/dev/null || true

# 4. 寫入 Wi-Fi 節電與 PCI 穩定度設定 (預防連線中斷/連不上)
sudo bash -c 'cat << EOF > /etc/modprobe.d/rtw89.conf
options rtw89core disable_ps_mode=y
options rtw89pci disable_clkreq=y
options rtw89pci disable_aspm_l1=y
options rtw89pci disable_aspm_l1ss=y
EOF'

# 5. 載入 Wi-Fi 驅動模組並套用節電模式設定
sudo depmod -a
sudo modprobe -r rtw_8852be 2>/dev/null || true
sudo modprobe -r rtw_8852b 2>/dev/null || true
sudo modprobe -r rtw89pci 2>/dev/null || true
sudo modprobe -r rtw89core 2>/dev/null || true
sudo modprobe rtw_8852be

# 6. 重新載入藍芽驅動模組使其讀取新解壓的韌體
sudo modprobe -r rtk_btusb btusb 2>/dev/null || true
sudo modprobe rtk_btusb
sudo modprobe btusb
sudo systemctl restart bluetooth

# 7. 解除 Wi-Fi 與藍芽的 RF 軟體封鎖
sudo rfkill unblock all

echo "========================================="
echo "驅動與韌體配置完成！"
echo "Wi-Fi 網卡介面已建立，並已停用 PCI 節電模式以防斷線。"
echo "藍芽驅動已重新載入並載入韌體。"
echo "已使用 rfkill 解除 Wi-Fi 與藍芽的軟體封鎖。"
echo "========================================="