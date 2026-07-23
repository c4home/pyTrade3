from config import *

from database import DatabaseManager, CSVManager
from exchange import ExchangeRateManager
from ib_api import IBApi
from trading_bot import TradingBot
from pdt_protector import PDTProtector

class NumericTableWidgetItem(QTableWidgetItem):
    def __init__(self, text, sort_value):
        super().__init__(text)
        self.sort_value = sort_value

    def __lt__(self, other):
        if hasattr(other, 'sort_value'):
            return bool(self.sort_value < other.sort_value)
        return super().__lt__(other)

class BacktestThread(QThread):
    progress = pyqtSignal(int, str)
    finished_file = pyqtSignal(str)
    error = pyqtSignal(str)
    
    def run(self):
        try:
            import sys
            import os
            # Add backtest dir to sys.path so we can import the script
            backtest_dir = os.path.join(os.path.dirname(__file__), 'backtest')
            if backtest_dir not in sys.path:
                sys.path.append(backtest_dir)
            import importlib
            mod = importlib.import_module('run_present_stocks_backtest')
            run_backtest_for_db_stocks = mod.run_backtest_for_db_stocks
            
            def cb(pct, msg):
                if not self.isInterruptionRequested():
                    self.progress.emit(pct, msg)

            res_path = run_backtest_for_db_stocks(cb)
            if not self.isInterruptionRequested():
                self.finished_file.emit(res_path)
        except Exception as e:
            self.error.emit(str(e))

class MaintenanceRoutineThread(QThread):
    progress = pyqtSignal(int, str)
    finished_data = pyqtSignal(list)
    error = pyqtSignal(str)
    
    def __init__(self, db_manager):
        super().__init__()
        self.db_manager = db_manager

    def run(self):
        try:
            import yfinance as yf
            import pandas as pd
            import requests
            import io
            from trading_bot import TradingBot
            
            self.progress.emit(0, "Fetching S&P 500 list from Wikipedia...")
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            response = requests.get('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies', headers=headers)
            response.raise_for_status()
            tables = pd.read_html(io.StringIO(response.text))
            df = tables[0]
            tickers = df['Symbol'].tolist()
            tickers = [t.replace('.', '-') for t in tickers]
            
            ignored_stocks = self.db_manager.get_ignored_stocks()
            
            results = []
            total = len(tickers)
            for i, symbol in enumerate(tickers):
                if self.isInterruptionRequested():
                    return
                if symbol in ignored_stocks:
                    continue
                self.progress.emit(int((i / total) * 100), f"Fetching {symbol} ({i+1}/{total})")
                try:
                    # Use TradingBot's native fetch so the logic perfectly matches the UI
                    bot = TradingBot(None, symbol, 1000, 5, 0.5, manual_mode=True, db_manager=self.db_manager, gui=None)
                    target, source, date = bot.fetch_fresh_bank_note()
                            
                    if target and isinstance(target, (int, float)) and target > 0:
                        is_stale = False
                        if date and isinstance(date, str) and len(date) >= 10:
                            try:
                                from datetime import datetime
                                d = datetime.strptime(date[:10], "%Y-%m-%d")
                                if (datetime.now() - d).days > 90:
                                    is_stale = True
                            except Exception:
                                pass
                        
                        if is_stale:
                            continue

                        info = yf.Ticker(symbol).info
                        current = info.get('currentPrice') or info.get('previousClose')
                        if current and current > 0:
                            upside = (target - current) / current
                            results.append({'symbol': symbol, 'upside': upside})
                except Exception:
                    pass
            
            self.progress.emit(100, "Sorting results...")
            results.sort(key=lambda x: x['upside'], reverse=True)
            top_10 = results[:10]
            self.finished_data.emit(top_10)
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.error.emit(str(e))

