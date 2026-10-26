#!/usr/bin/env bash
# ==============================================================================
# pyTrade3 - Deploy Script to Production Server (Upload nhanh lên Server)
#
# Rule: KHÔNG upload các file data (*.db, *.csv, *.log, .env) để tránh ghi đè
#       dữ liệu giao dịch và cấu hình hiện có trên server.
#
# Cách dùng:
#   ./deploy.sh                  # Deploy tới server mặc định (ubuntu@144.217.95.231)
#   ./deploy.sh --dry-run        # Kiểm tra trước danh sách file sẽ upload (chưa upload thật)
#   ./deploy.sh user@host:path   # Deploy tới host/path tùy chỉnh
# ==============================================================================

set -euo pipefail

# 1. Cấu hình mặc định (có thể override bằng biến môi trường hoặc tham số dòng lệnh)
DEFAULT_USER="ubuntu"
DEFAULT_HOST="144.217.95.231"
DEFAULT_DIR="/home/ubuntu/pyTrade3/"

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

# Đảm bảo lệnh rsync có sẵn
if ! command -v rsync &>/dev/null; then
    echo "❌ Lỗi: rsync chưa được cài đặt trên máy này."
    exit 1
fi

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/"

# Chạy kiểm tra tự động trước khi deploy
if [[ -x "${PROJECT_DIR}verify_py.sh" ]]; then
    echo "🔍 Đang chạy ./verify_py.sh trước khi upload..."
    "${PROJECT_DIR}verify_py.sh"
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

# Tự động sao lưu SQLite DB & CSV trên Server OVH trước khi cập nhật code (giữ 10 bản gần nhất)
if [[ "$DRY_RUN" == false ]]; then
    REMOTE_HOST_PART="${REMOTE_TARGET%%:*}"
    REMOTE_DIR_PART="${REMOTE_TARGET#*:}"
    echo "💾 Đang tự động sao lưu trading_bot.db & CSV trên Server ($REMOTE_HOST_PART)..."
    ssh -o ConnectTimeout=10 "$REMOTE_HOST_PART" "mkdir -p '${REMOTE_DIR_PART%/}/backups' && \
        TS=\$(date +%Y%m%d_%H%M%S) && \
        if [ -f '${REMOTE_DIR_PART%/}/trading_bot.db' ]; then cp '${REMOTE_DIR_PART%/}/trading_bot.db' \"${REMOTE_DIR_PART%/}/backups/trading_bot_\${TS}.db\"; fi && \
        if [ -f '${REMOTE_DIR_PART%/}/trading_orders_history.csv' ]; then cp '${REMOTE_DIR_PART%/}/trading_orders_history.csv' \"${REMOTE_DIR_PART%/}/backups/orders_\${TS}.csv\"; fi && \
        ls -1t '${REMOTE_DIR_PART%/}/backups'/trading_bot_*.db 2>/dev/null | tail -n +11 | xargs -r rm -f && \
        ls -1t '${REMOTE_DIR_PART%/}/backups'/orders_*.csv 2>/dev/null | tail -n +11 | xargs -r rm -f" || echo "⚠️  Không thể tạo bản backup từ xa (có thể lần đầu deploy), tiếp tục rsync..."
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
rsync "${RSYNC_OPTS[@]}" "$PROJECT_DIR" "$REMOTE_TARGET"

echo "------------------------------------------------------------------"
if [[ "$DRY_RUN" == true ]]; then
    echo "✅ Hoàn tất kiểm tra (Dry-run). Không có thay đổi nào được ghi."
else
    echo "✅ Upload code thành công! Dữ liệu trên server đã được giữ nguyên an toàn."
fi
echo "=================================================================="
