# 🗺️ CODEBASE_MAP.md — Bản Đồ Tọa Độ Dòng Code Tự Động (`pyTrade3`)

> **Cập nhật tự động bởi `./verify_py.sh` lúc:** `2026-10-28 10:32:43`
> Khi cần sửa hàm hoặc class nào, chỉ đọc đúng khoảng dòng (`StartLine` – `EndLine`) dưới đây để tiết kiệm 90% token.

## 1. Tổng Quan Quy Mô File

| File | Số dòng | Vai trò chính |
| :--- | ---: | :--- |
| `main.py` | 37 | Điểm khởi chạy ứng dụng Desktop (`QApplication`) |
| `backend/config.py` | 107 | Cấu hình biến môi trường (.env), SemVer (`APP_VERSION`), ThreadPoolExecutor & Logger |
| `backend/database.py` | 690 | Quản lý SQLite (`PRAGMA user_version`), lịch sử giao dịch, cache chỉ báo & `CSVManager` |
| `backend/ib_api.py` | 256 | Giao tiếp socket Interactive Brokers TWS / IB Gateway (`EWrapper`, `EClient`) |
| `backend/analyst_scraper.py` | 327 | Bộ thu thập dữ liệu phân tích (`AnalystDataMixin`: UBS, Barclays, Morgan Stanley, Yahoo & Earnings) |
| `backend/notifier.py` | 270 | Dịch vụ gửi thông báo Email SMTP (`EmailNotifier`: Trade Fill, IBKR Disconnect & Recovery) |
| `backend/ibkr_watchdog.py` | 388 | Quản lý kết nối IBKR (`IBKRWatchdogMixin`), Auto-Reconnect & Watchdog cảnh báo mất kết nối |
| `backend/trading_bot.py` | 724 | Lõi thuật toán `TradingBot`: Facade Coordinator điều phối 5 services Lean |
| `backend/services/models.py` | 74 | Định nghĩa Data Contracts chuẩn hóa (`MarketSnapshot`, `AlphaSignal`, `RiskDecision`) |
| `backend/services/data_feed.py` | 479 | Lean Khối 1: Thu thập nến, tính chỉ báo kỹ thuật RSI/ADX/MACD/BB & SQLite Cache |
| `backend/services/alpha_engine.py` | 245 | Lean Khối 2: Lõi toán học tính Smart Score (0-12) cho chiến lược DIP & MOMENTUM |
| `backend/services/portfolio_sizing.py` | 287 | Lean Khối 3: Định cỡ vị thế theo rủi ro (Kelly/ATR), tỷ giá ngoại tệ & phân bổ danh mục |
| `backend/services/risk_manager.py` | 359 | Lean Khối 4: Người gác cổng sắt thi hành 13 Hard Buy Guards & 7 Sell/Exit Triggers |
| `backend/services/execution.py` | 183 | Lean Khối 5: Tương tác Broker IBKR socket, quản lý vòng đời lệnh & CSV/DB Audits |
| `frontend/ui_components.py` | 458 | Khởi tạo giao diện PyQt6 (`UISetupMixin`, `NumericTableWidgetItem`, bảng 30 cột & Dark Theme) |
| `frontend/workers.py` | 140 | Luồng chạy ngầm `QThread` (`BacktestThread`, `MaintenanceRoutineThread` quét S&P 500) |
| `frontend/gui.py` | 1217 | Nhạc trưởng giao diện PyQt6 (`TradingApp`), xử lý sự kiện nút bấm, `update_display()` & `trading_loop()` |
| `backtest/core_backtest_engine.py` | 307 | Lõi mô phỏng Backtest kiểm chứng thuật toán DIP & MOMENTUM |
| `backtest/run_present_stocks_backtest.py` | 357 | Chạy Backtest toàn bộ danh mục trong SQLite DB và xuất báo cáo so sánh S&P 500 |

## 2. Chi Tiết Tọa Độ Class & Hàm Theo Từng File

### 📄 `backend/config.py` (107 dòng)

| Thành phần (Class / Hàm) | Dòng bắt đầu | Dòng kết thúc | Số dòng |
| :--- | ---: | ---: | ---: |
| def `_load_env_config()` | 51 | 63 | 13 |
| def `clean_company_name()` | 89 | 97 | 9 |
| def `format_currency_short()` | 99 | 107 | 9 |

### 📄 `backend/database.py` (690 dòng)

