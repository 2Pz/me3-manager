from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton, QVBoxLayout
from PyQt6.QtGui import QFont, QIcon, QPixmap, QPainter
from PyQt6.QtCore import pyqtSignal, Qt, QSize, QPropertyAnimation, QEasingCurve
from utils.resource_path import resource_path

class ModItem(QWidget):
    """Enhanced mod widget with expandable tree support and icon-based status indicators"""
    
    toggled = pyqtSignal(str, bool)
    delete_requested = pyqtSignal(str)
    open_folder_requested = pyqtSignal(str)
    edit_config_requested = pyqtSignal(str)
    regulation_activate_requested = pyqtSignal(str)
    advanced_options_requested = pyqtSignal(str)
    expand_requested = pyqtSignal(str, bool)  # New signal for expand/collapse
    
    def __init__(self, mod_path: str, mod_name: str, is_enabled: bool, is_external: bool, 
                 is_folder_mod: bool, is_regulation: bool, mod_type: str, type_icon: QIcon, 
                 item_bg_color: str, text_color: str, is_regulation_active: bool, 
                 has_advanced_options: bool = False, is_nested: bool = False, 
                 has_children: bool = False, is_expanded: bool = False):
        super().__init__()
        self.mod_path = mod_path
        self.mod_name = mod_name
        self.is_external = is_external
        self.is_enabled = is_enabled
        self.is_folder_mod = is_folder_mod
        self.is_regulation = is_regulation
        self.mod_type = mod_type
        self.type_icon = type_icon
        self.is_regulation_active = is_regulation_active
        self.is_nested = is_nested
        self.has_children = has_children
        self.is_expanded = is_expanded
        
        self._setup_styling(item_bg_color, is_nested)
        self._create_layout(text_color, has_advanced_options)
        self._setup_tooltip()
        self.update_toggle_button_ui()

    def _create_status_icon(self, icon_text: str, bg_color: str, text_color: str = "white", size: int = 20) -> QIcon:
        """Create a circular status icon with text"""
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw circle background
        painter.setBrush(Qt.GlobalColor.transparent)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.fillRect(0, 0, size, size, Qt.GlobalColor.transparent)
        
        # Draw colored circle
        from PyQt6.QtGui import QColor, QBrush
        painter.setBrush(QBrush(QColor(bg_color)))
        painter.drawEllipse(0, 0, size, size)
        
        # Draw icon text
        painter.setPen(QColor(text_color))
        font = QFont("Segoe UI", 10, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(0, 0, size, size, Qt.AlignmentFlag.AlignCenter, icon_text)
        
        painter.end()
        return QIcon(pixmap)

    def _create_diamond_icon(self, bg_color: str, size: int = 18) -> QIcon:
        """Create a diamond-shaped status icon"""
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        from PyQt6.QtGui import QColor, QBrush, QPolygon
        from PyQt6.QtCore import QPoint
        
        # Create diamond shape
        diamond = QPolygon([
            QPoint(size // 2, 2),           # Top
            QPoint(size - 2, size // 2),    # Right
            QPoint(size // 2, size - 2),    # Bottom
            QPoint(2, size // 2)            # Left
        ])
        
        painter.setBrush(QBrush(QColor(bg_color)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPolygon(diamond)
        
        painter.end()
        return QIcon(pixmap)

    def _setup_styling(self, item_bg_color, is_nested):
        """Setup widget styling based on mod type"""
        if is_nested:
            # Nested mod styling - heavily indented to the right under parent
            self.setStyleSheet(f"""
                ModItem {{
                    background-color: rgba(45, 45, 45, 0.3);
                    border: none;
                    border-left: 2px solid #555555;
                    border-radius: 0px;
                    padding: 4px 8px;
                    margin: 1px 0px 1px 80px;
                }}
                ModItem:hover {{
                    background-color: rgba(61, 61, 61, 0.5);
                    border-left: 2px solid #0078d4;
                }}
            """)
        else:
            # Parent mod styling - aligned with other main mods (no indentation)
            border_color = "#0078d4" if self.has_children else "#3d3d3d"
            self.setStyleSheet(f"""
                ModItem {{
                    background-color: {item_bg_color if item_bg_color != "transparent" else "#2a2a2a"};
                    border: 1px solid {border_color};
                    border-radius: 8px;
                    padding: 10px 12px;
                    margin: 3px 0px;
                }}
                ModItem:hover {{
                    background-color: #3a3a3a;
                    border-color: #0078d4;
                }}
            """)

    def _create_layout(self, text_color, has_advanced_options):
        """Create the main layout with all components"""
        layout = QHBoxLayout()
        layout.setContentsMargins(6 if self.is_nested else 12, 4 if self.is_nested else 8, 6 if self.is_nested else 12, 4 if self.is_nested else 8)
        
        # Left side: Icon + Name + Status Icons
        left_layout = QHBoxLayout()
        left_layout.setSpacing(6 if self.is_nested else 8)
        
        # For nested items - show connection indicator
        if self.is_nested:
            connector_label = QLabel()
            arrow_icon = QIcon(resource_path("resources/icon/arrow.png"))
            connector_label.setPixmap(arrow_icon.pixmap(QSize(14, 14)))
            connector_label.setFixedWidth(50)
            connector_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            left_layout.addWidget(connector_label)
        
        # Mod icon
        icon_label = QLabel()
        if self.type_icon:
            icon_label.setPixmap(self.type_icon.pixmap(QSize(18 if not self.is_nested else 15, 18 if not self.is_nested else 15)))
        left_layout.addWidget(icon_label)
        
        # Mod name
        name_label = QLabel(self.mod_name)
        font = QFont("Segoe UI", 11 if not self.is_nested else 9)
        font.setWeight(QFont.Weight.Medium if not self.is_nested else QFont.Weight.Normal)
        name_label.setFont(font)
        name_label.setStyleSheet(f"color: {text_color}; padding: 2px 0px;")
        left_layout.addWidget(name_label)
        
        # Status indicators with icons (only for main mods)
        if not self.is_nested:
            self._add_status_indicators(left_layout)
        
        layout.addLayout(left_layout)
        layout.addStretch()
        
        # Right side: Expand button + Action buttons
        # Expand/collapse button for parent mods with children (on the right side)
        if self.has_children and not self.is_nested:
            self.expand_btn = QPushButton()
            self.expand_btn.setFixedSize(24, 24)
            self.expand_btn.setStyleSheet(self._get_expand_button_style())
            self.expand_btn.clicked.connect(self._on_expand_clicked)
            self._update_expand_button()
            layout.addWidget(self.expand_btn)
        
        # Action buttons
        self._add_action_buttons(layout, has_advanced_options)
        
        self.setLayout(layout)

    def _add_status_indicators(self, layout):
        """Add status indicator icons"""
        # External mod indicator
        if self.is_external and not self.is_nested:
            external_icon = self._create_status_icon("E", "#ff8c00")
            external_label = QLabel()
            external_label.setPixmap(external_icon.pixmap(QSize(20, 20)))
            external_label.setToolTip("External Mod")
            external_label.setStyleSheet("""
                QLabel {
                    padding: 2px;
                    border-radius: 10px;
                }
                QLabel:hover {
                    background-color: rgba(255, 140, 0, 0.2);
                }
            """)
            layout.addWidget(external_label)
        
        # Children indicator for parent mods
        if self.has_children and not self.is_nested:
            children_icon = self._create_status_icon("▣", "#0078d4")
            children_label = QLabel()
            children_label.setPixmap(children_icon.pixmap(QSize(16, 16)))
            children_label.setToolTip("Contains nested mods")
            children_label.setStyleSheet("""
                QLabel {
                    padding: 1px;
                    border-radius: 8px;
                }
                QLabel:hover {
                    background-color: rgba(0, 120, 212, 0.2);
                }
            """)
            layout.addWidget(children_label)

    def _add_action_buttons(self, layout, has_advanced_options):
        """Add action buttons to the right side"""
        button_size = 28 if not self.is_nested else 24
        
        # Toggle button
        self.toggle_btn = QPushButton("⏻")
        self.toggle_btn.setFixedSize(button_size, button_size)
        self.toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_btn.clicked.connect(self.on_toggle)
        layout.addWidget(self.toggle_btn)
        
        # Config button (only for DLL mods)
        if not self.is_folder_mod and not self.is_regulation:
            config_btn = QPushButton("⚙️")
            config_btn.setFixedSize(button_size, button_size)
            config_btn.setToolTip("Edit mod configuration (.ini)")
            config_btn.setStyleSheet(self._get_action_button_style())
            config_btn.clicked.connect(lambda: self.edit_config_requested.emit(self.mod_path))
            layout.addWidget(config_btn)

        # Open folder button for external mods
        if self.is_external:
            open_btn = QPushButton("📂")
            open_btn.setFixedSize(button_size, button_size)
            open_btn.setToolTip("Open containing folder")
            open_btn.setStyleSheet(self._get_action_button_style())
            open_btn.clicked.connect(lambda: self.open_folder_requested.emit(self.mod_path))
            layout.addWidget(open_btn)
        
        # Advanced options button
        advanced_btn = QPushButton("🔧")
        advanced_btn.setFixedSize(button_size, button_size)
        advanced_btn.setToolTip("Advanced options (load order, initializers, etc.)")
        
        if has_advanced_options:
            advanced_btn.setStyleSheet(self._get_active_advanced_button_style())
        else:
            advanced_btn.setStyleSheet(self._get_action_button_style())
        
        advanced_btn.clicked.connect(lambda: self.advanced_options_requested.emit(self.mod_path))
        layout.addWidget(advanced_btn)
        
        # Delete button (hidden for nested mods)
        if not self.is_nested:
            delete_btn = QPushButton("🗑")
            delete_btn.setFixedSize(button_size, button_size)
            delete_btn.setToolTip("Delete mod")
            delete_btn.setStyleSheet(self._get_delete_button_style())
            delete_btn.clicked.connect(lambda: self.delete_requested.emit(self.mod_path))
            layout.addWidget(delete_btn)

        # Regulation activation button
        if self.is_regulation and not self.is_nested:
            self.activate_regulation_btn = QPushButton("🧩")
            self.activate_regulation_btn.setFixedSize(button_size, button_size)
            
            if self.is_regulation_active:
                self.activate_regulation_btn.setToolTip("This regulation file is currently active")
                self.activate_regulation_btn.setEnabled(False)
                self.activate_regulation_btn.setStyleSheet(self._get_active_regulation_button_style())
            else:
                self.activate_regulation_btn.setToolTip("Click to make this the active regulation file")
                self.activate_regulation_btn.setStyleSheet(self._get_action_button_style())

            self.activate_regulation_btn.clicked.connect(lambda: self.regulation_activate_requested.emit(self.mod_path))
            layout.addWidget(self.activate_regulation_btn)

    def _get_expand_button_style(self):
        """Style for expand/collapse button"""
        return """
            QPushButton {
                background-color: #3a3a3a;
                border: 1px solid #555555;
                color: #cccccc;
                font-size: 12px;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #0078d4;
                border-color: #0078d4;
                color: white;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
        """

    def _get_action_button_style(self):
        """Standard action button style"""
        radius = 12 if not self.is_nested else 10
        return f"""
            QPushButton {{
                background-color: #4a4a4a;
                border: none;
                border-radius: {radius}px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: #5a5a5a;
                border: 1px solid #0078d4;
            }}
        """

    def _get_active_advanced_button_style(self):
        """Style for advanced button when options are active"""
        radius = 12 if not self.is_nested else 10
        return f"""
            QPushButton {{
                background-color: #ff8c00;
                border: none;
                border-radius: {radius}px;
                font-size: 12px;
                color: white;
            }}
            QPushButton:hover {{
                background-color: #ffa500;
                border: 1px solid #ffaa00;
            }}
        """

    def _get_delete_button_style(self):
        """Style for delete button"""
        radius = 12 if not self.is_nested else 10
        return f"""
            QPushButton {{
                background-color: #4a4a4a;
                border: none;
                border-radius: {radius}px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: #dc3545;
                border: 1px solid #c82333;
            }}
        """

    def _get_active_regulation_button_style(self):
        """Style for active regulation button"""
        radius = 12 if not self.is_nested else 10
        return f"""
            QPushButton {{
                background-color: #28a745;
                border: none;
                border-radius: {radius}px;
                font-size: 12px;
                color: white;
            }}
            QPushButton:disabled {{
                background-color: #28a745;
                color: white;
            }}
        """

    def _update_expand_button(self):
        """Update expand button icon based on state"""
        if hasattr(self, 'expand_btn'):
            self.expand_btn.setText("▼" if self.is_expanded else "▶")

    def _on_expand_clicked(self):
        """Handle expand/collapse button click"""
        self.is_expanded = not self.is_expanded
        self._update_expand_button()
        self.expand_requested.emit(self.mod_path, self.is_expanded)

    def _setup_tooltip(self):
        """Setup tooltip based on mod type"""
        if self.is_nested:
            self.setToolTip(f"Nested DLL: {self.mod_name}\nPath: {self.mod_path}\n\nThis mod is part of a parent package.")
        else:
            tooltip_parts = [f"Type: {self.mod_type}", f"Path: {self.mod_path}"]
            if self.has_children:
                tooltip_parts.append("Click ▶ to expand nested mods")
            self.setToolTip("\n".join(tooltip_parts))

    def update_toggle_button_ui(self):
        """Update toggle button appearance based on enabled state"""
        radius = 12 if not self.is_nested else 10
        
        if self.is_enabled:
            self.toggle_btn.setToolTip("Click to disable")
            style = f"""
                QPushButton {{
                    background-color: #28a745;
                    border: none;
                    border-radius: {radius}px;
                    font-size: 14px;
                    color: white;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background-color: #34ce57;
                    border: 1px solid #28a745;
                }}
            """
        else:
            self.toggle_btn.setToolTip("Click to enable")
            style = f"""
                QPushButton {{
                    background-color: #dc3545;
                    border: none;
                    border-radius: {radius}px;
                    font-size: 14px;
                    color: white;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background-color: #e04558;
                    border: 1px solid #dc3545;
                }}
            """
        
        self.toggle_btn.setStyleSheet(style)

    def on_toggle(self):
        """Handle toggle button click"""
        self.is_enabled = not self.is_enabled
        self.update_toggle_button_ui()
        self.toggled.emit(self.mod_path, self.is_enabled)

    def set_expanded(self, expanded: bool):
        """Programmatically set expanded state"""
        self.is_expanded = expanded
        self._update_expand_button()