# ==================== MAIN GUI ====================
class TradingApp(QMainWindow):
    instance = None  # <-- ADD THIS
    DEFAULT_SORT_COLUMN = 18
    DEFAULT_SORT_ORDER  = Qt.SortOrder.DescendingOrder
    def __init__(self):
        super().__init__()
        TradingApp.instance = self  # <-- SET INSTANCE
        self.setWindowTitle("pyTrade")
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
        
        # 4. Auto maintenance chain (check every minute)
        # It will naturally trigger 60 seconds after startup to avoid rate limiting
        # with the initial data fetching of the watchlist stocks.
        self.auto_maint_timer = QTimer()
        self.auto_maint_timer.timeout.connect(self.run_auto_maintenance_chain)
        self.auto_maint_timer.start(60000) # 1 minute
        
    def run_auto_maintenance_chain(self):
        import time
        import logging
        logger = logging.getLogger(__name__)
        last_run = self.db_manager.get_setting("last_auto_routine_time")
        now = time.time()
        
        # Run if never run before, or if > 24 hours have passed
        if last_run is None or (now - float(last_run)) > 86400:
            logger.info("Triggering automated maintenance and backtest chain.")
            self.handle_maintenance_routine(silent=True)

    def _auto_connect(self):
        # Called once at start‑up – only if the checkbox is checked.
        if not self.auto_connect_cb.isChecked():
            return

        # Force the button into “Connect” mode (in case it was left disconnected)
        self.conn_btn.setText("Connect")
        self.toggle_connection()          # <-- this does the real connect
        
    #  Portfolio composition helpers
    # --------------------------------------------------------------
    def _get_usd_to_eur_rate(self):
        eur_usd = self.exchange_manager.get_eur_usd_rate()
        if eur_usd > 0:
            return 1 / eur_usd
        else:
            logger.warning("[FX WARNING] Bad EURUSD rate; using fallback 0.92")
            return 0.92  # Update based on recent avg; or raise error
        
    def _calc_portfolio_composition(self):
        """Return (stock_pct, etf_pct, etc_pct) – each is 0-100%"""
        total_port = self.ibapi.portfolio_value
        if total_port <= 0:
            return 0.0, 0.0, 0.0

        usd_to_eur = self._get_usd_to_eur_rate()

        stock_val = etf_val = etc_val = 0.0
        for bot in self.bots.values():
            if bot.quantity <= 0:
                continue
            val = bot.current_value  # In bot's local currency (from yf)
            curr = bot.currency.upper()
            if curr != "EUR":
                rate = self.exchange_manager.get_rate(curr)
                if rate > 0:
                    val = val / rate

            if bot.asset_type == "STOCK":
                stock_val += val
            elif bot.asset_type == "ETF":
                etf_val += val
            elif bot.asset_type == "ETC":
                etc_val += val

        stock_pct = (stock_val / total_port) * 100
        etf_pct   = (etf_val   / total_port) * 100
        etc_pct   = (etc_val   / total_port) * 100
        return round(stock_pct, 1), round(etf_pct, 1), round(etc_pct, 1)
    
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

    def on_header_clicked(self, logical_index):
        self.sort_column = logical_index
        self.sort_order = self.table.horizontalHeader().sortIndicatorOrder()
        self._user_clicked_header = True
        self._default_sort_applied = True  # stop forcing default
        
    def refresh_cash(self):
        if not self.connected:
            return
        self.ibapi.cash_ready_event.clear()
        self.ibapi.reqAccountSummary(9001, "All", "NetLiquidation,TotalCashValue,AvailableFunds")
        if self.ibapi.cash_ready_event.wait(5):
            self.rate_label.setText(
                f"EUR/USD: {self.exchange_manager.get_eur_usd_rate():.3f}  "
                f"Cash: {self.ibapi.currency_symbol}{self.ibapi.available_cash:,.0f}"
            )
            if hasattr(self.ibapi, 'net_liquidation') and self.ibapi.net_liquidation > 0:
                if hasattr(self, 'db_manager'):
                    self.db_manager.set_setting("global_account_value", str(self.ibapi.net_liquidation))
    
    def send_trade_email(self, symbol, action, quantity, price, native_currency, reason="", bot=None):
        try:
            SMTP_SERVER = ENV["SMTP_SERVER"]
            SMTP_PORT = ENV["SMTP_PORT"]
            SENDER_EMAIL = ENV["SENDER_EMAIL"]
            SENDER_PASS = ENV["SENDER_EMAIL_PASS"]            
            RECEIVER_EMAIL = ENV["RECEIVER_EMAIL"]   
            # Get bot data safely
            if bot is None:
                # Fallback if bot not passed
                score = "N/A"
                rsi = "N/A"
                drop = "N/A"
                volume = "N/A"
                ma = "N/A"
                macd = "N/A"
                earnings = "N/A"
            else:
                score = bot.smart_score
                rsi = f"{bot.rsi_value:.1f}"
                drop_pct = ((bot.fourteen_day_high - bot.market_value) / bot.fourteen_day_high * 100) if bot.fourteen_day_high > 0 else 0
                drop = f"{drop_pct:.1f}%"
                
                projected_vol = bot.get_projected_volume()
                volume = f"Proj {projected_vol/1e6:.1f}M (Act: {bot.today_volume/1e6:.1f}M vs Avg: {bot.avg_volume_14d/1e6:.1f}M)"
                
                prev_ma = getattr(bot, 'prev_ma_signal', '')
                ma = f"{prev_ma} → {bot.ma_signal}" if prev_ma and prev_ma != bot.ma_signal else bot.ma_signal
                
                prev_macd = getattr(bot, 'prev_macd_signal', '')
                macd = f"{prev_macd} → {bot.macd_signal}" if prev_macd and prev_macd != bot.macd_signal else bot.macd_signal
                
                earnings = bot.next_earnings_date or "None"
                
            # 1. Currency symbol ($, €, £ …)
            curr_symbol = self.exchange_manager.get_currency_symbol(native_currency)
            
            pnl_info = ""
            if action == "SELL" and bot and getattr(bot, 'bought_price', 0) > 0:
                comp_bought = bot.bought_price
                if bot.currency == "GBp":
                    comp_bought = bot.bought_price * 100.0
                
                pnl_amount = (price - comp_bought) * quantity
                if bot.currency == "GBp":
                    pnl_amount = pnl_amount / 100.0
                    
                pnl_info = f"Realised P/L : {curr_symbol}{pnl_amount:+.2f} ({bot.pnl_percent:+.2f}%)\n            "

            skipped_text = ""
            if action == "BUY" and bot:
                skipped_list = []
                my_score = bot.smart_score
                my_upside = getattr(bot, 'target_upside_pct', 0.0)
                
                def sort_func(b):
                    return (b.smart_score, getattr(b, 'target_upside_pct', 0.0))
                all_bots = sorted(self.bots.values(), key=sort_func, reverse=True)
                
                for other in all_bots:
                    if other.stock_id == symbol:
                        continue
                        
                    other_score = other.smart_score
                    other_upside = getattr(other, 'target_upside_pct', 0.0)
                    
                    if other_score > my_score or (other_score == my_score and other_upside > my_upside):
                        skip_reason = "unknown"
                        if other.quantity > 0:
                            skip_reason = "already in position"
                        elif getattr(other, 'cash_left', 0) < getattr(other, 'market_value', 100000):
                            skip_reason = "budget too low for this stock"
                        elif not other.is_running:
                            skip_reason = "bot is paused"
                        elif not getattr(other, 'is_market_open', lambda: False)():
                            skip_reason = "market is closed"
                        elif other.has_pending_order():
                            skip_reason = "pending order exists"
                        else:
                            skip_reason = "technical conditions not met for BUY"
                            
                        skipped_list.append(f"- {other.stock_id} (Score: {other_score}/12): Skipped because {skip_reason}")
                        
                    elif other_score == my_score and other_upside < my_upside:
                        if other.quantity == 0 and other.is_running:
                            skip_reason = f"bank target upside is lower ({other_upside:.1f}% vs {symbol} at {my_upside:.1f}%)"
                            skipped_list.append(f"- {other.stock_id} (Score: {other_score}/12): Skipped because {skip_reason}")
                            
                    if len(skipped_list) >= 10:
                        break
                        
                if skipped_list:
                    skipped_text = "\n            SKIPPED ALTERNATIVES:\n            " + "\n            ".join(skipped_list) + "\n"

            # Format the primary reason block to be multi-line (splitting by |)
            formatted_reason = reason
            if "|" in formatted_reason:
                parts = [p.strip() for p in formatted_reason.split("|") if p.strip()]
                for i, p in enumerate(parts):
                    if p.startswith("[") and "Score:" in p and "{" in p:
                        p = p.replace(" {", "\n              ")
                        p = p.replace(", ", ",\n              ")
                        p = p.replace("}", "")
                        parts[i] = p
                formatted_reason = "\n            - ".join(parts)
                if not formatted_reason.startswith("\n"):
                    formatted_reason = "- " + formatted_reason

            subject = f"{action} {symbol} - {quantity} @ {curr_symbol}{price:.2f}"

            body = f"""
            TRADE EXECUTED - pyTrade BOT

            Symbol     : {symbol}
            Action     : {action}
            Quantity   : {quantity}
            Price      : {curr_symbol}{price:.2f}
            Total      : {curr_symbol}{quantity * price:.2f}
            {pnl_info}Time       : {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} (CET)

            REASON:
            {formatted_reason}
            {skipped_text}
            TECHNICALS:
            Score      : {score}/12
            RSI        : {rsi}
            14d Drop   : {drop}
            Volume     : {volume}
            MA Signal  : {ma}
            MACD       : {macd}
            Earnings   : {earnings}

            Bot is running — happy trading!
            """.strip()

            msg = MIMEText(body, 'plain', 'utf-8')
            msg['Subject'] = subject
            msg['From'] = SENDER_EMAIL
            msg['To'] = RECEIVER_EMAIL

            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=10) as server:
                server.starttls()
                server.login(SENDER_EMAIL, SENDER_PASS)
                server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())

            logger.info(f"EMAIL SENT -> {action} {symbol} {quantity} @ ${price:.2f}")
            return True
        except Exception as e:
            logger.error(f"[EMAIL ERROR] {e}")
            return False
        
    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Style sheet for standard buttons
        common_button_style = """
            QPushButton {
                background-color: #34495e;
                color: white;
                font-weight: bold;
                border-radius: 4px;
                padding: 5px 12px;
                border: 1px solid #2c3e50;
            }
            QPushButton:hover {
                background-color: #415b76;
            }
            QPushButton:pressed {
                background-color: #2c3e50;
            }
            QPushButton:disabled {
                background-color: #7f8c8d;
                color: #bdc3c7;
            }
        """

        conn_frame = QGroupBox("IBKR Connection")
        conn_main_layout = QVBoxLayout()
        
        # Row 1: Connection controls
        conn_row_layout = QHBoxLayout()
        
        conn_row_layout.addWidget(QLabel("Host:"))
        self.host_edit = QLineEdit(ENV["IBKR_HOST"])
        self.host_edit.setFixedWidth(80)
        conn_row_layout.addWidget(self.host_edit)
        
        conn_row_layout.addWidget(QLabel("Port:"))  
        self.port_edit = QLineEdit(ENV["IBKR_PORT"])
        self.port_edit.setFixedWidth(80)
        conn_row_layout.addWidget(self.port_edit)
        
        conn_row_layout.addWidget(QLabel("Client:"))
        self.client_edit = QLineEdit(ENV["IBKR_CLIENT_ID"])
        self.client_edit.setFixedWidth(30)
        conn_row_layout.addWidget(self.client_edit)
        
        self.auto_connect_cb = QCheckBox("Auto‑connect")
        self.auto_connect_cb.setChecked(True)
        conn_row_layout.addWidget(self.auto_connect_cb)
    
        self.conn_btn = QPushButton("Connect")
        self.conn_btn.setStyleSheet(common_button_style)
        self.conn_btn.clicked.connect(self.toggle_connection)
        conn_row_layout.addWidget(self.conn_btn)
        
        self.status_label = QLabel("Disconnected")
        self.status_label.setStyleSheet("color: red; font-weight: bold;")
        conn_row_layout.addWidget(self.status_label)
        
        conn_row_layout.addSpacing(15)
        
        self.trade_btn = QPushButton("Start Trading")
        self.trade_btn.setStyleSheet(common_button_style)
        self.trade_btn.clicked.connect(self.toggle_trading)
        self.trade_btn.setEnabled(False)
        conn_row_layout.addWidget(self.trade_btn)
        
        self.trade_status_label = QLabel("Manual")
        self.trade_status_label.setStyleSheet("color: red; font-weight: bold;")
        conn_row_layout.addWidget(self.trade_status_label)
        
        conn_row_layout.addSpacing(10)
        
        self.update_btn = QPushButton("Update")
        self.update_btn.setStyleSheet(common_button_style)
        self.update_btn.clicked.connect(self.manual_refresh_data)
        conn_row_layout.addWidget(self.update_btn)

        self.update_time_label = QLabel("Last Fetch<br/>YF  : --<br/>IBKR: --")
        self.update_time_label.setFont(QFont("Courier New", 10))
        self.update_time_label.setStyleSheet("color: #bdc3c7; font-weight: normal; margin-left: 5px; font-family: 'Courier New', Courier, Monaco, monospace; font-size: 10px;")
        conn_row_layout.addWidget(self.update_time_label)
        
        conn_row_layout.addStretch()
                
        self.csv_btn = QPushButton("View CSV")
        self.csv_btn.setStyleSheet(common_button_style)
        self.csv_btn.clicked.connect(self.open_csv)
        conn_row_layout.addWidget(self.csv_btn)
        
        conn_main_layout.addLayout(conn_row_layout)
        
        # Row 2: Portfolio Dashboard Banner
        dash_row_layout = QHBoxLayout()
        
        self.portfolio_label = QLabel("Total Value: €--  |  Cash: €--  |  Portfolio: €--  |  Allocation: --")
        self.portfolio_label.setStyleSheet("font-size: 13px; font-weight: 500; color: #dfdfdf;")
        dash_row_layout.addWidget(self.portfolio_label)
        
        dash_row_layout.addStretch()
        
        # --- GLOBAL RISK SETTINGS ---
        saved_account = "14000"
        saved_risk = "1.0"
        if hasattr(self, 'db_manager'):
            saved_account = self.db_manager.get_setting("global_account_value", "14000")
            saved_risk = self.db_manager.get_setting("risk_per_trade_pct", "1.0")

        self.risk_pct_edit = QLineEdit(saved_risk)
        self.risk_pct_edit.setFixedWidth(40)
        self.risk_pct_edit.editingFinished.connect(self.save_global_risk)
        dash_row_layout.addWidget(QLabel("Risk (%):"))
        dash_row_layout.addWidget(self.risk_pct_edit)
        
        dash_row_layout.addSpacing(15)
        # ---------------------------
        
        dash_row_layout.addWidget(QLabel("Min Cash (€):"))
        self.min_cash_edit = QLineEdit("0")
        self.min_cash_edit.setFixedWidth(70)
        
        # Set same stylesheet for the new edits
        style = """
            QLineEdit {
                background-color: #1a1a1a;
                color: #ffffff;
                border: 1px solid #2c3e50;
                border-radius: 3px;
                padding: 2px;
                font-weight: bold;
            }
        """
        self.min_cash_edit.setStyleSheet(style)
        self.risk_pct_edit.setStyleSheet(style)
        dash_row_layout.addWidget(self.min_cash_edit)
        
        dash_row_layout.addSpacing(15)
        
        self.rate_label = QLabel("EUR/USD: --")
        self.rate_label.setStyleSheet("font-size: 13px; font-weight: bold; color: #3498db;")
        dash_row_layout.addWidget(self.rate_label)
        
        conn_main_layout.addLayout(dash_row_layout)
        conn_frame.setLayout(conn_main_layout)
        layout.addWidget(conn_frame)

        self.table = QTableWidget()
        self.table.setColumnCount(29)
        self.table.setWordWrap(True)                 
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #121212;
                gridline-color: #2c3e50;
                color: #ffffff;
                font-size: 10px;
            }
            QTableWidget::item {
                padding: 1px 3px;
            }
            QHeaderView::section {
                background-color: #2c3e50;
                color: #ffffff;
                font-size: 10px;
                font-weight: bold;
                padding: 2px 3px;
                border: 1px solid #1d1d1d;
            }
        """)
        headers = [
            "Company", "Sym", "Type", "Sector",
            "Price", "Chg%", "Target", "Bank Target", "Score", "14H", "14L", "RSI", "ADX", "MA", "MACD", "Vol(M)",
            "Qty", "Buy@", "Value", "P&L%", "Left", "Max", "DynMax", "TP%", "DynTP", "SL%", "DynSL", "Earn", "Status"
        ]

        self.table.setHorizontalHeaderLabels(headers)
        font = QFont()
        font.setBold(True)
        self.table.horizontalHeader().setFont(font)

        # Configure default column visibilities to optimize space on MacBook Air screens
        self.table.setColumnHidden(2, True)   # Hide Type
        self.table.setColumnHidden(3, True)   # Hide Sector
        self.table.setColumnHidden(20, True)  # Hide Left
        self.table.setColumnHidden(21, True)  # Hide Max
        self.table.setColumnHidden(23, True)  # Hide TP%
        self.table.setColumnHidden(25, True)  # Hide SL%

        # Enable context menu on the horizontal header to show/hide any column they want
        self.table.horizontalHeader().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.horizontalHeader().customContextMenuRequested.connect(self.show_header_context_menu)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().sectionClicked.connect(self.on_header_clicked)
        self.table.itemSelectionChanged.connect(self.highlight_selected_row)

        column_widths = [110, 42, 50, 80, 46, 46, 46, 105, 32, 45, 45, 25, 25, 45, 45, 40, 30, 45, 45, 48, 45, 45, 45, 40, 40, 35, 40, 68, 52]
        for i, w in enumerate(column_widths):
            if w:
                self.table.setColumnWidth(i, w)
            else:
                self.table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)

        layout.addWidget(self.table)

        input_frame = QGroupBox("Stock Settings")
        input_main_layout = QVBoxLayout()
        input_main_layout.setContentsMargins(10, 4, 10, 4)
        
        row_layout = QHBoxLayout()
        row_layout.addWidget(QLabel("Symbol:"))
        self.sym_edit = QLineEdit()
        self.sym_edit.setFixedWidth(65)
        self.sym_edit.setPlaceholderText("Sym")
        row_layout.addWidget(self.sym_edit)
        
        row_layout.addSpacing(10)
        
        self.add_btn = QPushButton("Add Stock")
        self.add_btn.setStyleSheet(common_button_style)
        self.add_btn.clicked.connect(self.add_stock)
        row_layout.addWidget(self.add_btn)
        
        self.remove_btn = QPushButton("Remove Stock")
        self.remove_btn.setStyleSheet(common_button_style)
        self.remove_btn.clicked.connect(self.remove_stock)
        row_layout.addWidget(self.remove_btn)
        
        row_layout.addStretch()
        
        self.buy_btn = QPushButton("Buy")
        self.buy_btn.setStyleSheet("""
            QPushButton {
                background-color: #2ecc71;
                color: white;
                font-weight: bold;
                border-radius: 4px;
                padding: 4px 10px;
                min-width: 60px;
            }
            QPushButton:hover {
                background-color: #27ae60;
            }
            QPushButton:pressed {
                background-color: #1e8449;
            }
        """)
        self.buy_btn.clicked.connect(self.handle_manual_buy)
        row_layout.addWidget(self.buy_btn)

        self.sell_btn = QPushButton("Sell")
        self.sell_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                font-weight: bold;
                border-radius: 4px;
                padding: 4px 10px;
                min-width: 60px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
            QPushButton:pressed {
                background-color: #922b21;
            }
        """)
        self.sell_btn.clicked.connect(self.handle_manual_sell)
        row_layout.addWidget(self.sell_btn)

        self.hold_btn = QPushButton("Hold")
        self.hold_btn.setStyleSheet("""
            QPushButton {
                background-color: #f1c40f;
                color: black;
                font-weight: bold;
                border-radius: 4px;
                padding: 4px 10px;
                min-width: 60px;
            }
            QPushButton:hover {
                background-color: #f39c12;
            }
            QPushButton:pressed {
                background-color: #d68910;
            }
        """)
        self.hold_btn.clicked.connect(self.handle_manual_hold)
        row_layout.addWidget(self.hold_btn)

        self.maint_btn = QPushButton("Maintenance Routine")
        self.maint_btn.setStyleSheet("""
            QPushButton {
                background-color: #8e44ad;
                color: white;
                font-weight: bold;
                border-radius: 4px;
                padding: 4px 10px;
                min-width: 120px;
            }
            QPushButton:hover { background-color: #9b59b6; }
            QPushButton:pressed { background-color: #732d91; }
            QPushButton:disabled { background-color: #555555; }
        """)
        self.maint_btn.clicked.connect(self.handle_maintenance_routine)
        row_layout.addWidget(self.maint_btn)
        
        self.backtest_btn = QPushButton("Run Backtest (DB)")
        self.backtest_btn.setStyleSheet("""
            QPushButton {
                background-color: #34495e;
                color: white;
                font-weight: bold;
                border-radius: 4px;
                padding: 4px 10px;
                min-width: 120px;
            }
            QPushButton:hover { background-color: #2c3e50; }
            QPushButton:pressed { background-color: #1a252f; }
            QPushButton:disabled { background-color: #555555; }
        """)
        self.backtest_btn.clicked.connect(self.handle_backtest)
        row_layout.addWidget(self.backtest_btn)
        
        self.auto_status_icon = QLabel("✉")
        self.auto_status_icon.setStyleSheet("color: #7f8c8d; font-size: 20px;")
        self.auto_status_icon.setToolTip("Automated Routine Status")
        row_layout.addWidget(self.auto_status_icon)

        input_main_layout.addLayout(row_layout)
        input_frame.setLayout(input_main_layout)
        layout.addWidget(input_frame)

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
            
            # 3. Create the bot with the saved manual_mode state
            bot = TradingBot(
                self.ibapi, sid, maxa, prof, drop, m_mode,
                self.db_manager, self.csv_manager, self.exchange_manager, self, is_auto
            )
            bot.last_rejection_time = last_rej
            bot.highest_pnl = highest_pnl
            
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
                        self.ibapi.reqAccountSummary(9001, "All", "NetLiquidation,TotalCashValue,AvailableFunds")
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

            # ----- % composition -----
            stock_p, etf_p, etc_p = self._calc_portfolio_composition()
            comp_str = f"{stock_p}% STOCK – {etf_p}% ETF – {etc_p}% ETC"

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
                    f"Total Value: <b>€{total_str}</b>  |  {cash_display}  |  "
                    f"Portfolio: <b>€{port_str}</b>  |  Allocation: <b>{comp_str}</b>"
                )
            else:
                self.portfolio_label.setText("Total Value: €--  |  Cash: €--  |  Portfolio: €--  |  Allocation: --")
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
                bot.check_trading_conditions()
                
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
                    
                    # If the market is closed, overnight pre-market changes are tiny.
                    # Show the performance of the last completed session instead to match user expectations.
                    if getattr(bot, 'is_market_open', None) and not bot.is_market_open():
                        if not getattr(bot, 'is_last_date_today', True):
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
                    bot.current_value,
                    bot.pnl_percent,
                    bot.cash_left,
                    bot.max_amount,
                    getattr(bot, 'current_max_investment', bot.max_amount),
                    bot.profit_target,
                    bot.dynamic_profit_target,
                    bot.drop_threshold,
                    bot.dynamic_stop_loss,
                    earn_display,
                    status
                ]

                for col, text in enumerate(items):
                    item = NumericTableWidgetItem(text, sort_values[col])
                    if col == 11:  # RSI column
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
                    elif col == 27:  # Earnings column
                        if bot.next_earnings_date:
                            try:
                                earn_date = datetime.strptime(bot.next_earnings_date, "%Y-%m-%d").date()
                                current_date = datetime.now().date()
                                delta = (earn_date - current_date).days
                                if 0 <= delta <= 30:  # Within 30 days (including today)
                                    item.setForeground(QColor("green"))  # Warning color
                            except ValueError:
                                pass  # Invalid date format; skip coloring
                    elif col == 28:  # Status column
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
                    elif "BUY" in text or "BULL" in text:
                        item.setForeground(QColor("green"))   # Bullish signal, indicating to buy
                    elif "SELL" in text or "BEAR" in text:
                        item.setForeground(QColor("red"))  # Bearish signal, indicating to sell
                    elif "Closed" in text:
                        item.setForeground(QColor("orange"))
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

    def toggle_connection(self):
        if not hasattr(self, "ibapi"):      # safety net
            return

        if self.connected:
            self.ibapi.disconnect()
            self.connected = False
            self.status_label.setText("Disconnected")
            self.status_label.setStyleSheet("color: red;")
            self.conn_btn.setText("Connect")
            self.trade_btn.setEnabled(False)
        else:
            # ----- CONNECT -----
            host = self.host_edit.text().strip() or ENV["IBKR_HOST"]
            self.status_label.setText("Connecting...")
            self.status_label.setStyleSheet("color: orange; font-weight: bold;")
            self.conn_btn.setEnabled(False)
            
            def connect_task():
                try:
                    try:
                        port = int(self.port_edit.text())
                    except ValueError:
                        port = int(ENV["IBKR_PORT"])
                    try:
                        cid = int(self.client_edit.text())
                    except ValueError:
                        cid = int(ENV["IBKR_CLIENT_ID"])
                    
                    self.ibapi.connect(host, port, clientId=cid)
                    threading.Thread(target=self.ibapi.run, daemon=True).start()

                    if self.ibapi.connected_event.wait(12):
                        self.connected = True
                        try:
                            self.ibapi.reqPositions()
                        except Exception as e:
                            logger.error(f"Error requesting positions: {e}")
                        
                        try:
                            # ---- INITIAL CASH ----
                            self.ibapi.cash_ready_event.clear()
                            self.ibapi.reqAccountSummary(9001, "All", "NetLiquidation,TotalCashValue,AvailableFunds")
                            if self.ibapi.cash_ready_event.wait(8):
                                self.ibapi.last_cash_fetch = time.time()
                        except Exception as e:
                            logger.error(f"Error requesting account summary: {e}")
                        
                        QTimer.singleShot(0, lambda: self._on_connect_success())
                    else:
                        QTimer.singleShot(0, lambda: self._on_connect_fail())
                except Exception as e:
                    logger.error(f"Connection task failed: {e}")
                    self.connected = False
                    QTimer.singleShot(0, lambda: self._on_connect_fail())
                    
            threading.Thread(target=connect_task, daemon=True).start()

    def _on_connect_success(self):
        self.status_label.setText("Connected")
        self.status_label.setStyleSheet("color: green; font-weight: bold;")
        self.conn_btn.setText("Disconnect")
        self.conn_btn.setEnabled(True)
        self.trade_btn.setEnabled(True)

    def _on_connect_fail(self):
        self.status_label.setText("Conn. failed")
        self.status_label.setStyleSheet("color: red; font-weight: bold;")
        self.conn_btn.setText("Connect")
        self.conn_btn.setEnabled(True)

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
                self.ibapi.reqAccountSummary(9001, "All", "NetLiquidation,AvailableFunds")
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
            if self.connected:
                self.ibapi.reqPositions()
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
        
        self.maint_thread = MaintenanceRoutineThread(self.db_manager)
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
        if not getattr(self, '_maint_silent', False):
            QMessageBox.information(self, "Success", f"Maintenance Routine completed!\nRemoved {len(stocks_to_remove)} old watchlist stocks.\nAdded {added_count} new stocks with highest upside to the Auto Watchlist.")
        else:
            self.handle_backtest(silent=True)

    def open_csv(self):
        import sys
        import subprocess
        filename = "trading_orders_history.csv"
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
            
        self.backtest_thread = BacktestThread()
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
        
        if getattr(self, '_backtest_silent', False):
            import time
            import logging
            logger = logging.getLogger(__name__)
            self.db_manager.set_setting("last_auto_routine_time", time.time())
            logger.info("Automated chain completed silently. Backtest results saved.")
            
            # Update status icon to red to alert the user
            if hasattr(self, 'auto_status_icon'):
                self.auto_status_icon.setStyleSheet("color: #e74c3c; font-size: 18px;")
                self.auto_status_icon.setToolTip("Automated chain completed! Check results.")
            return
            
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
    
