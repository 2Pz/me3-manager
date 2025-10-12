"""
User Profile Management Handler for GamePage.

Manages all UI and logic related to user profiles, including updating the profile
selection dropdown menu and operating the comprehensive "Manage Profiles" dialog.
"""

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction, QActionGroup, QIcon
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from me3_manager.utils.resource_path import resource_path
from me3_manager.utils.translator import tr

if TYPE_CHECKING:
    from ..game_page import GamePage


class ProfileHandler:
    """Handles profile selection dropdown and the profile management dialog."""

    def __init__(self, game_page: "GamePage"):
        self.game_page = game_page
        self.config_manager = game_page.config_manager
        self.game_name = game_page.game_name
        self.profile_action_group: QActionGroup | None = None

    def update_profile_dropdown(self):
        """Updates the profile dropdown button text and its menu items."""
        active_profile = self.config_manager.get_active_profile(self.game_name)
        if not active_profile:
            return
        gp = self.game_page
        gp.profile_menu_button.setText(active_profile["name"])
        gp.profile_menu.clear()
        # Create an exclusive action group for profiles
        self.profile_action_group = QActionGroup(gp)
        self.profile_action_group.setExclusive(True)
        self.profile_action_group.triggered.connect(self.on_profile_action_triggered)
        all_profiles = self.config_manager.get_profiles_for_game(self.game_name)
        active_profile_id = active_profile["id"]
        for profile in all_profiles:
            action = QAction(profile["name"], gp)
            action.setData(profile["id"])
            action.setCheckable(True)
            action.setChecked(profile["id"] == active_profile_id)
            self.profile_action_group.addAction(action)
            gp.profile_menu.addAction(action)
        gp.profile_menu.addSeparator()
        manage_action = QAction(
            QIcon(resource_path("resources/icon/profiles.svg")),
            tr("manage_profiles"),
            gp,
        )
        manage_action.triggered.connect(self.open_profile_manager)
        gp.profile_menu.addAction(manage_action)

    def on_profile_action_triggered(self, action: QAction):
        """Handles when a profile is chosen from the dropdown menu."""
        if isinstance(action, QAction):
            profile_id = action.data()
            self.config_manager.set_active_profile(self.game_name, profile_id)
            self.game_page.load_mods()
            self.update_profile_dropdown()

    def open_profile_manager(self, checked: bool = False):
        """Creates and shows the 'Manage Profiles' dialog."""
        dialog = QDialog(self.game_page)
        dialog.setWindowTitle(tr("manage_profiles_title", game_name=self.game_name))
        dialog.setModal(True)
        dialog.resize(600, 400)

        layout = QHBoxLayout(dialog)
        layout.setSpacing(15)

        left_layout = QVBoxLayout()
        search_bar = QLineEdit()
        search_bar.setPlaceholderText(tr("search_profiles_placeholder"))
        search_bar.setStyleSheet("""
            QLineEdit {
                background-color: #252525; border: 1px solid #3d3d3d; border-radius: 6px;
                padding: 8px; font-size: 13px; color: #ffffff;
            }
            QLineEdit:focus { border-color: #0078d4; }
        """)
        left_layout.addWidget(search_bar)

        list_widget = QListWidget()
        list_widget.setStyleSheet("""
            QListWidget {
                background-color: #252525; border: 1px solid #3d3d3d; border-radius: 6px;
                font-size: 14px; outline: 0;
            }
            QListWidget::item { padding: 8px 12px; border-bottom: 1px solid #333333; }
            QListWidget::item:selected { background-color: #0078d4; color: white; border-bottom: 1px solid #005a9e; }
            QListWidget::item:hover { background-color: #3d3d3d; }
        """)
        left_layout.addWidget(list_widget)
        layout.addLayout(left_layout, 2)

        button_layout = QVBoxLayout()
        button_layout.setSpacing(10)
        button_style = """
            QPushButton {
                background-color: #3d3d3d; color: white; border: none; border-radius: 6px;
                padding: 10px; text-align: left; font-size: 13px;
            }
            QPushButton:hover { background-color: #4d4d4d; }
            QPushButton:pressed { background-color: #2d2d2d; }
            QPushButton:disabled { background-color: #252525; color: #666; }
        """
        activate_btn = QPushButton(
            QIcon(resource_path("resources/icon/activate.svg")), tr("activate_button")
        )
        add_btn = QPushButton(
            QIcon(resource_path("resources/icon/add.svg")), tr("add_new_button")
        )
        rename_btn = QPushButton(
            QIcon(resource_path("resources/icon/edit.svg")), tr("rename_button")
        )
        delete_btn = QPushButton(
            QIcon(resource_path("resources/icon/delete.svg")), tr("delete_button")
        )

        for btn in [activate_btn, add_btn, rename_btn, delete_btn]:
            btn.setStyleSheet(button_style)
            btn.setIconSize(QSize(20, 20))

        button_layout.addWidget(activate_btn)
        button_layout.addWidget(add_btn)
        button_layout.addWidget(rename_btn)
        button_layout.addWidget(delete_btn)
        button_layout.addStretch()
        layout.addLayout(button_layout, 1)

        def refresh_list():
            list_widget.clear()
            search_text = search_bar.text().lower()
            active_id = self.config_manager.active_profiles.get(self.game_name)
            profiles = self.config_manager.get_profiles_for_game(self.game_name)
            for profile in profiles:
                if search_text not in profile["name"].lower():
                    continue
                item = QListWidgetItem()
                item.setText(profile["name"])
                item.setData(Qt.ItemDataRole.UserRole, profile["id"])
                if profile["id"] == active_id:
                    item.setIcon(QIcon(resource_path("resources/icon/active.png")))
                list_widget.addItem(item)
            update_button_states()

        def update_button_states():
            selected_item = list_widget.currentItem()
            has_selection = selected_item is not None
            activate_btn.setEnabled(has_selection)
            rename_btn.setEnabled(has_selection)
            delete_btn.setEnabled(has_selection)
            if has_selection:
                profile_id = selected_item.data(Qt.ItemDataRole.UserRole)
                is_active = profile_id == self.config_manager.active_profiles.get(
                    self.game_name
                )
                is_default = profile_id == "default"
                activate_btn.setEnabled(not is_active)
                rename_btn.setEnabled(not is_default)
                delete_btn.setEnabled(not is_default)

        def on_activate():
            selected_item = list_widget.currentItem()
            if not selected_item:
                return
            profile_id = selected_item.data(Qt.ItemDataRole.UserRole)
            self.config_manager.set_active_profile(self.game_name, profile_id)
            refresh_list()
            self.game_page.load_mods()

        def on_add():
            name, ok = QInputDialog.getText(
                dialog, tr("new_profile_name_title"), tr("new_profile_name_desc")
            )
            if ok and name.strip():
                # Get the default directory to start the file dialog in
                default_profiles_dir = (
                    Path(self.config_manager.get_profile_path(self.game_name))
                    .expanduser()
                    .parent
                )
                default_profiles_dir.mkdir(parents=True, exist_ok=True)

                profile_dir_str = QFileDialog.getExistingDirectory(
                    dialog,
                    tr("select_folder_for_profile_title"),
                    str(default_profiles_dir),
                )

                if profile_dir_str:
                    selected_path = Path(profile_dir_str).resolve()

                    all_profiles = self.config_manager.get_profiles_for_game(
                        self.game_name
                    )
                    # Build a set of existing mod directories, skipping any invalid/None entries
                    existing_mod_paths = set()
                    for p in all_profiles:
                        raw_mods_path = p.get("mods_path")
                        if isinstance(raw_mods_path, str) and raw_mods_path.strip():
                            try:
                                existing_mod_paths.add(Path(raw_mods_path).resolve())
                            except Exception:
                                # Skip malformed paths silently
                                pass

                    if selected_path in existing_mod_paths:
                        QMessageBox.warning(
                            dialog,
                            tr("folder_in_use_title"),
                            tr("folder_in_use_desc", folder_name=selected_path.name),
                        )
                        return  # Abort the operation

                    # Step 4: If the path is not in use, proceed with creating the profile.
                    try:
                        new_id = self.config_manager.add_profile(
                            self.game_name, name.strip(), profile_dir_str
                        )
                    except Exception as e:
                        QMessageBox.critical(
                            dialog,
                            tr("ERROR"),
                            tr("could_not_perform_action", e=str(e)),
                        )
                        return

                    if not new_id:
                        QMessageBox.warning(
                            dialog,
                            tr("validation_error"),
                            tr(
                                "could_not_perform_action",
                                e=tr("create_error_msg"),
                            ),
                        )
                        return

                    refresh_list()
                else:
                    QMessageBox.information(
                        dialog,
                        tr("validation_error"),
                        tr("no_folder_selected_msg"),
                    )

        def on_rename():
            selected_item = list_widget.currentItem()
            if not selected_item:
                return
            profile = next(
                p
                for p in self.config_manager.get_profiles_for_game(self.game_name)
                if p["id"] == selected_item.data(Qt.ItemDataRole.UserRole)
            )
            new_name, ok = QInputDialog.getText(
                dialog,
                tr("rename_profile_title"),
                tr("enter_new_name_desc"),
                text=profile["name"],
            )
            if ok and new_name.strip():
                self.config_manager.update_profile(
                    self.game_name, profile["id"], new_name.strip()
                )
                refresh_list()
                self.update_profile_dropdown()

        def on_delete():
            selected_item = list_widget.currentItem()
            if not selected_item:
                return
            reply = QMessageBox.question(
                dialog,
                tr("confirm_delete_title"),
                tr(
                    "delete_profile_confirm_question", profile_name=selected_item.text()
                ),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                profile_id = selected_item.data(Qt.ItemDataRole.UserRole)
                self.config_manager.delete_profile(self.game_name, profile_id)
                refresh_list()
                self.game_page.load_mods()

        search_bar.textChanged.connect(refresh_list)
        list_widget.currentItemChanged.connect(update_button_states)
        activate_btn.clicked.connect(on_activate)
        add_btn.clicked.connect(on_add)
        rename_btn.clicked.connect(on_rename)
        delete_btn.clicked.connect(on_delete)

        refresh_list()
        dialog.exec()
        self.update_profile_dropdown()