| Thành phần (Class / Hàm) | Dòng bắt đầu | Dòng kết thúc | Số dòng |
| :--- | ---: | ---: | ---: |
| class `DatabaseManager` | 4 | 640 | 637 |
|   └─ `DatabaseManager.__init__()` | 7 | 14 | 8 |
|   └─ `DatabaseManager.connection()` | 17 | 28 | 12 |
|   └─ `DatabaseManager.get_cursor()` | 31 | 59 | 29 |
|   └─ `DatabaseManager._recover_corrupt_database()` | 61 | 129 | 69 |
|   └─ `DatabaseManager.close()` | 131 | 138 | 8 |
|   └─ `DatabaseManager.init_database()` | 140 | 265 | 126 |
|   └─ `DatabaseManager.get_setting()` | 267 | 273 | 7 |
|   └─ `DatabaseManager.set_setting()` | 275 | 277 | 3 |
|   └─ `DatabaseManager.get_company_info()` | 279 | 346 | 68 |
|   └─ `DatabaseManager.get_latest_price()` | 348 | 359 | 12 |
|   └─ `DatabaseManager.update_latest_price()` | 361 | 367 | 7 |
|   └─ `DatabaseManager.get_cached_bank_note()` | 369 | 379 | 11 |
|   └─ `DatabaseManager.get_last_sell_price()` | 381 | 391 | 11 |
|   └─ `DatabaseManager.get_cached_indicators()` | 393 | 422 | 30 |
|   └─ `DatabaseManager.update_cached_indicators()` | 424 | 455 | 32 |
|   └─ `DatabaseManager.save_target_to_db()` | 457 | 482 | 26 |
|   └─ `DatabaseManager.add_stock()` | 484 | 491 | 8 |
|   └─ `DatabaseManager.get_all_stocks()` | 493 | 497 | 5 |
|   └─ `DatabaseManager.update_bought_strategy()` | 499 | 505 | 7 |
|   └─ `DatabaseManager.update_highest_pnl()` | 507 | 513 | 7 |
|   └─ `DatabaseManager.update_last_rejection_time()` | 515 | 521 | 7 |
|   └─ `DatabaseManager.remove_stock()` | 523 | 526 | 4 |
|   └─ `DatabaseManager.add_ignored_stock()` | 528 | 530 | 3 |
|   └─ `DatabaseManager.remove_ignored_stock()` | 532 | 534 | 3 |
|   └─ `DatabaseManager.get_ignored_stocks()` | 536 | 539 | 4 |
|   └─ `DatabaseManager.update_stock()` | 541 | 548 | 8 |
|   └─ `DatabaseManager.log_trade()` | 550 | 556 | 7 |
|   └─ `DatabaseManager.log_trades_batch()` | 558 | 567 | 10 |
|   └─ `DatabaseManager.get_trade_history()` | 569 | 582 | 14 |
|   └─ `DatabaseManager.get_last_trade_times()` | 584 | 621 | 38 |
|   └─ `DatabaseManager.get_setting()` | 623 | 632 | 10 |
|   └─ `DatabaseManager.set_setting()` | 634 | 640 | 7 |
| class `CSVManager` | 643 | 688 | 46 |
|   └─ `CSVManager.__init__()` | 644 | 649 | 6 |
|   └─ `CSVManager.init_csv()` | 651 | 658 | 8 |
|   └─ `CSVManager.save_order()` | 660 | 672 | 13 |
|   └─ `CSVManager.update_order_status()` | 674 | 688 | 15 |

### 📄 `backend/ib_api.py` (256 dòng)

| Thành phần (Class / Hàm) | Dòng bắt đầu | Dòng kết thúc | Số dòng |
| :--- | ---: | ---: | ---: |
| class `IBApi` | 4 | 255 | 252 |
|   └─ `IBApi.__init__()` | 5 | 33 | 29 |
|   └─ `IBApi.managedAccounts()` | 35 | 46 | 12 |
|   └─ `IBApi.currentTime()` | 48 | 52 | 5 |
|   └─ `IBApi.nextValidId()` | 54 | 60 | 7 |
|   └─ `IBApi.get_next_order_id()` | 62 | 67 | 6 |
|   └─ `IBApi.connectionClosed()` | 69 | 74 | 6 |
|   └─ `IBApi.error()` | 76 | 159 | 84 |
|   └─ `IBApi.accountSummary()` | 161 | 181 | 21 |
|   └─ `IBApi.pnl()` | 183 | 192 | 10 |
|   └─ `IBApi.accountSummaryEnd()` | 194 | 199 | 6 |
|   └─ `IBApi.position()` | 201 | 213 | 13 |
|   └─ `IBApi.updatePortfolio()` | 215 | 234 | 20 |
|   └─ `IBApi.orderStatus()` | 236 | 255 | 20 |

