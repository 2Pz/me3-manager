from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QCheckBox,
)
from PyQt6.QtGui import QFont
import sys


class SettingsDialog(QDialog):
    """Settings dialog for user preferences"""

    def __init__(self, main_window):
        super().__init__(main_window)
        self.main_window = main_window
        self.config_manager = main_window.config_manager
        self.init_ui()

    def init_ui(self):
        """Initialize the settings dialog UI"""
        self.setWindowTitle("Settings")
        self.setMinimumWidth(450)
        self.setMinimumHeight(350)
        self.apply_styles()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        # Title
        title = QLabel("Settings")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        layout.addWidget(title)

        # Steam Integration Section
        self.create_steam_section(layout)

        # Update Settings Section
        self.create_update_section(layout)

        # Future sections can be added here
        # self.create_ui_section(layout)
        # self.create_advanced_section(layout)

        layout.addStretch()

        # Bottom buttons
        self.create_button_section(layout)

    def create_steam_section(self, parent_layout):
        """Create Steam integration settings section"""
        # Section header
        steam_header = QLabel("Steam Integration")
        steam_header.setObjectName("SectionHeader")
        parent_layout.addWidget(steam_header)

        # Auto-launch Steam checkbox
        if sys.platform == "win32":
            self.auto_launch_steam_checkbox = QCheckBox(
                "Auto-launch Steam silently on app startup"
            )
        else:
            self.auto_launch_steam_checkbox = QCheckBox(
                "Auto-launch Steam silently on app startup (via flatpak-spawn)"
            )
        self.auto_launch_steam_checkbox.setChecked(
            self.config_manager.get_auto_launch_steam()
        )
        self.auto_launch_steam_checkbox.toggled.connect(
            self.on_auto_launch_steam_toggled
        )
        parent_layout.addWidget(self.auto_launch_steam_checkbox)

        # Steam status info
        steam_path = self.config_manager.get_steam_path()
        if steam_path and steam_path.exists():
            steam_status = QLabel(f"Steam found at: {steam_path}")
            steam_status.setObjectName("StatusSuccess")
        else:
            steam_status = QLabel("Steam not found or ME3 not installed")
            steam_status.setObjectName("StatusError")
            self.auto_launch_steam_checkbox.setEnabled(False)
            self.auto_launch_steam_checkbox.setToolTip(
                "Steam path not available - requires ME3 to be installed"
            )

        parent_layout.addWidget(steam_status)

    def create_button_section(self, parent_layout):
        """Create bottom button section"""
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        button_layout.addWidget(close_button)

        parent_layout.addLayout(button_layout)

    def create_update_section(self, parent_layout):
        """Create update checking settings section"""
        # Section header
        update_header = QLabel("Mod Engine 3 Updates")
        update_header.setObjectName("SectionHeader")
        parent_layout.addWidget(update_header)

        # Check for updates checkbox
        self.check_updates_checkbox = QCheckBox("Check for ME3 updates on app startup")
        self.check_updates_checkbox.setChecked(
            self.config_manager.get_check_for_updates()
        )
        self.check_updates_checkbox.toggled.connect(self.on_check_updates_toggled)
        parent_layout.addWidget(self.check_updates_checkbox)

    def apply_styles(self):
        """Apply consistent styling to the dialog"""
        self.setStyleSheet("""
            QDialog {
                background-color: #252525;
                color: #ffffff;
            }
            QLabel {
                background-color: transparent;
                color: #ffffff;
            }
            QPushButton {
                background-color: #2d2d2d;
                border: 1px solid #3d3d3d;
                padding: 8px 16px;
                border-radius: 4px;
                color: #ffffff;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #3d3d3d;
            }
            QPushButton:pressed {
                background-color: #1d1d1d;
            }
            QCheckBox {
                background-color: transparent;
                color: #ffffff;
                spacing: 8px;
                padding: 4px 0px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 2px solid #3d3d3d;
                border-radius: 3px;
                background-color: #2d2d2d;
            }
            QCheckBox::indicator:checked {
                background-color: #0078d4;
                border-color: #0078d4;
            }
            QCheckBox::indicator:hover {
                border-color: #4d4d4d;
            }
            QCheckBox::indicator:checked:hover {
                background-color: #106ebe;
                border-color: #106ebe;
            }
            #SectionHeader {
                font-size: 14px;
                font-weight: bold;
                margin-top: 10px;
                margin-bottom: 8px;
                color: #ffffff;
            }
            #StatusSuccess {
                color: #90EE90;
                font-size: 11px;
                margin-left: 24px;
                margin-top: 4px;
            }
            #StatusError {
                color: #FFB6C1;
                font-size: 11px;
                margin-left: 24px;
                margin-top: 4px;
            }
        """)

    # Event Handlers
    def on_auto_launch_steam_toggled(self, checked):
        """Handle auto-launch Steam setting change"""
        self.config_manager.set_auto_launch_steam(checked)

    def on_check_updates_toggled(self, checked):
        """Handle check for updates setting change"""
        self.config_manager.set_check_for_updates(checked)
