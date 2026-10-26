# 🗺️ CODEBASE_MAP.md — Bản Đồ Tọa Độ Dòng Code Tự Động (`pyTrade3`)

> **Cập nhật tự động bởi `./verify_py.sh` lúc:** `2026-10-26 12:52:02`
> Khi cần sửa hàm hoặc class nào, chỉ đọc đúng khoảng dòng (`StartLine` – `EndLine`) dưới đây để tiết kiệm 90% token.

## 1. Tổng Quan Quy Mô File

| File | Số dòng | Vai trò chính |
| :--- | ---: | :--- |
| `config.py` | 95 | Cấu hình biến môi trường (.env), SemVer (`APP_VERSION`), ThreadPoolExecutor & Logger |
| `database.py` | 632 | Quản lý SQLite (`PRAGMA user_version`), lịch sử giao dịch, cache chỉ báo & `CSVManager` |
| `exchange.py` | 67 | Quản lý tỷ giá ngoại tệ tự động (`EUR/USD`, `GBP`, `CAD`, `HKD`) |
| `ib_api.py` | 256 | Giao tiếp socket Interactive Brokers TWS / IB Gateway (`EWrapper`, `EClient`) |
| `pdt_protector.py` | 46 | Bảo vệ tài khoản khỏi quy tắc Pattern Day Trader (tối đa 3 giao dịch T+0 / 5 ngày) |
| `trading_bot.py` | 1955 | Lõi thuật toán `TradingBot`: tính chỉ báo, `calculate_score()`, quản trị rủi ro ATR & đặt lệnh |
| `gui.py` | 2454 | Giao diện PyQt6 (`TradingApp`), vòng lặp `trading_loop()`, Watchdog kết nối & Email thông báo |
| `main.py` | 15 | Điểm khởi chạy ứng dụng Desktop (`QApplication`) |
| `backtest/core_backtest_engine.py` | 307 | Lõi mô phỏng Backtest kiểm chứng thuật toán DIP & MOMENTUM |
| `backtest/download_cac40.py` | 104 | Script Backtest / Tiện ích |
| `backtest/download_sp500_bear.py` | 105 | Script Backtest / Tiện ích |
| `backtest/download_sp500_bull.py` | 109 | Script Backtest / Tiện ích |
| `backtest/run_cac40_backtest.py` | 52 | Script Backtest / Tiện ích |
| `backtest/run_dailychange_backtest.py` | 238 | Script Backtest / Tiện ích |
| `backtest/run_present_stocks_backtest.py` | 355 | Chạy Backtest toàn bộ danh mục trong SQLite DB và xuất báo cáo so sánh S&P 500 |
| `backtest/run_sp500_bear_backtest.py` | 89 | Script Backtest / Tiện ích |
| `backtest/run_sp500_bull_backtest.py` | 92 | Script Backtest / Tiện ích |

## 2. Chi Tiết Tọa Độ Class & Hàm Theo Từng File

### 📄 `config.py` (95 dòng)

| Thành phần (Class / Hàm) | Dòng bắt đầu | Dòng kết thúc | Số dòng |
| :--- | ---: | ---: | ---: |
| def `_load_env_config()` | 39 | 51 | 13 |
| def `clean_company_name()` | 77 | 85 | 9 |
| def `format_currency_short()` | 87 | 95 | 9 |

### 📄 `database.py` (632 dòng)

