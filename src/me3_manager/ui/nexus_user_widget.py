"""
Nexus User Widget for main window.

Displays login button when not logged in, or user profile when logged in.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import QByteArray, Qt, Signal, Slot
from PySide6.QtGui import QBrush, QColor, QCursor, QPainter, QPainterPath, QPixmap
from PySide6.QtNetwork import QNetworkAccessManager
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QWidget,
)

from me3_manager.utils.translator import tr

if TYPE_CHECKING:
    from me3_manager.core.config_facade import ConfigFacade

log = logging.getLogger(__name__)


class NexusUserWidget(QWidget):
    """
    Widget showing Nexus login state in main window.

    - Not logged in: Shows "Login" button
    - Logged in: Shows circular user avatar with username tooltip
    """

    login_completed = Signal()  # Emitted after successful login
    logout_completed = Signal()  # Emitted after logout

    def __init__(self, config_manager: ConfigFacade, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self._network_manager = QNetworkAccessManager(self)
        self._avatar_pixmap: QPixmap | None = None

        self._init_ui()
        self.refresh_state()

    def _init_ui(self):
        """Initialize the widget UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Login button (shown when not logged in)
        self.login_btn = QPushButton(tr("nexus_login_button", default="Nexus Login"))
        self.login_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.login_btn.setStyleSheet("""
            QPushButton {
                background-color: #da8e35;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                color: #ffffff;
                font-weight: bold;

            }
            QPushButton:hover {
                background-color: #e09840;
            }
            QPushButton:pressed {
                background-color: #c07830;
            }
        """)
        self.login_btn.clicked.connect(self._start_sso_login)
        layout.addWidget(self.login_btn)

        # Logged in container (avatar + username)
        self.logged_in_container = QWidget()
        logged_in_layout = QHBoxLayout(self.logged_in_container)
        logged_in_layout.setContentsMargins(0, 0, 0, 0)
        logged_in_layout.setSpacing(8)

        # Avatar button
        self.avatar_btn = QPushButton()
        self.avatar_btn.setFixedSize(32, 32)
        self.avatar_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.avatar_btn.setStyleSheet("""
            QPushButton {
                background-color: #da8e35;
                border: none;
                border-radius: 16px;
            }
            QPushButton:hover {
                background-color: #e09840;
            }
        """)
        self.avatar_btn.clicked.connect(self._show_user_menu)
        logged_in_layout.addWidget(self.avatar_btn)

        # Username label
        self.username_label = QLabel()
        self.username_label.setStyleSheet("""
            QLabel {
                color: #ffffff;

                font-weight: bold;
            }
        """)
        logged_in_layout.addWidget(self.username_label)

        self.logged_in_container.hide()
        layout.addWidget(self.logged_in_container)

    def refresh_state(self):
        """Refresh the widget based on current login state."""
        api_key = self.config_manager.get_nexus_api_key()
        user_info = self.config_manager.get_nexus_user_info()

        if api_key and user_info:
            # User is logged in
            name = user_info.get("name") or "User"
            profile_url = user_info.get("profile_url")
            self._show_logged_in(name, profile_url)
        else:
            # User is not logged in
            self._show_logged_out()

    def _show_logged_out(self):
        """Show login button."""
        self.login_btn.show()
        self.logged_in_container.hide()

    def _show_logged_in(self, name: str, profile_url: str | None):
        """Show user avatar with username."""
        self.login_btn.hide()
        self.logged_in_container.show()

        # Ensure name is never empty
        display_name = name if name else "User"

        # Set username
        self.username_label.setText(display_name)

        # Set tooltip with logout hint
        tooltip_text = f"Logged in as {display_name} - Click to logout"
        self.avatar_btn.setToolTip(tooltip_text)

        # Load avatar if URL available and valid
        if profile_url and profile_url.startswith("http"):
            log.debug("Loading avatar from: %s", profile_url)
            self._load_avatar(profile_url)
        else:
            # Use default avatar (first letter of name)
            self._set_default_avatar(display_name)

    def _set_default_avatar(self, name: str):
        """Set a default avatar with the first letter of the name."""
        # Create a pixmap with the first letter
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw circular background
        path = QPainterPath()
        path.addEllipse(0, 0, 32, 32)
        painter.fillPath(path, QBrush(QColor("#da8e35")))

        # Draw letter
        painter.setPen(QColor("#ffffff"))
        font = painter.font()
        font.setPointSize(14)
        font.setBold(True)
        painter.setFont(font)

        letter = name[0].upper() if name else "U"
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, letter)
        painter.end()

        self.avatar_btn.setIcon(pixmap)
        self.avatar_btn.setIconSize(pixmap.size())

    def _load_avatar(self, url: str):
        """Load avatar image from URL using requests library."""
        import threading

        def download_avatar():
            try:
                import requests

                log.debug("Downloading avatar from: %s", url)
                resp = requests.get(
                    url,
                    headers={"User-Agent": "ME3Manager/1.0"},
                    timeout=10,
                )
                if resp.status_code == 200:
                    log.debug("Avatar downloaded: %d bytes", len(resp.content))
                    # Load pixmap on main thread
                    from PySide6.QtCore import QMetaObject, Qt

                    # Store data and trigger UI update
                    self._pending_avatar_data = resp.content
                    QMetaObject.invokeMethod(
                        self,
                        "_apply_avatar_data",
                        Qt.ConnectionType.QueuedConnection,
                    )
                else:
                    log.debug("Avatar download failed: HTTP %s", resp.status_code)
            except Exception as e:
                log.debug("Failed to download avatar: %s", e)

        # Download in background thread
        thread = threading.Thread(target=download_avatar, daemon=True)
        thread.start()

    @Slot()
    def _apply_avatar_data(self):
        """Apply downloaded avatar data to the button (called on main thread)."""
        try:
            if hasattr(self, "_pending_avatar_data") and self._pending_avatar_data:
                data = self._pending_avatar_data
                self._pending_avatar_data = None

                pixmap = QPixmap()
                if pixmap.loadFromData(QByteArray(data)):
                    # Create circular avatar
                    circular = self._make_circular(pixmap, 32)
                    self.avatar_btn.setIcon(circular)
                    self.avatar_btn.setIconSize(circular.size())
                    self._avatar_pixmap = circular
                    log.debug("Avatar applied successfully")
                else:
                    log.debug("Failed to load pixmap from downloaded data")
        except Exception as e:
            log.debug("Failed to apply avatar: %s", e)

    def _make_circular(self, source: QPixmap, size: int) -> QPixmap:
        """Create a circular version of the pixmap."""
        scaled = source.scaled(
            size,
            size,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )

        result = QPixmap(size, size)
        result.fill(Qt.GlobalColor.transparent)

        painter = QPainter(result)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        path = QPainterPath()
        path.addEllipse(0, 0, size, size)
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, scaled)
        painter.end()

        return result

    def _start_sso_login(self):
        """Start SSO login flow."""
        from me3_manager.ui.dialogs.sso_auth_dialog import SSOAuthDialog

        dialog = SSOAuthDialog(self)
        api_key = dialog.start_auth()

        if api_key:
            # Save the API key
            self.config_manager.set_nexus_api_key(api_key)

            # Validate and get user info
            try:
                from me3_manager.services.nexus_service import NexusService

                svc = NexusService(api_key)
                user = svc.validate_user()

                # Cache user info for display
                self.config_manager.set_nexus_user_info(user.name, user.profile_url)

                # Update UI
                self.refresh_state()
                self.login_completed.emit()

                log.info("Nexus SSO login successful: %s", user.name)
            except Exception as e:
                log.error("Failed to validate Nexus user: %s", e)
                # Still refresh state - might show login button again
                self.refresh_state()

    def _show_user_menu(self):
        """Show context menu with logout option."""
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #2d2d2d;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 4px;
            }
            QMenu::item {
                padding: 8px 24px;
                color: #ffffff;
            }
            QMenu::item:selected {
                background-color: #3d3d3d;
            }
        """)

        logout_action = menu.addAction(tr("nexus_logout_button", default="Logout"))
        logout_action.triggered.connect(self._on_logout)

        # Show menu below the button
        menu.exec(self.avatar_btn.mapToGlobal(self.avatar_btn.rect().bottomLeft()))

    def _on_logout(self):
        """Handle logout."""
        log.info("Logging out from Nexus")

        # Clear credentials and user info
        self.config_manager.clear_nexus_api_key()
        self.config_manager.clear_nexus_user_info()

        # Update UI
        self.refresh_state()
        self.logout_completed.emit()
