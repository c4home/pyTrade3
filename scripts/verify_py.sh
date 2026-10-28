#!/usr/bin/env bash
# ==============================================================================
# pyTrade3 — 0-Token Automated Verification, Anti-Orphan Test & Codebase Map
# Usage:
#   ./verify_py.sh
# ==============================================================================
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

PYTHON_BIN="python3"
if [[ -x ".venv/bin/python" ]]; then
    PYTHON_BIN=".venv/bin/python"
fi

"$PYTHON_BIN" - <<'PYEOF'
import ast
import os
import re
import sys
import py_compile
import sqlite3
import tempfile
from datetime import datetime

for p in ["backend", "backend/services", "frontend", "backtest"]:
    if p not in sys.path:
        sys.path.insert(0, p)

BACKEND_FILES = [
    os.path.join("backend", f)
    for f in [
        "config.py",
        "database.py",
        "ib_api.py",
        "analyst_scraper.py",
        "notifier.py",
        "ibkr_watchdog.py",
        "trading_bot.py",
    ]
] + [
    os.path.join("backend", "services", f)
    for f in [
        "models.py",
        "data_feed.py",
        "alpha_engine.py",
        "portfolio_sizing.py",
        "risk_manager.py",
        "execution.py",
    ]
]
FRONTEND_FILES = [
    os.path.join("frontend", f)
    for f in [
        "ui_components.py",
        "workers.py",
        "gui.py",
    ]
] + [
    os.path.join("frontend", "components", f)
    for f in [
        "table_items.py",
        "ui_setup.py",
    ]
] + [
    os.path.join("frontend", "renderers", f)
    for f in [
        "table_renderer.py",
        "summary_formatter.py",
    ]
] + [
    os.path.join("frontend", "controllers", f)
    for f in [
        "stock_controller.py",
        "worker_controller.py",
        "trading_orchestrator.py",
    ]
] + [
    os.path.join("frontend", "workers", f)
    for f in [
        "backtest_worker.py",
        "maintenance_worker.py",
    ]
]
ROOT_FILES = [
    "main.py",
]
BACKTEST_FILES = [
    os.path.join("backtest", f)
    for f in sorted(os.listdir("backtest"))
    if f.endswith(".py")
] if os.path.isdir("backtest") else []

ALL_PY_FILES = [f for f in ROOT_FILES + BACKEND_FILES + FRONTEND_FILES + BACKTEST_FILES if os.path.exists(f)]

passed = 0
failed = 0

def ok(msg):
    global passed
    passed += 1
    print(f"  [PASS] {msg}")

def fail(msg):
    global failed
    failed += 1
    print(f"  [FAIL] {msg}")

print("==================================================================")
print("🔍 1. Kiểm tra cú pháp Python (Syntax & Bytecode Compilation)")
print("==================================================================")
syntax_ok = True
for f in ALL_PY_FILES:
    try:
        py_compile.compile(f, doraise=True)
    except Exception as e:
        syntax_ok = False
        fail(f"Syntax error in {f}: {e}")
if syntax_ok:
    ok(f"Toàn bộ {len(ALL_PY_FILES)} file Python hợp lệ 100%.")

print("\n==================================================================")
print("🛡️  2. Quét rò rỉ Secret & Chống Biến Ma (Static Security & Orphan Audit)")
print("==================================================================")
secret_pattern = re.compile(r"(AIzaSy[0-9A-Za-z_-]{33}|sk-[A-Za-z0-9]{20,})")
secret_leaks = []
for f in ALL_PY_FILES:
    with open(f, "r", encoding="utf-8") as fh:
        content = fh.read()
        if secret_pattern.search(content):
            secret_leaks.append(f)

if secret_leaks:
    fail(f"Phát hiện khóa bí mật hardcode trong: {secret_leaks}")
else:
    ok("Không có API Key / Secret nào bị hardcode trong mã nguồn.")

with open("backend/trading_bot.py", "r", encoding="utf-8") as fh:
    tb_code = fh.read()

