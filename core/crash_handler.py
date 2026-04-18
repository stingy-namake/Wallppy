import sys
import os
import traceback
import logging
import datetime
import threading
from pathlib import Path
from typing import Callable, Optional

from PyQt5.QtCore import Qt, qInstallMessageHandler
from PyQt5.QtWidgets import QMessageBox, QApplication


# Qt message type integer constants (stable across all Qt5 versions)
QT_DEBUG_MSG = 0
QT_WARNING_MSG = 1
QT_CRITICAL_MSG = 2
QT_FATAL_MSG = 3
QT_INFO_MSG = 4


class CrashHandler:
    """Global crash logger for wallppy. Hooks into Python and Qt exception handlers."""
    
    def __init__(self, app_name: str = "wallppy"):
        self.app_name = app_name
        self.config_dir = Path.home() / ".config" / app_name
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.config_dir / "crash.log"
        self.session_count_path = self.config_dir / ".session_count"
        
        # Setup Python file logger
        self.logger = logging.getLogger("wallppy.crash")
        self.logger.setLevel(logging.DEBUG)
        
        # Prevent duplicate handlers if re-initialized
        if not self.logger.handlers:
            file_handler = logging.FileHandler(self.log_path, mode='a', encoding='utf-8')
            file_handler.setLevel(logging.DEBUG)
            formatter = logging.Formatter(
                '[%(asctime)s] [%(levelname)s]\n%(message)s\n',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
        
        self._original_excepthook = sys.excepthook
        self._original_unraisablehook = getattr(sys, 'unraisablehook', None)
        self._original_threading_excepthook = getattr(threading, 'excepthook', None)
        
        # Track if we had a crash on previous run
        self.previous_crash = self._check_previous_crash()
        self.session_count = self._read_session_count()
    
    def install(self):
        """Install global exception hooks."""
        sys.excepthook = self._handle_exception
        
        if hasattr(sys, 'unraisablehook'):
            sys.unraisablehook = self._handle_unraisable
        
        if hasattr(threading, 'excepthook'):
            threading.excepthook = self._handle_thread_exception
        
        # Hook Qt's internal message handler
        qInstallMessageHandler(self._qt_message_handler)
        
        self._log_header("Session started")
    
    def uninstall(self):
        """Restore original hooks (mainly for testing)."""
        sys.excepthook = self._original_excepthook
        if self._original_unraisablehook:
            sys.unraisablehook = self._original_unraisablehook
        if self._original_threading_excepthook:
            threading.excepthook = self._original_threading_excepthook
        qInstallMessageHandler(None)
    
    def _read_session_count(self) -> int:
        """Read the number of consecutive clean sessions."""
        try:
            if self.session_count_path.exists():
                return int(self.session_count_path.read_text().strip())
        except Exception:
            pass
        return 0
    
    def _write_session_count(self, count: int):
        """Write the session count to file."""
        try:
            self.session_count_path.write_text(str(count))
        except Exception:
            pass
    
    def _clear_log(self):
        """Clear the crash log file."""
        try:
            if self.log_path.exists():
                self.log_path.unlink()
            # Reopen the file handler (new empty file)
            for handler in self.logger.handlers[:]:
                handler.close()
                self.logger.removeHandler(handler)
            file_handler = logging.FileHandler(self.log_path, mode='a', encoding='utf-8')
            file_handler.setLevel(logging.DEBUG)
            formatter = logging.Formatter(
                '[%(asctime)s] [%(levelname)s]\n%(message)s\n',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
        except Exception:
            pass
    
    def _check_previous_crash(self) -> bool:
        """Check if previous session ended without a clean shutdown marker."""
        marker = self.config_dir / ".clean_shutdown"
        had_crash = False
        if marker.exists():
            marker.unlink()
        else:
            # If log exists and has content, assume crash
            if self.log_path.exists() and self.log_path.stat().st_size > 0:
                had_crash = True
        return had_crash
    
    def mark_clean_shutdown(self):
        """Call this on normal exit to suppress the crash dialog next run."""
        marker = self.config_dir / ".clean_shutdown"
        marker.write_text(datetime.datetime.now().isoformat())
        
        # Increment session count on clean shutdown
        new_count = self.session_count + 1
        if new_count >= 5:
            self._clear_log()
            new_count = 0
        self._write_session_count(new_count)
        self.session_count = new_count
    
    def _log_header(self, text: str):
        """Write a visual separator to the log."""
        border = "=" * 60
        self.logger.info(f"\n{border}\n{text}\n{border}")
    
    def _handle_exception(self, exc_type, exc_value, exc_tb):
        """Handle uncaught exceptions in the main thread."""
        self._log_crash("UNCAUGHT EXCEPTION", exc_type, exc_value, exc_tb)
        self._original_excepthook(exc_type, exc_value, exc_tb)
    
    def _handle_thread_exception(self, args):
        """Handle uncaught exceptions in threads (Python 3.8+)."""
        self._log_crash(
            f"THREAD EXCEPTION (thread: {args.thread.name})",
            args.exc_type,
            args.exc_value,
            args.exc_traceback
        )
        # Call original if available
        if self._original_threading_excepthook:
            self._original_threading_excepthook(args)
    
    def _handle_unraisable(self, args):
        """Handle unraisable exceptions (e.g. __del__ failures)."""
        msg = f"UNRAISABLE EXCEPTION: {args.err_msg or 'Unraisable exception'}"
        tb_str = ''.join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback))
        self.logger.error(f"{msg}\nObject: {args.object}\n{tb_str}")
        if self._original_unraisablehook:
            self._original_unraisablehook(args)
    
    def _qt_message_handler(self, mode, context, message):
        """Capture Qt warnings, criticals, and fatals."""
        if mode == QT_DEBUG_MSG:
            level = "QT_DEBUG"
        elif mode == QT_WARNING_MSG:
            level = "QT_WARNING"
        elif mode == QT_CRITICAL_MSG:
            level = "QT_CRITICAL"
        elif mode == QT_FATAL_MSG:
            level = "QT_FATAL"
        elif mode == QT_INFO_MSG:
            level = "QT_INFO"
        else:
            level = "QT_UNKNOWN"
        
        log_line = f"[{level}] {message}"
        if hasattr(context, 'file') and context.file:
            log_line += f"\n  File: {context.file}:{context.line}"
        if hasattr(context, 'function') and context.function:
            log_line += f"\n  Function: {context.function}"
        
        if mode == QT_FATAL_MSG:
            self.logger.critical(log_line + "\nStack trace:\n" + traceback.format_exc())
        elif mode == QT_CRITICAL_MSG:
            self.logger.error(log_line)
        elif mode == QT_WARNING_MSG:
            self.logger.warning(log_line)
        else:
            self.logger.debug(log_line)
    
    def _log_crash(self, header: str, exc_type, exc_value, exc_tb):
        """Format and write a crash entry."""
        timestamp = datetime.datetime.now().isoformat()
        tb_str = ''.join(traceback.format_exception(exc_type, exc_value, exc_tb))
        
        entry = f"""{header}
Timestamp: {timestamp}
Exception: {exc_type.__name__}: {exc_value}
Traceback:
{tb_str}"""
        self.logger.critical(entry)
        
        # Ensure flush to disk
        for handler in self.logger.handlers:
            handler.flush()
    
    def show_crash_dialog_if_needed(self, parent=None):
        """Show a non-blocking dialog about the previous crash."""
        if not self.previous_crash or not self.log_path.exists():
            return
        
        try:
            log_size = self.log_path.stat().st_size
            if log_size > 50_000:
                size_kb = log_size // 1024
                msg = (f"<b>wallppy crashed during the previous session.</b><br><br>"
                       f"The crash log is {size_kb} KB.<br>"
                       f"<code>{self.log_path}</code>")
            else:
                msg = (f"<b>wallppy crashed during the previous session.</b><br><br>"
                       f"View the log at:<br>"
                       f"<code>{self.log_path}</code>")
            
            box = QMessageBox(parent)
            box.setWindowTitle("Previous Crash Detected")
            box.setTextFormat(Qt.RichText)
            box.setText(msg)
            box.setStandardButtons(QMessageBox.Ok | QMessageBox.Open)
            box.button(QMessageBox.Open).setText("Open Log Folder")
            
            if box.exec_() == QMessageBox.Open:
                import subprocess
                import platform
                path = str(self.config_dir)
                system = platform.system()
                if system == "Windows":
                    subprocess.Popen(["explorer", path])
                elif system == "Darwin":
                    subprocess.Popen(["open", path])
                else:
                    subprocess.Popen(["xdg-open", path])
        except Exception:
            # Never let the crash handler itself crash
            pass