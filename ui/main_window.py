# ============================================================
# SECTION: Imports & Dependencies
# ============================================================
from datetime import datetime
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget,
    QProgressBar, QLabel, QApplication, QStatusBar, QShortcut, QFrame,
    QGraphicsOpacityEffect, QScrollArea, QAction
)
from PyQt5.QtCore import Qt, QPropertyAnimation, QEasingCurve, QTimer, QSize, QEvent
from PyQt5.QtGui import QPalette, QColor, QLinearGradient, QPainter, QBrush, QFont, QKeySequence

from core.extension import create_extension, get_extension_names
from core.settings import Settings
from .landing_page import LandingPage
from .results_page import ResultsPage


# ============================================================
# SECTION: Enhanced Stacked Widget with Smooth Transitions
# ============================================================
class FadeStackedWidget(QStackedWidget):
    """
    Custom stacked widget with cross-fade animation.
    Provides smooth page transitions without performance impact.
    """
    def setCurrentIndex(self, index):
        if self.currentIndex() == index:
            return
        current_widget = self.currentWidget()
        next_widget = self.widget(index)
        if current_widget and next_widget:
            # Fade out current widget
            self.fade_out = QPropertyAnimation(current_widget, b"windowOpacity")
            self.fade_out.setDuration(200)
            self.fade_out.setStartValue(1.0)
            self.fade_out.setEndValue(0.0)
            self.fade_out.setEasingCurve(QEasingCurve.InOutCubic)
            self.fade_out.finished.connect(lambda: self._finish_switch(index, next_widget))
            self.fade_out.start()
        else:
            super().setCurrentIndex(index)

    def _finish_switch(self, index, next_widget):
        super().setCurrentIndex(index)
        # Fade in next widget with slight delay for depth perception
        self.fade_in = QPropertyAnimation(next_widget, b"windowOpacity")
        self.fade_in.setDuration(250)
        self.fade_in.setStartValue(0.0)
        self.fade_in.setEndValue(1.0)
        self.fade_in.setEasingCurve(QEasingCurve.OutCubic)
        self.fade_in.start()


