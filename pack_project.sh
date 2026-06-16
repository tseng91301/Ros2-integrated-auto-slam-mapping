#!/bin/bash

# 取得目前腳本所在的專案目錄路徑
PROJECT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PARENT_DIR="$( dirname "$PROJECT_DIR" )"
CURRENT_DIR_NAME="$( basename "$PROJECT_DIR" )"

# 定理打包後的壓縮檔名稱與臨時打包目錄名稱
TARGET_FOLDER_NAME="steven_verify_ws_backup"
TAR_FILE_NAME="${TARGET_FOLDER_NAME}.tar.gz"

echo "=== 開始打包專案 ==="
echo "專案路徑: $PROJECT_DIR"
echo "壓縮檔名: $TAR_FILE_NAME"
echo ""

# 進入專案的上一層目錄進行打包，這樣解壓縮時會解壓出一個獨立的資料夾，不會散落一地
cd "$PARENT_DIR" || exit 1

# 執行 tar 打包，並排除 build, install, log 目錄
# 註：此處也一併排除了 .git 目錄以減少檔案大小（如需保留 git 紀錄，可將該行刪除）
# 為了避免 tar 在寫入壓縮檔時「因壓縮檔也在專案目錄內，檔案大小持續變更」而報錯，我們先將壓縮檔輸出到上一層目錄，打包完後再移入。
tar --exclude="${CURRENT_DIR_NAME}/build" \
    --exclude="${CURRENT_DIR_NAME}/install" \
    --exclude="${CURRENT_DIR_NAME}/log" \
    --exclude="${CURRENT_DIR_NAME}/.git" \
    -czf "$PARENT_DIR/$TAR_FILE_NAME" "$CURRENT_DIR_NAME"

# 檢查打包結果
if [ $? -eq 0 ]; then
    # 打包成功後，將檔案移回專案目錄
    mv "$PARENT_DIR/$TAR_FILE_NAME" "$PROJECT_DIR/"
    echo "========================"
    echo "打包成功！"
    echo "檔案已儲存至: $PROJECT_DIR/$TAR_FILE_NAME"
    echo "========================"
else
    # 失敗時清理上一層可能殘留的毀損檔案
    rm -f "$PARENT_DIR/$TAR_FILE_NAME"
    echo "打包失敗，請檢查權限或空間是否足夠。"
fi
