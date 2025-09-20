"""
Mod Installation Handler for GamePage.

Handles the logic for installing mods from various sources, including loose files,
packaged folders, and imported profiles (.me3 files). Manages file operations and
user dialogs for naming and overwriting mods.
"""

import re
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING

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

from me3_manager.utils.translator import tr

if TYPE_CHECKING:
    from me3_manager.ui.game_page_components import GamePage


# Reserved names that cause issues
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

# Regex for valid mod names (letters, numbers, spaces, underscores, dots, hyphens)
NAME_RE = re.compile(r'^[^<>:"/\\|?*]{1,60}$')


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
    if not NAME_RE.fullmatch(mod_name):
        return False
    if Path(mod_name).stem.upper() in RESERVED_NAMES:
        return False
    if mod_name in (".", ".."):
        return False
    # Disallow trailing dot or space to avoid Windows filesystem issues
    if mod_name[-1] in {".", " "}:
        return False
    return True


class InstallWorker(QThread):
    progress_update = Signal(str, int, int)  # status, current, total
    finished_signal = Signal(int, list)  # installed_count, errors

    def __init__(self, items_to_install, mods_dir, operation_type="install"):
        super().__init__()
        self.items = items_to_install
        self.mods_dir = mods_dir
        self.operation_type = operation_type

    def _copy_with_cancel(self, src, dst, *, follow_symlinks=False):
        """Copy function that respects cancellation and doesn't follow symlinks."""
        if self.isInterruptionRequested():
            raise RuntimeError("cancelled")
        return shutil.copy2(src, dst, follow_symlinks=follow_symlinks)

    def run(self):
        installed, errors = 0, []
        parent = self.mods_dir.resolve()

        for i, item_path in enumerate(self.items):
            if self.isInterruptionRequested():
                break

            self.progress_update.emit(
                tr("installing_status", name=item_path.name), i, len(self.items)
            )

            try:
                # Check for symlinks before processing
                if _contains_symlink(item_path):
                    errors.append(tr("symlink_rejected_msg", name=item_path.name))
                    continue

                dest_path = self.mods_dir / item_path.name
                # Validate destination path is within mods directory
                try:
                    dest_path.resolve().relative_to(parent)
                except ValueError:
                    errors.append(
                        tr("invalid_destination_path_msg", name=item_path.name)
                    )
                    continue

                with TemporaryDirectory(dir=str(parent)) as tmp_root_str:
                    tmp_root = Path(tmp_root_str)
                    tmp_dst = tmp_root / item_path.name

                    if item_path.is_dir():
                        shutil.copytree(
                            item_path,
                            tmp_dst,
                            copy_function=self._copy_with_cancel,
                            symlinks=False,
                            ignore_dangling_symlinks=True,
                        )
                    else:
                        if self.isInterruptionRequested():
                            raise RuntimeError("cancelled")
                        shutil.copy2(item_path, tmp_dst, follow_symlinks=False)

                    # Atomic replace with fallback
                    try:
                        tmp_dst.replace(dest_path)
                    except OSError:
                        if dest_path.is_dir():
                            shutil.rmtree(dest_path)
                        elif dest_path.exists():
                            dest_path.unlink()
                        tmp_dst.replace(dest_path)

                # If a DLL was installed, also copy same-stem config folder and files
                try:
                    if item_path.is_file() and item_path.suffix.lower() == ".dll":
                        stem = item_path.stem
                        src_dir = item_path.parent
                        # 1) Config folder with same stem
                        cfg_dir = src_dir / stem
                        if cfg_dir.is_dir():
                            dst_cfg_dir = self.mods_dir / stem
                            if not dst_cfg_dir.exists():
                                shutil.copytree(
                                    cfg_dir,
                                    dst_cfg_dir,
                                    symlinks=False,
                                    ignore_dangling_symlinks=True,
                                )
                        # 2) Common config files with same stem
                        for ext in (".ini", ".cfg", ".toml", ".json"):
                            src_cfg = src_dir / f"{stem}{ext}"
                            if src_cfg.is_file():
                                dst_cfg = self.mods_dir / src_cfg.name
                                try:
                                    shutil.copy2(src_cfg, dst_cfg)
                                except Exception:
                                    pass
                except Exception:
                    pass

                installed += 1
            except RuntimeError as ex:
                if str(ex) == "cancelled":
                    break
                raise
            except Exception as e:
                errors.append(tr("copy_failed_msg", name=item_path.name, error=str(e)))

        self.finished_signal.emit(installed, errors)


