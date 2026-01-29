"""
Mod Installation Handler for GamePage.

Simplified mod installation system that handles:
- DLL-only mods (native mods)
- Package mods (game asset folders)
- .me3 profile mods (structured installation)

All installations flow through a single entry point: install_mod()
"""

import logging
import re
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING, Literal

import tomlkit
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QVBoxLayout,
)

from me3_manager.core.config_applicator import ConfigApplicator
from me3_manager.core.profiles.profile_manager import ProfileManager
from me3_manager.utils.archive_utils import ARCHIVE_EXTENSIONS, extract_archive
from me3_manager.utils.constants import ACCEPTABLE_FOLDERS
from me3_manager.utils.translator import tr

if TYPE_CHECKING:
    from me3_manager.ui.game_page_components import GamePage


# Reserved names that cause issues on Windows
RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    "COM1",
    "COM2",
    "COM3",
    "COM4",
    "COM5",
    "COM6",
    "COM7",
    "COM8",
    "COM9",
    "LPT1",
    "LPT2",
    "LPT3",
    "LPT4",
    "LPT5",
    "LPT6",
    "LPT7",
    "LPT8",
    "LPT9",
}

# Regex for valid mod names
NAME_RE = re.compile(r'^[^<>:"/\\|?*]{1,60}$')

# Common junk files/folders to filter out
_JUNK_NAMES = frozenset({"__MACOSX", ".DS_Store"})

# Files that should be overwritten (Mod binaries/core files)
# Everything else is considered user data/config and should be preserved if it exists
_BINARY_EXTENSIONS = {".dll", ".exe", ".bin"}


def _contains_symlink(path: Path) -> bool:
    """Check if a path or any of its contents are symlinks."""
    if path.is_symlink():
        return True
    if path.is_dir():
        for p in path.rglob("*"):
            if p.is_symlink():
                return True
    return False


def _validate_mod_name(mod_name: str) -> bool:
    """Validate mod name against reserved names and illegal characters."""
    if not mod_name or not NAME_RE.fullmatch(mod_name):
        return False
    if Path(mod_name).stem.upper() in RESERVED_NAMES:
        return False
    if mod_name in (".", ".."):
        return False
    if mod_name[-1] in {".", " "}:
        return False
    return True


def _filter_children(folder: Path) -> list[Path]:
    """Filter out junk files/folders from a directory listing."""
    try:
        return [p for p in folder.iterdir() if p.name not in _JUNK_NAMES]
    except Exception:
        return []


def _copy_item(src: Path, dst: Path) -> bool:
    """Copy a file or directory to destination. Returns True on success."""
    try:
        if src.is_dir():
            shutil.copytree(src, dst, symlinks=False, ignore_dangling_symlinks=True)
        else:
            shutil.copy2(src, dst, follow_symlinks=False)
        return True
    except Exception:
        return False


class InstallWorker(QThread):
    """Background worker for file copy operations."""

    progress_update = Signal(str, int, int)  # status, current, total
    finished_signal = Signal(int, list)  # installed_count, errors

    def __init__(
        self, items_to_install: list[Path | tuple[Path, Path]], mods_dir: Path
    ):
        super().__init__()
        self.items = items_to_install
        self.mods_dir = mods_dir

    def run(self):
        self.installed_count = 0
        self.errors = []
        parent = self.mods_dir.resolve()

        for i, item_entry in enumerate(self.items):
            if self.isInterruptionRequested():
                break

            # Handle both legacy Path and new tuple inputs
            if isinstance(item_entry, tuple):
                source_path, dest_rel_path = item_entry
            else:
                source_path = item_entry
                dest_rel_path = Path(item_entry.name)

            self.progress_update.emit(
                tr("installing_status", name=dest_rel_path.name), i, len(self.items)
            )

            try:
                if _contains_symlink(source_path):
                    msg = tr("symlink_rejected_msg", name=dest_rel_path.name)
                    self.errors.append(msg)
                    continue

                dest_path = self.mods_dir / dest_rel_path
                try:
                    dest_path.resolve().relative_to(parent)
                except ValueError:
                    msg = tr("invalid_destination_path_msg", name=dest_rel_path.name)
                    self.errors.append(msg)
                    continue

                with TemporaryDirectory(dir=str(parent)) as tmp_root_str:
                    tmp_root = Path(tmp_root_str)

                    # Prepare backup of existing config files
                    backup_dir = tmp_root / "_config_backup"

                    if dest_path.exists() and dest_path.is_dir():
                        self._backup_configs(dest_path, backup_dir)

                    tmp_dst = tmp_root / dest_rel_path.name

                    if source_path.is_dir():
                        shutil.copytree(
                            source_path,
                            tmp_dst,
                            symlinks=False,
                            ignore_dangling_symlinks=True,
                        )
                    else:
                        shutil.copy2(source_path, tmp_dst, follow_symlinks=False)

                    # Ensure parent directory exists
                    dest_path.parent.mkdir(parents=True, exist_ok=True)

                    # Atomic replace
                    try:
                        tmp_dst.replace(dest_path)
                    except OSError:
                        if dest_path.is_dir():
                            shutil.rmtree(dest_path)
                        elif dest_path.exists():
                            dest_path.unlink()
                        tmp_dst.replace(dest_path)

                    # Restore configs if they were backed up
                    if backup_dir.exists():
                        self._restore_configs(backup_dir, dest_path)

                self.installed_count += 1
            except Exception as e:
                self.errors.append(
                    tr("copy_failed_msg", name=dest_rel_path.name, error=str(e))
                )

        self.finished_signal.emit(self.installed_count, self.errors)

    def _backup_configs(self, source: Path, backup_root: Path):
        """Recursively backup config files (everything except binaries)."""
        try:
            for path in source.rglob("*"):
                if path.is_file() and path.suffix.lower() not in _BINARY_EXTENSIONS:
                    try:
                        rel_path = path.relative_to(source)
                        backup_path = backup_root / rel_path
                        backup_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(path, backup_path)
                    except Exception:
                        pass
        except Exception:
            pass

    def _restore_configs(self, backup_root: Path, target: Path):
        """Restore backed up config files, overwriting fresh ones."""
        try:
            for path in backup_root.rglob("*"):
                if path.is_file():
                    try:
                        rel_path = path.relative_to(backup_root)
                        target_path = target / rel_path
                        # Ensure target dir exists (should, but safe check)
                        target_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(path, target_path)
                    except Exception:
                        pass
        except Exception:
            pass


