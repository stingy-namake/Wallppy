import os
import random
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QLabel, QScrollArea, QGridLayout, QFrame, QStackedWidget,
    QProgressBar, QMessageBox, QCheckBox, QComboBox, QSizePolicy,
    QToolButton, QShortcut
)
from PyQt5.QtCore import Qt, pyqtSignal, QSize, QThread, QTimer
from PyQt5.QtGui import QIcon, QPixmap, QKeySequence
from core.extension import WallpaperExtension
from core.settings import Settings
from core.workers import SearchWorker, DownloadWorker, ThumbnailLoader, get_session
from core.wallpaper_manager import WallpaperSetterWorker
from .wallpaper_widget import WallpaperWidget


THUMB_SIZE = QSize(280, 158)
THUMB_PADDING = 12

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


class FilterPanel(QFrame):
    """Collapsible panel that contains filter widgets."""
    filters_changed = pyqtSignal()

    def __init__(self, extension: WallpaperExtension, parent=None):
        super().__init__(parent)
        self.extension = extension
        self.widgets = {}
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet("""
            FilterPanel {
                background-color: #2d2d2d;
                border-radius: 4px;
                padding: 8px;
            }
        """)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)
        main_layout.setAlignment(Qt.AlignTop)

        filters = self.extension.get_filters() if self.extension else {}
        
        for filter_id, filter_def in filters.items():
            filter_type = filter_def.get("type")
            label = filter_def.get("label", filter_id)
            options = filter_def.get("options", [])

            group_widget = QWidget()
            group_layout = QVBoxLayout(group_widget)
            group_layout.setContentsMargins(0, 0, 0, 0)
            group_layout.setSpacing(6)
            
            cat_label = QLabel(label)
            cat_label.setStyleSheet("color: #aaa; font-size: 13px; font-weight: bold;")
            group_layout.addWidget(cat_label)

            if filter_type == "checkboxes":
                cb_container = QWidget()
                cb_layout = QHBoxLayout(cb_container)
                cb_layout.setContentsMargins(0, 0, 0, 0)
                cb_layout.setSpacing(16)
                
                for opt in options:
                    cb = QCheckBox(opt["label"])
                    cb.setChecked(opt.get("default", False))
                    cb.stateChanged.connect(self.filters_changed.emit)
                    cb.setStyleSheet("color: white;")
                    cb_layout.addWidget(cb)
                    key = f"{filter_id}.{opt['id']}"
                    self.widgets[key] = cb
                
                cb_layout.addStretch()
                group_layout.addWidget(cb_container)

            elif filter_type == "dropdown":
                combo = QComboBox()
                combo.setStyleSheet("""
                    QComboBox {
                        background-color: #3d3d3d;
                        border: 1px solid #4d4d4d;
                        border-radius: 4px;
                        padding: 6px;
                        color: white;
                        min-width: 150px;
                    }
                    QComboBox::drop-down {
                        border: none;
                        width: 20px;
                    }
                    QComboBox QAbstractItemView {
                        background-color: #3d3d3d;
                        color: white;
                        selection-background-color: #1E6FF0;
                    }
                """)
                
                default_index = 0
                for i, opt in enumerate(options):
                    combo.addItem(opt["label"], opt["id"])
                    if opt.get("default", False):
                        default_index = i
                
                combo.setCurrentIndex(default_index)
                combo.currentIndexChanged.connect(self.filters_changed.emit)
                group_layout.addWidget(combo)
                self.widgets[filter_id] = combo

            main_layout.addWidget(group_widget)

        self.setLayout(main_layout)

    def get_filter_values(self) -> dict:
        filters = self.extension.get_filters()
        values = {}

        for filter_id, filter_def in filters.items():
            filter_type = filter_def.get("type")

            if filter_type == "checkboxes":
                if filter_id == "categories":
                    cat = ""
                    for opt in filter_def["options"]:
                        cb = self.widgets.get(f"{filter_id}.{opt['id']}")
                        cat += "1" if (cb and cb.isChecked()) else "0"
                    values[filter_id] = cat
                elif filter_id == "purity":
                    pur = ""
                    for opt in filter_def["options"]:
                        cb = self.widgets.get(f"{filter_id}.{opt['id']}")
                        pur += "1" if (cb and cb.isChecked()) else "0"
                    values[filter_id] = pur
                elif filter_id == "ratio":
                    selected = []
                    for opt in filter_def["options"]:
                        cb = self.widgets.get(f"{filter_id}.{opt['id']}")
                        if cb and cb.isChecked():
                            selected.append(opt["id"])
                    values[filter_id] = ",".join(selected) if selected else ""
                else:
                    checked = []
                    for opt in filter_def["options"]:
                        cb = self.widgets.get(f"{filter_id}.{opt['id']}")
                        if cb and cb.isChecked():
                            checked.append(opt["id"])
                    values[filter_id] = checked
                    
            elif filter_type == "dropdown":
                combo = self.widgets.get(filter_id)
                if combo:
                    values[filter_id] = combo.currentData()

        return values


