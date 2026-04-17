from datetime import datetime
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QStackedWidget,
    QProgressBar, QLabel, QApplication, QStatusBar
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPalette, QColor, QIcon

from core.extension import create_extension, get_extension_names
from core.settings import Settings
from .landing_page import LandingPage
from .results_page import ResultsPage


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
        
        self.init_ui()
        self.apply_dark_theme()
        self.setup_status_bar()
    
    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        self.stacked = QStackedWidget()
        layout.addWidget(self.stacked)
        
        # Landing page
        self.landing_page = LandingPage(self.settings)
        self.landing_page.search_requested.connect(self.on_search_requested)
        self.landing_page.explore_requested.connect(self.on_explore_requested)
        self.landing_page.extension_changed.connect(self.on_extension_changed)
        self.stacked.addWidget(self.landing_page)
        
        # Results page
        self.results_page = ResultsPage(self.extension, self.settings)
        self.results_page.home_requested.connect(self.go_home)
        self.results_page.search_requested.connect(self.on_search_requested)
        self.results_page.download_progress.connect(self.update_download_progress)
        self.results_page.download_finished.connect(self.on_download_finished)
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
        """Switch to a different extension."""
        new_ext = create_extension(name)
        if new_ext:
            self.extension = new_ext
            self.results_page.update_extension(new_ext)
    
    def setup_status_bar(self):
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("Ready")
        
        # ===== MODERN SLEEK DOWNLOAD PROGRESS =====
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
        
        tip_label = QLabel("🖱️ Double‑click thumbnail to download")
        tip_label.setStyleSheet("color: #666; padding-right: 10px; font-size: 11px; letter-spacing: 0.3px;")
        self.status_bar.addPermanentWidget(tip_label)
    
    def apply_dark_theme(self):
        dark_palette = QPalette()
        dark_palette.setColor(QPalette.Window, QColor(30, 30, 30))
        dark_palette.setColor(QPalette.WindowText, Qt.white)
        dark_palette.setColor(QPalette.Base, QColor(45, 45, 45))
        dark_palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.ToolTipBase, Qt.white)
        dark_palette.setColor(QPalette.ToolTipText, Qt.white)
        dark_palette.setColor(QPalette.Text, Qt.white)
        dark_palette.setColor(QPalette.Button, QColor(60, 60, 60))
        dark_palette.setColor(QPalette.ButtonText, Qt.white)
        dark_palette.setColor(QPalette.BrightText, Qt.red)
        dark_palette.setColor(QPalette.Highlight, QColor(30, 111, 240))
        dark_palette.setColor(QPalette.HighlightedText, Qt.white)
        QApplication.setPalette(dark_palette)
        
        self.setStyleSheet("""
            * {
                font-family: 'SF Mono', 'Menlo', 'Consolas', 'Cascadia Mono', 'Fira Code', 'Courier New', monospace;
            }
            QMainWindow {
                background-color: #1e1e1e;
            }
            QLineEdit, QPushButton, QScrollArea, QCheckBox, QComboBox {
                background-color: #2d2d2d;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 6px;
                color: white;
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
                width: 15px;
                height: 15px;
                border: 1px solid #555;
                border-radius: 3px;
                background-color: #2d2d2d;
            }
            QCheckBox::indicator:checked {
                background-color: #1E6FF0;
                border-color: #1E6FF0;
            }
            QPushButton:hover {
                background-color: #3d3d3d;
            }
            QPushButton:pressed {
                background-color: #1e1e1e;
            }
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollBar:vertical {
                background: #2d2d2d;
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
                background-color: #2d2d2d;
                color: #888;
                font-size: 11px;
            }
            QStatusBar::item {
                border: none;
            }
        """)
    
    def on_search_requested(self, query: str):
        self.results_page.start_search(query)
        self.stacked.setCurrentIndex(1)

    def on_explore_requested(self):
        """Handle explore action: search with empty query."""
        self.results_page.start_search("")
        self.stacked.setCurrentIndex(1)
    
    def go_home(self):
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