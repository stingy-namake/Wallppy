#!/usr/bin/env python3
"""
Wallhaven GUI - Modern, minimal wallpaper browser
Double-click any thumbnail to download.
Downloaded wallpapers show a checkmark.
"""

import sys
import os
import requests
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QLabel, QScrollArea, QGridLayout,
    QFrame, QMessageBox, QProgressBar, QSizePolicy
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt5.QtGui import QPixmap, QIcon, QPalette, QColor, QMouseEvent

# =============================================================================
# Configuration
# =============================================================================
API_URL = "https://wallhaven.cc/api/v1/search"
DOWNLOAD_FOLDER = "./wallpapers"
THUMB_SIZE = QSize(240, 135)  # 16:9
THUMB_PADDING = 12

if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

# =============================================================================
# Worker Threads
# =============================================================================
class SearchWorker(QThread):
    finished = pyqtSignal(list, int)
    error = pyqtSignal(str)

    def __init__(self, query, page=1, category="111", purity="100"):
        super().__init__()
        self.query = query
        self.page = page
        self.category = category
        self.purity = purity

    def run(self):
        params = {
            "q": self.query,
            "categories": self.category,
            "purity": self.purity,
            "page": self.page,
            "sorting": "date_added",
            "order": "desc"
        }
        try:
            response = requests.get(API_URL, params=params, timeout=15)
            if response.status_code != 200:
                self.error.emit(f"API error: {response.status_code}")
                return
            data = response.json()
            wallpapers = data.get("data", [])
            meta = data.get("meta", {})
            total_pages = meta.get("last_page", 1)
            self.finished.emit(wallpapers, total_pages)
        except Exception as e:
            self.error.emit(str(e))

class DownloadWorker(QThread):
    finished = pyqtSignal(bool, str, str)  # success, filepath, filename
    progress = pyqtSignal(int)

    def __init__(self, wallpaper_data):
        super().__init__()
        self.data = wallpaper_data

    def run(self):
        image_url = self.data.get("path")
        wall_id = self.data.get("id")
        file_type = self.data.get("file_type", "image/jpeg")
        if not image_url:
            self.finished.emit(False, "", "No image URL")
            return

        if "jpeg" in file_type or "jpg" in file_type:
            ext = "jpg"
        elif "png" in file_type:
            ext = "png"
        else:
            ext = "jpg"

        filename = f"wallhaven-{wall_id}.{ext}"
        filepath = os.path.join(DOWNLOAD_FOLDER, filename)

        if os.path.exists(filepath):
            self.finished.emit(True, filepath, filename)
            return

        try:
            response = requests.get(image_url, stream=True, timeout=30)
            response.raise_for_status()
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size:
                            self.progress.emit(int(downloaded * 100 / total_size))
            self.finished.emit(True, filepath, filename)
        except Exception as e:
            self.finished.emit(False, "", str(e))

class ThumbnailLoader(QThread):
    loaded = pyqtSignal(QPixmap)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        try:
            response = requests.get(self.url, timeout=10)
            if response.status_code == 200:
                pixmap = QPixmap()
                pixmap.loadFromData(response.content)
                self.loaded.emit(pixmap)
            else:
                self.loaded.emit(QPixmap())
        except:
            self.loaded.emit(QPixmap())

# =============================================================================
# Double‑Clickable Thumbnail Label (with checkmark overlay)
# =============================================================================
class DoubleClickableLabel(QLabel):
    double_clicked = pyqtSignal()

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.double_clicked.emit()
        super().mouseDoubleClickEvent(event)