class ModInstaller:
    """
    Simplified mod installer with a single entry point.

    Mod Types:
    - "me3": Has .me3 profile file (highest priority)
    - "native": Contains DLLs, no game asset folders
    - "package": Contains game asset folders or regulation.bin
    """

    def __init__(self, game_page: "GamePage"):
        self.game_page = game_page
        self.config_manager = game_page.config_manager
        self._log = logging.getLogger(__name__)
        # Track the last selected mod root path for metadata storage
        self._last_selected_mod_root_path: str | None = None

    # =========================================================================
    # PUBLIC API - Single Entry Point
    # =========================================================================

    def get_last_selected_mod_root_path(self) -> str | None:
        """Get the relative path selected by user during last installation.

        This is set when the user chooses a subfolder from the folder selection
        dialog during mod installation. Can be saved to metadata for updates.
        """
        return self._last_selected_mod_root_path

    def install_mod(
        self,
        source: Path,
        *,
        nexus_mod_id: int | None = None,
        mod_name_hint: str | None = None,
        mod_root_path: str | None = None,
        delete_archive: bool = False,
        load_mods: bool = True,
    ) -> list[str]:
        """
        Universal mod installation entry point.

        Args:
            source: Path to folder or archive to install
            nexus_mod_id: Optional Nexus mod ID (unused, for future tracking)
            mod_name_hint: Suggested name for the mod (e.g., from Nexus)
            mod_root_path: User-specified relative path to mod root within archive
            delete_archive: Whether to delete the source archive after installation

        Returns:
            List of installed mod folder/file names
        """
        # Reset the last selected path before each install
        self._last_selected_mod_root_path = None

        try:
            # Handle archives
            if source.is_file() and source.suffix.lower() in ARCHIVE_EXTENSIONS:
                return self._install_from_archive(
                    source, mod_name_hint, mod_root_path, delete_archive, load_mods
                )

            if not source.is_dir():
                self._show_error(tr("mod_source_not_found"))
                return []

            # Check for symlinks
            if _contains_symlink(source):
                self._show_error(tr("symlink_rejected_package_msg"))
                return []

            # Use user-specified path if provided, otherwise auto-detect
            if mod_root_path:
                user_root = source / mod_root_path
                if user_root.exists() and user_root.is_dir():
                    mod_root = user_root
                else:
                    # Fall back to auto-detect if specified path doesn't exist
                    mod_root = self._find_mod_root(source)
            else:
                # Find real mod root (auto-unwrap single child folders)
                mod_root = self._find_mod_root(source)

            # Scan for ambiguous mod structures
            candidates = self._scan_candidates(mod_root)
            mod_type = "unknown"

            # Prioritize me3 profiles always (no prompt)
            me3_candidates = [c for c in candidates if c[1] == "me3"]

            if me3_candidates:
                mod_root, mod_type = me3_candidates[0]
            elif len(candidates) > 1 and not mod_root_path:
                # Prompt user
                items = []
                for path, mtype in candidates:
                    name = (
                        tr("mod_option_entire_folder")
                        if path == mod_root
                        else path.name
                    )
                    type_label = {
                        "package": tr("mod_type_package"),
                        "native": tr("mod_type_native"),
                        "me3": "Profile",
                    }.get(mtype, mtype)
                    items.append(f"{name} ({type_label})")

                selected_item, ok = QInputDialog.getItem(
                    self.game_page,
                    tr("select_mod_root_title"),
                    tr("select_mod_root_desc"),
                    items,
                    0,
                    False,
                )

                if ok and selected_item:
                    idx = items.index(selected_item)
                    mod_root, mod_type = candidates[idx]
                    # Calculate relative path from source to selected mod_root
                    # This path can be saved for future updates
                    try:
                        rel_path = mod_root.relative_to(source)
                        if str(rel_path) != ".":
                            self._last_selected_mod_root_path = str(rel_path)
                    except ValueError:
                        # mod_root is not relative to source, shouldn't happen
                        pass
                else:
                    return []
            elif len(candidates) == 1:
                mod_root, mod_type = candidates[0]
            else:
                # Fallback to simple detection (likely unknown)
                mod_type = self._detect_mod_type(mod_root)

            if mod_type == "me3":
                return self._install_me3_mod(mod_root, mod_name_hint, load_mods)

            # Simplified: Treat all other types (native, package, unknown) as folder mods
            return self._install_folder_mod(
                mod_root, mod_name_hint, load_mods, mod_type
            )

        except Exception as e:
            self._log.exception("Mod installation failed")
            self._show_error(tr("import_error_msg", error=str(e)))
            return []

    # =========================================================================
    # MOD TYPE DETECTION
    # =========================================================================

    def _find_mod_root(self, folder: Path) -> Path:
        """
        Recursively find the real mod root by unwrapping single-child folders.
        Stops if it hits a folder with multiple children or mod files.
        """
        # Priority Check: If the current folder is already a valid mod package (especially me3),
        # return it immediately. Do not unwrap single children if the parent is already a valid mod.
        # This prevents drilling into the content of a me3 profile mod.
        detected_type = self._detect_mod_type(folder)
        if detected_type in ("me3", "native", "package"):
            return folder

        children = _filter_children(folder)

        if not children:
            return folder

        # If single child folder, check if it's the real mod
        if len(children) == 1 and children[0].is_dir():
            child = children[0]
            # Recursively find root in the child
            return self._find_mod_root(child)

        return folder

    def _scan_candidates(self, folder: Path) -> list[tuple[Path, str]]:
        """Find all viable mod candidates in folder."""
        candidates = []

        # Check root
        root_type = self._detect_mod_type(folder)
        # Use simple detection logic to avoid infinite recursion if _detect_mod_type calls this (it doesn't)
        if root_type in ("package", "native", "me3"):
            candidates.append((folder, root_type))

            # If root is a .me3 profile, it defines the entire mod structure.
            # We should NOT scan subfolders for other candidates, as they are likely
            # parts of the profile mod (e.g. DLLs or game folders)
            if root_type == "me3":
                return candidates

        # Check immediate subfolders
        for child in _filter_children(folder):
            if child.is_dir():
                t = self._detect_mod_type(child)

                # Filter out redundant candidates
                # If root accepts this type (same type), the root likely wraps it.
                # E.g. Root(dll) containing Child(dll) -> Root includes Child.
                if root_type == t:
                    continue

                if t in ("package", "native", "me3"):
                    candidates.append((child, t))

        return candidates

    def _detect_mod_type(
        self, folder: Path
    ) -> Literal["me3", "native", "package", "unknown"]:
        """
        Detect what type of mod this folder contains.

        Priority:
        1. me3 - Has .me3 profile file
        2. native - Has DLLs, no game asset folders
        3. package - Has game asset folders or regulation.bin
        """
        children = _filter_children(folder)

        # Priority 1: Has .me3 profile
        me3_files = list(folder.rglob("*.me3"))
        if me3_files:
            return "me3"
        if me3_files:
            return "me3"

        # Check for DLLs and game folders
        dlls = [c for c in children if c.is_file() and c.suffix.lower() == ".dll"]
        has_game_folders = any(
            c.is_dir() and c.name.lower() in ACCEPTABLE_FOLDERS for c in children
        )
        has_regulation = (folder / "regulation.bin").exists() or (
            folder / "regulation.bin.disabled"
        ).exists()

        # Priority 2: Native mod (DLL-only)
        if dlls and not has_game_folders and not has_regulation:
            return "native"

        # Priority 3: Package mod
        if has_game_folders or has_regulation:
            return "package"

        # Check for nested DLLs (e.g., SeamlessCoop/nrsc.dll)
        nested_dlls = list(folder.rglob("*.dll"))
        if nested_dlls:
            # Has DLLs somewhere inside - treat as native mod
            return "native"

        return "unknown"

    # =========================================================================
    # INSTALLATION METHODS
    # =========================================================================

    def _install_from_archive(
        self,
        archive: Path,
        mod_name_hint: str | None,
        mod_root_path: str | None = None,
        delete_archive: bool = False,
        load_mods: bool = True,
    ) -> list[str]:
        """Extract archive and install contents."""
        with TemporaryDirectory() as tmp:
            extract_dir = Path(tmp) / "extract"
            extract_dir.mkdir(parents=True, exist_ok=True)

            try:
                extract_archive(archive, extract_dir)
            except Exception as e:
                self._log.exception("Archive extraction failed for %s", archive)
                self._show_error(tr("download_file_not_vaild") + f"\n\n{e}")
                return []

            installed = self.install_mod(
                extract_dir,
                mod_name_hint=mod_name_hint or archive.stem,
                mod_root_path=mod_root_path,
            )
            if installed and delete_archive:
                try:
                    archive.unlink()
                except Exception as e:
                    # Best-effort cleanup; install already succeeded.
                    QMessageBox.warning(
                        self.game_page,
                        tr("ERROR"),
                        f"Installed successfully, but failed to delete archive:\n{archive}\n\n{e}",
                    )

            return installed

    def _install_me3_mod(
        self, mod_root: Path, mod_name_hint: str | None, load_mods: bool = True
    ) -> list[str]:
        """Install mod using its .me3 profile."""
        # Ensure we only pick up actual files, not directories
        me3_files = [p for p in mod_root.rglob("*.me3") if p.is_file()]

        if not me3_files:
            self._log.error(
                "Identified as 'me3' type but no .me3 files found in %s", mod_root
            )
            return []

        # Select profile if multiple
        if len(me3_files) > 1:
            items = [p.name for p in me3_files]
            selected, ok = QInputDialog.getItem(
                self.game_page,
                tr("select_profile_title"),
                tr("select_profile_desc"),
                items,
                0,
                False,
            )
            if not ok:
                return []
            profile_file = next(
                (p for p in me3_files if p.name == selected), me3_files[0]
            )
        else:
            profile_file = me3_files[0]

        self._log.info("Using profile file: %s", profile_file)

        return self._handle_profile_import(
            mod_root, profile_file, mod_name_hint, load_mods
        )

    def _install_folder_mod(
        self,
        mod_root: Path,
        mod_name_hint: str | None,
        load_mods: bool = True,
        mod_type: str = "unknown",
    ) -> list[str]:
        """Install mod as folder (unified installation for all mod types).

        Simplified logic:
        - All mods are installed as folders
        - Folder can contain DLLs, game assets, configs, or any combination
        - DLLs within folder are auto-registered as natives
        - Folder is registered for enable/disable
        """
        mod_name = self._resolve_mod_name(mod_name_hint, mod_root.name)
        if not mod_name:
            return []

        mods_dir = self._get_mods_dir()

        # Stage and copy the mod folder
        if not self._install_staged_items([(mod_root, Path(mod_name))]):
            return []

        # Register the folder mod (skip for native-only mods to avoid redundancy)
        dest = mods_dir / mod_name
        if mod_type != "native":
            self._register_folder_mod(mod_name, dest)

        # Auto-register all DLLs within the folder
        for dll in dest.rglob("*.dll"):
            self._register_native_mod(dll)

        if load_mods:
            self.game_page.load_mods()
        return [mod_name]

    def _install_staged_items(self, items_to_install: list[tuple[Path, Path]]) -> bool:
        """
        Stage and install a list of items with robust path handling.

        Args:
            items_to_install: List of (source_absolute_path, destination_relative_path)

        Returns:
            bool: True if installation succeeded, False otherwise.
        """
        if not items_to_install:
            return False

        with TemporaryDirectory() as tmp_dir:
            staged_items = []

            for src, dest_rel in items_to_install:
                # Ensure dest_rel is a Path
                dest_rel = Path(dest_rel)

                # Determine staged path
                staged_path = Path(tmp_dir) / dest_rel

                # Ensure parent directory exists in temp staging area
                staged_path.parent.mkdir(parents=True, exist_ok=True)

                if src.is_dir():
                    shutil.copytree(
                        src,
                        staged_path,
                        symlinks=False,
                        ignore_dangling_symlinks=True,
                        dirs_exist_ok=True,
                    )
                else:
                    shutil.copy2(src, staged_path, follow_symlinks=False)

                # Pass tuple to _copy_with_progress so InstallWorker uses relative path
                staged_items.append((staged_path, dest_rel))

            return self._copy_with_progress(staged_items)

    def _handle_profile_import(
        self,
        import_folder: Path,
        profile_file: Path,
        mod_name_override: str | None = None,
        load_mods: bool = True,
    ) -> list[str]:
        """
        Import mod using .me3 profile.
        """
        try:
            with open(profile_file, "r", encoding="utf-8") as f:
                raw_data = tomlkit.parse(f.read())
                from me3_manager.core.profiles import ProfileConverter

                profile_data = ProfileConverter.normalize(raw_data)

            # Use the profile file's parent as the base for resolving paths
            # Profile paths are relative to the .me3 file location, not the import_folder
            profile_base = profile_file.parent

            # Show merge/replace dialog
            dialog = QDialog(self.game_page)
            dialog.setWindowTitle(
                tr("import_profile_mods_title", game_name=self.game_page.game_name)
            )
            dialog.setModal(True)
            layout = QVBoxLayout()
            layout.addWidget(QLabel(tr("import_profile_mods_desc")))
            layout.addWidget(
                QLabel(tr("importing_from_label", folder=profile_base.name))
            )

            button_layout = QHBoxLayout()
            merge_btn = QPushButton(tr("merge_button_recommended"))
            replace_btn = QPushButton(tr("replace_button"))
            button_layout.addWidget(merge_btn)
            button_layout.addWidget(replace_btn)
            layout.addLayout(button_layout)
            dialog.setLayout(layout)

            merge_mode = None

            def on_merge():
                nonlocal merge_mode
                merge_mode = True
                dialog.accept()

            def on_replace():
                nonlocal merge_mode
                merge_mode = False
                dialog.accept()

            merge_btn.clicked.connect(on_merge)
            replace_btn.clicked.connect(on_replace)

            if dialog.exec() != QDialog.DialogCode.Accepted:
                return []

            # Check for nexus_link dependencies and download if needed
            # Done after confirmation so user knows what they are importing first
            self._handle_nexus_dependencies(profile_data)

            # Check for custom install script in profile metadata
            # Support both metadata.install_script (new standard) and older top-level if any
            install_script = profile_data.get("metadata", {}).get("install_script")
            script_approved = False

            if install_script:
                script_path = profile_base / install_script
                if script_path.exists():
                    # SECURITY: Ask user for permission
                    reply = QMessageBox.question(
                        self.game_page,
                        tr("custom_script_detected_title"),
                        tr("custom_script_detected_desc", script_name=install_script),
                        QMessageBox.Yes | QMessageBox.No,
                    )

                    if reply == QMessageBox.Yes:
                        script_approved = True
                        self._run_install_script(
                            script_path, profile_base, profile_data
                        )

            # Apply profile-level options
            self._apply_profile_options(profile_data)

            mods_dir = self._get_mods_dir()
            items_to_install: list[tuple[Path, str]] = []
            final_folder_names: list[str] = []

            # Collect packages
            for i, pkg in enumerate(profile_data.get("packages", [])):
                if isinstance(pkg, dict) and (pkg.get("source") or pkg.get("path")):
                    pkg_rel = Path(pkg.get("source") or pkg.get("path"))
                    pkg_abs = self._safe_join(profile_base, pkg_rel)
                    if pkg_abs and pkg_abs.is_dir():
                        dest_name = (
                            mod_name_override
                            if mod_name_override and i == 0
                            else pkg_abs.name
                        )
                        if _validate_mod_name(dest_name):
                            if pkg_abs and pkg_abs.is_dir():
                                items_to_install.append((pkg_abs, dest_name))
                                final_folder_names.append(dest_name)
                            else:
                                # If the package source doesn't exist (e.g. community profile),
                                # we just track the folder name so we can register it later.
                                # The assumption is that it will be filled by Nexus downloads or exists already.
                                final_folder_names.append(dest_name)

            # Collect natives not in packages
            # We need to map package source paths to their destination names (folder IDs)
            # so we can redirect natives to point inside the installed package.
            package_source_map = {}
            for i, pkg in enumerate(profile_data.get("packages", [])):
                if isinstance(pkg, dict) and (pkg.get("source") or pkg.get("path")):
                    pkg_rel = Path(pkg.get("source") or pkg.get("path"))
                    pkg_abs = self._safe_join(profile_base, pkg_rel)

                    # Determine the destination name (same logic as above loop)
                    dest_name = (
                        mod_name_override
                        if mod_name_override and i == 0
                        else pkg_abs.name
                    )
                    # If ID is present and valid, it takes precedence in the loop above?
                    # Wait, the loop above used `pkg_abs.name` as default dest_name unless overridden.
                    # It didn't explicitly use pkg['id'] unless mod_name_override logic covers it.
                    # Actually, `items_to_install.append((pkg_abs, dest_name))` uses `dest_name`.
                    # Let's ensure we use the exact same `dest_name` logic.

                    if pkg_abs and pkg_abs.is_dir():
                        package_source_map[pkg_abs] = dest_name

            # Stage and install
            for native in profile_data.get("natives", []):
                if not isinstance(native, dict):
                    continue

                self._process_import_native_entry(
                    native, profile_base, package_source_map, items_to_install
                )

            if (
                not items_to_install
                and not final_folder_names
                and not profile_data.get("natives")
                and not (script_approved and install_script)
            ):
                # Only cancel if truly nothing is happening (no folders register, no settings apply)
                self.game_page.status_label.setText(tr("import_cancelled_status"))
                return []

            # Stage and install
            if items_to_install:
                with TemporaryDirectory() as tmp_dir:
                    staged_items = []
                    for src, dest_name in items_to_install:
                        staged_path = Path(tmp_dir) / dest_name

                        # Ensure parent directory exists in temp staging area
                        staged_path.parent.mkdir(parents=True, exist_ok=True)

                        if src.is_dir():
                            shutil.copytree(
                                src,
                                staged_path,
                                symlinks=False,
                                ignore_dangling_symlinks=True,
                                dirs_exist_ok=True,
                            )
                        else:
                            shutil.copy2(src, staged_path, follow_symlinks=False)

                        # Pass tuple to _copy_with_progress so InstallWorker uses relative path
                        # First element is absolute path to staged file
                        # Second element is the relative path it should have in mods dir
                        dest_rel = (
                            dest_name
                            if isinstance(dest_name, Path)
                            else Path(dest_name)
                        )
                        staged_items.append((staged_path, dest_rel))

                    self._copy_with_progress(staged_items)

            # Register packages
            for folder_name in final_folder_names:
                self._register_folder_mod(folder_name, mods_dir / folder_name)

            # Register natives and apply settings (including load_early)
            for native in profile_data.get("natives", []):
                if isinstance(native, dict) and native.get("path"):
                    mod_path_str = native["path"]
                    # If relative, join with mods_dir
                    if not Path(mod_path_str).is_absolute():
                        full_path = mods_dir / mod_path_str
                    else:
                        full_path = Path(mod_path_str)

                    if full_path.exists():
                        # Enable it
                        self.config_manager.set_mod_enabled(
                            self.game_page.game_name, str(full_path), True
                        )

                        # Apply all settings (load_early, initializer, etc.)
                        settings = {
                            k: v
                            for k, v in native.items()
                            if k not in ("path", "enabled")
                        }
                        if settings:
                            self.config_manager.enable_native_with_options(
                                self.game_page.game_name, str(full_path), settings
                            )

            # Run post-install script if approved
            if script_approved and install_script:
                script_path = profile_base / install_script
                self._run_post_install_script(
                    script_path, final_folder_names, profile_data
                )

            # Show success dialog
            dialog = QDialog(self.game_page)
            dialog.setWindowTitle(tr("import_complete_title"))
            layout = QVBoxLayout()
            layout.addWidget(QLabel(tr("import_complete_success_header")))
            button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
            button_box.accepted.connect(dialog.accept)
            layout.addWidget(button_box)
            dialog.setLayout(layout)
            dialog.exec()

            # Apply configuration overrides
            mods_dir = self._get_mods_dir()

            def _apply_configs(entries):
                for entry in entries:
                    if (
                        isinstance(entry, dict)
                        and entry.get("config")
                        and entry.get("config_overrides")
                    ):
                        # path is relative to mods_dir
                        config_rel = entry["config"]
                        config_path = mods_dir / config_rel
                        # Simple security check to prevent escaping mods_dir
                        try:
                            config_path.resolve().relative_to(mods_dir.resolve())
                            ConfigApplicator.apply_ini_overrides(
                                config_path, entry["config_overrides"]
                            )
                        except Exception:
                            self._log.warning(
                                "Invalid config override path (security check failed): %s",
                                config_rel,
                            )

            _apply_configs(profile_data.get("natives", []))
            _apply_configs(profile_data.get("packages", []))

            self.game_page.load_mods()
            return final_folder_names

        except Exception as e:
            self._log.exception("Profile import failed")
            self._show_error(tr("import_error_msg", error=str(e)))
            return []

    # =========================================================================
    # NEXUS DEPENDENCY HANDLING
    # =========================================================================

    def _parse_nexus_url(self, url: str) -> tuple[str, int] | None:
        """Parse a Nexus Mods URL to extract game_domain and mod_id.

        Supports URLs like:
        - https://www.nexusmods.com/eldenring/mods/123
        - https://nexusmods.com/eldenring/mods/123
        """
        import re

        pattern = r"(?:https?://)?(?:www\.)?nexusmods\.com/([^/]+)/mods/(\d+)"
        match = re.search(pattern, url)
        if match:
            game_domain = match.group(1)
            mod_id = int(match.group(2))
            return (game_domain, mod_id)
        return None

    def _is_mod_installed(self, mod_name_hint: str) -> bool:
        """Check if a mod is already installed by checking the mods directory."""
        mods_dir = self._get_mods_dir()
        if not mods_dir.exists():
            return False

        # Check if any folder or DLL matches the mod name hint (case-insensitive)
        mod_name_lower = mod_name_hint.lower()
        for item in mods_dir.iterdir():
            if item.name.lower() == mod_name_lower:
                return True
            # Also check DLLs
            if item.suffix.lower() == ".dll" and item.stem.lower() == mod_name_lower:
                return True
        return False

    def _handle_nexus_dependencies(self, profile_data: dict) -> None:
        """Check for and download missing mods from nexus_link entries.

        Args:
            profile_data: Normalized profile data with natives and packages
        """
        # Collect all nexus_link entries from both natives and packages
        nexus_deps = []

        # Helper to process entries
        def _process_entries(entries, type_label):
            for entry in entries:
                if isinstance(entry, dict) and entry.get("nexus_link"):
                    nexus_url = entry["nexus_link"]
                    parsed = self._parse_nexus_url(nexus_url)
                    if parsed:
                        game_domain, mod_id = parsed
                        nexus_deps.append(
                            {
                                "type": type_label,
                                "url": nexus_url,
                                "game_domain": game_domain,
                                "mod_id": mod_id,
                                "settings": {
                                    k: v
                                    for k, v in entry.items()
                                    if k not in ("nexus_link", "path")
                                },
                                "entry": entry,
                            }
                        )

        _process_entries(profile_data.get("natives", []), "native")
        _process_entries(profile_data.get("packages", []), "package")

        if not nexus_deps:
            return

        # Check if we have nexus service available
        nexus_service = getattr(self.game_page, "nexus_service", None)
        if not nexus_service or not nexus_service.has_api_key:
            reply = QMessageBox.warning(
                self.game_page,
                tr("nexus_api_key_missing_status"),
                tr("nexus_dependencies_missing_api_key", count=len(nexus_deps)),
                QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
            )
            if reply == QMessageBox.StandardButton.Cancel:
                raise Exception("Nexus API key required for downloading dependencies")
            return

        # Filter to only mods that aren't already installed
        # For now, we'll just show all and let download_from_nexus handle duplicates
        missing_deps = nexus_deps

        # Show confirmation dialog
        msg_lines = [tr("nexus_dependencies_found", count=len(missing_deps)), ""]
        for i, dep in enumerate(missing_deps, 1):
            msg_lines.append(f"{i}. {dep['url']}")
        msg_lines.append("")
        msg_lines.append(tr("nexus_dependencies_confirm"))

        reply = QMessageBox.question(
            self.game_page,
            tr("nexus_dependencies_title"),
            "\n".join(msg_lines),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            # Download each missing dependency
            for dep in missing_deps:
                try:
                    mod = self.game_page.nexus_service.get_mod(
                        dep["game_domain"], dep["mod_id"]
                    )

                    # Use GamePage's existing download method headlessly
                    mod_folder = dep["entry"].get("mod_folder")
                    file_category = dep["settings"].get("nexus_category")
                    installed = self.game_page.download_selected_nexus_mod(
                        mod,
                        load_mods=False,
                        mod_root_path=mod_folder,
                        file_category=file_category,
                    )

                    if installed:
                        mod_name = (
                            installed[0]
                            if isinstance(installed[0], str)
                            else installed[0].name
                        )

                        # Resolve the path for the entry in the profile
                        if dep["type"] == "native":
                            # For natives, find the DLL inside the mod folder
                            mods_dir = self._get_mods_dir()
                            mod_path = mods_dir / mod_name
                            dll_files = list(mod_path.rglob("*.dll"))
                            if dll_files:
                                try:
                                    rel_dll = dll_files[0].relative_to(mods_dir)
                                    dep["entry"]["path"] = str(rel_dll).replace(
                                        "\\", "/"
                                    )
                                except Exception:
                                    pass
                        else:
                            # For packages, the path is just the folder name
                            dep["entry"]["path"] = mod_name

                        # Apply settings immediately as well
                        if dep["settings"]:
                            pass

                        # Save mod_root_path to metadata if provided in the profile
                        m_folder = dep["entry"].get("mod_folder") or dep["entry"].get(
                            "mod_root_path"
                        )
                        if m_folder:
                            try:
                                self.game_page.nexus_metadata.set_mod_root_path(
                                    dep["game_domain"], dep["mod_id"], m_folder
                                )
                            except Exception:
                                pass

                except Exception as e:
                    self._log.error(f"Failed to download {dep['url']}: {e}")
                    QMessageBox.warning(
                        self.game_page,
                        tr("ERROR"),
                        tr("nexus_download_failed", url=dep["url"], error=str(e)),
                    )
        finally:
            pass  # Sidebar is no longer touched during fetch

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def _process_import_native_entry(
        self,
        native: dict,
        profile_base: Path,
        package_source_map: dict[Path, str],
        items_to_install: list[tuple[Path, Path]],
    ):
        """Helper to process a single native entry during profile import."""
        has_path = bool(native.get("path"))
        if not has_path and not native.get("config"):
            return

        nat_abs = None
        if has_path:
            nat_rel = Path(native["path"])
            nat_abs = self._safe_join(profile_base, nat_rel)

        # 1. Process DLL installation if we have a valid source path
        if nat_abs and nat_abs.is_file() and nat_abs.suffix.lower() == ".dll":
            found_in_package = self._is_in_package(
                nat_abs, package_source_map, native, is_config=False
            )

            if not found_in_package:
                items_to_install.append((nat_abs, Path(native["path"])))

        # 2. Handle associated config
        # Explicit config field
        configs = native.get("config", [])
        if isinstance(configs, str):
            configs = [configs]

        for cfg_path_str in configs:
            if not cfg_path_str:
                continue

            cfg_rel = Path(cfg_path_str)
            cfg_abs = self._safe_join(profile_base, cfg_rel)

            if cfg_abs and cfg_abs.is_file():
                if not self._is_in_package(cfg_abs, package_source_map):
                    items_to_install.append((cfg_abs, cfg_rel))

        # Implicit config dir (only if we have a native path and no explicit configs)
        if nat_abs and not configs:
            cfg_dir = nat_abs.parent / nat_abs.stem
            if cfg_dir.is_dir():
                if not self._is_in_package(cfg_dir, package_source_map):
                    rel_parent = Path(native["path"]).parent
                    items_to_install.append((cfg_dir, rel_parent / cfg_dir.name))

    def _is_in_package(
        self,
        item_path: Path,
        package_source_map: dict[Path, str],
        native_entry: dict | None = None,
        is_config: bool = True,
    ) -> bool:
        """Check if an item is inside any of the packages being installed."""
        for pkg_src, pkg_dest_name in package_source_map.items():
            try:
                if item_path == pkg_src or item_path.is_relative_to(pkg_src):
                    # It is inside this package!
                    if not is_config and native_entry:
                        # Update profile path for natives
                        rel_inside_pkg = item_path.relative_to(pkg_src)
                        new_dest_path = Path(pkg_dest_name) / rel_inside_pkg
                        native_entry["path"] = str(new_dest_path).replace("\\", "/")
                    return True
            except Exception:
                continue
        return False

    def _sanitize_mod_name(self, name: str) -> str:
        """Sanitize mod name to be valid for Windows filesystem."""
        # Replace forbidden chars with underscore, but keep spaces
        name = re.sub(r'[<>:"/\\|?*]', "_", name)
        # Remove leading/trailing dots and spaces
        name = name.strip(". ")
        # Truncate to reasonable length
        if len(name) > 60:
            name = name[:60]
        return name

    def _resolve_mod_name(
        self, mod_name_hint: str | None, fallback_name: str
    ) -> str | None:
        """
        Resolve and validate mod name, prompting user ONLY if absolutely necessary.
        """
        # Try sanitized hint first
        if mod_name_hint:
            clean_hint = self._sanitize_mod_name(mod_name_hint)
            if _validate_mod_name(clean_hint):
                return clean_hint

        # Try sanitized fallback
        clean_fallback = self._sanitize_mod_name(fallback_name)
        if _validate_mod_name(clean_fallback):
            return clean_fallback

        # Last resort: Prompt user
        mod_name, ok = QInputDialog.getText(
            self.game_page,
            tr("name_mod_package_title"),
            tr("name_mod_package_desc"),
            text=mod_name_hint or fallback_name,
        )
        if not ok or not mod_name.strip():
            return None
        return mod_name.strip()

    def _get_mods_dir(self) -> Path:
        """Get the mods directory for the current game."""
        return self.config_manager.get_mods_dir(self.game_page.game_name)

    def _safe_join(self, base: Path, child: Path) -> Path | None:
        """Safely join paths, preventing traversal attacks."""
        try:
            if child.is_absolute():
                return None
            candidate = (base / child).resolve()
            candidate.relative_to(base.resolve())
            return candidate
        except Exception:
            return None

    def _show_error(self, message: str):
        """Show error message box."""
        QMessageBox.warning(self.game_page, tr("ERROR"), message)

    def _register_folder_mod(self, folder_name: str, dest_path: Path) -> bool:
        """Register a folder mod in config and enable it."""
        try:
            self.config_manager.add_folder_mod(
                self.game_page.game_name, folder_name, str(dest_path)
            )
            self.config_manager.set_mod_enabled(
                self.game_page.game_name, str(dest_path), True
            )
            return True
        except Exception:
            return False

    def _register_native_mod(self, dll_path: Path) -> bool:
        """Register a DLL mod in config and enable it."""
        try:
            self.config_manager.set_mod_enabled(
                self.game_page.game_name, str(dll_path), True
            )
            return True
        except Exception:
            return False

    def _apply_profile_options(self, profile_data: dict):
        """Apply profile-level options to the active profile."""
        try:
            target_profile_path = self.config_manager.get_profile_path(
                self.game_page.game_name
            )
        except Exception:
            return

        try:
            current_profile = ProfileManager.read_profile(target_profile_path)
        except Exception:
            current_profile = {"profileVersion": "v1", "natives": [], "packages": []}

        updated_profile = dict(current_profile)
        updated_profile["profileVersion"] = profile_data.get(
            "profileVersion", current_profile.get("profileVersion", "v1")
        )

        # Handle savefile conflict detection
        current_savefile = current_profile.get("savefile")
        imported_savefile = profile_data.get("savefile")

        # If both have different savefiles, ask user which to use
        if (
            current_savefile
            and imported_savefile
            and current_savefile != imported_savefile
        ):
            reply = QMessageBox.question(
                self.game_page,
                tr("savefile_preference_title"),
                tr(
                    "savefile_preference_message",
                    current_savefile=current_savefile,
                    imported_savefile=imported_savefile,
                ),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                # User chose to use imported savefile
                updated_profile["savefile"] = imported_savefile
            # else: keep current savefile (don't modify)
        elif imported_savefile:
            # No conflict - just apply imported savefile
            updated_profile["savefile"] = imported_savefile

        # Apply other profile options (excluding savefile which was handled above)
        for key in ("start_online", "disable_arxan", "supports"):
            if key in profile_data:
                updated_profile[key] = profile_data.get(key)

        try:
            ProfileManager.write_profile(
                target_profile_path, updated_profile, self.game_page.game_name
            )
        except Exception:
            pass

    def _copy_with_progress(self, items: list[Path | tuple[Path, Path]]) -> bool:
        """Copy items with progress dialog."""
        mods_dir = self._get_mods_dir()

        # Helper to get destination name for conflict check
        def get_dest_name(item: Path | tuple[Path, Path]) -> str:
            if isinstance(item, tuple):
                return str(item[1])
            return item.name

        # Check for conflicts
        # Check for conflicts
        conflicts = []
        config_conflicts = []

        for p in items:
            name = get_dest_name(p)
            target = mods_dir / name
            if target.exists():
                # Check if it's a specific config file
                # If target is a file, and extension is NOT a binary -> Treat as config/user data
                if target.is_file() and target.suffix.lower() not in _BINARY_EXTENSIONS:
                    config_conflicts.append(name)
                else:
                    conflicts.append(name)

        # Handle messages
        msgs = []
        if conflicts:
            msgs.append(tr("overwrite_dll_confirm_text"))
            msgs.extend(f"- {name}" for name in conflicts)
            msgs.append("")

        if config_conflicts:
            msgs.append(tr("shipped_configs_found_header"))
            for name in config_conflicts:
                # Try to extract mod name if possible (first folder of path)
                p = Path(name)
                if len(p.parts) > 1:
                    msgs.append(
                        tr("shipped_config_entry_fmt", config=p.name, mod=p.parts[0])
                    )
                else:
                    msgs.append(f"- {name}")
            msgs.append(tr("use_shipped_config_question"))

        if conflicts or config_conflicts:
            reply = QMessageBox.question(
                self.game_page,
                tr("confirm_overwrite_title"),
                "\n".join(msgs),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                # Filter out all conflicts
                all_conflicts = set(conflicts + config_conflicts)
                items = [p for p in items if get_dest_name(p) not in all_conflicts]

        if not items:
            return False

        progress = QProgressDialog(
            tr("installing_status", name="..."),
            tr("cancel_button"),
            0,
            len(items),
            self.game_page,
        )
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        # Prevent auto-close/reset race conditions
        progress.setAutoClose(False)
        progress.setAutoReset(False)

        worker = InstallWorker(items, mods_dir)

        def on_progress(status, current, total):
            progress.setLabelText(status)
            progress.setMaximum(total)
            progress.setValue(current)

        def on_complete(count, errors):
            progress.close()

        worker.progress_update.connect(on_progress)
        worker.finished_signal.connect(on_complete)
        progress.canceled.connect(worker.requestInterruption)

        worker.start()
        progress.exec()
        worker.wait()

        if worker.errors:
            QMessageBox.warning(
                self.game_page, tr("install_error_title"), "\n".join(worker.errors)
            )

        return worker.installed_count > 0

    def _run_install_script(
        self, script_path: Path, root_path: Path, profile_data: dict | None = None
    ) -> bool:
        """
        Run a custom installation script from the profile.

        The script should define:
        def on_prepare_install(context): ...

        context provides:
        - root_path: Path (temp dir containing extracted files)
        - mods_dir: Path (game mods directory)
        - game_name: str
        - profile_data: dict (mutable profile data)
        """
        import importlib.util

        try:
            self._log.info("Running custom install script: %s", script_path)

            # Load module dynamically
            spec = importlib.util.spec_from_file_location(
                "mod_install_hook", script_path
            )
            if not spec or not spec.loader:
                raise ImportError(f"Could not load script from {script_path}")

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Check for hook
            if hasattr(module, "on_prepare_install"):
                context = {
                    "root_path": root_path,
                    "mods_dir": self._get_mods_dir(),
                    "game_name": self.game_page.game_name,
                    "profile_data": profile_data,
                    "shutil": shutil,
                    "Path": Path,
                }
                module.on_prepare_install(context)
                self._log.info("Custom install script executed successfully")
                return True
            else:
                self._log.warning(
                    "Script %s has no on_prepare_install function", script_path.name
                )
                return False

        except Exception as e:
            self._log.exception("Error running install script")
            self._show_error(tr("script_execution_failed", error=str(e)))
            return False

    def _run_post_install_script(
        self,
        script_path: Path,
        installed_list: list[str],
        profile_data: dict | None = None,
    ) -> bool:
        """
        Run a custom post-installation script.

        The script should define:
        def on_post_install(context): ...

        context provides:
        - installed: list[str] (names of installed mods, mutable)
        - mods_dir: Path
        - game_name: str
        - profile_data: dict
        """
        import importlib.util

        try:
            self._log.info("Running post-install script: %s", script_path)

            spec = importlib.util.spec_from_file_location(
                "mod_post_install_hook", script_path
            )
            if not spec or not spec.loader:
                return False

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            if hasattr(module, "on_post_install"):
                context = {
                    "installed": installed_list,
                    "mods_dir": self._get_mods_dir(),
                    "game_name": self.game_page.game_name,
                    "profile_data": profile_data,
                    "shutil": shutil,
                    "Path": Path,
                }
                module.on_post_install(context)
                self._log.info("Post-install script executed successfully")
                return True
            return False
        except Exception:
            self._log.exception("Error running post-install script")
            return False
