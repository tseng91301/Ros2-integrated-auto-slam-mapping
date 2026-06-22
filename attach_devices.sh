#!/usr/bin/env bash
# attach_devices.sh
# 用於動態將 Host 端的序列埠裝置掛載進正在運行的 Docker 容器中。

CONTAINER_NAME="isaac_ros_dev_container"

# 檢查是否有傳入引數
if [ "$#" -lt 1 ]; then
    echo "❌ 使用方法: $0 <裝置1> [裝置2] [裝置3] ..."
    echo "   範例: $0 /dev/playrobot_base /dev/sllidar_a2m12"
    exit 1
fi

# 檢查容器是否在運行
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "❌ 錯誤: 容器 ${CONTAINER_NAME} 未啟動或不存在！"
    exit 1
fi

echo "🔄 開始為運行中的容器 ${CONTAINER_NAME} 掛載裝置..."

for dev in "$@"; do
    if [ ! -e "$dev" ]; then
        echo "⚠️ 警告: Host 端未發現裝置 $dev，請確認硬體已連接且 udev 規則已生效。"
        continue
    fi

    # 取得裝置的 Major 與 Minor 號碼 (支援軟連結解析)
    MAJOR_HEX=$(stat -L -c "%t" "$dev")
    MINOR_HEX=$(stat -L -c "%T" "$dev")
    
    # 十六進位轉十進位
    MAJOR=$((16#$MAJOR_HEX))
    MINOR=$((16#$MINOR_HEX))

    echo "📍 發現裝置 $dev -> 主設備號: $MAJOR, 次設備號: $MINOR"

    # 在容器中移除舊節點並建立新節點
    docker exec -u root "$CONTAINER_NAME" rm -f "$dev"
    docker exec -u root "$CONTAINER_NAME" mknod "$dev" c "$MAJOR" "$MINOR"
    docker exec -u root "$CONTAINER_NAME" chmod 666 "$dev"

    echo "✅ 成功掛載 $dev 到容器內部！"
done

echo "🎉 裝置掛載完成。您可以在容器內部存取這些裝置了！"
