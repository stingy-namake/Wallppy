import os
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QLabel, QFileDialog, QComboBox, QFrame
)
from PyQt5.QtCore import Qt, pyqtSignal
from core.settings import Settings
from core.extension import get_extension_names


class LandingPage(QWidget):
    search_requested = pyqtSignal(str)
    explore_requested = pyqtSignal()
    extension_changed = pyqtSignal(str)
    
    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(24)

        container = QWidget()
        container.setFixedWidth(520)
        container_layout = QVBoxLayout(container)
        container_layout.setSpacing(16)

        title = QLabel("wallppy")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("""
            font-size: 42px; 
            font-weight: bold; 
            color: #1E6FF0;
            margin-bottom: 8px;
        """)
        container_layout.addWidget(title)

        # Source selector — original style with dropdown arrow
        src_layout = QHBoxLayout()
        src_layout.setSpacing(8)
        src_label = QLabel("Source")
        src_label.setStyleSheet("color: #888; font-size: 12px; text-transform: uppercase; letter-spacing: 1px;")
        self.ext_combo = QComboBox()
        self.ext_combo.addItems(get_extension_names())
        self.ext_combo.setCurrentText(self.settings.extension_name)
        self.ext_combo.currentTextChanged.connect(self.on_extension_changed)
        self.ext_combo.setStyleSheet("""
            QComboBox {
                background-color: transparent;
                border: none;
                color: #aaa;
                font-size: 12px;
                padding: 4px;
            }
            QComboBox::drop-down {
                border: none;
                width: 16px;
            }
            QComboBox QAbstractItemView {
                background-color: #2d2d2d;
                color: white;
                border: 1px solid #3d3d3d;
            }
        """)
        src_layout.addWidget(src_label)
        src_layout.addWidget(self.ext_combo)
        src_layout.addStretch()
        container_layout.addLayout(src_layout)

        # Search input
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search wallpapers...")
        self.search_edit.setFixedHeight(44)
        self.search_edit.setStyleSheet("""
            QLineEdit {
                font-size: 15px;
                padding: 0px 20px;
                border-radius: 6px;
                background-color: #2d2d2d;
                border: 1px solid #3d3d3d;
                color: white;
            }
            QLineEdit:focus {
                border: 1px solid #1E6FF0;
                background-color: #323232;
            }
        """)
        self.search_edit.returnPressed.connect(self.emit_search)
        container_layout.addWidget(self.search_edit)

        # Hint and Explore row
        hint_layout = QHBoxLayout()
        hint_layout.setSpacing(10)
        
        hint = QLabel("Press Enter to search")
        hint.setAlignment(Qt.AlignLeft)
        hint.setStyleSheet("color: #666; font-size: 12px;")
        hint_layout.addWidget(hint)
        hint_layout.addStretch()
        
        # Explore link — QLabel properly renders rich text
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
        divider.setStyleSheet("color: #333; max-height: 1px;")
        divider.setFixedHeight(1)
        container_layout.addSpacing(8)
        container_layout.addWidget(divider)
        container_layout.addSpacing(8)

        # Save to section
        dir_label = QLabel("Download Location")
        dir_label.setStyleSheet("color: #888; font-size: 11px; text-transform: uppercase; letter-spacing: 1px;")
        container_layout.addWidget(dir_label)
        
        dir_layout = QHBoxLayout()
        dir_layout.setSpacing(8)
        
        self.dir_edit = QLineEdit()
        self.dir_edit.setText(self.settings.download_folder)
        self.dir_edit.setReadOnly(True)
        self.dir_edit.setFixedHeight(32)
        self.dir_edit.setStyleSheet("""
            QLineEdit {
                background-color: #262626;
                border: 1px solid #333;
                border-radius: 4px;
                padding: 0px 10px;
                color: #aaa;
                font-size: 12px;
            }
        """)
        dir_layout.addWidget(self.dir_edit)
        
        self.browse_btn = QPushButton("Change")
        self.browse_btn.setFixedWidth(70)
        self.browse_btn.setFixedHeight(32)
        self.browse_btn.setStyleSheet("""
            QPushButton {
                background-color: #3d3d3d;
                border: none;
                border-radius: 4px;
                color: #ccc;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #4d4d4d;
                color: white;
            }
        """)
        self.browse_btn.clicked.connect(self.choose_directory)
        dir_layout.addWidget(self.browse_btn)
        
        container_layout.addLayout(dir_layout)
        
        layout.addWidget(container)
        
        # Initialize search box state based on current selection
        self.on_extension_changed(self.ext_combo.currentText())
    
    def emit_explore(self):
        """Emit signal for explore action (empty query)."""
        self.explore_requested.emit()
    
    def on_extension_changed(self, name: str):
        self.settings.set_extension(name)
        self.extension_changed.emit(name)
        
        # Gray out and block search box when using Local source
        if name == "Local":
            self.search_edit.setEnabled(False)
            self.search_edit.setPlaceholderText("Browsing local folder...")
            self.search_edit.setStyleSheet("""
                QLineEdit {
                    font-size: 15px;
                    padding: 0px 20px;
                    border-radius: 6px;
                    background-color: #252525;
                    border: 1px solid #333;
                    color: #666;
                }
            """)
        else:
            self.search_edit.setEnabled(True)
            self.search_edit.setPlaceholderText("Search wallpapers...")
            self.search_edit.setStyleSheet("""
                QLineEdit {
                    font-size: 15px;
                    padding: 0px 20px;
                    border-radius: 6px;
                    background-color: #2d2d2d;
                    border: 1px solid #3d3d3d;
                    color: white;
                }
                QLineEdit:focus {
                    border: 1px solid #1E6FF0;
                    background-color: #323232;
                }
            """)
    
    def emit_search(self):
        # Block search when disabled (Local source)
        if not self.search_edit.isEnabled():
            return
        query = self.search_edit.text().strip()
        if query:
            self.search_requested.emit(query)
    
    def choose_directory(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Download Folder", self.settings.download_folder)
        if folder:
            self.settings.set_download_folder(folder)
            self.dir_edit.setText(folder)
    
    def set_search_text(self, text: str):
        self.search_edit.setText(text)