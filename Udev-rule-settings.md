在 Linux 中，建立固定裝置名稱（別名）的標準作法是透過 udev 機制。它會在偵測到該 USB 裝置插入時，自動在 /dev/ 下建立一個你自訂的軟連結（Symbolic Link）。

步驟 1：查詢 USB 裝置的詳細資訊
請先把你的 USB 裝置插上，然後在終端機輸入以下指令（假設目前是 ttyUSB0）：

Bash
udevadm info --name=/dev/ttyUSB0 --attribute-walk
這會列出大量的硬體屬性。請往上滾動，找到最頂層（通常是第一個區塊）的親代裝置屬性，記下以下三個關鍵值：

idVendor（例如：0403）

idProduct（例如：6001）

serial（例如：A900872A —— 這就是最神準的「身分證」，能防止你插兩條同型號線時搞混）

步驟 2：建立 Udev 規則檔案
在 /etc/udev/rules.d/ 目錄下建立一個新的規則檔案（檔名必須以 .rules 結尾，前面數字通常大於 50）：

Bash
sudo nano /etc/udev/rules.d/99-usb-serial.rules
在檔案中寫入以下內容（請將其中的 0403、6001 和 A900872A 替換為你在步驟 1 查到的資料，而 my_device 就是你想要的自訂名稱）：

Plaintext
SUBSYSTEM=="tty", ATTRS{idVendor}=="0403", ATTRS{idProduct}=="6001", ATTRS{serial}=="A900872A", SYMLINK+="my_device"
💡 小提示： > 如果你的 USB 晶片是山寨版或便宜貨，可能沒有獨一無二的 serial（欄位可能是空的或大家都一樣）。這時你可以退而求其次，根據它插在電腦上的**物理插槽位置（Kernels）**來綁定：
SUBSYSTEM=="tty", KERNELS=="1-2.1", SYMLINK+="my_device"

步驟 3：重新載入 Udev 規則
存檔離開後，執行以下指令讓系統立刻應用新規則，而不用重啟電腦：

Bash
sudo udevadm control --reload-rules && sudo udevadm trigger
驗證結果
這時候你可以檢查 /dev/ 目錄，你會發現神奇的事情發生了：

Bash
ls -l /dev/my_device
輸出的結果會類似這樣：
lrwxrwxrwx 1 root root 7  6月 16 16:20 /dev/my_device -> ttyUSB0

系統成功幫你建立了一個軟連結（Symlink）。以後不論你的 USB 裝置插拔後變成 ttyUSB0 還是 ttyUSB1，你只要在程式或腳本中固定存取 /dev/my_device，就能保證絕對不會認錯裝置了！

重要: 最後一步
src/sllidar_ros2/launch/sllidar_a2m12_launch .py 裡面 serial_port = LaunchConfiguration('serial_port', default='/dev/ttyUSB0')
改成  serial_port = LaunchConfiguration('serial_port', default='/dev/sllidar_a2m12') 