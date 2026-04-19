import os
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QLabel, QFileDialog, QComboBox, QFrame, QApplication
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from core.settings import Settings
from core.extension import get_extension_names


class LandingPage(QWidget):
    search_requested = pyqtSignal(str)
    explore_requested = pyqtSignal()
    extension_changed = pyqtSignal(str)
    status_message = pyqtSignal(str)

    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        
        # Debounce timer for search
        self._search_debounce_timer = QTimer()
        self._search_debounce_timer.setSingleShot(True)
        self._search_debounce_timer.timeout.connect(self._debounced_search)
        self._pending_search_query = ""
        
        self.init_ui()
        # Initial extension state
        self.on_extension_changed(self.ext_combo.currentText())

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(24)

        container = QWidget()
        container.setFixedWidth(560)
        container_layout = QVBoxLayout(container)
        container_layout.setSpacing(20)

        # Title with a subtle gradient
        title = QLabel("wallppy")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("""
            font-size: 48px;
            font-weight: 800;
            color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #1E6FF0, stop:1 #00c6ff);
            margin-bottom: 8px;
        """)
        container_layout.addWidget(title)

        # Source selector
        src_layout = QHBoxLayout()
        src_layout.setSpacing(8)
        src_label = QLabel("SOURCE")
        src_label.setStyleSheet("color: #777; font-size: 11px; font-weight: 600; letter-spacing: 1px;")
        self.ext_combo = QComboBox()
        self.ext_combo.addItems(get_extension_names())
        self.ext_combo.setCurrentText(self.settings.extension_name)
        self.ext_combo.currentTextChanged.connect(self.on_extension_changed)
        self.ext_combo.setStyleSheet("""
            QComboBox {
                background-color: transparent;
                border: none;
                color: #ccc;
                font-size: 13px;
                padding: 4px 0px;
            }
            QComboBox::drop-down {
                border: none;
                width: 16px;
            }
            QComboBox QAbstractItemView {
                background-color: #2d2d2d;
                color: white;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                selection-background-color: #1E6FF0;
            }
        """)
        src_layout.addWidget(src_label)
        src_layout.addWidget(self.ext_combo)
        src_layout.addStretch()
        container_layout.addLayout(src_layout)

        # Search input with clear button
        search_wrapper = QFrame()
        search_wrapper.setStyleSheet("""
            QFrame {
                background-color: #2a2a2f;
                border-radius: 8px;
                border: 1px solid #3a3a40;
            }
        """)
        search_layout = QHBoxLayout(search_wrapper)
        search_layout.setContentsMargins(16, 2, 8, 2)
        search_layout.setSpacing(8)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search wallpapers...")
        self.search_edit.setFixedHeight(48)
        self.search_edit.setStyleSheet("""
            QLineEdit {
                font-size: 15px;
                padding: 0px;
                background: transparent;
                border: none;
                color: white;
            }
            QLineEdit:focus {
                border: none;
            }
        """)
        self.search_edit.returnPressed.connect(self.emit_search)
        self.search_edit.textChanged.connect(self.on_search_text_changed)
        search_layout.addWidget(self.search_edit)

        self.clear_btn = QPushButton("✕")
        self.clear_btn.setFixedSize(24, 24)
        self.clear_btn.setFlat(True)
        self.clear_btn.setCursor(Qt.PointingHandCursor)
        self.clear_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #888;
                font-size: 14px;
                border: none;
                border-radius: 12px;
            }
            QPushButton:hover {
                background: #3a3a40;
                color: white;
            }
        """)
        self.clear_btn.clicked.connect(self.clear_search)
        self.clear_btn.hide()
        search_layout.addWidget(self.clear_btn)

        container_layout.addWidget(search_wrapper)

        # Hint row
        hint_layout = QHBoxLayout()
        hint_layout.setSpacing(10)

        hint = QLabel("⏎ Enter to search")
        hint.setAlignment(Qt.AlignLeft)
        hint.setStyleSheet("color: #666; font-size: 12px;")
        hint_layout.addWidget(hint)
        hint_layout.addStretch()

        self.explore_label = QLabel('or <font color="#1E6FF0">explore</font> recent uploads →')
        self.explore_label.setTextFormat(Qt.RichText)
        self.explore_label.setStyleSheet("""
            QLabel {
                color: #888;
                font-size: 12px;
                background: transparent;
            }
        """)
        self.explore_label.setCursor(Qt.PointingHandCursor)
        self.explore_label.mousePressEvent = lambda ev: self.emit_explore() if ev.button() == Qt.LeftButton else None
        hint_layout.addWidget(self.explore_label)

        container_layout.addLayout(hint_layout)

        # Divider
        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setStyleSheet("color: #2a2a2f; max-height: 1px;")
        divider.setFixedHeight(1)
        container_layout.addSpacing(8)
        container_layout.addWidget(divider)
        container_layout.addSpacing(8)

        # Download location
        dir_label = QLabel("DOWNLOAD LOCATION")
        dir_label.setStyleSheet("color: #777; font-size: 11px; font-weight: 600; letter-spacing: 1px;")
        container_layout.addWidget(dir_label)

        dir_layout = QHBoxLayout()
        dir_layout.setSpacing(8)

        self.dir_edit = QLineEdit()
        self.dir_edit.setText(self.settings.download_folder)
        self.dir_edit.setReadOnly(True)
        self.dir_edit.setFixedHeight(36)
        self.dir_edit.setStyleSheet("""
            QLineEdit {
                background-color: #202024;
                border: 1px solid #333;
                border-radius: 6px;
                padding: 0px 12px;
                color: #aaa;
                font-size: 12px;
            }
        """)
        dir_layout.addWidget(self.dir_edit)

        self.browse_btn = QPushButton("Change")
        self.browse_btn.setFixedWidth(80)
        self.browse_btn.setFixedHeight(36)
        self.browse_btn.setStyleSheet("""
            QPushButton {
                background-color: #3a3a40;
                border: none;
                border-radius: 6px;
                color: #ddd;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #4a4a50;
                color: white;
            }
        """)
        self.browse_btn.clicked.connect(self.choose_directory)
        dir_layout.addWidget(self.browse_btn)

        container_layout.addLayout(dir_layout)

        layout.addWidget(container)

    def on_search_text_changed(self, text):
        self.clear_btn.setVisible(bool(text))
        # Debounce the search (optional - currently only search on Enter)
        self._pending_search_query = text.strip()
        self._search_debounce_timer.stop()
        self._search_debounce_timer.start(300)

    def _debounced_search(self):
        """Called after user stops typing (optional live search)."""
        # Uncomment to enable live search:
        # if self._pending_search_query and self.search_edit.isEnabled():
        #     self.search_requested.emit(self._pending_search_query)
        pass

    def clear_search(self):
        self.search_edit.clear()
        self.search_edit.setFocus()
        self._search_debounce_timer.stop()

    def emit_explore(self):
        self.explore_requested.emit()

    def on_extension_changed(self, name: str):
        if name != "Local":
            self.settings.set_extension(name)

        self.extension_changed.emit(name)

        if name == "Local":
            self.search_edit.setEnabled(False)
            self.search_edit.setPlaceholderText("Browsing local folder...")
            self.search_edit.setStyleSheet("""
                QLineEdit {
                    font-size: 15px;
                    padding: 0px;
                    background: transparent;
                    border: none;
                    color: #666;
                }
            """)
            self.clear_btn.hide()
            self.status_message.emit("Scanning local folder...")
            self.explore_requested.emit()
        else:
            self.search_edit.setEnabled(True)
            self.search_edit.setPlaceholderText("Search wallpapers...")
            self.search_edit.setStyleSheet("""
                QLineEdit {
                    font-size: 15px;
                    padding: 0px;
                    background: transparent;
                    border: none;
                    color: white;
                }
            """)
            self.on_search_text_changed(self.search_edit.text())
            self.status_message.emit("Ready")

    def emit_search(self):
        if not self.search_edit.isEnabled():
            return
        query = self.search_edit.text().strip()
        if query:
            self._search_debounce_timer.stop()
            self.search_requested.emit(query)

    def choose_directory(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Download Folder", self.settings.download_folder)
        if folder:
            self.settings.set_download_folder(folder)
            self.dir_edit.setText(folder)

    def set_search_text(self, text: str):
        """Set the search text (called when returning from results page)."""
        self.search_edit.setText(text)