### 📄 `backend/analyst_scraper.py` (327 dòng)

| Thành phần (Class / Hàm) | Dòng bắt đầu | Dòng kết thúc | Số dòng |
| :--- | ---: | ---: | ---: |
| class `AnalystDataMixin` | 4 | 327 | 324 |
|   └─ `AnalystDataMixin.get_bank_note()` | 7 | 46 | 40 |
|   └─ `AnalystDataMixin.fetch_fresh_bank_note()` | 48 | 120 | 73 |
|   └─ `AnalystDataMixin.fetch_next_event_date()` | 122 | 165 | 44 |
|   └─ `AnalystDataMixin.update_analyst_data()` | 167 | 190 | 24 |
|   └─ `AnalystDataMixin.get_barclays_target()` | 192 | 219 | 28 |
|   └─ `AnalystDataMixin.get_ubs_target()` | 221 | 302 | 82 |
|   └─ `AnalystDataMixin.get_morgan_stanley_target()` | 304 | 327 | 24 |

### 📄 `backend/notifier.py` (270 dòng)

| Thành phần (Class / Hàm) | Dòng bắt đầu | Dòng kết thúc | Số dòng |
| :--- | ---: | ---: | ---: |
| class `EmailNotifier` | 4 | 270 | 267 |
|   └─ `EmailNotifier.send_ibkr_disconnect_email()` | 8 | 58 | 51 |
|   └─ `EmailNotifier.send_ibkr_recovery_email()` | 61 | 102 | 42 |
|   └─ `EmailNotifier.send_trade_email()` | 105 | 270 | 166 |

### 📄 `backend/ibkr_watchdog.py` (388 dòng)

| Thành phần (Class / Hàm) | Dòng bắt đầu | Dòng kết thúc | Số dòng |
| :--- | ---: | ---: | ---: |
| class `IBKRWatchdogMixin` | 5 | 388 | 384 |
|   └─ `IBKRWatchdogMixin._auto_connect()` | 8 | 15 | 8 |
|   └─ `IBKRWatchdogMixin._check_auto_reconnect()` | 17 | 91 | 75 |
|   └─ `IBKRWatchdogMixin._trigger_auto_reconnect()` | 93 | 159 | 67 |
|   └─ `IBKRWatchdogMixin._on_auto_reconnect_success()` | 161 | 180 | 20 |
|   └─ `IBKRWatchdogMixin._on_auto_reconnect_fail()` | 182 | 190 | 9 |
|   └─ `IBKRWatchdogMixin._check_ibkr_watchdog()` | 192 | 291 | 100 |
|   └─ `IBKRWatchdogMixin._on_ibkr_reconnected()` | 293 | 298 | 6 |
|   └─ `IBKRWatchdogMixin.toggle_connection()` | 300 | 367 | 68 |
|   └─ `IBKRWatchdogMixin._on_connect_success()` | 369 | 382 | 14 |
|   └─ `IBKRWatchdogMixin._on_connect_fail()` | 384 | 388 | 5 |

### 📄 `backend/trading_bot.py` (724 dòng)