# =============================================================================
# Wallpaper Item Widget (checkmark for downloaded)
# =============================================================================
class WallpaperWidget(QFrame):
    download_triggered = pyqtSignal(dict)

    def __init__(self, wallpaper_data, parent=None):
        super().__init__(parent)
        self.data = wallpaper_data
        self.thumb_url = wallpaper_data.get("thumbs", {}).get("large", "")
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet("""
            WallpaperWidget {
                background-color: #2d2d2d;
                border-radius: 8px;
            }
            WallpaperWidget:hover {
                background-color: #3d3d3d;
            }
        """)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.init_ui()
        self.load_thumbnail()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        # Double‑clickable thumbnail
        self.thumb_label = DoubleClickableLabel()
        self.thumb_label.setFixedSize(THUMB_SIZE)
        self.thumb_label.setAlignment(Qt.AlignCenter)
        self.thumb_label.setStyleSheet("""
            QLabel {
                background-color: #1e1e1e;
                border-radius: 6px;
            }
            QLabel:hover {
                border: 2px solid #0078d7;
            }
        """)
        self.thumb_label.setScaledContents(True)
        self.thumb_label.setCursor(Qt.PointingHandCursor)
        self.thumb_label.double_clicked.connect(self.emit_download)
        layout.addWidget(self.thumb_label)

        # Checkmark overlay (child of thumb_label)
        self.checkmark_label = QLabel(self.thumb_label)
        self.checkmark_label.setAlignment(Qt.AlignCenter)
        self.checkmark_label.setStyleSheet("""
            QLabel {
                background-color: rgba(0, 180, 0, 0.85);
                color: white;
                font-weight: bold;
                font-size: 14px;
                border-radius: 4px;
                padding: 2px 6px;
            }
        """)
        self.checkmark_label.setText("✓")
        self.checkmark_label.hide()
        self.checkmark_label.raise_()  # Ensure it's on top of the pixmap

        # Resolution label
        info_layout = QHBoxLayout()
        info_layout.setContentsMargins(0, 0, 0, 0)
        res = self.data.get("resolution", "?x?")
        self.res_label = QLabel(res)
        self.res_label.setStyleSheet("color: #aaa; font-size: 10px;")
        info_layout.addWidget(self.res_label)
        info_layout.addStretch()
        layout.addLayout(info_layout)

        self.setLayout(layout)
        self.setFixedSize(THUMB_SIZE.width() + 20, THUMB_SIZE.height() + 45)

    def showEvent(self, event):
        """Called when the widget is shown – position the checkmark and update status."""
        super().showEvent(event)
        self.position_checkmark()
        self.update_downloaded_status()

    def position_checkmark(self):
        """Place the checkmark at the bottom-right corner of the thumbnail."""
        if self.checkmark_label:
            label_width = self.checkmark_label.sizeHint().width()
            label_height = self.checkmark_label.sizeHint().height()
            margin = 4
            self.checkmark_label.move(
                THUMB_SIZE.width() - label_width - margin,
                THUMB_SIZE.height() - label_height - margin
            )

    def update_downloaded_status(self):
        """Check if file exists and show/hide checkmark."""
        wall_id = self.data.get("id")
        file_type = self.data.get("file_type", "image/jpeg")
        if "jpeg" in file_type or "jpg" in file_type:
            ext = "jpg"
        elif "png" in file_type:
            ext = "png"
        else:
            ext = "jpg"
        filename = f"wallhaven-{wall_id}.{ext}"
        filepath = os.path.join(DOWNLOAD_FOLDER, filename)
        if os.path.exists(filepath):
            self.checkmark_label.show()
            self.checkmark_label.raise_()  # Keep on top
        else:
            self.checkmark_label.hide()

    def load_thumbnail(self):
        if self.thumb_url:
            self.loader = ThumbnailLoader(self.thumb_url)
            self.loader.loaded.connect(self.set_thumbnail)
            self.loader.start()
        else:
            self.thumb_label.setText("No preview")

    def set_thumbnail(self, pixmap):
        if not pixmap.isNull():
            scaled = pixmap.scaled(THUMB_SIZE, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.thumb_label.setPixmap(scaled)
        else:
            self.thumb_label.setText("Load failed")
        # After setting the pixmap, ensure the checkmark is correctly positioned
        self.position_checkmark()
        self.update_downloaded_status()

    def emit_download(self):
        self.download_triggered.emit(self.data)
        
# =============================================================================
# Main Window
# =============================================================================
class WallhavenGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Wallhaven Browser")
        self.setMinimumSize(600, 400)
        self.resize(1100, 700)

        self.current_query = ""
        self.current_page = 1
        self.total_pages = 1
        self.wallpapers = []
        self.columns = 3
        self.workers = []

        self.init_ui()
        self.apply_dark_theme()
        self.scroll_area.viewport().installEventFilter(self)

    def eventFilter(self, obj, event):
        if obj == self.scroll_area.viewport() and event.type() == event.Resize:
            if self.update_columns_from_width() and self.wallpapers:
                self.update_grid()
        return super().eventFilter(obj, event)

    def update_columns_from_width(self):
        viewport_width = self.scroll_area.viewport().width()
        thumb_width_total = THUMB_SIZE.width() + 20 + THUMB_PADDING
        if thumb_width_total > 0:
            new_cols = max(1, viewport_width // thumb_width_total)
            if new_cols != self.columns:
                self.columns = new_cols
                return True
        return False

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)

        # Top Bar
        top_bar = QHBoxLayout()
        top_bar.setSpacing(10)

        search_layout = QHBoxLayout()
        search_layout.setSpacing(0)
        search_icon = QLabel()
        search_icon.setPixmap(QIcon.fromTheme("system-search").pixmap(16,16))
        search_layout.addWidget(search_icon)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search wallpapers...")
        self.search_edit.returnPressed.connect(self.perform_search)
        search_layout.addWidget(self.search_edit)
        top_bar.addLayout(search_layout, 3)

        self.search_btn = QPushButton("Search")
        self.search_btn.clicked.connect(self.perform_search)
        top_bar.addWidget(self.search_btn)

        top_bar.addStretch()

        self.prev_btn = QPushButton("◀")
        self.prev_btn.setToolTip("Previous page")
        self.prev_btn.clicked.connect(self.prev_page)
        self.prev_btn.setEnabled(False)
        top_bar.addWidget(self.prev_btn)

        self.page_label = QLabel("Page 0/0")
        top_bar.addWidget(self.page_label)

        self.next_btn = QPushButton("▶")
        self.next_btn.setToolTip("Next page")
        self.next_btn.clicked.connect(self.next_page)
        self.next_btn.setEnabled(False)
        top_bar.addWidget(self.next_btn)

        main_layout.addLayout(top_bar)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        main_layout.addWidget(self.progress)

        # Scroll Area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.grid_widget = QWidget()
        self.grid_layout = QGridLayout(self.grid_widget)
        self.grid_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.grid_layout.setSpacing(THUMB_PADDING)
        self.grid_layout.setContentsMargins(4, 4, 4, 4)

        self.scroll_area.setWidget(self.grid_widget)
        main_layout.addWidget(self.scroll_area)

        # Status bar with permanent tip
        self.statusBar().showMessage("Ready")
        tip_label = QLabel("🖱️ Double‑click thumbnail to download")
        tip_label.setStyleSheet("color: #aaa; padding-right: 8px;")
        self.statusBar().addPermanentWidget(tip_label)

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
        dark_palette.setColor(QPalette.Highlight, QColor(0, 120, 215))
        dark_palette.setColor(QPalette.HighlightedText, Qt.white)
        QApplication.setPalette(dark_palette)

        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e1e;
            }
            QLineEdit, QPushButton, QSlider, QScrollArea {
                background-color: #2d2d2d;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 6px;
                color: white;
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
                color: #ccc;
            }
        """)

    def perform_search(self):
        query = self.search_edit.text().strip()
        if not query:
            QMessageBox.information(self, "Info", "Please enter a search term.")
            return
        self.current_query = query
        self.current_page = 1
        self.start_search()

    def start_search(self):
        self.statusBar().showMessage(f"Searching for '{self.current_query}'...")
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        self.prev_btn.setEnabled(False)
        self.next_btn.setEnabled(False)

        self.worker = SearchWorker(self.current_query, self.current_page)
        self.worker.finished.connect(self.on_search_finished)
        self.worker.error.connect(self.on_search_error)
        self.worker.start()
        self.workers.append(self.worker)

    def on_search_finished(self, wallpapers, total_pages):
        self.progress.setVisible(False)
        self.wallpapers = wallpapers
        self.total_pages = total_pages
        self.update_columns_from_width()
        self.update_grid()
        self.update_pagination()
        self.statusBar().showMessage(f"Found {len(wallpapers)} wallpapers (page {self.current_page}/{total_pages})")

    def on_search_error(self, error_msg):
        self.progress.setVisible(False)
        QMessageBox.critical(self, "Search Error", error_msg)
        self.statusBar().showMessage("Search failed")

    def update_grid(self):
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self.wallpapers:
            return

        for i, wp in enumerate(self.wallpapers):
            row = i // self.columns
            col = i % self.columns
            widget = WallpaperWidget(wp)
            widget.download_triggered.connect(self.download_wallpaper)
            self.grid_layout.addWidget(widget, row, col)

        row_count = (len(self.wallpapers) - 1) // self.columns + 1
        self.grid_layout.setRowStretch(row_count, 1)

    def update_pagination(self):
        self.page_label.setText(f"Page {self.current_page}/{self.total_pages}")
        self.prev_btn.setEnabled(self.current_page > 1)
        self.next_btn.setEnabled(self.current_page < self.total_pages)

    def prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.start_search()

    def next_page(self):
        if self.current_page < self.total_pages:
            self.current_page += 1
            self.start_search()

    def download_wallpaper(self, wallpaper_data):
        self.statusBar().showMessage("Downloading...")
        self.progress.setVisible(True)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)

        self.dl_worker = DownloadWorker(wallpaper_data)
        self.dl_worker.finished.connect(self.on_download_finished)
        self.dl_worker.progress.connect(self.progress.setValue)
        self.dl_worker.start()
        self.workers.append(self.dl_worker)

    def on_download_finished(self, success, filepath, filename):
        self.progress.setVisible(False)
        if success:
            timestamp = datetime.now().strftime("%H:%M:%S")
            msg = f"✅ Downloaded: {filename}  →  {DOWNLOAD_FOLDER}  ({timestamp})"
            self.statusBar().showMessage(msg)
            # If we wanted to update checkmarks live, we could iterate over widgets,
            # but the simplest is to let the user see it on next search/navigation.
        else:
            self.statusBar().showMessage(f"❌ Download failed: {filename}")

# =============================================================================
# Entry Point
# =============================================================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon.fromTheme("wallpaper"))
    window = WallhavenGUI()
    window.show()
    sys.exit(app.exec_())