# ============================================================
# SECTION: Imports & Dependencies
# ============================================================
import os
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QLabel, QFileDialog, QComboBox, QFrame, QApplication,
    QGraphicsDropShadowEffect, QToolButton, QGraphicsEffect
)
from PyQt5.QtCore import (
    Qt, pyqtSignal, QPropertyAnimation, QEasingCurve,
    QTimer, QSize, QPoint, QRectF, pyqtProperty
)
from PyQt5.QtGui import QColor, QFont, QPixmap, QIcon, QPainter, QBrush, QPen, QRadialGradient

from core.settings import Settings
from core.extension import get_extension_names
from core.workers import ThumbnailLoader


# ─────────────────────────────────────────────────────────────────────────────
# HoverScaleEffect — reused from wallpaper_widget, without glow (no_glow=True)
# for landing page elements where only zoom matters
# ─────────────────────────────────────────────────────────────────────────────
class HoverScaleEffect(QGraphicsEffect):
    def __init__(self, radius=10.0, no_glow=False, parent=None):
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

        painter.save()
        painter.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)

        if self._glow_t > 0.005 and not self._no_glow:
            t  = self._glow_t
            pw = 1.0
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(QColor(0, 212, 255, int(60 * t)), pw))
            painter.drawRoundedRect(
                QRectF(ox + pw/2, oy + pw/2, w - pw, h - pw),
                self._radius, self._radius
            )

        painter.translate(cx, cy)
        painter.scale(self._scale, self._scale)
        painter.translate(-cx, -cy)
        painter.drawPixmap(off, pixmap)
        painter.restore()


class AnimatedButton(QPushButton):
    """QPushButton with subtle hover animation."""
    def __init__(self, *args, no_glow=True, radius=8.0, **kwargs):
        super().__init__(*args, **kwargs)
        self.setAttribute(Qt.WA_Hover, True)
        self._effect = HoverScaleEffect(radius=radius, no_glow=no_glow, parent=self)
        self.setGraphicsEffect(self._effect)
        self._anim = QPropertyAnimation(self._effect, b"scale", self)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

    def _animate_to(self, end, dur):
        self._anim.stop()
        self._anim.setDuration(dur)
        self._anim.setStartValue(self._effect.getScale())
        self._anim.setEndValue(end)
        self._anim.start()

    def enterEvent(self, e):
        self._animate_to(1.05, 160)
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._animate_to(1.0, 200)
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._animate_to(0.95, 60)
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._animate_to(1.05 if self.underMouse() else 1.0, 160)
        super().mouseReleaseEvent(e)