| Thành phần (Class / Hàm) | Dòng bắt đầu | Dòng kết thúc | Số dòng |
| :--- | ---: | ---: | ---: |
| class `TradingBot` | 22 | 724 | 703 |
|   └─ `TradingBot.__init__()` | 46 | 125 | 80 |
|   └─ `TradingBot.market_value()` | 129 | 130 | 2 |
|   └─ `TradingBot.market_value()` | 133 | 134 | 2 |
|   └─ `TradingBot.rsi_value()` | 137 | 138 | 2 |
|   └─ `TradingBot.rsi_value()` | 141 | 142 | 2 |
|   └─ `TradingBot.adx_value()` | 145 | 146 | 2 |
|   └─ `TradingBot.adx_value()` | 149 | 150 | 2 |
|   └─ `TradingBot.ma_signal()` | 153 | 154 | 2 |
|   └─ `TradingBot.ma_signal()` | 157 | 158 | 2 |
|   └─ `TradingBot.prev_ma_signal()` | 161 | 162 | 2 |
|   └─ `TradingBot.prev_ma_signal()` | 165 | 166 | 2 |
|   └─ `TradingBot.macd_signal()` | 169 | 170 | 2 |
|   └─ `TradingBot.macd_signal()` | 173 | 174 | 2 |
|   └─ `TradingBot.prev_macd_signal()` | 177 | 178 | 2 |
|   └─ `TradingBot.prev_macd_signal()` | 181 | 182 | 2 |
|   └─ `TradingBot.previous_close()` | 185 | 186 | 2 |
|   └─ `TradingBot.previous_close()` | 189 | 190 | 2 |
|   └─ `TradingBot.day_before_yesterday_close()` | 193 | 194 | 2 |
|   └─ `TradingBot.day_before_yesterday_close()` | 197 | 198 | 2 |
|   └─ `TradingBot.close_3d_ago()` | 201 | 202 | 2 |
|   └─ `TradingBot.close_3d_ago()` | 205 | 206 | 2 |
|   └─ `TradingBot.fourteen_day_high()` | 209 | 210 | 2 |
|   └─ `TradingBot.fourteen_day_high()` | 213 | 214 | 2 |
|   └─ `TradingBot.fourteen_day_low()` | 217 | 218 | 2 |
|   └─ `TradingBot.fourteen_day_low()` | 221 | 222 | 2 |
|   └─ `TradingBot.today_volume()` | 225 | 226 | 2 |
|   └─ `TradingBot.today_volume()` | 229 | 230 | 2 |
|   └─ `TradingBot.avg_volume_14d()` | 233 | 234 | 2 |
|   └─ `TradingBot.avg_volume_14d()` | 237 | 238 | 2 |
|   └─ `TradingBot.next_earnings_date()` | 241 | 242 | 2 |
|   └─ `TradingBot.next_earnings_date()` | 245 | 246 | 2 |
|   └─ `TradingBot.target_price()` | 249 | 250 | 2 |
|   └─ `TradingBot.target_price()` | 253 | 254 | 2 |
|   └─ `TradingBot.num_analysts()` | 257 | 258 | 2 |
|   └─ `TradingBot.num_analysts()` | 261 | 262 | 2 |
|   └─ `TradingBot.company_name()` | 265 | 266 | 2 |
|   └─ `TradingBot.asset_type()` | 269 | 270 | 2 |
|   └─ `TradingBot.sector()` | 273 | 274 | 2 |
|   └─ `TradingBot.currency()` | 277 | 278 | 2 |
|   └─ `TradingBot.currency_symbol()` | 281 | 282 | 2 |
|   └─ `TradingBot.exchange_tz_name()` | 285 | 286 | 2 |
|   └─ `TradingBot.bb_pct_b()` | 289 | 290 | 2 |
|   └─ `TradingBot.min_cash()` | 293 | 296 | 4 |
|   └─ `TradingBot.create_yf_ticker()` | 299 | 300 | 2 |
|   └─ `TradingBot.is_market_open()` | 302 | 303 | 2 |
|   └─ `TradingBot.is_market_cooling_down()` | 305 | 306 | 2 |
|   └─ `TradingBot.get_projected_volume()` | 308 | 309 | 2 |
|   └─ `TradingBot.calculate_rsi()` | 312 | 313 | 2 |
|   └─ `TradingBot.calculate_adx()` | 315 | 318 | 4 |
|   └─ `TradingBot.calculate_technical_indicators()` | 320 | 321 | 2 |
|   └─ `TradingBot.get_ma200()` | 323 | 324 | 2 |
|   └─ `TradingBot.get_ma50()` | 326 | 327 | 2 |
|   └─ `TradingBot.get_atr_14()` | 329 | 330 | 2 |
|   └─ `TradingBot.get_market_value()` | 332 | 333 | 2 |
|   └─ `TradingBot.check_macro_guard()` | 336 | 337 | 2 |
|   └─ `TradingBot.calculate_analyst_modifier()` | 339 | 341 | 3 |
|   └─ `TradingBot.calculate_score()` | 343 | 354 | 12 |
|   └─ `TradingBot._calculate_dynamic_max_amount()` | 356 | 365 | 10 |
|   └─ `TradingBot.update_position()` | 367 | 408 | 42 |
|   └─ `TradingBot.update_parameters()` | 410 | 414 | 5 |
|   └─ `TradingBot.has_pending_order()` | 416 | 435 | 20 |
|   └─ `TradingBot.get_native_currency_and_exchange()` | 437 | 438 | 2 |
|   └─ `TradingBot._on_order_completed()` | 440 | 496 | 57 |
|   └─ `TradingBot.check_trading_conditions()` | 498 | 590 | 93 |
|   └─ `TradingBot.place_buy_order()` | 592 | 644 | 53 |
|   └─ `TradingBot.place_sell_order()` | 646 | 672 | 27 |
|   └─ `TradingBot.get_buy_block_reason()` | 674 | 696 | 23 |
|   └─ `TradingBot.get_status()` | 698 | 721 | 24 |
|   └─ `TradingBot.stop()` | 723 | 724 | 2 |

