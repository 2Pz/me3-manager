"""
Styling for the GamePage UI.

This module contains the GamePageStyle class, which centralizes all Qt Style Sheet (QSS)
definitions for the widgets in GamePage.
"""


class GamePageStyle:
    """Encapsulate QSS styles for GamePage UI components."""

    def __init__(self):
        self.profile_label_style = self._get_enhanced_profile_label_style()
        self.profile_button_style = self._get_enhanced_profile_button_style()
        self.profile_menu_style = self._get_enhanced_profile_menu_style()
        self.launch_button_style = self._get_launch_button_style()
        self.icon_button_style = self._get_icon_button_style()
        self.search_bar_style = self._get_search_bar_style()
        self.drop_zone_style = self._get_drop_zone_style()
        self.spinbox_style = self._get_spinbox_style()
        self.pagination_button_style = self._get_pagination_button_style()
        self.mods_widget_style = self._get_mods_widget_style()

    def _get_enhanced_profile_label_style(self):
        """Return modern, simple QSS style for profile label."""
        return """
            QLabel {
                background-color: #2c2c2c;
                color: #ffffff;
                font-size: 14px;
                font-weight: 500;
                padding: 12px 16px;
                border: none;
                border-top-left-radius: 8px;
                border-bottom-left-radius: 8px;
                min-height: 20px;
            }
        """

    def _get_enhanced_profile_button_style(self):
        """Return modern, simple QSS style for profile button."""
        return """
            QPushButton {
                background-color: #404040;
                border: none;
                color: #ffffff;
                border-top-right-radius: 8px;
                border-bottom-right-radius: 8px;
                font-size: 14px;
                font-weight: 500;
                padding: 12px 16px;
                text-align: center;
            }
            QPushButton:hover {
                background-color: #0078d4;
            }
            QPushButton:pressed {
                background-color: #106ebe;
            }
            QPushButton::menu-indicator {
                image: none;
                width: 0px;
                height: 0px;
            }
        """

    def _get_enhanced_profile_menu_style(self):
        """Return modern, simple QSS style for profile menu."""
        return """
            QMenu {
                background-color: #2c2c2c;
                border: 1px solid #404040;
                border-radius: 8px;
                padding: 4px;
            }
            QMenu::item {
                background-color: transparent;
                color: #ffffff;
                padding: 10px 16px;
                border-radius: 4px;
                margin: 1px;
                font-size: 14px;
            }
            QMenu::item:selected {
                background-color: #0078d4;
                color: #ffffff;
            }
            QMenu::item:pressed {
                background-color: #106ebe;
            }
            QMenu::separator {
                height: 1px;
                background-color: #404040;
                margin: 4px 8px;
            }
        """

    def _get_launch_button_style(self):
        """Return QSS style for launch button."""
        return """
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
        """

    def _get_icon_button_style(self):
        """Return QSS style for icon buttons."""
        return """
            QPushButton {
                background-color: #4d4d4d;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #5d5d5d;
            }
            QPushButton:pressed {
                background-color: #3d3d3d;
            }
        """

    def _get_search_bar_style(self):
        """Return QSS style for search bar."""
        return """
            QLineEdit {
                background-color: #2d2d2d;
                border: 2px solid #3d2d2d;
                border: 2px solid #3d3d3d;
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 12px;
                color: #ffffff;
            }
            QLineEdit:focus {
                border-color: #0078d4;
            }
        """

    def _get_drop_zone_style(self):
        """Return QSS style for drop zone."""
        return """
            QLabel {
                background-color: #1e1e1e;
                border: 2px dashed #3d3d3d;
                border-radius: 12px;
                padding: 20px;
                font-size: 14px;
                color: #888888;
                margin: 8px 0px;
            }
        """

    def _get_spinbox_style(self):
        """Return QSS style for spinbox."""
        return """
            QSpinBox {
                background-color: #2d2d2d;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 4px;
                color: #ffffff;
                min-width: 60px;
            }
        """

    def _get_pagination_button_style(self):
        """Return QSS style for pagination buttons."""
        return """
            QPushButton {
                background-color: #3d3d3d;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #4d4d4d;
            }
            QPushButton:disabled {
                background-color: #2d2d2d;
                color: #666666;
            }
        """

    def _get_mods_widget_style(self):
        """Return QSS style for mods widget."""
        return """
            QWidget {
                background-color: #1e1e1e;
                border: 1px solid #3d3d3d;
                border-radius: 8px;
                padding: 8px;
            }
        """