class AnimatedComboBox(QComboBox):
    """QComboBox with subtle hover animation."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setAttribute(Qt.WA_Hover, True)
        self._effect = HoverScaleEffect(radius=8.0, no_glow=True, parent=self)
        self.setGraphicsEffect(self._effect)
        self._anim = QPropertyAnimation(self._effect, b"scale", self)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

    def _animate_to(self, end, dur):
        self._anim.stop()
        self._anim.setDuration(dur)
        self._anim.setStartValue(self._effect.getScale())
        self._anim.setEndValue(end)
        self._anim.start()

    def enterEvent(self, e):
        self._animate_to(1.04, 160)
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._animate_to(1.0, 200)
        super().leaveEvent(e)


# ============================================================
# SECTION: Landing Page Widget
# ============================================================
class LandingPage(QWidget):
    """
    Premium landing page — dark, minimal, with zoom on interactive elements.
    """

    COLOR_BG_PRIMARY    = "#050508"
    COLOR_BG_SECONDARY  = "#0a0a0f"
    COLOR_BG_TERTIARY   = "#111118"
    COLOR_BG_CARD       = "#0d0d14"
    COLOR_ACCENT        = "#00d4ff"  
    COLOR_ACCENT_DIM    = "#00d4ff22"
    COLOR_TEXT_PRIMARY  = "#eeeef5"
    COLOR_TEXT_SECONDARY= "#6b6b88"
    COLOR_TEXT_MUTED    = "#36364a"
    COLOR_BORDER        = "#18182a"
    COLOR_BORDER_HOVER  = "#252540"

    search_requested  = pyqtSignal(str)
    explore_requested = pyqtSignal()
    extension_changed = pyqtSignal(str)
    status_message    = pyqtSignal(str)

    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self._search_timer = None
        self.init_ui()
        self.on_extension_changed(self.ext_combo.currentText())

    # ============================================================
    # SECTION: UI Initialization
    # ============================================================
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(0)
        layout.setContentsMargins(40, 40, 40, 40)

        container = QWidget()
        container.setFixedWidth(540)
        cl = QVBoxLayout(container)
        cl.setSpacing(0)
        cl.setContentsMargins(0, 0, 0, 0)

        # ── Logo ──────────────────────────────────────────────────────────
        logo_wrap = QWidget()
        logo_layout = QVBoxLayout(logo_wrap)
        logo_layout.setContentsMargins(0, 0, 0, 32)
        logo_layout.setSpacing(6)

        title = QLabel("wallppy")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"""
            font-size: 52px;
            font-weight: 800;
            letter-spacing: -2px;
            color: {self.COLOR_ACCENT};
            background: transparent;
            border: none;
        """)
        logo_layout.addWidget(title)

        # sub = QLabel("discover beautiful wallpapers")
        # sub.setAlignment(Qt.AlignCenter)
        # sub.setStyleSheet(f"""
        #     font-size: 13px;
        #     font-weight: 400;
        #     letter-spacing: 0.5px;
        #     color: {self.COLOR_TEXT_MUTED};
        #     background: transparent;
        #     border: none;
        # """)
        # logo_layout.addWidget(sub)
        cl.addWidget(logo_wrap)

        # ── Source selector ───────────────────────────────────────────────
        src_wrap = QWidget()
        src_wrap.setContentsMargins(0, 0, 0, 12)
        src_layout = QHBoxLayout(src_wrap)
        src_layout.setContentsMargins(0, 0, 0, 0)
        src_layout.setSpacing(10)

        src_label = QLabel("SOURCE")
        src_label.setStyleSheet(f"""
            color: {self.COLOR_TEXT_MUTED};
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 2px;
            background: transparent;
            border: none;
        """)

        self.ext_combo = AnimatedComboBox()
        self.ext_combo.addItems(get_extension_names())
        self.ext_combo.setCurrentText(self.settings.extension_name)
        self.ext_combo.currentTextChanged.connect(self.on_extension_changed)
        self.ext_combo.setFixedHeight(32)
        self.ext_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {self.COLOR_BG_TERTIARY};
                border: 1px solid {self.COLOR_BORDER};
                border-radius: 7px;
                color: {self.COLOR_TEXT_PRIMARY};
                font-size: 12px;
                font-weight: 500;
                padding: 0px 12px;
                min-width: 130px;
            }}
            QComboBox:hover {{
                border-color: {self.COLOR_BORDER_HOVER};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 20px;
            }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 4px solid {self.COLOR_ACCENT};
                margin-right: 8px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {self.COLOR_BG_TERTIARY};
                color: {self.COLOR_TEXT_PRIMARY};
                border: 1px solid {self.COLOR_BORDER};
                border-radius: 7px;
                selection-background-color: {self.COLOR_ACCENT};
                selection-color: {self.COLOR_BG_PRIMARY};
                padding: 4px;
            }}
        """)

        src_layout.addWidget(src_label, 0, Qt.AlignVCenter)
        src_layout.addWidget(self.ext_combo)
        src_layout.addStretch()
        
        self.clear_cache_btn = QPushButton("Clear Cache")
        self.clear_cache_btn.setToolTip("Clear extension cache")
        self.clear_cache_btn.setFixedHeight(34)
        self.clear_cache_btn.setMinimumWidth(100)
        self.clear_cache_btn.setCursor(Qt.PointingHandCursor)
        self.clear_cache_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.COLOR_BG_TERTIARY};
                border: 1px solid {self.COLOR_BORDER};
                border-radius: 7px;
                color: {self.COLOR_TEXT_SECONDARY};
                font-size: 12px;
                font-weight: 500;
                padding: 0px 16px;
            }}
            QPushButton:hover {{
                border-color: {self.COLOR_BORDER_HOVER};
                color: {self.COLOR_TEXT_PRIMARY};
            }}
        """)
        self.clear_cache_btn.clicked.connect(self._clear_extension_cache)
        src_layout.addWidget(self.clear_cache_btn)
        
        cl.addWidget(src_wrap)

        # ── Search card ───────────────────────────────────────────────────
        search_card = QFrame()
        search_card.setFixedHeight(52)
        search_card.setStyleSheet(f"""
            QFrame {{
                background-color: {self.COLOR_BG_CARD};
                border-radius: 12px;
                border: 1px solid {self.COLOR_BORDER};
            }}
        """)

        # Sombra suave
        shadow = QGraphicsDropShadowEffect(search_card)
        shadow.setBlurRadius(32)
        shadow.setColor(QColor(0, 0, 0, 100))
        shadow.setOffset(0, 6)
        search_card.setGraphicsEffect(shadow)

        sc_layout = QHBoxLayout(search_card)
        sc_layout.setContentsMargins(16, 0, 8, 0)
        sc_layout.setSpacing(10)

        # Ícone lupa SVG
        lupa_svg = b"""<svg width="15" height="15" viewBox="0 0 15 15"
            fill="none" xmlns="http://www.w3.org/2000/svg">
          <circle cx="6" cy="6" r="4.25" stroke="#36364a" stroke-width="1.4"/>
          <line x1="9.3" y1="9.3" x2="13.2" y2="13.2"
                stroke="#36364a" stroke-width="1.4" stroke-linecap="round"/>
        </svg>"""
        lupa_px = QPixmap()
        lupa_px.loadFromData(lupa_svg, "SVG")
        lupa = QLabel()
        lupa.setPixmap(lupa_px)
        lupa.setFixedSize(15, 15)
        lupa.setStyleSheet("background: transparent; border: none;")
        sc_layout.addWidget(lupa, 0, Qt.AlignVCenter)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search for wallpapers...")
        self.search_edit.setFrame(False)
        self.search_edit.setStyleSheet(f"""
            QLineEdit {{
                font-size: 14px;
                background: transparent;
                border: none;
                color: {self.COLOR_TEXT_PRIMARY};
                selection-background-color: {self.COLOR_ACCENT};
                padding: 0px;
            }}
        """)
        self.search_edit.returnPressed.connect(self.emit_search)
        self.search_edit.textChanged.connect(self.on_search_text_changed)
        sc_layout.addWidget(self.search_edit, 1, Qt.AlignVCenter)

        # Botão X limpar
        self.clear_btn = AnimatedButton("✕", no_glow=True)
        self.clear_btn.setFixedSize(26, 26)
        self.clear_btn.setCursor(Qt.PointingHandCursor)
        self.clear_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {self.COLOR_TEXT_MUTED};
                font-size: 12px;
                border: none;
                border-radius: 13px;
            }}
            QPushButton:hover {{
                background: {self.COLOR_BORDER};
                color: {self.COLOR_TEXT_PRIMARY};
            }}
        """)
        self.clear_btn.clicked.connect(self.clear_search)
        self.clear_btn.hide()
        sc_layout.addWidget(self.clear_btn, 0, Qt.AlignVCenter)

        # Separador vertical
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setFixedWidth(1)
        sep.setFixedHeight(20)
        sep.setStyleSheet(f"background: {self.COLOR_BORDER}; border: none;")
        sc_layout.addWidget(sep, 0, Qt.AlignVCenter)

        # Botão Search — mesmo cyan da results_page
        self.search_btn = AnimatedButton("Search", no_glow=True, radius=8.0)
        self.search_btn.setFixedSize(80, 34)
        self.search_btn.setCursor(Qt.PointingHandCursor)
        self.search_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.COLOR_ACCENT};
                color: #050508;
                border-radius: 8px;
                border: none;
                font-size: 12px;
                font-weight: 700;
                letter-spacing: 0.3px;
            }}
            QPushButton:disabled {{
                background-color: {self.COLOR_BORDER};
                color: {self.COLOR_TEXT_MUTED};
            }}
        """)
        self.search_btn.clicked.connect(self.emit_search)
        sc_layout.addWidget(self.search_btn, 0, Qt.AlignVCenter)

        cl.addWidget(search_card)

        # ── Hints row ─────────────────────────────────────────────────────
        hints_wrap = QWidget()
        hints_wrap.setContentsMargins(0, 0, 0, 0)
        hl = QHBoxLayout(hints_wrap)
        hl.setContentsMargins(4, 10, 4, 0)
        hl.setSpacing(0)

        hint = QLabel("⏎ Enter to search")
        hint.setStyleSheet(f"""
            color: {self.COLOR_TEXT_MUTED};
            font-size: 11px;
            background: transparent;
            border: none;
        """)
        hl.addWidget(hint)
        hl.addStretch()

        self.explore_label = QLabel(f'<font color="{self.COLOR_ACCENT}">explore recent</font> →')
        self.explore_label.setTextFormat(Qt.RichText)
        self.explore_label.setStyleSheet(f"""
            QLabel {{
                color: {self.COLOR_TEXT_SECONDARY};
                font-size: 11px;
                background: transparent;
                border: none;
                padding: 3px 6px;
                border-radius: 4px;
            }}
            QLabel:hover {{
                background-color: {self.COLOR_BG_TERTIARY};
            }}
        """)
        self.explore_label.setCursor(Qt.PointingHandCursor)
        self.explore_label.mousePressEvent = lambda ev: self.emit_explore() if ev.button() == Qt.LeftButton else None
        hl.addWidget(self.explore_label)

        cl.addWidget(hints_wrap)

        # ── Divisor ───────────────────────────────────────────────────────
        div_wrap = QWidget()
        div_wrap.setContentsMargins(0, 28, 0, 28)
        div_l = QVBoxLayout(div_wrap)
        div_l.setContentsMargins(0, 0, 0, 0)
        div = QFrame()
        div.setFrameShape(QFrame.HLine)
        div.setFixedHeight(1)
        div.setStyleSheet(f"background-color: {self.COLOR_BORDER}; border: none;")
        div_l.addWidget(div)
        cl.addWidget(div_wrap)

        # ── Download location ─────────────────────────────────────────────
        dl_label = QLabel("DOWNLOAD LOCATION")
        dl_label.setStyleSheet(f"""
            color: {self.COLOR_TEXT_MUTED};
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 2px;
            background: transparent;
            border: none;
            margin-bottom: 8px;
        """)
        cl.addWidget(dl_label)

        dir_row = QHBoxLayout()
        dir_row.setSpacing(8)
        dir_row.setContentsMargins(0, 8, 0, 0)

        self.dir_edit = QLineEdit()
        self.dir_edit.setText(self.settings.download_folder)
        self.dir_edit.setReadOnly(True)
        self.dir_edit.setFixedHeight(34)
        self.dir_edit.setStyleSheet(f"""
            QLineEdit {{
                background-color: {self.COLOR_BG_TERTIARY};
                border: 1px solid {self.COLOR_BORDER};
                border-radius: 7px;
                padding: 0px 12px;
                color: {self.COLOR_TEXT_SECONDARY};
                font-size: 12px;
                font-weight: 400;
            }}
        """)
        dir_row.addWidget(self.dir_edit)

        self.browse_btn = QPushButton("Change")
        self.browse_btn.setFixedHeight(34)
        self.browse_btn.setMinimumWidth(100)
        self.browse_btn.setCursor(Qt.PointingHandCursor)
        self.browse_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.COLOR_BG_TERTIARY};
                border: 1px solid {self.COLOR_BORDER};
                border-radius: 7px;
                color: {self.COLOR_TEXT_SECONDARY};
                font-size: 12px;
                font-weight: 500;
                padding: 0px 16px;
            }}
            QPushButton:hover {{
                border-color: {self.COLOR_BORDER_HOVER};
                color: {self.COLOR_TEXT_PRIMARY};
            }}
        """)
        self.browse_btn.clicked.connect(self.choose_directory)
        dir_row.addWidget(self.browse_btn)

        cl.addLayout(dir_row)
        layout.addWidget(container)
        layout.addStretch()

    # ============================================================
    # SECTION: Event Handlers
    # ============================================================
    def on_search_text_changed(self, text):
        self.clear_btn.setVisible(bool(text))

    def clear_search(self):
        self.search_edit.clear()
        self.search_edit.setFocus()

    def emit_explore(self):
        self.explore_requested.emit()

    def on_extension_changed(self, name: str):
        if name != "Local":
            self.settings.set_extension(name)
        self.extension_changed.emit(name)
        self.clear_cache_btn.setToolTip(f"Clear {name} extension cache")
        
        if name == "Local":
            self.search_edit.setEnabled(False)
            self.search_edit.setPlaceholderText("Browsing local folder...")
            self.search_edit.setStyleSheet(f"""
                QLineEdit {{
                    font-size: 14px;
                    background: transparent;
                    border: none;
                    color: {self.COLOR_TEXT_MUTED};
                }}
            """)
            self.search_btn.setEnabled(False)
            self.clear_btn.hide()
            self.status_message.emit("Scanning local folder...")
            self.explore_requested.emit()
        else:
            self.search_edit.setEnabled(True)
            self.search_edit.setPlaceholderText("Search for wallpapers...")
            self.search_edit.setStyleSheet(f"""
                QLineEdit {{
                    font-size: 14px;
                    background: transparent;
                    border: none;
                    color: {self.COLOR_TEXT_PRIMARY};
                    selection-background-color: {self.COLOR_ACCENT};
                }}
            """)
            self.search_btn.setEnabled(True)
            self.on_search_text_changed(self.search_edit.text())
            self.status_message.emit("Ready")
    
    def _clear_extension_cache(self):
        ext_name = self.ext_combo.currentText()
        with ThumbnailLoader._lock:
            keys_to_remove = [k for k in ThumbnailLoader._cache if ext_name.lower() in k.lower()]
            for k in keys_to_remove:
                del ThumbnailLoader._cache[k]
        self.status_message.emit(f"{ext_name}: cache cleared successfully")
    
    def emit_search(self):
        if not self.search_edit.isEnabled():
            return
        query = self.search_edit.text().strip()
        if query:
            self.search_requested.emit(query)

    def choose_directory(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Download Folder",
            self.settings.download_folder
        )
        if folder:
            self.settings.set_download_folder(folder)
            self.dir_edit.setText(folder)

    def set_search_text(self, text: str):
        self.search_edit.setText(text)