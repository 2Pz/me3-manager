import logging
import os
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

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


def setup_ssl_certificates():
    """Setup SSL certificates for PyInstaller builds.

    PyInstaller bundles its own Python environment which may not find
    system SSL certificates. Use certifi's bundled certificates instead.
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        try:
            import certifi

            os.environ.setdefault("SSL_CERT_FILE", certifi.where())
            os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())
        except ImportError:
            pass  # certifi not available, rely on system certificates


def main():
    setup_ssl_certificates()
    setup_logging()

    # Check for CLI arguments first
    from me3_manager.core.cli import handle_cli_args

    if handle_cli_args():
        sys.exit(0)

    # Check for forbidden executable names (e.g. "me3.exe")
    # This prevents infinite recursion if the manager is renamed to "me3.exe"
    # and tries to call the "me3" CLI tool.
    exe_name = os.path.basename(sys.executable).lower()
    if exe_name == "me3.exe":
        sys.exit(1)

    # Apply UI Scaling from settings
    # We must set this before creating the QApplication to ensure it takes effect.
    ui_scale = 1.0
    try:
        from me3_manager.core.paths.profile_paths import get_me3_profiles_root
        from me3_manager.core.settings.settings_manager import SettingsManager

        config_root = get_me3_profiles_root()
        settings_file = config_root.parent / "manager_settings.json"

        # Use SettingsManager to load configuration safely
        if settings_file.exists():
            settings = SettingsManager(settings_file)
            ui_scale = settings.get("ui_settings", {}).get("ui_scale", 1.0)

            if ui_scale != 1.0:
                os.environ["QT_SCALE_FACTOR"] = str(ui_scale)
                log.info("Applied UI Scale Factor from settings: %s", ui_scale)
    except Exception as e:
        log.warning("Failed to apply UI scale from settings: %s", e)

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

    base_font_size = 9
    if ui_scale < 1.0:
        new_size = int(base_font_size / ui_scale)
        app.setFont(QFont("Segoe UI", new_size))
        log.info("Applied compensated font size: %dpt for scale %s", new_size, ui_scale)
    else:
        app.setFont(QFont("Segoe UI", base_font_size))

    app.setStyle("Fusion")

    # Force dark mode
    app.styleHints().setColorScheme(Qt.ColorScheme.Dark)

    # Create and show main window
    window = ModEngine3Manager()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
