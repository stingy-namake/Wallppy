#!/usr/bin/env python3
"""
wallppy - Modern, minimal wallpaper browser with infinite scrolling.
Double-click any thumbnail to download.
Downloaded wallpapers show a green checkmark.
"""

import sys
import os
import requests
import random
import json
from pathlib import Path
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QLabel, QScrollArea, QGridLayout,
    QFrame, QMessageBox, QProgressBar, QSizePolicy, QStatusBar,
    QStackedWidget, QCheckBox, QFileDialog
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt5.QtGui import QPixmap, QIcon, QPalette, QColor, QMouseEvent

# =============================================================================
# Configuration
# =============================================================================
API_URL = "https://wallhaven.cc/api/v1/search"
DEFAULT_DOWNLOAD_FOLDER = "./wallpapers"
THUMB_SIZE = QSize(280, 158)  # 16:9
THUMB_PADDING = 12

os.makedirs(DEFAULT_DOWNLOAD_FOLDER, exist_ok=True)

NO_RESULTS_MESSAGES = [
    "Nothing here... Maybe it's in another world?",
    "This search result is a lie.",
    "No wallpapers found. Believe it!",
    "The data is empty. Just like my soul.",
    "404: Wallpapers Not Found. Try a different keyword, nya~",
    "Even the Great Sage couldn't find anything.",
    "This search returned void. Like the Abyss.",
    "No results. Perhaps you need the Sharingan to see them?",
]