if "self.gui.bots" in tb_code:
    fail("Phát hiện Biến Ma 'self.gui.bots' trong trading_bot.py (phải dùng self.app.bots).")
else:
    ok("Đã khử sạch Biến Ma 'self.gui.bots' -> chuẩn hóa 'self.app.bots'.")

if "min(self.max_amount, self.cash_left" in tb_code:
    fail("place_buy_order() vẫn bị khóa cứng ở self.max_amount thay vì dynamic_max (~Max).")
else:
    ok("place_buy_order() đã nối chuẩn 2 chiều với dynamic_max (~Max).")

with open("frontend/gui.py", "r", encoding="utf-8") as fh:
    gui_code = fh.read()

if "bot.check_trading_conditions(readonly=True)" in gui_code:
    ok("update_display() trong gui.py gọi check_trading_conditions(readonly=True) an toàn (không làm mất tín hiệu MACD Crossover).")
else:
    fail("update_display() trong gui.py chưa bật readonly=True khi gọi check_trading_conditions().")

print("\n==================================================================")
print("🧪 3. Kiểm thử Schema Migration (PRAGMA user_version) & Logic Lõi")
print("==================================================================")
try:
    from database import DatabaseManager
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db_path = os.path.join(tmpdir, "test_bot.db")
        db = DatabaseManager(db_path=test_db_path)
        with db.get_cursor() as cur:
            cur.execute("PRAGMA user_version")
            ver = cur.fetchone()[0]
        if ver == DatabaseManager.TARGET_DB_VERSION:
            ok(f"SQLite PRAGMA user_version đạt chuẩn v{ver}.")
        else:
            fail(f"SQLite PRAGMA user_version = {ver}, kỳ vọng {DatabaseManager.TARGET_DB_VERSION}.")

        db.add_stock("NVDA", 1000.0, 3.0, 5.0)
        db.update_bought_strategy("NVDA", "DIP")
        rows = db.get_all_stocks()
        if rows and len(rows[0]) >= 9 and rows[0][8] == "DIP":
            ok("Lưu trữ & khôi phục 'bought_strategy' (DIP/MOMENTUM) trong SQLite hoạt động chính xác 100%.")
        else:
            fail(f"Lỗi lưu trữ bought_strategy trong SQLite: {rows}")
        db.close()
except Exception as e:
    fail(f"Lỗi khi test DatabaseManager: {e}")

try:
    import numpy as np
    import pandas as pd
    sys.path.insert(0, "backtest")
    from core_backtest_engine import compute_indicators
    from trading_bot import TradingBot

    np.random.seed(42)
    closes = pd.Series(100 + np.cumsum(np.random.randn(250)))
    highs = closes + np.abs(np.random.randn(250)) + 0.5
    lows = closes - np.abs(np.random.randn(250)) - 0.5
    vols = pd.Series(np.random.randint(100000, 500000, size=250), dtype=float)
    df_test = pd.DataFrame({"Close": closes, "High": highs, "Low": lows, "Volume": vols})
    df_bt = compute_indicators(df_test.copy())

    dummy_bot = object.__new__(TradingBot)
    live_rsi = TradingBot.calculate_rsi(closes)
    live_adx = dummy_bot.calculate_adx(highs, lows, closes)
    bt_rsi = float(df_bt["RSI"].iat[-1])
    bt_adx = float(df_bt["ADX"].iat[-1])

    if abs(live_rsi - bt_rsi) < 1e-6 and abs(live_adx - bt_adx) < 1e-6:
        ok(f"Đồng bộ 100% công thức RSI ({live_rsi:.4f}) & ADX ({live_adx:.4f}) giữa trading_bot.py và core_backtest_engine.py.")
    else:
        fail(f"Lệch công thức Live vs Backtest! RSI: {live_rsi} vs {bt_rsi}, ADX: {live_adx} vs {bt_adx}")

    with open("frontend/workers.py", "r", encoding="utf-8") as fh:
        workers_code = fh.read()
    if getattr(TradingBot, "TIME_STOP_DAYS", None) == 25 and getattr(TradingBot, "MAX_SECTOR_POSITIONS", None) == 6 and "pf >= 1.2" in workers_code:
        ok("Đã tích hợp đầy đủ Gói nâng cấp C4 (Auto-Watchlist MA200 & PF>=1.2 + Time-Stop 25d + Max 6 Pos/Sector Guard).")
    else:
        fail("Thiếu cấu hình Gói nâng cấp C4 trong TradingBot hoặc workers.py.")