class FullImageLoader(QThread):
    """Loads the full resolution image for preview."""
    loaded = pyqtSignal(QPixmap)
    error = pyqtSignal(str)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        try:
            if self.url.startswith("file://"):
                filepath = self.url[7:]
            else:
                filepath = self.url

            if os.path.exists(filepath):
                pixmap = QPixmap(filepath)
                if pixmap.isNull():
                    self.error.emit("Failed to load image from disk")
                else:
                    self.loaded.emit(pixmap)
                return

            session = get_session()
            response = session.get(self.url, timeout=30)
            if response.status_code == 200:
                pixmap = QPixmap()
                pixmap.loadFromData(response.content)
                self.loaded.emit(pixmap)
            else:
                self.error.emit(f"Failed to load image: {response.status_code}")
        except Exception as e:
            self.error.emit(str(e))


class ImageOverlay(QWidget):
    """Semi-transparent overlay showing the full image."""
    closed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: rgba(0, 0, 0, 0.9);")
        self.setVisible(False)
        self.loader = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignCenter)

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setScaledContents(False)
        layout.addWidget(self.image_label)

        self.loading_label = QLabel("Loading full image...")
        self.loading_label.setStyleSheet("color: white; font-size: 18px; background: transparent;")
        self.loading_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.loading_label)

        hint = QLabel("Press ESC to close")
        hint.setStyleSheet("color: #aaa; font-size: 12px; background: transparent; padding: 10px;")
        hint.setAlignment(Qt.AlignCenter)
        layout.addWidget(hint)

        QShortcut(QKeySequence("Escape"), self, self.close_overlay)

    def show_image(self, url):
        self.image_label.clear()
        self.loading_label.setVisible(True)
        self.setVisible(True)
        self.raise_()

        self._cancel_loader()
        
        self.loader = FullImageLoader(url)
        self.loader.loaded.connect(self.on_image_loaded)
        self.loader.error.connect(self.on_load_error)
        self.loader.start()

    def _cancel_loader(self):
        """Safely stop any running image loader to prevent deleted-object crashes."""
        if self.loader is None:
            return
        try:
            # Disconnect our slots first so stale signals don't fire after we're gone
            try:
                self.loader.loaded.disconnect(self.on_image_loaded)
            except (TypeError, RuntimeError):
                pass
            try:
                self.loader.error.disconnect(self.on_load_error)
            except (TypeError, RuntimeError):
                pass
            if self.loader.isRunning():
                self.loader.terminate()
                self.loader.wait(300)
        except RuntimeError:
            pass  # C++ object already deleted
        finally:
            self.loader = None

    def on_image_loaded(self, pixmap):
        self.loading_label.setVisible(False)
        if not pixmap.isNull():
            available = self.size() - QSize(40, 80)
            scaled = pixmap.scaled(available, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.image_label.setPixmap(scaled)
        else:
            self.image_label.setText("Failed to load image")

    def on_load_error(self, msg):
        self.loading_label.setVisible(False)
        self.image_label.setText(f"Error: {msg}")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.image_label.pixmap() and not self.image_label.pixmap().isNull():
            available = self.size() - QSize(40, 80)
            scaled = self.image_label.pixmap().scaled(available, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.image_label.setPixmap(scaled)

    def close_overlay(self):
        self._cancel_loader()
        self.setVisible(False)
        self.closed.emit()

    def mousePressEvent(self, event):
        self.close_overlay()


class ResultsPage(QWidget):
    home_requested = pyqtSignal()
    search_requested = pyqtSignal(str)
    download_progress = pyqtSignal(int)
    download_finished = pyqtSignal(bool, str, str, str)

    def __init__(self, extension: WallpaperExtension, settings: Settings, parent=None):
        super().__init__(parent)
        self.extension = extension
        self.settings = settings
        self.current_query = ""
        self.current_page = 1
        self.total_pages = 1
        self.wallpapers = []
        self.columns = 3
        self.is_loading = False
        self._active_workers = []
        self._widget_cache = {}
        self._resize_timer = None

        self.init_ui()
        self.init_overlay()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # Top bar
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
        self.home_btn.clicked.connect(self.home_requested.emit)
        top_bar.addWidget(self.home_btn)

        # Search bar
        search_container = QWidget()
        search_layout = QHBoxLayout(search_container)
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.setSpacing(8)

        search_icon = QLabel()
        search_icon.setPixmap(QIcon.fromTheme("system-search").pixmap(16, 16))
        search_layout.addWidget(search_icon)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search wallpapers...")
        self.search_edit.setFixedHeight(32) 
        self.search_edit.setStyleSheet("""
            QLineEdit {
                font-size: 14px;
                padding: 0px 12px;
                border-radius: 4px;
                background-color: #2d2d2d;
                border: 1px solid #3d3d3d;
                color: white;
            }
            QLineEdit:focus {
                border: 1px solid #1E6FF0;
            }
        """)
        self.search_edit.returnPressed.connect(self.emit_search)
        search_layout.addWidget(self.search_edit, 3)

        self.filter_toggle_btn = QToolButton()
        self.filter_toggle_btn.setText("▼ Filters")
        self.filter_toggle_btn.setToolTip("Show/hide filters")
        self.filter_toggle_btn.setCheckable(True)
        self.filter_toggle_btn.setChecked(False)
        self.filter_toggle_btn.setFixedSize(100, 32)
        self.filter_toggle_btn.setStyleSheet("""
            QToolButton {
                background-color: #3d3d3d;
                border-radius: 4px;
                padding: 0px 12px;
                min-height: 30px;
                color: white;
                border: 1px solid #4d4d4d;
                font-size: 13px;
            }
            QToolButton:hover {
                background-color: #4d4d4d;
            }
            QToolButton:checked {
                background-color: #1E6FF0;
            }
        """)
        self.filter_toggle_btn.clicked.connect(self.toggle_filter_panel)
        search_layout.addWidget(self.filter_toggle_btn)

        self.search_btn = QPushButton("Search")
        self.search_btn.setFixedSize(100, 32)
        self.search_btn.clicked.connect(self.emit_search)
        self.search_btn.setStyleSheet("""
            QPushButton {
                background-color: #1E6FF0;
                color: white;
                border-radius: 4px;
                padding: 0px 16px;
                min-height: 30px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #3D82F5;
            }
            QPushButton:pressed {
                background-color: #1558C4;
            }
        """)
        search_layout.addWidget(self.search_btn)

        top_bar.addWidget(search_container, 3)
        top_bar.addStretch()
        layout.addLayout(top_bar)

        # Collapsible filter panel
        self.filter_panel = FilterPanel(self.extension)
        self.filter_panel.filters_changed.connect(self.on_filters_changed)
        self.filter_panel.setVisible(False)
        layout.addWidget(self.filter_panel)

        # Results container
        self.results_container = QStackedWidget()
        layout.addWidget(self.results_container)

        # Grid with centering
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

        grid_container = QWidget()
        container_layout = QHBoxLayout(grid_container)
        container_layout.setAlignment(Qt.AlignCenter)
        container_layout.addWidget(self.grid_widget)
        container_layout.setContentsMargins(0, 0, 0, 0)

        self.scroll_area.setWidget(grid_container)
        self.results_container.addWidget(self.scroll_area)

        # No results
        self.no_results_widget = QWidget()
        no_results_layout = QVBoxLayout(self.no_results_widget)
        no_results_layout.setAlignment(Qt.AlignCenter)
        self.no_results_label = QLabel()
        self.no_results_label.setAlignment(Qt.AlignCenter)
        self.no_results_label.setStyleSheet("color: #aaa; font-size: 18px; padding: 40px;")
        self.no_results_label.setWordWrap(True)
        no_results_layout.addWidget(self.no_results_label)
        self.results_container.addWidget(self.no_results_widget)

        # Loading indicator
        self.loading_progress = QProgressBar()
        self.loading_progress.setVisible(False)
        self.loading_progress.setRange(0, 0)
        layout.addWidget(self.loading_progress)

        self.scroll_area.viewport().installEventFilter(self)
        self.scroll_area.verticalScrollBar().valueChanged.connect(self.on_scroll)

    def init_overlay(self):
        self.overlay = ImageOverlay(self)
        self.overlay.closed.connect(self.on_overlay_closed)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'overlay') and self.overlay.isVisible():
            self.overlay.resize(self.size())
            self.overlay.move(0, 0)
        
        if self._resize_timer is None:
            self._resize_timer = QTimer(self)
            self._resize_timer.setSingleShot(True)
            self._resize_timer.timeout.connect(self._do_resize)
        self._resize_timer.start(200)
    
    def _do_resize(self):
        if self.update_columns_from_width() and self.wallpapers:
            self.rebuild_grid()

    def on_overlay_closed(self):
        self.activateWindow()

    def toggle_filter_panel(self):
        is_visible = self.filter_panel.isVisible()
        self.filter_panel.setVisible(not is_visible)
        self.filter_toggle_btn.setText("▲ Filters" if not is_visible else "▼ Filters")

    def on_filters_changed(self):
        self.start_search(self.current_query)

    def eventFilter(self, obj, event):
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
        if self.is_loading or self.current_page >= self.total_pages:
            return
        scrollbar = self.scroll_area.verticalScrollBar()
        if scrollbar.maximum() - value < 200:
            self.load_next_page()

    def emit_search(self):
        query = self.search_edit.text().strip()
        if query:
            self.search_requested.emit(query)

    def start_search(self, query: str):
        self.current_query = query
        if query == "":
            self.search_edit.setText("")
            self.search_edit.setPlaceholderText("Showing recent uploads...")
        else:
            self.search_edit.setText(query)
            self.search_edit.setPlaceholderText("Search wallpapers...")
        
        self.current_page = 1
        self.wallpapers = []
        self.total_pages = 1
        self.is_loading = True
        self.loading_progress.setVisible(True)
        self.results_container.setCurrentIndex(0)
        
        self._clear_grid()
        
        filter_values = self.filter_panel.get_filter_values()
        
        if self.extension.name == "Local":
            filter_values["download_folder"] = self.settings.download_folder
        
        self._start_search_worker(query, self.current_page, filter_values)

    def load_next_page(self):
        if self.is_loading or self.current_page >= self.total_pages:
            return
        
        self.is_loading = True
        self.loading_progress.setVisible(True)
        
        filter_values = self.filter_panel.get_filter_values()
        
        if self.extension.name == "Local":
            filter_values["download_folder"] = self.settings.download_folder
        
        self._start_search_worker(self.current_query, self.current_page + 1, filter_values)

    def _start_search_worker(self, query, page, filter_values):
        worker = SearchWorker(
            self.extension,
            query,
            page,
            **filter_values
        )
        worker.finished.connect(self.on_search_finished)
        worker.error.connect(self.on_search_error)
        worker.finished.connect(lambda *args: self._remove_worker(worker))
        worker.error.connect(lambda *args: self._remove_worker(worker))
        worker.start()
        self._active_workers.append(worker)

    def _remove_worker(self, worker):
        if worker in self._active_workers:
            self._active_workers.remove(worker)
        worker.deleteLater()

    def on_search_finished(self, wallpapers, page, total_pages):
        self.is_loading = False
        self.loading_progress.setVisible(False)

        if page == 1:
            self.wallpapers = wallpapers
            self.total_pages = total_pages
            self.current_page = 1
            if not wallpapers:
                self.show_no_results()
            else:
                self.results_container.setCurrentIndex(0)
                self.rebuild_grid()
                main_win = self.window()
                if hasattr(main_win, 'status_bar'):
                    if self.current_query == "":
                        main_win.status_bar.showMessage(f"Showing recent uploads (page 1/{total_pages})")
                    else:
                        main_win.status_bar.showMessage(f"Found {len(wallpapers)} wallpapers (page 1/{total_pages})")
        else:
            self.wallpapers.extend(wallpapers)
            self.current_page = page
            self.total_pages = total_pages
            self.append_to_grid(wallpapers)
            main_win = self.window()
            if hasattr(main_win, 'status_bar'):
                main_win.status_bar.showMessage(f"Loaded {len(wallpapers)} more wallpapers (page {page}/{total_pages})")

    def on_search_error(self, error_msg):
        self.is_loading = False
        self.loading_progress.setVisible(False)
        QMessageBox.critical(self, "Search Error", error_msg)

    def show_no_results(self):
        message = random.choice(NO_RESULTS_MESSAGES)
        self.no_results_label.setText(message)
        self.results_container.setCurrentIndex(1)

    def _clear_grid(self):
        """Clear grid and cache widgets for potential reuse."""
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
                if isinstance(widget, WallpaperWidget):
                    widget.cleanup()
                    wall_id = self.extension.get_wallpaper_id(widget.data)
                    if wall_id and len(self._widget_cache) < 100:
                        self._widget_cache[wall_id] = widget
                    else:
                        widget.deleteLater()

    def rebuild_grid(self):
        self._clear_grid()

        if not self.wallpapers:
            return

        self.update_columns_from_width()

        for i, wp in enumerate(self.wallpapers):
            row = i // self.columns
            col = i % self.columns
            widget = self._get_or_create_widget(wp)
            self.grid_layout.addWidget(widget, row, col)

        row_count = (len(self.wallpapers) - 1) // self.columns + 1
        self.grid_layout.setRowStretch(row_count, 1)
        self._trim_widget_cache()

    def append_to_grid(self, new_wallpapers):
        start_index = len(self.wallpapers) - len(new_wallpapers)
        for i, wp in enumerate(new_wallpapers):
            global_index = start_index + i
            row = global_index // self.columns
            col = global_index % self.columns
            widget = self._get_or_create_widget(wp)
            self.grid_layout.addWidget(widget, row, col)

        row_count = (len(self.wallpapers) - 1) // self.columns + 1
        self.grid_layout.setRowStretch(row_count, 1)

    def _get_or_create_widget(self, wp_data):
        """Get widget from cache or create new one."""
        wall_id = self.extension.get_wallpaper_id(wp_data)
        widget = self._widget_cache.pop(wall_id, None)
        
        if widget is not None:
            widget.data = wp_data
            widget.thumb_url = self.extension.get_thumbnail_url(wp_data)
            widget.download_folder = self.settings.download_folder
            widget.res_label.setText(self.extension.get_resolution(wp_data))
            widget.update_downloaded_status()
            widget.load_thumbnail()
        else:
            widget = WallpaperWidget(self.extension, wp_data, self.settings.download_folder)
            widget.download_triggered.connect(self.download_wallpaper)
            widget.expand_triggered.connect(self.expand_wallpaper)
            widget.set_wallpaper_triggered.connect(self.set_as_background)
        
        return widget

    def _trim_widget_cache(self):
        """Limit cache size to prevent memory bloat."""
        while len(self._widget_cache) > 50:
            _, widget = self._widget_cache.popitem()
            widget.deleteLater()

    def download_wallpaper(self, wallpaper_data):
        self.download_progress.emit(0)
        self.dl_worker = DownloadWorker(self.extension, wallpaper_data, self.settings.download_folder)
        self.dl_worker.finished.connect(self.on_download_finished)
        self.dl_worker.progress.connect(self.download_progress.emit)
        self.dl_worker.finished.connect(lambda *args: self._remove_worker(self.dl_worker))
        self.dl_worker.start()
        self._active_workers.append(self.dl_worker)

    def on_download_finished(self, success, filepath, filename, wall_id):
        self.download_finished.emit(success, filepath, filename, wall_id)
        if success:
            for i in range(self.grid_layout.count()):
                widget = self.grid_layout.itemAt(i).widget()
                if isinstance(widget, WallpaperWidget):
                    if self.extension.get_wallpaper_id(widget.data) == wall_id:
                        widget.update_downloaded_status()
                        break

    def expand_wallpaper(self, wallpaper_data):
        image_url = self.extension.get_download_url(wallpaper_data)
        if image_url:
            if os.path.exists(image_url):
                image_url = f"file://{os.path.abspath(image_url)}"
            self.overlay.resize(self.size())
            self.overlay.move(0, 0)
            self.overlay.show_image(image_url)
        else:
            QMessageBox.information(self, "Preview", "Original image URL not available.")

    def set_as_background(self, wallpaper_data):
        main_win = self.window()
        if hasattr(main_win, 'status_bar'):
            main_win.status_bar.showMessage("Setting wallpaper...")
        
        self.wallpaper_worker = WallpaperSetterWorker(
            wallpaper_data, self.extension, self.settings.download_folder
        )
        self.wallpaper_worker.finished.connect(self.on_wallpaper_set)
        self.wallpaper_worker.finished.connect(lambda *args: self._remove_worker(self.wallpaper_worker))
        self.wallpaper_worker.start()
        self._active_workers.append(self.wallpaper_worker)

    def on_wallpaper_set(self, success, message):
        main_win = self.window()
        if hasattr(main_win, 'status_bar'):
            if success:
                main_win.status_bar.showMessage("Wallpaper set successfully!")
            else:
                main_win.status_bar.showMessage(f"Failed to set wallpaper: {message}")

    def update_extension(self, new_extension: WallpaperExtension):
        self.extension = new_extension
        layout = self.layout()
        old_panel = self.filter_panel
        layout.removeWidget(old_panel)
        old_panel.deleteLater()
        
        for widget in self._widget_cache.values():
            widget.deleteLater()
        self._widget_cache.clear()

        self.filter_panel = FilterPanel(self.extension)
        self.filter_panel.filters_changed.connect(self.on_filters_changed)
        self.filter_panel.setVisible(self.filter_toggle_btn.isChecked())
        layout.insertWidget(1, self.filter_panel)