| Thành phần (Class / Hàm) | Dòng bắt đầu | Dòng kết thúc | Số dòng |
| :--- | ---: | ---: | ---: |
| class `DatabaseManager` | 4 | 585 | 582 |
|   └─ `DatabaseManager.__init__()` | 7 | 11 | 5 |
|   └─ `DatabaseManager.connection()` | 14 | 25 | 12 |
|   └─ `DatabaseManager.get_cursor()` | 28 | 56 | 29 |
|   └─ `DatabaseManager._recover_corrupt_database()` | 58 | 74 | 17 |
|   └─ `DatabaseManager.close()` | 76 | 83 | 8 |
|   └─ `DatabaseManager.init_database()` | 85 | 210 | 126 |
|   └─ `DatabaseManager.get_setting()` | 212 | 218 | 7 |
|   └─ `DatabaseManager.set_setting()` | 220 | 222 | 3 |
|   └─ `DatabaseManager.get_company_info()` | 224 | 291 | 68 |
|   └─ `DatabaseManager.get_latest_price()` | 293 | 304 | 12 |
|   └─ `DatabaseManager.update_latest_price()` | 306 | 312 | 7 |
|   └─ `DatabaseManager.get_cached_bank_note()` | 314 | 324 | 11 |
|   └─ `DatabaseManager.get_last_sell_price()` | 326 | 336 | 11 |
|   └─ `DatabaseManager.get_cached_indicators()` | 338 | 367 | 30 |
|   └─ `DatabaseManager.update_cached_indicators()` | 369 | 400 | 32 |
|   └─ `DatabaseManager.save_target_to_db()` | 402 | 427 | 26 |
|   └─ `DatabaseManager.add_stock()` | 429 | 436 | 8 |
|   └─ `DatabaseManager.get_all_stocks()` | 438 | 442 | 5 |
|   └─ `DatabaseManager.update_bought_strategy()` | 444 | 450 | 7 |
|   └─ `DatabaseManager.update_highest_pnl()` | 452 | 458 | 7 |
|   └─ `DatabaseManager.update_last_rejection_time()` | 460 | 466 | 7 |
|   └─ `DatabaseManager.remove_stock()` | 468 | 471 | 4 |
|   └─ `DatabaseManager.add_ignored_stock()` | 473 | 475 | 3 |
|   └─ `DatabaseManager.remove_ignored_stock()` | 477 | 479 | 3 |
|   └─ `DatabaseManager.get_ignored_stocks()` | 481 | 484 | 4 |
|   └─ `DatabaseManager.update_stock()` | 486 | 493 | 8 |
|   └─ `DatabaseManager.log_trade()` | 495 | 501 | 7 |
|   └─ `DatabaseManager.log_trades_batch()` | 503 | 512 | 10 |
|   └─ `DatabaseManager.get_trade_history()` | 514 | 527 | 14 |
|   └─ `DatabaseManager.get_last_trade_times()` | 529 | 566 | 38 |
|   └─ `DatabaseManager.get_setting()` | 568 | 577 | 10 |
|   └─ `DatabaseManager.set_setting()` | 579 | 585 | 7 |
| class `CSVManager` | 588 | 630 | 43 |
|   └─ `CSVManager.__init__()` | 589 | 591 | 3 |
|   └─ `CSVManager.init_csv()` | 593 | 600 | 8 |
|   └─ `CSVManager.save_order()` | 602 | 614 | 13 |
|   └─ `CSVManager.update_order_status()` | 616 | 630 | 15 |

### 📄 `exchange.py` (67 dòng)

| Thành phần (Class / Hàm) | Dòng bắt đầu | Dòng kết thúc | Số dòng |
| :--- | ---: | ---: | ---: |
| class `ExchangeRateManager` | 3 | 66 | 64 |
|   └─ `ExchangeRateManager.__init__()` | 4 | 13 | 10 |
|   └─ `ExchangeRateManager.eur_usd_rate()` | 16 | 17 | 2 |
|   └─ `ExchangeRateManager.eur_usd_rate()` | 20 | 21 | 2 |
|   └─ `ExchangeRateManager.get_eur_usd_rate()` | 23 | 24 | 2 |
|   └─ `ExchangeRateManager.get_rate()` | 26 | 50 | 25 |
|   └─ `ExchangeRateManager.eur_to_native()` | 52 | 55 | 4 |
|   └─ `ExchangeRateManager.get_currency_symbol()` | 57 | 66 | 10 |

### 📄 `ib_api.py` (256 dòng)

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

### 📄 `pdt_protector.py` (46 dòng)