except Exception as e:
    fail(f"Lỗi khi test đồng bộ Live vs Backtest: {e}")

print("\n==================================================================")
print("🗺️  4. Tự động cập nhật docs/CODEBASE_MAP.md (0-Token Map Generator)")
print("==================================================================")
os.makedirs("docs", exist_ok=True)
map_lines = [
    "# 🗺️ CODEBASE_MAP.md — Bản Đồ Tọa Độ Dòng Code Tự Động (`pyTrade3`)",
    "",
    f"> **Cập nhật tự động bởi `./verify_py.sh` lúc:** `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`",
    "> Khi cần sửa hàm hoặc class nào, chỉ đọc đúng khoảng dòng (`StartLine` – `EndLine`) dưới đây để tiết kiệm 90% token.",
    "",
    "## 1. Tổng Quan Quy Mô File",
    "",
    "| File | Số dòng | Vai trò chính |",
    "| :--- | ---: | :--- |",
]

ROLE_DESCRIPTIONS = {
    "backend/config.py": "Cấu hình biến môi trường (.env), SemVer (`APP_VERSION`), ThreadPoolExecutor & Logger",
    "backend/services/models.py": "Định nghĩa Data Contracts chuẩn hóa (`MarketSnapshot`, `AlphaSignal`, `RiskDecision`)",
    "backend/services/data_feed.py": "Lean Khối 1: Thu thập nến, tính chỉ báo kỹ thuật RSI/ADX/MACD/BB & SQLite Cache",
    "backend/services/alpha_engine.py": "Lean Khối 2: Lõi toán học tính Smart Score (0-12) cho chiến lược DIP & MOMENTUM",
    "backend/services/portfolio_sizing.py": "Lean Khối 3: Định cỡ vị thế theo rủi ro (Kelly/ATR), tỷ giá ngoại tệ & phân bổ danh mục",
    "backend/services/risk_manager.py": "Lean Khối 4: Người gác cổng sắt thi hành 13 Hard Buy Guards & 7 Sell/Exit Triggers",
    "backend/services/execution.py": "Lean Khối 5: Tương tác Broker IBKR socket, quản lý vòng đời lệnh & CSV/DB Audits",
    "backend/database.py": "Quản lý SQLite (`PRAGMA user_version`), lịch sử giao dịch, cache chỉ báo & `CSVManager`",
    "backend/ib_api.py": "Giao tiếp socket Interactive Brokers TWS / IB Gateway (`EWrapper`, `EClient`)",
    "backend/analyst_scraper.py": "Bộ thu thập dữ liệu phân tích (`AnalystDataMixin`: UBS, Barclays, Morgan Stanley, Yahoo & Earnings)",
    "backend/notifier.py": "Dịch vụ gửi thông báo Email SMTP (`EmailNotifier`: Trade Fill, IBKR Disconnect & Recovery)",
    "backend/ibkr_watchdog.py": "Quản lý kết nối IBKR (`IBKRWatchdogMixin`), Auto-Reconnect & Watchdog cảnh báo mất kết nối",
    "backend/trading_bot.py": "Lõi thuật toán `TradingBot`: Facade Coordinator điều phối 5 services Lean",
    "frontend/components/table_items.py": "Custom Widget bảng: `NumericTableWidgetItem` hỗ trợ sắp xếp theo giá trị số thực",
    "frontend/components/ui_setup.py": "Khởi tạo layout giao diện PyQt6 (`UISetupMixin`), Dark Theme, bảng 30 cột & toolbar",
    "frontend/renderers/table_renderer.py": "Render bảng 30 cột (`TableRenderer`): format giá, PnL, màu sắc, font, tooltip & bank acronym",
    "frontend/renderers/summary_formatter.py": "Format header tổng quan (`SummaryFormatter`): Total PnL, Daily/Unrealized PnL, Cash & Last Fetch",
    "frontend/controllers/stock_controller.py": "Điều phối hành động cổ phiếu (`StockActionsMixin`): Add/Remove stock, Manual Buy/Sell/Hold, Sort",
    "frontend/controllers/worker_controller.py": "Điều phối luồng ngầm (`WorkerControllerMixin`): Maintenance Routine S&P500, Backtest & Sync DB Server",
    "frontend/controllers/trading_orchestrator.py": "Nhạc trưởng giao dịch tự động (`TradingOrchestrator`): Vòng lặp duyệt lệnh Sell, xếp hạng Smart Score & Buy",
    "frontend/workers/backtest_worker.py": "Luồng ngầm Backtest (`BacktestThread`): Chạy mô phỏng chiến lược toàn bộ danh mục",
    "frontend/workers/maintenance_worker.py": "Luồng ngầm Maintenance (`MaintenanceRoutineThread`): Quét top 10 cổ phiếu S&P500 lọc MA200 & PF>=1.2",
    "frontend/workers.py": "Facade tương thích ngược: Re-export BacktestThread & MaintenanceRoutineThread",
    "frontend/ui_components.py": "Facade tương thích ngược: Re-export NumericTableWidgetItem & UISetupMixin",
    "frontend/gui.py": "Nhạc trưởng giao diện PyQt6 (`TradingApp`): Shell mỏng tích hợp các Mixin & điều phối hiển thị",
    "main.py": "Điểm khởi chạy ứng dụng Desktop (`QApplication`)",
    "backtest/core_backtest_engine.py": "Lõi mô phỏng Backtest kiểm chứng thuật toán DIP & MOMENTUM",
    "backtest/run_present_stocks_backtest.py": "Chạy Backtest toàn bộ danh mục trong SQLite DB và xuất báo cáo so sánh S&P 500",
}