# =============================================================================
# Worker Threads
# =============================================================================
class SearchWorker(QThread):
    finished = pyqtSignal(list, int, int)
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
    finished = pyqtSignal(bool, str, str, str)
    progress = pyqtSignal(int)

    def __init__(self, wallpaper_data, download_folder):
        super().__init__()
        self.data = wallpaper_data
        self.download_folder = download_folder

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

        filename = f"wallppy-{wall_id}.{ext}"
        filepath = os.path.join(self.download_folder, filename)
        os.makedirs(self.download_folder, exist_ok=True)

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

    def __init__(self, wallpaper_data, download_folder, parent=None):
        super().__init__(parent)
        self.data = wallpaper_data
        self.download_folder = download_folder
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
                border: 2px solid #1E6FF0;
            }
        """)
        self.thumb_label.setScaledContents(True)
        self.thumb_label.setCursor(Qt.PointingHandCursor)
        self.thumb_label.double_clicked.connect(self.emit_download)
        layout.addWidget(self.thumb_label)

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
        filename = f"wallppy-{wall_id}.{ext}"
        filepath = os.path.join(self.download_folder, filename)
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
# Main Window
# =============================================================================
class WallppyGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("wallppy")
        self.setMinimumSize(682, 500)
        self.resize(1100, 700)

        self.load_settings()

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

    def get_config_path(self):
        config_dir = Path.home() / ".config" / "wallppy"
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir / "settings.json"

    def load_settings(self):
        config_path = self.get_config_path()
        defaults = {
            "download_folder": DEFAULT_DOWNLOAD_FOLDER,
            "categories": {"general": True, "anime": True, "people": True},
            "purity": {"sfw": True, "sketchy": False}
        }
        if config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    settings = json.load(f)
                    self.download_folder = settings.get("download_folder", defaults["download_folder"])
                    self.cat_settings = settings.get("categories", defaults["categories"])
                    self.purity_settings = settings.get("purity", defaults["purity"])
            except Exception:
                self.download_folder = defaults["download_folder"]
                self.cat_settings = defaults["categories"]
                self.purity_settings = defaults["purity"]
        else:
            self.download_folder = defaults["download_folder"]
            self.cat_settings = defaults["categories"]
            self.purity_settings = defaults["purity"]
        os.makedirs(self.download_folder, exist_ok=True)

    def save_settings(self):
        config_path = self.get_config_path()
        settings = {
            "download_folder": self.download_folder,
            "categories": {
                "general": self.cat_general.isChecked(),
                "anime": self.cat_anime.isChecked(),
                "people": self.cat_people.isChecked()
            },
            "purity": {
                "sfw": self.purity_sfw.isChecked(),
                "sketchy": self.purity_sketchy.isChecked()
            }
        }
        try:
            with open(config_path, 'w') as f:
                json.dump(settings, f, indent=2)
        except Exception:
            pass

    def keyPressEvent(self, event):
        if (self.stacked.currentIndex() == 0 and 
            event.key() == Qt.Key_Return and 
            event.modifiers() == Qt.NoModifier):
            self.perform_search_from_landing()
        else:
            super().keyPressEvent(event)

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.stacked = QStackedWidget()
        main_layout.addWidget(self.stacked)

        # ===== Landing page =====
        self.landing_page = QWidget()
        landing_layout = QVBoxLayout(self.landing_page)
        landing_layout.setAlignment(Qt.AlignCenter)
        landing_layout.setSpacing(20)

        search_container = QWidget()
        search_container.setFixedWidth(550)
        container_layout = QVBoxLayout(search_container)
        container_layout.setSpacing(15)

        title = QLabel("wallppy")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 36px; font-weight: bold; color: #1E6FF0;")
        container_layout.addWidget(title)

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
                border: 1px solid #1E6FF0;
            }
        """)
        self.landing_search_edit.returnPressed.connect(self.perform_search_from_landing)
        container_layout.addWidget(self.landing_search_edit)

        hint1 = QLabel("Press Enter to search")
        hint1.setAlignment(Qt.AlignCenter)
        hint1.setStyleSheet("color: #777; font-size: 12px;")
        container_layout.addWidget(hint1)

        filter_label = QLabel("Categories")
        filter_label.setStyleSheet("color: #aaa; font-size: 13px; font-weight: bold; margin-top: 5px;")
        container_layout.addWidget(filter_label)

        cat_layout = QHBoxLayout()
        cat_layout.setSpacing(20)
        cat_layout.setAlignment(Qt.AlignCenter)

        self.cat_general = QCheckBox("General")
        self.cat_anime = QCheckBox("Anime")
        self.cat_people = QCheckBox("People")

        # Set from loaded settings
        self.cat_general.setChecked(self.cat_settings.get("general", True))
        self.cat_anime.setChecked(self.cat_settings.get("anime", True))
        self.cat_people.setChecked(self.cat_settings.get("people", True))

        self.cat_general.stateChanged.connect(self.save_settings)
        self.cat_anime.stateChanged.connect(self.save_settings)
        self.cat_people.stateChanged.connect(self.save_settings)

        cat_layout.addWidget(self.cat_general)
        cat_layout.addWidget(self.cat_anime)
        cat_layout.addWidget(self.cat_people)
        container_layout.addLayout(cat_layout)

        purity_label = QLabel("Content")
        purity_label.setStyleSheet("color: #aaa; font-size: 13px; font-weight: bold; margin-top: 5px;")
        container_layout.addWidget(purity_label)

        purity_layout = QHBoxLayout()
        purity_layout.setSpacing(20)
        purity_layout.setAlignment(Qt.AlignCenter)

        self.purity_sfw = QCheckBox("SFW")
        self.purity_sketchy = QCheckBox("Sketchy")

        self.purity_sfw.setChecked(self.purity_settings.get("sfw", True))
        self.purity_sketchy.setChecked(self.purity_settings.get("sketchy", False))

        self.purity_sfw.stateChanged.connect(self.save_settings)
        self.purity_sketchy.stateChanged.connect(self.save_settings)

        purity_layout.addWidget(self.purity_sfw)
        purity_layout.addWidget(self.purity_sketchy)
        container_layout.addLayout(purity_layout)

        dir_label = QLabel("Save to")
        dir_label.setStyleSheet("color: #aaa; font-size: 13px; font-weight: bold; margin-top: 10px;")
        container_layout.addWidget(dir_label)

        dir_layout = QHBoxLayout()
        dir_layout.setSpacing(10)

        self.dir_edit = QLineEdit()
        self.dir_edit.setText(self.download_folder)
        self.dir_edit.setReadOnly(True)
        dir_layout.addWidget(self.dir_edit)

        self.browse_btn = QPushButton("Browse")
        self.browse_btn.setFixedWidth(80)
        self.browse_btn.clicked.connect(self.choose_directory)
        dir_layout.addWidget(self.browse_btn)

        container_layout.addLayout(dir_layout)

        landing_layout.addWidget(search_container)
        self.stacked.addWidget(self.landing_page)

        # ===== Results page =====
        self.results_page = QWidget()
        results_layout = QVBoxLayout(self.results_page)
        results_layout.setContentsMargins(12, 12, 12, 12)
        results_layout.setSpacing(12)

        top_bar = QHBoxLayout()
        top_bar.setSpacing(10)

        self.home_btn = QPushButton("⌂")
        self.home_btn.setToolTip("Back to home")
        self.home_btn.setFixedSize(36, 36)
        self.home_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: 1px solid #3d3d3d;
                border-radius: 18px;
                font-size: 20px;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #3d3d3d;
            }
        """)
        self.home_btn.clicked.connect(self.go_home)
        top_bar.addWidget(self.home_btn)

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
        self.results_search_btn.setStyleSheet("""
            QPushButton {
                background-color: #1E6FF0;
                color: white;
                border-radius: 4px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #3D82F5;
            }
            QPushButton:pressed {
                background-color: #1558C4;
            }
        """)
        top_bar.addWidget(self.results_search_btn)
        top_bar.addStretch()
        results_layout.addLayout(top_bar)

        self.results_container = QStackedWidget()
        results_layout.addWidget(self.results_container)

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
        self.results_container.addWidget(self.scroll_area)

        self.no_results_widget = QWidget()
        no_results_layout = QVBoxLayout(self.no_results_widget)
        no_results_layout.setAlignment(Qt.AlignCenter)
        self.no_results_label = QLabel()
        self.no_results_label.setAlignment(Qt.AlignCenter)
        self.no_results_label.setStyleSheet("color: #aaa; font-size: 18px; padding: 40px;")
        self.no_results_label.setWordWrap(True)
        no_results_layout.addWidget(self.no_results_label)
        self.results_container.addWidget(self.no_results_widget)

        self.loading_progress = QProgressBar()
        self.loading_progress.setVisible(False)
        self.loading_progress.setRange(0, 0)
        results_layout.addWidget(self.loading_progress)

        self.stacked.addWidget(self.results_page)
        self.stacked.setCurrentIndex(0)

        self.scroll_area.viewport().installEventFilter(self)
        self.scroll_area.verticalScrollBar().valueChanged.connect(self.on_scroll)

    def go_home(self):
        self.stacked.setCurrentIndex(0)
        self.landing_search_edit.setText(self.results_search_edit.text())

    def choose_directory(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Download Folder", self.download_folder)
        if folder:
            self.download_folder = folder
            self.dir_edit.setText(folder)
            self.save_settings()
            os.makedirs(self.download_folder, exist_ok=True)

    def get_category_string(self):
        cat = ""
        cat += "1" if self.cat_general.isChecked() else "0"
        cat += "1" if self.cat_anime.isChecked() else "0"
        cat += "1" if self.cat_people.isChecked() else "0"
        return cat

    def get_purity_string(self):
        purity = ""
        purity += "1" if self.purity_sfw.isChecked() else "0"
        purity += "1" if self.purity_sketchy.isChecked() else "0"
        purity += "0"
        return purity

    def setup_status_bar(self):
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("Ready")

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
                background-color: #1E6FF0;
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
            QLineEdit, QPushButton, QScrollArea, QCheckBox {
                background-color: #2d2d2d;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 6px;
                color: white;
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
            self.current_page = 1
            self.start_search()

    def start_search(self):
        self.current_page = 1
        self.wallpapers = []
        self.total_pages = 1
        self.is_loading = True
        self.loading_progress.setVisible(True)
        self.status_bar.showMessage(f"Searching for '{self.current_query}'...")
        self.results_container.setCurrentIndex(0)

        self.worker = SearchWorker(
            self.current_query,
            self.current_page,
            self.get_category_string(),
            self.get_purity_string()
        )
        self.worker.finished.connect(self.on_search_finished)
        self.worker.error.connect(self.on_search_error)
        self.worker.start()
        self.workers.append(self.worker)

    def load_next_page(self):
        if self.is_loading or self.current_page >= self.total_pages:
            return

        self.is_loading = True
        self.loading_progress.setVisible(True)
        self.status_bar.showMessage(f"Loading page {self.current_page + 1}...")

        self.worker = SearchWorker(
            self.current_query,
            self.current_page + 1,
            self.get_category_string(),
            self.get_purity_string()
        )
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
            if not wallpapers:
                self.show_no_results()
                self.status_bar.showMessage("No wallpapers found. Try a different search.")
            else:
                self.results_container.setCurrentIndex(0)
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

    def show_no_results(self):
        message = random.choice(NO_RESULTS_MESSAGES)
        self.no_results_label.setText(message)
        self.results_container.setCurrentIndex(1)

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
            widget = WallpaperWidget(wp, self.download_folder)
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
            widget = WallpaperWidget(wp, self.download_folder)
            widget.download_triggered.connect(self.download_wallpaper)
            self.grid_layout.addWidget(widget, row, col)

        row_count = (len(self.wallpapers) - 1) // self.columns + 1
        self.grid_layout.setRowStretch(row_count, 1)

    def download_wallpaper(self, wallpaper_data):
        self.status_bar.showMessage("Downloading...")
        self.download_progress.setVisible(True)
        self.download_progress.setValue(0)

        self.dl_worker = DownloadWorker(wallpaper_data, self.download_folder)
        self.dl_worker.finished.connect(self.on_download_finished)
        self.dl_worker.progress.connect(self.download_progress.setValue)
        self.dl_worker.start()
        self.workers.append(self.dl_worker)

    def on_download_finished(self, success, filepath, filename, wall_id):
        self.download_progress.setVisible(False)
        if success:
            timestamp = datetime.now().strftime("%H:%M:%S")
            msg = f"✅ Downloaded: {filename}  →  {self.download_folder}  ({timestamp})"
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
    window = WallppyGUI()
    window.show()
    sys.exit(app.exec_())