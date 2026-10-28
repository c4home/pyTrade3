import os
import sys
from PyQt6.QtCore import QThread, pyqtSignal

from backend.config import PROJECT_ROOT


class BacktestThread(QThread):
    progress = pyqtSignal(int, str)
    finished_file = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, pause_callback=None):
        super().__init__()
        self.pause_callback = pause_callback

    def run(self):
        try:
            # Add backtest dir to sys.path so we can import the script
            backtest_dir = os.path.join(PROJECT_ROOT, "backtest")
            if backtest_dir not in sys.path:
                sys.path.append(backtest_dir)
            import importlib
            mod = importlib.import_module("run_present_stocks_backtest")
            run_backtest_for_db_stocks = mod.run_backtest_for_db_stocks

            def cb(pct, msg):
                if not self.isInterruptionRequested():
                    self.progress.emit(pct, msg)

            res_path = run_backtest_for_db_stocks(cb, pause_callback=self.pause_callback)
            if not self.isInterruptionRequested():
                self.finished_file.emit(res_path)
        except Exception as e:
            self.error.emit(str(e))