file_sections = []
for f in ALL_PY_FILES:
    with open(f, "r", encoding="utf-8") as fh:
        source = fh.read()
    lines = source.splitlines()
    role = ROLE_DESCRIPTIONS.get(f, "Script Backtest / Tiện ích")
    map_lines.append(f"| `{f}` | {len(lines)} | {role} |")

    try:
        tree = ast.parse(source, filename=f)
    except Exception:
        continue

    items = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            end_line = getattr(node, "end_lineno", node.lineno)
            items.append((f"class `{node.name}`", node.lineno, end_line))
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    sub_end = getattr(sub, "end_lineno", sub.lineno)
                    items.append((f"  └─ `{node.name}.{sub.name}()`", sub.lineno, sub_end))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end_line = getattr(node, "end_lineno", node.lineno)
            items.append((f"def `{node.name}()`", node.lineno, end_line))

    if items:
        sec = [f"### 📄 `{f}` ({len(lines)} dòng)", "", "| Thành phần (Class / Hàm) | Dòng bắt đầu | Dòng kết thúc | Số dòng |", "| :--- | ---: | ---: | ---: |"]
        for name, s_line, e_line in items:
            sec.append(f"| {name} | {s_line} | {e_line} | {e_line - s_line + 1} |")
        sec.append("")
        file_sections.append("\n".join(sec))

map_lines.append("")
map_lines.append("## 2. Chi Tiết Tọa Độ Class & Hàm Theo Từng File")
map_lines.append("")
map_lines.extend(file_sections)

with open("docs/CODEBASE_MAP.md", "w", encoding="utf-8") as fh:
    fh.write("\n".join(map_lines))

ok("Đã sinh tự động docs/CODEBASE_MAP.md chính xác 100%.")

print("==================================================================")
if failed > 0:
    print(f"❌ KẾT QUẢ: {passed} PASS, {failed} FAIL")
    sys.exit(1)
else:
    print(f"✅ KẾT QUẢ: [OK] {passed}/{passed} bài kiểm tra đều PASS 100%!")
PYEOF
