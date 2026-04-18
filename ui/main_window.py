from datetime import datetime
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QStackedWidget,
    QProgressBar, QLabel, QApplication, QStatusBar
)
from PyQt5.QtCore import Qt, QPropertyAnimation, QEasingCurve, QTimer
from PyQt5.QtGui import QPalette, QColor

from core.extension import create_extension, get_extension_names
from core.settings import Settings
from .landing_page import LandingPage
from .results_page import ResultsPage


class FadeStackedWidget(QStackedWidget):
    """Stacked widget with a simple cross-fade animation."""
    def setCurrentIndex(self, index):
        if self.currentIndex() == index:
            return
        current_widget = self.currentWidget()
        next_widget = self.widget(index)
        if current_widget and next_widget:
            self.fade_out = QPropertyAnimation(current_widget, b"windowOpacity")
            self.fade_out.setDuration(150)
            self.fade_out.setStartValue(1.0)
            self.fade_out.setEndValue(0.0)
            self.fade_out.setEasingCurve(QEasingCurve.OutCubic)
            self.fade_out.finished.connect(lambda: self._finish_switch(index, next_widget))
            self.fade_out.start()
        else:
            super().setCurrentIndex(index)

    def _finish_switch(self, index, next_widget):
        super().setCurrentIndex(index)
        self.fade_in = QPropertyAnimation(next_widget, b"windowOpacity")
        self.fade_in.setDuration(150)
        self.fade_in.setStartValue(0.0)
        self.fade_in.setEndValue(1.0)
        self.fade_in.setEasingCurve(QEasingCurve.OutCubic)
        self.fade_in.start()


