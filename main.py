import os
import sys

# Đảm bảo đường dẫn gốc, backend và frontend luôn nằm trong sys.path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend")

for path in (PROJECT_ROOT, BACKEND_DIR, FRONTEND_DIR):
    if path not in sys.path:
        sys.path.insert(0, path)

# Tự động kích hoạt môi trường ảo .venv nếu người dùng chạy 'python3 main.py' từ terminal
if __name__ == "__main__":
    _venv_python = os.path.join(PROJECT_ROOT, ".venv", "bin", "python")
    if os.path.exists(_venv_python) and os.path.realpath(sys.executable) != os.path.realpath(_venv_python):
        try:
            import PyQt6
            import yfinance
        except ImportError:
            os.execv(_venv_python, [_venv_python] + sys.argv)

from backend.config import *
from PyQt6.QtGui import QIcon
from frontend.gui import TradingApp

if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Set App & Dock Icon
    icon_path = os.path.join(PROJECT_ROOT, "assets", "app_icon.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    window = TradingApp()
    window.showMaximized()  # maximized window with title bar visible
    sys.exit(app.exec())
