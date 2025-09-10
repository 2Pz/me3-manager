"""
Mod Installation Handler for GamePage.

Handles the logic for installing mods from various sources, including loose files,
packaged folders, and imported profiles (.me3 files). Manages file operations and
user dialogs for naming and overwriting mods.
"""

import shutil
from pathlib import Path
from typing import TYPE_CHECKING, List

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QInputDialog, QMessageBox

from me3_manager.utils.translator import tr

if TYPE_CHECKING:
    from me3_manager.ui.game_page_components import GamePage


class ModInstaller:
    def __init__(self, game_page: "GamePage"):
        self.game_page = game_page
        self.config_manager = game_page.config_manager

    def install_linked_mods(self, items_to_install: List[Path]) -> bool:
        """
        Installs a list of items (DLLs and their associated config folders) directly
        into the mods directory without bundling them.
        """

        mods_dir = self.config_manager.get_mods_dir(self.game_page.game_name)
        conflicts = [p for p in items_to_install if (mods_dir / p.name).exists()]

        if conflicts:
            conflict_msg = tr("overwrite_confirm_text") + "\n".join(
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

        installed_count = 0
        errors = []
        for item_path in items_to_install:
            try:
                dest_path = mods_dir / item_path.name
                if item_path.is_dir():
                    if dest_path.exists():
                        shutil.rmtree(dest_path)
                    shutil.copytree(item_path, dest_path)
                else:  # is_file
                    shutil.copy2(item_path, dest_path)
                installed_count += 1
            except Exception as e:
                errors.append(f"Failed to copy {item_path.name}: {e}")

        if errors:
            QMessageBox.warning(
                self.game_page, tr("install_error_title"), "\n".join(errors)
            )

        if installed_count > 0:
            self.game_page.status_label.setText(
                tr("install_success_status", count=installed_count)
            )
            return True
        return False

    def handle_profile_import(self, import_folder: Path, profile_file: Path):
        msg_box = QMessageBox(self.game_page)

        msg_box.setWindowTitle(
            tr("import_profile_mods_title", game_name=self.game_page.game_name)
        )
        msg_box.setTextFormat(Qt.TextFormat.RichText)
        msg_box.setText(
            f"""{tr("import_profile_mods_desc")}<br><br>
            <b>{tr("profile_label")}:</b> {profile_file.name}<br>
            <b>{tr("from_folder_label")}:</b> {import_folder}<br><br>
            {tr("import_merge_or_replace_question")}"""
        )
        msg_box.setStandardButtons(
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No
            | QMessageBox.StandardButton.Cancel
        )
        merge_btn = msg_box.button(QMessageBox.StandardButton.Yes)
        merge_btn.setText(tr("merge_button_recommended"))
        replace_btn = msg_box.button(QMessageBox.StandardButton.No)
        replace_btn.setText(tr("replace_button"))

        reply = msg_box.exec()
        if reply == QMessageBox.StandardButton.Cancel:
            return
        merge = reply == QMessageBox.StandardButton.Yes

        default_name = import_folder.name
        mod_name, ok = QInputDialog.getText(
            self.game_page,
            tr("name_imported_package_title"),
            tr("name_imported_package_desc")
            + tr("importing_from_label", folder=import_folder.name),
            text=default_name,
        )
        if not ok or not mod_name.strip():
            self.game_page.status_label.setText(tr("import_cancelled_status"))
            QTimer.singleShot(
                2000, lambda: self.game_page.status_label.setText(tr("status_ready"))
            )
            return
        mod_name = mod_name.strip()

        try:
            self.game_page.status_label.setText(
                tr("importing_from_status", folder=import_folder.name)
            )
            config_data = self.config_manager._parse_toml_config(profile_file)
            packages = config_data.get("packages", [])

            results = {
                "success": True,
                "profile_imported": False,
                "package_mods_imported": 0,
                "dll_mods_imported": 0,
                "mods_skipped": 0,
                "skipped_details": [],
                "errors": [],
            }

            mods_dir = self.config_manager.get_mods_dir(self.game_page.game_name)

            for package in packages:
                package_id = package.get("id", "")
                package_path = package.get("path", "")
                package_source = package.get("source", "")
                search_name = package_path or package_source or package_id
                if not package_id or not search_name:
                    continue

                mod_source_path = None
                possible_paths = [
                    import_folder / search_name,
                    import_folder / package_id,
                    import_folder / "Mod",
                    import_folder / "mod",
                ]
                for possible_path in possible_paths:
                    if possible_path.exists() and possible_path.is_dir():
                        mod_source_path = possible_path
                        break
                if not mod_source_path:
                    for item in import_folder.iterdir():
                        if (
                            item.is_dir()
                            and item.name != profile_file.stem
                            and self.game_page._is_valid_mod_folder(item)
                        ):
                            mod_source_path = item
                            break
                if not mod_source_path:
                    results["errors"].append(
                        f"Could not find mod folder for package '{package_id}' (searched for: {search_name})"
                    )
                    continue

                dest_mod_path = mods_dir / mod_name
                if dest_mod_path.exists():
                    if not merge:
                        reply = QMessageBox.question(
                            self.game_page,
                            tr("mod_exists_title"),
                            tr("mod_folder_exists_replace_question", mod_name=mod_name),
                            QMessageBox.StandardButton.Yes
                            | QMessageBox.StandardButton.No,
                        )
                        if reply == QMessageBox.StandardButton.No:
                            results["mods_skipped"] += 1
                            results["skipped_details"].append(
                                tr("skipped_reason_exists", name=mod_name)
                            )
                            continue
                        else:
                            shutil.rmtree(dest_mod_path)
                try:
                    if dest_mod_path.exists():
                        for item in mod_source_path.iterdir():
                            dest_item = dest_mod_path / item.name
                            if item.is_dir():
                                if dest_item.exists():
                                    shutil.rmtree(dest_item)
                                shutil.copytree(item, dest_item)
                            else:
                                shutil.copy2(item, dest_item)
                    else:
                        shutil.copytree(mod_source_path, dest_mod_path)

                    self.config_manager.add_folder_mod(
                        self.game_page.game_name, mod_name, str(dest_mod_path)
                    )
                    self.config_manager.set_mod_enabled(
                        self.game_page.game_name, str(dest_mod_path), True
                    )
                    results["package_mods_imported"] += 1
                except Exception as e:
                    results["errors"].append(
                        f"Failed to copy mod '{mod_name}': {str(e)}"
                    )

            natives = config_data.get("natives", [])
            for native in natives:
                native_path = native.get("path", "")
                if not native_path:
                    continue
                native_path_obj = Path(native_path)
                possible_dll_paths = []
                if mod_source_path:
                    for search_pattern in [native_path, native_path_obj.name]:
                        potential_dll = mod_source_path / search_pattern
                        if potential_dll.exists():
                            possible_dll_paths.append(potential_dll)
                            break
                    dll_name = native_path_obj.name
                    for dll_file in mod_source_path.rglob(dll_name):
                        if dll_file.is_file():
                            possible_dll_paths.append(dll_file)
                            break
                if possible_dll_paths:
                    results["dll_mods_imported"] += 1

            try:
                profile_path = self.config_manager.get_profile_path(
                    self.game_page.game_name
                )
                imported_config = self.config_manager._parse_toml_config(profile_file)
                if not merge:
                    updated_packages = []

                    main_mods_dir = self.config_manager.games[self.game_page.game_name][
                        "mods_dir"
                    ]
                    updated_packages.append(
                        {
                            "id": main_mods_dir,
                            "path": main_mods_dir,
                            "load_after": [],
                            "load_before": [],
                        }
                    )
                    if results["package_mods_imported"] > 0:
                        updated_packages.append(
                            {
                                "id": mod_name,
                                "path": f"{main_mods_dir}/{mod_name}",
                                "load_after": [],
                                "load_before": [],
                            }
                        )
                    updated_natives = []
                    natives = imported_config.get("natives", [])
                    for native in natives:
                        native_path = native.get("path", "")
                        if not native_path:
                            continue
                        if results["package_mods_imported"] > 0:
                            new_native_path = (
                                f"{main_mods_dir}/{mod_name}/{native_path}"
                            )
                            new_native = native.copy()
                            new_native["path"] = new_native_path
                            updated_natives.append(new_native)
                    imported_config["natives"] = updated_natives

                    self.game_page.mod_manager._write_improved_config(
                        profile_path, imported_config, self.game_page.game_name
                    )
                results["profile_imported"] = True
            except Exception as e:
                results["errors"].append(f"Failed to import profile: {str(e)}")

            if results["success"] and (
                results["profile_imported"] or results["package_mods_imported"] > 0
            ):
                message_parts = [f"<b>{tr('import_complete_success_header')}</b>"]
                if results["profile_imported"]:
                    message_parts.append(tr("import_profile_success"))
                if results["package_mods_imported"] > 0:
                    message_parts.append(
                        tr(
                            "import_package_mods_success",
                            count=results["package_mods_imported"],
                        )
                    )
                if results["dll_mods_imported"] > 0:
                    message_parts.append(
                        tr(
                            "import_dll_mods_success",
                            count=results["dll_mods_imported"],
                        )
                    )
                if results["mods_skipped"] > 0:
                    skipped_header = f"<b>{tr('import_mods_skipped_header', count=results['mods_skipped'])}</b>"
                    skipped_details = [
                        f"• <i>{detail}</i>"
                        for detail in results.get("skipped_details", [])
                    ]
                    message_parts.append(
                        f"{skipped_header}<br>" + "<br>".join(skipped_details)
                    )
                if results["errors"]:
                    error_header = f"<b>{tr('import_errors_header')}</b>"
                    error_details = [
                        f"• {error}" for error in results.get("errors", [])
                    ]
                    message_parts.append(
                        f"{error_header}<br>" + "<br>".join(error_details)
                    )

                message = "<br>".join(message_parts)
                msg_box = QMessageBox(self.game_page)
                msg_box.setWindowTitle(tr("import_complete_title"))
                msg_box.setTextFormat(Qt.TextFormat.RichText)
                msg_box.setText(message)
                msg_box.exec()
                self.game_page.load_mods()
            else:
                error_msg = f"<b>{tr('import_failed_header')}</b><br>".join(
                    f"• {error}" for error in results["errors"]
                )
                QMessageBox.warning(
                    self.game_page, tr("import_failed_title"), error_msg
                )

        except Exception as e:
            QMessageBox.warning(
                self.game_page,
                tr("import_error_title"),
                tr("import_error_msg", error=str(e)),
            )
        finally:
            self.game_page.status_label.setText(tr("status_ready"))

    def install_root_mod_package(self, root_path: Path):
        mod_name, ok = QInputDialog.getText(
            self.game_page,
            tr("name_mod_package_title"),
            tr("name_mod_package_desc"),
            text=root_path.name,
        )
        if not ok or not mod_name.strip():
            return
        mod_name = mod_name.strip()

        mods_dir = self.config_manager.get_mods_dir(self.game_page.game_name)
        dest_folder_path = mods_dir / mod_name

        if dest_folder_path.exists():
            reply = QMessageBox.question(
                self.game_page,
                tr("confirm_overwrite_title"),
                tr("mod_folder_exists_overwrite_question", mod_name=mod_name),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                return
            shutil.rmtree(dest_folder_path)

        try:
            shutil.copytree(root_path, dest_folder_path)

            self.config_manager.add_folder_mod(
                self.game_page.game_name, mod_name, str(dest_folder_path)
            )
            self.config_manager.set_mod_enabled(
                self.game_page.game_name, str(dest_folder_path), True
            )
            self.game_page.status_label.setText(
                tr("install_package_success_status", mod_name=mod_name)
            )
        except Exception as e:
            QMessageBox.warning(
                self.game_page,
                tr("install_error_title"),
                tr("create_folder_mod_failed_msg", mod_name=mod_name, error=e),
            )
            if dest_folder_path.exists():
                shutil.rmtree(dest_folder_path)

    def install_loose_items(self, items_to_install: List[Path]):
        if not items_to_install:
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

        mods_dir = self.config_manager.get_mods_dir(self.game_page.game_name)
        dest_path = mods_dir / mod_name

        if dest_path.exists():
            reply = QMessageBox.question(
                self.game_page,
                tr("mod_exists_title"),
                tr("mod_folder_exists_replace_question", mod_name=mod_name),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                return
            shutil.rmtree(dest_path)

        dest_path.mkdir(parents=True, exist_ok=True)
        try:
            for item in items_to_install:
                if item.is_dir():
                    shutil.copytree(item, dest_path / item.name, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, dest_path / item.name)

            self.config_manager.add_folder_mod(
                self.game_page.game_name, mod_name, str(dest_path)
            )
            self.config_manager.set_mod_enabled(
                self.game_page.game_name, str(dest_path), True
            )
            self.game_page.status_label.setText(
                tr("install_bundled_mod_success_status", mod_name=mod_name)
            )
        except Exception as e:
            QMessageBox.warning(
                self.game_page,
                tr("install_error_title"),
                tr("bundle_items_failed_msg", mod_name=mod_name, error=e),
            )
            if dest_path.exists():
                shutil.rmtree(dest_path)
