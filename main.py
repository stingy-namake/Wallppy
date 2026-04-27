#!/usr/bin/env python3

import os
import sys
import subprocess
import ssl

def is_gnome_wayland():
    """Detect if running on GNOME Wayland using multiple methods"""
    
    # Method 1: Environment variables

    session_type = os.environ.get('XDG_SESSION_TYPE', '')
    desktop = os.environ.get('XDG_CURRENT_DESKTOP', '')
    
    if session_type == 'wayland' and desktop == 'GNOME':
        return True
    
    # Method 2: Check if we can detect GNOME Wayland via loginctl
    try:
        result = subprocess.run(['loginctl', 'show-session', 'self', '-p', 'Type'], 
                              capture_output=True, text=True)
        if 'Type=wayland' in result.stdout:
            # Now check if GNOME
            desktop_result = subprocess.run(['echo', '$XDG_CURRENT_DESKTOP'], 
                                          shell=True, capture_output=True, text=True)
            if 'GNOME' in os.environ.get('XDG_CURRENT_DESKTOP', ''):
                return True
    except:
        pass
    
    # Method 3: Check for GNOME-specific Wayland compositor
    if os.environ.get('WAYLAND_DISPLAY') and 'gnome' in os.environ.get('DESKTOP_SESSION', '').lower():
        return True
    
    return False

def debug_ssl():
    import ssl
    import requests
    try:
        import certifi
        cert_path = certifi.where()
    except:
        cert_path = "not found"
    
    debug = f"""Wallppy Debug
Python: {sys.version}
OpenSSL: {ssl.OPENSSL_VERSION}
Certifi: {cert_path}
Requests: {requests.__version__}
Frozen: {getattr(sys, 'frozen', False)}
"""
    
    # Write to config dir
    config_dir = os.path.expanduser("~/.config/wallppy")
    os.makedirs(config_dir, exist_ok=True)
    with open(os.path.join(config_dir, "debug.log"), "w") as f:
        f.write(debug)

# Apply fix before Qt loads
if sys.platform.startswith('linux'):
    if is_gnome_wayland():
        os.environ['QT_QPA_PLATFORM'] = 'xcb'
        # Also set these for better compatibility
        os.environ['QT_AUTO_SCREEN_SCALE_FACTOR'] = '0'
        os.environ['QT_SCALE_FACTOR'] = '1'

# Now import Qt
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
    app.setApplicationName("Wallppy")    
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
    debug_ssl()
    main()