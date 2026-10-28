import os
import threading
import time

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QMainWindow, QMessageBox

from backend.config import APP_BUILD, APP_VERSION, PROJECT_ROOT, executor, logger
from database import CSVManager, DatabaseManager
from frontend.components.table_items import NumericTableWidgetItem
from frontend.components.ui_setup import UISetupMixin
from frontend.controllers.stock_controller import StockActionsMixin
from frontend.controllers.trading_orchestrator import TradingOrchestrator
from frontend.controllers.worker_controller import WorkerControllerMixin
from frontend.renderers.summary_formatter import SummaryFormatter
from frontend.renderers.table_renderer import TableRenderer
from ib_api import IBApi
from ibkr_watchdog import IBKRWatchdogMixin
from notifier import EmailNotifier
from services.portfolio_sizing import (
    ExchangeRateManager,
    calc_portfolio_composition,
    calc_total_daily_pnl_eur,
    calc_total_positions_pnl_eur,
    get_usd_to_eur_rate,
)
from services.risk_manager import PDTProtector
from trading_bot import TradingBot


# ==================== MAIN GUI ====================
class TradingApp(
    QMainWindow,
    IBKRWatchdogMixin,
    UISetupMixin,
    StockActionsMixin,
    WorkerControllerMixin,
):
    """Main window coordinating UI view setup, renderers, stock actions, workers and trading orchestration."""

    instance = None
    DEFAULT_SORT_COLUMN = 18
    DEFAULT_SORT_ORDER = Qt.SortOrder.DescendingOrder

    def is_background_busy(self) -> bool:
        """Returns True if any bot is actively fetching indicators, market values, or bank notes."""
        for bot in self.bots.values():
            if (
                getattr(bot, "_fetching_indicators", False)
                or getattr(bot, "_fetching_market_value", False)
                or getattr(bot, "_fetching_bank_note", False)
            ):
                return True
        return False

    def __init__(self):
        super().__init__()
        TradingApp.instance = self
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

        self.sort_column = self.DEFAULT_SORT_COLUMN
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

        # Trigger default sort after GUI is ready
        QTimer.singleShot(100, self._apply_default_sort)

        # Try auto-connect after 500 ms
        QTimer.singleShot(500, self._auto_connect)

        # Auto-refresh data
        QTimer.singleShot(1500, self.manual_refresh_data)

        # Periodic Auto-Reconnect Monitor (checks every 15s for midnight TWS resets or connection drops)
        self.is_reconnecting = False
        self.reconnect_timer = QTimer()
        self.reconnect_timer.timeout.connect(self._check_auto_reconnect)
        self.reconnect_timer.start(15000)

        # IBKR Connection Watchdog
        self.app_start_time = time.time()
        self.ibkr_alert_sent = False
        self.last_ibkr_alert_time = 0
        self.ibkr_disconnected_since = None
        self.last_ibkr_ping_time = 0

    # --------------------------------------------------------------
    # Email notification delegates
    # --------------------------------------------------------------
    def _send_ibkr_disconnect_email(self, duration_minutes, reason):
        return EmailNotifier.send_ibkr_disconnect_email(self, duration_minutes, reason)

    def _send_ibkr_recovery_email(self):
        return EmailNotifier.send_ibkr_recovery_email(self)

    def send_trade_email(self, symbol, action, quantity, price, native_currency, reason="", bot=None):
        return EmailNotifier.send_trade_email(
            self, symbol, action, quantity, price, native_currency, reason=reason, bot=bot
        )

    # --------------------------------------------------------------
    # Portfolio composition helpers
    # --------------------------------------------------------------
    def _get_usd_to_eur_rate(self):
        return get_usd_to_eur_rate(self.exchange_manager)

    def _calc_portfolio_composition(self):
        return calc_portfolio_composition(self.bots, self.ibapi, self.exchange_manager)

    def _calc_total_positions_pnl_eur(self):
        return calc_total_positions_pnl_eur(self.bots, self.exchange_manager)

    def _calc_total_daily_pnl_eur(self):
        return calc_total_daily_pnl_eur(self.bots, self.exchange_manager)

    def refresh_cash(self):
        if not self.connected:
            return
        self.ibapi.cash_ready_event.clear()
        self.ibapi.reqAccountSummary(
            9001,
            "All",
            "NetLiquidation,TotalCashValue,AvailableFunds,DailyPnL,UnrealizedPnL,RealizedPnL",
        )
        if self.ibapi.cash_ready_event.wait(5):
            self.rate_label.setText(
                f"EUR/USD: {self.exchange_manager.get_eur_usd_rate():.3f}  "
                f"Cash: {self.ibapi.currency_symbol}{self.ibapi.available_cash:,.0f}"
            )
            if hasattr(self.ibapi, "net_liquidation") and self.ibapi.net_liquidation > 0:
                if hasattr(self, "db_manager"):
                    self.db_manager.set_setting("global_account_value", str(self.ibapi.net_liquidation))

    def load_stocks(self):
        stocks = self.db_manager.get_all_stocks()
        self.table.setRowCount(len(stocks))

        for row in stocks:
            sid = row[0]
            maxa = row[1]
            prof = row[2]
            drop = row[3]
            m_mode = bool(row[4])
            last_rej = row[5] if (len(row) > 5 and row[5] is not None) else 0
            highest_pnl = row[6] if (len(row) > 6 and row[6] is not None) else 0.0
            is_auto = bool(row[7]) if (len(row) > 7 and row[7] is not None) else False
            bought_strat = row[8] if (len(row) > 8 and row[8]) else None

            bot = TradingBot(
                self.ibapi,
                sid,
                maxa,
                prof,
                drop,
                m_mode,
                self.db_manager,
                self.csv_manager,
                self.exchange_manager,
                self,
                is_auto,
            )
            bot.last_rejection_time = last_rej
            bot.highest_pnl = highest_pnl
            bot.bought_strategy = bought_strat

            self.bots[sid] = bot
            bot.create_yf_ticker()

    def update_display(self):
        now = time.time()
        try:
            # 1. CASH + PORTFOLIO
            market_open = any(bot.is_market_open() for bot in self.bots.values())
            interval = self.ibapi.cash_fetch_interval if market_open else self.ibapi.max_cash_cache_age
            if now - self.ibapi.last_cash_fetch >= interval:
                self.ibapi.last_cash_fetch = now

                def fetch_cash():
                    try:
                        self.ibapi.cancelAccountSummary(9001)
                        time.sleep(0.5)
                        self.ibapi.cash_ready_event.clear()
                        self.ibapi.reqAccountSummary(
                            9001,
                            "All",
                            "NetLiquidation,TotalCashValue,AvailableFunds,DailyPnL,UnrealizedPnL,RealizedPnL",
                        )
                        self.ibapi.cash_ready_event.wait(15)
                    except Exception as e:
                        logger.error(f"Error fetching cash summary in background: {e}")

                executor.submit(fetch_cash)

            # 2. EUR/USD
            rate = self.exchange_manager.get_eur_usd_rate()
            self.rate_label.setText(f"EUR/USD: {rate:.3f}")

            # 3. CONNECTION + CASH + PORTFOLIO + TOTAL
            if self.ibapi and hasattr(self.ibapi, "isConnected"):
                self.connected = self.ibapi.isConnected()

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

            cash_val = self.ibapi.available_cash if self.connected else 0.0
            port_val = self.ibapi.portfolio_value if self.connected else 0.0

            raw_daily_pnl = getattr(self.ibapi, "daily_pnl", 0.0) if self.connected else 0.0
            if raw_daily_pnl == 0.0:
                raw_daily_pnl = self._calc_total_daily_pnl_eur()

            raw_unreal_pnl = getattr(self.ibapi, "unrealized_pnl", 0.0) if self.connected else 0.0
            if raw_unreal_pnl == 0.0 and hasattr(self.ibapi, "positions") and self.ibapi.positions:
                with getattr(self.ibapi, "data_lock", threading.Lock()):
                    raw_unreal_pnl = sum(pos.get("unrealizedPNL", 0.0) for pos in self.ibapi.positions.values())
            if raw_unreal_pnl == 0.0:
                raw_unreal_pnl = self._calc_total_positions_pnl_eur()

            stock_p, etf_p, etc_p = self._calc_portfolio_composition()
            comp_str = f"{stock_p}% STOCK – {etf_p}% ETF – {etc_p}% ETC"

            conn_text, conn_color = SummaryFormatter.get_connection_status(
                self.connected, getattr(self, "is_reconnecting", False), self.status_label.text()
            )
            self.status_label.setText(conn_text)
            self.status_label.setStyleSheet(f"color: {conn_color}; font-weight: bold;")

            summary_text = SummaryFormatter.format_portfolio_summary_text(
                self.connected,
                cash_val,
                port_val,
                getattr(self, "min_cash", 0.0),
                raw_daily_pnl,
                raw_unreal_pnl,
                comp_str,
            )
            self.portfolio_label.setText(summary_text)

            # 4. TABLE RENDERING
            selected_symbol = None
            selected_items = self.table.selectedItems()
            if selected_items:
                selected_row = selected_items[0].row()
                selected_symbol_item = self.table.item(selected_row, 1)
                if selected_symbol_item:
                    selected_symbol = selected_symbol_item.text()

            v_scroll = self.table.verticalScrollBar().value()
            h_scroll = self.table.horizontalScrollBar().value()

            for row, (sid, bot) in enumerate(self.bots.items()):
                # Call check_trading_conditions with readonly=True for safe indicator audit
                bot.check_trading_conditions(readonly=True)
                TableRenderer.render_row(self.table, row, sid, bot)

            self.table.sortItems(self.sort_column, self.sort_order)

            if not self._default_sort_applied and self.table.rowCount() > 0:
                self._apply_default_sort()

            # Restore selection by unique symbol
            if selected_symbol is not None:
                for row in range(self.table.rowCount()):
                    symbol_item = self.table.item(row, 1)
                    if symbol_item and symbol_item.text() == selected_symbol:
                        self.table.selectRow(row)
                        break

            self.table.resizeColumnsToContents()
            self.table.verticalScrollBar().setValue(v_scroll)
            self.table.horizontalScrollBar().setValue(h_scroll)

            # Last fetch timestamp labels
            self.update_time_label.setText(
                SummaryFormatter.format_last_fetch_html(
                    self.bots, self.connected, getattr(self.ibapi, "last_ibkr_update", 0)
                )
            )
        except Exception as e:
            logger.error(f"Error in update_display: {e}")
            raise

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
        self.update_btn.setEnabled(False)
        self.update_btn.setText("Updating...")

        for sid, bot in self.bots.items():
            bot.last_yf_fetch = 0
            bot.last_indicators_fetch = 0
            bot.calculate_technical_indicators(force=True)
            bot.get_market_value()
            bot.get_bank_note(run_async=True, force=True)

        if self.connected and self.ibapi:
            try:
                self.ibapi.reqAccountSummary(
                    9001,
                    "All",
                    "NetLiquidation,AvailableFunds,DailyPnL,UnrealizedPnL,RealizedPnL",
                )
                self.ibapi.reqPositions()
            except Exception as e:
                logger.error(f"Error requesting manual update from IBKR: {e}")

        self.update_display()
        QTimer.singleShot(1500, self.reset_update_btn)

    def reset_update_btn(self):
        self.update_btn.setEnabled(True)
        self.update_btn.setText("Update")

    def trading_loop(self):
        TradingOrchestrator.run_loop(self)

    def closeEvent(self, event):
        logger.info("Shutting down application...")
        self.auto_trading = False
        for bot in self.bots.values():
            bot.stop()

        if self.connected:
            self.ibapi.disconnect()

        executor.shutdown(wait=False)
