import os
import random
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QLabel, QScrollArea, QGridLayout, QFrame, QStackedWidget,
    QProgressBar, QMessageBox, QCheckBox, QComboBox, QSizePolicy,
    QToolButton, QShortcut, QGraphicsOpacityEffect
)
from PyQt5.QtCore import Qt, pyqtSignal, QSize, QThread, QTimer, QPropertyAnimation, QEasingCurve, QEvent
from PyQt5.QtGui import QIcon, QPixmap, QKeySequence, QWheelEvent
from core.extension import WallpaperExtension
from core.settings import Settings
from core.workers import SearchWorker, DownloadWorker, ThumbnailLoader, get_session
from core.wallpaper_manager import WallpaperSetterWorker
from .wallpaper_widget import WallpaperWidget
from .wallpaper_widget import WallpaperWidget, AnimatedToolButton


THUMB_SIZE = QSize(280, 158)
THUMB_PADDING = 12

# Modern dark theme color palette - matching main_window.py
COLOR_BG_PRIMARY = "#050508"
COLOR_BG_SECONDARY = "#0a0a0c"
COLOR_BG_TERTIARY = "#1e1e24"
COLOR_ACCENT_PRIMARY = "#00d4ff"
COLOR_ACCENT_SECONDARY = "#7b61ff"
COLOR_TEXT_PRIMARY = "#ffffff"
COLOR_TEXT_SECONDARY = "#a0a0b0"
COLOR_TEXT_MUTED = "#6a6a7a"
COLOR_BORDER = "#2a2a35"
COLOR_BORDER_HOVER = "#3a3a4a"

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