class MainWindow(QMainWindow):
    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings
        self.extension = create_extension(settings.extension_name)
        if self.extension is None:
            fallback_name = get_extension_names()[0] if get_extension_names() else None
            if fallback_name:
                self.extension = create_extension(fallback_name)
                self.settings.set_extension(fallback_name)
        self.setWindowTitle("wallppy")
        self.setMinimumSize(682, 500)
        self.resize(1100, 700)

        # Track custom status label
        self._status_label = None
        self._clear_timer = None

        self.init_ui()
        self.apply_dark_theme()
        self.setup_status_bar()

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.stacked = FadeStackedWidget()
        layout.addWidget(self.stacked)

        # Landing page
        self.landing_page = LandingPage(self.settings)
        self.landing_page.search_requested.connect(self.on_search_requested)
        self.landing_page.explore_requested.connect(self.on_explore_requested)
        self.landing_page.extension_changed.connect(self.on_extension_changed)
        self.landing_page.status_message.connect(self.on_status_message)
        self.stacked.addWidget(self.landing_page)

        # Results page
        self.results_page = ResultsPage(self.extension, self.settings)
        self.results_page.home_requested.connect(self.go_home)
        self.results_page.search_requested.connect(self.on_search_requested)
        self.results_page.download_progress.connect(self.update_download_progress)
        self.results_page.download_finished.connect(self.on_download_finished)
        self.results_page.search_finished.connect(self._clear_highlighted_status)
        self.stacked.addWidget(self.results_page)

        self.stacked.setCurrentIndex(0)

    def keyPressEvent(self, event):
        if (self.stacked.currentIndex() == 0 and
            event.key() == Qt.Key_Return and
            event.modifiers() == Qt.NoModifier):
            self.landing_page.emit_search()
        else:
            super().keyPressEvent(event)

    def on_extension_changed(self, name: str):
        new_ext = create_extension(name)
        if new_ext:
            self.extension = new_ext
            self.results_page.update_extension(new_ext)

    def setup_status_bar(self):
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("Ready")

        self.download_progress = QProgressBar()
        self.download_progress.setFixedWidth(140)
        self.download_progress.setFixedHeight(4)
        self.download_progress.setRange(0, 100)
        self.download_progress.setValue(0)
        self.download_progress.setVisible(False)
        self.download_progress.setTextVisible(False)
        self.download_progress.setStyleSheet("""
            QProgressBar {
                background-color: #1e1e1e;
                border: none;
                border-radius: 2px;
                max-height: 4px;
                min-height: 4px;
            }
            QProgressBar::chunk {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #1E6FF0, stop:1 #00c6ff);
                border-radius: 2px;
            }
        """)
        self.status_bar.addPermanentWidget(self.download_progress)

        tip_label = QLabel("🖱️ Double‑click thumbnail to download  •  Click 🖵 to set as wallpaper")
        tip_label.setStyleSheet("color: #777; padding-right: 10px; font-size: 11px;")
        self.status_bar.addPermanentWidget(tip_label)

    def on_status_message(self, message: str):
        """Display a highlighted status message (for scanning) or normal message."""
        if "Scanning" in message:
            self._set_highlighted_status(message)
        else:
            self._clear_highlighted_status()
            self.status_bar.showMessage(message)

    def _set_highlighted_status(self, message: str):
        """Insert a rich-text label on the left side of the status bar."""
        # Cancel any pending clear
        if self._clear_timer is not None:
            self._clear_timer.stop()
            self._clear_timer = None

        self._clear_highlighted_status()  # Remove any existing one

        self._status_label = QLabel(f"<font color='#1E6FF0'>⟳ {message}</font>")
        self._status_label.setTextFormat(Qt.RichText)
        self._status_label.setStyleSheet("padding: 2px 8px;")
        self.status_bar.addWidget(self._status_label)

        # Clear the normal status message so it doesn't overlap
        self.status_bar.showMessage("")

        self._status_label.show()
        self.status_bar.repaint()


    def _clear_highlighted_status(self):
        """Remove the temporary status label and restore normal message."""
        if self._clear_timer is not None:
            self._clear_timer.stop()
            self._clear_timer = None

        if self._status_label is not None:
            self.status_bar.removeWidget(self._status_label)
            self._status_label.deleteLater()
            self._status_label = None

        # Restore default message only if nothing else is showing
        if self.status_bar.currentMessage() == "":
            self.status_bar.showMessage("Ready")

    def apply_dark_theme(self):
        dark_palette = QPalette()
        dark_palette.setColor(QPalette.Window, QColor(25, 25, 28))
        dark_palette.setColor(QPalette.WindowText, Qt.white)
        dark_palette.setColor(QPalette.Base, QColor(35, 35, 40))
        dark_palette.setColor(QPalette.AlternateBase, QColor(45, 45, 50))
        dark_palette.setColor(QPalette.ToolTipBase, Qt.white)
        dark_palette.setColor(QPalette.ToolTipText, Qt.white)
        dark_palette.setColor(QPalette.Text, Qt.white)
        dark_palette.setColor(QPalette.Button, QColor(50, 50, 55))
        dark_palette.setColor(QPalette.ButtonText, Qt.white)
        dark_palette.setColor(QPalette.BrightText, Qt.red)
        dark_palette.setColor(QPalette.Highlight, QColor(30, 111, 240))
        dark_palette.setColor(QPalette.HighlightedText, Qt.white)
        QApplication.setPalette(dark_palette)

        self.setStyleSheet("""
            * {
                font-family: 'Segoe UI', 'SF Pro Text', 'Helvetica Neue', sans-serif;
            }
            QMainWindow {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #1a1a1e, stop:1 #121214);
            }
            QLineEdit, QPushButton, QScrollArea, QCheckBox, QComboBox {
                background-color: #2a2a2f;
                border: 1px solid #3a3a40;
                border-radius: 6px;
                padding: 6px;
                color: white;
            }
            QLineEdit:focus {
                border: 1px solid #1E6FF0;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #aaa;
                margin-right: 5px;
            }
            QCheckBox {
                border: none;
                background: transparent;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 1px solid #555;
                border-radius: 4px;
                background-color: #2a2a2f;
            }
            QCheckBox::indicator:checked {
                background-color: #1E6FF0;
                border-color: #1E6FF0;
            }
            QPushButton:hover {
                background-color: #3a3a40;
            }
            QPushButton:pressed {
                background-color: #1e1e22;
            }
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollBar:vertical {
                background: #2a2a2f;
                width: 10px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background: #555;
                border-radius: 5px;
                min-height: 20px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                border: none;
                background: none;
            }
            QStatusBar {
                background-color: #1e1e22;
                color: #999;
                font-size: 11px;
            }
            QStatusBar::item {
                border: none;
            }
            QToolTip {
                background-color: #2a2a2f;
                color: white;
                border: 1px solid #3a3a40;
                border-radius: 4px;
                padding: 4px 8px;
            }
        """)

    def on_search_requested(self, query: str):
        self._clear_highlighted_status()
        self.results_page.start_search(query)
        self.stacked.setCurrentIndex(1)

    def on_explore_requested(self):
        # Keep scanning message; it will be cleared by search_finished
        self.results_page.start_search("")
        self.stacked.setCurrentIndex(1)

    def go_home(self):
        self._clear_highlighted_status()
        self.landing_page.set_search_text(self.results_page.search_edit.text())
        self.stacked.setCurrentIndex(0)

    def update_download_progress(self, value):
        self.download_progress.setVisible(True)
        self.download_progress.setValue(value)

    def on_download_finished(self, success, filepath, filename, wall_id):
        self.download_progress.setVisible(False)
        if success:
            timestamp = datetime.now().strftime("%H:%M:%S")
            msg = f"Downloaded: {filename}  →  {self.settings.download_folder}  ({timestamp})"
            self.status_bar.showMessage(msg)
        else:
            self.status_bar.showMessage(f"Download failed: {filename}")

    def closeEvent(self, event):
        if hasattr(self.extension, 'shutdown'):
            self.extension.shutdown()
        event.accept()