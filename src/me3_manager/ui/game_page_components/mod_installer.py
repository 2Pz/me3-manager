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
import zipfile
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

from me3_manager.core.profiles.profile_manager import ProfileManager
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

    def __init__(self, items_to_install: list[Path], mods_dir: Path):
        super().__init__()
        self.items = items_to_install
        self.mods_dir = mods_dir

    def run(self):
        self.installed_count = 0
        self.errors = []
        parent = self.mods_dir.resolve()

        for i, item_path in enumerate(self.items):
            if self.isInterruptionRequested():
                break

            self.progress_update.emit(
                tr("installing_status", name=item_path.name), i, len(self.items)
            )

            try:
                if _contains_symlink(item_path):
                    msg = tr("symlink_rejected_msg", name=item_path.name)
                    self.errors.append(msg)
                    continue

                dest_path = self.mods_dir / item_path.name
                try:
                    dest_path.resolve().relative_to(parent)
                except ValueError:
                    msg = tr("invalid_destination_path_msg", name=item_path.name)
                    self.errors.append(msg)
                    continue

                with TemporaryDirectory(dir=str(parent)) as tmp_root_str:
                    tmp_root = Path(tmp_root_str)
                    tmp_dst = tmp_root / item_path.name

                    if item_path.is_dir():
                        shutil.copytree(
                            item_path,
                            tmp_dst,
                            symlinks=False,
                            ignore_dangling_symlinks=True,
                        )
                    else:
                        shutil.copy2(item_path, tmp_dst, follow_symlinks=False)

                    # Atomic replace
                    try:
                        tmp_dst.replace(dest_path)
                    except OSError:
                        if dest_path.is_dir():
                            shutil.rmtree(dest_path)
                        elif dest_path.exists():
                            dest_path.unlink()
                        tmp_dst.replace(dest_path)

                self.installed_count += 1
            except Exception as e:
                self.errors.append(
                    tr("copy_failed_msg", name=item_path.name, error=str(e))
                )

        self.finished_signal.emit(self.installed_count, self.errors)

    # ... (skipping ModInstaller class and other methods) ...
    # Wait, need to check where _copy_with_progress is relative to this.
    # It's inside ModInstaller which is AFTER InstallWorker.
    # So I need to perform TWO replacements or ONE large one if they are close.
    # They are separated by ModInstaller __init__ and likely other methods.
    # I will do InstallWorker first.


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

    # =========================================================================
    # PUBLIC API - Single Entry Point
    # =========================================================================

    def install_mod(
        self,
        source: Path,
        *,
        nexus_mod_id: int | None = None,
        mod_name_hint: str | None = None,
        mod_root_path: str | None = None,
    ) -> list[str]:
        """
        Universal mod installation entry point.

        Args:
            source: Path to folder or archive to install
            nexus_mod_id: Optional Nexus mod ID (unused, for future tracking)
            mod_name_hint: Suggested name for the mod (e.g., from Nexus)
            mod_root_path: User-specified relative path to mod root within archive

        Returns:
            List of installed mod folder/file names
        """
        try:
            # Handle archives
            if source.is_file() and source.suffix.lower() == ".zip":
                return self._install_from_archive(source, mod_name_hint, mod_root_path)

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
                else:
                    return []
            elif len(candidates) == 1:
                mod_root, mod_type = candidates[0]
            else:
                # Fallback to simple detection (likely unknown)
                mod_type = self._detect_mod_type(mod_root)

            if mod_type == "me3":
                return self._install_me3_mod(mod_root, mod_name_hint)
            elif mod_type == "native":
                return self._install_native_mod(mod_root, mod_name_hint)
            elif mod_type == "package":
                return self._install_package_mod(mod_root, mod_name_hint)

            self._show_error(tr("unknown_mod_structure_error"))
            return []

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
        children = _filter_children(folder)

        # Determine if current folder is potentially a mod
        # (This prevents unwrapping valid mods that just happen to have 1 folder?)
        # Actually our wrapper logic is safe because we check TYPE.
        # But wait, if ambiguity exists, unwrapping might HIDE the outer candidate?
        # NO, _find_mod_root is called BEFORE scanning.
        # If folder has 1 child "Grand Merchant", and inside is "Mod", "modengine2".
        # Unwrap "Grand Merchant". Now root is "Grand Merchant" folder content.
        # Scan candidates on THAT.
        # That seems correct.

        if not children:
            return folder

        # If single child folder, check if it's the real mod
        if len(children) == 1 and children[0].is_dir():
            child = children[0]
            # Verify we aren't unwrapping a valid mod (like a packge with just 'msg' folder?)
            # But 'msg' is acceptable folder.
            # _detect_mod_type(child)
            # If child IS a mod, we return child?
            # Existing logic:
            child_type = self._detect_mod_type(child)
            if child_type in ("me3", "native", "package"):
                return child

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

        # Check for DLLs and game folders
        dlls = [c for c in children if c.is_file() and c.suffix.lower() == ".dll"]
        has_game_folders = any(
            c.is_dir() and c.name in ACCEPTABLE_FOLDERS for c in children
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
        self, archive: Path, mod_name_hint: str | None, mod_root_path: str | None = None
    ) -> list[str]:
        """Extract archive and install contents."""
        with TemporaryDirectory() as tmp:
            extract_dir = Path(tmp) / "extract"
            extract_dir.mkdir(parents=True, exist_ok=True)

            try:
                with zipfile.ZipFile(archive, "r") as z:
                    z.extractall(extract_dir)
            except Exception:
                self._show_error(tr("download_file_not_vaild"))
                return []

            return self.install_mod(
                extract_dir,
                mod_name_hint=mod_name_hint or archive.stem,
                mod_root_path=mod_root_path,
            )

    def _install_me3_mod(self, mod_root: Path, mod_name_hint: str | None) -> list[str]:
        """Install mod using its .me3 profile."""
        me3_files = list(mod_root.rglob("*.me3"))

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

        return self._handle_profile_import(mod_root, profile_file, mod_name_hint)

    def _install_native_mod(
        self, mod_root: Path, mod_name_hint: str | None
    ) -> list[str]:
        """Install native (DLL-only) mod."""
        mod_name = self._resolve_mod_name(mod_name_hint, mod_root.name)
        if not mod_name:
            return []

        mods_dir = self._get_mods_dir()

        # Stage and copy the mod
        if not self._stage_and_copy_mod(mod_root, mod_name):
            return []

        # Register all DLLs (handles both root-level and nested)
        wrapper = mods_dir / mod_name
        for dll in wrapper.rglob("*.dll"):
            self._register_native_mod(dll)

        self.game_page.load_mods()
        return [mod_name]

    def _install_package_mod(
        self, mod_root: Path, mod_name_hint: str | None
    ) -> list[str]:
        """Install package mod (game assets)."""
        mod_name = self._resolve_mod_name(mod_name_hint, mod_root.name)
        if not mod_name:
            return []

        mods_dir = self._get_mods_dir()

        # Stage and copy the mod
        if not self._stage_and_copy_mod(mod_root, mod_name):
            return []

        # Register as package mod
        dest = mods_dir / mod_name
        self._register_folder_mod(mod_name, dest)
        self.game_page.load_mods()
        return [mod_name]

    def _handle_profile_import(
        self,
        import_folder: Path,
        profile_file: Path,
        mod_name_override: str | None = None,
    ) -> list[str]:
        """
        Import mod using .me3 profile.
        """
        try:
            with open(profile_file, "r", encoding="utf-8") as f:
                raw_data = tomlkit.parse(f.read())
                from me3_manager.core.profiles import ProfileConverter

                profile_data = ProfileConverter.normalize(raw_data)

            # Show merge/replace dialog
            dialog = QDialog(self.game_page)
            dialog.setWindowTitle(
                tr("import_profile_mods_title", game_name=self.game_page.game_name)
            )
            dialog.setModal(True)
            layout = QVBoxLayout()
            layout.addWidget(QLabel(tr("import_profile_mods_desc")))
            layout.addWidget(
                QLabel(tr("importing_from_label", folder=import_folder.name))
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

            # Apply profile-level options
            self._apply_profile_options(profile_data)

            mods_dir = self._get_mods_dir()
            items_to_install: list[tuple[Path, str]] = []
            final_folder_names: list[str] = []

            # Collect packages
            for i, pkg in enumerate(profile_data.get("packages", [])):
                if isinstance(pkg, dict) and (pkg.get("source") or pkg.get("path")):
                    pkg_rel = Path(pkg.get("source") or pkg.get("path"))
                    pkg_abs = self._safe_join(import_folder, pkg_rel)
                    if pkg_abs and pkg_abs.is_dir():
                        dest_name = (
                            mod_name_override
                            if mod_name_override and i == 0
                            else pkg_abs.name
                        )
                        if _validate_mod_name(dest_name):
                            items_to_install.append((pkg_abs, dest_name))
                            final_folder_names.append(dest_name)

            # Collect natives not in packages
            pkg_names = [
                Path(pkg.get("source") or pkg.get("path")).name
                for pkg in profile_data.get("packages", [])
                if isinstance(pkg, dict) and (pkg.get("source") or pkg.get("path"))
            ]

            for native in profile_data.get("natives", []):
                if not (isinstance(native, dict) and native.get("path")):
                    continue
                nat_rel = Path(native["path"])
                nat_abs = self._safe_join(import_folder, nat_rel)
                if (
                    not nat_abs
                    or not nat_abs.is_file()
                    or nat_abs.suffix.lower() != ".dll"
                ):
                    continue
                # Skip if in a package
                if any((import_folder / p / nat_abs.name).exists() for p in pkg_names):
                    continue
                items_to_install.append((nat_abs, nat_abs.name))
                cfg_dir = nat_abs.parent / nat_abs.stem
                if cfg_dir.is_dir():
                    items_to_install.append((cfg_dir, cfg_dir.name))

            if not items_to_install:
                self.game_page.status_label.setText(tr("import_cancelled_status"))
                return []

            # Stage and install
            with TemporaryDirectory() as tmp_dir:
                staged_items = []
                for src, dest_name in items_to_install:
                    staged_path = Path(tmp_dir) / dest_name
                    if src.is_dir():
                        shutil.copytree(
                            src,
                            staged_path,
                            symlinks=False,
                            ignore_dangling_symlinks=True,
                        )
                    else:
                        shutil.copy2(src, staged_path, follow_symlinks=False)
                    staged_items.append(staged_path)

                self._copy_with_progress(staged_items)

            # Register packages
            for folder_name in final_folder_names:
                self._register_folder_mod(folder_name, mods_dir / folder_name)

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

            self.game_page.load_mods()
            return final_folder_names

        except Exception as e:
            self._log.exception("Profile import failed")
            self._show_error(tr("import_error_msg", error=str(e)))
            return []

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def _resolve_mod_name(
        self, mod_name_hint: str | None, fallback_name: str
    ) -> str | None:
        """
        Resolve and validate mod name, prompting user if needed.

        Returns validated mod name or None if cancelled/invalid.
        """
        mod_name = mod_name_hint or fallback_name
        if not _validate_mod_name(mod_name):
            mod_name, ok = QInputDialog.getText(
                self.game_page,
                tr("name_mod_package_title"),
                tr("name_mod_package_desc"),
                text=fallback_name,
            )
            if not ok or not mod_name.strip():
                return None
            mod_name = mod_name.strip()

        if not _validate_mod_name(mod_name):
            self._show_error(tr("invalid_mod_name_msg"))
            return None
        return mod_name

    def _stage_and_copy_mod(self, mod_root: Path, mod_name: str) -> bool:
        """
        Stage mod contents into a temp folder with correct name and copy to mods dir.

        Handles both same-name and different-name scenarios.
        Returns True on success, False on failure/cancellation.
        """
        with TemporaryDirectory() as tmp:
            staged = Path(tmp) / mod_name
            if mod_root.name == mod_name:
                # Copy the folder directly (it already has the right name)
                shutil.copytree(
                    mod_root, staged, symlinks=False, ignore_dangling_symlinks=True
                )
            else:
                # Wrap contents in a new folder with mod_name
                staged.mkdir(parents=True, exist_ok=True)
                for item in _filter_children(mod_root):
                    _copy_item(item, staged / item.name)

            return self._copy_with_progress([staged])

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

        for key in ("start_online", "disable_arxan", "supports", "savefile"):
            if key in profile_data:
                updated_profile[key] = profile_data.get(key)

        try:
            ProfileManager.write_profile(
                target_profile_path, updated_profile, self.game_page.game_name
            )
        except Exception:
            pass

    def _copy_with_progress(self, items: list[Path]) -> bool:
        """Copy items with progress dialog."""
        mods_dir = self._get_mods_dir()

        # Check for conflicts
        conflicts = [p for p in items if (mods_dir / p.name).exists()]
        if conflicts:
            msg = tr("overwrite_dll_confirm_text") + "\n".join(
                f"- {p.name}" for p in conflicts
            )
            reply = QMessageBox.question(
                self.game_page,
                tr("confirm_overwrite_title"),
                msg,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                conflict_names = {p.name for p in conflicts}
                items = [p for p in items if p.name not in conflict_names]

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
