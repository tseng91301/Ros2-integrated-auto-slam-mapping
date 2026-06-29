sudo mkdir -p /lib/firmware/rtl_bt
sudo cp -r ./* /lib/firmware/rtl_bt

# 詢問是否需要立即重新啟動
echo "Do you want to reboot now? (y/n)"
read answer
if [ "$answer" = "y" ]; then
    sudo reboot
fi