| Thành phần (Class / Hàm) | Dòng bắt đầu | Dòng kết thúc | Số dòng |
| :--- | ---: | ---: | ---: |
| class `PDTProtector` | 2 | 46 | 45 |
|   └─ `PDTProtector.__init__()` | 3 | 6 | 4 |
|   └─ `PDTProtector._load_history()` | 8 | 28 | 21 |
|   └─ `PDTProtector._cleanup()` | 30 | 33 | 4 |
|   └─ `PDTProtector.count_day_trades_5d()` | 35 | 37 | 3 |
|   └─ `PDTProtector.register_day_trade_if_needed()` | 39 | 40 | 2 |
|   └─ `PDTProtector.can_trade()` | 42 | 46 | 5 |

### 📄 `trading_bot.py` (1955 dòng)

| Thành phần (Class / Hàm) | Dòng bắt đầu | Dòng kết thúc | Số dòng |
| :--- | ---: | ---: | ---: |
| class `TradingBot` | 3 | 1954 | 1952 |
|   └─ `TradingBot.__init__()` | 25 | 115 | 91 |
|   └─ `TradingBot.min_cash()` | 118 | 122 | 5 |
|   └─ `TradingBot.create_yf_ticker()` | 124 | 160 | 37 |
|   └─ `TradingBot.is_market_open()` | 162 | 179 | 18 |
|   └─ `TradingBot.is_market_cooling_down()` | 181 | 206 | 26 |
|   └─ `TradingBot.get_projected_volume()` | 208 | 242 | 35 |
|   └─ `TradingBot.calculate_rsi()` | 245 | 253 | 9 |
|   └─ `TradingBot.calculate_adx()` | 255 | 274 | 20 |
|   └─ `TradingBot.get_bank_note()` | 276 | 315 | 40 |
|   └─ `TradingBot.fetch_fresh_bank_note()` | 317 | 389 | 73 |
|   └─ `TradingBot.calculate_technical_indicators()` | 391 | 567 | 177 |
|   └─ `TradingBot.get_ma200()` | 569 | 577 | 9 |
|   └─ `TradingBot.get_ma50()` | 579 | 587 | 9 |
|   └─ `TradingBot.get_atr_14()` | 589 | 597 | 9 |
|   └─ `TradingBot.fetch_next_event_date()` | 600 | 643 | 44 |
|   └─ `TradingBot.get_market_value()` | 645 | 673 | 29 |
|   └─ `TradingBot._calculate_dynamic_max_amount()` | 675 | 721 | 47 |
|   └─ `TradingBot.update_position()` | 723 | 766 | 44 |
|   └─ `TradingBot.update_parameters()` | 768 | 772 | 5 |
|   └─ `TradingBot.has_pending_order()` | 774 | 795 | 22 |
|   └─ `TradingBot._on_order_completed()` | 797 | 861 | 65 |
|   └─ `TradingBot.get_native_currency_and_exchange()` | 863 | 882 | 20 |
|   └─ `TradingBot.place_buy_order()` | 884 | 998 | 115 |
|   └─ `TradingBot.place_sell_order()` | 1000 | 1072 | 73 |
|   └─ `TradingBot.update_analyst_data()` | 1074 | 1097 | 24 |
|   └─ `TradingBot.get_barclays_target()` | 1099 | 1126 | 28 |
|   └─ `TradingBot.get_ubs_target()` | 1128 | 1209 | 82 |
|   └─ `TradingBot.get_morgan_stanley_target()` | 1211 | 1234 | 24 |
|   └─ `TradingBot.calculate_analyst_modifier()` | 1236 | 1289 | 54 |
|   └─ `TradingBot.calculate_score()` | 1291 | 1462 | 172 |
|   └─ `TradingBot.check_macro_guard()` | 1465 | 1485 | 21 |
|   └─ `TradingBot.check_trading_conditions()` | 1487 | 1794 | 308 |
|   └─ `TradingBot.get_buy_block_reason()` | 1797 | 1926 | 130 |
|   └─ `TradingBot.get_status()` | 1929 | 1951 | 23 |
|   └─ `TradingBot.stop()` | 1953 | 1954 | 2 |

### 📄 `gui.py` (2454 dòng)

