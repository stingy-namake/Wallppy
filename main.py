#!/usr/bin/env python3

import os
import sys

# Detect and fix GNOME Wayland crash before Qt loads
if sys.platform.startswith('linux'):
    # Check if we're on GNOME Wayland
    session_type = os.environ.get('XDG_SESSION_TYPE', '')
    desktop = os.environ.get('XDG_CURRENT_DESKTOP', '')
    
    if session_type == 'wayland' and desktop == 'GNOME':
        # Force X11 only on GNOME Wayland to prevent Qt crashes
        os.environ['QT_QPA_PLATFORM'] = 'xcb'

from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QIcon
from core.settings import Settings
from core.crash_handler import CrashHandler
from ui.main_window import MainWindow
import extensions  # registers extensions

def resource_path(relative_path):
    """Get absolute path to resource, works for dev and PyInstaller"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    
    return os.path.join(base_path, relative_path)

def main():
    # Install crash handler BEFORE creating QApplication
    crash = CrashHandler()
    crash.install()
    
    app = QApplication(sys.argv)
    
    # Set window icon
    app_icon = QIcon(resource_path(".resources/wallppy.png"))
    app.setWindowIcon(app_icon)
    
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