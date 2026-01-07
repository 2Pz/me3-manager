"""
Nexus Mods SSO (Single Sign-On) authentication service.

Implements WebSocket-based SSO flow:
1. Connect to wss://sso.nexusmods.com
2. Send handshake with UUID and protocol version
3. Receive connection token
4. User authorizes in browser at nexusmods.com/sso
5. Receive API key via WebSocket
"""

from __future__ import annotations

import json
import logging
import threading
import uuid
import webbrowser
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal

if TYPE_CHECKING:
    from websocket import WebSocketApp

log = logging.getLogger(__name__)

NEXUS_SSO_URL = "wss://sso.nexusmods.com"
NEXUS_SSO_PAGE = "https://www.nexusmods.com/sso"
APPLICATION_SLUG = "2pz-me3manager"


class NexusSSOClient(QObject):
    """
    WebSocket client for Nexus Mods SSO authentication.

    Signals:
        connected: Emitted when WebSocket connection established
        connection_token_received: Emitted with connection token for reconnection
        api_key_received: Emitted with the API key when user authorizes
        error: Emitted with error message on failure
        closed: Emitted when connection is closed
    """

    connected = Signal()
    connection_token_received = Signal(str)
    api_key_received = Signal(str)
    error = Signal(str)
    closed = Signal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._ws: WebSocketApp | None = None
        self._ws_thread: threading.Thread | None = None
        self._request_id: str = ""
        self._connection_token: str | None = None
        self._running = False

    @property
    def request_id(self) -> str:
        """Get the current request ID (UUID)."""
        return self._request_id

    def start_auth(self, connection_token: str | None = None) -> str:
        """
        Start the SSO authentication flow.

        Args:
            connection_token: Optional token from previous connection for reconnection

        Returns:
            The request UUID used for this auth session
        """
        # Generate new UUID for this auth request
        self._request_id = str(uuid.uuid4())
        self._connection_token = connection_token
        self._running = True

        # Import websocket here to avoid import errors if not installed
        try:
            import websocket
        except ImportError as e:
            self.error.emit(f"WebSocket library not installed: {e}")
            return self._request_id

        # Create WebSocket connection
        self._ws = websocket.WebSocketApp(
            NEXUS_SSO_URL,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
        )

        # Run WebSocket in background thread
        self._ws_thread = threading.Thread(
            target=self._run_websocket, daemon=True, name="NexusSSO-WebSocket"
        )
        self._ws_thread.start()

        return self._request_id

    def _run_websocket(self):
        """Run WebSocket connection (called in background thread)."""
        if self._ws:
            try:
                self._ws.run_forever()
            except Exception as e:
                log.exception("WebSocket run error")
                self.error.emit(str(e))

    def _on_open(self, ws):
        """Handle WebSocket connection opened."""
        log.info("SSO WebSocket connected")

        # Send handshake request
        handshake = {
            "id": self._request_id,
            "token": self._connection_token,
            "protocol": 2,
        }
        try:
            ws.send(json.dumps(handshake))
            log.debug("Sent SSO handshake: id=%s", self._request_id)
            self.connected.emit()
        except Exception as e:
            log.exception("Failed to send handshake")
            self.error.emit(f"Failed to send handshake: {e}")

    def _on_message(self, ws, message: str):
        """Handle incoming WebSocket message."""
        log.debug("SSO message received: %s", message[:200])

        try:
            data = json.loads(message)
        except json.JSONDecodeError as e:
            log.warning("Invalid JSON from SSO: %s", e)
            return

        if not isinstance(data, dict):
            return

        success = data.get("success", False)
        error_msg = data.get("error")
        payload = data.get("data", {}) or {}

        if not success and error_msg:
            self.error.emit(str(error_msg))
            return

        # Check for connection token (initial response)
        if "connection_token" in payload:
            token = payload["connection_token"]
            self._connection_token = token
            log.info("Received connection token")
            self.connection_token_received.emit(token)
            return

        # Check for API key (user authorized)
        if "api_key" in payload:
            api_key = payload["api_key"]
            log.info("Received API key via SSO")
            self.api_key_received.emit(api_key)
            # Close connection after receiving key
            self.close()
            return

    def _on_error(self, ws, error):
        """Handle WebSocket error."""
        log.error("SSO WebSocket error: %s", error)
        self.error.emit(str(error))

    def _on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket connection closed."""
        log.info("SSO WebSocket closed: %s %s", close_status_code, close_msg)
        self._running = False
        self.closed.emit()

    def open_browser(self):
        """Open browser to Nexus authorization page."""
        if not self._request_id:
            log.warning("Cannot open browser: no request ID")
            return False

        url = f"{NEXUS_SSO_PAGE}?id={self._request_id}&application={APPLICATION_SLUG}"
        log.info("Opening SSO authorization page: %s", url)
        try:
            webbrowser.open(url)
            return True
        except Exception as e:
            log.exception("Failed to open browser")
            self.error.emit(f"Failed to open browser: {e}")
            return False

    def close(self):
        """Close the WebSocket connection."""
        self._running = False
        if self._ws:
            try:
                self._ws.close()
            except Exception:
                pass
            self._ws = None

    def is_running(self) -> bool:
        """Check if SSO client is currently running."""
        return self._running
