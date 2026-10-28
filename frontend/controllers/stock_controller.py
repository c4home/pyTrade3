from typing import TYPE_CHECKING, Any

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QColor
from PyQt6.QtWidgets import QMainWindow, QMenu, QMessageBox, QWidget

from backend.config import logger
from trading_bot import TradingBot

if TYPE_CHECKING:
    class _StockMixinBase(QMainWindow):
        def __getattr__(self, name: str) -> Any: ...
else:
    _StockMixinBase = object


class StockActionsMixin(_StockMixinBase):
    """Mixin handling user interactions with stocks, manual trade overrides, sorting and table selection."""

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
            if hasattr(self, "db_manager"):
                self.db_manager.set_setting("risk_per_trade_pct", str(risk_pct))
            logger.info(f"Updated Global Risk Settings: Risk={risk_pct}%")
        except ValueError as e:
            logger.error(f"Invalid Global Risk values: {e}")

    def highlight_selected_row(self):
        # Clear previous highlights
        for row in range(self.table.rowCount()):
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                if item:
                    item.setBackground(QColor("transparent"))

        selected_rows = self.table.selectionModel().selectedRows()
        if selected_rows:
            selected_row = selected_rows[0].row()
            if hasattr(self, "_prev_selected_row") and self._prev_selected_row == selected_row:
                self.table.clearSelection()
                self._prev_selected_row = -1
                return

            self._prev_selected_row = selected_row
            for col in range(self.table.columnCount()):
                item = self.table.item(selected_row, col)
                if item:
                    item.setBackground(QColor("#2a4365"))
        else:
            self._prev_selected_row = -1

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            if hasattr(self, "table") and self.table:
                self.table.clearSelection()
            event.accept()
        elif hasattr(super(), "keyPressEvent"):
            super().keyPressEvent(event)
        elif isinstance(self, QWidget):
            QWidget.keyPressEvent(self, event)

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
            action.triggered.connect(
                lambda checked, idx=i: (
                    self.table.setColumnHidden(idx, not checked),
                    self.table.resizeColumnsToContents(),
                )
            )
            menu.addAction(action)

        menu.exec(self.table.horizontalHeader().mapToGlobal(pos))

    def add_stock(self):
        sid = self.sym_edit.text().upper().strip()
        if not sid or sid in self.bots:
            QMessageBox.warning(self, "Error", "Invalid or duplicate")
            return
        try:
            max_amt = 1000.0
            prof = 5.0
            drop = 5.0

            self.db_manager.add_stock(sid, max_amt, prof, drop)
            self.db_manager.remove_ignored_stock(sid)

            bot = TradingBot(
                self.ibapi,
                sid,
                max_amt,
                prof,
                drop,
                manual_mode=False,
                db_manager=self.db_manager,
                csv_manager=self.csv_manager,
                exchange_manager=self.exchange_manager,
                gui=self,
            )
            self.bots[sid] = bot
            bot.create_yf_ticker()
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.sym_edit.clear()
            self.update_display()
        except Exception:
            QMessageBox.warning(self, "Error", "Invalid numbers")

    def remove_stock(self):
        sel = self.table.selectedItems()
        if not sel:
            return
        row = sel[0].row()
        sid = self.table.item(row, 1).text()

        reply = QMessageBox.question(
            self,
            "Remove Stock",
            f"Delete {sid} and all its data?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            ignore_reply = QMessageBox.question(
                self,
                "Blacklist Stock",
                f"Do you want to ignore {sid} in future Maintenance Routines?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if ignore_reply == QMessageBox.StandardButton.Yes:
                self.db_manager.add_ignored_stock(sid)

            bot = self.bots.get(sid)
            if bot:
                bot.is_running = False

            self.db_manager.remove_stock(sid)
            if sid in self.bots:
                del self.bots[sid]

            self.table.removeRow(row)
            self.update_display()

    def get_selected_bot(self):
        """Helper to identify which stock is selected in the table."""
        selected_items = self.table.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Selection Required", "Please select a stock from the table first.")
            return None

        row = selected_items[0].row()
        symbol = self.table.item(row, 1).text()
        return self.bots.get(symbol)

    def handle_manual_buy(self):
        bot = self.get_selected_bot()
        if bot:
            reply = QMessageBox.question(
                self,
                "Confirm",
                f"Execute manual BUY for {bot.stock_id}?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                logger.info(f"User triggered manual BUY for {bot.stock_id}")
                bot.place_buy_order()

    def handle_manual_sell(self):
        bot = self.get_selected_bot()
        if bot:
            if bot.quantity <= 0:
                QMessageBox.warning(self, "Error", "You don't own any shares to sell!")
                return
            reply = QMessageBox.question(
                self,
                "Confirm",
                f"Execute manual SELL for {bot.stock_id}?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                logger.info(f"User triggered manual SELL for {bot.stock_id}")
                bot.place_sell_order()

    def handle_manual_hold(self):
        bot = self.get_selected_bot()
        if bot:
            bot.manual_mode = not bot.manual_mode

            with self.db_manager.get_cursor() as cursor:
                cursor.execute(
                    "UPDATE stocks SET manual_mode = ? WHERE stock_id = ?",
                    (1 if bot.manual_mode else 0, bot.stock_id),
                )

            state = "MANUAL/HOLD" if bot.manual_mode else "AUTOMATED"
            logger.info(f"Bot {bot.stock_id} is now in {state} mode (Saved to DB).")
            self.update_display()

