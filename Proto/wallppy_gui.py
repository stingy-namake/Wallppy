#!/usr/bin/env python3
"""
Wallhaven GUI - Modern, minimal wallpaper downloader
"""

import sys
import os
import requests
from PyQt5.QtCore import (
    Qt, QThread, pyqtSignal, QSize, QUrl, QByteArray
)
from PyQt5.QtGui import (
    QIcon, QPixmap, QFont, QPalette, QColor
)
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QListWidget, QListWidgetItem,
    QLabel, QProgressBar, QStatusBar, QFrame, QSizePolicy,
    QMessageBox, QStyle, QSpacerItem
)

# =============================================================================
# Configuration
# =============================================================================
API_URL = "https://wallhaven.cc/api/v1/search"
DOWNLOAD_FOLDER = "./wallpapers"
THUMB_SIZE = 200, 150  # width, height

# Create download folder if missing
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# =============================================================================
# Worker Threads (to keep UI responsive)
# =============================================================================
class SearchWorker(QThread):
    """Performs API search in background."""
    finished = pyqtSignal(list, int)  # results, total_pages (approx)
    error = pyqtSignal(str)

    def __init__(self, query, page=1):
        super().__init__()
        self.query = query
        self.page = page

    def run(self):
        params = {
            "q": self.query,
            "categories": "111",  # general + anime + people
            "purity": "100",      # SFW only
            "page": self.page,
            "sorting": "date_added",
            "order": "desc"
        }
        try:
            resp = requests.get(API_URL, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            results = data.get("data", [])
            # Wallhaven API returns "meta" with "last_page"
            total_pages = data.get("meta", {}).get("last_page", 1)
            self.finished.emit(results, total_pages)
        except Exception as e:
            self.error.emit(str(e))


class ThumbnailLoader(QThread):
    """Downloads a thumbnail and emits a QPixmap."""
    loaded = pyqtSignal(str, QPixmap)  # wall_id, pixmap

    def __init__(self, wall_id, thumb_url):
        super().__init__()
        self.wall_id = wall_id
        self.thumb_url = thumb_url

    def run(self):
        try:
            resp = requests.get(self.thumb_url, timeout=10)
            resp.raise_for_status()
            pixmap = QPixmap()
            pixmap.loadFromData(QByteArray(resp.content))
            if not pixmap.isNull():
                # Scale to thumbnail size
                pixmap = pixmap.scaled(
                    THUMB_SIZE[0], THUMB_SIZE[1],
                    Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
            self.loaded.emit(self.wall_id, pixmap)
        except Exception:
            # Silently fail – item will keep default icon
            pass


class DownloadWorker(QThread):
    """Downloads the full image."""
    finished = pyqtSignal(bool, str)  # success, message

    def __init__(self, wallpaper_data):
        super().__init__()
        self.data = wallpaper_data

    def run(self):
        image_url = self.data.get("path")
        wall_id = self.data.get("id")
        file_type = self.data.get("file_type", "image/jpeg")

        if not image_url:
            self.finished.emit(False, "No image URL found.")
            return

        # Determine extension
        if "jpeg" in file_type or "jpg" in file_type:
            ext = "jpg"
        elif "png" in file_type:
            ext = "png"
        else:
            ext = "jpg"

        filename = f"wallhaven-{wall_id}.{ext}"
        filepath = os.path.join(DOWNLOAD_FOLDER, filename)

        if os.path.exists(filepath):
            self.finished.emit(True, f"Already exists: {filename}")
            return

        try:
            resp = requests.get(image_url, stream=True, timeout=30)
            resp.raise_for_status()
            with open(filepath, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            self.finished.emit(True, f"Downloaded: {filename}")
        except Exception as e:
            self.finished.emit(False, f"Download failed: {e}")


# =============================================================================
# Custom List Widget Item (holds wallpaper data)
# =============================================================================
class WallpaperItem(QListWidgetItem):
    def __init__(self, wallpaper_data):
        super().__init__()
        self.data = wallpaper_data
        self.wall_id = wallpaper_data.get("id")
        resolution = wallpaper_data.get("resolution", "?")
        self.setText(f"{resolution}  •  {wallpaper_data.get('category','?')}")
        self.setToolTip(
            f"ID: {self.wall_id}\n"
            f"Resolution: {resolution}\n"
            f"Purity: {wallpaper_data.get('purity','?')}\n"
            "Double‑click to download"
        )
        # Default icon (placeholder)
        self.setIcon(QApplication.style().standardIcon(QStyle.SP_FileIcon))


# =============================================================================
# Main Window
# =============================================================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_page = 1
        self.total_pages = 1
        self.current_query = ""
        self.wallpapers = []  # raw data list
        self.thumbnail_loaders = []  # keep references
        self.setWindowTitle("Wallhaven Browser")
        self.setMinimumSize(800, 600)
        self.setup_ui()
        self.apply_style()

    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # ----- Search Bar -----
        search_frame = QFrame()
        search_frame.setFrameShape(QFrame.StyledPanel)
        search_layout = QHBoxLayout(search_frame)
        search_layout.setContentsMargins(5, 5, 5, 5)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search wallpapers...")
        self.search_input.returnPressed.connect(self.on_search)
        search_layout.addWidget(self.search_input)

        self.search_btn = QPushButton()
        self.search_btn.setIcon(self.style().standardIcon(QStyle.SP_FileDialogContentsView))
        self.search_btn.setToolTip("Search")
        self.search_btn.clicked.connect(self.on_search)
        search_layout.addWidget(self.search_btn)

        layout.addWidget(search_frame)

        # ----- Thumbnail List (icon view) -----
        self.list_widget = QListWidget()
        self.list_widget.setViewMode(QListWidget.IconMode)
        self.list_widget.setIconSize(QSize(*THUMB_SIZE))
        self.list_widget.setResizeMode(QListWidget.Adjust)
        self.list_widget.setMovement(QListWidget.Static)
        self.list_widget.setSpacing(12)
        self.list_widget.setWordWrap(True)
        self.list_widget.itemDoubleClicked.connect(self.download_selected)
        layout.addWidget(self.list_widget, 1)

        # ----- Pagination Bar -----
        page_frame = QFrame()
        page_layout = QHBoxLayout(page_frame)
        page_layout.setContentsMargins(0, 0, 0, 0)

        self.prev_btn = QPushButton()
        self.prev_btn.setIcon(self.style().standardIcon(QStyle.SP_ArrowBack))
        self.prev_btn.setToolTip("Previous page")
        self.prev_btn.clicked.connect(self.previous_page)
        self.prev_btn.setEnabled(False)
        page_layout.addWidget(self.prev_btn)

        self.page_label = QLabel("Page 0 / 0")
        self.page_label.setAlignment(Qt.AlignCenter)
        page_layout.addWidget(self.page_label)

        self.next_btn = QPushButton()
        self.next_btn.setIcon(self.style().standardIcon(QStyle.SP_ArrowForward))
        self.next_btn.setToolTip("Next page")
        self.next_btn.clicked.connect(self.next_page)
        self.next_btn.setEnabled(False)
        page_layout.addWidget(self.next_btn)

        page_layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        self.download_btn = QPushButton("Download Selected")
        self.download_btn.setIcon(self.style().standardIcon(QStyle.SP_DialogSaveButton))
        self.download_btn.clicked.connect(self.download_selected)
        self.download_btn.setEnabled(False)
        page_layout.addWidget(self.download_btn)

        layout.addWidget(page_frame)

        # ----- Status Bar -----
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

        # Progress indicator (hidden by default)
        self.progress = QProgressBar()
        self.progress.setMaximum(0)  # indefinite
        self.progress.setVisible(False)
        self.status_bar.addPermanentWidget(self.progress)

    def apply_style(self):
        # Modern dark theme (optional)
        dark_palette = QPalette()
        dark_palette.setColor(QPalette.Window, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.WindowText, Qt.white)
        dark_palette.setColor(QPalette.Base, QColor(25, 25, 25))
        dark_palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.ToolTipBase, Qt.white)
        dark_palette.setColor(QPalette.ToolTipText, Qt.white)
        dark_palette.setColor(QPalette.Text, Qt.white)
        dark_palette.setColor(QPalette.Button, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.ButtonText, Qt.white)
        dark_palette.setColor(QPalette.BrightText, Qt.red)
        dark_palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
        dark_palette.setColor(QPalette.HighlightedText, Qt.black)
        self.setPalette(dark_palette)

        # Font adjustments
        font = QFont("Segoe UI", 9)
        QApplication.setFont(font)

    # -------------------------------------------------------------------------
    # Event Handlers
    # -------------------------------------------------------------------------
    def on_search(self):
        query = self.search_input.text().strip()
        if not query:
            QMessageBox.information(self, "Info", "Please enter a search term.")
            return
        self.current_query = query
        self.current_page = 1
        self.perform_search()

    def perform_search(self):
        self.set_busy(True)
        self.list_widget.clear()
        self.wallpapers.clear()
        self.status_bar.showMessage(f"Searching for '{self.current_query}'...")

        self.search_worker = SearchWorker(self.current_query, self.current_page)
        self.search_worker.finished.connect(self.on_search_finished)
        self.search_worker.error.connect(self.on_search_error)
        self.search_worker.start()

    def on_search_finished(self, results, total_pages):
        self.set_busy(False)
        self.wallpapers = results
        self.total_pages = total_pages
        self.update_pagination_ui()

        if not results:
            self.status_bar.showMessage("No wallpapers found.", 3000)
            return

        self.status_bar.showMessage(f"Found {len(results)} wallpapers (page {self.current_page}/{total_pages})")
        self.populate_list(results)

    def on_search_error(self, error_msg):
        self.set_busy(False)
        self.status_bar.showMessage(f"Error: {error_msg}", 5000)
        QMessageBox.critical(self, "Search Error", error_msg)

    def populate_list(self, wallpapers):
        self.list_widget.clear()
        for wp in wallpapers:
            item = WallpaperItem(wp)
            self.list_widget.addItem(item)

            # Load thumbnail asynchronously
            thumb_url = wp.get("thumbs", {}).get("small")
            if thumb_url:
                loader = ThumbnailLoader(wp.get("id"), thumb_url)
                loader.loaded.connect(self.on_thumbnail_loaded)
                loader.start()
                self.thumbnail_loaders.append(loader)  # prevent GC

        self.download_btn.setEnabled(True)

    def on_thumbnail_loaded(self, wall_id, pixmap):
        # Find item with matching wall_id and set its icon
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if isinstance(item, WallpaperItem) and item.wall_id == wall_id:
                item.setIcon(QIcon(pixmap))
                break

    def update_pagination_ui(self):
        self.page_label.setText(f"Page {self.current_page} / {self.total_pages}")
        self.prev_btn.setEnabled(self.current_page > 1)
        self.next_btn.setEnabled(self.current_page < self.total_pages)

    def previous_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.perform_search()

    def next_page(self):
        if self.current_page < self.total_pages:
            self.current_page += 1
            self.perform_search()

    def download_selected(self):
        item = self.list_widget.currentItem()
        if not item or not isinstance(item, WallpaperItem):
            QMessageBox.information(self, "Info", "Please select a wallpaper first.")
            return
        self.download_wallpaper(item.data)

    def download_wallpaper(self, wallpaper_data):
        self.set_busy(True)
        self.status_bar.showMessage("Downloading...")
        self.download_worker = DownloadWorker(wallpaper_data)
        self.download_worker.finished.connect(self.on_download_finished)
        self.download_worker.start()

    def on_download_finished(self, success, message):
        self.set_busy(False)
        self.status_bar.showMessage(message, 4000)
        if success:
            # Optionally play a sound or flash
            pass
        else:
            QMessageBox.warning(self, "Download", message)

    def set_busy(self, busy):
        self.progress.setVisible(busy)
        self.search_btn.setEnabled(not busy)
        self.search_input.setEnabled(not busy)
        self.prev_btn.setEnabled(not busy and self.current_page > 1)
        self.next_btn.setEnabled(not busy and self.current_page < self.total_pages)
        self.download_btn.setEnabled(not busy and self.list_widget.count() > 0)


# =============================================================================
# Entry Point
# =============================================================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # consistent cross-platform look
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())