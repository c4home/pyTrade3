# 📋 Kế Hoạch Phân Tách Kiến Trúc 3 Tầng (Frontend / Services / Backend Engine) — `pyTrade3`

> **Mục tiêu:** Áp dụng **Quy tắc Chống File Khổng Lồ (Anti-Monolith Rule)** trong `docs/QUY_TRINH_PHAT_TRIEN_APP_BANG_ANTIGRAVITY.md` để chia nhỏ `gui.py` (2.518 dòng) và `trading_bot.py` (1.955 dòng) thành các module dưới 800–1.200 dòng.
> **Hiệu quả tiết kiệm Token:** Giảm **70% – 85% token** ở mọi phiên chat tương lai (sửa giao diện chỉ mở file UI, sửa thông báo chỉ mở `notifier.py`, sửa kết nối chỉ mở `ibkr_watchdog.py`, sửa thuật toán chỉ mở `trading_bot.py`).
> **Cam kết An toàn (`AGENTS.md`):** Giữ nguyên **100%** thuật toán `calculate_score()`, 13 bộ lọc mua, 7 quy tắc bán và cơ chế đồng bộ với `backtest/core_backtest_engine.py`.

---

## 🏗️ Sơ Đồ Kiến Trúc Thư Mục Thực Tế (`pyTrade3`)

```text
pyTrade3/
├── 🚀 main.py                     (Điểm khởi chạy ứng dụng Desktop ngoài thư mục gốc)
│
├── 🎯 backend/                    (TẦNG LOGIC & DỮ LIỆU)
│   ├── __init__.py                (Cấu hình sys.path)
│   ├── config.py                  (Cấu hình .env, SemVer, Logger, ThreadPool)
│   ├── database.py                (SQLite PRAGMA user_version, CSVManager)
│   ├── exchange.py                (Quy đổi tỷ giá ngoại tệ tự động)
│   ├── ib_api.py                  (Socket EWrapper/EClient giao tiếp TWS/Gateway)
│   ├── ibkr_watchdog.py           (Tự động kết nối lại & kiểm tra cổng IBKR)
│   ├── notifier.py                (Dịch vụ gửi Email HTML)
│   ├── pdt_protector.py           (Bảo vệ tài khoản khỏi quy tắc PDT)
│   ├── analyst_scraper.py         (Thu thập Target & Rating UBS, Barclays, MS, Yahoo)
│   ├── portfolio_metrics.py       (Tính tổng PnL EUR, Daily PnL & phân bổ danh mục)
│   └── trading_bot.py             (Lõi thuật toán TradingBot, Smart Score, Orders)
│
├── 🖥️ frontend/                   (TẦNG GIAO DIỆN PYQT6)
│   ├── __init__.py                (Cấu hình sys.path)
│   ├── gui.py                     (Nhạc trưởng điều phối sự kiện nút bấm & bảng dữ liệu)
│   ├── ui_components.py           (NumericTableWidgetItem, UISetupMixin, Dark Theme)
│   └── workers.py                 (QThread chạy ngầm: BacktestThread, MaintenanceRoutineThread)
│
├── 📊 backtest/                   (Mô phỏng & kiểm định thuật toán)
├── 📦 assets/                     (Icons & ubs_links.json)
└── 🛠️ scripts/                    (verify_py.sh, deploy.sh, sync_from_server.sh)
```

---

## 🚀 Lộ Trình Thực Thi Từng Task Độc Lập (1 Task = 1 Phiên Chat)

### [x] Task 1: Tách Dịch Vụ Thông Báo Email (`notifier.py`) Khỏi `gui.py`
* **Mục tiêu:** Đưa toàn bộ ~260 dòng code SMTP + HTML template ra khỏi lớp giao diện PyQt6.
* **File tham gia (2 file):** `notifier.py` (tạo mới), `gui.py` (cập nhật), `scripts/verify_py.sh` (thêm `notifier.py` vào `ROOT_FILES`).
* **Tọa độ dòng code trong `gui.py` (theo `docs/CODEBASE_MAP.md`):**
  * `TradingApp._send_ibkr_disconnect_email()`: Dòng `539` – `589` (51 dòng)
  * `TradingApp._send_ibkr_recovery_email()`: Dòng `591` – `632` (42 dòng)
  * `TradingApp.send_trade_email()`: Dòng `790` – `955` (166 dòng)
