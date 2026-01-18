import sys

from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from me3_manager.utils.translator import tr


class SettingsDialog(QDialog):
    """Settings dialog with tabbed layout for user preferences"""

    def __init__(self, main_window):
        super().__init__(main_window)
        self.main_window = main_window
        self.config_manager = main_window.config_manager
        self.init_ui()

    def init_ui(self):
        """Initialize the settings dialog UI with tabs"""
        self.setWindowTitle(tr("settings_title"))
        self.setMinimumWidth(520)
        self.setMinimumHeight(420)
        self.apply_styles()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Title
        title = QLabel(tr("settings_title"))
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        layout.addWidget(title)

        # Tab Widget
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet(self._get_tab_style())

        # Create tabs
        self.tab_widget.addTab(self._create_general_tab(), tr("settings_tab_general"))
        self.tab_widget.addTab(self._create_updates_tab(), tr("settings_tab_updates"))

        layout.addWidget(self.tab_widget)

        # Bottom buttons
        self.create_button_section(layout)

    def _create_general_tab(self):
        """Create the General settings tab with Steam integration"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(16, 20, 16, 16)
        layout.setSpacing(16)

        # UI Scale Section
        ui_scale_header = QLabel(tr("ui_scale_header"))
        ui_scale_header.setObjectName("SectionHeader")
        layout.addWidget(ui_scale_header)

        scale_layout = QHBoxLayout()
        scale_layout.setSpacing(10)

        self.ui_scale_spin = QDoubleSpinBox()
        self.ui_scale_spin.setRange(0.5, 3.0)
        self.ui_scale_spin.setSingleStep(0.1)
        self.ui_scale_spin.setValue(self.config_manager.get_ui_scale())
        self.ui_scale_spin.valueChanged.connect(self.on_ui_scale_changed)
        self.ui_scale_spin.setFixedWidth(100)
        scale_layout.addWidget(self.ui_scale_spin)

        scale_note = QLabel(tr("ui_scale_restart_note"))
        scale_note.setObjectName("StatusInfo")
        scale_layout.addWidget(scale_note)
        scale_layout.addStretch()

        layout.addLayout(scale_layout)

        # Steam Integration Section
        steam_header = QLabel(tr("steam_integration_header"))
        steam_header.setObjectName("SectionHeader")
        layout.addWidget(steam_header)

        # Auto-launch Steam checkbox
        if sys.platform == "win32":
            checkbox_text = tr("auto_launch_steam_win_checkbox")
        else:
            checkbox_text = tr("auto_launch_steam_linux_checkbox")

        self.auto_launch_steam_checkbox = QCheckBox(checkbox_text)
        self.auto_launch_steam_checkbox.setChecked(
            self.config_manager.get_auto_launch_steam()
        )
        self.auto_launch_steam_checkbox.toggled.connect(
            self.on_auto_launch_steam_toggled
        )
        layout.addWidget(self.auto_launch_steam_checkbox)

        # Steam status info
        steam_path = self.config_manager.get_steam_path()
        if steam_path and steam_path.exists():
            steam_status = QLabel(tr("steam_found_status", steam_path=steam_path))
            steam_status.setObjectName("StatusSuccess")
        else:
            steam_status = QLabel(tr("steam_not_found_status"))
            steam_status.setObjectName("StatusError")
            self.auto_launch_steam_checkbox.setEnabled(False)
            self.auto_launch_steam_checkbox.setToolTip(
                tr("steam_path_unavailable_tooltip")
            )

        steam_status.setWordWrap(True)
        layout.addWidget(steam_status)

        layout.addStretch()
        return tab

    def _create_updates_tab(self):
        """Create the Updates settings tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(16, 20, 16, 16)
        layout.setSpacing(16)

        # Updates Header
        update_header = QLabel(tr("me3_updates_header"))
        update_header.setObjectName("SectionHeader")
        layout.addWidget(update_header)

        # Check for updates checkbox
        self.check_updates_checkbox = QCheckBox(tr("check_for_updates_checkbox"))
        self.check_updates_checkbox.setChecked(
            self.config_manager.get_check_for_updates()
        )
        self.check_updates_checkbox.toggled.connect(self.on_check_updates_toggled)
        layout.addWidget(self.check_updates_checkbox)

        # Check for mod updates checkbox (Nexus)
        self.check_mod_updates_checkbox = QCheckBox(
            tr("check_for_mod_updates_checkbox")
        )
        self.check_mod_updates_checkbox.setChecked(
            self.config_manager.get_check_mod_updates_on_startup()
        )
        self.check_mod_updates_checkbox.toggled.connect(
            self.on_check_mod_updates_toggled
        )
        layout.addWidget(self.check_mod_updates_checkbox)

        layout.addStretch()
        return tab

    def create_button_section(self, parent_layout):
        """Create bottom button section"""
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        close_button = QPushButton(tr("close_button"))
        close_button.clicked.connect(self.accept)
        button_layout.addWidget(close_button)

        parent_layout.addLayout(button_layout)

    def _get_tab_style(self):
        """Return modern tab widget styling"""
        return """
            QTabWidget::pane {
                border: 1px solid #3d3d3d;
                border-radius: 8px;
                background-color: #1f1f1f;
                top: -1px;
            }
            QTabBar::tab {
                background-color: #2d2d2d;
                color: #888888;
                padding: 10px 24px;
                margin-right: 4px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                font-weight: 500;
            }
            QTabBar::tab:selected {
                background-color: #1f1f1f;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                border-bottom: none;
            }
            QTabBar::tab:hover:!selected {
                background-color: #3d3d3d;
                color: #cccccc;
            }
        """

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
                padding: 10px 20px;
                border-radius: 6px;
                color: #ffffff;
                min-width: 80px;
                font-weight: 500;
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
                spacing: 10px;
                padding: 6px 0px;
                font-size: 13px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 2px solid #3d3d3d;
                border-radius: 4px;
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
            QLineEdit {
                background-color: #2d2d2d;
                border: 1px solid #3d3d3d;
                border-radius: 6px;
                padding: 8px 12px;
                color: #ffffff;
                font-size: 13px;
            }
            QDoubleSpinBox {
                background-color: #2d2d2d;
                border: 1px solid #3d3d3d;
                border-radius: 6px;
                padding: 4px 8px;
                color: #ffffff;
                font-size: 13px;
            }
            QLineEdit:focus, QDoubleSpinBox:focus {
                border-color: #0078d4;
            }
            #SectionHeader {
                font-size: 15px;
                font-weight: bold;
                color: #ffffff;
            }
            #StatusSuccess {
                color: #90EE90;
                font-size: 12px;
                margin-top: 6px;
            }
            #StatusError {
                color: #FFB6C1;
                font-size: 12px;
                margin-top: 6px;
            }
            #StatusInfo {
                color: #cccccc;
                font-size: 12px;
                margin-top: 6px;
            }
        """)

    # Event Handlers
    def on_ui_scale_changed(self, value):
        """Handle UI scale setting change"""
        self.config_manager.set_ui_scale(value)

    def on_auto_launch_steam_toggled(self, checked):
        """Handle auto-launch Steam setting change"""
        self.config_manager.set_auto_launch_steam(checked)

    def on_check_updates_toggled(self, checked):
        """Handle check for updates setting change"""
        self.config_manager.set_check_for_updates(checked)

    def on_check_mod_updates_toggled(self, checked):
        """Handle check for Nexus mod updates setting change"""
        self.config_manager.set_check_mod_updates_on_startup(checked)
