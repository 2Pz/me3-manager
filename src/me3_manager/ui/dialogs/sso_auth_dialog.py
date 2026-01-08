"""
SSO Authentication Dialog for Nexus Mods.

Shows a modal dialog during the SSO authentication flow,
handling browser launch and waiting for API key response.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from me3_manager.services.nexus_sso import NexusSSOClient
from me3_manager.utils.translator import tr

log = logging.getLogger(__name__)


class SSOAuthDialog(QDialog):
    """
    Modal dialog for Nexus Mods SSO authentication.

    Shows progress while waiting for user to authorize in browser,
    then returns the API key on success.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sso_client: NexusSSOClient | None = None
        self._api_key: str | None = None
        self._init_ui()

    def _init_ui(self):
        """Initialize the dialog UI."""
        self.setWindowTitle(tr("nexus_sso_title", default="Nexus Mods Login"))
        self.setMinimumWidth(400)
        self.setMinimumHeight(200)
        self.setModal(True)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Status label
        self.status_label = QLabel(
            tr("nexus_sso_waiting", default="Waiting for authorization...")
        )
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("font-size: 14px; color: #ffffff;")
        layout.addWidget(self.status_label)

        # Progress bar (indeterminate)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #2d2d2d;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                height: 8px;
            }
            QProgressBar::chunk {
                background-color: #0078d4;
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.progress_bar)

        # Info label
        self.info_label = QLabel(
            tr(
                "nexus_sso_browser_info",
                default="A browser window will open. Please log in and authorize the app.",
            )
        )
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet("font-size: 12px; color: #888888;")
        layout.addWidget(self.info_label)

        layout.addStretch()

        # Button row
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.cancel_btn = QPushButton(tr("nexus_sso_cancel", default="Cancel"))
        self.cancel_btn.clicked.connect(self._on_cancel)
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #2d2d2d;
                border: 1px solid #3d3d3d;
                padding: 8px 20px;
                border-radius: 4px;
                color: #ffffff;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #3d3d3d;
            }
        """)
        btn_layout.addWidget(self.cancel_btn)

        layout.addLayout(btn_layout)

        # Apply dark theme
        self.setStyleSheet("""
            QDialog {
                background-color: #252525;
            }
        """)

    def start_auth(self) -> str | None:
        """
        Start SSO authentication and show dialog.

        Returns:
            API key on success, None on cancel/error
        """
        self._api_key = None

        # Create SSO client
        self._sso_client = NexusSSOClient(self)
        self._sso_client.connected.connect(self._on_connected)
        self._sso_client.connection_token_received.connect(self._on_token_received)
        self._sso_client.api_key_received.connect(self._on_api_key_received)
        self._sso_client.error.connect(self._on_error)
        self._sso_client.closed.connect(self._on_closed)

        # Start authentication
        self._sso_client.start_auth()

        # Show dialog (blocks until closed)
        result = self.exec()

        # Cleanup
        if self._sso_client:
            self._sso_client.close()
            self._sso_client = None

        if result == QDialog.DialogCode.Accepted and self._api_key:
            return self._api_key
        return None

    def _on_connected(self):
        """Handle WebSocket connected."""
        log.debug("SSO connected, waiting for token...")
        self.status_label.setText(
            tr("nexus_sso_connecting", default="Connecting to Nexus...")
        )

    def _on_token_received(self, token: str):
        """Handle connection token received - open browser."""
        log.debug("Token received, opening browser")
        self.status_label.setText(
            tr("nexus_sso_open_browser", default="Opening browser for login...")
        )

        # Open browser after short delay
        QTimer.singleShot(500, self._open_browser)

    def _open_browser(self):
        """Open the authorization page in browser."""
        if self._sso_client:
            if self._sso_client.open_browser():
                self.status_label.setText(
                    tr("nexus_sso_waiting", default="Waiting for authorization...")
                )
            else:
                self._on_error("Failed to open browser")

    def _on_api_key_received(self, api_key: str):
        """Handle API key received - success!"""
        log.info("SSO authentication successful")
        self._api_key = api_key
        self.status_label.setText(
            tr("nexus_sso_success_msg", default="Login successful!")
        )
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(1)

        # Close dialog after brief delay
        QTimer.singleShot(800, lambda: self.accept())

    def _on_error(self, error_msg: str):
        """Handle error."""
        log.error("SSO error: %s", error_msg)
        self.status_label.setText(
            tr("nexus_sso_error", default="Authentication failed: {error}").format(
                error=error_msg
            )
        )
        self.status_label.setStyleSheet("font-size: 14px; color: #ff6b6b;")
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)

    def _on_closed(self):
        """Handle WebSocket closed."""
        log.debug("SSO connection closed")

    def _on_cancel(self):
        """Handle cancel button clicked."""
        log.info("SSO authentication cancelled by user")
        if self._sso_client:
            self._sso_client.close()
        self.reject()

    def closeEvent(self, event):
        """Handle dialog close."""
        if self._sso_client:
            self._sso_client.close()
        super().closeEvent(event)