### 📄 `backend/services/models.py` (74 dòng)

| Thành phần (Class / Hàm) | Dòng bắt đầu | Dòng kết thúc | Số dòng |
| :--- | ---: | ---: | ---: |
| class `MarketSnapshot` | 10 | 41 | 32 |
| class `AlphaSignal` | 44 | 51 | 8 |
| class `RiskDecision` | 54 | 61 | 8 |
| class `OrderIntent` | 64 | 73 | 10 |

### 📄 `backend/services/data_feed.py` (479 dòng)

| Thành phần (Class / Hàm) | Dòng bắt đầu | Dòng kết thúc | Số dòng |
| :--- | ---: | ---: | ---: |
| class `DataFeedService` | 16 | 478 | 463 |
|   └─ `DataFeedService.__init__()` | 21 | 80 | 60 |
|   └─ `DataFeedService._load_initial_metadata()` | 82 | 119 | 38 |
|   └─ `DataFeedService.is_market_open()` | 121 | 141 | 21 |
|   └─ `DataFeedService.is_market_cooling_down()` | 143 | 169 | 27 |
|   └─ `DataFeedService.get_projected_volume()` | 171 | 202 | 32 |
|   └─ `DataFeedService.calculate_rsi()` | 205 | 213 | 9 |
|   └─ `DataFeedService.calculate_adx()` | 215 | 234 | 20 |
|   └─ `DataFeedService.calculate_technical_indicators()` | 236 | 393 | 158 |
|   └─ `DataFeedService.get_ma200()` | 395 | 399 | 5 |
|   └─ `DataFeedService.get_ma50()` | 401 | 405 | 5 |
|   └─ `DataFeedService.get_atr_14()` | 407 | 411 | 5 |
|   └─ `DataFeedService.get_market_value()` | 413 | 443 | 31 |
|   └─ `DataFeedService.get_snapshot()` | 445 | 478 | 34 |

### 📄 `backend/services/alpha_engine.py` (245 dòng)

| Thành phần (Class / Hàm) | Dòng bắt đầu | Dòng kết thúc | Số dòng |
| :--- | ---: | ---: | ---: |
| class `AlphaEngine` | 10 | 244 | 235 |
|   └─ `AlphaEngine.calculate_analyst_modifier()` | 21 | 67 | 47 |
|   └─ `AlphaEngine.calculate_score()` | 70 | 244 | 175 |

### 📄 `backend/services/portfolio_sizing.py` (287 dòng)

| Thành phần (Class / Hàm) | Dòng bắt đầu | Dòng kết thúc | Số dòng |
| :--- | ---: | ---: | ---: |
| class `ExchangeRateManager` | 13 | 76 | 64 |
|   └─ `ExchangeRateManager.__init__()` | 15 | 24 | 10 |
|   └─ `ExchangeRateManager.eur_usd_rate()` | 27 | 28 | 2 |
|   └─ `ExchangeRateManager.eur_usd_rate()` | 31 | 32 | 2 |
|   └─ `ExchangeRateManager.get_eur_usd_rate()` | 34 | 35 | 2 |
|   └─ `ExchangeRateManager.get_rate()` | 37 | 61 | 25 |
|   └─ `ExchangeRateManager.eur_to_native()` | 63 | 66 | 4 |
|   └─ `ExchangeRateManager.get_currency_symbol()` | 68 | 76 | 9 |
| def `get_usd_to_eur_rate()` | 80 | 85 | 6 |
| def `calc_portfolio_composition()` | 88 | 115 | 28 |
| def `calc_total_positions_pnl_eur()` | 118 | 146 | 29 |
| def `calc_total_daily_pnl_eur()` | 149 | 185 | 37 |
| class `PortfolioSizingService` | 189 | 286 | 98 |
|   └─ `PortfolioSizingService.__init__()` | 196 | 198 | 3 |
|   └─ `PortfolioSizingService.calculate_dynamic_max_amount()` | 200 | 251 | 52 |
|   └─ `PortfolioSizingService.calculate_order_sizing()` | 253 | 286 | 34 |