# ============================================================
# SECTION: Shortcuts Overlay
# ============================================================
class ShortcutsOverlay(QWidget):
    """Semi-transparent overlay showing all keyboard shortcuts."""

    BG = "#050508"
    CARD_BG = "#0f0f18"
    BORDER = "#2a2a35"
    ACCENT = "#00d4ff"
    TEXT = "#e8e8f0"
    TEXT_SEC = "#a0a0b0"
    TEXT_MUTED = "#6a6a7a"
    BADGE_BG = "rgba(128,128,128,0.12)"

    SHORTCUTS = [
        ("Searching", [
            ("Ctrl+K", "Focus search bar"),
            ("Enter", "Search / Explore"),
            ("Ctrl+N", "Go home + focus search"),
        ]),
        ("Navigation", [
            ("↑ ↓ ← →", "Move between wallpapers"),
            ("j k h l", "Vim-style navigation"),
            ("Tab", "Next wallpaper"),
            ("Shift+Tab", "Previous wallpaper"),
            ("Home", "Scroll to top"),
            ("Esc", "Back / close"),
        ]),
        ("Wallpaper Actions", [
            ("Enter", "Set as wallpaper"),
            ("Space", "Preview full image"),
            ("Ctrl+D", "Download wallpaper"),
            ("Delete", "Delete downloaded file"),
        ]),
        ("Sources & Downloads", [
            ("Ctrl+S", "Cycle wallpaper source"),
            ("Ctrl+L", "Explore downloaded wallpapers"),
            ("Ctrl+F", "Toggle filters panel"),
            ("Ctrl+,", "Change download directory"),
        ]),
        ("General", [
            ("Ctrl+/", "Show this overlay"),
        ]),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background-color: rgba(5, 5, 8, 0.92);")
        self.setVisible(False)

        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignCenter)
        outer.setContentsMargins(20, 20, 20, 20)

        # Scroll area wraps the card
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(f"""
            QScrollArea {{ background: transparent; border: none; }}
            QScrollBar:vertical {{
                background: transparent; width: 6px; border-radius: 3px;
            }}
            QScrollBar::handle:vertical {{
                background: {self.BORDER}; border-radius: 3px; min-height: 30px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                border: none; background: none; height: 0px;
            }}
        """)

        # Inner widget holds the card
        inner = QWidget()
        inner.setStyleSheet("background: transparent;")
        inner_layout = QVBoxLayout(inner)
        inner_layout.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        inner_layout.setContentsMargins(0, 0, 0, 0)

        # Card
        card = QFrame()
        card.setMaximumWidth(620)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {self.CARD_BG};
                border: 1px solid {self.BORDER};
                border-radius: 16px;
            }}
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(32, 28, 32, 24)
        card_layout.setSpacing(20)

        # Shortcut categories
        for category, shortcuts in self.SHORTCUTS:
            cat_widget = QWidget()
            cat_layout = QVBoxLayout(cat_widget)
            cat_layout.setContentsMargins(0, 0, 0, 0)
            cat_layout.setSpacing(6)

            cat_label = QLabel(category)
            cat_label.setStyleSheet(f"""
                color: {self.ACCENT};
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 1.5px;
                background: transparent;
                border: none;
            """)
            cat_layout.addWidget(cat_label)

            for key, desc in shortcuts:
                row = QHBoxLayout()
                row.setContentsMargins(0, 0, 0, 0)
                row.setSpacing(12)

                key_label = QLabel(key)
                key_label.setMinimumWidth(90)
                key_label.setMaximumWidth(130)
                key_label.setStyleSheet(f"""
                    color: {self.TEXT};
                    font-size: 12px;
                    font-weight: 600;
                    font-family: 'SF Mono', 'Consolas', monospace;
                    background: {self.BADGE_BG};
                    border-radius: 4px;
                    padding: 3px 8px;
                    border: none;
                """)
                row.addWidget(key_label, 0)

                desc_label = QLabel(desc)
                desc_label.setStyleSheet(f"""
                    color: {self.TEXT_SEC};
                    font-size: 12px;
                    background: transparent;
                    border: none;
                """)
                row.addWidget(desc_label, 1)

                cat_layout.addLayout(row)

            card_layout.addWidget(cat_widget)

        # Footer hint
        footer = QLabel("Press Esc or Ctrl+/ to close")
        footer.setAlignment(Qt.AlignCenter)
        footer.setStyleSheet(f"""
            color: {self.TEXT_MUTED};
            font-size: 11px;
            background: transparent;
            border: none;
            padding-top: 8px;
        """)
        card_layout.addWidget(footer)

        inner_layout.addWidget(card, 0, Qt.AlignHCenter)
        scroll.setWidget(inner)
        outer.addWidget(scroll)

        # Escape to close
        QShortcut(QKeySequence("Escape"), self, self.hide)
        QShortcut(QKeySequence("Ctrl+/"), self, self.hide)

    def toggle(self):
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.raise_()

    def showEvent(self, event):
        self.resize(self.parent().size())
        super().showEvent(event)

    def mousePressEvent(self, event):
        self.hide()


