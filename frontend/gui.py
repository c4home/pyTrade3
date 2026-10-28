from backend.config import *

from database import DatabaseManager, CSVManager
from ib_api import IBApi
from trading_bot import TradingBot
from notifier import EmailNotifier
from workers import BacktestThread, MaintenanceRoutineThread
from services.portfolio_sizing import (
    ExchangeRateManager,
    get_usd_to_eur_rate,
    calc_portfolio_composition,
    calc_total_positions_pnl_eur,
    calc_total_daily_pnl_eur,
)
from services.risk_manager import PDTProtector
from ibkr_watchdog import IBKRWatchdogMixin
from ui_components import NumericTableWidgetItem, UISetupMixin

# ==================== MAIN GUI ====================
class TradingApp(QMainWindow, IBKRWatchdogMixin, UISetupMixin):
    instance = None  # <-- ADD THIS
    DEFAULT_SORT_COLUMN = 18
    DEFAULT_SORT_ORDER  = Qt.SortOrder.DescendingOrder

    def is_background_busy(self):
        for bot in self.bots.values():
            if getattr(bot, '_fetching_indicators', False) or getattr(bot, '_fetching_market_value', False) or getattr(bot, '_fetching_bank_note', False):
                return True
        return False

    def __init__(self):
        super().__init__()
        TradingApp.instance = self  # <-- SET INSTANCE
        self.setWindowTitle(f"pyTrade3 {APP_VERSION} • Build {APP_BUILD}")
        icon_path = os.path.join(PROJECT_ROOT, "assets", "app_icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        self.setGeometry(100, 100, 1900, 900)

        self.db_manager = DatabaseManager()
        self.csv_manager = CSVManager()
        self.exchange_manager = ExchangeRateManager()
        self.ibapi = IBApi()
        self.bots = {}
        self.connected = False
        self.auto_trading = False
        self.order_cooldown = {}  # Per-symbol cooldown

        self.sort_column = self.DEFAULT_SORT_COLUMN  # Value
        self.sort_order = self.DEFAULT_SORT_ORDER

        self.min_cash = 0.0
        self.init_ui()
        self.load_stocks()
        
        # Load min cash setting
        saved_min_cash = self.db_manager.get_setting("min_cash", "0")
        try:
            self.min_cash = float(saved_min_cash)
        except ValueError:
            self.min_cash = 0.0
        self.min_cash_edit.setText(saved_min_cash)
        self.min_cash_edit.editingFinished.connect(self.save_min_cash)
        
        self._default_sort_applied = False
        self._user_clicked_header = False

        self.timer_display = QTimer()
        self.timer_display.timeout.connect(self.update_display)
        self.timer_display.start(5000)
        
        self.pdt_protector = PDTProtector(self.db_manager)
        
        # trigger default sort after GUI is ready
        QTimer.singleShot(100, self._apply_default_sort)
        
        # 2. try auto‑connect (after 500 ms – table is already built)
        QTimer.singleShot(500, self._auto_connect)
        
        # 3. auto-refresh data
        QTimer.singleShot(1500, self.manual_refresh_data)

        # 4. Periodic Auto-Reconnect Monitor (checks every 15s for midnight TWS resets or connection drops)
        self.is_reconnecting = False
        self.reconnect_timer = QTimer()
        self.reconnect_timer.timeout.connect(self._check_auto_reconnect)
        self.reconnect_timer.start(15000)

        # 5. IBKR Connection Watchdog (gửi mail cảnh báo khi mất kết nối/logged out trừ T7, CN)
        self.app_start_time = time.time()
        self.ibkr_alert_sent = False
        self.last_ibkr_alert_time = 0
        self.ibkr_disconnected_since = None
        self.last_ibkr_ping_time = 0
        
    def _format_last_run(self, ts_str):
        """Convert a stored epoch timestamp string to a human-readable label."""
        if ts_str is None:
            return "Never"
        try:
            from datetime import datetime
            dt = datetime.fromtimestamp(float(ts_str))
            return dt.strftime("%Y-%m-%d %H:%M")
        except Exception:
            return "Never"

    def _send_ibkr_disconnect_email(self, duration_minutes, reason):
        return EmailNotifier.send_ibkr_disconnect_email(self, duration_minutes, reason)

    def _send_ibkr_recovery_email(self):
        return EmailNotifier.send_ibkr_recovery_email(self)
        
    #  Portfolio composition helpers
    # --------------------------------------------------------------
    def _get_usd_to_eur_rate(self):
        return get_usd_to_eur_rate(self.exchange_manager)

    def _calc_portfolio_composition(self):
        return calc_portfolio_composition(self.bots, self.ibapi, self.exchange_manager)

    def _calc_total_positions_pnl_eur(self):
        return calc_total_positions_pnl_eur(self.bots, self.exchange_manager)

    def _calc_total_daily_pnl_eur(self):
        return calc_total_daily_pnl_eur(self.bots, self.exchange_manager)
    
    def _apply_default_sort(self):
        if self.table.rowCount() == 0:
            QTimer.singleShot(200, self._apply_default_sort)
            return

        if not self._default_sort_applied:
            self.sort_column = self.DEFAULT_SORT_COLUMN  
            self.sort_order = self.DEFAULT_SORT_ORDER

            header = self.table.horizontalHeader()
            header.blockSignals(True)  # PREVENT RECURSION
            header.setSortIndicator(self.sort_column, self.sort_order)
            header.blockSignals(False)

            self.table.sortItems(self.sort_column, self.sort_order)
            self._default_sort_applied = True

    def refresh_cash(self):
        if not self.connected:
            return
        self.ibapi.cash_ready_event.clear()
        self.ibapi.reqAccountSummary(9001, "All", "NetLiquidation,TotalCashValue,AvailableFunds,DailyPnL,UnrealizedPnL,RealizedPnL")
        if self.ibapi.cash_ready_event.wait(5):
            self.rate_label.setText(
                f"EUR/USD: {self.exchange_manager.get_eur_usd_rate():.3f}  "
                f"Cash: {self.ibapi.currency_symbol}{self.ibapi.available_cash:,.0f}"
            )
            if hasattr(self.ibapi, 'net_liquidation') and self.ibapi.net_liquidation > 0:
                if hasattr(self, 'db_manager'):
                    self.db_manager.set_setting("global_account_value", str(self.ibapi.net_liquidation))
    
    def send_trade_email(self, symbol, action, quantity, price, native_currency, reason="", bot=None):
        return EmailNotifier.send_trade_email(self, symbol, action, quantity, price, native_currency, reason=reason, bot=bot)

    def save_min_cash(self):
        val = self.min_cash_edit.text().strip()
        try:
            float_val = float(val) if val else 0.0
            if float_val < 0:
                float_val = 0.0
                self.min_cash_edit.setText("0")
            self.min_cash = float_val
            self.db_manager.set_setting("min_cash", str(float_val))
        except ValueError:
            self.min_cash = 0.0
            self.min_cash_edit.setText("0")
            self.db_manager.set_setting("min_cash", "0.0")
        logger.info(f"Minimum cash updated to: €{self.min_cash:,.2f}")

    def save_global_risk(self):
        try:
            risk_pct = float(self.risk_pct_edit.text().strip())
            if hasattr(self, 'db_manager'):
                self.db_manager.set_setting("risk_per_trade_pct", str(risk_pct))
            logger.info(f"Updated Global Risk Settings: Risk={risk_pct}%")
        except ValueError as e:
            logger.error(f"Invalid Global Risk values: {e}")

    def highlight_selected_row(self):
        # Clear previous highlights (reset all rows to default background)
        for row in range(self.table.rowCount()):
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                if item:
                    item.setBackground(QColor("transparent"))  # Or your default color

        # Get selected rows (usually one, since single selection is default)
        selected_rows = self.table.selectionModel().selectedRows()
        if selected_rows:
            selected_row = selected_rows[0].row()
            
            # Toggle selection: if user clicked the same row again, clear selection to deselect it
            if hasattr(self, "_prev_selected_row") and self._prev_selected_row == selected_row:
                self.table.clearSelection()
                self._prev_selected_row = -1
                return
                
            self._prev_selected_row = selected_row
            # Apply premium slate-blue highlight to the entire row (transparent-friendly)
            for col in range(self.table.columnCount()):
                item = self.table.item(selected_row, col)
                if item:
                    item.setBackground(QColor("#2a4365"))
        else:
            self._prev_selected_row = -1

    def keyPressEvent(self, event):
        # Clear selection on Escape key press
        if event.key() == Qt.Key.Key_Escape:
            self.table.clearSelection()
            event.accept()
        else:
            super().keyPressEvent(event)

    def on_header_clicked(self, logical_index):
        self.sort_column = logical_index
        self.sort_order = self.table.horizontalHeader().sortIndicatorOrder()

    def show_header_context_menu(self, pos):
        menu = QMenu(self)
        headers = [self.table.horizontalHeaderItem(i).text() for i in range(self.table.columnCount())]
        
        for i, header_text in enumerate(headers):
            action = QAction(header_text, self)
            action.setCheckable(True)
            action.setChecked(not self.table.isColumnHidden(i))
            action.triggered.connect(lambda checked, idx=i: (
                self.table.setColumnHidden(idx, not checked),
                self.table.resizeColumnsToContents()
            ))
            menu.addAction(action)
            
        menu.exec(self.table.horizontalHeader().mapToGlobal(pos))

    def load_stocks(self):
        # 1. Get all stocks from the DB
        stocks = self.db_manager.get_all_stocks()
        self.table.setRowCount(len(stocks))

        for i, row in enumerate(stocks):
            sid = row[0]
            maxa = row[1]
            prof = row[2]
            drop = row[3]
            m_mode = bool(row[4])
            last_rej = row[5] if (len(row) > 5 and row[5] is not None) else 0
            highest_pnl = row[6] if (len(row) > 6 and row[6] is not None) else 0.0
            is_auto = bool(row[7]) if (len(row) > 7 and row[7] is not None) else False
            bought_strat = row[8] if (len(row) > 8 and row[8]) else None
            
            # 3. Create the bot with the saved manual_mode state
            bot = TradingBot(
                self.ibapi, sid, maxa, prof, drop, m_mode,
                self.db_manager, self.csv_manager, self.exchange_manager, self, is_auto
            )
            bot.last_rejection_time = last_rej
            bot.highest_pnl = highest_pnl
            bot.bought_strategy = bought_strat
            
            self.bots[sid] = bot
            bot.create_yf_ticker()

    def update_display(self):
        now = time.time()
        try:
            # ---------- 1. CASH + PORTFOLIO (same cadence as yfinance) ----------
            market_open = any(bot.is_market_open() for bot in self.bots.values())
            interval = self.ibapi.cash_fetch_interval if market_open else self.ibapi.max_cash_cache_age
            if now - self.ibapi.last_cash_fetch >= interval:
                self.ibapi.last_cash_fetch = now
                def fetch_cash():
                    try:
                        self.ibapi.cancelAccountSummary(9001)
                        time.sleep(0.5)
                        self.ibapi.cash_ready_event.clear()
                        self.ibapi.reqAccountSummary(9001, "All", "NetLiquidation,TotalCashValue,AvailableFunds,DailyPnL,UnrealizedPnL,RealizedPnL")
                        self.ibapi.cash_ready_event.wait(15)
                    except Exception as e:
                        logger.error(f"Error fetching cash summary in background: {e}")
                executor.submit(fetch_cash)

            # ---------- 2. EUR/USD ----------
            rate = self.exchange_manager.get_eur_usd_rate()
            self.rate_label.setText(f"EUR/USD: {rate:.3f}")

            # ---------- 3. CONNECTION + CASH + PORTFOLIO + TOTAL ----------
            if self.ibapi and hasattr(self.ibapi, 'isConnected'):
                self.connected = self.ibapi.isConnected()

            # Synchronize connection controls and trade button status based on actual connection status
            if self.connected:
                self.conn_btn.setText("Disconnect")
                self.conn_btn.setEnabled(True)
                if not self.auto_trading:
                    self.trade_btn.setEnabled(True)
            else:
                self.conn_btn.setText("Connect")
                if self.status_label.text() != "Connecting...":
                    self.conn_btn.setEnabled(True)
                self.trade_btn.setEnabled(False)

            cash_val   = self.ibapi.available_cash if self.connected else 0.0
            port_val   = self.ibapi.portfolio_value if self.connected else 0.0
            total_val  = cash_val + port_val

            cash_str   = f"{cash_val:,.0f}" if self.connected else "--"
            port_str   = f"{port_val:,.0f}" if self.connected else "--"
            total_str  = f"{total_val:,.0f}" if self.connected else "--"

            # ---------- 1. DAILY P&L (from IBKR reqPnL or calculated from prior close) ----------
            raw_daily_pnl = getattr(self.ibapi, 'daily_pnl', 0.0) if self.connected else 0.0
            if raw_daily_pnl == 0.0:
                raw_daily_pnl = self._calc_total_daily_pnl_eur()

            daily_sign = "+" if raw_daily_pnl > 0 else ""
            daily_pct = (raw_daily_pnl / total_val * 100) if total_val > 0 else 0.0
            daily_color = "#2ecc71" if raw_daily_pnl > 0 else ("#e74c3c" if raw_daily_pnl < 0 else "#aaaaaa")
            daily_pnl_display = f"Daily: <span style='color: {daily_color}; font-weight: bold;'>{daily_sign}€{raw_daily_pnl:,.2f} ({daily_sign}{daily_pct:.2f}%)</span>"

            # ---------- 2. UNREALIZED P&L (Total open position profit/loss) ----------
            raw_unreal_pnl = getattr(self.ibapi, 'unrealized_pnl', 0.0) if self.connected else 0.0
            if raw_unreal_pnl == 0.0 and hasattr(self.ibapi, 'positions') and self.ibapi.positions:
                with getattr(self.ibapi, 'data_lock', threading.Lock()):
                    raw_unreal_pnl = sum(pos.get('unrealizedPNL', 0.0) for pos in self.ibapi.positions.values())
            if raw_unreal_pnl == 0.0:
                raw_unreal_pnl = self._calc_total_positions_pnl_eur()

            unreal_sign = "+" if raw_unreal_pnl > 0 else ""
            unreal_pct = (raw_unreal_pnl / total_val * 100) if total_val > 0 else 0.0
            unreal_color = "#2ecc71" if raw_unreal_pnl > 0 else ("#e74c3c" if raw_unreal_pnl < 0 else "#aaaaaa")
            unreal_pnl_display = f"Unrealized: <span style='color: {unreal_color}; font-weight: bold;'>{unreal_sign}€{raw_unreal_pnl:,.2f} ({unreal_sign}{unreal_pct:.2f}%)</span>"

            # ----- % composition -----
            stock_p, etf_p, etc_p = self._calc_portfolio_composition()
            comp_str = f"{stock_p}% STOCK – {etf_p}% ETF – {etc_p}% ETC"

            if getattr(self, 'is_reconnecting', False) or self.status_label.text() in ("Connecting...", "Reconnecting..."):
                conn_text = "Reconnecting..." if not self.connected else "Connected"
                conn_color = "orange" if not self.connected else "green"
            else:
                conn_text = "Connected" if self.connected else "Disconnected"
                conn_color = "green" if self.connected else "red"

            self.status_label.setText(conn_text)
            self.status_label.setStyleSheet(f"color: {conn_color}; font-weight: bold;")

            if self.connected:
                if getattr(self, 'min_cash', 0.0) > 0:
                    usable_val = max(0.0, cash_val - self.min_cash)
                    usable_str = f"{usable_val:,.0f}"
                    cash_display = f"Cash: <b>€{cash_str}</b> (Usable: <b>€{usable_str}</b>)"
                else:
                    cash_display = f"Cash: <b>€{cash_str}</b>"
                self.portfolio_label.setText(
                    f"Total: <b>€{total_str}</b>  |  {daily_pnl_display}  |  {unreal_pnl_display}  |  {cash_display}  |  "
                    f"Port: <b>€{port_str}</b>  |  Alloc: <b>{comp_str}</b>"
                )
            else:
                self.portfolio_label.setText("Total: €--  |  Daily: €--  |  Unrealized: €--  |  Cash: €--  |  Port: €--  |  Alloc: --")
            # ---------- 4. TABLE ----------
            selected_symbol = None
            selected_items = self.table.selectedItems()
            if selected_items:
                selected_row = selected_items[0].row()
                selected_symbol_item = self.table.item(selected_row, 1)  # Assuming column 1 is Symbol/ID
                if selected_symbol_item:
                    selected_symbol = selected_symbol_item.text()

            v_scroll = self.table.verticalScrollBar().value()
            h_scroll = self.table.horizontalScrollBar().value()

            for row, (sid, bot) in enumerate(self.bots.items()):
                bot.get_market_value()
                bot.update_position()
                bot.calculate_technical_indicators()
                bot.check_trading_conditions(readonly=True)
                
                status = bot.get_status()
                volume_display = f"{bot.today_volume / 1e6:.1f}"
                # 1. Format the TPrice string with the warning emoji
                if bot.target_price > 0:
                    t_price_display = f"{bot.currency_symbol}{bot.target_price:.2f}"
                else:
                    t_price_display = "--"
                
                # --- ONE COLUMN: Latest Bank Target (Price + Name + Date) ---
                # Retrieve data from the bot
                bank_target_long = getattr(bot, 'latest_bank_target', 0)
                                
                # 1. Determine Currency Symbol
                currency_sym = "$" 
                if ".L" in bot.stock_id: currency_sym = "£"
                if ".PA" in bot.stock_id or ".DE" in bot.stock_id: currency_sym = "€"

                # 2. Format the Price: remove .00
                bank_target = f"{bank_target_long:g}" if bank_target_long else ""
                
                bank_name_long = getattr(bot, 'latest_bank_source', "--")
                abbr_map = {
                    "Morgan Stanley": "MS",
                    "JPMorgan Chase & Co.": "JPM",
                    "Goldman Sachs": "GS",
                    "Barclays": "BCS",
                    "Deutsche Bank": "DB",
                    "Bank of America": "BofA",
                    "Citigroup": "Citi",
                    "Credit Suisse": "CS",
                    "HSBC": "HSBC",
                    "RBC Capital Markets": "RBC",
                    "KeyBanc": "Key",
                    "Berenberg": "BER",
                    "Jefferies": "JEF",
                    "Wells Fargo": "WFC",
                    "Piper Sandler": "PIP",
                    "Truist Securities": "TUI",
                    "Bernstein": "AB",
                    "Mizuho": "MIZ",
                    "Nomura": "NOM",
                    "Susquehanna": "SUS",
                    "Evercore ISI": "EVR",
                    "Raymond James": "RJ",
                    "Canaccord Genuity": "CG",
                    "Stifel": "SF",
                    "BMO Capital Markets": "BMO",
                    "Oppenheimer": "OPP",
                    "Wedbush": "WED",
                    "Cowen": "COW",
                    "Needham": "NDM",
                    "Craig-Hallum": "CH",
                    "Roth Capital": "ROTH",
                    "Northland": "NLD",
                    "Loop Capital": "LOOP",
                    "Guggenheim": "GUG",
                    "Rosenblatt": "ROS",
                    "Benchmark": "BNC",
                    "Colliers Securities": "COL",
                }
                bank_name = abbr_map.get(bank_name_long, bank_name_long)

                bank_date = getattr(bot, 'latest_bank_date', "")

                short_date = bank_date
                if len(bank_date) == 10 and bank_date[4] == '-' and bank_date[7] == '-':
                    short_date = bank_date[5:]  # Get "MM-DD"

                # Create the consolidated string
                if bank_target and short_date and short_date != "--":
                    bank_note = f"{currency_sym}{bank_target} {bank_name} ({short_date})"
                elif bank_target:
                    bank_note = f"{currency_sym}{bank_target} {bank_name}"
                else:
                    bank_note = bank_name

                # Calcul de la variation journalière
                if bot.previous_close > 0:
                    price_pct = ((bot.market_value - bot.previous_close) / bot.previous_close) * 100
                    
                    # If the market is closed or hasn't started trading live today (e.g. US stocks before 15:30 CET),
                    # fallback to showing the last completed session's performance instead of +0.00%.
                    if getattr(bot, 'is_market_open', None) and not bot.is_market_open():
                        if not getattr(bot, 'is_last_date_today', True) or abs(price_pct) < 0.0001:
                            db_close = getattr(bot, 'day_before_yesterday_close', 0)
                            if db_close > 0:
                                price_pct = ((bot.previous_close - db_close) / db_close) * 100
                else:
                    price_pct = 0.0
                    
                if bot.manual_mode:
                    if getattr(bot, 'is_auto_watchlist', False):
                        status = "Watchlist"
                    else:
                        status = "Hold"

                earn_display = bot.next_earnings_date
                if not earn_display or earn_display == "No payment":
                    earn_display = '--'
                elif len(earn_display) == 10 and earn_display[4] == '-' and earn_display[7] == '-':
                    earn_display = earn_display[5:]

                comp_name_display = bot.company_name[:12] + ".." if len(bot.company_name) > 14 else bot.company_name

                strategy_arrow = " ↘" if getattr(bot, 'current_strategy', '') == "DIP" else (" ↗" if getattr(bot, 'current_strategy', '') == "MOMENTUM" else "")

                if bot.smart_score == 0 and "Insufficient Data" in bot.score_reason:
                    score_display = "⚠️ Data"
                else:
                    score_display = f"{bot.smart_score}{strategy_arrow}"

                # Compute trailing sell price (price at which trailing profit or protective stop would trigger)
                peak_pnl = max(price_pct, getattr(bot, 'highest_pnl', 0.0))
                target_pnl_pct = bot.dynamic_profit_target * 100

                if bot.quantity > 0 and bot.bought_price > 0 and peak_pnl >= target_pnl_pct:
                    _atr_pct = (bot.get_atr_14() / bot.market_value) * 100 if bot.market_value > 0 else 0
                    _trail_drop = max(0.5, min(_atr_pct * 0.5, 1.5))
                    _trail_activation = peak_pnl - _trail_drop
                    trail_sell_price = bot.bought_price * (1 + _trail_activation / 100)
                    _sign = "+" if _trail_activation > 0 else ""
                    trail_sell_display = f"{bot.currency_symbol}{trail_sell_price:.2f} ({_sign}{_trail_activation:.2f}%)"
                    trail_sell_sort = trail_sell_price
                elif bot.quantity > 0 and bot.bought_price > 0 and peak_pnl >= 5.0:
                    # Protective Trailing Stop (locks 75% of peak gains once peak >= 5%)
                    _trail_drop = peak_pnl * 0.25
                    _trail_activation = peak_pnl - _trail_drop
                    trail_sell_price = bot.bought_price * (1 + _trail_activation / 100)
                    _sign = "+" if _trail_activation > 0 else ""
                    trail_sell_display = f"{bot.currency_symbol}{trail_sell_price:.2f} ({_sign}{_trail_activation:.2f}%)"
                    trail_sell_sort = trail_sell_price
                else:
                    trail_sell_display = "--"
                    trail_sell_sort = 0.0

                items = [
                    comp_name_display, sid, bot.asset_type, bot.sector,
                    f"{bot.currency_symbol}{bot.market_value:.2f}",  
                    f"{price_pct:+.2f}%",
                    t_price_display,
                    bank_note,
                    score_display, 
                    f"{bot.currency_symbol}{bot.fourteen_day_high:.2f}",
                    f"{bot.currency_symbol}{bot.fourteen_day_low:.2f}",
                    f"{bot.rsi_value:.0f}", 
                    f"{bot.adx_value:.0f}",
                    bot.ma_signal, 
                    bot.macd_signal,
                    volume_display,
                    str(bot.quantity),
                    f"{bot.currency_symbol}{bot.bought_price:.2f}",
                    f"{bot.currency_symbol}{bot.current_value:.0f}",
                    f"{bot.pnl_percent:+.1f}%",
                    format_currency_short(bot.cash_left, "€"),
                    format_currency_short(bot.max_amount, "€"),
                    format_currency_short(getattr(bot, 'current_max_investment', bot.max_amount), "€"),
                    f"{bot.profit_target*100:.1f}%",
                    f"{bot.dynamic_profit_target*100:.1f}%",
                    trail_sell_display,
                    f"{bot.drop_threshold*100:.1f}%",
                    f"{bot.dynamic_stop_loss:.1f}%",
                    earn_display,
                    status
                ]

                sort_values = [
                    comp_name_display, sid, bot.asset_type, bot.sector,
                    bot.market_value,  
                    price_pct,
                    bot.target_price,
                    bank_target_long,
                    bot.smart_score, 
                    bot.fourteen_day_high,
                    bot.fourteen_day_low,
                    bot.rsi_value, 
                    bot.adx_value,
                    bot.ma_signal, 
                    bot.macd_signal,
                    bot.today_volume,
                    bot.quantity,
                    bot.bought_price,
                    (bot.current_value, bot.smart_score, getattr(bot, 'target_upside_pct', 0.0)),
                    bot.pnl_percent,
                    bot.cash_left,
                    bot.max_amount,
                    getattr(bot, 'current_max_investment', bot.max_amount),
                    bot.profit_target,
                    bot.dynamic_profit_target,
                    trail_sell_sort,
                    bot.drop_threshold,
                    bot.dynamic_stop_loss,
                    earn_display,
                    status
                ]

                for col, text in enumerate(items):
                    item = NumericTableWidgetItem(text, sort_values[col])
                    if col == 4:  # Price Column (Highlight in Green based purely on BUY score condition)
                        current_strat = getattr(bot, 'current_strategy', 'DIP')
                        base_score = getattr(bot, 'base_score', 0)
                        smart_score = getattr(bot, 'smart_score', 0)
                        
                        qualifies_dip = (current_strat == 'DIP' and smart_score >= 7 and base_score >= 5)
                        qualifies_mom = (current_strat == 'MOMENTUM' and smart_score >= 8 and base_score >= 6)
                        
                        if qualifies_dip or qualifies_mom:
                            item.setForeground(QColor("green"))          # Green Text Only
                            item.setFont(QFont("Arial", 10, QFont.Weight.Bold))
                            item.setToolTip(f"🟢 BUY TRIGGER SCORE MET: {current_strat} Score: {smart_score}/12 (Base: {base_score}/10)")

                    elif col == 11:  # RSI column
                        try:
                            rsi_val = float(text)
                            if rsi_val > 70:
                                item.setForeground(QColor("red"))  # Overbought, good to sell
                            elif rsi_val < 30:
                                item.setForeground(QColor("green"))  # Oversold, good to buy
                        except ValueError:
                            pass
                    elif col == 12:  # ADX column
                        try:
                            adx_val = float(text)
                            if adx_val >= 25:
                                item.setForeground(QColor("green"))  # Strong trend
                            else:
                                item.setForeground(QColor("orange"))  # Choppy
                        except ValueError:
                            pass
                    elif col == 15:  # Volume column
                        if bot.today_volume > 1.5 * bot.avg_volume_14d:
                            item.setForeground(QColor("green"))
                    elif col == 5: # Price%
                        if price_pct > 0:
                            item.setForeground(QColor("green"))
                        elif price_pct < 0:
                            item.setForeground(QColor("red"))
                    elif col == 8:
                        try:
                            score = bot.smart_score
                            if score == 0 and "Insufficient Data" in getattr(bot, 'score_reason', ''):
                                item.setBackground(QColor(180, 0, 0))      # Dark Red background for error
                                item.setForeground(QColor("white"))
                            elif score >= 8:
                                item.setBackground(QColor(0, 180, 0))      # Green
                                item.setForeground(QColor("white"))
                            elif score >= 6:
                                item.setBackground(QColor(255, 220, 0))    # Yellow
                                item.setForeground(QColor("black"))
                            elif score < 6:
                                item.setBackground(QColor(100, 100, 100))    # Orange
                            item.setFont(QFont("Arial", 10, QFont.Weight.Bold))
                            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                        except:
                            pass
                    elif col == 6 and bot.target_price > 0:
                        if bot.market_value < bot.target_price:
                        # Undervalued (Good for Buy) -> Green
                            item.setForeground(QColor("green"))
                        elif bot.market_value > bot.target_price:
                            # Overvalued (Above Analyst Target) -> Red
                            item.setForeground(QColor("red"))
                    elif col == 7 and bank_target_long > 0:
                        is_stale = False
                        bank_date_str = getattr(bot, 'latest_bank_date', "")
                        if bank_date_str and len(bank_date_str) >= 10:
                            try:
                                d = datetime.strptime(bank_date_str[:10], "%Y-%m-%d")
                                if (datetime.now() - d).days > 90:
                                    is_stale = True
                            except ValueError:
                                pass

                        if is_stale:
                            item.setForeground(QColor("red"))
                        elif bot.market_value < bank_target_long:
                            # Undervalued (Good for Buy) -> Green
                            item.setForeground(QColor("green"))
                        elif bot.market_value > bank_target_long:
                            # Overvalued (Above Analyst Target) -> Red
                            item.setForeground(QColor("red"))
                    elif col == 19: # PnL%
                        if bot.pnl_percent > 0:
                            item.setForeground(QColor("green"))
                        elif bot.pnl_percent < 0:
                            item.setForeground(QColor("red"))
                    elif col in (22, 24, 27): # ~Max, ~TP and ~SL
                        current_strat = getattr(bot, 'bought_strategy', None) or getattr(bot, 'current_strategy', 'DIP')
                        stop_cap = -7.0 if current_strat == 'DIP' else -9.0
                        atr = bot.get_atr_14()
                        atr_pct = (atr / bot.market_value * 100) if (atr > 0 and bot.market_value > 0) else 0
                        
                        if bot.dynamic_stop_loss <= stop_cap or atr_pct >= 3.0:
                            item.setForeground(QColor("red"))
                            item.setToolTip(f"High Volatility Stock (ATR: {atr_pct:.1f}%, Max Stop: {stop_cap:.1f}%)")
                    elif col == 25:  # Trail$ column - highlight green/orange when trailing is active
                        if trail_sell_sort > 0:
                            item.setForeground(QColor("#f39c12"))  # Orange to indicate active trailing
                            item.setToolTip(f"Trailing sell triggers if price drops to {trail_sell_display} (Peak PnL: {peak_pnl:.1f}%)")
                    elif col == 28:  # Earnings column
                        if bot.next_earnings_date:
                            try:
                                earn_date = datetime.strptime(bot.next_earnings_date, "%Y-%m-%d").date()
                                current_date = datetime.now().date()
                                delta = (earn_date - current_date).days
                                if 0 <= delta <= 30:  # Within 30 days (including today)
                                    item.setForeground(QColor("green"))  # Warning color
                            except ValueError:
                                pass  # Invalid date format; skip coloring
                    elif col == 29:  # Status column
                        if text == "Hold":
                            item.setForeground(QColor("red"))
                        elif text == "Watchlist":
                            item.setForeground(QColor("magenta"))
                        elif text == "Full capacity":
                            item.setForeground(QColor("green"))
                        elif text == "Budget too low":
                            item.setForeground(QColor("red"))
                        elif "Low Cash" in text:
                            item.setForeground(QColor("orange"))
                        elif "Closed" in text:
                            item.setForeground(QColor("orange"))
                        elif "Ready" in text:
                            item.setForeground(QColor("green"))
                    elif "BUY" in text or "BULL" in text:
                        item.setForeground(QColor("green"))   # Bullish signal, indicating to buy
                    elif "SELL" in text or "BEAR" in text:
                        item.setForeground(QColor("red"))  # Bearish signal, indicating to sell
                    elif col == 2:
                        color = QColor("blue") if "STOCK" in text else QColor("green") if "ETF" in text else QColor("orange") if "ETC" in text else QColor("black")
                        item.setForeground(QBrush(color))
                    self.table.setItem(row, col, item)

            # Sort using current settings
            self.table.sortItems(self.sort_column, self.sort_order)

            # Apply default sort ONCE, only if user hasn't clicked
            if not self._default_sort_applied and self.table.rowCount() > 0:
                self._apply_default_sort()

            # --- Restore selection by unique symbol ---
            if selected_symbol is not None:
                for row in range(self.table.rowCount()):
                    symbol_item = self.table.item(row, 1)
                    if symbol_item and symbol_item.text() == selected_symbol:
                        self.table.selectRow(row)
                        break

            # Automatically and dynamically resize all columns to prevent text truncation
            self.table.resizeColumnsToContents()

            self.table.verticalScrollBar().setValue(v_scroll)
            self.table.horizontalScrollBar().setValue(h_scroll)

            # 1. Yahoo Finance last fetch time
            last_yf_times = [bot.last_yf_fetch for bot in self.bots.values() if bot.last_yf_fetch > 0]
            yf_time_str = datetime.fromtimestamp(max(last_yf_times)).strftime("%H:%M:%S %d/%m/%Y") if last_yf_times else "--"

            # 2. IBKR last update time
            ibkr_time_str = datetime.fromtimestamp(self.ibapi.last_ibkr_update).strftime("%H:%M:%S %d/%m/%Y") if (self.connected and self.ibapi.last_ibkr_update > 0) else "--"

            self.update_time_label.setText(
                f"Last Fetch<br/>"
                f"YF  : {yf_time_str}<br/>"
                f"IBKR: {ibkr_time_str}"
            )
        except Exception as e:
            logger.error(f"Error in update_display: {e}")
            raise  # re-raise to see full traceback

    def toggle_trading(self):
        if self.auto_trading:
            self.auto_trading = False
            self.trade_btn.setText("Start Trading")
            self.trade_status_label.setText("Manual")
            self.trade_status_label.setStyleSheet("color: red; font-weight: bold;")
            for bot in self.bots.values():
                bot.is_running = False
        else:
            if not self.connected:
                QMessageBox.warning(self, "Error", "Connect first!")
                return
            self.auto_trading = True
            self.trade_btn.setText("Stop Trading")
            self.trade_status_label.setText("Running")
            self.trade_status_label.setStyleSheet("color: green; font-weight: bold;")
            for bot in self.bots.values():
                bot.is_running = True
            threading.Thread(target=self.trading_loop, daemon=True).start()

    def manual_refresh_data(self):
        # 1. Disable the update button and change text for visual feedback
        self.update_btn.setEnabled(False)
        self.update_btn.setText("Updating...")

        # 2. Reset indicator caches and trigger manual fetches
        for sid, bot in self.bots.items():
            bot.last_yf_fetch = 0
            bot.last_indicators_fetch = 0
            bot.calculate_technical_indicators(force=True)
            bot.get_market_value()
            bot.get_bank_note(run_async=True, force=True)

        # 3. Request fresh values from IBKR if connected
        if self.connected and self.ibapi:
            try:
                self.ibapi.reqAccountSummary(9001, "All", "NetLiquidation,AvailableFunds,DailyPnL,UnrealizedPnL,RealizedPnL")
                self.ibapi.reqPositions()
            except Exception as e:
                logger.error(f"Error requesting manual update from IBKR: {e}")

        # 4. Trigger a GUI table refresh immediately
        self.update_display()

        # 5. Restore the button state after 1.5 seconds
        QTimer.singleShot(1500, self.reset_update_btn)

    def reset_update_btn(self):
        self.update_btn.setEnabled(True)
        self.update_btn.setText("Update")

    def trading_loop(self):
        while self.auto_trading:
            if self.connected and hasattr(self, 'ibapi') and self.ibapi and getattr(self.ibapi, 'isConnected', lambda: False)():
                try:
                    self.ibapi.reqPositions()
                except Exception as e:
                    logger.warning(f"Error requesting positions in trading loop: {e}")
                time.sleep(3)

                # 1. Evaluate and Execute Sell Orders Immediately (First Priority)
                for sid, bot in self.bots.items():
                    if (bot.is_running and 
                        not bot.has_pending_order() and 
                        bot.is_market_open() and
                        bot.get_market_value() > 0 and
                        bot.quantity > 0):

                        # Respect order cooldown for this symbol
                        last_order = self.order_cooldown.get(sid, 0)
                        if time.time() - last_order < 300:
                            continue

                        action = bot.check_trading_conditions()
                        if action == 'SELL':
                            if bot.place_sell_order():
                                self.order_cooldown[sid] = time.time()
                                time.sleep(30)  # Wait for position & cash updates to process

                # 2. Collect Eligible Buy Candidates
                buy_candidates = []
                for sid, bot in self.bots.items():
                    if (bot.is_running and 
                        not bot.has_pending_order() and 
                        bot.is_market_open() and
                        bot.get_market_value() > 0 and
                        bot.cash_left >= getattr(bot, 'MIN_CASH_FOR_BUY', 500)):

                        # Respect order cooldown for this symbol
                        last_order = self.order_cooldown.get(sid, 0)
                        if time.time() - last_order < 300:
                            continue

                        action = bot.check_trading_conditions()
                        if action == 'BUY':
                            buy_candidates.append(bot)

                # 3. Sort Candidates by Smart Score (Tie-break by highest analyst target upside percentage)
                def sort_key(b):
                    return (b.smart_score, getattr(b, 'target_upside_pct', 0.0))
                    
                buy_candidates.sort(key=sort_key, reverse=True)

                # 4. Execute Buy Orders Sequentially
                for bot in buy_candidates:
                    # Re-verify cash limits before placing each order since preceding buys consume cash
                    usable_cash = bot.ibapi.available_cash - getattr(self, 'min_cash', 0.0)
                    if min(bot.cash_left, usable_cash) < bot.MIN_CASH_FOR_BUY:
                        logger.info(f"[{bot.stock_id}] Skipping buy candidate: remaining cash is insufficient (usable cash: €{usable_cash:,.2f}).")
                        continue

                    if bot.place_buy_order():
                        self.order_cooldown[bot.stock_id] = time.time()
                        time.sleep(30)  # Wait 30 seconds for cash balance updates to process

            time.sleep(15)

    def add_stock(self):
        sid = self.sym_edit.text().upper().strip()
        if not sid or sid in self.bots:
            QMessageBox.warning(self, "Error", "Invalid or duplicate")
            return
        try:
            # Hardcode dummy defaults since these are now dynamically calculated
            max_amt = 1000.0
            prof = 5.0
            drop = 5.0

            self.db_manager.add_stock(sid, max_amt, prof, drop)
            self.db_manager.remove_ignored_stock(sid) # Un-ignore if added manually
            
            bot = TradingBot(
                self.ibapi, sid, max_amt, prof, drop,
                manual_mode=False,                 
                db_manager=self.db_manager,         
                csv_manager=self.csv_manager,
                exchange_manager=self.exchange_manager,
                gui=self
            )
            self.bots[sid] = bot
            bot.create_yf_ticker()
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.sym_edit.clear()
            self.update_display()
        except:
            QMessageBox.warning(self, "Error", "Invalid numbers")



    def remove_stock(self):
        sel = self.table.selectedItems()
        if not sel:
            return
        row = sel[0].row()
        sid = self.table.item(row, 1).text()

        # CORRECTED: Proper QMessageBox usage
        reply = QMessageBox.question(
            self,
            "Remove Stock",
            f"Delete {sid} and all its data?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No  # default
        )

        if reply == QMessageBox.StandardButton.Yes:
            ignore_reply = QMessageBox.question(
                self,
                "Blacklist Stock",
                f"Do you want to ignore {sid} in future Maintenance Routines?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            if ignore_reply == QMessageBox.StandardButton.Yes:
                self.db_manager.add_ignored_stock(sid)
                
            # Stop trading for this bot
            bot = self.bots.get(sid)
            if bot:
                bot.is_running = False

            # Remove from DB and bots dict
            self.db_manager.remove_stock(sid)
            if sid in self.bots:
                del self.bots[sid]

            # Remove row from table
            self.table.removeRow(row)

            # Optional: refresh display to avoid index issues
            self.update_display()
            
    def get_selected_bot(self):
        """Helper to identify which stock is selected in the table."""
        selected_items = self.table.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Selection Required", "Please select a stock from the table first.")
            return None
        
        # Get the row index of the selection
        row = selected_items[0].row()
        # Symbol is in the second column (index 1)
        symbol = self.table.item(row, 1).text()
        return self.bots.get(symbol)

    def handle_manual_buy(self):
        bot = self.get_selected_bot()
        if bot:
            reply = QMessageBox.question(self, 'Confirm', f"Execute manual BUY for {bot.stock_id}?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                logger.info(f"User triggered manual BUY for {bot.stock_id}")
                bot.place_buy_order()

    def handle_manual_sell(self):
        bot = self.get_selected_bot()
        if bot:
            if bot.quantity <= 0:
                QMessageBox.warning(self, "Error", "You don't own any shares to sell!")
                return
            reply = QMessageBox.question(self, 'Confirm', f"Execute manual SELL for {bot.stock_id}?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                logger.info(f"User triggered manual SELL for {bot.stock_id}")
                bot.place_sell_order()

    def handle_manual_hold(self):
        bot = self.get_selected_bot()
        if bot:
            bot.manual_mode = not bot.manual_mode

            # Save the new state to the database
            with self.db_manager.get_cursor() as cursor:
                cursor.execute(
                    "UPDATE stocks SET manual_mode = ? WHERE stock_id = ?", # Fixed column name
                    (1 if bot.manual_mode else 0, bot.stock_id)
                )

            state = "MANUAL/HOLD" if bot.manual_mode else "AUTOMATED"
            logger.info(f"Bot {bot.stock_id} is now in {state} mode (Saved to DB).")
            self.update_display()
            
    def handle_maintenance_routine(self, silent=False):
        self._maint_silent = silent
        self.maint_btn.setEnabled(False)
        
        if not silent:
            self.progress_dialog = QProgressDialog("Starting...", "Cancel", 0, 100, self)
            self.progress_dialog.setWindowTitle("Maintenance Routine")
            self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        else:
            self.progress_dialog = None
        
        self.maint_thread = MaintenanceRoutineThread(self.db_manager, pause_callback=self.is_background_busy)
        self.maint_thread.progress.connect(self.on_maint_progress)
        self.maint_thread.finished_data.connect(self.on_maint_finished)
        self.maint_thread.error.connect(self.on_maint_error)
        
        if not silent:
            self.progress_dialog.canceled.connect(self.maint_thread.requestInterruption)
        self.maint_thread.start()

    def on_maint_progress(self, val, text):
        if not getattr(self, '_maint_silent', False) and getattr(self, 'progress_dialog', None):
            self.progress_dialog.setValue(val)
            self.progress_dialog.setLabelText(text)

    def on_maint_error(self, err):
        if not getattr(self, '_maint_silent', False) and getattr(self, 'progress_dialog', None):
            self.progress_dialog.close()
        self.maint_btn.setEnabled(True)
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Maintenance Routine failed:\n{err}")
        print(f"Maintenance Routine error: {err}")
        if not getattr(self, '_maint_silent', False):
            QMessageBox.critical(self, "Error", f"Maintenance failed: {err}")

    def on_maint_finished(self, top_10):
        if not getattr(self, '_maint_silent', False) and getattr(self, 'progress_dialog', None):
            self.progress_dialog.close()
        self.maint_btn.setEnabled(True)
        
        if not top_10:
            if not getattr(self, '_maint_silent', False):
                QMessageBox.warning(self, "No Results", "Could not fetch any target prices.")
            return

        # 1. Identify old auto-watchlist stocks that have NO open positions
        stocks_to_remove = []
        for bot in list(self.bots.values()):
            if getattr(bot, 'is_auto_watchlist', False):
                if bot.quantity == 0:
                    stocks_to_remove.append(bot.stock_id)
        
        # 2. Remove them
        for sid in stocks_to_remove:
            self.db_manager.remove_stock(sid)
            self.bots.pop(sid, None)
            
        # 3. Add new top 10
        added_count = 0
        for item in top_10:
            sym = item['symbol']
            if sym not in self.bots:
                # Default configuration for the new auto-added stock
                # Assumes default: max=1000, profit=5.0, drop=0.5
                self.db_manager.add_stock(sym, 1000.0, 5.0, 0.5, manual_mode=1, is_auto_watchlist=1)
                added_count += 1
                
        self.load_stocks()
        import time as _time
        self.db_manager.set_setting("last_maint_time", _time.time())
        if hasattr(self, 'maint_last_label'):
            self.maint_last_label.setText(f"Last: {self._format_last_run(str(_time.time()))}")
        self.maint_btn.setEnabled(True)
        if not getattr(self, '_maint_silent', False):
            QMessageBox.information(self, "Success", f"Maintenance Routine completed!\nRemoved {len(stocks_to_remove)} old watchlist stocks.\nAdded {added_count} new stocks with highest upside to the Auto Watchlist.")

    def handle_sync_from_server(self):
        script_path = os.path.join(PROJECT_ROOT, "scripts", "sync_from_server.sh")
        if not os.path.exists(script_path):
            QMessageBox.warning(self, "Error", f"Script not found: {script_path}")
            return

        # Check if SSH key works without password; if not and SERVER_SSH_PASS is not set, ask user for password
        import subprocess
        env_vars = os.environ.copy()
        ssh_pass = env_vars.get("SERVER_SSH_PASS", "").strip()
        if not ssh_pass:
            # Quick non-interactive SSH check (3s timeout)
            chk = subprocess.run(
                ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=4", "ubuntu@144.217.95.231", "echo OK"],
                capture_output=True, text=True
            )
            if chk.returncode != 0:
                pwd, ok = QInputDialog.getText(
                    self, "Server SSH Password",
                    "Nhập mật khẩu SSH cho ubuntu@144.217.95.231\n(Hoặc thêm SERVER_SSH_PASS=... vào file .env để không phải nhập lại):",
                    QLineEdit.EchoMode.Password
                )
                if not ok or not pwd.strip():
                    return
                env_vars["SERVER_SSH_PASS"] = pwd.strip()

        self.sync_db_btn.setEnabled(False)
        self.sync_db_btn.setText("Syncing...")

        def run_sync():
            try:
                res = subprocess.run([script_path], env=env_vars, capture_output=True, text=True, timeout=90)
                if res.returncode == 0:
                    QTimer.singleShot(0, lambda: self._on_sync_finished(True, res.stdout))
                else:
                    err_msg = (res.stderr or res.stdout or "Unknown error").strip()
                    QTimer.singleShot(0, lambda: self._on_sync_finished(False, err_msg))
            except Exception as e:
                QTimer.singleShot(0, lambda: self._on_sync_finished(False, str(e)))

        threading.Thread(target=run_sync, daemon=True).start()

    def _on_sync_finished(self, success, message):
        self.sync_db_btn.setEnabled(True)
        self.sync_db_btn.setText("☁️ Sync DB")
        if success:
            try:
                self.db_manager.close()
                self.db_manager.init_database()
                self.bots.clear()
                self.load_stocks()
                self.update_display()
            except Exception as e:
                logger.error(f"Error reloading DB after sync: {e}")
            QMessageBox.information(self, "Sync Complete", "✅ Đã đồng bộ thành công trading_bot.db & CSV từ Server OVH về máy Local!")
        else:
            QMessageBox.critical(self, "Sync Failed", f"❌ Không thể đồng bộ từ Server:\n\n{message[-600:]}")

    def open_csv(self):
        import sys
        import subprocess
        filename = os.path.join(PROJECT_ROOT, "trading_orders_history.csv")
        if os.path.exists(filename):
            if sys.platform == "win32":
                os.startfile(filename)
            elif sys.platform == "darwin":
                subprocess.run(["open", filename], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                subprocess.run(["xdg-open", filename], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            QMessageBox.information(self, "Info", "No trades yet.")
            
    def handle_backtest(self, silent=False):
        self._backtest_silent = silent
        self.backtest_btn.setEnabled(False)
        
        if not silent:
            self.progress_dialog = QProgressDialog("Running Backtest on all Database Stocks...", "Cancel", 0, 100, self)
            self.progress_dialog.setWindowTitle("Backtest")
            self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
            self.progress_dialog.setAutoClose(True)
            self.progress_dialog.setAutoReset(True)
        else:
            self.progress_dialog = None
            
        self.backtest_thread = BacktestThread(pause_callback=self.is_background_busy)
        if not silent:
            self.progress_dialog.canceled.connect(self.backtest_thread.requestInterruption)
        self.backtest_thread.progress.connect(self.on_backtest_progress)
        self.backtest_thread.finished_file.connect(self.on_backtest_finished)
        self.backtest_thread.error.connect(self.on_backtest_error)
        self.backtest_thread.start()

    def on_backtest_progress(self, val, msg):
        if not getattr(self, '_backtest_silent', False) and getattr(self, 'progress_dialog', None):
            self.progress_dialog.setValue(val)
            self.progress_dialog.setLabelText(msg)

    def on_backtest_error(self, err):
        if not getattr(self, '_backtest_silent', False) and getattr(self, 'progress_dialog', None):
            self.progress_dialog.close()
        self.backtest_btn.setEnabled(True)
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Backtest Error: {err}")
        if not getattr(self, '_backtest_silent', False):
            QMessageBox.critical(self, "Error", f"Backtest failed: {err}")

    def on_backtest_finished(self, file_path):
        self.backtest_btn.setEnabled(True)
        import time as _time
        self.db_manager.set_setting("last_backtest_time", _time.time())
        if hasattr(self, 'backtest_last_label'):
            self.backtest_last_label.setText(f"Last: {self._format_last_run(str(_time.time()))}") 
            
        if hasattr(self, 'progress_dialog'):
            self.progress_dialog.setValue(100)
            
        import sys
        import subprocess
        if os.path.exists(file_path):
            if sys.platform == "win32":
                os.startfile(file_path)
            elif sys.platform == "darwin":
                subprocess.run(["open", file_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                subprocess.run(["xdg-open", file_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            QMessageBox.warning(self, "Error", "Result file not found.")
    
    def closeEvent(self, event):
        logger.info("Shutting down application...")
    
        #   1. Stop all bots
        self.auto_trading = False
        for bot in self.bots.values():
            bot.stop()
        
        # 2. Disconnect IBKR
        if self.connected:
            self.ibapi.disconnect()
        
        # 3. Shutdown Executor (Global)
        executor.shutdown(wait=False) # Prevent new tasks
    