class AnimatedFilterPanel(QFrame):
    """Collapsible panel with smooth expand/collapse animation, scrollable content, and Apply button."""
    apply_clicked = pyqtSignal(dict)

    def __init__(self, extension: WallpaperExtension, parent=None):
        super().__init__(parent)
        self.extension = extension
        self.widgets = {}
        self._last_applied_values = None
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet(f"""
            AnimatedFilterPanel {{
                background-color: {COLOR_BG_TERTIARY};
                border-radius: 12px;
                border: 1px solid {COLOR_BORDER};
                padding: 0px;
            }}
        """)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        self.init_ui()
        self._animation = None

    def init_ui(self):
        panel_layout = QVBoxLayout(self)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(0)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setStyleSheet(f"""
            QScrollArea {{
                background-color: transparent;
                border: none;
            }}
            QScrollBar:vertical {{
                background: {COLOR_BG_TERTIARY};
                width: 8px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: {COLOR_BORDER};
                border-radius: 4px;
                min-height: 20px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                border: none;
                background: none;
            }}
        """)
        self.scroll_area.setMaximumHeight(400)

        content_widget = QWidget()
        content_widget.setStyleSheet("background-color: transparent;")
        main_layout = QVBoxLayout(content_widget)
        main_layout.setContentsMargins(12, 12, 12, 8)
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
            cat_label.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: 13px; font-weight: bold; background: transparent; border: none;")
            group_layout.addWidget(cat_label)

            if filter_type == "checkboxes":
                cb_container = QWidget()
                cb_layout = QHBoxLayout(cb_container)
                cb_layout.setContentsMargins(0, 0, 0, 0)
                cb_layout.setSpacing(16)

                for opt in options:
                    cb = QCheckBox(opt["label"])
                    cb.setChecked(opt.get("default", False))
                    cb.setStyleSheet(f"color: {COLOR_TEXT_PRIMARY}; background: transparent; border: none;")
                    cb_layout.addWidget(cb)
                    key = f"{filter_id}.{opt['id']}"
                    self.widgets[key] = cb

                cb_layout.addStretch()
                group_layout.addWidget(cb_container)

            elif filter_type == "dropdown":
                combo = QComboBox()
                combo.setStyleSheet(f"""
                    QComboBox {{
                        background-color: {COLOR_BG_SECONDARY};
                        border: 1px solid {COLOR_BORDER};
                        border-radius: 8px;
                        padding: 6px 12px;
                        color: {COLOR_TEXT_PRIMARY};
                        min-width: 150px;
                    }}
                    QComboBox:hover {{
                        border-color: {COLOR_BORDER_HOVER};
                    }}
                    QComboBox::drop-down {{
                        border: none;
                        width: 24px;
                    }}
                    QComboBox QAbstractItemView {{
                        background-color: {COLOR_BG_TERTIARY};
                        color: {COLOR_TEXT_PRIMARY};
                        border: 1px solid {COLOR_BORDER};
                        border-radius: 8px;
                        selection-background-color: {COLOR_ACCENT_PRIMARY};
                        selection-color: {COLOR_BG_PRIMARY};
                        padding: 4px;
                    }}
                """)

                default_index = 0
                for i, opt in enumerate(options):
                    combo.addItem(opt["label"], opt["id"])
                    if opt.get("default", False):
                        default_index = i

                combo.setCurrentIndex(default_index)
                group_layout.addWidget(combo)
                self.widgets[filter_id] = combo

            main_layout.addWidget(group_widget)

        # Apply button
        self.apply_btn = QPushButton("Apply Filters")
        self.apply_btn.setFixedHeight(36)
        self.apply_btn.setCursor(Qt.PointingHandCursor)
        self.apply_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_ACCENT_PRIMARY};
                color: {COLOR_BG_PRIMARY};
                border-radius: 8px;
                font-size: 13px;
                font-weight: 600;
                border: none;
            }}
            QPushButton:hover {{
                background-color: #33ddff;
            }}
            QPushButton:pressed {{
                background-color: #00a8cc;
            }}
            QPushButton:disabled {{
                background-color: {COLOR_BORDER};
                color: {COLOR_TEXT_MUTED};
            }}
        """)
        self.apply_btn.clicked.connect(self._on_apply_clicked)
        main_layout.addWidget(self.apply_btn)

        self.scroll_area.setWidget(content_widget)
        panel_layout.addWidget(self.scroll_area)

    def _on_apply_clicked(self):
        """Check if filters changed before emitting."""
        current_values = self.get_filter_values()
        if current_values != self._last_applied_values:
            self._last_applied_values = current_values.copy()
            self.apply_clicked.emit(current_values)

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

    def set_apply_enabled(self, enabled: bool):
        """Enable or disable the Apply button."""
        self.apply_btn.setEnabled(enabled)

    def reset_last_applied(self):
        """Clear the last applied values."""
        self._last_applied_values = None

    def animate_toggle(self, expand):
        if self._animation and self._animation.state() == QPropertyAnimation.Running:
            self._animation.stop()

        if expand:
            self.setVisible(True)
            self._animation = QPropertyAnimation(self, b"maximumHeight")
            self._animation.setDuration(250)
            self._animation.setStartValue(0)
            content_height = self.scroll_area.widget().sizeHint().height() + 24
            target_height = min(content_height, 400)
            self._animation.setEndValue(target_height)
            self._animation.setEasingCurve(QEasingCurve.OutCubic)
            self._animation.start()
        else:
            self._animation = QPropertyAnimation(self, b"maximumHeight")
            self._animation.setDuration(200)
            self._animation.setStartValue(self.height())
            self._animation.setEndValue(0)
            self._animation.setEasingCurve(QEasingCurve.InCubic)
            self._animation.finished.connect(lambda: self.setVisible(False))
            self._animation.start()


class FullImageLoader(QThread):
    """Loads the full resolution image for preview with safe cancellation."""
    loaded = pyqtSignal(QPixmap)
    error = pyqtSignal(str)

    def __init__(self, url):
        super().__init__()
        self.url = url
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
            if self.url.startswith("file://"):
                filepath = self.url[7:]
            else:
                filepath = self.url

            if os.path.exists(filepath):
                if self._is_cancelled:
                    return
                pixmap = QPixmap(filepath)
                if not pixmap.isNull():
                    self.loaded.emit(pixmap)
                else:
                    self.error.emit("Failed to load image from disk")
                return

            session = get_session()
            response = session.get(self.url, timeout=30, stream=True)
            if self._is_cancelled:
                return
            data = bytearray()
            for chunk in response.iter_content(chunk_size=8192):
                if self._is_cancelled:
                    return
                data.extend(chunk)
            pixmap = QPixmap()
            pixmap.loadFromData(data)
            if not self._is_cancelled:
                self.loaded.emit(pixmap)
        except Exception as e:
            if not self._is_cancelled:
                self.error.emit(str(e))


class ImageOverlay(QWidget):
    """Semi-transparent overlay showing the full image."""
    closed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background-color: rgba(15, 15, 18, 0.95);")
        self.setVisible(False)
        self.loader = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignCenter)

        self.loading_card = QFrame()
        self.loading_card.setFixedSize(220, 120)
        self.loading_card.setStyleSheet(f"""
            QFrame {{
                background-color: {COLOR_BG_TERTIARY};
                border-radius: 16px;
                border: 1px solid {COLOR_BORDER};
            }}
        """)
        card_layout = QVBoxLayout(self.loading_card)
        card_layout.setAlignment(Qt.AlignCenter)
        card_layout.setSpacing(10)
        card_layout.setContentsMargins(20, 16, 20, 16)

        self.spinner = QLabel("⟳")
        self.spinner.setAlignment(Qt.AlignCenter)
        self.spinner.setStyleSheet(f"""
            QLabel {{
                color: {COLOR_ACCENT_PRIMARY};
                font-size: 28px;
                background: transparent;
                font-weight: bold;
                border: none;
            }}
        """)
        card_layout.addWidget(self.spinner)

        self.loading_text = QLabel("Loading image")
        self.loading_text.setAlignment(Qt.AlignCenter)
        self.loading_text.setStyleSheet(f"""
            QLabel {{
                color: {COLOR_TEXT_SECONDARY};
                font-size: 14px;
                font-weight: 500;
                letter-spacing: 0.8px;
                background: transparent;
                border: none;
            }}
        """)
        card_layout.addWidget(self.loading_text)

        layout.addWidget(self.loading_card, alignment=Qt.AlignCenter)

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setScaledContents(False)
        layout.addWidget(self.image_label, alignment=Qt.AlignCenter)
        self.image_label.hide()

        self.hint = QLabel("Press ESC or click to close")
        self.hint.setAlignment(Qt.AlignCenter)
        self.hint.setStyleSheet(f"""
            color: {COLOR_TEXT_MUTED};
            font-size: 11px;
            background: transparent;
            padding: 12px;
            letter-spacing: 0.5px;
            border: none;
        """)
        layout.addWidget(self.hint, alignment=Qt.AlignCenter)

        QShortcut(QKeySequence("Escape"), self, self.close_overlay)

    def show_image(self, url):
        self.image_label.clear()
        self.image_label.hide()
        self.loading_card.setVisible(True)
        self.setVisible(True)
        self.raise_()

        self._cancel_loader()

        self.loader = FullImageLoader(url)
        self.loader.loaded.connect(self.on_image_loaded)
        self.loader.error.connect(self.on_load_error)
        self.loader.start()

    def _cancel_loader(self):
        if self.loader is None:
            return
        try:
            self.loader.cancel()
            try:
                self.loader.loaded.disconnect(self.on_image_loaded)
            except (TypeError, RuntimeError):
                pass
            try:
                self.loader.error.disconnect(self.on_load_error)
            except (TypeError, RuntimeError):
                pass
            if self.loader.isRunning():
                self.loader.quit()
                self.loader.wait(500)
        except RuntimeError:
            pass
        finally:
            self.loader = None

    def on_image_loaded(self, pixmap):
        self.loading_card.hide()
        self.image_label.show()
        if not pixmap.isNull():
            available = self.size() - QSize(60, 120)
            scaled = pixmap.scaled(available, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.image_label.setPixmap(scaled)
        else:
            self.image_label.setText("Failed to load image")

    def on_load_error(self, msg):
        self.loading_card.hide()
        self.image_label.show()
        self.image_label.setText(f"Error: {msg}")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.image_label.isVisible() and self.image_label.pixmap() and not self.image_label.pixmap().isNull():
            available = self.size() - QSize(60, 120)
            scaled = self.image_label.pixmap().scaled(available, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.image_label.setPixmap(scaled)

    def close_overlay(self):
        self._cancel_loader()
        self.loading_card.hide()
        self.image_label.hide()
        self.setVisible(False)
        self.closed.emit()

    def mousePressEvent(self, event):
        self.close_overlay()


class ResultsPage(QWidget):
    home_requested = pyqtSignal()
    search_requested = pyqtSignal(str)
    search_finished = pyqtSignal()
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
        self._widget_by_id = {}
        self._resize_timer = None
        self._scroll_animation = None

        # Search cancellation / stale result prevention
        self._current_search_worker = None
        self._search_request_id = 0
        self._current_filter_values = {}

        # Download queue management
        self._download_queue = []
        self._current_download_worker = None
        self._is_downloading = False

        self.init_ui()
        self.init_overlay()
        self._setup_loading_bar_animation()
        self._setup_smooth_scrolling()

    def _cancel_current_search_worker(self):
        """Safely cancel and clean up the current search worker."""
        if self._current_search_worker is None:
            return
        
        worker = self._current_search_worker
        self._current_search_worker = None
        
        try:
            worker.finished.disconnect()
            worker.error.disconnect()
        except (TypeError, RuntimeError):
            pass
        
        if worker.isRunning():
            worker.quit()
            if not worker.wait(500):
                worker.terminate()
                worker.wait(100)
        
        if worker in self._active_workers:
            self._active_workers.remove(worker)
        
        worker.deleteLater()

    def _cancel_current_download_worker(self):
        """Safely cancel the current download worker."""
        if self._current_download_worker is None:
            return
        
        worker = self._current_download_worker
        self._current_download_worker = None
        self._is_downloading = False
        
        try:
            worker.finished.disconnect()
            worker.progress.disconnect()
        except (TypeError, RuntimeError):
            pass
        
        if worker.isRunning():
            worker.quit()
            worker.wait(200)
        
        if worker in self._active_workers:
            self._active_workers.remove(worker)
        
        worker.deleteLater()

    def _cleanup_worker(self, worker):
        """Clean up a worker after it finishes."""
        if worker in self._active_workers:
            self._active_workers.remove(worker)
        if worker == self._current_search_worker:
            self._current_search_worker = None
        if worker == self._current_download_worker:
            self._current_download_worker = None
            self._is_downloading = False
        worker.deleteLater()

    def _setup_loading_bar_animation(self):
        self.loading_opacity = QGraphicsOpacityEffect(self.loading_progress)
        self.loading_progress.setGraphicsEffect(self.loading_opacity)
        self.loading_opacity.setOpacity(0.0)
        self.loading_progress.setVisible(True)

        self.loading_fade_anim = QPropertyAnimation(self.loading_opacity, b"opacity")
        self.loading_fade_anim.setDuration(250)
        self.loading_fade_anim.setEasingCurve(QEasingCurve.InOutCubic)

    def _fade_in_loading(self):
        if self.loading_fade_anim.state() == QPropertyAnimation.Running:
            self.loading_fade_anim.stop()
        self.loading_fade_anim.setStartValue(self.loading_opacity.opacity())
        self.loading_fade_anim.setEndValue(1.0)
        self.loading_fade_anim.start()

    def _fade_out_loading(self):
        if self.loading_fade_anim.state() == QPropertyAnimation.Running:
            self.loading_fade_anim.stop()
        self.loading_fade_anim.setStartValue(self.loading_opacity.opacity())
        self.loading_fade_anim.setEndValue(0.0)
        self.loading_fade_anim.start()

    def _setup_smooth_scrolling(self):
        self.scroll_area.viewport().installEventFilter(self)

    def eventFilter(self, obj, event):
        if obj == self.scroll_area.viewport() and event.type() == QEvent.Wheel:
            self._handle_wheel_event(event)
            return True
        return super().eventFilter(obj, event)

    def _handle_wheel_event(self, event: QWheelEvent):
        scrollbar = self.scroll_area.verticalScrollBar()
        current_val = scrollbar.value()
        max_val = scrollbar.maximum()

        delta = event.angleDelta().y()
        if delta == 0:
            return

        scroll_amount = -delta * 2
        target_val = current_val + scroll_amount
        target_val = max(0, min(target_val, max_val))

        if target_val == current_val:
            return

        if self._scroll_animation and self._scroll_animation.state() == QPropertyAnimation.Running:
            self._scroll_animation.stop()

        self._scroll_animation = QPropertyAnimation(scrollbar, b"value")
        self._scroll_animation.setDuration(150)
        self._scroll_animation.setStartValue(current_val)
        self._scroll_animation.setEndValue(target_val)
        self._scroll_animation.setEasingCurve(QEasingCurve.OutCubic)
        self._scroll_animation.start()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # Top bar
        top_bar = QHBoxLayout()
        top_bar.setSpacing(10)
        
        self.home_btn = AnimatedToolButton(no_glow=True)
        self.home_btn.setToolTip("Back to home")
        self.home_btn.setFixedSize(36, 36)
        self.home_btn.setCursor(Qt.PointingHandCursor)

        # SVG da casinha — stroke fino, centralizado
        _home_svg = b"""<svg width="18" height="18" viewBox="0 0 18 18" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M2 8.5L9 2L16 8.5V16H11.5V11.5H6.5V16H2V8.5Z"
                stroke="#e8e8f0" stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round"/>
        </svg>"""
        _home_px = QPixmap()
        _home_px.loadFromData(_home_svg, "SVG")
        self.home_btn.setIcon(QIcon(_home_px))
        self.home_btn.setIconSize(QSize(18, 18))

        self.home_btn.setStyleSheet(f"""
            AnimatedToolButton {{
                background-color: transparent;
                border: 1px solid {COLOR_BORDER};
                border-radius: 18px;
                padding: 0px;
            }}
            AnimatedToolButton:hover {{
                background-color: {COLOR_BORDER_HOVER};
                border-color: {COLOR_BORDER_HOVER};
            }}
        """)
        self.home_btn.clicked.connect(self.home_requested.emit)
        top_bar.addWidget(self.home_btn)

# ── Search bar ────────────────────────────────────────────────────
        # Container com fundo semitransparente, borda sutil e ícone SVG inline
        search_container = QFrame()
        search_container.setFixedHeight(40)
        search_container.setStyleSheet(f"""
            QFrame {{
                background-color: rgba(255, 255, 255, 0.04);
                border-radius: 10px;
                border: 1px solid rgba(255, 255, 255, 0.08);
            }}
            QFrame:focus-within {{
                border-color: rgba(0, 212, 255, 0.55);
                background-color: rgba(255, 255, 255, 0.06);
            }}
        """)

        search_layout = QHBoxLayout(search_container)
        search_layout.setContentsMargins(12, 0, 6, 0)
        search_layout.setSpacing(8)

        # Ícone SVG embutido — lupa moderna com stroke fino
        search_icon = QLabel()
        search_icon.setFixedSize(16, 16)
        search_icon.setStyleSheet("background: transparent; border: none;")
        svg_bytes = b"""<svg width="16" height="16" viewBox="0 0 16 16"
                fill="none" xmlns="http://www.w3.org/2000/svg">
            <circle cx="6.5" cy="6.5" r="4.5" stroke="#6a6a8a" stroke-width="1.5"/>
            <line x1="10.0" y1="10.0" x2="14.0" y2="14.0"
                  stroke="#6a6a8a" stroke-width="1.5" stroke-linecap="round"/>
        </svg>"""
        icon_pixmap = QPixmap()
        icon_pixmap.loadFromData(svg_bytes, "SVG")
        search_icon.setPixmap(icon_pixmap)
        search_layout.addWidget(search_icon, 0, Qt.AlignVCenter)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search wallpapers...")
        self.search_edit.setFrame(False)          # sem borda própria — o container já tem
        self.search_edit.setStyleSheet(f"""
            QLineEdit {{
                font-size: 13px;
                background: transparent;
                border: none;
                color: {COLOR_TEXT_PRIMARY};
                selection-background-color: {COLOR_ACCENT_PRIMARY};
                padding: 0px;
            }}
            QLineEdit::placeholder {{
                color: {COLOR_TEXT_MUTED};
            }}
        """)
        self.search_edit.returnPressed.connect(self.emit_search)
        search_layout.addWidget(self.search_edit, 1, Qt.AlignVCenter)

        self.filter_toggle_btn = AnimatedToolButton()
        self.filter_toggle_btn.setText("▼ Filters")
        self.filter_toggle_btn.setToolTip("Show/hide filters")
        self.filter_toggle_btn.setCheckable(True)
        self.filter_toggle_btn.setChecked(False)
        self.filter_toggle_btn.setFixedSize(100, 36)
        self.filter_toggle_btn.setCursor(Qt.PointingHandCursor)
        self.filter_toggle_btn.setStyleSheet(f"""
            AnimatedToolButton {{
                background-color: {COLOR_BG_TERTIARY};
                border-radius: 8px;
                border: 1px solid {COLOR_BORDER};
                color: {COLOR_TEXT_PRIMARY};
                font-size: 13px;
                font-weight: 500;
                padding: 0px 12px;
            }}
            AnimatedToolButton:disabled {{
                background-color: {COLOR_BG_SECONDARY};
                color: {COLOR_TEXT_MUTED};
                border-color: {COLOR_BORDER};
            }}
        """)
        self.filter_toggle_btn.clicked.connect(self.toggle_filter_panel)

        self.search_btn = AnimatedToolButton()
        self.search_btn.setText("Search")
        self.search_btn.setFixedSize(100, 36)
        self.search_btn.setCursor(Qt.PointingHandCursor)
        self.search_btn.clicked.connect(self.emit_search)
        # Troque o stylesheet do search_btn por:
        self.search_btn.setStyleSheet(f"""
            AnimatedToolButton {{
                background-color: {COLOR_ACCENT_PRIMARY};
                color: {COLOR_BG_PRIMARY};
                border-radius: 8px;
                border: 1px solid {COLOR_ACCENT_PRIMARY};
                font-size: 13px;
                font-weight: 600;
                padding: 0px 16px;
            }}
            AnimatedToolButton:disabled {{
                background-color: {COLOR_BORDER};
                color: {COLOR_TEXT_MUTED};
                border-color: {COLOR_BORDER};
            }}
        """)

        top_bar.addWidget(search_container, 3)
        top_bar.addWidget(self.filter_toggle_btn)  # ← aqui
        top_bar.addWidget(self.search_btn)         # ← aqui
        top_bar.addStretch()
        layout.addLayout(top_bar)

        # Filter panel
        self.filter_panel = AnimatedFilterPanel(self.extension)
        self.filter_panel.apply_clicked.connect(self.on_apply_filters)
        self.filter_panel.setVisible(False)
        layout.addWidget(self.filter_panel)

        # Initialize filter values from panel defaults
        self._current_filter_values = self.filter_panel.get_filter_values()

        # Results container
        self.results_container = QStackedWidget()
        layout.addWidget(self.results_container)

        # Scroll area
        scroll_container = QWidget()
        scroll_layout = QVBoxLayout(scroll_container)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(0)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setStyleSheet(f"""
            QScrollArea {{
                border: none;
                background: transparent;
            }}
        """)

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
        scroll_layout.addWidget(self.scroll_area)

        self.scroll_to_top_btn = AnimatedToolButton(no_glow=True)
        self.scroll_to_top_btn.setText("↑")
        self.scroll_to_top_btn.setFixedSize(40, 40)
        self.scroll_to_top_btn.setCursor(Qt.PointingHandCursor)
        self.scroll_to_top_btn.setStyleSheet(f"""
            AnimatedToolButton {{
                background-color: {COLOR_ACCENT_PRIMARY};
                border-radius: 20px;
                color: {COLOR_BG_PRIMARY};
                font-size: 20px;
                font-weight: bold;
                border: none;
            }}
            AnimatedToolButton:disabled {{
                background-color: {COLOR_BORDER};
                color: {COLOR_TEXT_MUTED};
            }}
        """)
        self.scroll_to_top_btn.clicked.connect(self.scroll_to_top)
        self.scroll_to_top_btn.setParent(scroll_container)
        self.scroll_to_top_btn.hide()

        self.results_container.addWidget(scroll_container)

        # No results
        self.no_results_widget = QWidget()
        no_results_layout = QVBoxLayout(self.no_results_widget)
        no_results_layout.setAlignment(Qt.AlignCenter)
        self.no_results_label = QLabel()
        self.no_results_label.setAlignment(Qt.AlignCenter)
        self.no_results_label.setStyleSheet(f"""
            color: {COLOR_TEXT_SECONDARY}; 
            font-size: 18px; 
            padding: 40px;
            background: transparent;
            border: none;
        """)
        self.no_results_label.setWordWrap(True)
        no_results_layout.addWidget(self.no_results_label)
        self.results_container.addWidget(self.no_results_widget)

        # Loading indicator
        self.loading_progress = QProgressBar()
        self.loading_progress.setVisible(True)
        self.loading_progress.setRange(0, 0)
        self.loading_progress.setTextVisible(False)
        self.loading_progress.setMaximumHeight(3)
        self.loading_progress.setStyleSheet(f"""
            QProgressBar {{
                background-color: {COLOR_BG_PRIMARY};
                border: none;
                border-radius: 1px;
                max-height: 3px;
                min-height: 3px;
            }}
            QProgressBar::chunk {{
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                    stop:0 {COLOR_ACCENT_SECONDARY}, stop:0.5 {COLOR_ACCENT_PRIMARY}, stop:1 {COLOR_ACCENT_SECONDARY});
                border-radius: 1px;
            }}
        """)
        layout.addWidget(self.loading_progress)

        self.scroll_area.verticalScrollBar().valueChanged.connect(self.on_scroll)
        scroll_container.resizeEvent = self._scroll_container_resize_event

    def _scroll_container_resize_event(self, event):
        QWidget.resizeEvent(self.scroll_area.parent(), event)
        self._position_scroll_button()

    def _position_scroll_button(self):
        if not hasattr(self, 'scroll_to_top_btn'):
            return
        btn = self.scroll_to_top_btn
        sa = self.scroll_area
        x = sa.x() + sa.width() - btn.width() - 20
        y = sa.y() + sa.height() - btn.height() - 20
        btn.move(x, y)
        btn.raise_()

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
        self._resize_timer.start(150)

        QTimer.singleShot(0, self._position_scroll_button)

    def _do_resize(self):
        if self.update_columns_from_width() and self.wallpapers:
            self.relayout_grid()

    def on_overlay_closed(self):
        self.activateWindow()

    def toggle_filter_panel(self):
        is_visible = self.filter_panel.isVisible()
        if is_visible:
            self.filter_panel.animate_toggle(False)
            self.filter_toggle_btn.setText("▼ Filters")
        else:
            self.filter_panel.animate_toggle(True)
            self.filter_toggle_btn.setText("▲ Filters")

    def on_apply_filters(self, filter_values):
        """Called when user clicks Apply in filter panel."""
        self._current_filter_values = filter_values.copy()
        self.filter_panel.set_apply_enabled(False)
        self.start_search(self.current_query)

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
        scrollbar = self.scroll_area.verticalScrollBar()
        self.scroll_to_top_btn.setVisible(scrollbar.value() > 200)

        if self.is_loading or self.current_page >= self.total_pages:
            return
        if scrollbar.maximum() - value < 200:
            self.load_next_page()

    def scroll_to_top(self):
        scrollbar = self.scroll_area.verticalScrollBar()
        current_val = scrollbar.value()
        if current_val == 0:
            return

        if self._scroll_animation and self._scroll_animation.state() == QPropertyAnimation.Running:
            self._scroll_animation.stop()

        self._scroll_animation = QPropertyAnimation(scrollbar, b"value")
        self._scroll_animation.setDuration(300)
        self._scroll_animation.setStartValue(current_val)
        self._scroll_animation.setEndValue(0)
        self._scroll_animation.setEasingCurve(QEasingCurve.OutCubic)
        self._scroll_animation.start()

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
        self._fade_in_loading()
        self.results_container.setCurrentIndex(0)

        self._clear_grid()

        # Cancel any ongoing search worker safely
        self._cancel_current_search_worker()

        # Prepare filter values with download_folder for Local extension
        filter_values = self._current_filter_values.copy()
        if self.extension.name == "Local":
            filter_values["download_folder"] = self.settings.download_folder

        self._start_search_worker(query, self.current_page, filter_values)

    def load_next_page(self):
        if self.is_loading or self.current_page >= self.total_pages:
            return

        self.is_loading = True
        self._fade_in_loading()

        filter_values = self._current_filter_values.copy()
        if self.extension.name == "Local":
            filter_values["download_folder"] = self.settings.download_folder

        self._start_search_worker(self.current_query, self.current_page + 1, filter_values)

    def _start_search_worker(self, query, page, filter_values):
        self._search_request_id += 1
        request_id = self._search_request_id

        worker = SearchWorker(self.extension, query, page, **filter_values)
        worker.finished.connect(lambda w, p, t, rid=request_id: self._on_search_finished_safe(w, p, t, rid))
        worker.error.connect(lambda msg, rid=request_id: self._on_search_error_safe(msg, rid))
        worker.finished.connect(lambda *args, w=worker: self._cleanup_worker(w))
        worker.error.connect(lambda *args, w=worker: self._cleanup_worker(w))
        worker.start()
        self._current_search_worker = worker
        self._active_workers.append(worker)

    def _on_search_finished_safe(self, wallpapers, page, total_pages, request_id):
        if request_id != self._search_request_id:
            return
        self.on_search_finished(wallpapers, page, total_pages)

    def _on_search_error_safe(self, error_msg, request_id):
        if request_id != self._search_request_id:
            return
        self.on_search_error(error_msg)

    def _remove_worker(self, worker):
        """General worker removal."""
        if worker in self._active_workers:
            self._active_workers.remove(worker)
        if worker == self._current_search_worker:
            self._current_search_worker = None
        if worker == self._current_download_worker:
            self._current_download_worker = None
            self._is_downloading = False
        worker.deleteLater()

    def on_search_finished(self, wallpapers, page, total_pages):
        self.is_loading = False
        self._fade_out_loading()
        self.search_finished.emit()
        self.filter_panel.set_apply_enabled(True)

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

        QTimer.singleShot(0, self._position_scroll_button)

    def on_search_error(self, error_msg):
        self.is_loading = False
        self._fade_out_loading()
        self.search_finished.emit()
        self.filter_panel.set_apply_enabled(True)
        QMessageBox.critical(self, "Search Error", error_msg)

    def show_no_results(self):
        message = random.choice(NO_RESULTS_MESSAGES)
        self.no_results_label.setText(f"🔍\n\n{message}")
        self.results_container.setCurrentIndex(1)

    def _clear_grid(self):
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
        self._widget_by_id.clear()

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
            wall_id = self.extension.get_wallpaper_id(wp)
            self._widget_by_id[wall_id] = widget

        row_count = (len(self.wallpapers) - 1) // self.columns + 1
        self.grid_layout.setRowStretch(row_count, 1)
        self._trim_widget_cache()

    def relayout_grid(self):
        if not self.wallpapers:
            return

        while self.grid_layout.count():
            self.grid_layout.takeAt(0)

        for i, wp in enumerate(self.wallpapers):
            row = i // self.columns
            col = i % self.columns
            wall_id = self.extension.get_wallpaper_id(wp)
            widget = self._widget_by_id.get(wall_id)
            if widget is None:
                widget = self._get_or_create_widget(wp)
                self._widget_by_id[wall_id] = widget
            self.grid_layout.addWidget(widget, row, col)

        row_count = (len(self.wallpapers) - 1) // self.columns + 1
        self.grid_layout.setRowStretch(row_count, 1)

    def append_to_grid(self, new_wallpapers):
        start_index = len(self.wallpapers) - len(new_wallpapers)
        for i, wp in enumerate(new_wallpapers):
            global_index = start_index + i
            row = global_index // self.columns
            col = global_index % self.columns
            widget = self._get_or_create_widget(wp)
            self.grid_layout.addWidget(widget, row, col)
            wall_id = self.extension.get_wallpaper_id(wp)
            self._widget_by_id[wall_id] = widget

        row_count = (len(self.wallpapers) - 1) // self.columns + 1
        self.grid_layout.setRowStretch(row_count, 1)

    def _get_or_create_widget(self, wp_data):
        wall_id = self.extension.get_wallpaper_id(wp_data)
        widget = self._widget_cache.pop(wall_id, None)

        if widget is not None:
            widget.data = wp_data
            widget.thumb_url = self.extension.get_thumbnail_url(wp_data)
            widget.download_folder = self.settings.download_folder
            widget.res_label.setText(self.extension.get_resolution(wp_data))
            widget.update_downloaded_status()
            widget.update_active_status()
            widget.load_thumbnail()
        else:
            widget = WallpaperWidget(self.extension, wp_data, self.settings.download_folder)
            widget.download_triggered.connect(self.download_wallpaper)
            widget.expand_triggered.connect(self.expand_wallpaper)
            widget.set_wallpaper_triggered.connect(self.set_as_background)

        return widget

    def _trim_widget_cache(self):
        while len(self._widget_cache) > 50:
            _, widget = self._widget_cache.popitem()
            widget.deleteLater()

    def download_wallpaper(self, wallpaper_data):
        """Queue a wallpaper for download."""
        self._download_queue.append(wallpaper_data)
        self._process_download_queue()

    def _process_download_queue(self):
        """Process the next item in the download queue."""
        if self._is_downloading or not self._download_queue:
            return
        
        wallpaper_data = self._download_queue.pop(0)
        self._is_downloading = True
        
        queue_size = len(self._download_queue)
        filename = self.extension.get_wallpaper_id(wallpaper_data)
        ext = self.extension.get_file_extension(wallpaper_data)
        
        if queue_size > 0:
            status_msg = f"Downloading 1 of {queue_size + 1}: {filename}.{ext}"
        else:
            status_msg = f"Downloading: {filename}.{ext}"
        
        main_win = self.window()
        if hasattr(main_win, 'status_bar'):
            main_win.status_bar.showMessage(status_msg)
        
        self.download_progress.emit(0)
        
        worker = DownloadWorker(self.extension, wallpaper_data, self.settings.download_folder)
        worker.finished.connect(self._on_download_finished_safe)
        worker.progress.connect(self.download_progress.emit)
        worker.start()
        
        self._current_download_worker = worker
        self._active_workers.append(worker)

    def _on_download_finished_safe(self, success, filepath, filename, wall_id):
        """Handle download completion and process next in queue."""
        self._is_downloading = False
        self._current_download_worker = None
        
        self.download_finished.emit(success, filepath, filename, wall_id)
        
        if success:
            for i in range(self.grid_layout.count()):
                widget = self.grid_layout.itemAt(i).widget()
                if isinstance(widget, WallpaperWidget):
                    if self.extension.get_wallpaper_id(widget.data) == wall_id:
                        widget.update_downloaded_status()
                        break
            
            main_win = self.window()
            if hasattr(main_win, 'status_bar'):
                if self._download_queue:
                    remaining = len(self._download_queue)
                    main_win.status_bar.showMessage(f"Downloaded: {filename} ({remaining} remaining)")
                else:
                    main_win.status_bar.showMessage(f"Downloaded: {filename}")
        else:
            main_win = self.window()
            if hasattr(main_win, 'status_bar'):
                main_win.status_bar.showMessage(f"Download failed: {filename}")
        
        QTimer.singleShot(100, self._process_download_queue)

    def on_download_finished(self, success, filepath, filename, wall_id):
        """Kept for compatibility."""
        pass

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

        for i in range(self.grid_layout.count()):
            widget = self.grid_layout.itemAt(i).widget()
            if isinstance(widget, WallpaperWidget):
                widget.wallpaper_btn.setEnabled(False)
                widget.wallpaper_btn.setText("⟳")
                widget.wallpaper_btn.setToolTip("Setting wallpaper...")

        self.wallpaper_worker = WallpaperSetterWorker(
            wallpaper_data, self.extension, self.settings.download_folder
        )
        self.wallpaper_worker.finished.connect(lambda s, m, p: self._on_wallpaper_set_complete(s, m))
        self.wallpaper_worker.finished.connect(lambda *args: self._remove_worker(self.wallpaper_worker))
        self.wallpaper_worker.start()
        self._active_workers.append(self.wallpaper_worker)

    def _on_wallpaper_set_complete(self, success, message):
        """Handle wallpaper set completion for all widgets."""
        main_win = self.window()
        if hasattr(main_win, 'status_bar'):
            if success:
                main_win.status_bar.showMessage("Wallpaper set successfully!")
            else:
                main_win.status_bar.showMessage(f"Failed to set wallpaper: {message}")

        for i in range(self.grid_layout.count()):
            widget = self.grid_layout.itemAt(i).widget()
            if isinstance(widget, WallpaperWidget):
                widget.on_wallpaper_set_complete(success)

    def on_wallpaper_set(self, success, message):
        """Kept for compatibility."""
        self._on_wallpaper_set_complete(success, message)

    def update_extension(self, new_extension: WallpaperExtension):
        self.extension = new_extension
        layout = self.layout()
        old_panel = self.filter_panel
        layout.removeWidget(old_panel)
        old_panel.deleteLater()

        for widget in self._widget_cache.values():
            widget.deleteLater()
        self._widget_cache.clear()
        self._widget_by_id.clear()

        self.filter_panel = AnimatedFilterPanel(self.extension)
        self.filter_panel.apply_clicked.connect(self.on_apply_filters)
        self.filter_panel.reset_last_applied()
        self.filter_panel.setVisible(self.filter_toggle_btn.isChecked())
        layout.insertWidget(1, self.filter_panel)

        has_filters = bool(self.extension.get_filters())
        self.filter_toggle_btn.setEnabled(has_filters)
        self.filter_toggle_btn.setVisible(has_filters)
        if not has_filters:
            self.filter_panel.setVisible(False)

        self._current_filter_values = self.filter_panel.get_filter_values()

    def ensure_filter_collapsed(self):
        if self.filter_panel.isVisible():
            self.filter_panel.animate_toggle(False)
            self.filter_toggle_btn.setChecked(False)
            self.filter_toggle_btn.setText("▼ Filters")

    def closeEvent(self, event):
        """Clean up any running workers when the page is closed."""
        self._cancel_current_search_worker()
        self._cancel_current_download_worker()
        
        self._download_queue.clear()
        
        for worker in self._active_workers[:]:
            if worker.isRunning():
                worker.quit()
                worker.wait(200)
            if worker in self._active_workers:
                self._active_workers.remove(worker)
            worker.deleteLater()
        self._active_workers.clear()
        
        super().closeEvent(event)