### 📄 `backend/services/risk_manager.py` (359 dòng)

| Thành phần (Class / Hàm) | Dòng bắt đầu | Dòng kết thúc | Số dòng |
| :--- | ---: | ---: | ---: |
| class `PDTProtector` | 17 | 59 | 43 |
|   └─ `PDTProtector.__init__()` | 19 | 22 | 4 |
|   └─ `PDTProtector._load_history()` | 24 | 44 | 21 |
|   └─ `PDTProtector._cleanup()` | 46 | 49 | 4 |
|   └─ `PDTProtector.count_day_trades_5d()` | 51 | 53 | 3 |
|   └─ `PDTProtector.register_day_trade_if_needed()` | 55 | 56 | 2 |
|   └─ `PDTProtector.can_trade()` | 58 | 59 | 2 |
| class `RiskManagementEngine` | 63 | 358 | 296 |
|   └─ `RiskManagementEngine.__init__()` | 79 | 82 | 4 |
|   └─ `RiskManagementEngine.check_macro_guard()` | 85 | 105 | 21 |
|   └─ `RiskManagementEngine.throttled_sell_log()` | 107 | 112 | 6 |
|   └─ `RiskManagementEngine.evaluate_exit()` | 114 | 218 | 105 |
|   └─ `RiskManagementEngine.validate_buy()` | 220 | 358 | 139 |

### 📄 `backend/services/execution.py` (183 dòng)

| Thành phần (Class / Hàm) | Dòng bắt đầu | Dòng kết thúc | Số dòng |
| :--- | ---: | ---: | ---: |
| class `ExecutionService` | 14 | 182 | 169 |
|   └─ `ExecutionService.__init__()` | 19 | 24 | 6 |
|   └─ `ExecutionService.get_native_currency_and_exchange()` | 27 | 45 | 19 |
|   └─ `ExecutionService.has_pending_order()` | 47 | 53 | 7 |
|   └─ `ExecutionService.place_buy_order()` | 55 | 119 | 65 |
|   └─ `ExecutionService.place_sell_order()` | 121 | 182 | 62 |

### 📄 `frontend/ui_components.py` (458 dòng)

| Thành phần (Class / Hàm) | Dòng bắt đầu | Dòng kết thúc | Số dòng |
| :--- | ---: | ---: | ---: |
| class `NumericTableWidgetItem` | 30 | 38 | 9 |
|   └─ `NumericTableWidgetItem.__init__()` | 31 | 33 | 3 |
|   └─ `NumericTableWidgetItem.__lt__()` | 35 | 38 | 4 |
| class `UISetupMixin` | 41 | 458 | 418 |
|   └─ `UISetupMixin.init_ui()` | 44 | 458 | 415 |

### 📄 `frontend/workers.py` (140 dòng)

| Thành phần (Class / Hàm) | Dòng bắt đầu | Dòng kết thúc | Số dòng |
| :--- | ---: | ---: | ---: |
| class `BacktestThread` | 4 | 33 | 30 |
|   └─ `BacktestThread.__init__()` | 9 | 11 | 3 |
|   └─ `BacktestThread.run()` | 13 | 33 | 21 |
| class `MaintenanceRoutineThread` | 36 | 140 | 105 |
|   └─ `MaintenanceRoutineThread.__init__()` | 41 | 44 | 4 |
|   └─ `MaintenanceRoutineThread.run()` | 46 | 140 | 95 |

### 📄 `frontend/gui.py` (1217 dòng)

