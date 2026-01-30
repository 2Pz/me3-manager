"""
Pagination and Mod Display Handler for GamePage.

Manages the logic for paginating the mod list, including navigating between pages,
changing the number of items per page, and redrawing the list of visible mods.
"""

import math
from typing import TYPE_CHECKING

from me3_manager.utils.translator import tr

if TYPE_CHECKING:
    from ..game_page import GamePage


class PaginationHandler:
    """Manages the pagination and display of the mod list."""

    def __init__(self, game_page: "GamePage"):
        self.game_page = game_page

    def change_items_per_page(self, value: int):
        """Handles the spinbox value change for items per page."""
        self.game_page.mods_per_page = value
        self.game_page.config_manager.set_mods_per_page(value)
        self.game_page.current_page = 1
        self.update_pagination()

    def prev_page(self):
        """Navigates to the previous page."""
        if self.game_page.current_page > 1:
            self.game_page.current_page -= 1
            self.update_pagination()

    def next_page(self):
        """Navigates to the next page."""
        if self.game_page.current_page < self.game_page.total_pages:
            self.game_page.current_page += 1
            self.update_pagination()

    def update_pagination(self):
        """
        Updates the mod list display based on the current page and filters.
        This is the core method for redrawing the mod widgets.
        """
        gp = self.game_page  # Create a shorter alias for readability
        # Group mods for tree display (calls back to a method on GamePage)
        grouped_mods_all = gp._group_mods_for_tree_display(
            list(gp.filtered_mods.items())
        )

        # Calculate pages based on visible ROOT groups (collapsed children don't count)
        group_keys = list(grouped_mods_all.keys())
        total_groups = len(group_keys)

        gp.total_pages = max(1, math.ceil(total_groups / gp.mods_per_page))
        if gp.current_page > gp.total_pages:
            gp.current_page = gp.total_pages

        gp.page_label.setText(
            tr(
                "page_label_text",
                current_page=gp.current_page,
                total_pages=gp.total_pages,
            )
        )
        gp.prev_btn.setEnabled(gp.current_page > 1)
        gp.next_btn.setEnabled(gp.current_page < gp.total_pages)

        # Clear existing widgets from the layout
        while gp.mods_layout.count():
            child = gp.mods_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # Initialize map to track widgets for scrolling
        gp.mod_widgets_map = {}

        # Slice the GROUPS for the current page
        start_idx = (gp.current_page - 1) * gp.mods_per_page
        end_idx = start_idx + gp.mods_per_page

        current_page_keys = group_keys[start_idx:end_idx]

        # Create widgets for visible groups
        for group_key in current_page_keys:
            group_data = grouped_mods_all[group_key]

            if group_data["type"] == "parent_with_children":
                parent_info = group_data["parent"]
                # Create parent mod widget (calls back to a method on GamePage)
                parent_widget = gp.mod_list_handler._create_mod_widget(
                    group_key,
                    parent_info,
                    has_children=True,
                    is_expanded=group_data.get("expanded", False),
                )
                parent_widget.expand_requested.connect(gp._on_mod_expand_requested)
                gp.mods_layout.addWidget(parent_widget)
                gp.mod_widgets_map[group_key] = parent_widget

                if group_data.get("expanded", False):
                    children_items = list(group_data["children"].items())
                    total_children = len(children_items)
                    for i, (child_path, child_info) in enumerate(children_items):
                        is_last = i == total_children - 1
                        child_widget = gp.mod_list_handler._create_mod_widget(
                            child_path,
                            child_info,
                            is_nested=True,
                            is_last_child=is_last,
                        )
                        gp.mods_layout.addWidget(child_widget)
                        gp.mod_widgets_map[child_path] = child_widget
            else:
                # Regular standalone mod
                mod_widget = gp.mod_list_handler._create_mod_widget(
                    group_key, group_data["info"]
                )
                gp.mods_layout.addWidget(mod_widget)
                gp.mod_widgets_map[group_key] = mod_widget

        # Add stretch to push items to the top
        gp.mods_layout.addStretch()

        # Update status label
        total_mods_filtered = len(gp.filtered_mods)
        enabled_mods_filtered = sum(
            1 for info in gp.filtered_mods.values() if info["enabled"]
        )
        showing_start = start_idx + 1 if total_mods_filtered > 0 else 0
        showing_end = min(end_idx, total_mods_filtered)
        gp.status_label.setText(
            tr(
                "showing_mods_status",
                start=showing_start,
                end=showing_end,
                total=total_mods_filtered,
                enabled=enabled_mods_filtered,
            )
        )
