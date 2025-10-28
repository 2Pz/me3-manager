from PySide6.QtCore import QTimer

from me3_manager.utils.status import Status


class AppController:
    """
    Coordinates app-level behaviors decoupled from MainWindow UI:
    - Debounced global refresh via QTimer
    - File-watcher connections
    - Startup checks (me3 install, Steam autolaunch, update checks)
    """

    def __init__(self, main_window, config_manager):
        self.main_window = main_window
        self.config_manager = config_manager
        self.refresh_timer = QTimer(self.main_window)
        self.refresh_timer.setSingleShot(True)
        self.refresh_timer.timeout.connect(self.main_window.perform_global_refresh)

    def wire_file_watcher(self):
        # Connect BOTH directory and file change signals to the same refresh slot.
        self.config_manager.file_watcher.directoryChanged.connect(
            self.main_window.schedule_global_refresh
        )
        self.config_manager.file_watcher.fileChanged.connect(
            self.main_window.schedule_global_refresh
        )

    def schedule_global_refresh(self, delay_ms: int = 500):
        self.refresh_timer.start(delay_ms)

    def run_startup_checks(self):
        # Prompt installation if needed
        if (
            self.config_manager.me3_info_manager.get_me3_installation_status()
            == Status.NOT_INSTALLED
        ):
            self.main_window.prompt_for_me3_installation()
            return

        # Auto launch steam if enabled
        if self.config_manager.get_auto_launch_steam():
            self.main_window.auto_launch_steam_if_enabled()

        # Check for updates if enabled
        self.main_window.check_for_me3_updates_if_enabled()

        # Check for app updates (always runs)
        self.main_window.check_for_app_updates()
