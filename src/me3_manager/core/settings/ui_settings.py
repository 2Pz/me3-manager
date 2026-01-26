"""
UI settings management for ME3 Manager.
Handles all user interface related configuration.
"""

from typing import Any


class UISettings:
    """Manages UI-specific settings."""

    def __init__(self, settings_manager):
        """
        Initialize UI settings manager.

        Args:
            settings_manager: Reference to the main SettingsManager
        """
        self.settings_manager = settings_manager
        self._ensure_defaults()

    def _ensure_defaults(self):
        """Ensure default UI settings exist."""
        ui_settings = self.settings_manager.get("ui_settings", {})

        defaults = {
            "mods_per_page": 50,
            "check_for_updates": True,
            "check_mod_updates_on_startup": True,
            "auto_launch_steam": False,
            "theme": "default",
            "window_geometry": None,
            "splitter_state": None,
            "default_profile_version": "v1",
            "ui_scale": 1.0,
        }

        # Add missing defaults
        updated = False
        for key, default_value in defaults.items():
            if key not in ui_settings:
                ui_settings[key] = default_value
                updated = True

        if updated:
            self.settings_manager.set("ui_settings", ui_settings)

    def get_ui_scale(self) -> float:
        """
        Get the UI scale factor.

        Returns:
            UI scale factor (1.0 = 100%)
        """
        ui_settings = self.settings_manager.get("ui_settings", {})
        return ui_settings.get("ui_scale", 1.0)

    def set_ui_scale(self, value: float) -> None:
        """
        Set the UI scale factor.

        Args:
            value: UI scale factor
        """
        # Clamp between decent values
        if value < 0.5:
            value = 0.5
        elif value > 3.0:
            value = 3.0

        ui_settings = self.settings_manager.get("ui_settings", {})
        ui_settings["ui_scale"] = value
        self.settings_manager.set("ui_settings", ui_settings)

    def get_mods_per_page(self) -> int:
        """
        Get the number of mods to display per page.

        Returns:
            Number of mods per page
        """
        ui_settings = self.settings_manager.get("ui_settings", {})
        return ui_settings.get("mods_per_page", 50)

    def set_mods_per_page(self, value: int) -> None:
        """
        Set the number of mods to display per page.

        Args:
            value: Number of mods per page
        """
        if value < 1:
            value = 1
        elif value > 200:
            value = 200

        ui_settings = self.settings_manager.get("ui_settings", {})
        ui_settings["mods_per_page"] = value
        self.settings_manager.set("ui_settings", ui_settings)

    def get_check_for_updates(self) -> bool:
        """
        Get whether to check for updates on startup.

        Returns:
            True if updates should be checked
        """
        ui_settings = self.settings_manager.get("ui_settings", {})
        return ui_settings.get("check_for_updates", True)

    def set_check_for_updates(self, enabled: bool) -> None:
        """
        Set whether to check for updates on startup.

        Args:
            enabled: Whether to check for updates
        """
        ui_settings = self.settings_manager.get("ui_settings", {})
        ui_settings["check_for_updates"] = enabled
        self.settings_manager.set("ui_settings", ui_settings)

    def get_check_mod_updates_on_startup(self) -> bool:
        """
        Get whether to check for Nexus mod updates on startup.

        Returns:
            True if mod updates should be checked
        """
        ui_settings = self.settings_manager.get("ui_settings", {})
        return ui_settings.get("check_mod_updates_on_startup", True)

    def set_check_mod_updates_on_startup(self, enabled: bool) -> None:
        """
        Set whether to check for Nexus mod updates on startup.

        Args:
            enabled: Whether to check for mod updates
        """
        ui_settings = self.settings_manager.get("ui_settings", {})
        ui_settings["check_mod_updates_on_startup"] = enabled
        self.settings_manager.set("ui_settings", ui_settings)

    def get_auto_launch_steam(self) -> bool:
        """
        Get whether to auto-launch Steam.

        Returns:
            True if Steam should be auto-launched
        """
        ui_settings = self.settings_manager.get("ui_settings", {})
        return ui_settings.get("auto_launch_steam", False)

    def set_auto_launch_steam(self, enabled: bool) -> None:
        """
        Set whether to auto-launch Steam.

        Args:
            enabled: Whether to auto-launch Steam
        """
        ui_settings = self.settings_manager.get("ui_settings", {})
        ui_settings["auto_launch_steam"] = enabled
        self.settings_manager.set("ui_settings", ui_settings)

    def get_window_geometry(self) -> dict[str, int] | None:
        """
        Get saved window geometry.

        Returns:
            Dictionary with window position and size, or None
        """
        ui_settings = self.settings_manager.get("ui_settings", {})
        return ui_settings.get("window_geometry")

    def set_window_geometry(self, geometry: dict[str, int]) -> None:
        """
        Save window geometry.

        Args:
            geometry: Dictionary with x, y, width, height
        """
        ui_settings = self.settings_manager.get("ui_settings", {})
        ui_settings["window_geometry"] = geometry
        self.settings_manager.set("ui_settings", ui_settings)

    def get_splitter_state(self) -> bytes | None:
        """
        Get saved splitter state.

        Returns:
            Splitter state bytes or None
        """
        ui_settings = self.settings_manager.get("ui_settings", {})
        state = ui_settings.get("splitter_state")
        if state and isinstance(state, str):
            # Convert from base64 if stored as string
            import base64

            return base64.b64decode(state)
        return state

    def set_splitter_state(self, state: bytes) -> None:
        """
        Save splitter state.

        Args:
            state: Splitter state bytes
        """
        if state:
            # Convert to base64 for JSON storage
            import base64

            state_str = base64.b64encode(state).decode("utf-8")
            ui_settings = self.settings_manager.get("ui_settings", {})
            ui_settings["splitter_state"] = state_str
            self.settings_manager.set("ui_settings", ui_settings)

    def get_theme(self) -> str:
        """
        Get the current UI theme.

        Returns:
            Theme name
        """
        ui_settings = self.settings_manager.get("ui_settings", {})
        return ui_settings.get("theme", "default")

    def set_theme(self, theme: str) -> None:
        """
        Set the UI theme.

        Args:
            theme: Theme name
        """
        ui_settings = self.settings_manager.get("ui_settings", {})
        ui_settings["theme"] = theme
        self.settings_manager.set("ui_settings", ui_settings)

    def get_all_ui_settings(self) -> dict[str, Any]:
        """
        Get all UI settings.

        Returns:
            Dictionary of all UI settings
        """
        return self.settings_manager.get("ui_settings", {}).copy()

    # Profile version default
    def get_default_profile_version(self) -> str:
        ui_settings = self.settings_manager.get("ui_settings", {})
        val = str(ui_settings.get("default_profile_version", "v1")).lower()
        return "v2" if val == "v2" else "v1"

    def set_default_profile_version(self, version: str) -> None:
        normalized = str(version).lower()
        if normalized not in ("v1", "v2"):
            normalized = "v1"
        ui_settings = self.settings_manager.get("ui_settings", {})
        ui_settings["default_profile_version"] = normalized
        self.settings_manager.set("ui_settings", ui_settings)

    def reset_to_defaults(self) -> None:
        """Reset all UI settings to defaults."""
        defaults = {
            "mods_per_page": 50,
            "check_for_updates": True,
            "auto_launch_steam": False,
            "theme": "default",
            "window_geometry": None,
            "splitter_state": None,
        }
        self.settings_manager.set("ui_settings", defaults)