| Thành phần (Class / Hàm) | Dòng bắt đầu | Dòng kết thúc | Số dòng |
| :--- | ---: | ---: | ---: |
| class `NumericTableWidgetItem` | 9 | 17 | 9 |
|   └─ `NumericTableWidgetItem.__init__()` | 10 | 12 | 3 |
|   └─ `NumericTableWidgetItem.__lt__()` | 14 | 17 | 4 |
| class `BacktestThread` | 19 | 48 | 30 |
|   └─ `BacktestThread.__init__()` | 24 | 26 | 3 |
|   └─ `BacktestThread.run()` | 28 | 48 | 21 |
| class `MaintenanceRoutineThread` | 50 | 154 | 105 |
|   └─ `MaintenanceRoutineThread.__init__()` | 55 | 58 | 4 |
|   └─ `MaintenanceRoutineThread.run()` | 60 | 154 | 95 |
| class `TradingApp` | 157 | 2453 | 2297 |
|   └─ `TradingApp.is_background_busy()` | 162 | 166 | 5 |
|   └─ `TradingApp.__init__()` | 168 | 231 | 64 |
|   └─ `TradingApp._format_last_run()` | 233 | 242 | 10 |
|   └─ `TradingApp._auto_connect()` | 244 | 251 | 8 |
|   └─ `TradingApp._check_auto_reconnect()` | 253 | 327 | 75 |
|   └─ `TradingApp._trigger_auto_reconnect()` | 329 | 395 | 67 |
|   └─ `TradingApp._on_auto_reconnect_success()` | 397 | 416 | 20 |
|   └─ `TradingApp._on_auto_reconnect_fail()` | 418 | 426 | 9 |
|   └─ `TradingApp._check_ibkr_watchdog()` | 431 | 530 | 100 |
|   └─ `TradingApp._on_ibkr_reconnected()` | 532 | 537 | 6 |
|   └─ `TradingApp._send_ibkr_disconnect_email()` | 539 | 589 | 51 |
|   └─ `TradingApp._send_ibkr_recovery_email()` | 591 | 632 | 42 |
|   └─ `TradingApp._get_usd_to_eur_rate()` | 636 | 642 | 7 |
|   └─ `TradingApp._calc_portfolio_composition()` | 644 | 673 | 30 |
|   └─ `TradingApp._calc_total_positions_pnl_eur()` | 675 | 707 | 33 |
|   └─ `TradingApp._calc_total_daily_pnl_eur()` | 709 | 751 | 43 |
|   └─ `TradingApp._apply_default_sort()` | 753 | 768 | 16 |
|   └─ `TradingApp.on_header_clicked()` | 770 | 774 | 5 |
|   └─ `TradingApp.refresh_cash()` | 776 | 788 | 13 |
|   └─ `TradingApp.send_trade_email()` | 790 | 955 | 166 |
|   └─ `TradingApp.init_ui()` | 957 | 1364 | 408 |
|   └─ `TradingApp.save_min_cash()` | 1366 | 1379 | 14 |
|   └─ `TradingApp.save_global_risk()` | 1381 | 1388 | 8 |
|   └─ `TradingApp.highlight_selected_row()` | 1390 | 1416 | 27 |
|   └─ `TradingApp.keyPressEvent()` | 1418 | 1424 | 7 |
|   └─ `TradingApp.on_header_clicked()` | 1426 | 1428 | 3 |
|   └─ `TradingApp.show_header_context_menu()` | 1430 | 1444 | 15 |
|   └─ `TradingApp.load_stocks()` | 1446 | 1472 | 27 |
|   └─ `TradingApp.update_display()` | 1474 | 1956 | 483 |
|   └─ `TradingApp.toggle_connection()` | 1958 | 2025 | 68 |
|   └─ `TradingApp._on_connect_success()` | 2027 | 2040 | 14 |
|   └─ `TradingApp._on_connect_fail()` | 2042 | 2046 | 5 |
|   └─ `TradingApp.toggle_trading()` | 2048 | 2066 | 19 |
|   └─ `TradingApp.manual_refresh_data()` | 2068 | 2093 | 26 |
|   └─ `TradingApp.reset_update_btn()` | 2095 | 2097 | 3 |
|   └─ `TradingApp.trading_loop()` | 2099 | 2163 | 65 |
|   └─ `TradingApp.add_stock()` | 2165 | 2194 | 30 |
|   └─ `TradingApp.remove_stock()` | 2198 | 2239 | 42 |
|   └─ `TradingApp.get_selected_bot()` | 2241 | 2252 | 12 |
|   └─ `TradingApp.handle_manual_buy()` | 2254 | 2261 | 8 |
|   └─ `TradingApp.handle_manual_sell()` | 2263 | 2273 | 11 |
|   └─ `TradingApp.handle_manual_hold()` | 2275 | 2289 | 15 |
|   └─ `TradingApp.handle_maintenance_routine()` | 2291 | 2309 | 19 |
|   └─ `TradingApp.on_maint_progress()` | 2311 | 2314 | 4 |
|   └─ `TradingApp.on_maint_error()` | 2316 | 2325 | 10 |
|   └─ `TradingApp.on_maint_finished()` | 2327 | 2366 | 40 |
|   └─ `TradingApp.open_csv()` | 2368 | 2380 | 13 |
|   └─ `TradingApp.handle_backtest()` | 2382 | 2401 | 20 |
|   └─ `TradingApp.on_backtest_progress()` | 2403 | 2406 | 4 |
|   └─ `TradingApp.on_backtest_error()` | 2408 | 2416 | 9 |
|   └─ `TradingApp.on_backtest_finished()` | 2418 | 2438 | 21 |
|   └─ `TradingApp.closeEvent()` | 2440 | 2453 | 14 |

