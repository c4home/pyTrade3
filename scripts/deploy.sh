#!/usr/bin/env bash
# ==============================================================================
# pyTrade3 - Deploy Script to Production Server (Upload nhanh lên Server)
#
# Rule: KHÔNG upload các file data (*.db, *.csv, *.log, .env) để tránh ghi đè
#       dữ liệu giao dịch và cấu hình hiện có trên server.
#
# Cách dùng:
#   ./scripts/deploy.sh                  # Deploy tới server mặc định (ubuntu@144.217.95.231)
#   ./scripts/deploy.sh --dry-run        # Kiểm tra trước danh sách file sẽ upload (chưa upload thật)
#   ./scripts/deploy.sh user@host:path   # Deploy tới host/path tùy chỉnh
# ==============================================================================

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/"

# Tự động đọc cấu hình từ .env (hỗ trợ cả trường hợp dòng cuối file không có newline)
if [[ -f "${PROJECT_DIR}.env" ]]; then
    while IFS='=' read -r key val || [[ -n "$key" ]]; do
        key="${key%$'\r'}"
        val="${val%$'\r'}"
        [[ -z "$key" || "$key" =~ ^[[:space:]]*# ]] && continue
        key="$(echo "$key" | xargs)"
        val="$(echo "$val" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//")"
        if [[ "$key" == "SERVER_SSH_PASS" || "$key" == "SERVER_HOST" || "$key" == "SERVER_USER" || "$key" == "SERVER_DIR" ]]; then
            export "$key=$val"
        fi
    done < "${PROJECT_DIR}.env"
fi

DEFAULT_USER="${SERVER_USER:-ubuntu}"
DEFAULT_HOST="${SERVER_HOST:-144.217.95.231}"
DEFAULT_DIR="${SERVER_DIR:-/home/ubuntu/pyTrade3/}"

DRY_RUN=false
CUSTOM_DEST=""

# Duyệt tham số dòng lệnh
for arg in "$@"; do
    case "$arg" in
        -n|--dry-run)
            DRY_RUN=true
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS] [user@host:destination_path]"
            echo ""
            echo "Options:"
            echo "  -n, --dry-run    Show what would be copied without making changes"
            echo "  -h, --help       Show this help message"
            echo ""
            echo "Default destination: ${DEFAULT_USER}@${DEFAULT_HOST}:${DEFAULT_DIR}"
            exit 0
            ;;
        *)
            CUSTOM_DEST="$arg"
            ;;
    esac
done

if [[ -n "$CUSTOM_DEST" ]]; then
    REMOTE_TARGET="$CUSTOM_DEST"
else
    REMOTE_TARGET="${DEFAULT_USER}@${DEFAULT_HOST}:${DEFAULT_DIR}"
fi

REMOTE_HOST_PART="${REMOTE_TARGET%%:*}"
REMOTE_DIR_PART="${REMOTE_TARGET#*:}"
REMOTE_DIR_PART="${REMOTE_DIR_PART%/}"

# Đảm bảo lệnh rsync có sẵn
if ! command -v rsync &>/dev/null; then
    echo "❌ Lỗi: rsync chưa được cài đặt trên máy này."
    exit 1
fi

# Chạy kiểm tra tự động trước khi deploy
if [[ -x "${PROJECT_DIR}scripts/verify_py.sh" ]]; then
    echo "🔍 Đang chạy ./scripts/verify_py.sh trước khi upload..."
    "${PROJECT_DIR}scripts/verify_py.sh"
fi

echo "=================================================================="
echo "🚀 pyTrade3 - Upload Code lên Server OVH"
echo "=================================================================="
echo "📂 Thư mục nguồn      : $PROJECT_DIR"
echo "🎯 Đích đến           : $REMOTE_TARGET"
if [[ "$DRY_RUN" == true ]]; then
    echo "⚠️  CHẾ ĐỘ KIỂM TRA    : DRY-RUN (không ghi file)"
