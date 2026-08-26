"""
Conflict Inspector Dialog for ME3 Manager.
Provides a spacious, clean, single-view table with category filtering and interactive mod badges.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QColor, QFont
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from me3_manager.core.conflict_scanner import (
    ConflictScannerService,
    ConflictScanResult,
    FileConflict,
)
from me3_manager.ui.dialogs.dialog_utils import StyleUtils
from me3_manager.utils.platform_utils import PlatformUtils
from me3_manager.utils.translator import tr

if TYPE_CHECKING:
    from me3_manager.core.config_facade import ConfigFacade

log = logging.getLogger(__name__)


class ConflictInspectorDialog(QDialog):
    """
    Spacious, visual dialog for inspecting file conflicts between mods.
    Displays clear, clickable mod badges for each conflicting mod with generous layout space.
    """

    def __init__(
        self,
        game_name: str,
        config_manager: ConfigFacade,
        mod_infos: dict[str, Any] | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.game_name = game_name
        self.config_manager = config_manager
        self.mod_infos = mod_infos or {}
        self.scanner_service = ConflictScannerService()

        self.scan_result: ConflictScanResult | None = None
        self.current_category = "all"
        self.current_search = ""
        self.filtered_conflicts: list[FileConflict] = []
        self.cat_buttons: dict[str, QPushButton] = {}

        self.setWindowTitle(tr("conflict_inspector_title", game_name=game_name))
        self.resize(1120, 680)
        self.setMinimumSize(920, 500)
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e1e;
                color: #ffffff;
            }
            QLabel {
                background-color: transparent;
                color: #ffffff;
            }
        """)

        self.init_ui()
        self.run_scan()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(14)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # 1. Header Section
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(12)

        icon_label = QLabel("⚠️")
        icon_label.setStyleSheet("font-size: 24px; color: #ffaa00;")
        header_layout.addWidget(icon_label)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)

        title_lbl = QLabel(tr("conflict_inspector_heading"))
        title_lbl.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title_lbl.setStyleSheet("color: #ffffff;")
        title_col.addWidget(title_lbl)

        desc_lbl = QLabel(tr("conflict_inspector_desc"))
        desc_lbl.setStyleSheet("color: #9e9e9e; font-size: 12px;")
        title_col.addWidget(desc_lbl)

        header_layout.addLayout(title_col, 1)

        self.rescan_btn = QPushButton(f"🔄 {tr('conflict_rescan_btn')}")
        self.rescan_btn.setStyleSheet(StyleUtils.get_button_style())
        self.rescan_btn.clicked.connect(self.run_scan)
        header_layout.addWidget(self.rescan_btn)

        main_layout.addWidget(header_widget)

        # 2. Search Filter
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(tr("conflict_filter_placeholder"))
        self.search_edit.setStyleSheet(StyleUtils.get_lineedit_style())
        self.search_edit.textChanged.connect(self.on_search_changed)
        main_layout.addWidget(self.search_edit)

        # 3. Category Filter Buttons (Scrollable horizontally)
        self.category_scroll = QScrollArea()
        self.category_scroll.setWidgetResizable(True)
        self.category_scroll.setFixedHeight(42)
        self.category_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.category_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.category_scroll.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
        """)

        self.category_widget = QWidget()
        self.category_widget.setStyleSheet("background: transparent;")
        self.category_bar = QHBoxLayout(self.category_widget)
        self.category_bar.setContentsMargins(0, 0, 0, 0)
        self.category_bar.setSpacing(8)
        self.category_scroll.setWidget(self.category_widget)

        main_layout.addWidget(self.category_scroll)

        # 4. Main Conflict Table
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(
            [
                tr("category"),
                tr("file"),
                tr("conflicting_mods"),
            ]
        )
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Interactive
        )
        self.table.horizontalHeader().resizeSection(1, 380)
        self.table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(40)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #252525;
                border: 1px solid #3d3d3d;
                border-radius: 6px;
                color: #ffffff;
                gridline-color: #2e2e2e;
                outline: none;
            }
            QTableWidget::item {
                padding: 4px 8px;
                border-bottom: 1px solid #2a2a2a;
            }
            QTableWidget::item:selected {
                background-color: #0078d4;
                color: #ffffff;
            }
            QHeaderView::section {
                background-color: #2d2d2d;
                color: #b0b0b0;
                padding: 8px;
                border: none;
                border-bottom: 2px solid #3d3d3d;
                font-weight: bold;
                font-size: 12px;
            }
        """)
        main_layout.addWidget(self.table, 1)

        # 5. Empty State Label
        self.empty_label = QLabel()
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setStyleSheet(
            "color: #888888; font-size: 14px; padding: 40px;"
        )
        self.empty_label.setVisible(False)
        main_layout.addWidget(self.empty_label)

        # 6. Bottom Bar
        bottom_bar = QHBoxLayout()
        self.summary_label = QLabel("")
        self.summary_label.setStyleSheet("color: #aaaaaa; font-size: 12px;")
        bottom_bar.addWidget(self.summary_label)
        bottom_bar.addStretch()

        close_btn = QPushButton(tr("close_button"))
        close_btn.setStyleSheet(StyleUtils.get_button_style())
        close_btn.clicked.connect(self.accept)
        bottom_bar.addWidget(close_btn)

        main_layout.addLayout(bottom_bar)

    def run_scan(self):
        """Scans enabled mods and populates the conflict table."""
        self.scan_result = self.scanner_service.scan_game_profile(
            self.game_name, self.config_manager, self.mod_infos
        )
        self.update_category_buttons()
        self.populate_table()

    def update_category_buttons(self):
        """Build category filter buttons dynamically based on scan results."""
        for btn in self.cat_buttons.values():
            self.category_bar.removeWidget(btn)
            btn.deleteLater()
        self.cat_buttons.clear()

        if not self.scan_result or not self.scan_result.has_conflicts:
            self.category_scroll.setVisible(False)
            return

        self.category_scroll.setVisible(True)

        categories = [
            ("all", tr("conflict_cat_all", count=self.scan_result.total_conflicts))
        ]
        for cat_key, conflict_list in self.scan_result.conflicts_by_category.items():
            if conflict_list:
                label = f"{cat_key} ({len(conflict_list)})"
                categories.append((cat_key, label))

        for cat_key, label in categories:
            btn = QPushButton(label)
            btn.setFixedHeight(30)
            btn.setCheckable(True)
            btn.setChecked(cat_key == self.current_category)
            btn.clicked.connect(lambda _, k=cat_key: self.set_category_filter(k))
            self._style_cat_button(btn, cat_key == self.current_category)
            self.category_bar.addWidget(btn)
            self.cat_buttons[cat_key] = btn

        self.category_bar.addStretch()

    def _style_cat_button(self, btn: QPushButton, is_active: bool):
        if is_active:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #0078d4;
                    color: #ffffff;
                    border: 1px solid #0078d4;
                    border-radius: 6px;
                    padding: 4px 12px;
                    font-size: 12px;
                    font-weight: bold;
                }
            """)
        else:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #2d2d2d;
                    color: #cccccc;
                    border: 1px solid #3d3d3d;
                    border-radius: 6px;
                    padding: 4px 12px;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: #383838;
                    color: #ffffff;
                }
            """)

    def set_category_filter(self, category_key: str):
        self.current_category = category_key
        for k, btn in self.cat_buttons.items():
            is_active = k == category_key
            btn.setChecked(is_active)
            self._style_cat_button(btn, is_active)
        self.populate_table()

    def on_search_changed(self, text: str):
        self.current_search = text.strip().lower()
        self.populate_table()

    def _open_folder_safe(self, folder_path: Path):
        """Safely opens a folder path in native file manager using PlatformUtils with error feedback."""
        try:
            if not PlatformUtils.open_dir(str(folder_path)):
                raise Exception("Desktop service rejected request")
        except Exception as e:
            QMessageBox.warning(
                self,
                tr("open_folder_error"),
                tr("open_folder_error_msg", path=str(folder_path), e=str(e)),
            )

    def _create_mods_cell_widget(self, conflict: FileConflict) -> QWidget:
        """Creates a horizontal container with distinct, clickable mod badges."""
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(6)

        for mod_name, folder_path in conflict.mod_folders:
            btn = QPushButton(mod_name)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(f"{tr('conflict_open_folder_btn')}: {folder_path}")
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #2e333d;
                    color: #e0e0e0;
                    border: 1px solid #464f5f;
                    border-radius: 4px;
                    padding: 4px 10px;
                    font-size: 11px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background-color: #0078d4;
                    color: #ffffff;
                    border-color: #0078d4;
                }
            """)
            btn.clicked.connect(lambda _, p=folder_path: self._open_folder_safe(p))
            layout.addWidget(btn)

        layout.addStretch()
        return container

    def populate_table(self):
        """Populates the conflict table with filtered items."""
        self.table.setRowCount(0)

        if not self.scan_result or not self.scan_result.has_conflicts:
            self.table.setVisible(False)
            self.empty_label.setText(
                f"✅ {tr('conflict_no_conflicts_title')}\n\n{tr('conflict_no_conflicts_desc')}"
            )
            self.empty_label.setVisible(True)
            self.summary_label.setText(tr("conflict_no_conflicts_title"))
            return

        self.empty_label.setVisible(False)
        self.table.setVisible(True)

        if self.current_category == "all":
            conflicts = self.scan_result.conflicts
        else:
            conflicts = self.scan_result.conflicts_by_category.get(
                self.current_category, []
            )

        if self.current_search:
            conflicts = [
                c
                for c in conflicts
                if (
                    self.current_search in c.relative_path.lower()
                    or self.current_search in c.category.lower()
                    or self.current_search in c.winning_mod_name.lower()
                    or any(
                        self.current_search in o.mod_name.lower()
                        for o in c.overwritten_records
                    )
                )
            ]

        self.filtered_conflicts = conflicts
        self.table.setRowCount(len(conflicts))

        for row, conflict in enumerate(conflicts):
            # Column 0: Folder Badge
            cat_item = QTableWidgetItem(f"[{conflict.category}]")
            cat_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            cat_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            if conflict.category == "regulation.bin":
                cat_item.setForeground(QColor("#ffaa00"))
            else:
                cat_item.setForeground(QColor("#66b2ff"))
            self.table.setItem(row, 0, cat_item)

            # Column 1: Relative File Path
            path_item = QTableWidgetItem(conflict.relative_path)
            path_item.setToolTip(conflict.relative_path)
            path_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self.table.setItem(row, 1, path_item)

            # Column 2: Conflicting Mod Badges Widget
            all_mod_names = [conflict.winning_mod_name] + [
                o.mod_name for o in conflict.overwritten_records
            ]
            mods_item = QTableWidgetItem(", ".join(all_mod_names))
            mods_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self.table.setItem(row, 2, mods_item)

            # Cell Widget with badges for clear visual presentation and direct click
            mods_widget = self._create_mods_cell_widget(conflict)
            self.table.setCellWidget(row, 2, mods_widget)

        self.summary_label.setText(
            f"{len(conflicts)} / {self.scan_result.total_conflicts} conflicts displayed"
        )

        if len(conflicts) > 0:
            self.table.selectRow(0)

    def show_context_menu(self, pos):
        """Show context menu on table row to open mod directory in file manager."""
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            return

        row = selected_rows[0].row()
        if not (0 <= row < len(self.filtered_conflicts)):
            return

        conflict = self.filtered_conflicts[row]
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #2a2a2a;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 20px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #0078d4;
            }
        """)

        for mod_name, folder_path in conflict.mod_folders:
            action = QAction(f"Open in {mod_name}", self)
            action.triggered.connect(lambda _, p=folder_path: self._open_folder_safe(p))
            menu.addAction(action)

        menu.exec(self.table.viewport().mapToGlobal(pos))
