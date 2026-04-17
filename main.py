#!/usr/bin/env python3
import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QIcon

from core.settings import Settings
from core.crash_handler import CrashHandler
from ui.main_window import MainWindow
import extensions  # registers extensions


def main():
    # Install crash handler BEFORE creating QApplication
    crash = CrashHandler()
    crash.install()
    
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon.fromTheme("wallpaper"))
    
    settings = Settings()
    window = MainWindow(settings)
    window.show()
    
    # Show previous crash dialog after window is shown
    crash.show_crash_dialog_if_needed(parent=window)
    
    exit_code = app.exec_()
    
    # Mark clean shutdown on normal exit
    crash.mark_clean_shutdown()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()