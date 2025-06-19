# ui/mod_item.py

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton
from PyQt6.QtGui import QFont
from PyQt6.QtCore import pyqtSignal, Qt

class ModItem(QWidget):
    """Custom widget for displaying mod information with toggle"""
    
    toggled = pyqtSignal(str, bool)
    delete_requested = pyqtSignal(str)
    open_folder_requested = pyqtSignal(str)
    edit_config_requested = pyqtSignal(str)
    
    def __init__(self, mod_path: str, mod_name: str, is_enabled: bool, is_external: bool = False, is_folder_mod: bool = False):
        super().__init__()
        self.mod_path = mod_path
        self.mod_name = mod_name
        self.is_external = is_external
        self.is_enabled = is_enabled # Store enabled state internally
        self.is_folder_mod = is_folder_mod # <-- FIX: Add this line
        
        self.setStyleSheet("""
            ModItem {
                background-color: #2d2d2d;
                border: 1px solid #3d3d3d;
                border-radius: 8px;
                padding: 8px;
                margin: 2px;
            }
            ModItem:hover {
                background-color: #3d3d3d;
                border-color: #4d4d4d;
            }
        """)
        
        layout = QHBoxLayout()
        layout.setContentsMargins(12, 8, 12, 8)
        
        # --- Start of Changed Block ---
        # Status indicator (self.status_label) has been removed.
        
        # Mod name with icon
        name_layout = QHBoxLayout()
        name_layout.setSpacing(8)

        if self.is_folder_mod:
            icon_label = QLabel("📁")
            icon_label.setStyleSheet("color: #ffa500; font-size: 12px;")
            name_layout.addWidget(icon_label)
        else:
            icon_label = QLabel("⚙️")
            icon_label.setStyleSheet("color: #569cd6; font-size: 12px;")
            name_layout.addWidget(icon_label)

        name_label = QLabel(mod_name)
        name_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Medium))
        name_label.setStyleSheet("color: #ffffff; font-weight: 500;")
        name_layout.addWidget(name_label)

        name_widget = QWidget()
        name_widget.setLayout(name_layout)
        layout.addWidget(name_widget)
        # --- End of Changed Block ---
        
        # External indicator
        if is_external:
            external_label = QLabel("📁 External")
            external_label.setStyleSheet("color: #ffa500; font-size: 9px;")
            layout.addWidget(external_label)
        
        layout.addStretch()
        
        # Toggle button (replaces QCheckBox)
        self.toggle_btn = QPushButton("⏻") # Power symbol icon
        self.toggle_btn.setFixedSize(30, 30)
        self.toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_btn.clicked.connect(self.on_toggle)
        layout.addWidget(self.toggle_btn)
        
        # Config button (only for DLL mods)
        if not self.is_folder_mod:
            config_btn = QPushButton("⚙️")
            config_btn.setFixedSize(30, 30)
            config_btn.setToolTip("Edit mod configuration (.ini)")
            config_btn.setStyleSheet("""
                QPushButton {
                    background-color: #4d4d4d;
                    border: none;
                    border-radius: 15px;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: #5d5d5d;
                }
            """)
            config_btn.clicked.connect(lambda: self.edit_config_requested.emit(self.mod_path))
            layout.addWidget(config_btn)

        # Buttons
        if is_external:
            open_btn = QPushButton("📂")
            open_btn.setFixedSize(30, 30)
            open_btn.setStyleSheet("""
                QPushButton {
                    background-color: #4d4d4d;
                    border: none;
                    border-radius: 15px;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: #5d5d5d;
                }
            """)
            open_btn.clicked.connect(lambda: self.open_folder_requested.emit(self.mod_path))
            layout.addWidget(open_btn)
        
        delete_btn = QPushButton("🗑")
        delete_btn.setFixedSize(30, 30)
        delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #4d4d4d;
                border: none;
                border-radius: 15px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #cc4444;
            }
        """)
        delete_btn.clicked.connect(lambda: self.delete_requested.emit(self.mod_path))
        layout.addWidget(delete_btn)
        
        self.setLayout(layout)
        mod_type = "Folder Mod" if self.is_folder_mod else "DLL Mod"
        self.setToolTip(f"Type: {mod_type}\nPath: {mod_path}")
        self.update_toggle_button_ui() # Set initial tooltip
    
    def update_toggle_button_ui(self):
        """Updates the toggle button's tooltip and color based on the mod's state."""
        base_style = """
            QPushButton {{
                background-color: {color};
                border: none;
                border-radius: 15px;
                font-size: 14px;
                color: white;
            }}
            QPushButton:hover {{
                background-color: {hover_color};
            }}
        """
        if self.is_enabled:
            self.toggle_btn.setToolTip("Click to disable")
            # Green for active
            color = "#6a9955"
            hover_color = "#7aa865"
        else:
            self.toggle_btn.setToolTip("Click to enable")
            # Red for disabled
            color = "#cc4444"
            hover_color = "#d85555"

        self.toggle_btn.setStyleSheet(base_style.format(color=color, hover_color=hover_color))
    
    def on_toggle(self):
        self.is_enabled = not self.is_enabled
        self.update_toggle_button_ui()
        self.toggled.emit(self.mod_path, self.is_enabled)
