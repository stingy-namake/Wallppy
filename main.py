#!/usr/bin/env python3
import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QIcon

from core.settings import Settings
from ui.main_window import MainWindow
import extensions  # registers extensions

def main():
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon.fromTheme("wallpaper"))
    
    settings = Settings()
    window = MainWindow(settings)
    window.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()