# ============================================================
# SECTION: Main Application Window
# ============================================================
class MainWindow(QMainWindow):
    """
    Main application window with modern dark UI styling.
    Features: Deep charcoal backgrounds, neon cyan accents, 
    subtle depth effects, and improved typography.
    """
    
    # Color palette - Modern Dark Theme with Neon Accents
    COLOR_BG_PRIMARY = "#050508"
    COLOR_BG_SECONDARY = "#0a0a0c"
    COLOR_BG_TERTIARY = "#1e1e24"
    COLOR_ACCENT_PRIMARY = "#00d4ff"
    COLOR_ACCENT_SECONDARY = "#7b61ff"
    COLOR_ACCENT_GRADIENT_START = "#00d4ff"
    COLOR_ACCENT_GRADIENT_END = "#7b61ff"
    COLOR_TEXT_PRIMARY = "#ffffff"
    COLOR_TEXT_SECONDARY = "#a0a0b0"
    COLOR_TEXT_MUTED = "#6a6a7a"
    COLOR_BORDER = "#2a2a35"
    COLOR_BORDER_HOVER = "#6b6b76"
    
    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings
        
        # Initialize extension with fallback
        self.extension = create_extension(settings.extension_name)
        if self.extension is None:
            fallback_name = get_extension_names()[0] if get_extension_names() else None
            if fallback_name:
                self.extension = create_extension(fallback_name)
                self.settings.set_extension(fallback_name)
        
        # Window configuration - KEEPING ORIGINAL MINIMUM SIZE
        self.setWindowTitle("wallppy")
        self.setMinimumSize(682, 500)
        self.resize(1100, 700)
        
        # Status tracking
        self._status_label = None
        self._clear_timer = None
        
        self.init_ui()
        self.apply_modern_dark_theme()
        self.setup_status_bar()
        self._setup_global_shortcuts()
        QApplication.instance().installEventFilter(self)

    # ============================================================
    # SECTION: UI Initialization
    # ============================================================
    def init_ui(self):
        """Initialize the main UI structure with stacked pages."""
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Stacked widget for page navigation
        self.stacked = FadeStackedWidget()
        layout.addWidget(self.stacked)

        # Landing page (search/explore interface)
        self.landing_page = LandingPage(self.settings)
        self.landing_page.search_requested.connect(self.on_search_requested)
        self.landing_page.explore_requested.connect(self.on_explore_requested)
        self.landing_page.explore_local_requested.connect(self.on_explore_local_requested)
        self.landing_page.extension_changed.connect(self.on_extension_changed)
        self.landing_page.status_message.connect(self.on_status_message)
        self.stacked.addWidget(self.landing_page)

        # Results page (gallery view)
        self.results_page = ResultsPage(self.extension, self.settings)
        self.results_page.home_requested.connect(self.go_home)
        self.results_page.search_requested.connect(self.on_search_requested)
        self.results_page.download_progress.connect(self.update_download_progress)
        self.results_page.download_finished.connect(self.on_download_finished)
        self.results_page.search_finished.connect(self._clear_highlighted_status)
        self.stacked.addWidget(self.results_page)

        self.stacked.setCurrentIndex(0)

        # Shortcuts overlay (on top of everything)
        self.shortcuts_overlay = ShortcutsOverlay(central)

    # ============================================================
    # SECTION: Event Handlers
    # ============================================================
    def eventFilter(self, obj, event):
        """Application-level event filter for grid navigation fallback."""
        if event.type() == QEvent.KeyPress and self.stacked.currentIndex() == 1:
            # Skip if filter panel has focus
            focused = QApplication.focusWidget()
            if self.results_page._filter_has_focus():
                return super().eventFilter(obj, event)
            key = event.key()
            nav_keys = {
                Qt.Key_Up: (-1, 0), Qt.Key_K: (-1, 0),
                Qt.Key_Down: (1, 0), Qt.Key_J: (1, 0),
                Qt.Key_Left: (0, -1), Qt.Key_H: (0, -1),
                Qt.Key_Right: (0, 1), Qt.Key_L: (0, 1),
            }
            if key in nav_keys and event.modifiers() == Qt.NoModifier:
                from .wallpaper_widget import WallpaperWidget
                if isinstance(focused, WallpaperWidget) and self.results_page._focused_wallpaper:
                    row_d, col_d = nav_keys[key]
                    self.results_page._navigate_grid(row_d, col_d)
                    return True
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event):
        """Handle Escape and Enter on landing page."""
        key = event.key()
        modifiers = event.modifiers()

        if key == Qt.Key_Escape and modifiers == Qt.NoModifier:
            if self.stacked.currentIndex() == 1:
                if self.results_page.overlay.isVisible():
                    return
                elif self.results_page.filter_panel.isVisible() and self.results_page._filter_has_focus():
                    self.results_page.toggle_filter_panel()
                    return
                else:
                    self.go_home()
                    return

        # Enter on landing page — search or explore
        if key in (Qt.Key_Return, Qt.Key_Enter) and modifiers == Qt.NoModifier:
            if self.stacked.currentIndex() == 0:
                self.landing_page.emit_search()
                return

        super().keyPressEvent(event)

    def _setup_global_shortcuts(self):
        """Global shortcuts that work regardless of focused widget."""
        # Ctrl+K — focus search bar
        sc = QShortcut(QKeySequence("Ctrl+K"), self)
        sc.setContext(Qt.ApplicationShortcut)
        sc.activated.connect(self._focus_search)

        # Ctrl+N — go home + focus search
        sc = QShortcut(QKeySequence("Ctrl+N"), self)
        sc.setContext(Qt.ApplicationShortcut)
        sc.activated.connect(self._go_home_focus_search)

        # Ctrl+D — download focused wallpaper
        sc = QShortcut(QKeySequence("Ctrl+D"), self)
        sc.setContext(Qt.ApplicationShortcut)
        sc.activated.connect(self._download_focused)

        # Ctrl+F — toggle filters (results page only)
        sc = QShortcut(QKeySequence("Ctrl+F"), self)
        sc.setContext(Qt.ApplicationShortcut)
        sc.activated.connect(self._toggle_filters)

        # Ctrl+S — cycle source (skip Local)
        cycle_action = QAction("Cycle Source", self)
        cycle_action.setShortcut(QKeySequence("Ctrl+S"))
        cycle_action.triggered.connect(self._cycle_source)
        self.addAction(cycle_action)

        # Ctrl+/ — show shortcuts
        sc = QShortcut(QKeySequence("Ctrl+/"), self)
        sc.setContext(Qt.ApplicationShortcut)
        sc.activated.connect(self._show_shortcuts_overlay)

        # Ctrl+L — explore downloaded wallpapers
        sc = QShortcut(QKeySequence("Ctrl+L"), self)
        sc.setContext(Qt.ApplicationShortcut)
        sc.activated.connect(self.on_explore_local_requested)

        # Ctrl+, — change download directory
        sc = QShortcut(QKeySequence("Ctrl+,"), self)
        sc.setContext(Qt.ApplicationShortcut)
        sc.activated.connect(self._change_download_dir)

        # Home — scroll to top on results page
        sc = QShortcut(QKeySequence("Home"), self)
        sc.setContext(Qt.ApplicationShortcut)
        sc.activated.connect(self._scroll_to_top)

    def _focus_search(self):
        if self.stacked.currentIndex() == 0:
            self.landing_page.search_edit.setFocus()
        else:
            self.results_page.search_edit.setFocus()

    def _go_home_focus_search(self):
        self.go_home()
        QTimer.singleShot(50, lambda: self.landing_page.search_edit.setFocus())

    def _download_focused(self):
        if self.stacked.currentIndex() == 1 and self.results_page._focused_wallpaper:
            self.results_page._focused_wallpaper.emit_download()

    def _toggle_filters(self):
        if self.stacked.currentIndex() == 1:
            self.results_page.toggle_filter_panel()

    def _cycle_source(self):
        combo = self.landing_page.ext_combo
        idx = (combo.currentIndex() + 1) % combo.count()
        combo.setCurrentIndex(idx)

    def _scroll_to_top(self):
        if self.stacked.currentIndex() == 1:
            self.results_page.scroll_to_top()

    def _change_download_dir(self):
        from PyQt5.QtWidgets import QFileDialog
        folder = QFileDialog.getExistingDirectory(
            self, "Select Download Folder", self.settings.download_folder
        )
        if folder:
            self.settings.set_download_folder(folder)
            self.landing_page.dir_edit.setText(folder)

    def _show_shortcuts_overlay(self):
        """Toggle keyboard shortcuts overlay."""
        self.shortcuts_overlay.toggle()

    def on_extension_changed(self, name: str):
        """Handle extension source changes."""
        new_ext = create_extension(name)
        if new_ext:
            self.extension = new_ext
            self.results_page.update_extension(new_ext)

    # ============================================================
    # SECTION: Status Bar Configuration
    # ============================================================
    def setup_status_bar(self):
        """Configure modern status bar with subtle styling."""
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("Ready")

        # Modern progress bar with neon gradient
        self.download_progress = QProgressBar()
        self.download_progress.setFixedWidth(160)
        self.download_progress.setFixedHeight(3)
        self.download_progress.setRange(0, 100)
        self.download_progress.setValue(0)
        self.download_progress.setVisible(False)
        self.download_progress.setTextVisible(False)
        self.download_progress.setStyleSheet(f"""
            QProgressBar {{
                background-color: {self.COLOR_BG_TERTIARY};
                border: none;
                border-radius: 1px;
                max-height: 3px;
                min-height: 3px;
            }}
            QProgressBar::chunk {{
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {self.COLOR_ACCENT_GRADIENT_START}, 
                    stop:1 {self.COLOR_ACCENT_GRADIENT_END});
                border-radius: 1px;
            }}
        """)
        self.status_bar.addPermanentWidget(self.download_progress)

        # Modern tip label - explicitly no border
        tip_label = QLabel("Double-click to download · Click 🖵 to set wallpaper")
        tip_label.setStyleSheet(f"""
            color: {self.COLOR_TEXT_MUTED}; 
            padding-right: 12px; 
            font-size: 11px;
            font-weight: 500;
            border: none;
            background: transparent;
        """)
        self.status_bar.addPermanentWidget(tip_label)

    def on_status_message(self, message: str):
        """Display status with appropriate styling."""
        if "Scanning" in message:
            self._set_highlighted_status(message)
        else:
            self._clear_highlighted_status()
            self.status_bar.showMessage(message)

    def _set_highlighted_status(self, message: str):
        """Show animated scanning indicator."""
        if self._clear_timer is not None:
            self._clear_timer.stop()
            self._clear_timer = None

        self._clear_highlighted_status()

        # Animated spinner with neon accent
        self._status_label = QLabel(f'<font color="{self.COLOR_ACCENT_PRIMARY}">⟳ {message}</font>')
        self._status_label.setTextFormat(Qt.RichText)
        self._status_label.setStyleSheet(f"""
            padding: 4px 10px;
            background-color: {self.COLOR_BG_TERTIARY};
            border-radius: 4px;
            border: 1px solid {self.COLOR_BORDER};
        """)
        self.status_bar.addWidget(self._status_label)
        self.status_bar.showMessage("")
        self._status_label.show()
        self.status_bar.repaint()

    def _clear_highlighted_status(self):
        """Clear temporary status and restore default."""
        if self._clear_timer is not None:
            self._clear_timer.stop()
            self._clear_timer = None

        if self._status_label is not None:
            self.status_bar.removeWidget(self._status_label)
            self._status_label.deleteLater()
            self._status_label = None

        if self.status_bar.currentMessage() == "":
            self.status_bar.showMessage("Ready")

    # ============================================================
    # SECTION: Modern Dark Theme Styling
    # ============================================================
    def apply_modern_dark_theme(self):
        """
        Apply comprehensive modern dark theme.
        Features: Deep charcoal base, neon cyan accents, 
        subtle borders, and improved typography.
        """
        # Application palette
        dark_palette = QPalette()
        dark_palette.setColor(QPalette.Window, QColor(self.COLOR_BG_PRIMARY))
        dark_palette.setColor(QPalette.WindowText, QColor(self.COLOR_TEXT_PRIMARY))
        dark_palette.setColor(QPalette.Base, QColor(self.COLOR_BG_SECONDARY))
        dark_palette.setColor(QPalette.AlternateBase, QColor(self.COLOR_BG_TERTIARY))
        dark_palette.setColor(QPalette.ToolTipBase, QColor(self.COLOR_BG_TERTIARY))
        dark_palette.setColor(QPalette.ToolTipText, QColor(self.COLOR_TEXT_PRIMARY))
        dark_palette.setColor(QPalette.Text, QColor(self.COLOR_TEXT_PRIMARY))
        dark_palette.setColor(QPalette.Button, QColor(self.COLOR_BG_TERTIARY))
        dark_palette.setColor(QPalette.ButtonText, QColor(self.COLOR_TEXT_PRIMARY))
        dark_palette.setColor(QPalette.BrightText, QColor(self.COLOR_ACCENT_PRIMARY))
        dark_palette.setColor(QPalette.Highlight, QColor(self.COLOR_ACCENT_PRIMARY))
        dark_palette.setColor(QPalette.HighlightedText, QColor(self.COLOR_BG_PRIMARY))
        QApplication.setPalette(dark_palette)

        # Global stylesheet with modern aesthetics
        # FIX: QLabel and QFrame have NO global border to avoid unwanted boxes around text
        self.setStyleSheet(f"""
            /* Base Typography */
            * {{
                font-family: 'Segoe UI', 'SF Pro Display', -apple-system, BlinkMacSystemFont, sans-serif;
            }}
            
            /* Main Window - Deep gradient background */
            QMainWindow {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {self.COLOR_BG_PRIMARY}, 
                    stop:1 {self.COLOR_BG_SECONDARY});
            }}
            
            /* Input Fields */
            QLineEdit {{
                background-color: {self.COLOR_BG_TERTIARY};
                border: 1px solid {self.COLOR_BORDER};
                border-radius: 8px;
                padding: 8px 12px;
                color: {self.COLOR_TEXT_PRIMARY};
                font-size: 14px;
                selection-background-color: {self.COLOR_ACCENT_PRIMARY};
                selection-color: {self.COLOR_BG_PRIMARY};
            }}
            
            QLineEdit:focus {{
                border: 1px solid {self.COLOR_ACCENT_PRIMARY};
                background-color: {self.COLOR_BG_SECONDARY};
            }}
            
            QLineEdit:hover:!focus {{
                border: 1px solid {self.COLOR_BORDER_HOVER};
            }}
            
            /* Buttons */
            QPushButton {{
                background-color: {self.COLOR_BG_TERTIARY};
                border: 1px solid {self.COLOR_BORDER};
                border-radius: 8px;
                padding: 8px 16px;
                color: {self.COLOR_TEXT_PRIMARY};
                font-size: 13px;
                font-weight: 500;
            }}
            
            QPushButton:hover {{
                background-color: {self.COLOR_BORDER_HOVER};
                border-color: {self.COLOR_ACCENT_PRIMARY};
            }}
            
            QPushButton:pressed {{
                background-color: {self.COLOR_BG_PRIMARY};
                border-color: {self.COLOR_ACCENT_PRIMARY};
            }}
            
            QPushButton:default {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #4d9fff, stop:1 #a78bfa);
                color: {self.COLOR_BG_PRIMARY};
                border: none;
                font-weight: 600;
            }}
            
            QPushButton:default:hover {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #6bb0ff, stop:1 #b9a0fc);
            }}
            
            /* Combo Boxes */
            QComboBox {{
                background-color: {self.COLOR_BG_TERTIARY};
                border: 1px solid {self.COLOR_BORDER};
                border-radius: 8px;
                padding: 6px 12px;
                color: {self.COLOR_TEXT_PRIMARY};
                font-size: 13px;
                min-width: 120px;
            }}
            
            QComboBox:hover {{
                border-color: {self.COLOR_BORDER_HOVER};
            }}
            
            QComboBox::drop-down {{
                border: none;
                width: 24px;
            }}
            
            QComboBox::down-arrow {{
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid {self.COLOR_TEXT_SECONDARY};
                margin-right: 8px;
            }}
            
            QComboBox QAbstractItemView {{
                background-color: {self.COLOR_BG_TERTIARY};
                color: {self.COLOR_TEXT_PRIMARY};
                border: 1px solid {self.COLOR_BORDER};
                border-radius: 8px;
                selection-background-color: {self.COLOR_ACCENT_PRIMARY};
                selection-color: {self.COLOR_BG_PRIMARY};
                padding: 4px;
            }}
            
            /* Checkboxes */
            QCheckBox {{
                border: none;
                background: transparent;
                color: {self.COLOR_TEXT_PRIMARY};
                font-size: 13px;
                spacing: 8px;
            }}
            
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border: 2px solid {self.COLOR_BORDER};
                border-radius: 4px;
                background-color: {self.COLOR_BG_TERTIARY};
            }}
            
            QCheckBox::indicator:hover {{
                border-color: {self.COLOR_BORDER_HOVER};
            }}
            
            QCheckBox::indicator:checked {{
                background-color: {self.COLOR_ACCENT_PRIMARY};
                border-color: {self.COLOR_ACCENT_PRIMARY};
            }}
            
            /* Scroll Areas */
            QScrollArea {{
                border: none;
                background: transparent;
            }}
            
            /* Scrollbars */
            QScrollBar:vertical {{
                background: transparent;
                width: 8px;
                border-radius: 4px;
                margin: 4px;
            }}
            
            QScrollBar::handle:vertical {{
                background: {self.COLOR_BORDER};
                border-radius: 4px;
                min-height: 40px;
            }}
            
            QScrollBar::handle:vertical:hover {{
                background: {self.COLOR_ACCENT_PRIMARY};
            }}
            
            QScrollBar::add-line:vertical, 
            QScrollBar::sub-line:vertical {{
                border: none;
                background: none;
                height: 0px;
            }}
            
            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical {{
                background: none;
            }}
            
            QScrollBar:horizontal {{
                background: transparent;
                height: 8px;
                border-radius: 4px;
                margin: 4px;
            }}
            
            QScrollBar::handle:horizontal {{
                background: {self.COLOR_BORDER};
                border-radius: 4px;
                min-width: 40px;
            }}
            
            QScrollBar::handle:horizontal:hover {{
                background: {self.COLOR_ACCENT_PRIMARY};
            }}
            
            /* Status Bar */
            QStatusBar {{
                background-color: {self.COLOR_BG_SECONDARY};
                color: {self.COLOR_TEXT_SECONDARY};
                font-size: 12px;
                border-top: 1px solid {self.COLOR_BORDER};
            }}
            
            QStatusBar::item {{
                border: none;
            }}
            
            /* Tooltips */
            QToolTip {{
                background-color: {self.COLOR_BG_TERTIARY};
                color: {self.COLOR_TEXT_PRIMARY};
                border: 1px solid {self.COLOR_BORDER};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
            }}
            
            /* Labels - FIX: NO border, NO background by default */
            QLabel {{
                color: {self.COLOR_TEXT_PRIMARY};
                background: transparent;
                border: none;
            }}
            
            /* Frames - FIX: NO global border, only when explicitly styled per-widget */
            QFrame {{
                background: transparent;
                border: none;
            }}
            
            /* Group Boxes */
            QGroupBox {{
                background-color: {self.COLOR_BG_TERTIARY};
                border: 1px solid {self.COLOR_BORDER};
                border-radius: 12px;
                margin-top: 12px;
                padding-top: 16px;
                font-weight: 600;
                color: {self.COLOR_TEXT_PRIMARY};
            }}
            
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 16px;
                padding: 0 8px;
                color: {self.COLOR_ACCENT_PRIMARY};
            }}
            
            /* Sliders */
            QSlider::groove:horizontal {{
                height: 4px;
                background: {self.COLOR_BORDER};
                border-radius: 2px;
            }}
            
            QSlider::sub-page:horizontal {{
                background: {self.COLOR_ACCENT_PRIMARY};
                border-radius: 2px;
            }}
            
            QSlider::handle:horizontal {{
                background: {self.COLOR_TEXT_PRIMARY};
                width: 16px;
                height: 16px;
                margin: -6px 0;
                border-radius: 8px;
            }}
            
            QSlider::handle:horizontal:hover {{
                background: {self.COLOR_ACCENT_PRIMARY};
            }}
        """)

    # ============================================================
    # SECTION: Navigation & Actions
    # ============================================================
    def on_search_requested(self, query: str):
        """Handle search request and switch to results."""
        self._clear_highlighted_status()
        self.results_page.start_search(query)
        self.stacked.setCurrentIndex(1)

    def on_explore_requested(self):
        """Handle explore request for recent uploads."""
        self.results_page.start_search("")
        self.stacked.setCurrentIndex(1)

    def on_explore_local_requested(self):
        """Handle explore request for local/downloaded wallpapers."""
        local_ext = create_extension("Local")
        if local_ext:
            self.extension = local_ext
            self.results_page.update_extension(local_ext)
            self.results_page.start_search("")
            self.stacked.setCurrentIndex(1)

    def go_home(self):
        """Return to landing page."""
        self._clear_highlighted_status()
        self.results_page.ensure_filter_collapsed()
        self.landing_page.set_search_text(self.results_page.search_edit.text())
        self.stacked.setCurrentIndex(0)

    def update_download_progress(self, value):
        """Update download progress bar."""
        self.download_progress.setVisible(True)
        self.download_progress.setValue(value)

    def on_download_finished(self, success, filepath, filename, wall_id):
        """Handle download completion with status message."""
        self.download_progress.setVisible(False)
        if success:
            timestamp = datetime.now().strftime("%H:%M:%S")
            msg = f"✓ Downloaded: {filename} → {self.settings.download_folder} ({timestamp})"
            self.status_bar.showMessage(msg)
        else:
            self.status_bar.showMessage(f"X Download failed: {filename}")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.shortcuts_overlay.isVisible():
            self.shortcuts_overlay.resize(self.centralWidget().size())

    def closeEvent(self, event):
        """Cleanup on application close."""
        if hasattr(self.extension, 'shutdown'):
            self.extension.shutdown()
        event.accept()