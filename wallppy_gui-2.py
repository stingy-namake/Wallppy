#!/usr/bin/env python3
"""
Wallhaven GUI - Modern, minimal wallpaper browser with infinite scrolling.
Double-click any thumbnail to download.
Downloaded wallpapers show a green checkmark.
"""

import sys
import os
import requests
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QLabel, QScrollArea, QGridLayout,
    QFrame, QMessageBox, QProgressBar, QSizePolicy, QStatusBar,
    QStackedWidget
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt5.QtGui import QPixmap, QIcon, QPalette, QColor, QMouseEvent

# =============================================================================
# Configuration
# =============================================================================
API_URL = "https://wallhaven.cc/api/v1/search"
DOWNLOAD_FOLDER = "./wallpapers"
THUMB_SIZE = QSize(280, 158)  # 16:9, ~15% larger than before
THUMB_PADDING = 12

if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

# =============================================================================
# Worker Threads
# =============================================================================
class SearchWorker(QThread):
    finished = pyqtSignal(list, int, int)  # wallpapers, page, total_pages
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
            self.finished.emit(wallpapers, self.page, total_pages)
        except Exception as e:
            self.error.emit(str(e))

class DownloadWorker(QThread):
    finished = pyqtSignal(bool, str, str, str)  # success, filepath, filename, wall_id
    progress = pyqtSignal(int)

    def __init__(self, wallpaper_data):
        super().__init__()
        self.data = wallpaper_data

    def run(self):
        image_url = self.data.get("path")
        wall_id = self.data.get("id")
        file_type = self.data.get("file_type", "image/jpeg")
        if not image_url:
            self.finished.emit(False, "", "No image URL", wall_id)
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
            self.finished.emit(True, filepath, filename, wall_id)
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
            self.finished.emit(True, filepath, filename, wall_id)
        except Exception as e:
            self.finished.emit(False, "", str(e), wall_id)

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
# Double‑Clickable Thumbnail Label
# =============================================================================
class DoubleClickableLabel(QLabel):
    double_clicked = pyqtSignal()

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.double_clicked.emit()
        super().mouseDoubleClickEvent(event)

# =============================================================================
# Wallpaper Item Widget
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

        # Checkmark overlay
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
        self.checkmark_label.raise_()

        # Resolution
        info_layout = QHBoxLayout()
        info_layout.setContentsMargins(0, 0, 0, 0)
        res = self.data.get("resolution", "?x?")
        self.res_label = QLabel(res)
        self.res_label.setStyleSheet("color: #aaa; font-size: 10px;")
        info_layout.addWidget(self.res_label)
        info_layout.addStretch()
        layout.addLayout(info_layout)

        self.setLayout(layout)
        # Adjust widget size to accommodate larger thumbnail
        self.setFixedSize(THUMB_SIZE.width() + 20, THUMB_SIZE.height() + 45)

    def showEvent(self, event):
        super().showEvent(event)
        self.position_checkmark()
        self.update_downloaded_status()

    def position_checkmark(self):
        if self.checkmark_label:
            label_width = self.checkmark_label.sizeHint().width()
            label_height = self.checkmark_label.sizeHint().height()
            margin = 4
            self.checkmark_label.move(
                THUMB_SIZE.width() - label_width - margin,
                THUMB_SIZE.height() - label_height - margin
            )

    def update_downloaded_status(self):
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
            self.checkmark_label.raise_()
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
        self.position_checkmark()
        self.update_downloaded_status()

    def emit_download(self):
        self.download_triggered.emit(self.data)

