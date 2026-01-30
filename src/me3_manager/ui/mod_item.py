from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSizePolicy, QWidget

from me3_manager.utils.resource_path import resource_path
from me3_manager.utils.translator import tr


class TreeConnector(QWidget):
    """Widget that draws tree connection lines."""

    def __init__(self, is_last_child: bool, parent=None):
        super().__init__(parent)
        self.is_last_child = is_last_child
        self.setFixedWidth(30)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)

    def sizeHint(self):
        return QSize(30, 0)  # Width 30, Height variable

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Line color
        color = QColor("#666666")
        pen = QPen(color)
        pen.setWidth(1)
        painter.setPen(pen)

        # Geometry
        rect = self.rect()
        center_x = rect.width() // 2
        center_y = rect.height() // 2

        # Draw vertical line
        # From top to center (or bottom if not last child)
        if self.is_last_child:
            painter.drawLine(center_x, 0, center_x, center_y)
        else:
            painter.drawLine(center_x, 0, center_x, rect.height())

        # Draw horizontal line
        # From center to right
        painter.drawLine(center_x, center_y, rect.width(), center_y)

        painter.end()


class TreeExpandButton(QPushButton):
    """Custom paint button for tree expansion."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(24, 24)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.is_expanded = False

    def set_expanded(self, expanded: bool):
        self.is_expanded = expanded
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw arrow
        # Match tree connector color or slightly brighter for button
        pen = QPen(QColor("#cccccc"))
        pen.setWidth(2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)

        rect = self.rect()
        center_x = rect.width() // 2
        center_y = rect.height() // 2
        offset = 4

        if self.is_expanded:
            # Down arrow (Chevron)
            painter.drawLine(center_x - offset, center_y - 2, center_x, center_y + 3)
            painter.drawLine(center_x, center_y + 3, center_x + offset, center_y - 2)
        else:
            # Right arrow (Chevron)
            painter.drawLine(center_x - 2, center_y - offset, center_x + 3, center_y)
            painter.drawLine(center_x + 3, center_y, center_x - 2, center_y + offset)

        painter.end()


class ModItem(QWidget):
    """Enhanced mod widget with expandable tree support and icon-based status indicators"""

    toggled = Signal(str, bool)
    delete_requested = Signal(str)
    rename_requested = Signal(str)
    open_folder_requested = Signal(str)
    edit_config_requested = Signal(str)
    regulation_activate_requested = Signal(str)
    advanced_options_requested = Signal(str)
    expand_requested = Signal(str, bool)  # New signal for expand/collapse
    clicked = Signal(str)  # Emitted when the row is clicked (for sidebar/details)

    def __init__(
        self,
        mod_path: str,
        mod_name: str,
        is_enabled: bool,
        is_external: bool,
        is_folder_mod: bool,
        is_regulation: bool,
        mod_type: str,
        type_icon: QIcon,
        item_bg_color: str,
        text_color: str,
        is_regulation_active: bool,
        has_advanced_options: bool = False,
        is_nested: bool = False,
        has_children: bool = False,
        is_expanded: bool = False,
        is_container: bool = False,
        update_available_version: str | None = None,
        is_last_child: bool = False,
    ):
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
        self.is_container = is_container
        self.update_available_version = update_available_version
        self.is_last_child = is_last_child

        self._setup_styling(item_bg_color, is_nested)
        self._create_layout(text_color, has_advanced_options)
        self._setup_tooltip()
        self.update_toggle_button_ui()

    def _create_status_icon(
        self, icon_text: str, bg_color: str, text_color: str = "white", size: int = 20
    ) -> QIcon:
        """Create a circular status icon with text"""
        pixmap, painter = self._create_transparent_pixmap(size)

        # Draw circle background
        painter.setBrush(Qt.GlobalColor.transparent)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.fillRect(0, 0, size, size, Qt.GlobalColor.transparent)

        # Draw colored circle
        from PySide6.QtGui import QBrush, QColor

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
        pixmap, painter = self._create_transparent_pixmap(size)

        from PySide6.QtCore import QPoint
        from PySide6.QtGui import QBrush, QColor, QPolygon

        # Create diamond shape
        diamond = QPolygon(
            [
                QPoint(size // 2, 2),  # Top
                QPoint(size - 2, size // 2),  # Right
                QPoint(size // 2, size - 2),  # Bottom
                QPoint(2, size // 2),  # Left
            ]
        )

        painter.setBrush(QBrush(QColor(bg_color)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPolygon(diamond)

        painter.end()
        return QIcon(pixmap)

    def _create_transparent_pixmap(self, size: int) -> tuple[QPixmap, QPainter]:
        """Create a transparent pixmap with antialiased painter."""
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        return pixmap, painter

    def _setup_styling(self, item_bg_color, is_nested):
        """Setup widget styling based on mod type"""
        if is_nested:
            # Nested mod styling - indented nicely under parent
            # The tree ASCII art will handle the rest of the visual indentation
            self.setStyleSheet("""
                ModItem {
                    background-color: rgba(45, 45, 45, 0.3);
                    border: none;
                    border-left: 2px solid transparent; 
                    border-radius: 0px;
                    padding: 0px 8px 0px 0px;
                    margin: 0px 0px 0px 30px; 
                }
                ModItem:hover {
                    background-color: rgba(61, 61, 61, 0.5);
                    border-left: 2px solid #0078d4;
                }
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
        # Reduce vertical padding for nested items to connect the lines better
        layout.setContentsMargins(
            0 if self.is_nested else 12,
            0 if self.is_nested else 8,
            6 if self.is_nested else 12,
            0 if self.is_nested else 8,
        )

        # Left side: Icon + Name + Status Icons
        left_layout = QHBoxLayout()
        # Remove spacing for connector to touch the icon/content
        left_layout.setSpacing(0 if self.is_nested else 8)

        # For nested items - show connection indicator (Tree style)
        if self.is_nested:
            connector = TreeConnector(self.is_last_child)
            left_layout.addWidget(connector)

            # Add a small spacer after the connector for visual padding before the icon
            # container_widget = QWidget()
            # container_widget.setFixedWidth(5)
            # left_layout.addWidget(container_widget)

            # Actually, standard spacing might be fine if we want a gap.
            # But "tree command" usually has the line touch the item name/icon.
            # Let's add a small fixed gap.
            left_layout.addSpacing(5)

        # Mod icon
        icon_label = QLabel()
        if self.type_icon:
            icon_label.setPixmap(
                self.type_icon.pixmap(
                    QSize(
                        18 if not self.is_nested else 15,
                        18 if not self.is_nested else 15,
                    )
                )
            )
        left_layout.addWidget(icon_label)

        # Mod name
        name_label = QLabel(self.mod_name)
        font = QFont("Segoe UI", 11 if not self.is_nested else 9)
        font.setWeight(
            QFont.Weight.Medium if not self.is_nested else QFont.Weight.Normal
        )
        name_label.setFont(font)
        name_label.setStyleSheet(f"color: {text_color}; padding: 2px 0px;")
        left_layout.addWidget(name_label)

        # Update available badge (only for main mods)
        # Update available badge (only for main mods)
        if not self.is_nested:
            self.update_label = QLabel()
            self.update_label.setStyleSheet(
                "color: #ffb020; font-size: 10px; padding: 2px 0px 2px 6px;"
            )
            self.update_label.setAlignment(Qt.AlignmentFlag.AlignVCenter)
            left_layout.addWidget(self.update_label)

            # Use setter to handle visibility/text to avoid duplication
            self.set_update_available(self.update_available_version)

        # Status indicators with icons (only for main mods)
        if not self.is_nested:
            self._add_status_indicators(left_layout)

        layout.addLayout(left_layout)
        layout.addStretch()

        # Right side: Expand button + Action buttons
        # Expand/collapse button for parent mods with children (on the right side)
        if self.has_children and not self.is_nested:
            self.expand_btn = TreeExpandButton()
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
            external_label.setToolTip(tr("external_mod_tooltip"))
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

    def _add_action_buttons(self, layout, has_advanced_options):
        """Add action buttons to the right side"""
        button_size = 28

        # Toggle button
        self.toggle_btn = QPushButton()
        self.toggle_btn.setIcon(QIcon(resource_path("resources/icon/activate.svg")))
        self.toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_btn.clicked.connect(self.on_toggle)
        layout.addWidget(self.toggle_btn)

        # Config button (only for DLL mods)
        if not self.is_folder_mod and not self.is_regulation and not self.is_container:
            config_btn = QPushButton()
            config_btn.setIcon(QIcon(resource_path("resources/icon/settings.svg")))
            config_btn.setFixedSize(button_size, button_size)
            config_btn.setToolTip(tr("edit_config_tooltip_ini"))
            config_btn.setStyleSheet(self._get_action_button_style())
            config_btn.clicked.connect(
                lambda: self.edit_config_requested.emit(self.mod_path)
            )
            layout.addWidget(config_btn)

        # Open folder button for external mods
        if self.is_external and not self.is_container:
            open_btn = QPushButton()
            open_btn.setIcon(QIcon(resource_path("resources/icon/folder.svg")))
            open_btn.setToolTip(tr("open_containing_folder_tooltip"))
            open_btn.setStyleSheet(self._get_action_button_style())
            open_btn.clicked.connect(
                lambda: self.open_folder_requested.emit(self.mod_path)
            )
            layout.addWidget(open_btn)

        # Advanced options button (skip for parent containers)
        if not self.is_container:
            advanced_btn = QPushButton()
            advanced_btn.setIcon(
                QIcon(resource_path("resources/icon/advanced_options.svg"))
            )
            advanced_btn.setToolTip(tr("advanced_options_tooltip"))

            if has_advanced_options:
                advanced_btn.setStyleSheet(self._get_active_advanced_button_style())
            else:
                advanced_btn.setStyleSheet(self._get_action_button_style())

            advanced_btn.clicked.connect(
                lambda: self.advanced_options_requested.emit(self.mod_path)
            )
            layout.addWidget(advanced_btn)

        # Delete button (skip only for nested mods)
        if not self.is_nested:
            delete_btn = QPushButton()
            delete_btn.setIcon(QIcon(resource_path("resources/icon/delete.svg")))
            delete_btn.setFixedSize(button_size, button_size)
            delete_btn.setToolTip(tr("delete_mod_tooltip"))
            delete_btn.setStyleSheet(self._get_delete_button_style())
            delete_btn.clicked.connect(
                lambda: self.delete_requested.emit(self.mod_path)
            )
            layout.addWidget(delete_btn)

        # Regulation button (show for any folder with regulation)
        if self.is_regulation:
            self.activate_regulation_btn = QPushButton()
            self.activate_regulation_btn.setIcon(
                QIcon(resource_path("resources/icon/regulation.svg"))
            )
            self.activate_regulation_btn.setFixedSize(button_size, button_size)

            if self.is_regulation_active:
                self.activate_regulation_btn.setToolTip(tr("click_to_disable_tooltip"))
                self.activate_regulation_btn.setStyleSheet(
                    self._get_active_regulation_button_style()
                )
            else:
                self.activate_regulation_btn.setToolTip(
                    tr("regulation_inactive_tooltip")
                )
                self.activate_regulation_btn.setStyleSheet(
                    self._get_action_button_style()
                )

            self.activate_regulation_btn.clicked.connect(
                lambda: self.regulation_activate_requested.emit(self.mod_path)
            )
            layout.addWidget(self.activate_regulation_btn)

    def _get_expand_button_style(self):
        """Style for expand/collapse button"""
        radius = 12 if not self.is_nested else 10
        return f"""
            QPushButton {{
                background-color: #4a4a4a;
                border: none;
                border-radius: {radius}px;
                color: #cccccc;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #5a5a5a;
                border: 1px solid #0078d4;
                color: white;
            }}
            QPushButton:pressed {{
                background-color: #005a9e;
            }}
        """

    def _get_action_button_style(self):
        """Standard action button style"""
        radius = 12 if not self.is_nested else 10
        return f"""
            QPushButton {{
                background-color: #4a4a4a;
                border: none;
                border-radius: {radius}px;
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
                color: white;
            }}
            QPushButton:disabled {{
                background-color: #28a745;
                color: white;
            }}
        """

    def _update_expand_button(self):
        """Update expand button icon based on state"""
        if hasattr(self, "expand_btn"):
            self.expand_btn.set_expanded(self.is_expanded)

    def _on_expand_clicked(self):
        """Handle expand/collapse button click"""
        self.is_expanded = not self.is_expanded
        self._update_expand_button()
        self.expand_requested.emit(self.mod_path, self.is_expanded)

    def _setup_tooltip(self):
        """Setup tooltip based on mod type"""
        if self.is_nested:
            self.setToolTip(
                tr(
                    "nested_mod_full_tooltip",
                    mod_name=self.mod_name,
                    mod_path=self.mod_path,
                )
            )
        else:
            tooltip_parts = [
                tr("mod_type_tooltip", mod_type=self.mod_type),
                tr("mod_path_tooltip", mod_path=self.mod_path),
            ]
            if self.has_children:
                tooltip_parts.append("Click > to expand nested mods")

            tooltip_html = "<br>".join(tooltip_parts)
            self.setToolTip(tooltip_html)

    def update_toggle_button_ui(self):
        """Update toggle button appearance based on enabled state"""
        if not hasattr(self, "toggle_btn"):
            return

        radius = 12 if not self.is_nested else 10

        if self.is_enabled:
            self.toggle_btn.setToolTip(tr("click_to_disable_tooltip"))
            style = f"""
                QPushButton {{
                    background-color: #28a745;
                    border: none;
                    border-radius: {radius}px;
                    color: white;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background-color: #34ce57;
                    border: 1px solid #28a745;
                }}
            """
        else:
            self.toggle_btn.setToolTip(tr("click_to_enable_tooltip"))
            style = f"""
                QPushButton {{
                    background-color: #dc3545;
                    border: none;
                    border-radius: {radius}px;
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

    def mousePressEvent(self, event):
        """Emit a click signal for selection (sidebar/details)."""
        try:
            if event.button() == Qt.MouseButton.LeftButton:
                self.clicked.emit(self.mod_path)
        except Exception:
            pass
        super().mousePressEvent(event)

    def set_expanded(self, expanded: bool):
        """Programmatically set expanded state"""
        self.is_expanded = expanded
        self._update_expand_button()

    def set_update_available(self, version: str | None):
        """Update the update available badge dynamically."""
        if self.is_nested or not hasattr(self, "update_label"):
            return

        self.update_available_version = version
        if version:
            self.update_label.setText(
                tr("nexus_update_available_status", version=str(version))
            )
            self.update_label.show()
        else:
            self.update_label.hide()

    def contextMenuEvent(self, event):
        """Show context menu on right-click"""
        from PySide6.QtGui import QAction
        from PySide6.QtWidgets import QMenu

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #2a2a2a;
                color: #ffffff;
                border: 1px solid #3d3d3d;
            }
            QMenu::item {
                padding: 6px 24px;
            }
            QMenu::item:selected {
                background-color: #0078d4;
            }
        """)

        rename_action = QAction(tr("rename_mod_context_menu", default="Rename"), self)
        rename_action.triggered.connect(
            lambda: self.rename_requested.emit(self.mod_path)
        )
        menu.addAction(rename_action)

        menu.exec_(event.globalPos())
