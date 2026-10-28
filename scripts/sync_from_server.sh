#!/usr/bin/env bash
# ==============================================================================
# pyTrade3 - Sync Database & CSV from Production Server OVH to Local Mac
#
# Cách dùng:
#   ./sync_from_server.sh                  # Đồng bộ từ server mặc định (ubuntu@144.217.95.231)
#   ./sync_from_server.sh user@host:path   # Đồng bộ từ host/path tùy chỉnh
#
# Hỗ trợ xác thực:
#   1. SSH Key (tự động không cần mật khẩu nếu đã chạy ssh-copy-id)
#   2. Biến môi trường SERVER_SSH_PASS (trong file .env hoặc export) thông qua /usr/bin/expect
#   3. Nhập mật khẩu trực tiếp trên Terminal nếu chạy thủ công
# ==============================================================================

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

# Tự động đọc cấu hình từ .env (hỗ trợ cả trường hợp dòng cuối file không có newline)
if [[ -f "${PROJECT_DIR}/.env" ]]; then
    while IFS='=' read -r key val || [[ -n "$key" ]]; do
        # Xóa ký tự \r nếu có
        key="${key%$'\r'}"
        val="${val%$'\r'}"
        [[ -z "$key" || "$key" =~ ^[[:space:]]*# ]] && continue
        key="$(echo "$key" | xargs)"
        val="$(echo "$val" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//")"
        if [[ "$key" == "SERVER_SSH_PASS" || "$key" == "SERVER_HOST" || "$key" == "SERVER_USER" || "$key" == "SERVER_DIR" ]]; then
            export "$key=$val"
        fi
    done < "${PROJECT_DIR}/.env"
fi

DEFAULT_USER="${SERVER_USER:-ubuntu}"
DEFAULT_HOST="${SERVER_HOST:-144.217.95.231}"
DEFAULT_DIR="${SERVER_DIR:-/home/ubuntu/pyTrade3}"

CUSTOM_SRC="${1:-}"
if [[ -n "$CUSTOM_SRC" ]]; then
    REMOTE_HOST_PART="${CUSTOM_SRC%%:*}"
    REMOTE_DIR_PART="${CUSTOM_SRC#*:}"
else
    REMOTE_HOST_PART="${DEFAULT_USER}@${DEFAULT_HOST}"
    REMOTE_DIR_PART="${DEFAULT_DIR}"
fi
REMOTE_DIR_PART="${REMOTE_DIR_PART%/}"

echo "=================================================================="
echo "☁️  pyTrade3 - Đồng bộ Database & CSV từ Server OVH về Local Mac"
echo "=================================================================="
echo "🌐 Server nguồn : ${REMOTE_HOST_PART}:${REMOTE_DIR_PART}"
echo "📂 Thư mục đích : ${PROJECT_DIR}"
echo "------------------------------------------------------------------"

# Hàm chạy lệnh ssh/rsync tự động điền password bằng expect nếu SERVER_SSH_PASS được cấu hình
run_with_auth() {
    if [[ -n "${SERVER_SSH_PASS:-}" ]] && command -v expect &>/dev/null; then
        /usr/bin/expect -f - "$@" <<'EOF'
set timeout 60
log_user 1
set pass $env(SERVER_SSH_PASS)
eval spawn $argv
expect {
    -nocase "yes/no" {
        send "yes\r"
        exp_continue
    }
    -nocase "password:" {
        send -- "$pass\r"
        exp_continue
    }
    eof
}
catch wait result
exit [lindex $result 3]
EOF
    else
        "$@"
    fi
}

# 1. Sao lưu bản local hiện tại trước khi ghi đè
mkdir -p "${PROJECT_DIR}/backups_local"
TS=$(date +%Y%m%d_%H%M%S)
if [[ -f "${PROJECT_DIR}/trading_bot.db" ]]; then
    cp "${PROJECT_DIR}/trading_bot.db" "${PROJECT_DIR}/backups_local/trading_bot_local_${TS}.db"
    # Giữ tối đa 5 bản backup local gần nhất
    ls -1t "${PROJECT_DIR}/backups_local"/trading_bot_local_*.db 2>/dev/null | tail -n +6 | xargs rm -f 2>/dev/null || true
fi

# 2. Tạo bản snapshot SQLite sạch trên Server (an toàn tuyệt đối khi Server đang chạy chế độ WAL)
echo "📸 [1/3] Đang tạo snapshot SQLite an toàn trên Server..."
REMOTE_SNAPSHOT="/tmp/trading_bot_sync_snapshot.db"
REMOTE_CMD="if command -v sqlite3 >/dev/null 2>&1; then sqlite3 '${REMOTE_DIR_PART}/trading_bot.db' \".backup '${REMOTE_SNAPSHOT}'\"; else cp '${REMOTE_DIR_PART}/trading_bot.db' '${REMOTE_SNAPSHOT}'; fi"

run_with_auth ssh -o ConnectTimeout=12 "$REMOTE_HOST_PART" "$REMOTE_CMD"

# 3. Kéo file snapshot DB từ Server về file tạm ở Local
echo "⬇️  [2/3] Đang tải trading_bot.db từ Server về máy..."
LOCAL_TMP_DB="${PROJECT_DIR}/trading_bot.db.sync_tmp"
run_with_auth rsync -avz "${REMOTE_HOST_PART}:${REMOTE_SNAPSHOT}" "$LOCAL_TMP_DB"

# Xóa các file -wal / -shm cũ ở local trước khi thay thế DB mới để tránh xung đột WAL
rm -f "${PROJECT_DIR}/trading_bot.db-wal" "${PROJECT_DIR}/trading_bot.db-shm"
mv "$LOCAL_TMP_DB" "${PROJECT_DIR}/trading_bot.db"

# 4. Kéo file lịch sử giao dịch CSV từ Server về Local
echo "⬇️  [3/3] Đang tải trading_orders_history.csv từ Server..."
run_with_auth rsync -avz "${REMOTE_HOST_PART}:${REMOTE_DIR_PART}/trading_orders_history.csv" "${PROJECT_DIR}/trading_orders_history.csv" || echo "⚠️  Không tìm thấy file CSV trên server, bỏ qua."

echo "------------------------------------------------------------------"
echo "✅ Đồng bộ hoàn tất! Dữ liệu từ Server OVH đã được cập nhật vào trading_bot.db."
echo "=================================================================="
