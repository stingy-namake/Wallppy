import os
from PyQt5.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QSizePolicy,
    QToolButton, QGraphicsEffect
)
from PyQt5.QtCore import (
    Qt, pyqtSignal, QSize, QTimer, QPropertyAnimation,
    QEasingCurve, pyqtProperty, QPoint, QRectF
)
from PyQt5.QtGui import (
    QPixmap, QPainter, QColor, QLinearGradient, QRadialGradient,
    QBrush, QPen, QIcon
)
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from core.extension import WallpaperExtension

THUMB_SIZE = QSize(280, 158)

COLOR_BG_PRIMARY      = "#080810"
COLOR_BG_CARD         = "#0f0f18"
COLOR_ACCENT_BLUE     = "#4d9fff"
COLOR_ACCENT_LAVENDER = "#a78bfa"
COLOR_TEXT_PRIMARY    = "#e8e8f0"
COLOR_TEXT_SECONDARY  = "#6b6b88"
COLOR_TEXT_MUTED      = "#36364a"
COLOR_BORDER          = "#18182a"
COLOR_BORDER_HOVER    = "#252540"
COLOR_SUCCESS         = "#34d399"


# ─────────────────────────────────────────────────────────────────────────────
# HoverScaleEffect
# Simple and robust LogicalCoordinates — without manual DPR manipulation.
# Glow: subtle border + diffuse radial halo at the top. No conical neon.
# ─────────────────────────────────────────────────────────────────────────────
class HoverScaleEffect(QGraphicsEffect):
    def __init__(self, radius=14.0, no_glow=False, parent=None):
        super().__init__(parent)
        self._scale   = 1.0
        self._glow_t  = 0.0
        self._radius  = radius
        self._no_glow = no_glow

    def getScale(self) -> float:
        return self._scale

    def setScale(self, v: float):
        self._scale  = v
        self._glow_t = max(0.0, min(1.0, (v - 1.0) / 0.025))
        self.update()

    scale = pyqtProperty(float, fget=getScale, fset=setScale)

    def boundingRectFor(self, src: QRectF) -> QRectF:
        return src.adjusted(-3, -3, 3, 3)

    def draw(self, painter: QPainter):
        result = self.sourcePixmap(Qt.LogicalCoordinates)
        if isinstance(result, tuple):
            pixmap, offset = result
        else:
            pixmap, offset = result, QPoint()

        if not pixmap or pixmap.isNull():
            self.drawSource(painter)
            return

        off = offset if isinstance(offset, QPoint) else QPoint()
        w   = float(pixmap.width())
        h   = float(pixmap.height())
        ox  = float(off.x())
        oy  = float(off.y())
        cx  = ox + w / 2.0
        cy  = oy + h / 2.0
        r   = self._radius

        painter.save()
        painter.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)

        # ── Soft glow on the border ───────────────────────────────────────────
        if self._glow_t > 0.005 and not self._no_glow:
            t    = self._glow_t
            card = QRectF(ox, oy, w, h)
            pw   = 1.0

            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(QColor(77, 159, 255, int(70 * t)), pw))
            painter.drawRoundedRect(card.adjusted(pw/2, pw/2, -pw/2, -pw/2), r, r)

            # Radial halo at the top — very soft
            hr = w * 0.48
            halo = QRadialGradient(cx, oy, hr)
            halo.setColorAt(0.0, QColor(77, 159, 255, int(14 * t)))
            halo.setColorAt(1.0, QColor(0, 0, 0, 0))
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(halo))
            painter.drawEllipse(int(cx - hr), int(oy - hr), int(hr * 2), int(hr * 2))

        # ── Centered Zoom ─────────────────────────────────────────────────
        painter.translate(cx, cy)
        painter.scale(self._scale, self._scale)
        painter.translate(-cx, -cy)
        painter.drawPixmap(off, pixmap)
        painter.restore()


