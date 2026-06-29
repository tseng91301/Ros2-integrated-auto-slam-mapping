
git clone https://github.com/WCHSoftGroup/ch341ser_linux.git
cd ch341ser_linux/driver
make
sudo make install
cd ../..
rm -rf ch341ser_linux
echo "CH341 driver installed successfully!"
ls -al /dev/ttyCH*