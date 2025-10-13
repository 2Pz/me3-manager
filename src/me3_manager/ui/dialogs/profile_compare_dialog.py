from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from me3_manager.utils.translator import tr


class ProfileCompareDialog(QDialog):
    """Side-by-side comparison of two profiles for a game."""

    def __init__(self, game_name: str, config_manager, parent=None):
        super().__init__(parent)
        self.game_name = game_name
        self.config_manager = config_manager
        self.setWindowTitle(tr("profile_compare_title", game_name=game_name))
        self.setMinimumSize(900, 550)
        self.setStyleSheet(
            """
            QDialog { background-color: #1e1e1e; color: #ffffff; }
            QLabel { background-color: transparent; }
            QListWidget { background-color: #252525; border: 1px solid #3d3d3d; border-radius: 6px; }
            QGroupBox { border: 1px solid #3d3d3d; border-radius: 6px; margin-top: 12px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
            QPushButton { background-color: #2d2d2d; border: 1px solid #3d3d3d; padding: 8px 14px; border-radius: 6px; }
            QPushButton:hover { background-color: #3d3d3d; }
            #DiffAdded { color: #6CC04A; }
            #DiffRemoved { color: #E05D5D; }
            #Header { font-weight: bold; }
            QFrame#line { background-color: #3d3d3d; }
            """
        )

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(14, 14, 14, 14)
        root_layout.setSpacing(10)

        header = QLabel(tr("profile_compare_header"))
        header.setObjectName("Header")
        root_layout.addWidget(header)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        # Left profile selection and contents
        self.left_box = self._build_profile_panel(side="left")
        # Right profile selection and contents
        self.right_box = self._build_profile_panel(side="right")

        splitter.addWidget(self.left_box)
        splitter.addWidget(self.right_box)
        splitter.setSizes([450, 450])
        root_layout.addWidget(splitter)

        # Differences summary
        self.diff_group = QGroupBox(tr("profile_compare_differences"))
        diff_layout = QGridLayout(self.diff_group)
        self.added_label = QLabel(tr("profile_compare_added", count=0))
        self.added_label.setObjectName("DiffAdded")
        self.removed_label = QLabel(tr("profile_compare_removed", count=0))
        self.removed_label.setObjectName("DiffRemoved")
        diff_layout.addWidget(self.added_label, 0, 0)
        diff_layout.addWidget(self.removed_label, 0, 1)
        root_layout.addWidget(self.diff_group)

        # Bottom buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()
        close_btn = QPushButton(tr("close_button"))
        close_btn.clicked.connect(self.accept)
        buttons_layout.addWidget(close_btn)
        root_layout.addLayout(buttons_layout)

        # Initialize selection to active profile on the left
        self._populate_profiles()
        self._load_selected_profiles()

    def _build_profile_panel(self, side: str) -> QWidget:
        container = QWidget()
        v = QVBoxLayout(container)
        v.setSpacing(8)

        title = QLabel(
            tr(
                "profile_compare_side_title",
                side=tr("left") if side == "left" else tr("right"),
            )
        )
        v.addWidget(title)

        self.__dict__[f"{side}_profiles"] = QListWidget()
        self.__dict__[f"{side}_profiles"].currentItemChanged.connect(
            self._load_selected_profiles
        )
        v.addWidget(self.__dict__[f"{side}_profiles"])

        group = QGroupBox(tr("profile_compare_contents"))
        grid = QGridLayout(group)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)

        # Natives and Packages lists
        self.__dict__[f"{side}_natives_list"] = QListWidget()
        self.__dict__[f"{side}_packages_list"] = QListWidget()
        grid.addWidget(QLabel(tr("profile_compare_natives")), 0, 0)
        grid.addWidget(QLabel(tr("profile_compare_packages")), 0, 1)
        grid.addWidget(self.__dict__[f"{side}_natives_list"], 1, 0)
        grid.addWidget(self.__dict__[f"{side}_packages_list"], 1, 1)

        v.addWidget(group)
        return container

    def _populate_profiles(self):
        profiles = self.config_manager.get_profiles_for_game(self.game_name)
        active = self.config_manager.get_active_profile(self.game_name)
        left_widget: QListWidget = self.left_profiles
        right_widget: QListWidget = self.right_profiles
        left_widget.clear()
        right_widget.clear()
        for p in profiles:
            item_left = QListWidgetItem(p.get("name", ""))
            item_left.setData(Qt.ItemDataRole.UserRole, p.get("id"))
            left_widget.addItem(item_left)

            item_right = QListWidgetItem(p.get("name", ""))
            item_right.setData(Qt.ItemDataRole.UserRole, p.get("id"))
            right_widget.addItem(item_right)

        # Preselect active on left, first different on right
        if active:
            for i in range(left_widget.count()):
                if left_widget.item(i).data(Qt.ItemDataRole.UserRole) == active.get(
                    "id"
                ):
                    left_widget.setCurrentRow(i)
                    break
        if right_widget.count() > 0:
            # Choose a different profile if available
            right_row = 0
            if active:
                for i in range(right_widget.count()):
                    if right_widget.item(i).data(
                        Qt.ItemDataRole.UserRole
                    ) != active.get("id"):
                        right_row = i
                        break
            right_widget.setCurrentRow(right_row)

    def _read_profile(self, profile_id: str) -> dict[str, Any]:
        # Find profile path and read TOML via ProfileManager through facade
        for p in self.config_manager.get_profiles_for_game(self.game_name):
            if p.get("id") == profile_id:
                path = Path(p.get("profile_path", ""))
                try:
                    return self.config_manager._parse_toml_config(path)
                except Exception:
                    return {"natives": [], "packages": []}
        return {"natives": [], "packages": []}

    def _load_selected_profiles(self):
        left_item = self.left_profiles.currentItem()
        right_item = self.right_profiles.currentItem()
        if not left_item or not right_item:
            return
        left_id = left_item.data(Qt.ItemDataRole.UserRole)
        right_id = right_item.data(Qt.ItemDataRole.UserRole)

        left_data = self._read_profile(left_id)
        right_data = self._read_profile(right_id)

        def extract_lists(data: dict[str, Any]):
            natives = []
            for n in data.get("natives", []) or []:
                if isinstance(n, dict):
                    path_str = n.get("path") or ""
                    if path_str:
                        # Extract just the filename from the path
                        natives.append(Path(path_str).name)
            packages = []
            for p in data.get("packages", []) or []:
                if isinstance(p, dict):
                    pid = p.get("id")
                    if pid:
                        packages.append(pid)
            return set(natives), set(packages)

        l_natives, l_packages = extract_lists(left_data)
        r_natives, r_packages = extract_lists(right_data)

        # Populate UI lists
        self._fill_list(self.left_natives_list, l_natives)
        self._fill_list(self.left_packages_list, l_packages)
        self._fill_list(self.right_natives_list, r_natives)
        self._fill_list(self.right_packages_list, r_packages)

        # Differences summary
        added = len(r_natives - l_natives) + len(r_packages - l_packages)
        removed = len(l_natives - r_natives) + len(l_packages - r_packages)
        self.added_label.setText(tr("profile_compare_added", count=added))
        self.removed_label.setText(tr("profile_compare_removed", count=removed))

    def _fill_list(self, widget: QListWidget, items: set[str]):
        widget.clear()
        for s in sorted(items):
            widget.addItem(QListWidgetItem(s))
