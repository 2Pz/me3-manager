"""
UI Construction Handler for GamePage.

This class is responsible for creating, styling, and laying out all the Qt widgets
that constitute the GamePage UI. It centralizes the UI setup logic, keeping the
main GamePage class clean.
"""

from typing import TYPE_CHECKING

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from me3_manager.utils.resource_path import resource_path
from me3_manager.utils.translator import tr

if TYPE_CHECKING:
    from ..game_page import GamePage


class UiBuilder:
    """Handles the creation and layout of widgets for the GamePage."""

    def __init__(self, game_page: "GamePage"):
        self.game_page = game_page
        self.style = game_page.style  # Share the style object

    def init_ui(self):
        """Initialize the main UI components."""
        self.game_page.main_layout = QVBoxLayout()
        self._setup_layout_properties()

        # Build UI sections in logical order
        self._create_header_section()
        self._create_custom_savefile_warning_banner()
        self._create_search_section()
        self._create_filter_section()
        self._create_drop_zone()
        self._create_pagination_section()
        self._create_mods_section()
        self._create_status_section()

        self.game_page.setLayout(self.game_page.main_layout)

    def _setup_layout_properties(self):
        """Configure main layout properties."""
        self.game_page.main_layout.setSpacing(12)
        self.game_page.main_layout.setContentsMargins(24, 24, 24, 24)

    def _create_header_section(self):
        """Create the header with title and action buttons."""
        header_layout = QHBoxLayout()

        title = self._create_title_label()
        header_layout.addWidget(title)
        header_layout.addStretch()

        profile_widget = self._create_profile_selector()
        header_layout.addLayout(profile_widget)

        action_buttons = self._create_action_buttons()
        for button in action_buttons:
            header_layout.addWidget(button)

        self.game_page.main_layout.addLayout(header_layout)

    def _create_title_label(self):
        """Create and style the main title label."""
        title = QLabel(tr("game_mods_title", game_name=self.game_page.game_name))
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setStyleSheet("color: #ffffff; margin-bottom: 8px;")
        return title

    def _create_profile_selector(self):
        """Create an enhanced profile selector with modern styling."""
        profile_container = QWidget()
        profile_container.setFixedHeight(44)
        profile_container.setMinimumWidth(220)

        container_layout = QHBoxLayout(profile_container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        profile_label = QLabel(tr("profile_label"))
        profile_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        profile_label.setFixedWidth(90)
        profile_label.setStyleSheet(self.style.profile_label_style)

        # IMPORTANT: Store the button on the game_page instance
        self.game_page.profile_menu_button = QPushButton(tr("select_profile_button"))
        self.game_page.profile_menu_button.setFixedHeight(44)
        self.game_page.profile_menu_button.setMinimumWidth(130)
        self.game_page.profile_menu_button.setStyleSheet(
            self.style.profile_button_style
        )

        self.game_page.profile_menu = QMenu(self.game_page)
        self.game_page.profile_menu.setStyleSheet(self.style.profile_menu_style)
        self.game_page.profile_menu_button.setMenu(self.game_page.profile_menu)

        container_layout.addWidget(profile_label)
        container_layout.addWidget(self.game_page.profile_menu_button)

        wrapper_layout = QHBoxLayout()
        wrapper_layout.addWidget(profile_container)

        return wrapper_layout

    def _create_action_buttons(self):
        """Create all header action buttons."""
        buttons = []

        # Launch button
        self.game_page.launch_btn = QPushButton(
            tr("launch_game_button", game_name=self.game_page.game_name)
        )
        self.game_page.launch_btn.setFixedHeight(40)
        self.game_page.launch_btn.setStyleSheet(self.style.launch_button_style)
        # Connect the signal to a method on the game_page object
        self.game_page.launch_btn.clicked.connect(self.game_page.launch_game)
        buttons.append(self.game_page.launch_btn)

        icon_buttons_config = [
            {
                "attr": "game_options_btn",
                "icon": "game_options.svg",
                "tooltip": tr("configure_game_options_tooltip"),
                "callback": self.game_page.open_game_options,
            },
            {
                "attr": "profile_settings_btn",
                "icon": "profiles.svg",
                "tooltip": tr("profile_settings_tooltip"),
                "callback": self.game_page.open_profile_settings,
            },
            {
                "attr": "open_mods_folder_btn",
                "icon": "folder.svg",
                "tooltip": tr("open_mods_folder_tooltip"),
                "callback": self.game_page.open_mods_folder,
            },
            {
                "attr": "add_external_mod_btn",
                "icon": "dll.svg",
                "tooltip": tr("add_external_mod_tooltip"),
                "callback": self.game_page.add_external_mod,
            },
            {
                "attr": "edit_profile_btn",
                "icon": "note.svg",
                "tooltip": tr("edit_profile_tooltip"),
                "callback": self.game_page.open_profile_editor,
            },
            {
                "attr": "export_setup_btn",
                "icon": "zip.svg",
                "tooltip": tr("export_setup_tooltip"),
                "callback": self.game_page.export_mods_setup,
            },
        ]

        for config in icon_buttons_config:
            button = self._create_icon_button(config)
            # Store the button on the game_page instance
            setattr(self.game_page, config["attr"], button)
            buttons.append(button)

        return buttons

    def _create_custom_savefile_warning_banner(self):
        """Create a prominent banner warning when custom savefile is not set."""
        banner = QWidget()
        layout = QHBoxLayout(banner)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(12)

        icon_label = QLabel("⚠")
        icon_label.setStyleSheet("color: #ffcc00; font-size: 18px;")
        layout.addWidget(icon_label)

        text_label = QLabel(tr("gamepage_savefile_warning"))
        text_label.setWordWrap(True)
        text_label.setStyleSheet("color: #ffffff; font-size: 13px;")
        layout.addWidget(text_label, 1)

        action_btn = QPushButton(tr("gamepage_configure_savefile_button"))
        action_btn.setFixedHeight(32)
        action_btn.clicked.connect(self.game_page.open_profile_settings)
        layout.addWidget(action_btn)

        banner.setStyleSheet(
            """
            QWidget { background-color: #3a2a00; border: 1px solid #7a5a00; border-radius: 8px; }
            QPushButton { background: #0078d4; color: white; border: none; border-radius: 6px; padding: 6px 12px; }
            QPushButton:hover { background: #106ebe; }
            """
        )

        # Store on game_page and hide by default; GamePage controls visibility
        self.game_page.custom_savefile_banner = banner
        banner.setVisible(False)
        self.game_page.main_layout.addWidget(banner)

    def _create_icon_button(self, config):
        """Create a standardized icon button."""
        button = QPushButton(
            QIcon(resource_path(f"resources/icon/{config['icon']}")), ""
        )
        button.setIconSize(QSize(40, 40))
        button.setFixedSize(60, 60)
        button.setToolTip(config["tooltip"])
        button.setStyleSheet(self.style.icon_button_style)
        # The callback is a method from game_page, passed in the config dict
        button.clicked.connect(config["callback"])
        return button

    def _create_search_section(self):
        """Create the search bar."""
        self.game_page.search_bar = QLineEdit()
        self.game_page.search_bar.setPlaceholderText(tr("search_mods_placeholder"))
        self.game_page.search_bar.setStyleSheet(self.style.search_bar_style)
        self.game_page.search_bar.textChanged.connect(self.game_page.apply_filters)
        self.game_page.main_layout.addWidget(self.game_page.search_bar)

    def _create_filter_section(self):
        """Create the filter buttons section."""
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(8)
        buttons_layout.setContentsMargins(0, 4, 0, 0)

        filter_definitions = self.game_page._get_filter_definitions()

        for filter_name, (text, tooltip) in filter_definitions.items():
            button = self._create_filter_button(filter_name, text, tooltip)
            # Store buttons on the game_page instance
            self.game_page.filter_buttons[filter_name] = button
            buttons_layout.addWidget(button)

        buttons_layout.addStretch()
        self.game_page.main_layout.addLayout(buttons_layout)
        self.game_page.update_filter_button_styles()

    def _create_filter_button(self, filter_name, text, tooltip):
        """Create a single filter button."""
        button = QPushButton(text)
        button.setFixedHeight(32)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setToolTip(tooltip)
        # Connect to the game_page's set_filter method
        button.clicked.connect(
            lambda checked, name=filter_name: self.game_page.set_filter(name)
        )
        return button

    def _create_drop_zone(self):
        """Create the drag and drop zone."""
        self.game_page.drop_zone = QLabel(tr("drag_drop_zone_text"))
        self.game_page.drop_zone.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.game_page.drop_zone.setStyleSheet(self.style.drop_zone_style)
        self.game_page.drop_zone.setFixedHeight(80)
        self.game_page.main_layout.addWidget(self.game_page.drop_zone)

    def _create_pagination_section(self):
        """Create the pagination controls."""
        pagination_layout = QHBoxLayout()

        items_per_page_layout = self._create_items_per_page_controls()
        pagination_layout.addLayout(items_per_page_layout)
        pagination_layout.addStretch()

        nav_buttons = self._create_pagination_buttons()
        for widget in nav_buttons:
            pagination_layout.addWidget(widget)

        self.game_page.main_layout.addLayout(pagination_layout)

    def _create_items_per_page_controls(self):
        """Create the items per page selector."""
        layout = QHBoxLayout()
        label = QLabel(tr("items_per_page_label"))
        layout.addWidget(label)

        self.game_page.items_per_page_spinbox = QSpinBox()
        self.game_page.items_per_page_spinbox.setRange(1, 50)
        self.game_page.items_per_page_spinbox.setValue(self.game_page.mods_per_page)
        self.game_page.items_per_page_spinbox.setStyleSheet(self.style.spinbox_style)
        self.game_page.items_per_page_spinbox.valueChanged.connect(
            self.game_page.change_items_per_page
        )
        layout.addWidget(self.game_page.items_per_page_spinbox)

        layout.addStretch()
        return layout

    def _create_pagination_buttons(self):
        """Create pagination navigation buttons."""
        widgets = []

        self.game_page.prev_btn = QPushButton(tr("previous_page_button"))
        self.game_page.prev_btn.setStyleSheet(self.style.pagination_button_style)
        self.game_page.prev_btn.clicked.connect(self.game_page.prev_page)
        widgets.append(self.game_page.prev_btn)

        self.game_page.page_label = QLabel(
            tr("page_label_text", current_page=1, total_pages=1)
        )
        self.game_page.page_label.setStyleSheet("color: #ffffff; padding: 0px 12px;")
        widgets.append(self.game_page.page_label)

        self.game_page.next_btn = QPushButton(tr("next_page_button"))
        self.game_page.next_btn.setStyleSheet(self.style.pagination_button_style)
        self.game_page.next_btn.clicked.connect(self.game_page.next_page)
        widgets.append(self.game_page.next_btn)

        return widgets

    def _create_mods_section(self):
        """Create the main mods display area."""
        self.game_page.mods_widget = QWidget()
        self.game_page.mods_layout = QVBoxLayout(self.game_page.mods_widget)
        self.game_page.mods_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.game_page.mods_layout.setSpacing(4)
        self.game_page.mods_widget.setStyleSheet(self.style.mods_widget_style)
        self.game_page.main_layout.addWidget(self.game_page.mods_widget)

    def _create_status_section(self):
        """Create the status bar."""
        self.game_page.status_label = QLabel(tr("status_ready"))
        self.game_page.status_label.setStyleSheet("color: #888888; font-size: 11px;")
        self.game_page.main_layout.addWidget(self.game_page.status_label)
