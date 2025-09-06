import logging
import os
import sys

from PyQt6.QtWidgets import QApplication

from me3_manager.ui.main_window import ModEngine3Manager
from me3_manager.utils.translator import translator

log = logging.getLogger(__name__)


def setup_logging():
    """One-time setup of logging for all modules."""

    FORMAT = "%(levelname)s:%(name)s:%(lineno)d %(message)s"
    log_level = logging.INFO

    # TODO: What happens in cxfreeze builds?
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        # This message won't be shown to users unless they set LOG_LEVEL to DEBUG
        location = "PyInstaller bundle"
    else:
        # Default to DEBUG for devs running from source
        log_level = logging.DEBUG
        location = "normal Python process"

    # Prefer LOG_LEVEL env var if set
    env_log_level = os.environ.get("LOG_LEVEL")
    if env_log_level is not None:
        log_level = env_log_level.upper()

    # Configure root logger
    try:
        logging.basicConfig(format=FORMAT, level=log_level)
    except ValueError:
        logging.basicConfig(format=FORMAT, level=logging.INFO)
        # Only log after basicConfig!
        log.warning("Invalid LOG_LEVEL %s, defaulting to INFO", env_log_level)

    log.debug("Running in %s", location)


def main():
    setup_logging()

    if sys.platform == "linux":
        if "QT_QPA_PLATFORM" in os.environ:
            del os.environ["QT_QPA_PLATFORM"]

        os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = ""

    app = QApplication(sys.argv)

    # Check what platform Qt actually chose at runtime
    if sys.platform == "linux":
        platform_name = app.platformName()
        log.debug("Qt selected platform: %s", platform_name)

        # If drag-drop issues persist, we can detect and handle them
        if platform_name == "wayland":
            log.debug("Wayland detected - drag-drop compatibility may vary")
            # Could show a user notification about potential drag-drop issues

    # Set language based on system locale
    translator.set_system_language()

    # Set application properties
    app.setApplicationName("Mod Engine 3 Manager")
    app.setOrganizationName("ME3 Tools")

    # Apply dark theme
    app.setStyle("Fusion")

    # Create and show main window
    window = ModEngine3Manager()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
