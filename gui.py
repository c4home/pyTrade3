from config import *

from database import DatabaseManager, CSVManager
from exchange import ExchangeRateManager
from ib_api import IBApi
from trading_bot import TradingBot
from pdt_protector import PDTProtector

# ==================== MAIN GUI ====================
class TradingApp(QMainWindow):
    instance = None  # <-- ADD THIS
    DEFAULT_SORT_COLUMN = 27
    DEFAULT_SORT_ORDER  = Qt.SortOrder.AscendingOrder
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

        self.sort_column = self.DEFAULT_SORT_COLUMN  # Earning Date
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
            self.sort_order = self.DEFAULT_SORT_ORDER   # Ascending

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
            {reason}

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
            
            # 3. Create the bot with the saved manual_mode state
            bot = TradingBot(
                self.ibapi, sid, maxa, prof, drop, m_mode,
                self.db_manager, self.csv_manager, self.exchange_manager, self
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
                        db_close = getattr(bot, 'day_before_yesterday_close', 0)
                        if db_close > 0:
                            price_pct = ((bot.previous_close - db_close) / db_close) * 100
                else:
                    price_pct = 0.0
                    
                if bot.manual_mode:
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

                for col, text in enumerate(items):
                    item = QTableWidgetItem(text)
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
                        if bot.market_value < bank_target_long:
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
            
            bot = TradingBot(
                self.ibapi, sid, max_amt, prof, drop,
                manual_mode=False,                 
                db_manager=self.db_manager,         
                csv_manager=self.csv_manager,
                exchange_manager=self.exchange_manager,
                app=self
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
            
    def open_csv(self):
        if os.path.exists("trading_orders_history.csv"):
            os.startfile("trading_orders_history.csv")
        else:
            QMessageBox.information(self, "Info", "No trades yet.")
    
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
    