| Thành phần (Class / Hàm) | Dòng bắt đầu | Dòng kết thúc | Số dòng |
| :--- | ---: | ---: | ---: |
| class `TradingApp` | 20 | 1216 | 1197 |
|   └─ `TradingApp.is_background_busy()` | 25 | 29 | 5 |
|   └─ `TradingApp.__init__()` | 31 | 94 | 64 |
|   └─ `TradingApp._format_last_run()` | 96 | 105 | 10 |
|   └─ `TradingApp._send_ibkr_disconnect_email()` | 107 | 108 | 2 |
|   └─ `TradingApp._send_ibkr_recovery_email()` | 110 | 111 | 2 |
|   └─ `TradingApp._get_usd_to_eur_rate()` | 115 | 116 | 2 |
|   └─ `TradingApp._calc_portfolio_composition()` | 118 | 119 | 2 |
|   └─ `TradingApp._calc_total_positions_pnl_eur()` | 121 | 122 | 2 |
|   └─ `TradingApp._calc_total_daily_pnl_eur()` | 124 | 125 | 2 |
|   └─ `TradingApp._apply_default_sort()` | 127 | 142 | 16 |
|   └─ `TradingApp.refresh_cash()` | 144 | 156 | 13 |
|   └─ `TradingApp.send_trade_email()` | 158 | 159 | 2 |
|   └─ `TradingApp.save_min_cash()` | 161 | 174 | 14 |
|   └─ `TradingApp.save_global_risk()` | 176 | 183 | 8 |
|   └─ `TradingApp.highlight_selected_row()` | 185 | 211 | 27 |
|   └─ `TradingApp.keyPressEvent()` | 213 | 219 | 7 |
|   └─ `TradingApp.on_header_clicked()` | 221 | 223 | 3 |
|   └─ `TradingApp.show_header_context_menu()` | 225 | 239 | 15 |
|   └─ `TradingApp.load_stocks()` | 241 | 267 | 27 |
|   └─ `TradingApp.update_display()` | 269 | 751 | 483 |
|   └─ `TradingApp.toggle_trading()` | 753 | 771 | 19 |
|   └─ `TradingApp.manual_refresh_data()` | 773 | 798 | 26 |
|   └─ `TradingApp.reset_update_btn()` | 800 | 802 | 3 |
|   └─ `TradingApp.trading_loop()` | 804 | 868 | 65 |
|   └─ `TradingApp.add_stock()` | 870 | 899 | 30 |
|   └─ `TradingApp.remove_stock()` | 903 | 944 | 42 |
|   └─ `TradingApp.get_selected_bot()` | 946 | 957 | 12 |
|   └─ `TradingApp.handle_manual_buy()` | 959 | 966 | 8 |
|   └─ `TradingApp.handle_manual_sell()` | 968 | 978 | 11 |
|   └─ `TradingApp.handle_manual_hold()` | 980 | 994 | 15 |
|   └─ `TradingApp.handle_maintenance_routine()` | 996 | 1014 | 19 |
|   └─ `TradingApp.on_maint_progress()` | 1016 | 1019 | 4 |
|   └─ `TradingApp.on_maint_error()` | 1021 | 1030 | 10 |
|   └─ `TradingApp.on_maint_finished()` | 1032 | 1071 | 40 |
|   └─ `TradingApp.handle_sync_from_server()` | 1073 | 1113 | 41 |
|   └─ `TradingApp._on_sync_finished()` | 1115 | 1129 | 15 |
|   └─ `TradingApp.open_csv()` | 1131 | 1143 | 13 |
|   └─ `TradingApp.handle_backtest()` | 1145 | 1164 | 20 |
|   └─ `TradingApp.on_backtest_progress()` | 1166 | 1169 | 4 |
|   └─ `TradingApp.on_backtest_error()` | 1171 | 1179 | 9 |
|   └─ `TradingApp.on_backtest_finished()` | 1181 | 1201 | 21 |
|   └─ `TradingApp.closeEvent()` | 1203 | 1216 | 14 |

### 📄 `backtest/core_backtest_engine.py` (307 dòng)

| Thành phần (Class / Hàm) | Dòng bắt đầu | Dòng kết thúc | Số dòng |
| :--- | ---: | ---: | ---: |
| def `compute_indicators()` | 35 | 83 | 49 |
| def `calculate_score()` | 85 | 122 | 38 |
| def `run_backtest_with_params()` | 124 | 259 | 136 |
| def `filter_sector_concentration()` | 261 | 278 | 18 |

### 📄 `backtest/run_present_stocks_backtest.py` (357 dòng)

| Thành phần (Class / Hàm) | Dòng bắt đầu | Dòng kết thúc | Số dòng |
| :--- | ---: | ---: | ---: |
| def `get_stocks_from_db()` | 78 | 91 | 14 |
| def `run_backtest_for_db_stocks()` | 93 | 351 | 259 |
