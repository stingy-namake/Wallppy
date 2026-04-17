import os
from PyQt5.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QSizePolicy,
    QToolButton, QMessageBox, QWidget
)
from PyQt5.QtCore import Qt, pyqtSignal, QSize, QTimer
from PyQt5.QtGui import QPixmap
from core.extension import WallpaperExtension
from core.workers import ThumbnailLoader
from core.wallpaper_manager import WallpaperSetterWorker, WallpaperManager


THUMB_SIZE = QSize(280, 158)

_placeholder_pixmap = None

def get_placeholder():
    global _placeholder_pixmap
    if _placeholder_pixmap is None:
        _placeholder_pixmap = QPixmap(THUMB_SIZE)
        _placeholder_pixmap.fill(Qt.darkGray)
    return _placeholder_pixmap


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
        self._wallpaper_worker = None
        self._thumb_loader = None
        self._loaded = False
        
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet("""
            WallpaperWidget {
                background-color: #2d2d2d;
                border-radius: 8px;
                border: 1px solid #333;
            }
            WallpaperWidget:hover {
                background-color: #323232;
                border-color: #3d3d3d;
            }
        """)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.init_ui()
        QTimer.singleShot(0, self.load_thumbnail)

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        self.thumb_label = QLabel()
        self.thumb_label.setFixedSize(THUMB_SIZE)
        self.thumb_label.setAlignment(Qt.AlignCenter)
        self.thumb_label.setStyleSheet("""
            QLabel {
                background-color: #1e1e1e;
                border-radius: 6px;
                border: 1px solid #262626;
            }
            QLabel:hover {
                border: 2px solid #1E6FF0;
            }
        """)
        self.thumb_label.setScaledContents(True)
        self.thumb_label.setCursor(Qt.PointingHandCursor)
        self.thumb_label.setPixmap(get_placeholder())
        layout.addWidget(self.thumb_label, alignment=Qt.AlignHCenter)

        layout.addStretch()

        bottom_layout = QHBoxLayout()
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(16)

        # ===== ACTIVE WALLPAPER INDICATOR =====
        self.active_indicator = QToolButton()
        self.active_indicator.setText("★")
        self.active_indicator.setToolTip("Current wallpaper")
        self.active_indicator.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.active_indicator.setStyleSheet("""
            QToolButton {
                background-color: rgba(30, 111, 240, 0.85);
                border-radius: 4px;
                border: none;
                color: white;
                font-size: 12px;
                padding-top: 7px;
                padding-bottom: 7px;
                text-align: center;
                font-weight: bold;
            }
        """)
        self.active_indicator.setFixedSize(36, 30)
        self.active_indicator.hide()
        bottom_layout.addWidget(self.active_indicator)

        # Checkmark button (downloaded)
        self.checkmark_btn = QToolButton()
        self.checkmark_btn.setText("🗂")
        self.checkmark_btn.setToolTip("Downloaded")
        self.checkmark_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.checkmark_btn.setStyleSheet("""
            QToolButton {
                background-color: rgba(0, 180, 0, 0.85);
                border-radius: 4px;
                border: none;
                color: white;
                font-size: 12px;
                padding-top: 7px;
                padding-bottom: 7px;
                text-align: center;
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
                background-color: rgba(60, 60, 60, 0.8);
                border-radius: 4px;
                border: none;
                color: white;
                font-size: 14px;
                padding-top: 7px;
                padding-bottom: 7px;
                text-align: center;
            }
            QToolButton:hover {
                background-color: rgba(80, 80, 80, 1);
            }
        """

        self.expand_btn = QToolButton()
        self.expand_btn.setText("⤢")
        self.expand_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.expand_btn.setToolTip("Expand Preview")
        self.expand_btn.setCursor(Qt.PointingHandCursor)
        self.expand_btn.setStyleSheet(BUTTON_STYLE)
        self.expand_btn.setFixedSize(36, 30)
        self.expand_btn.clicked.connect(lambda: self.expand_triggered.emit(self.data))
        bottom_layout.addWidget(self.expand_btn)

        self.wallpaper_btn = QToolButton()
        self.wallpaper_btn.setText("🖵")
        self.wallpaper_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.wallpaper_btn.setToolTip("Set as Desktop Background")
        self.wallpaper_btn.setCursor(Qt.PointingHandCursor)
        self.wallpaper_btn.setStyleSheet(BUTTON_STYLE)
        self.wallpaper_btn.setFixedSize(36, 30)
        self.wallpaper_btn.clicked.connect(self.set_as_wallpaper)
        bottom_layout.addWidget(self.wallpaper_btn)

        layout.addLayout(bottom_layout)
        self.setLayout(layout)
        self.setFixedSize(THUMB_SIZE.width() + 20, THUMB_SIZE.height() + 54)

    def _is_loader_running(self):
        """Safely check if thumbnail loader is active (handles deleted C++ objects)."""
        if not self._thumb_loader:
            return False
        try:
            return self._thumb_loader.isRunning()
        except RuntimeError:
            self._thumb_loader = None
            return False

    def set_as_wallpaper(self):
        self._wallpaper_worker = WallpaperSetterWorker(
            self.data, self.extension, self.download_folder
        )
        self._wallpaper_worker.finished.connect(self._on_wallpaper_set)
        self._wallpaper_worker.start()
        self.wallpaper_btn.setEnabled(False)
        self.wallpaper_btn.setToolTip("Setting wallpaper...")

    def _on_wallpaper_set(self, success: bool, message: str, filepath: str):
        self.wallpaper_btn.setEnabled(True)
        self.wallpaper_btn.setToolTip("Set as Desktop Background" if success else message)
        if not success:
            QMessageBox.warning(self, "Wallpaper Error", f"Failed to set wallpaper:\n{message}")
        
        if success:
            self.update_downloaded_status()
            self.update_active_status()
        
        self._wallpaper_worker = None

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
        """Show blue star if this wallpaper is the current desktop background."""
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
                self.thumb_label.setText("No preview")
            return
        
        if self._is_loader_running():
            self._thumb_loader.terminate()
            self._thumb_loader.wait(100)
        
        if os.path.exists(self.thumb_url):
            pixmap = QPixmap(self.thumb_url)
            if not pixmap.isNull():
                scaled = pixmap.scaled(THUMB_SIZE, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.thumb_label.setPixmap(scaled)
                self._loaded = True
            else:
                self.thumb_label.setText("Invalid image")
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
            self.thumb_label.setPixmap(scaled)
            self._loaded = True
        else:
            self.thumb_label.setText("Load failed")
        self.update_downloaded_status()
        self.update_active_status()

    def emit_download(self):
        self.download_triggered.emit(self.data)
        
    def cleanup(self):
        """Prepare widget for recycling. Safely stops any running loaders."""
        if self._is_loader_running():
            self._thumb_loader.terminate()
            self._thumb_loader.wait(100)
        self._thumb_loader = None
        self._loaded = False
        self.thumb_label.setPixmap(get_placeholder())
        self.checkmark_btn.hide()
        self.active_indicator.hide()