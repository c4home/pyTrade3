# 📊 Nhật Ký Đo Lường Hiệu Suất & Chất Lượng Thuật Toán (`pyTrade3`)

> Tài liệu này theo dõi quy mô mã nguồn, độ an toàn kiểm thử (`./verify_py.sh`) và hiệu suất định lượng của thuật toán qua từng phiên bản.

| Ngày | Phiên bản | Tổng dòng code Python | Kiểm thử `./verify_py.sh` | Backtest Total PnL (66 mã) | Profit Factor | Win Rate | Ghi chú thay đổi |
| :--- | :--- | ---: | :---: | ---: | ---: | ---: | :--- |
| 2026-10-26 | `v3.1.0` (`20261026_v1`) | 6.680 | **8/8 PASS (100%)** | `+34.504 EUR` | `1.47` | `63.8%` | Khởi tạo hạ tầng Antigravity (`verify_py.sh`, `CODEBASE_MAP.md`, `.antigravityignore`), vá 4 lỗi Biến Ma (`self.app.bots`, `readonly=True` bảo vệ `prev_macd_signal`, `dynamic_max` trong `place_buy_order`, lưu `bought_strategy` vào SQLite `PRAGMA user_version=2`) & tự động backup DB trên OVH trong `deploy.sh`. |
| 2026-10-26 | `v3.2.0` (`20261026_v2`) | 6.683 | **9/9 PASS (100%)** | **`+40.218 EUR`** *(+5.714€)* | **`1.72`** *(+0.25)* | **`67.0%`** *(+3.2%)* | Đồng bộ 100% công thức chỉ báo (`RSI`, `ADX` 14d Rolling Mean, `MACD` EMA `adjust=False` & `S_BULL` khi `MACD > 0`), `prot_drop=0.25` (khóa 75% lãi đỉnh), khóa `bought_strategy` Stop Cap, bộ lọc ATR Fast-Rising Momentum và ETF/ETC `+6` Boost giữa `trading_bot.py` và `core_backtest_engine.py`. Giảm 71 lệnh chạm Stop Loss (tiết kiệm 16.950€ thua lỗ). |
| 2026-10-26 | `v3.3.0` (`20261026_v3`) | 6.779 | **10/10 PASS (100%)** | **`+43.080 EUR`** *(+2.862€ vs v3.2 / +8.576€ vs v3.1)* | **`1.92`** *(+0.20)* | **`64.2%`** | Tích hợp Gói nâng cấp `C4`: (1) Bộ lọc chất lượng Auto-Watchlist yêu cầu `Price >= MA200` khi mua & lọc `Price >= MA200` + 2Y Backtest `PF >= 1.2` trong `MaintenanceRoutineThread`; (2) `Time-Stop Stagnation Exit` (`>= 25 ngày` & `PnL <= -0.5%`); (3) Giới hạn tập trung ngành `MAX_SECTOR_POSITIONS = 6`. Giảm thêm 63 lệnh chạm Full Stop Loss (tiết kiệm thêm 15.093€ lỗ Stop, tổng giảm 134 lệnh Full Stop Loss so với ban đầu). |

---

## 🔬 Bước 3: Báo Cáo Kiểm Nghiệm Định Lượng 3 Nhóm Nâng Cấp (Trên 65 Mã DB Lịch Sử 2 Năm)

| Kịch Bản Kiểm Nghiệm | Total PnL | Profit Factor | Win Rate | Số Lệnh | Tổng Lỗ Gộp (`Gross Loss`) | Số Lệnh Chạm Full Stop Loss |
| :--- | ---: | :---: | :---: | :---: | ---: | :---: |
| **0. Baseline `v3.2.0` (Hiện tại)** | **`+40.218 €`** | **`1.72`** | **`67.0%`** | `758` | `-55.833 €` | `235 lệnh (-54.745 €)` |
| **1a. Breakeven Floor (`peak >= +3.0% ➔ floor +0.5%`)** | `+34.594 €` *(-5.624€)* | `1.64` | `63.6%` | `781` | `-54.254 €` | `218 lệnh (-50.664 €)` |
| **1b. Stop Tighten (`peak >= +3.0% ➔ stop -1.0%`)** | `+35.703 €` *(-4.515€)* | `1.64` | `63.6%` | `773` | `-55.388 €` | `267 lệnh (-54.317 €)` |
| **1c. Time-Stop Stagnation Exit (`>= 25 ngày & PnL <= -0.5%`)** | **`+41.595 €`** *(+1.377€)* | **`1.81`** | `62.9%` | `780` | **`-51.666 €`** *(giảm 4.167€ lỗ)* | **`187 lệnh (-43.866 €)`** *(giảm 48 Stops)* |
| **2a. Chỉ nhóm Core (`is_auto_watchlist=0`, 55 mã)** | `+40.149 €` | **`1.92`** | **`69.2%`** | `640` | `-43.631 €` | `189 lệnh (-43.181 €)` |
| **2b. Chỉ nhóm Auto-Watchlist (`is_auto_watchlist=1`, 10 mã)** | `+69 €` | `1.01` | `55.1%` | `118` | `-12.202 €` | `46 lệnh (-11.565 €)` |
| **2c. Bộ lọc Auto-Watchlist/Manual yêu cầu `Price > MA200`** | **`+41.930 €`** *(+1.712€)* | **`1.81`** | **`68.0%`** | `732` | **`-51.480 €`** *(giảm 4.353€ lỗ)* | **`220 lệnh (-50.486 €)`** *(giảm 15 Stops)* |
| **2d. Chặn MOMENTUM Bull-Trap dưới `MA200` + `AW > MA200` (`M2`)** | **`+41.158 €`** *(+940€)* | **`1.88`** | **`68.2%`** | `682` | **`-46.994 €`** *(giảm 8.839€ lỗ)* | **`202 lệnh (-45.970 €)`** *(giảm 33 Stops)* |
| **3a. Giới hạn Tập Trung Ngành (`Max 6 lệnh mở / Sector`)** | `+40.168 €` | `1.73` | `67.3%` | `749` | `-54.741 €` *(giảm 1.092€ lỗ)* | `231 lệnh (-53.863 €)` |
| **🏆 TỔNG HỢP `C2` (`AW > MA200` + `TimeStop 25d <= -0.5%`)** | **`+42.855 €`** *(+2.637€)* | **`1.90`** | `63.8%` | `754` | **`-47.823 €`** *(giảm 8.010€ lỗ)* | **`175 lệnh (-40.321 €)`** *(giảm 60 Stops)* |
| **🏆 TỔNG HỢP `C4` (`C2` + `Max 6 lệnh/Sector Guard`)** | **`+43.080 €`** *(+2.862€)* | **`1.92`** | `64.2%` | `745` | **`-46.859 €`** *(giảm 8.974€ lỗ)* | **`172 lệnh (-39.652 €)`** *(giảm 63 Stops)* |
| **🛡️ TỔNG HỢP AN TOÀN CAO NHẤT `M4` (`M2` + `TimeStop 25d` + `Max 6/Sector`)** | **`+41.413 €`** *(+1.195€)* | **`1.95`** | `64.0%` | `695` | **`-43.446 €`** *(giảm 12.387€ lỗ)* | **`158 lệnh (-36.518 €)`** *(giảm 77 Stops)* |