* **Thiết kế đầu vào / đầu ra:**
  * Tạo class hoặc module `EmailNotifier` trong `notifier.py`.
  * Giữ hàm ủy quyền (wrapper 3 dòng) `send_trade_email()`, `_send_ibkr_disconnect_email()`, `_send_ibkr_recovery_email()` trên `TradingApp` gọi sang `notifier.py` để tương thích ngược 100% với `trading_bot.py` (`self.app.send_trade_email(...)`).
* **Kiểm thử nghiệm thu (`0 token`):**
  ```bash
  ./scripts/verify_py.sh
  ```

---

### [x] Task 2: Tách Luồng Chạy Ngầm (`workers.py`) & Hàm Tính Toán Danh Mục (`portfolio_metrics.py`) Khỏi `gui.py`
* **Mục tiêu:** Đưa các luồng xử lý nặng (`QThread`) và các hàm toán học tính PnL toàn danh mục về đúng tầng Backend/Workers.
* **File tham gia (3 file):** `workers.py` (tạo mới), `portfolio_metrics.py` (tạo mới), `gui.py` (cập nhật), `scripts/verify_py.sh`.
* **Tọa độ dòng code trong `gui.py` (theo `docs/CODEBASE_MAP.md`):**
  * `BacktestThread`: Dòng `20` – `49` (30 dòng)
  * `MaintenanceRoutineThread`: Dòng `51` – `155` (105 dòng)
  * `_get_usd_to_eur_rate()`, `_calc_portfolio_composition()`, `_calc_total_positions_pnl_eur()`, `_calc_total_daily_pnl_eur()`: Dòng `548` – `663` (116 dòng)
* **Thiết kế đầu vào / đầu ra:**
  * `workers.py` chứa `BacktestThread` và `MaintenanceRoutineThread` (giữ nguyên điều kiện lọc `pf >= 1.2` và `MA200`).
  * `portfolio_metrics.py` chứa các hàm tính toán thuần nhận `(bots, ibapi)` và trả về kết quả số học EUR.
* **Kiểm thử nghiệm thu (`0 token`):**
  ```bash
  ./scripts/verify_py.sh
  ```

---

### [x] Task 3: Tách Quản Lý Kết Nối & Watchdog IBKR (`ibkr_watchdog.py`) Khỏi `gui.py`
* **Mục tiêu:** Cô lập toàn bộ máy trạng thái (state machine) tự động kết nối, quét cổng port `7497/7496/4001/4002` và theo dõi mất kết nối sang một Mixin độc lập.
* **File tham gia (2 file):** `ibkr_watchdog.py` (tạo mới), `gui.py` (cập nhật), `scripts/verify_py.sh`.
* **Tọa độ dòng code trong `gui.py` (theo `docs/CODEBASE_MAP.md`):**
  * `_auto_connect()`, `_check_auto_reconnect()`, `_trigger_auto_reconnect()`, `_on_auto_reconnect_success()`, `_on_auto_reconnect_fail()`, `_check_ibkr_watchdog()`, `_on_ibkr_reconnected()`: Dòng `245` – `538` (~294 dòng).
  * `toggle_connection()`, `_on_connect_success()`, `_on_connect_fail()`: Dòng `1712` – `1800` (~89 dòng).
* **Thiết kế đầu vào / đầu ra:**
  * Tạo class `IBKRWatchdogMixin` trong `ibkr_watchdog.py`.
  * `class TradingApp(QMainWindow, IBKRWatchdogMixin):` kế thừa trực tiếp, không làm thay đổi bất kỳ thuộc tính `self.ibapi` hay timer nào.
* **Kiểm thử nghiệm thu (`0 token`):**
  ```bash
  ./scripts/verify_py.sh
  ```

---