# ─────────────────────────────────────────────────────────────────────────────
# AnimatedToolButton
# ─────────────────────────────────────────────────────────────────────────────
class AnimatedToolButton(QToolButton):
    def __init__(self, no_glow=False, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_Hover, True)

        self._effect = HoverScaleEffect(radius=8.0, no_glow=no_glow, parent=self)
        self.setGraphicsEffect(self._effect)

        self._anim = QPropertyAnimation(self._effect, b"scale", self)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

    def _animate_to(self, end: float, duration: int):
        self._anim.stop()
        self._anim.setDuration(duration)
        self._anim.setStartValue(self._effect.getScale())
        self._anim.setEndValue(end)
        self._anim.start()

    def enterEvent(self, e):
        self._animate_to(1.06, 160)
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._animate_to(1.0, 200)
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._animate_to(0.94, 60)
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._animate_to(1.06 if self.underMouse() else 1.0, 180)
        super().mouseReleaseEvent(e)

    def cleanup(self):
        if self._anim.state() == QPropertyAnimation.Running:
            self._anim.stop()
        self._effect.setScale(1.0)


# ─────────────────────────────────────────────────────────────────────────────
# ShimmerLabel
# ─────────────────────────────────────────────────────────────────────────────
class ShimmerLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(THUMB_SIZE)
        self.setAlignment(Qt.AlignCenter)
        self.setScaledContents(True)
        self._shimmer_value = 0.0
        self._shimmer_anim  = None
        self._base_color    = QColor(15, 15, 24)
        self._highlight     = QColor(26, 26, 42)
        self._fade_effect   = None
        self._fade_anim     = None

    def paintEvent(self, event):
        if self.pixmap() and not self.pixmap().isNull():
            super().paintEvent(event)
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(self._base_color)
        painter.drawRoundedRect(self.rect(), 10, 10)
        pos = self._shimmer_value
        g   = QLinearGradient(0, 0, self.width(), 0)
        g.setColorAt(max(0.0, pos - 0.3), self._base_color)
        g.setColorAt(pos,                 self._highlight)
        g.setColorAt(min(1.0, pos + 0.3), self._base_color)
        painter.setBrush(QBrush(g))
        painter.drawRoundedRect(self.rect(), 10, 10)

    def start_shimmer(self):
        if self._shimmer_anim:
            return
        self._shimmer_anim = QPropertyAnimation(self, b"shimmerValue")
        self._shimmer_anim.setDuration(1600)
        self._shimmer_anim.setStartValue(-0.4)
        self._shimmer_anim.setEndValue(1.4)
        self._shimmer_anim.setLoopCount(-1)
        self._shimmer_anim.setEasingCurve(QEasingCurve.InOutSine)
        self._shimmer_anim.start()

    def stop_shimmer(self):
        if self._shimmer_anim:
            self._shimmer_anim.stop()
            self._shimmer_anim = None
        self.setShimmerValue(0.0)

    def getShimmerValue(self): return self._shimmer_value
    def setShimmerValue(self, v):
        self._shimmer_value = v
        self.update()
    shimmerValue = pyqtProperty(float, fget=getShimmerValue, fset=setShimmerValue)

    def fade_in_pixmap(self, pixmap: QPixmap):
        from PyQt5.QtWidgets import QGraphicsOpacityEffect
        if self._fade_anim and self._fade_anim.state() == QPropertyAnimation.Running:
            self._fade_anim.stop()
        self._fade_effect = QGraphicsOpacityEffect(self)
        self._fade_effect.setOpacity(0.0)
        self.setGraphicsEffect(self._fade_effect)
        self.setPixmap(pixmap)
        self._fade_anim = QPropertyAnimation(self._fade_effect, b"opacity", self)
        self._fade_anim.setDuration(350)
        self._fade_anim.setStartValue(0.0)
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._fade_anim.finished.connect(self._on_fade_done)
        self._fade_anim.start()

    def _on_fade_done(self):
        self.setGraphicsEffect(None)
        self._fade_effect = self._fade_anim = None

    def cleanup_fade(self):
        if self._fade_anim and self._fade_anim.state() == QPropertyAnimation.Running:
            self._fade_anim.stop()
        self._fade_anim = self._fade_effect = None
        self.setGraphicsEffect(None)


