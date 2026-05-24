from config import *

from gui import TradingApp

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TradingApp()
    window.showMaximized()  # maximized window with title bar visible
    sys.exit(app.exec())