### [x] Task 4: Tách Khởi Tạo Khung Giao Diện & Widget (`ui_components.py`) Khỏi `gui.py`
* **Mục tiêu:** Tách phần khai báo bố cục nút bấm, thanh công cụ, bảng 24 cột, stylesheet (`init_ui`) ra khỏi phần xử lý sự kiện của `gui.py`, đồng thời dọn bỏ hàm `on_header_clicked` bị định nghĩa trùng lặp.
* **File tham gia (2 file):** `ui_components.py` (tạo mới), `gui.py` (cập nhật), `scripts/verify_py.sh`.
* **Tọa độ dòng code trong `gui.py` (theo `docs/CODEBASE_MAP.md`):**
  * `NumericTableWidgetItem`: Dòng `10` – `18` (9 dòng)
  * `init_ui()`: Dòng `705` – `1118` (414 dòng)
  * Xóa hàm `on_header_clicked()` bị trùng ở dòng `682` – `686` (giữ bản ở dòng `1180`).
* **Thiết kế đầu vào / đầu ra:**
  * Tạo `UISetupMixin` (hoặc hàm `setup_main_window_ui(app)`) và `NumericTableWidgetItem` trong `ui_components.py`.
  * Sau bước này, `gui.py` giảm từ **2.518 dòng xuống còn ~1.100 dòng**!
* **Kiểm thử nghiệm thu (`0 token`):**
  ```bash
  ./scripts/verify_py.sh
  ```

---

### [x] Task 5: Tách Bộ Thu Thập Dữ Liệu Phân Tích (`analyst_scraper.py`) Khỏi `trading_bot.py`
* **Mục tiêu:** Giảm tải cho `trading_bot.py` bằng cách tách riêng toàn bộ logic cào web/API lấy mục tiêu giá của UBS, Barclays, Morgan Stanley, Yahoo Finance và lịch sử sự kiện Earnings sang module dữ liệu độc lập, giữ `trading_bot.py` thuần túy cho Chỉ báo kỹ thuật, Chấm điểm `calculate_score()` và Đặt lệnh.
* **File tham gia (2 file):** `analyst_scraper.py` (tạo mới), `trading_bot.py` (cập nhật), `scripts/verify_py.sh`.
* **Tọa độ dòng code trong `trading_bot.py` (theo `docs/CODEBASE_MAP.md`):**
  * `get_bank_note()` & `fetch_fresh_bank_note()`: Dòng `276` – `389` (114 dòng)
  * `fetch_next_event_date()`: Dòng `600` – `643` (44 dòng)
  * `update_analyst_data()`, `get_barclays_target()`, `get_ubs_target()`, `get_morgan_stanley_target()`: Dòng `1074` – `1234` (161 dòng)
* **Thiết kế đầu vào / đầu ra:**
  * Tạo `AnalystDataMixin` trong `analyst_scraper.py` để `class TradingBot(AnalystDataMixin):` kế thừa.
  * Giữ nguyên 100% chữ ký hàm và công thức `calculate_analyst_modifier()` trong `trading_bot.py`.
* **Kiểm thử nghiệm thu (`0 token`):**
  ```bash
  ./scripts/verify_py.sh
  ```

---

## ⚡ Hướng Dẫn Chạy Từng Task Để Tiết Kiệm Tối Đa Token

Theo đúng **Nguyên tắc 1 Nhiệm Vụ = 1 Phiên Chat Mới** trong `docs/QUY_TRINH_PHAT_TRIEN_APP_BANG_ANTIGRAVITY.md`, ở mỗi phiên chat mới bạn chỉ cần copy & paste đúng câu lệnh sau:

```text
Đọc @docs/plans/refactor_frontend_backend.md và @docs/CODEBASE_MAP.md.
Hãy thực thi duy nhất Task [Số thứ tự Task, ví dụ: 1].
Chỉ đọc đúng khoảng dòng đã ghi trong kế hoạch, tách file, cập nhật scripts/verify_py.sh và chạy ./scripts/verify_py.sh để kiểm chứng PASS 100% + tự động cập nhật CODEBASE_MAP.md, đánh dấu [x] vào Task trong file kế hoạch rồi dừng lại.
```