# ─────────────────────────────────────────────────────────────────────────────
# WallpaperWidget
# ─────────────────────────────────────────────────────────────────────────────
class WallpaperWidget(QFrame):
    download_triggered      = pyqtSignal(dict)
    expand_triggered        = pyqtSignal(dict)
    set_wallpaper_triggered = pyqtSignal(dict)

    def __init__(self, extension: "WallpaperExtension", wallpaper_data: dict,
                 download_folder: str, parent=None):
        from core.extension import WallpaperExtension  # lazy — evita import circular
        super().__init__(parent)
        self.extension             = extension
        self.data                  = wallpaper_data
        self.download_folder       = download_folder
        self.thumb_url             = extension.get_thumbnail_url(wallpaper_data)
        self._thumb_loader         = None
        self._loaded               = False
        self._is_setting_wallpaper = False

        self.setFrameShape(QFrame.NoFrame)
        self.setStyleSheet(f"""
            WallpaperWidget {{
                background-color: {COLOR_BG_CARD};
                border-radius: 14px;
                border: 1px solid {COLOR_BORDER};
            }}
        """)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        self._hover_effect = HoverScaleEffect(radius=14.0, parent=self)
        self.setGraphicsEffect(self._hover_effect)

        self._hover_anim = QPropertyAnimation(self._hover_effect, b"scale", self)
        self._hover_anim.setDuration(250)
        self._hover_anim.setEasingCurve(QEasingCurve.OutCubic)

        self.init_ui()
        QTimer.singleShot(0, self.load_thumbnail)

    def enterEvent(self, event):
        self._hover_anim.stop()
        self._hover_anim.setStartValue(self._hover_effect.getScale())
        self._hover_anim.setEndValue(1.025)
        self._hover_anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover_anim.stop()
        self._hover_anim.setStartValue(self._hover_effect.getScale())
        self._hover_anim.setEndValue(1.0)
        self._hover_anim.start()
        super().leaveEvent(event)

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(7)

        self.thumb_label = ShimmerLabel()
        self.thumb_label.setAlignment(Qt.AlignCenter)
        self.thumb_label.setStyleSheet(f"""
            QLabel {{
                background-color: {COLOR_BG_PRIMARY};
                border-radius: 8px;
                border: 1px solid {COLOR_BORDER};
            }}
        """)
        self.thumb_label.setCursor(Qt.PointingHandCursor)
        self.thumb_label.start_shimmer()
        layout.addWidget(self.thumb_label, alignment=Qt.AlignHCenter)

        bar = QHBoxLayout()
        bar.setContentsMargins(2, 0, 2, 0)
        bar.setSpacing(5)

        self.active_indicator = QToolButton()
        self.active_indicator.setText("★")
        self.active_indicator.setToolTip("Wallpaper atual")
        self.active_indicator.setStyleSheet(f"""
            QToolButton {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {COLOR_ACCENT_BLUE}, stop:1 {COLOR_ACCENT_LAVENDER});
                border-radius: 6px; border: none;
                color: #080810; font-size: 10px; font-weight: 700;
            }}
        """)
        self.active_indicator.setFixedSize(26, 22)
        self.active_indicator.hide()
        bar.addWidget(self.active_indicator)

        self.checkmark_btn = QToolButton()
        self.checkmark_btn.setText("✓")
        self.checkmark_btn.setToolTip("Downloaded")
        self.checkmark_btn.setStyleSheet(f"""
            QToolButton {{
                background-color: transparent;
                border-radius: 6px;
                border: 1px solid {COLOR_SUCCESS}44;
                color: {COLOR_SUCCESS};
                font-size: 11px; font-weight: 600;
            }}
        """)
        self.checkmark_btn.setFixedSize(26, 22)
        self.checkmark_btn.hide()
        bar.addWidget(self.checkmark_btn)

        res = self.extension.get_resolution(self.data)
        self.res_label = QLabel(res)
        self.res_label.setStyleSheet(
            f"color: {COLOR_TEXT_MUTED}; font-size: 10px; letter-spacing: 0.3px;"
            " background: transparent; border: none;"
        )
        bar.addWidget(self.res_label)
        bar.addStretch()

        BTN_STYLE = f"""
            QToolButton {{
                background-color: transparent;
                border-radius: 7px;
                border: 1px solid {COLOR_BORDER};
                color: {COLOR_TEXT_SECONDARY};
                font-size: 13px; padding: 0px;
            }}
            QToolButton:hover {{
                background-color: {COLOR_BORDER};
                color: {COLOR_TEXT_PRIMARY};
                border-color: {COLOR_BORDER_HOVER};
            }}
            QToolButton:disabled {{
                color: {COLOR_TEXT_MUTED};
                border-color: {COLOR_BORDER};
            }}
        """

        _expand_svg = b'<svg width="14" height="14" viewBox="0 0 14 14" fill="none" xmlns="http://www.w3.org/2000/svg">\n  <polyline points="9,1 13,1 13,5" stroke="#6b6b88" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>\n  <polyline points="5,13 1,13 1,9" stroke="#6b6b88" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>\n  <line x1="13" y1="1" x2="8.5" y2="5.5" stroke="#6b6b88" stroke-width="1.4" stroke-linecap="round"/>\n  <line x1="1" y1="13" x2="5.5" y2="8.5" stroke="#6b6b88" stroke-width="1.4" stroke-linecap="round"/>\n</svg>'
        _expand_px = QPixmap()
        _expand_px.loadFromData(_expand_svg, "SVG")

        self.expand_btn = AnimatedToolButton()

        self.expand_btn.setIcon(QIcon(_expand_px))
        self.expand_btn.setIconSize(QSize(14, 14))
        self.expand_btn.setToolTip("Expandir preview")

        self.expand_btn.setCursor(Qt.PointingHandCursor)
        self.expand_btn.setStyleSheet(BTN_STYLE)
        self.expand_btn.setFixedSize(30, 26)
        self.expand_btn.clicked.connect(lambda: self.expand_triggered.emit(self.data))
        bar.addWidget(self.expand_btn)

        _monitor_svg = b'<svg width="14" height="14" viewBox="0 0 14 14" fill="none" xmlns="http://www.w3.org/2000/svg">\n  <rect x="1" y="1.5" width="12" height="8.5" rx="1.5" stroke="#6b6b88" stroke-width="1.4"/>\n  <line x1="5" y1="12.5" x2="9" y2="12.5" stroke="#6b6b88" stroke-width="1.4" stroke-linecap="round"/>\n  <line x1="7" y1="10" x2="7" y2="12.5" stroke="#6b6b88" stroke-width="1.4" stroke-linecap="round"/>\n</svg>'
        _monitor_px = QPixmap()
        _monitor_px.loadFromData(_monitor_svg, "SVG")
        self._monitor_px = _monitor_px

        _hourglass_svg = b'<svg width="14" height="14" viewBox="0 0 14 14" fill="none" xmlns="http://www.w3.org/2000/svg">\n  <path d="M3 1h8M3 13h8M4 1c0 3 3 5 3 6s-3 3-3 6M10 1c0 3-3 5-3 6s3 3 3 6" stroke="#6b6b88" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>\n</svg>'
        _hourglass_px = QPixmap()
        _hourglass_px.loadFromData(_hourglass_svg, "SVG")
        self._hourglass_px = _hourglass_px

        self.wallpaper_btn = AnimatedToolButton()

        self.wallpaper_btn.setIcon(QIcon(_monitor_px))
        self.wallpaper_btn.setIconSize(QSize(14, 14))
        self.wallpaper_btn.setToolTip("Definir como papel de parede")

        self.wallpaper_btn.setCursor(Qt.PointingHandCursor)
        self.wallpaper_btn.setStyleSheet(BTN_STYLE)
        self.wallpaper_btn.setFixedSize(30, 26)
        self.wallpaper_btn.clicked.connect(self._on_set_wallpaper_clicked)
        bar.addWidget(self.wallpaper_btn)

        layout.addLayout(bar)
        self.setLayout(layout)
        self.setFixedSize(THUMB_SIZE.width() + 18, THUMB_SIZE.height() + 48)

    def _on_set_wallpaper_clicked(self):
        if self._is_setting_wallpaper:
            return
        self._is_setting_wallpaper = True
        self.wallpaper_btn.setEnabled(False)
        self.wallpaper_btn.setIcon(QIcon(self._hourglass_px))
        self.wallpaper_btn.setToolTip("Aplicando…")
        self.set_wallpaper_triggered.emit(self.data)

    def on_wallpaper_set_complete(self, success: bool):
        self._is_setting_wallpaper = False
        self.wallpaper_btn.setEnabled(True)
        self.wallpaper_btn.setIcon(QIcon(self._monitor_px))
        self.wallpaper_btn.setToolTip("Definir como papel de parede")
        self.update_active_status()

    def _is_loader_running(self) -> bool:
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
        wall_id  = self.extension.get_wallpaper_id(self.data)
        ext      = self.extension.get_file_extension(self.data)
        filepath = os.path.join(self.download_folder, f"wallppy-{wall_id}.{ext}")
        self.checkmark_btn.setVisible(os.path.exists(filepath))

    def update_active_status(self):
        from core.wallpaper_manager import WallpaperManager
        current = WallpaperManager.get_current_wallpaper()
        if not current:
            self.active_indicator.hide()
            return
        wall_id    = self.extension.get_wallpaper_id(self.data)
        ext        = self.extension.get_file_extension(self.data)
        downloaded = os.path.join(self.download_folder, f"wallppy-{wall_id}.{ext}")
        direct     = self.extension.get_download_url(self.data) or ""
        current_abs = os.path.abspath(current)
        self.active_indicator.setVisible(
            current_abs == os.path.abspath(downloaded) or
            bool(direct and current_abs == os.path.abspath(direct))
        )

    def load_thumbnail(self):
        if self._loaded or not self.thumb_url:
            if not self.thumb_url:
                self.thumb_label.stop_shimmer()
                self.thumb_label.setText("No preview")
            return
        if self._is_loader_running():
            self._thumb_loader.quit()
            self._thumb_loader.wait(100)
        if os.path.exists(self.thumb_url):
            px = QPixmap(self.thumb_url)
            if not px.isNull():
                scaled = px.scaled(THUMB_SIZE, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.thumb_label.stop_shimmer()
                self.thumb_label.fade_in_pixmap(scaled)
                self._loaded = True
            else:
                self.thumb_label.stop_shimmer()
                self.thumb_label.setText("Invalid preview")
            self.update_downloaded_status()
            self.update_active_status()
            return
        from core.workers import ThumbnailLoader  # lazy — evita import circular
        self._thumb_loader = ThumbnailLoader(self.thumb_url)
        self._thumb_loader.loaded.connect(self.set_thumbnail)
        self._thumb_loader.finished.connect(self._thumb_loader.deleteLater)
        self._thumb_loader.start()

    def set_thumbnail(self, pixmap: QPixmap):
        if not pixmap.isNull():
            scaled = pixmap.scaled(THUMB_SIZE, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.thumb_label.stop_shimmer()
            self.thumb_label.fade_in_pixmap(scaled)
            self._loaded = True
        else:
            self.thumb_label.stop_shimmer()
            self.thumb_label.setText("Failed to load preview")
        self.update_downloaded_status()
        self.update_active_status()

    def emit_download(self):
        self.download_triggered.emit(self.data)

    def cleanup(self):
        if self._hover_anim.state() == QPropertyAnimation.Running:
            self._hover_anim.stop()
        self._hover_effect.setScale(1.0)
        self.expand_btn.cleanup()
        self.wallpaper_btn.cleanup()
        self.thumb_label.cleanup_fade()
        if self._is_loader_running():
            self._thumb_loader.quit()
            self._thumb_loader.wait(100)
        self._thumb_loader         = None
        self._loaded               = False
        self._is_setting_wallpaper = False
        self.thumb_label.stop_shimmer()
        self.thumb_label.start_shimmer()
        self.checkmark_btn.hide()
        self.active_indicator.hide()