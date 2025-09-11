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
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
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
    progress_update = pyqtSignal(str, int, int)  # status, current, total
    finished_signal = pyqtSignal(int, list)  # installed_count, errors

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

        mods_dir = self.config_manager.get_mods_dir(self.game_page.game_name)
        parent = mods_dir.resolve()
        dest_folder_path = mods_dir / mod_name

        # Ensure destination is within mods directory
        if not self._safe_within(parent, dest_folder_path):
            QMessageBox.warning(
                self.game_page,
                tr("ERROR"),
                tr("invalid_destination_path_msg", name=mod_name),
            )
            return

        if dest_folder_path.exists():
            reply = QMessageBox.question(
                self.game_page,
                tr("confirm_overwrite_title"),
                tr("mod_folder_exists_overwrite_question", mod_name=mod_name),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                return

        with TemporaryDirectory(dir=str(parent)) as tmp_root_str:
            try:
                tmp_root = Path(tmp_root_str)
                tmp_dst = tmp_root / dest_folder_path.name
                shutil.copytree(
                    root_path, tmp_dst, symlinks=False, ignore_dangling_symlinks=True
                )

                # Atomic replace
                self._atomic_replace(tmp_dst, dest_folder_path)

                self.config_manager.add_folder_mod(
                    self.game_page.game_name, mod_name, str(dest_folder_path)
                )
                self.config_manager.set_mod_enabled(
                    self.game_page.game_name, str(dest_folder_path), True
                )
                self.game_page.status_label.setText(
                    tr("install_package_success_status", mod_name=mod_name)
                )
                # Refresh UI to reflect new mod
                self.game_page.load_mods()
            except Exception as e:
                QMessageBox.warning(
                    self.game_page,
                    tr("install_error_title"),
                    tr("create_folder_mod_failed_msg", mod_name=mod_name, error=str(e)),
                )

    def handle_profile_import(self, import_folder: Path, profile_file: Path):
        """
        Imports a profile and its mods, then cleans up the manager's copy of the profile.
        """
        try:
            with open(profile_file, "r", encoding="utf-8") as f:
                profile_data = tomlkit.parse(f.read())

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

            # Use the profile's filename as the installed mod's name.
            profile_mod_name = profile_file.stem
            mods_dir = self.config_manager.get_mods_dir(self.game_page.game_name)

            # Copy the .me3 file to the manager's internal profiles directory.
            profile_path = self.config_manager.get_profile_path(
                self.game_page.game_name
            )
            dest_profile_path = profile_path.parent / profile_file.name

            # Write profile atomically to prevent partial/corrupt files
            from me3_manager.core.profiles.toml_profile_writer import TomlProfileWriter

            with TemporaryDirectory(dir=str(profile_path.parent)) as tmp_root_str:
                tmp_root = Path(tmp_root_str)
                tmp_profile = tmp_root / profile_file.name
                TomlProfileWriter.write_profile(
                    tmp_profile, profile_data, self.game_page.game_name
                )
                if not merge_mode and dest_profile_path.exists():
                    dest_profile_path.unlink()
                self._atomic_replace(tmp_profile, dest_profile_path)

            # Get all top-level package folders with safe path validation
            package_paths = []
            for pkg in profile_data.get("packages", []):
                if isinstance(pkg, dict) and (pkg.get("source") or pkg.get("path")):
                    try:
                        pkg_path = Path(pkg.get("source") or pkg.get("path"))
                        # Validate path is safe
                        self._safe_join(import_folder, pkg_path)
                        package_paths.append(pkg_path)
                    except (ValueError, Exception):
                        continue  # Skip invalid paths

            # Get all individual native files with safe path validation
            native_paths = []
            for native in profile_data.get("natives", []):
                if isinstance(native, dict) and "path" in native:
                    try:
                        native_path = Path(native["path"])
                        # Validate path is safe
                        self._safe_join(import_folder, native_path)
                        native_paths.append(native_path)
                    except (ValueError, Exception):
                        continue  # Skip invalid paths

            # Build the final list of items to install, preventing nested duplicates.
            all_mod_paths = list(package_paths)
            for native_path in native_paths:
                if not any(p in native_path.parents for p in package_paths):
                    all_mod_paths.append(native_path)

            imported_mods, skipped_mods = [], []

            # Copy all necessary mod files and folders.
            for mod_path in all_mod_paths:
                try:
                    source_path = self._safe_join(import_folder, mod_path)
                except ValueError:
                    # Invalid path in profile - track as skipped
                    skipped_mods.append(str(mod_path))
                    continue

                if not source_path.exists() or _contains_symlink(source_path):
                    skipped_mods.append(str(mod_path))
                    continue

                # Rename main packages to the profile name; keep original names for loose files.
                final_mod_name = (
                    profile_mod_name if mod_path in package_paths else mod_path.name
                )

                # Validate and sanitize final mod name
                if not _validate_mod_name(final_mod_name):
                    skipped_mods.append(str(mod_path))
                    continue
                final_mod_name = Path(final_mod_name).name

                dest_path = mods_dir / final_mod_name
                parent = mods_dir.resolve()

                # Ensure destination is within mods directory
                if not self._safe_within(parent, dest_path):
                    skipped_mods.append(str(mod_path))
                    continue

                try:
                    with TemporaryDirectory(dir=str(parent)) as tmp_root_str:
                        tmp_root = Path(tmp_root_str)
                        tmp_dst = tmp_root / final_mod_name

                        if source_path.is_dir():
                            if merge_mode and dest_path.exists() and dest_path.is_dir():
                                # Seed with existing dest, then overlay source (merge)
                                shutil.copytree(
                                    dest_path,
                                    tmp_dst,
                                    symlinks=False,
                                    ignore_dangling_symlinks=True,
                                )
                                shutil.copytree(
                                    source_path,
                                    tmp_dst,
                                    symlinks=False,
                                    ignore_dangling_symlinks=True,
                                    dirs_exist_ok=True,
                                )
                            else:
                                shutil.copytree(
                                    source_path,
                                    tmp_dst,
                                    symlinks=False,
                                    ignore_dangling_symlinks=True,
                                )
                        else:
                            if (
                                merge_mode
                                and dest_path.exists()
                                and dest_path.is_file()
                            ):
                                # Overwrite existing file in a temp path to allow atomic replace
                                shutil.copy2(dest_path, tmp_dst, follow_symlinks=False)
                                shutil.copy2(
                                    source_path, tmp_dst, follow_symlinks=False
                                )
                            else:
                                shutil.copy2(
                                    source_path, tmp_dst, follow_symlinks=False
                                )

                        # Atomic replace
                        self._atomic_replace(tmp_dst, dest_path)

                    imported_mods.append(final_mod_name)

                    # Register the new mod.
                    self.config_manager.add_folder_mod(
                        self.game_page.game_name, final_mod_name, str(dest_path)
                    )
                    self.config_manager.set_mod_enabled(
                        self.game_page.game_name, str(dest_path), True
                    )
                except Exception:
                    skipped_mods.append(str(mod_path))

            # Show a summary of the import.
            completion_dialog = QDialog(self.game_page)
            completion_dialog.setWindowTitle(tr("import_complete_title"))
            completion_layout = QVBoxLayout()
            completion_layout.addWidget(QLabel(tr("import_complete_success_header")))
            if imported_mods:
                completion_layout.addWidget(
                    QLabel(tr("import_package_mods_success", count=len(imported_mods)))
                )
            if skipped_mods:
                completion_layout.addWidget(
                    QLabel(tr("import_mods_skipped_header", count=len(skipped_mods)))
                )

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

        mods_dir = self.config_manager.get_mods_dir(self.game_page.game_name)
        parent = mods_dir.resolve()
        dest_path = mods_dir / mod_name

        # Ensure destination is within mods directory
        if not self._safe_within(parent, dest_path):
            QMessageBox.warning(
                self.game_page,
                tr("ERROR"),
                tr("invalid_destination_path_msg", name=mod_name),
            )
            return

        if dest_path.exists():
            reply = QMessageBox.question(
                self.game_page,
                tr("mod_exists_title"),
                tr("mod_folder_exists_replace_question", mod_name=mod_name),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                return

        with TemporaryDirectory(dir=str(parent)) as tmp_root_str:
            try:
                tmp_root = Path(tmp_root_str)
                tmp_dst = tmp_root / mod_name
                tmp_dst.mkdir(parents=True, exist_ok=True)

                for item in items_to_install:
                    if item.is_dir():
                        shutil.copytree(
                            item,
                            tmp_dst / item.name,
                            dirs_exist_ok=True,
                            symlinks=False,
                            ignore_dangling_symlinks=True,
                        )
                    else:
                        shutil.copy2(item, tmp_dst / item.name, follow_symlinks=False)

                # Atomic replace
                self._atomic_replace(tmp_dst, dest_path)

                self.config_manager.add_folder_mod(
                    self.game_page.game_name, mod_name, str(dest_path)
                )
                self.config_manager.set_mod_enabled(
                    self.game_page.game_name, str(dest_path), True
                )
                self.game_page.status_label.setText(
                    tr("install_bundled_mod_success_status", mod_name=mod_name)
                )
                # Refresh UI
                self.game_page.load_mods()
            except Exception as e:
                QMessageBox.warning(
                    self.game_page,
                    tr("install_error_title"),
                    tr("bundle_items_failed_msg", mod_name=mod_name, error=str(e)),
                )
