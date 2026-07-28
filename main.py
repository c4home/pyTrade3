from config import *
from PyQt6.QtGui import QIcon
from gui import TradingApp

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Set App & Dock Icon
    icon_path = os.path.join(os.path.dirname(__file__), "assets", "app_icon.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    window = TradingApp()
    window.showMaximized()  # maximized window with title bar visible
    sys.exit(app.exec())