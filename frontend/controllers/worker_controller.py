import os
import subprocess
import sys
import threading
import time
from datetime import datetime
from typing import TYPE_CHECKING, Any

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QInputDialog, QLineEdit, QMainWindow, QMessageBox, QProgressDialog

from backend.config import PROJECT_ROOT, logger
from frontend.workers.backtest_worker import BacktestThread
from frontend.workers.maintenance_worker import MaintenanceRoutineThread

if TYPE_CHECKING:
    class _WorkerMixinBase(QMainWindow):
        def __getattr__(self, name: str) -> Any: ...
else:
    _WorkerMixinBase = object


class WorkerControllerMixin(_WorkerMixinBase):
    """Mixin managing asynchronous background operations: Maintenance Routine, Backtests, and Server DB Sync."""

    def _format_last_run(self, ts_str):
        """Convert a stored epoch timestamp string to a human-readable label."""
        if ts_str is None:
            return "Never"
        try:
            dt = datetime.fromtimestamp(float(ts_str))
            return dt.strftime("%Y-%m-%d %H:%M")
        except Exception:
            return "Never"

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
        if not getattr(self, "_maint_silent", False) and getattr(self, "progress_dialog", None):
            self.progress_dialog.setValue(val)
            self.progress_dialog.setLabelText(text)

    def on_maint_error(self, err):
        if not getattr(self, "_maint_silent", False) and getattr(self, "progress_dialog", None):
            self.progress_dialog.close()
        self.maint_btn.setEnabled(True)
        logger.error(f"Maintenance Routine failed:\n{err}")
        print(f"Maintenance Routine error: {err}")
        if not getattr(self, "_maint_silent", False):
            QMessageBox.critical(self, "Error", f"Maintenance failed: {err}")

    def on_maint_finished(self, top_10):
        if not getattr(self, "_maint_silent", False) and getattr(self, "progress_dialog", None):
            self.progress_dialog.close()
        self.maint_btn.setEnabled(True)

        if not top_10:
            if not getattr(self, "_maint_silent", False):
                QMessageBox.warning(self, "No Results", "Could not fetch any target prices.")
            return

        # 1. Identify old auto-watchlist stocks that have NO open positions
        stocks_to_remove = []
        for bot in list(self.bots.values()):
            if getattr(bot, "is_auto_watchlist", False):
                if bot.quantity == 0:
                    stocks_to_remove.append(bot.stock_id)

        # 2. Remove them
        for sid in stocks_to_remove:
            self.db_manager.remove_stock(sid)
            self.bots.pop(sid, None)

        # 3. Add new top 10
        added_count = 0
        for item in top_10:
            sym = item["symbol"]
            if sym not in self.bots:
                self.db_manager.add_stock(sym, 1000.0, 5.0, 0.5, manual_mode=1, is_auto_watchlist=1)
                added_count += 1

        self.load_stocks()
        _now = time.time()
        self.db_manager.set_setting("last_maint_time", _now)
        if hasattr(self, "maint_last_label"):
            self.maint_last_label.setText(f"Last: {self._format_last_run(str(_now))}")
        self.maint_btn.setEnabled(True)
        if not getattr(self, "_maint_silent", False):
            QMessageBox.information(
                self,
                "Success",
                f"Maintenance Routine completed!\nRemoved {len(stocks_to_remove)} old watchlist stocks.\nAdded {added_count} new stocks with highest upside to the Auto Watchlist.",
            )

    def handle_sync_from_server(self):
        script_path = os.path.join(PROJECT_ROOT, "scripts", "sync_from_server.sh")
        if not os.path.exists(script_path):
            QMessageBox.warning(self, "Error", f"Script not found: {script_path}")
            return

        env_vars = os.environ.copy()
        ssh_pass = env_vars.get("SERVER_SSH_PASS", "").strip()
        if not ssh_pass:
            chk = subprocess.run(
                ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=4", "ubuntu@144.217.95.231", "echo OK"],
                capture_output=True,
                text=True,
            )
            if chk.returncode != 0:
                pwd, ok = QInputDialog.getText(
                    self,
                    "Server SSH Password",
                    "Nhập mật khẩu SSH cho ubuntu@144.217.95.231\n(Hoặc thêm SERVER_SSH_PASS=... vào file .env để không phải nhập lại):",
                    QLineEdit.EchoMode.Password,
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
            QMessageBox.information(
                self,
                "Sync Complete",
                "✅ Đã đồng bộ thành công trading_bot.db & CSV từ Server OVH về máy Local!",
            )
        else:
            QMessageBox.critical(self, "Sync Failed", f"❌ Không thể đồng bộ từ Server:\n\n{message[-600:]}")

    def open_csv(self):
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
            self.progress_dialog = QProgressDialog(
                "Running Backtest on all Database Stocks...", "Cancel", 0, 100, self
            )
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
        if not getattr(self, "_backtest_silent", False) and getattr(self, "progress_dialog", None):
            self.progress_dialog.setValue(val)
            self.progress_dialog.setLabelText(msg)

    def on_backtest_error(self, err):
        if not getattr(self, "_backtest_silent", False) and getattr(self, "progress_dialog", None):
            self.progress_dialog.close()
        self.backtest_btn.setEnabled(True)
        logger.error(f"Backtest Error: {err}")
        if not getattr(self, "_backtest_silent", False):
            QMessageBox.critical(self, "Error", f"Backtest failed: {err}")

    def on_backtest_finished(self, file_path):
        self.backtest_btn.setEnabled(True)
        _now = time.time()
        self.db_manager.set_setting("last_backtest_time", _now)
        if hasattr(self, "backtest_last_label"):
            self.backtest_last_label.setText(f"Last: {self._format_last_run(str(_now))}")

        if hasattr(self, "progress_dialog") and self.progress_dialog:
            self.progress_dialog.setValue(100)

        if os.path.exists(file_path):
            if sys.platform == "win32":
                os.startfile(file_path)
            elif sys.platform == "darwin":
                subprocess.run(["open", file_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                subprocess.run(["xdg-open", file_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            QMessageBox.warning(self, "Error", "Result file not found.")

