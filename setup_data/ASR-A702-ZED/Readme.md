# ASR-A702 板的 ZED 雙目視覺鏡頭的驅動程式及 SDK 安裝

## GMSL 驅動程式安裝
```bash
# 進入 ASR-A702 資料夾

cd Binary/
sudo dpkg -i ./zed_1222_1624.deb
cd ..
```

## SDK 安裝
```bash
# 進入 ASR-A702 資料夾
cd ./SDK
chmod +x ./ZED_SDK_Tegra_L4T38.2_v5.1.2.zstd.run
./ZED_SDK_Tegra_L4T38.2_v5.1.2.zstd.run
cd ..
```
