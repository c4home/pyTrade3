from typing import TYPE_CHECKING, Any

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from backend.config import ENV

if TYPE_CHECKING:
    class _UIMixinBase(QMainWindow):
        def __getattr__(self, name: str) -> Any: ...
else:
    _UIMixinBase = object


class NumericTableWidgetItem(QTableWidgetItem):
    def __init__(self, text, sort_value):
        super().__init__(text)
        self.sort_value = sort_value

    def __lt__(self, other):
        if hasattr(other, 'sort_value'):
            return bool(self.sort_value < other.sort_value)
        return super().__lt__(other)


class UISetupMixin(_UIMixinBase):
    """Mixin khởi tạo khung giao diện PyQt6, thanh công cụ điều khiển và bảng dữ liệu 30 cột."""

    def init_ui(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e1e;
                color: #ffffff;
            }
            QWidget#centralWidget {
                background-color: #1e1e1e;
            }
            QLabel, QCheckBox {
                background-color: transparent;
                color: #e0e0e0;
            }
            QGroupBox {
                background-color: #252526;
                color: #ffffff;
                font-weight: bold;
                border: 1px solid #3c3c3c;
                border-radius: 6px;
                margin-top: 6px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 5px;
                color: #3498db;
            }
            QLineEdit {
                background-color: #2d2d2d;
                color: #ffffff;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                padding: 3px 6px;
            }
            QSpinBox, QDoubleSpinBox {
                background-color: #2d2d2d;
                color: #ffffff;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
            }
        """)

        central = QWidget()
        central.setObjectName("centralWidget")
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

        # Single Unified Title-less Top Header Panel (IBKR Connection + Stock Settings combined)
        top_frame = QFrame()
        top_frame.setObjectName("topHeaderFrame")
        top_frame.setStyleSheet("""
            QFrame#topHeaderFrame {
                background-color: #252526;
                border: 1px solid #3c3c3c;
                border-radius: 6px;
            }
            QFrame#topHeaderFrame QLabel, QFrame#topHeaderFrame QCheckBox {
                background-color: transparent;
            }
        """)
        top_main_layout = QVBoxLayout()
        top_main_layout.setContentsMargins(10, 6, 10, 10)
        top_main_layout.setSpacing(6)

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

        self.sync_db_btn = QPushButton("☁️ Sync DB")
        self.sync_db_btn.setStyleSheet(common_button_style)
        self.sync_db_btn.setToolTip("Sync trading_bot.db & CSV from Production Server (OVH) to Local PC")
        self.sync_db_btn.clicked.connect(self.handle_sync_from_server)
        conn_row_layout.addWidget(self.sync_db_btn)

        self.csv_btn = QPushButton("View CSV")
        self.csv_btn.setStyleSheet(common_button_style)
        self.csv_btn.clicked.connect(self.open_csv)
        conn_row_layout.addWidget(self.csv_btn)

        top_main_layout.addLayout(conn_row_layout)

        # Row 2: Portfolio Dashboard Banner
        dash_row_layout = QHBoxLayout()

        self.portfolio_label = QLabel("Total: €--  |  Daily: €--  |  Unrealized: €--  |  Cash: €--  |  Portfolio: €--  |  Allocation: --")
        self.portfolio_label.setStyleSheet("font-size: 13px; font-weight: 500; color: #dfdfdf;")
        dash_row_layout.addWidget(self.portfolio_label)

        dash_row_layout.addStretch()

        # --- GLOBAL RISK SETTINGS ---
        saved_risk = "1.0"
        if hasattr(self, 'db_manager'):
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

        top_main_layout.addLayout(dash_row_layout)

        top_main_layout.addSpacing(4)
        separator_line = QFrame()
        separator_line.setFrameShape(QFrame.Shape.HLine)
        separator_line.setFrameShadow(QFrame.Shadow.Sunken)
        separator_line.setStyleSheet("background-color: #3c3c3c; max-height: 1px; border: none; margin-top: 4px; margin-bottom: 4px;")
        top_main_layout.addWidget(separator_line)
        top_main_layout.addSpacing(4)

        # Row 3: Stock Settings Controls
        stock_row_layout = QHBoxLayout()
        stock_row_layout.addWidget(QLabel("Symbol:"))
        self.sym_edit = QLineEdit()
        self.sym_edit.setFixedWidth(65)
        self.sym_edit.setPlaceholderText("Sym")
        stock_row_layout.addWidget(self.sym_edit)

        stock_row_layout.addSpacing(10)

        self.add_btn = QPushButton("Add Stock")
        self.add_btn.setStyleSheet(common_button_style)
        self.add_btn.clicked.connect(self.add_stock)
        stock_row_layout.addWidget(self.add_btn)

        self.remove_btn = QPushButton("Remove Stock")
        self.remove_btn.setStyleSheet(common_button_style)
        self.remove_btn.clicked.connect(self.remove_stock)
        stock_row_layout.addWidget(self.remove_btn)

        stock_row_layout.addStretch()

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
        stock_row_layout.addWidget(self.buy_btn)

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
        stock_row_layout.addWidget(self.sell_btn)

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
        stock_row_layout.addWidget(self.hold_btn)

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
        stock_row_layout.addWidget(self.maint_btn)

        last_maint = self.db_manager.get_setting("last_maint_time")
        maint_ts = self._format_last_run(last_maint)
        self.maint_last_label = QLabel(f"Last: {maint_ts}")
        self.maint_last_label.setStyleSheet("color: #aaaaaa; font-size: 10px; font-style: italic;")
        self.maint_last_label.setToolTip("Last time Maintenance Routine was run")
        stock_row_layout.addWidget(self.maint_last_label)

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
        stock_row_layout.addWidget(self.backtest_btn)

        last_bt = self.db_manager.get_setting("last_backtest_time")
        bt_ts = self._format_last_run(last_bt)
        self.backtest_last_label = QLabel(f"Last: {bt_ts}")
        self.backtest_last_label.setStyleSheet("color: #aaaaaa; font-size: 10px; font-style: italic;")
        self.backtest_last_label.setToolTip("Last time Backtest was run")
        stock_row_layout.addWidget(self.backtest_last_label)

        self.auto_status_icon = QLabel("✉")
        self.auto_status_icon.setStyleSheet("color: #7f8c8d; font-size: 20px;")
        self.auto_status_icon.setToolTip("Automated Routine Status")
        stock_row_layout.addWidget(self.auto_status_icon)

        top_main_layout.addLayout(stock_row_layout)
        top_frame.setLayout(top_main_layout)
        layout.addWidget(top_frame)

        # Main Stock Table
        self.table = QTableWidget()
        self.table.setColumnCount(30)
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
            "Qty", "Buy", "Value", "P&L%", "Left", "Max", "~Max", "TP%", "~TP", "Trail", "SL%", "~SL", "Earn", "Status"
        ]

        self.table.setHorizontalHeaderLabels(headers)
        h_header = self.table.horizontalHeader()
        if h_header is not None:
            font = QFont()
            font.setBold(True)
            h_header.setFont(font)

            # Enable context menu on the horizontal header to show/hide any column they want
            h_header.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            h_header.customContextMenuRequested.connect(self.show_header_context_menu)
            h_header.setStretchLastSection(True)
            h_header.sectionClicked.connect(self.on_header_clicked)

        # Configure default column visibilities to optimize space on MacBook Air screens
        self.table.setColumnHidden(2, True)   # Hide Type
        self.table.setColumnHidden(3, True)   # Hide Sector
        self.table.setColumnHidden(20, True)  # Hide Left
        self.table.setColumnHidden(21, True)  # Hide Max
        self.table.setColumnHidden(23, True)  # Hide TP%
        self.table.setColumnHidden(26, True)  # Hide SL%

        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.itemSelectionChanged.connect(self.highlight_selected_row)

        column_widths = [110, 42, 50, 80, 46, 46, 46, 105, 32, 45, 45, 25, 25, 45, 45, 40, 30, 45, 45, 48, 45, 45, 36, 40, 36, 46, 40, 36, 68, 52]
        for i, w in enumerate(column_widths):
            if w:
                self.table.setColumnWidth(i, w)
            elif h_header is not None:
                h_header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)

        layout.addWidget(self.table)
