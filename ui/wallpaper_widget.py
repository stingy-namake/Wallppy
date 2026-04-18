import os
from PyQt5.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QSizePolicy,
    QToolButton, QWidget, QGraphicsOpacityEffect
)
from PyQt5.QtCore import Qt, pyqtSignal, QSize, QTimer, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QPixmap, QPainter, QColor, QLinearGradient, QBrush
from core.extension import WallpaperExtension
from core.workers import ThumbnailLoader


THUMB_SIZE = QSize(280, 158)

# Shimmer placeholder
class ShimmerLabel(QLabel):
    """Label with animated shimmer effect while loading."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(THUMB_SIZE)
        self.setAlignment(Qt.AlignCenter)
        self.setScaledContents(True)
        self._shimmer_anim = None
        self._shimmer_value = 0.0
        self._base_color = QColor(45, 45, 50)
        self._highlight = QColor(70, 70, 80)

    def paintEvent(self, event):
        if self.pixmap() and not self.pixmap().isNull():
            super().paintEvent(event)
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        # Draw base rect
        painter.setPen(Qt.NoPen)
        painter.setBrush(self._base_color)
        painter.drawRoundedRect(self.rect(), 6, 6)

        # Draw shimmer gradient
        gradient = QLinearGradient(0, 0, self.width(), 0)
        pos = self._shimmer_value
        gradient.setColorAt(max(0, pos - 0.3), self._base_color)
        gradient.setColorAt(pos, self._highlight)
        gradient.setColorAt(min(1, pos + 0.3), self._base_color)
        painter.setBrush(QBrush(gradient))
        painter.drawRoundedRect(self.rect(), 6, 6)

    def start_shimmer(self):
        if self._shimmer_anim:
            return
        self._shimmer_anim = QPropertyAnimation(self, b"_shimmer_value")
        self._shimmer_anim.setDuration(1200)
        self._shimmer_anim.setStartValue(-0.5)
        self._shimmer_anim.setEndValue(1.5)
        self._shimmer_anim.setLoopCount(-1)
        self._shimmer_anim.setEasingCurve(QEasingCurve.InOutSine)
        self._shimmer_anim.start()

    def stop_shimmer(self):
        if self._shimmer_anim:
            self._shimmer_anim.stop()
            self._shimmer_anim = None
        self._shimmer_value = 0.0
        self.update()

    def set_shimmer_value(self, value):
        self._shimmer_value = value
        self.update()

    _shimmer_value = 0.0


class WallpaperWidget(QFrame):
    download_triggered = pyqtSignal(dict)
    expand_triggered = pyqtSignal(dict)
    set_wallpaper_triggered = pyqtSignal(dict)

    def __init__(self, extension: WallpaperExtension, wallpaper_data: dict, download_folder: str, parent=None):
        super().__init__(parent)
        self.extension = extension
        self.data = wallpaper_data
        self.download_folder = download_folder
        self.thumb_url = extension.get_thumbnail_url(wallpaper_data)
        self._thumb_loader = None
        self._loaded = False

        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet("""
            WallpaperWidget {
                background-color: #2a2a2f;
                border-radius: 10px;
                border: 1px solid #3a3a40;
            }
            WallpaperWidget:hover {
                background-color: #323238;
                border-color: #4a4a50;
            }
        """)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.init_ui()
        self.setup_hover_animation()
        QTimer.singleShot(0, self.load_thumbnail)

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self.thumb_label = ShimmerLabel()
        self.thumb_label.setAlignment(Qt.AlignCenter)
        self.thumb_label.setStyleSheet("""
            QLabel {
                background-color: #1e1e22;
                border-radius: 8px;
                border: 1px solid #2a2a2f;
            }
            QLabel:hover {
                border: 2px solid #1E6FF0;
            }
        """)
        self.thumb_label.setCursor(Qt.PointingHandCursor)
        self.thumb_label.start_shimmer()
        layout.addWidget(self.thumb_label, alignment=Qt.AlignHCenter)

        bottom_layout = QHBoxLayout()
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(12)

        # Active indicator
        self.active_indicator = QToolButton()
        self.active_indicator.setText("★")
        self.active_indicator.setToolTip("Current wallpaper")
        self.active_indicator.setStyleSheet("""
            QToolButton {
                background-color: #1E6FF0;
                border-radius: 4px;
                border: none;
                color: white;
                font-size: 12px;
                padding: 6px 0px;
                font-weight: bold;
            }
        """)
        self.active_indicator.setFixedSize(36, 30)
        self.active_indicator.hide()
        bottom_layout.addWidget(self.active_indicator)

        # Downloaded indicator
        self.checkmark_btn = QToolButton()
        self.checkmark_btn.setText("✓")
        self.checkmark_btn.setToolTip("Downloaded")
        self.checkmark_btn.setStyleSheet("""
            QToolButton {
                background-color: #2ea043;
                border-radius: 4px;
                border: none;
                color: white;
                font-size: 12px;
                padding: 6px 0px;
                font-weight: bold;
            }
        """)
        self.checkmark_btn.setFixedSize(36, 30)
        self.checkmark_btn.hide()
        bottom_layout.addWidget(self.checkmark_btn)

        res = self.extension.get_resolution(self.data)
        self.res_label = QLabel(res)
        self.res_label.setStyleSheet("color: #aaa; font-size: 12px;")
        bottom_layout.addWidget(self.res_label)

        bottom_layout.addStretch()

        BUTTON_STYLE = """
            QToolButton {
                background-color: rgba(60, 60, 65, 0.9);
                border-radius: 6px;
                border: none;
                color: white;
                font-size: 14px;
                padding: 6px 0px;
            }
            QToolButton:hover {
                background-color: rgba(80, 80, 85, 1);
            }
        """

        self.expand_btn = QToolButton()
        self.expand_btn.setText("⤢")
        self.expand_btn.setToolTip("Expand Preview")
        self.expand_btn.setCursor(Qt.PointingHandCursor)
        self.expand_btn.setStyleSheet(BUTTON_STYLE)
        self.expand_btn.setFixedSize(36, 30)
        self.expand_btn.clicked.connect(lambda: self.expand_triggered.emit(self.data))
        bottom_layout.addWidget(self.expand_btn)

        self.wallpaper_btn = QToolButton()
        self.wallpaper_btn.setText("🖵")
        self.wallpaper_btn.setToolTip("Set as Desktop Background")
        self.wallpaper_btn.setCursor(Qt.PointingHandCursor)
        self.wallpaper_btn.setStyleSheet(BUTTON_STYLE)
        self.wallpaper_btn.setFixedSize(36, 30)
        self.wallpaper_btn.clicked.connect(lambda: self.set_wallpaper_triggered.emit(self.data))
        bottom_layout.addWidget(self.wallpaper_btn)

        layout.addLayout(bottom_layout)
        self.setLayout(layout)
        self.setFixedSize(THUMB_SIZE.width() + 20, THUMB_SIZE.height() + 54)

    def setup_hover_animation(self):
        self._hover_anim = QPropertyAnimation(self, b"graphicsEffect")
        self._hover_anim.setDuration(150)
        self._opacity_effect = QGraphicsOpacityEffect()
        self._opacity_effect.setOpacity(1.0)
        self.setGraphicsEffect(self._opacity_effect)

    def enterEvent(self, event):
        self._hover_anim.stop()
        self._hover_anim.setEndValue(0.95)
        self._hover_anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover_anim.stop()
        self._hover_anim.setEndValue(1.0)
        self._hover_anim.start()
        super().leaveEvent(event)

    def _is_loader_running(self):
        if not self._thumb_loader:
            return False
        try:
            return self._thumb_loader.isRunning()
        except RuntimeError:
            self._thumb_loader = None
            return False

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.emit_download()

    def showEvent(self, event):
        super().showEvent(event)
        self.update_downloaded_status()
        self.update_active_status()

    def update_downloaded_status(self):
        wall_id = self.extension.get_wallpaper_id(self.data)
        ext = self.extension.get_file_extension(self.data)
        filename = f"wallppy-{wall_id}.{ext}"
        filepath = os.path.join(self.download_folder, filename)
        if os.path.exists(filepath):
            self.checkmark_btn.show()
        else:
            self.checkmark_btn.hide()

    def update_active_status(self):
        from core.wallpaper_manager import WallpaperManager
        current = WallpaperManager.get_current_wallpaper()
        if not current:
            self.active_indicator.hide()
            return

        wall_id = self.extension.get_wallpaper_id(self.data)
        ext = self.extension.get_file_extension(self.data)
        downloaded = os.path.join(self.download_folder, f"wallppy-{wall_id}.{ext}")
        direct = self.extension.get_download_url(self.data) or ""

        current_abs = os.path.abspath(current)
        if current_abs == os.path.abspath(downloaded):
            self.active_indicator.show()
        elif direct and current_abs == os.path.abspath(direct):
            self.active_indicator.show()
        else:
            self.active_indicator.hide()

    def load_thumbnail(self):
        if self._loaded or not self.thumb_url:
            if not self.thumb_url:
                self.thumb_label.stop_shimmer()
                self.thumb_label.setText("No preview")
            return

        if self._is_loader_running():
            self._thumb_loader.terminate()
            self._thumb_loader.wait(100)

        if os.path.exists(self.thumb_url):
            pixmap = QPixmap(self.thumb_url)
            if not pixmap.isNull():
                scaled = pixmap.scaled(THUMB_SIZE, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.thumb_label.stop_shimmer()
                self.thumb_label.setPixmap(scaled)
                self._loaded = True
            else:
                self.thumb_label.stop_shimmer()
                self.thumb_label.setText("Invalid")
            self.update_downloaded_status()
            self.update_active_status()
            return

        self._thumb_loader = ThumbnailLoader(self.thumb_url)
        self._thumb_loader.loaded.connect(self.set_thumbnail)
        self._thumb_loader.finished.connect(self._thumb_loader.deleteLater)
        self._thumb_loader.start()

    def set_thumbnail(self, pixmap: QPixmap):
        if not pixmap.isNull():
            scaled = pixmap.scaled(THUMB_SIZE, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.thumb_label.stop_shimmer()
            self.thumb_label.setPixmap(scaled)
            self._loaded = True
        else:
            self.thumb_label.stop_shimmer()
            self.thumb_label.setText("Load failed")
        self.update_downloaded_status()
        self.update_active_status()

    def emit_download(self):
        self.download_triggered.emit(self.data)

    def cleanup(self):
        if self._is_loader_running():
            self._thumb_loader.terminate()
            self._thumb_loader.wait(100)
        self._thumb_loader = None
        self._loaded = False
        self.thumb_label.stop_shimmer()
        self.thumb_label.start_shimmer()
        self.checkmark_btn.hide()
        self.active_indicator.hide()