### 📄 `backtest/core_backtest_engine.py` (307 dòng)

| Thành phần (Class / Hàm) | Dòng bắt đầu | Dòng kết thúc | Số dòng |
| :--- | ---: | ---: | ---: |
| def `compute_indicators()` | 35 | 83 | 49 |
| def `calculate_score()` | 85 | 122 | 38 |
| def `run_backtest_with_params()` | 124 | 259 | 136 |
| def `filter_sector_concentration()` | 261 | 278 | 18 |

### 📄 `backtest/download_cac40.py` (104 dòng)

| Thành phần (Class / Hàm) | Dòng bắt đầu | Dòng kết thúc | Số dòng |
| :--- | ---: | ---: | ---: |
| def `compute_indicators()` | 14 | 64 | 51 |
| def `download_and_process()` | 66 | 79 | 14 |

### 📄 `backtest/download_sp500_bear.py` (105 dòng)

| Thành phần (Class / Hàm) | Dòng bắt đầu | Dòng kết thúc | Số dòng |
| :--- | ---: | ---: | ---: |
| def `compute_indicators()` | 14 | 64 | 51 |
| def `download_and_process()` | 66 | 79 | 14 |

### 📄 `backtest/download_sp500_bull.py` (109 dòng)

| Thành phần (Class / Hàm) | Dòng bắt đầu | Dòng kết thúc | Số dòng |
| :--- | ---: | ---: | ---: |
| def `compute_indicators()` | 19 | 69 | 51 |
| def `download_and_process()` | 71 | 83 | 13 |

### 📄 `backtest/run_dailychange_backtest.py` (238 dòng)

| Thành phần (Class / Hàm) | Dòng bắt đầu | Dòng kết thúc | Số dòng |
| :--- | ---: | ---: | ---: |
| def `get_db_stocks()` | 17 | 31 | 15 |
| def `get_combined_stock_universe()` | 33 | 35 | 3 |
| def `load_or_fetch_market_data()` | 37 | 66 | 30 |
| def `run_dailychange_sweep()` | 68 | 173 | 106 |
| def `generate_markdown_report()` | 175 | 235 | 61 |

### 📄 `backtest/run_present_stocks_backtest.py` (355 dòng)

| Thành phần (Class / Hàm) | Dòng bắt đầu | Dòng kết thúc | Số dòng |
| :--- | ---: | ---: | ---: |
| def `get_stocks_from_db()` | 78 | 91 | 14 |
| def `run_backtest_for_db_stocks()` | 93 | 349 | 257 |