# =============================================================================
# Main Window with Stacked Layout (Landing Page + Results)
# =============================================================================
class WallhavenGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Wallhaven Browser")
        self.setMinimumSize(600, 400)
        self.resize(1100, 700)

        # State
        self.current_query = ""
        self.current_page = 1
        self.total_pages = 1
        self.wallpapers = []
        self.columns = 3
        self.workers = []
        self.is_loading = False

        self.init_ui()
        self.apply_dark_theme()
        self.setup_status_bar()

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Stacked widget to switch between landing page and results
        self.stacked = QStackedWidget()
        main_layout.addWidget(self.stacked)

        # ===== Page 0: Landing page (centered search) =====
        self.landing_page = QWidget()
        landing_layout = QVBoxLayout(self.landing_page)
        landing_layout.setAlignment(Qt.AlignCenter)
        landing_layout.setSpacing(20)

        # Large search container
        search_container = QWidget()
        search_container.setFixedWidth(500)
        container_layout = QVBoxLayout(search_container)
        container_layout.setSpacing(10)

        # App title / logo
        title = QLabel("Wallhaven")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 36px; font-weight: bold; color: #0078d7;")
        container_layout.addWidget(title)

        # Search input (larger)
        self.landing_search_edit = QLineEdit()
        self.landing_search_edit.setPlaceholderText("Search wallpapers...")
        self.landing_search_edit.setMinimumHeight(50)
        self.landing_search_edit.setStyleSheet("""
            QLineEdit {
                font-size: 16px;
                padding: 12px;
                border-radius: 25px;
                background-color: #2d2d2d;
                border: 1px solid #3d3d3d;
                color: white;
            }
            QLineEdit:focus {
                border: 1px solid #0078d7;
            }
        """)
        self.landing_search_edit.returnPressed.connect(self.perform_search_from_landing)
        container_layout.addWidget(self.landing_search_edit)

        # Subtle hint (replaces the Search button)
        hint = QLabel("Press Enter to search")
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet("color: #777; font-size: 12px; margin-top: 5px;")
        container_layout.addWidget(hint)

        landing_layout.addWidget(search_container)
        self.stacked.addWidget(self.landing_page)

        # ===== Page 1: Results page (with top search bar and grid) =====
        self.results_page = QWidget()
        results_layout = QVBoxLayout(self.results_page)
        results_layout.setContentsMargins(12, 12, 12, 12)
        results_layout.setSpacing(12)

        # Top bar (compact search)
        top_bar = QHBoxLayout()
        top_bar.setSpacing(10)

        search_layout = QHBoxLayout()
        search_layout.setSpacing(0)
        search_icon = QLabel()
        search_icon.setPixmap(QIcon.fromTheme("system-search").pixmap(16,16))
        search_layout.addWidget(search_icon)
        self.results_search_edit = QLineEdit()
        self.results_search_edit.setPlaceholderText("Search wallpapers...")
        self.results_search_edit.returnPressed.connect(self.perform_search_from_results)
        search_layout.addWidget(self.results_search_edit)
        top_bar.addLayout(search_layout, 3)

        self.results_search_btn = QPushButton("Search")
        self.results_search_btn.clicked.connect(self.perform_search_from_results)
        top_bar.addWidget(self.results_search_btn)

        top_bar.addStretch()
        results_layout.addLayout(top_bar)

        # Scroll Area for grid
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
        results_layout.addWidget(self.scroll_area)

        # Loading indicator for infinite scroll
        self.loading_progress = QProgressBar()
        self.loading_progress.setVisible(False)
        self.loading_progress.setRange(0, 0)
        results_layout.addWidget(self.loading_progress)

        self.stacked.addWidget(self.results_page)

        # Start on landing page
        self.stacked.setCurrentIndex(0)

        # Install event filter for resize on scroll area viewport
        self.scroll_area.viewport().installEventFilter(self)
        self.scroll_area.verticalScrollBar().valueChanged.connect(self.on_scroll)

    def setup_status_bar(self):
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("Ready")

        # Tiny download progress bar
        self.download_progress = QProgressBar()
        self.download_progress.setFixedWidth(120)
        self.download_progress.setFixedHeight(12)
        self.download_progress.setRange(0, 100)
        self.download_progress.setValue(0)
        self.download_progress.setVisible(False)
        self.download_progress.setStyleSheet("""
            QProgressBar {
                border: 1px solid #555;
                border-radius: 2px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #0078d7;
                border-radius: 2px;
            }
        """)
        self.status_bar.addPermanentWidget(self.download_progress)

        tip_label = QLabel("🖱️ Double‑click thumbnail to download")
        tip_label.setStyleSheet("color: #aaa; padding-right: 8px;")
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
        dark_palette.setColor(QPalette.Highlight, QColor(0, 120, 215))
        dark_palette.setColor(QPalette.HighlightedText, Qt.white)
        QApplication.setPalette(dark_palette)

        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e1e;
            }
            QLineEdit, QPushButton, QScrollArea {
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

    def eventFilter(self, obj, event):
        if obj == self.scroll_area.viewport() and event.type() == event.Resize:
            if self.update_columns_from_width() and self.wallpapers:
                self.rebuild_grid()
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

    def on_scroll(self, value):
        if self.is_loading or self.stacked.currentIndex() != 1:
            return
        if self.current_page >= self.total_pages:
            return

        scrollbar = self.scroll_area.verticalScrollBar()
        if scrollbar.maximum() - value < 200:
            self.load_next_page()

    # ===== Search Handlers =====
    def perform_search_from_landing(self):
        query = self.landing_search_edit.text().strip()
        if query:
            self.current_query = query
            self.results_search_edit.setText(query)
            self.start_search()
            self.stacked.setCurrentIndex(1)

    def perform_search_from_results(self):
        query = self.results_search_edit.text().strip()
        if query and query != self.current_query:
            self.current_query = query
            self.landing_search_edit.setText(query)
            self.start_search()
        elif query:
            # Same query, just re-run search (page 1)
            self.current_page = 1
            self.start_search()

    def start_search(self):
        self.current_page = 1
        self.wallpapers = []
        self.total_pages = 1
        self.is_loading = True
        self.loading_progress.setVisible(True)
        self.status_bar.showMessage(f"Searching for '{self.current_query}'...")

        self.worker = SearchWorker(self.current_query, self.current_page)
        self.worker.finished.connect(self.on_search_finished)
        self.worker.error.connect(self.on_search_error)
        self.worker.start()
        self.workers.append(self.worker)

    def load_next_page(self):
        if self.is_loading:
            return
        if self.current_page >= self.total_pages:
            return

        self.is_loading = True
        self.loading_progress.setVisible(True)
        self.status_bar.showMessage(f"Loading page {self.current_page + 1}...")

        self.worker = SearchWorker(self.current_query, self.current_page + 1)
        self.worker.finished.connect(self.on_search_finished)
        self.worker.error.connect(self.on_search_error)
        self.worker.start()
        self.workers.append(self.worker)

    def on_search_finished(self, wallpapers, page, total_pages):
        self.is_loading = False
        self.loading_progress.setVisible(False)

        if page == 1:
            self.wallpapers = wallpapers
            self.total_pages = total_pages
            self.current_page = 1
            self.rebuild_grid()
            self.status_bar.showMessage(f"Found {len(wallpapers)} wallpapers (page 1/{total_pages})")
        else:
            self.wallpapers.extend(wallpapers)
            self.current_page = page
            self.total_pages = total_pages
            self.append_to_grid(wallpapers)
            self.status_bar.showMessage(f"Loaded {len(wallpapers)} more wallpapers (page {page}/{total_pages})")

    def on_search_error(self, error_msg):
        self.is_loading = False
        self.loading_progress.setVisible(False)
        QMessageBox.critical(self, "Search Error", error_msg)
        self.status_bar.showMessage("Search failed")
        # If on landing page and error, stay there; if on results and no results, could go back but we'll just show empty grid
        if self.stacked.currentIndex() == 1 and not self.wallpapers:
            # Optionally switch back to landing? We'll keep results page with empty grid.
            pass

    def rebuild_grid(self):
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self.wallpapers:
            return

        self.update_columns_from_width()

        for i, wp in enumerate(self.wallpapers):
            row = i // self.columns
            col = i % self.columns
            widget = WallpaperWidget(wp)
            widget.download_triggered.connect(self.download_wallpaper)
            self.grid_layout.addWidget(widget, row, col)

        row_count = (len(self.wallpapers) - 1) // self.columns + 1
        self.grid_layout.setRowStretch(row_count, 1)

    def append_to_grid(self, new_wallpapers):
        start_index = len(self.wallpapers) - len(new_wallpapers)
        for i, wp in enumerate(new_wallpapers):
            global_index = start_index + i
            row = global_index // self.columns
            col = global_index % self.columns
            widget = WallpaperWidget(wp)
            widget.download_triggered.connect(self.download_wallpaper)
            self.grid_layout.addWidget(widget, row, col)

        row_count = (len(self.wallpapers) - 1) // self.columns + 1
        self.grid_layout.setRowStretch(row_count, 1)

    def download_wallpaper(self, wallpaper_data):
        self.status_bar.showMessage("Downloading...")
        self.download_progress.setVisible(True)
        self.download_progress.setValue(0)

        self.dl_worker = DownloadWorker(wallpaper_data)
        self.dl_worker.finished.connect(self.on_download_finished)
        self.dl_worker.progress.connect(self.download_progress.setValue)
        self.dl_worker.start()
        self.workers.append(self.dl_worker)

    def on_download_finished(self, success, filepath, filename, wall_id):
        self.download_progress.setVisible(False)
        if success:
            timestamp = datetime.now().strftime("%H:%M:%S")
            msg = f"✅ Downloaded: {filename}  →  {DOWNLOAD_FOLDER}  ({timestamp})"
            self.status_bar.showMessage(msg)

            for i in range(self.grid_layout.count()):
                widget = self.grid_layout.itemAt(i).widget()
                if isinstance(widget, WallpaperWidget):
                    if widget.data.get("id") == wall_id:
                        widget.update_downloaded_status()
                        break
        else:
            self.status_bar.showMessage(f"❌ Download failed: {filename}")

# =============================================================================
# Entry Point
# =============================================================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon.fromTheme("wallpaper"))
    window = WallhavenGUI()
    window.show()
    sys.exit(app.exec_())