class ModInstaller:
    def __init__(self, game_page: "GamePage"):
        self.game_page = game_page
        self.config_manager = game_page.config_manager

    def _safe_within(self, base: Path, target: Path) -> bool:
        """Check if target path is safely within base directory."""
        try:
            target.resolve().relative_to(base.resolve())
            return True
        except Exception:
            return False

    def _atomic_replace(self, tmp_dst: Path, final_dst: Path) -> None:
        """Atomically replace destination with temporary source."""
        try:
            tmp_dst.replace(final_dst)
        except OSError:
            if final_dst.is_dir():
                shutil.rmtree(final_dst, ignore_errors=True)
            elif final_dst.exists():
                final_dst.unlink(missing_ok=True)
            tmp_dst.replace(final_dst)

    def _safe_join(self, base: Path, child: Path) -> Path:
        """Safely join paths, preventing traversal attacks."""
        if child.is_absolute():
            raise ValueError(tr("absolute_path_in_profile_msg"))
        base_res = base.resolve()
        candidate = (base / child).resolve()
        candidate.relative_to(base_res)
        return candidate

    def install_linked_mods(self, items_to_install: list[Path]) -> bool:
        """
        Installs a list of items (DLLs and their associated config folders) directly
        into the mods directory without bundling them.
        """
        mods_dir = self.config_manager.get_mods_dir(self.game_page.game_name)
        conflicts = [p for p in items_to_install if (mods_dir / p.name).exists()]

        if conflicts:
            conflict_msg = tr("overwrite_dll_confirm_text") + "\n".join(
                f"- {p.name}" for p in conflicts
            )
            reply = QMessageBox.question(
                self.game_page,
                tr("confirm_overwrite_title"),
                conflict_msg,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                conflict_names = {p.name for p in conflicts}
                items_to_install = [
                    p for p in items_to_install if p.name not in conflict_names
                ]

        if not items_to_install:
            self.game_page.status_label.setText(tr("install_cancelled_status"))
            return False

        # Create progress dialog and worker
        progress = QProgressDialog(
            tr("install_in_progress"),
            tr("cancel_button"),
            0,
            len(items_to_install),
            self.game_page,
        )
        progress.setWindowModality(Qt.WindowModality.WindowModal)

        worker = InstallWorker(items_to_install, mods_dir, "linked")

        result = {"success": False}

        def on_progress_update(status, current, total):
            progress.setLabelText(status)
            progress.setMaximum(total)
            # Show progress in range 1..total for better UX
            progress.setValue(current + 1)

        def on_install_complete(installed_count, errors):
            # Ensure progress shows as complete
            progress.setValue(progress.maximum())
            progress.close()

            if errors:
                QMessageBox.warning(
                    self.game_page, tr("install_error_title"), "\n".join(errors)
                )

            if installed_count > 0:
                self.game_page.status_label.setText(
                    tr("install_success_status", count=installed_count)
                )
                self.game_page.load_mods()
                result["success"] = True
            else:
                result["success"] = False

        worker.progress_update.connect(on_progress_update)
        worker.finished_signal.connect(on_install_complete)
        progress.canceled.connect(worker.requestInterruption)

        worker.start()
        progress.exec()
        # Ensure the thread has fully stopped before returning
        worker.wait()

        return result["success"]

    def install_root_mod_package(self, root_path: Path):
        # Check for symlinks before processing
        if _contains_symlink(root_path):
            QMessageBox.warning(
                self.game_page, tr("ERROR"), tr("symlink_rejected_package_msg")
            )
            return

        mod_name, ok = QInputDialog.getText(
            self.game_page,
            tr("name_mod_package_title"),
            tr("name_mod_package_desc"),
            text=root_path.name,
        )
        if not ok or not mod_name.strip():
            return
        mod_name = mod_name.strip()

        # Validate mod name against reserved names and illegal characters
        if not _validate_mod_name(mod_name):
            QMessageBox.warning(self.game_page, tr("ERROR"), tr("invalid_mod_name_msg"))
            return

        # Sanitize mod name
        mod_name = Path(mod_name).name

        # Use the unified installer pathway
        success = self.install_linked_mods([root_path])
        if not success:
            return

        mods_dir = self.config_manager.get_mods_dir(self.game_page.game_name)
        dest_folder_path = mods_dir / root_path.name
        try:
            self.config_manager.add_folder_mod(
                self.game_page.game_name, root_path.name, str(dest_folder_path)
            )
            self.config_manager.set_mod_enabled(
                self.game_page.game_name, str(dest_folder_path), True
            )
            self.game_page.status_label.setText(
                tr("install_package_success_status", mod_name=root_path.name)
            )
            self.game_page.load_mods()
        except Exception as e:
            QMessageBox.warning(
                self.game_page,
                tr("install_error_title"),
                tr("create_folder_mod_failed_msg", mod_name=mod_name, error=str(e)),
            )

    def install_mods_folder_root(self, root_dir: Path):
        """Install each valid child of a dropped container folder using existing flows."""
        try:
            if not root_dir.is_dir():
                return
            if _contains_symlink(root_dir):
                QMessageBox.warning(
                    self.game_page, tr("ERROR"), tr("symlink_rejected_package_msg")
                )
                return

            # Build install set using the same linked logic (DLL + same-stem folder)
            items_to_install = set()
            package_folders = []

            try:
                for child in root_dir.iterdir():
                    if _contains_symlink(child):
                        continue
                    if child.is_file() and child.suffix.lower() == ".dll":
                        items_to_install.add(child)
                        cfg_dir = root_dir / child.stem
                        if cfg_dir.is_dir():
                            items_to_install.add(cfg_dir)
                    elif child.is_dir() and self.game_page._is_valid_mod_folder(child):
                        # Validate/sanitize mod folder name
                        if _validate_mod_name(child.name):
                            items_to_install.add(child)
                            package_folders.append(child.name)
            except Exception:
                pass

            if not items_to_install:
                return

            # Use existing linked installer to copy files/folders consistently
            success = self.install_linked_mods(list(items_to_install))

            if not success:
                return

            # Register and enable only the package folders (match other flows)
            mods_dir = self.config_manager.get_mods_dir(self.game_page.game_name)
            for folder_name in package_folders:
                dest_path = mods_dir / folder_name
                try:
                    self.config_manager.add_folder_mod(
                        self.game_page.game_name, folder_name, str(dest_path)
                    )
                    self.config_manager.set_mod_enabled(
                        self.game_page.game_name, str(dest_path), True
                    )
                except Exception:
                    continue

            # Refresh after enabling packages
            self.game_page.load_mods()
            self.game_page.status_label.setText(tr("status_ready"))
        except Exception as e:
            QMessageBox.warning(
                self.game_page,
                tr("install_error_title"),
                tr("import_error_msg", error=str(e)),
            )
            self.game_page.status_label.setText(tr("status_ready"))

    def handle_profile_import(self, import_folder: Path, profile_file: Path):
        """
        Imports a profile and its mods, then cleans up the manager's copy of the profile.
        """
        try:
            with open(profile_file, "r", encoding="utf-8") as f:
                raw_data = tomlkit.parse(f.read())
                # Normalize any profile version to canonical structure
                from me3_manager.core.profiles import ProfileConverter

                profile_data = ProfileConverter.normalize(raw_data)

            # Ask the user to merge with existing mods or replace them.
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
                self.game_page.status_label.setText(tr("import_cancelled_status"))
                return

            # Prepare to install referenced mods without persisting the .me3 file
            mods_dir = self.config_manager.get_mods_dir(self.game_page.game_name)

            # Build install set using the same linked logic
            mods_dir = self.config_manager.get_mods_dir(self.game_page.game_name)
            items_to_install = set()
            package_folder_names: list[str] = []

            # Collect package folders
            for pkg in profile_data.get("packages", []):
                if isinstance(pkg, dict) and (pkg.get("source") or pkg.get("path")):
                    try:
                        pkg_rel = Path(pkg.get("source") or pkg.get("path"))
                        pkg_abs = self._safe_join(import_folder, pkg_rel)
                        if pkg_abs.is_dir() and _validate_mod_name(pkg_abs.name):
                            items_to_install.add(pkg_abs)
                            package_folder_names.append(pkg_abs.name)
                    except Exception:
                        continue

            # Collect natives (DLLs) that are not inside collected package folders
            for native in profile_data.get("natives", []):
                if not (isinstance(native, dict) and native.get("path")):
                    continue
                try:
                    nat_rel = Path(native["path"])
                    nat_abs = self._safe_join(import_folder, nat_rel)
                    if not (nat_abs.is_file() and nat_abs.suffix.lower() == ".dll"):
                        continue
                    # Skip if DLL lives under a package folder we already plan to install
                    if any(
                        (import_folder / p / nat_abs.name).exists()
                        for p in package_folder_names
                    ):
                        continue
                    items_to_install.add(nat_abs)
                    cfg_dir = nat_abs.parent / nat_abs.stem
                    if cfg_dir.is_dir():
                        items_to_install.add(cfg_dir)
                except Exception:
                    continue

            if not items_to_install:
                self.game_page.status_label.setText(tr("import_cancelled_status"))
                return

            # Use existing linked installer for consistent copying
            self.install_linked_mods(list(items_to_install))

            # Register and enable only the package folders
            for folder_name in package_folder_names:
                dest_path = mods_dir / folder_name
                try:
                    self.config_manager.add_folder_mod(
                        self.game_page.game_name, folder_name, str(dest_path)
                    )
                    self.config_manager.set_mod_enabled(
                        self.game_page.game_name, str(dest_path), True
                    )
                except Exception:
                    continue

            # Show a summary of the import.
            completion_dialog = QDialog(self.game_page)
            completion_dialog.setWindowTitle(tr("import_complete_title"))
            completion_layout = QVBoxLayout()
            completion_layout.addWidget(QLabel(tr("import_complete_success_header")))

            button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
            button_box.accepted.connect(completion_dialog.accept)
            completion_layout.addWidget(button_box)
            completion_dialog.setLayout(completion_layout)
            completion_dialog.exec()

            # Refresh UI after import completes
            self.game_page.load_mods()
            self.game_page.status_label.setText(tr("status_ready"))

        except Exception as e:
            QMessageBox.warning(
                self.game_page,
                tr("import_error_title"),
                tr("import_error_msg", error=str(e)),
            )
            self.game_page.status_label.setText(tr("status_ready"))

    def install_loose_items(self, items_to_install: list[Path]):
        if not items_to_install:
            return

        # Check for symlinks in any of the items before processing
        for item in items_to_install:
            if _contains_symlink(item):
                QMessageBox.warning(
                    self.game_page, tr("ERROR"), tr("symlink_rejected_items_msg")
                )
                return

        mod_name, ok = QInputDialog.getText(
            self.game_page,
            tr("new_mod_name_title"),
            tr("new_mod_name_desc", count=len(items_to_install)),
            text="new_bundled_mod",
        )
        if not ok or not mod_name.strip():
            return
        mod_name = mod_name.strip()

        # Validate mod name against reserved names and illegal characters
        if not _validate_mod_name(mod_name):
            QMessageBox.warning(self.game_page, tr("ERROR"), tr("invalid_mod_name_msg"))
            return

        # Sanitize mod name
        mod_name = Path(mod_name).name

        # Build a temporary staging folder under a container with the chosen mod name
        with TemporaryDirectory() as tmp_dir:
            staging_root = Path(tmp_dir) / mod_name
            staging_root.mkdir(parents=True, exist_ok=True)

            for item in items_to_install:
                try:
                    if item.is_dir():
                        shutil.copytree(
                            item,
                            staging_root / item.name,
                            dirs_exist_ok=True,
                            symlinks=False,
                            ignore_dangling_symlinks=True,
                        )
                    else:
                        shutil.copy2(
                            item, staging_root / item.name, follow_symlinks=False
                        )
                except Exception:
                    pass

            # Use unified installer to move the staged folder
            success = self.install_linked_mods([staging_root])
            if not success:
                return

        mods_dir = self.config_manager.get_mods_dir(self.game_page.game_name)
        dest_path = mods_dir / mod_name
        try:
            self.config_manager.add_folder_mod(
                self.game_page.game_name, mod_name, str(dest_path)
            )
            self.config_manager.set_mod_enabled(
                self.game_page.game_name, str(dest_path), True
            )
            self.game_page.status_label.setText(
                tr("install_bundled_mod_success_status", mod_name=mod_name)
            )
            self.game_page.load_mods()
        except Exception as e:
            QMessageBox.warning(
                self.game_page,
                tr("install_error_title"),
                tr("bundle_items_failed_msg", mod_name=mod_name, error=str(e)),
            )
