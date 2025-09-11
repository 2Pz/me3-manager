"""
File system watcher for ME3 Manager.
Monitors directories and files for changes.
"""

from pathlib import Path

from PyQt6.QtCore import QFileSystemWatcher, QObject, pyqtSignal


class FileWatcher(QObject):
    """Manages file system watching for mod directories and profile files."""

    # Signals
    directory_changed = pyqtSignal(str)  # Emitted when a watched directory changes
    file_changed = pyqtSignal(str)  # Emitted when a watched file changes

    def __init__(self, parent=None):
        """
        Initialize the file watcher.

        Args:
            parent: Optional parent QObject
        """
        super().__init__(parent)
        self.watcher = QFileSystemWatcher()
        self._watched_dirs: set[str] = set()
        self._watched_files: set[str] = set()

        # Connect signals
        self.watcher.directoryChanged.connect(self._on_directory_changed)
        self.watcher.fileChanged.connect(self._on_file_changed)

    def setup_for_game(self, game_name: str, path_manager, settings_manager) -> None:
        """
        Setup file watching for a specific game.

        Args:
            game_name: Name of the game
            path_manager: PathManager instance
            settings_manager: SettingsManager instance
        """
        target_dirs = set()
        target_files = set()

        # Get profiles for this game
        profiles = settings_manager.get("profiles", {})
        game_profiles = profiles.get(game_name, [])

        # Add default mods directory
        default_mods_dir = path_manager.get_mods_dir(game_name)
        if default_mods_dir.is_dir():
            target_dirs.add(str(default_mods_dir))

        # Add custom profile directories and files
        for profile in game_profiles:
            if profile.get("id") != "default":
                # Add custom mods directory
                mods_path_str = profile.get("mods_path")
                if mods_path_str and Path(mods_path_str).is_dir():
                    target_dirs.add(mods_path_str)

                # Add profile file
                profile_path_str = profile.get("profile_path")
                if profile_path_str and Path(profile_path_str).is_file():
                    target_files.add(profile_path_str)

        # Update watched paths
        self._update_watched_paths(target_dirs, target_files)

    def setup_global(self, path_manager, settings_manager, game_registry) -> None:
        """
        Setup file watching for all games.

        Args:
            path_manager: PathManager instance
            settings_manager: SettingsManager instance
            game_registry: GameRegistry instance
        """
        target_dirs = set()
        target_files = set()

        profiles = settings_manager.get("profiles", {})
        games = game_registry.get_all_games()

        for game_name in games.keys():
            # Skip if game has no profiles
            if game_name not in profiles:
                continue

            # Add default mods directory
            default_mods_dir = path_manager.get_mods_dir(game_name)
            if default_mods_dir.is_dir():
                target_dirs.add(str(default_mods_dir))

            # Add custom profile directories and files
            for profile in profiles.get(game_name, []):
                if profile.get("id") != "default":
                    # Add custom mods directory
                    mods_path_str = profile.get("mods_path")
                    if mods_path_str and Path(mods_path_str).is_dir():
                        target_dirs.add(mods_path_str)

                    # Add profile file
                    profile_path_str = profile.get("profile_path")
                    if profile_path_str and Path(profile_path_str).is_file():
                        target_files.add(profile_path_str)

        # Update watched paths
        self._update_watched_paths(target_dirs, target_files)

    def add_directory(self, directory: str) -> bool:
        """
        Add a directory to watch.

        Args:
            directory: Path to directory

        Returns:
            True if successfully added
        """
        if directory not in self._watched_dirs and Path(directory).is_dir():
            if self.watcher.addPath(directory):
                self._watched_dirs.add(directory)
                return True
        return False

    def add_file(self, file_path: str) -> bool:
        """
        Add a file to watch.

        Args:
            file_path: Path to file

        Returns:
            True if successfully added
        """
        if file_path not in self._watched_files and Path(file_path).is_file():
            if self.watcher.addPath(file_path):
                self._watched_files.add(file_path)
                return True
        return False

    def remove_directory(self, directory: str) -> bool:
        """
        Remove a directory from watching.

        Args:
            directory: Path to directory

        Returns:
            True if successfully removed
        """
        if directory in self._watched_dirs:
            if self.watcher.removePath(directory):
                self._watched_dirs.discard(directory)
                return True
        return False

    def remove_file(self, file_path: str) -> bool:
        """
        Remove a file from watching.

        Args:
            file_path: Path to file

        Returns:
            True if successfully removed
        """
        if file_path in self._watched_files:
            if self.watcher.removePath(file_path):
                self._watched_files.discard(file_path)
                return True
        return False

    def clear_all(self) -> None:
        """Remove all watched paths."""
        # Remove all directories
        for directory in list(self._watched_dirs):
            self.remove_directory(directory)

        # Remove all files
        for file_path in list(self._watched_files):
            self.remove_file(file_path)

    def get_watched_directories(self) -> list[str]:
        """
        Get list of currently watched directories.

        Returns:
            List of directory paths
        """
        return list(self._watched_dirs)

    def get_watched_files(self) -> list[str]:
        """
        Get list of currently watched files.

        Returns:
            List of file paths
        """
        return list(self._watched_files)

    def _update_watched_paths(
        self, target_dirs: set[str], target_files: set[str]
    ) -> None:
        """
        Update watched paths to match target sets.

        Args:
            target_dirs: Set of directories to watch
            target_files: Set of files to watch
        """
        # Update directories
        current_dirs = self._watched_dirs.copy()

        # Remove directories no longer needed
        for directory in current_dirs - target_dirs:
            self.remove_directory(directory)

        # Add new directories
        for directory in target_dirs - current_dirs:
            self.add_directory(directory)

        # Update files
        current_files = self._watched_files.copy()

        # Remove files no longer needed
        for file_path in current_files - target_files:
            self.remove_file(file_path)

        # Add new files
        for file_path in target_files - current_files:
            self.add_file(file_path)

    def _on_directory_changed(self, path: str) -> None:
        """
        Handle directory change signal.

        Args:
            path: Path that changed
        """
        # Re-add the path if it still exists (Qt removes it after change)
        if Path(path).is_dir() and path in self._watched_dirs:
            self.watcher.addPath(path)

        # Emit our signal
        self.directory_changed.emit(path)

    def _on_file_changed(self, path: str) -> None:
        """
        Handle file change signal.

        Args:
            path: Path that changed
        """
        # Re-add the path if it still exists (Qt removes it after change)
        if Path(path).is_file() and path in self._watched_files:
            self.watcher.addPath(path)

        # Emit our signal
        self.file_changed.emit(path)

    def is_watching_directory(self, directory: str) -> bool:
        """
        Check if a directory is being watched.

        Args:
            directory: Path to directory

        Returns:
            True if directory is being watched
        """
        return directory in self._watched_dirs

    def is_watching_file(self, file_path: str) -> bool:
        """
        Check if a file is being watched.

        Args:
            file_path: Path to file

        Returns:
            True if file is being watched
        """
        return file_path in self._watched_files