fi
echo "🛡️  Dữ liệu loại trừ  : *.db, *.csv, *.log, .env, .venv, cache..."
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
set exit_status [lindex $result 3]
exit $exit_status
EOF
    else
        "$@"
    fi
}

# Tự động sao lưu SQLite DB & CSV trên Server OVH trước khi cập nhật code (giữ 10 bản gần nhất)
if [[ "$DRY_RUN" == false ]]; then
    echo "💾 Đang tự động sao lưu trading_bot.db & CSV trên Server ($REMOTE_HOST_PART)..."
    run_with_auth ssh -o ConnectTimeout=10 "$REMOTE_HOST_PART" "mkdir -p '${REMOTE_DIR_PART}/backups' && \
        TS=\$(date +%Y%m%d_%H%M%S) && \
        if [ -f '${REMOTE_DIR_PART}/trading_bot.db' ]; then python3 -c \"import sqlite3; s=sqlite3.connect('${REMOTE_DIR_PART}/trading_bot.db'); d=sqlite3.connect('${REMOTE_DIR_PART}/backups/trading_bot_\${TS}.db'); s.backup(d); s.close(); d.close()\" 2>/dev/null || cp '${REMOTE_DIR_PART}/trading_bot.db' \"${REMOTE_DIR_PART}/backups/trading_bot_\${TS}.db\"; fi && \
        if [ -f '${REMOTE_DIR_PART}/trading_orders_history.csv' ]; then cp '${REMOTE_DIR_PART}/trading_orders_history.csv' \"${REMOTE_DIR_PART}/backups/orders_\${TS}.csv\"; fi && \
        ls -1t '${REMOTE_DIR_PART}/backups'/trading_bot_*.db 2>/dev/null | tail -n +11 | xargs -r rm -f && \
        ls -1t '${REMOTE_DIR_PART}/backups'/orders_*.csv 2>/dev/null | tail -n +11 | xargs -r rm -f" || echo "⚠️  Không thể tạo bản backup từ xa (có thể lần đầu deploy), tiếp tục rsync..."
fi

RSYNC_OPTS=(
    -avz
    --progress
    --exclude="*.db"
    --exclude="*.db-journal"
    --exclude="*.sqlite"
    --exclude="*.sqlite3"
    --exclude="*.csv"
    --exclude="*.log"
    --exclude="*.pkl"
    --exclude=".env"
    --exclude=".venv/"
    --exclude="venv/"
    --exclude="__pycache__/"
    --exclude="*.pyc"
    --exclude="*.pyo"
    --exclude=".git/"
    --exclude=".DS_Store"
    --exclude=".vscode/"
    --exclude=".idea/"
    --exclude="scratch/"
    --exclude="archive/"
)

if [[ "$DRY_RUN" == true ]]; then
    RSYNC_OPTS+=(-n)
fi

# Thực thi rsync
run_with_auth rsync "${RSYNC_OPTS[@]}" "$PROJECT_DIR" "${REMOTE_TARGET%/}/"

# Dọn dẹp an toàn các file cũ ở root đã được chuyển vào backend/ và frontend/
if [[ "$DRY_RUN" == false ]]; then
    echo "🧹 Dọn dẹp các file cũ ở root trên Server..."
    run_with_auth ssh -o ConnectTimeout=10 "$REMOTE_HOST_PART" "cd '${REMOTE_DIR_PART}' && rm -f config.py database.py exchange.py ib_api.py pdt_protector.py trading_bot.py gui.py ui_components.py workers.py notifier.py analyst_scraper.py portfolio_metrics.py ibkr_watchdog.py" || true
fi

echo "------------------------------------------------------------------"
if [[ "$DRY_RUN" == true ]]; then
    echo "✅ Hoàn tất kiểm tra (Dry-run). Không có thay đổi nào được ghi."
else
    echo "✅ Upload code thành công! Dữ liệu trên server đã được giữ nguyên an toàn."
fi
echo "=================================================================="
