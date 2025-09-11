"""
Game registry for managing game configurations.
Handles game definitions, order, and game-specific settings.
"""

from typing import Dict, List, Optional


class GameRegistry:
    """Manages game configurations and registry."""

    # Default game configurations
    DEFAULT_GAMES = {
        "Elden Ring": {
            "mods_dir": "eldenring-mods",
            "profile": "eldenring-default.me3",
            "cli_id": "elden-ring",
            "executable": "eldenring.exe",
        },
        "Nightreign": {
            "mods_dir": "nightreign-mods",
            "profile": "nightreign-default.me3",
            "cli_id": "nightreign",
            "executable": "nightreign.exe",
        },
        "Sekiro": {
            "mods_dir": "sekiro-mods",
            "profile": "sekiro-default.me3",
            "cli_id": "sekiro",
            "executable": "sekiro.exe",
        },
        "Dark Souls 3": {
            "mods_dir": "darksouls3-mods",
            "profile": "darksouls3-default.me3",
            "cli_id": "ds3",
            "executable": "darksouls3.exe",
        },
        "Armoredcore6": {
            "mods_dir": "armoredcore6-mods",
            "profile": "armoredcore6-default.me3",
            "cli_id": "armoredcore6",
            "executable": "armoredcore6.exe",
        },
    }

    DEFAULT_GAME_ORDER = [
        "Elden Ring",
        "Nightreign",
        "Sekiro",
        "Dark Souls 3",
        "Armoredcore6",
    ]

    def __init__(self, settings_manager):
        """
        Initialize game registry.

        Args:
            settings_manager: Reference to the main SettingsManager
        """
        self.settings_manager = settings_manager
        self._initialize_games()
        self._initialize_game_order()
        self._initialize_game_paths()

    def _initialize_games(self):
        """Initialize games configuration, using defaults only if no games are saved."""
        # If the 'games' key exists, the user has a saved configuration.
        # We must trust it and not merge with defaults, as this would
        # re-introduce games the user has intentionally deleted.
        if self.settings_manager.get("games") is not None:
            return

        # If no 'games' configuration exists (e.g., first run), populate with defaults.
        self.settings_manager.set("games", self.DEFAULT_GAMES.copy(), auto_save=False)

    def _initialize_game_order(self):
        """Initialize game order, using defaults only if no order is saved."""
        # Similar to games, if a game_order exists, we respect it.
        # Pruning the order to match existing games is still a good idea.
        if self.settings_manager.get("game_order") is not None:
            saved_order = self.settings_manager.get("game_order", [])
            available_games = list(self.get_all_games().keys())

            # Create a new order that preserves the saved order but removes non-existent games.
            pruned_order = [game for game in saved_order if game in available_games]

            # Add any new games that are not in the saved order to the end.
            for game in available_games:
                if game not in pruned_order:
                    pruned_order.append(game)

            self.settings_manager.set("game_order", pruned_order, auto_save=False)
            return

        # If no 'game_order' exists, populate it with the default order.
        self.settings_manager.set(
            "game_order", self.DEFAULT_GAME_ORDER.copy(), auto_save=False
        )

    def _initialize_game_paths(self):
        """Ensure game executable paths dictionary exists."""
        if not self.settings_manager.has_key("game_exe_paths"):
            self.settings_manager.set("game_exe_paths", {}, auto_save=False)

    def get_all_games(self) -> Dict[str, Dict[str, str]]:
        """
        Get all registered games.

        Returns:
            Dictionary of game configurations
        """
        return self.settings_manager.get("games", {}).copy()

    def get_game(self, game_name: str) -> Optional[Dict[str, str]]:
        """
        Get configuration for a specific game.

        Args:
            game_name: Name of the game

        Returns:
            Game configuration dictionary or None
        """
        games = self.settings_manager.get("games", {})
        return games.get(game_name, {}).copy() if game_name in games else None

    def add_game(
        self, name: str, mods_dir: str, profile: str, cli_id: str, executable: str
    ) -> bool:
        """
        Add a new game configuration.

        Args:
            name: Game name
            mods_dir: Mods directory name
            profile: Profile filename
            cli_id: CLI identifier
            executable: Executable filename

        Returns:
            True if successful
        """
        games = self.settings_manager.get("games", {})

        # Check if game already exists
        if name in games:
            return False

        # Add new game
        games[name] = {
            "mods_dir": mods_dir,
            "profile": profile,
            "cli_id": cli_id,
            "executable": executable,
        }

        self.settings_manager.set("games", games)

        # Add to game order
        game_order = self.settings_manager.get("game_order", [])
        if name not in game_order:
            game_order.append(name)
            self.settings_manager.set("game_order", game_order)

        return True

    def remove_game(self, name: str) -> bool:
        """
        Remove a game configuration.

        Args:
            name: Game name to remove

        Returns:
            True if successful
        """
        games = self.settings_manager.get("games", {})

        if name not in games:
            return False

        # Remove from games
        del games[name]
        self.settings_manager.set("games", games)

        # Remove from game order
        game_order = self.settings_manager.get("game_order", [])
        if name in game_order:
            game_order.remove(name)
            self.settings_manager.set("game_order", game_order)

        # Clean up related settings
        self._clean_game_data(name)

        return True

    def update_game(self, name: str, **kwargs) -> bool:
        """
        Update game configuration.

        Args:
            name: Game name
            **kwargs: Configuration values to update

        Returns:
            True if successful
        """
        games = self.settings_manager.get("games", {})

        if name not in games:
            return False

        # Update only valid keys
        valid_keys = ["mods_dir", "profile", "cli_id", "executable"]
        for key, value in kwargs.items():
            if key in valid_keys:
                games[name][key] = value

        self.settings_manager.set("games", games)
        return True

    def get_game_order(self) -> List[str]:
        """
        Get the current game order.

        Returns:
            List of game names in order
        """
        return self.settings_manager.get("game_order", []).copy()

    def set_game_order(self, new_order: List[str]) -> bool:
        """
        Set a new game order.

        Args:
            new_order: List of game names in desired order

        Returns:
            True if successful
        """
        available_games = set(self.get_all_games().keys())

        # Validate that all games in new order exist
        if set(new_order) != available_games:
            return False

        self.settings_manager.set("game_order", new_order)
        return True

    def get_game_exe_path(self, game_name: str) -> Optional[str]:
        """
        Get custom executable path for a game.

        Args:
            game_name: Name of the game

        Returns:
            Custom executable path or None
        """
        exe_paths = self.settings_manager.get("game_exe_paths", {})
        return exe_paths.get(game_name)

    def set_game_exe_path(self, game_name: str, path: Optional[str]) -> None:
        """
        Set or clear custom executable path for a game.

        Args:
            game_name: Name of the game
            path: Executable path or None to clear
        """
        exe_paths = self.settings_manager.get("game_exe_paths", {})

        if path:
            exe_paths[game_name] = path
        else:
            exe_paths.pop(game_name, None)

        self.settings_manager.set("game_exe_paths", exe_paths)

    def get_game_cli_id(self, game_name: str) -> Optional[str]:
        """
        Get CLI identifier for a game.

        Args:
            game_name: Name of the game

        Returns:
            CLI identifier or None
        """
        game = self.get_game(game_name)
        return game.get("cli_id") if game else None

    def get_game_executable_name(self, game_name: str) -> Optional[str]:
        """
        Get expected executable filename for a game.

        Args:
            game_name: Name of the game

        Returns:
            Executable filename or None
        """
        game = self.get_game(game_name)
        return game.get("executable") if game else None

    def get_game_mods_dir(self, game_name: str) -> Optional[str]:
        """
        Get mods directory name for a game.

        Args:
            game_name: Name of the game

        Returns:
            Mods directory name or None
        """
        game = self.get_game(game_name)
        return game.get("mods_dir") if game else None

    def get_game_profile_name(self, game_name: str) -> Optional[str]:
        """
        Get profile filename for a game.

        Args:
            game_name: Name of the game

        Returns:
            Profile filename or None
        """
        game = self.get_game(game_name)
        return game.get("profile") if game else None

    def _clean_game_data(self, game_name: str):
        """
        Clean up all data associated with a game.

        Args:
            game_name: Name of the game to clean
        """
        # Remove from various settings
        settings_to_clean = [
            "profiles",
            "active_profiles",
            "tracked_external_mods",
            "game_exe_paths",
            "custom_config_paths",
            "me3_config_paths",
        ]

        for setting_key in settings_to_clean:
            setting_data = self.settings_manager.get(setting_key, {})
            if isinstance(setting_data, dict) and game_name in setting_data:
                del setting_data[game_name]
                self.settings_manager.set(setting_key, setting_data, auto_save=False)

        # Save all changes at once
        self.settings_manager.save_settings()

    def restore_default_game(self, game_name: str) -> bool:
        """
        Restore a game to its default configuration.

        Args:
            game_name: Name of the game

        Returns:
            True if successful
        """
        if game_name not in self.DEFAULT_GAMES:
            return False

        games = self.settings_manager.get("games", {})
        games[game_name] = self.DEFAULT_GAMES[game_name].copy()
        self.settings_manager.set("games", games)

        return True

    def is_default_game(self, game_name: str) -> bool:
        """
        Check if a game is one of the default games.

        Args:
            game_name: Name of the game

        Returns:
            True if it's a default game
        """
        return game_name in self.DEFAULT_GAMES
