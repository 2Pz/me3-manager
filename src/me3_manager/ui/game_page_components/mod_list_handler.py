"""
Mod List Data and Presentation Handler for GamePage.

This is the core handler for managing the mod list's data and presentation.
It is responsible for loading mod data, applying filters and search queries,
and generating the `ModItem` widgets for display.
"""

from pathlib import Path
from typing import TYPE_CHECKING, Any

from PySide6.QtGui import QIcon

from me3_manager.core.mod_manager import ModStatus, ModType
from me3_manager.ui.mod_item import ModItem
from me3_manager.utils.resource_path import resource_path
from me3_manager.utils.translator import tr

if TYPE_CHECKING:
    from me3_manager.ui.game_page_components import GamePage


class ModListHandler:
    """Manages the loading, filtering, and display of the mod list itself."""

    def __init__(self, game_page: "GamePage"):
        self.game_page = game_page

    def set_filter(self, filter_name: str):
        """Sets the current mod filter and triggers a UI update."""
        self.game_page.current_filter = filter_name
        self.update_filter_button_styles()
        self.apply_filters()

    def update_filter_button_styles(self):
        """Updates the visual style of the filter buttons to show the active filter."""
        base_style = """
            QPushButton {{
                background-color: {bg_color}; border: 1px solid {border_color};
                color: {text_color}; border-radius: 6px; padding: 0px 12px;
                font-size: 12px; font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {hover_bg_color}; border-color: {hover_border_color};
            }}
        """
        selected_style = base_style.format(
            bg_color="#0078d4",
            border_color="#0078d4",
            text_color="white",
            hover_bg_color="#106ebe",
            hover_border_color="#106ebe",
        )
        default_style = base_style.format(
            bg_color="#3d3d3d",
            border_color="#4d4d4d",
            text_color="#cccccc",
            hover_bg_color="#4d4d4d",
            hover_border_color="#5d5d5d",
        )
        for name, button in self.game_page.filter_buttons.items():
            if name == self.game_page.current_filter:
                button.setStyleSheet(selected_style)
            else:
                button.setStyleSheet(default_style)

    def load_mods(self, reset_page: bool = True):
        """Reloads mods from the ModManager and updates the UI."""
        gp = self.game_page  # short alias
        mods_dir = gp.config_manager.get_mods_dir(gp.game_name)
        if not mods_dir or not mods_dir.is_dir():
            self.apply_filters(reset_page=True, source_mods={})
            gp.update_profile_dropdown()
            gp.status_label.setText(tr("mods_dir_not_found_warning"))
            return

        gp.mod_infos = gp.mod_manager.get_all_mods(gp.game_name)
        final_mods = {}
        for mod_path, mod_info in gp.mod_infos.items():
            display_name = mod_info.name
            # If this mod was downloaded/linked from Nexus, prefer Nexus display name.
            try:
                linked = gp.nexus_metadata.find_for_local_mod(
                    str(Path(mod_path).resolve())
                )
                if linked and linked.mod_name:
                    display_name = linked.mod_name
            except Exception:
                pass
            final_mods[mod_path] = {
                "name": display_name,
                "enabled": mod_info.status == ModStatus.ENABLED,
                "external": mod_info.is_external,
                "is_folder_mod": mod_info.mod_type == ModType.PACKAGE,
                "has_regulation": mod_info.has_regulation,
                "regulation_active": mod_info.regulation_active,
                "advanced_options": mod_info.advanced_options,
            }

        gp.all_mods_data = final_mods
        self.apply_filters(reset_page=reset_page, source_mods=final_mods)
        gp.update_profile_dropdown()

    def apply_filters(
        self, reset_page: bool = True, source_mods: dict[str, Any] | None = None
    ):
        """Filters the mod list based on search text and category."""
        gp = self.game_page
        # Only use the search bar text to filter LOCAL mods when in local search mode.
        # In Nexus mode, the search bar contains a URL/ID which would hide the local list.
        if getattr(gp, "search_mode", "local") == "local":
            search_text = gp.search_bar.text().lower()
        else:
            search_text = ""
        all_mods = source_mods if source_mods is not None else gp.all_mods_data
        gp.filtered_mods = {}

        for mod_path, info in all_mods.items():
            if search_text not in info["name"].lower():
                continue

            is_enabled = info["enabled"]
            is_folder_mod = info.get("is_folder_mod", False)
            has_regulation = info.get("has_regulation", False)

            category_match = False
            if gp.current_filter == "all":
                category_match = True
            elif gp.current_filter == "enabled":
                category_match = is_enabled
            elif gp.current_filter == "disabled":
                category_match = not is_enabled
            elif gp.current_filter == "with_regulation":
                category_match = is_folder_mod and is_enabled and has_regulation
            elif gp.current_filter == "without_regulation":
                category_match = is_folder_mod and is_enabled and not has_regulation

            if category_match:
                gp.filtered_mods[mod_path] = info

        if reset_page:
            gp.current_page = 1
        gp.update_pagination()

    def _group_mods_for_tree_display(self, mod_items):
        """Groups mods to create expandable tree structure."""
        gp = self.game_page
        if not hasattr(gp, "expanded_states"):
            gp.expanded_states = {}

        grouped = {}
        parent_packages, nested_mods = {}, {}

        for mod_path, info in mod_items:
            if mod_path in gp.mod_infos:
                mod_info = gp.mod_infos[mod_path]
                if mod_info.mod_type.value == "nested" and mod_info.parent_package:
                    parent_name = mod_info.parent_package
                    if parent_name not in nested_mods:
                        nested_mods[parent_name] = []
                    clean_info = info.copy()
                    clean_info["name"] = Path(mod_path).name
                    # Store both clean_info (for children display) and original info (for standalone)
                    nested_mods[parent_name].append((mod_path, clean_info, info))
                elif mod_info.mod_type.value == "package":
                    parent_packages[mod_info.name] = (mod_path, info)
                else:
                    grouped[mod_path] = {"type": "standalone", "info": info}
            else:
                grouped[mod_path] = {"type": "standalone", "info": info}

        for parent_name, children_list in nested_mods.items():
            if parent_name in parent_packages:
                parent_path, parent_info = parent_packages[parent_name]
                grouped[parent_path] = {
                    "type": "parent_with_children",
                    "parent": parent_info,
                    "children": {
                        child_path: child_info
                        for child_path, child_info, _ in children_list
                    },
                    "expanded": gp.expanded_states.get(parent_path, False),
                }
                parent_packages.pop(parent_name, None)
            else:
                # Orphaned nested mods (parent is DLL-only folder, not a package)
                # Display them as standalone mods with original info (includes Nexus name)
                for child_path, _, original_info in children_list:
                    grouped[child_path] = {"type": "standalone", "info": original_info}

        for parent_path, parent_info in parent_packages.values():
            if parent_path not in grouped:
                grouped[parent_path] = {"type": "standalone", "info": parent_info}
        return grouped

    def _create_mod_widget(
        self, mod_path, info, is_nested=False, has_children=False, is_expanded=False
    ):
        """Factory method to create a single ModItem widget."""
        gp = self.game_page
        is_enabled, is_folder_mod, has_regulation, regulation_active = (
            info["enabled"],
            info.get("is_folder_mod", False),
            info.get("has_regulation", False),
            info.get("regulation_active", False),
        )

        text_color = "#cccccc" if not is_enabled else "#90EE90"
        if is_nested:
            text_color = "#b0b0b0" if not is_enabled else "#90EE90"
        elif regulation_active:
            text_color = "#FFD700"

        mod_info = gp.mod_infos.get(mod_path)
        # Determine mod type and icon based on conditions
        if mod_info and mod_info.mod_type.value == "nested":
            mod_type, type_icon = (
                tr("mod_type_nested_dll"),
                QIcon(resource_path("resources/icon/dll.svg")),
            )
        elif regulation_active:
            mod_type, type_icon = (
                tr("mod_type_active_regulation"),
                QIcon(resource_path("resources/icon/regulation_active.svg")),
            )
        elif has_regulation:
            mod_type, type_icon = (
                tr("mod_type_package_with_regulation"),
                QIcon(resource_path("resources/icon/folder.svg")),
            )
        elif is_folder_mod:
            mod_type, type_icon = (
                tr("mod_type_package"),
                QIcon(resource_path("resources/icon/folder.svg")),
            )
        else:
            mod_type, type_icon = (
                tr("mod_type_native"),
                QIcon(resource_path("resources/icon/dll.svg")),
            )

        has_advanced_options = (
            gp.mod_manager.has_advanced_options(mod_info) if mod_info else False
        )

        mod_widget = ModItem(
            mod_path=mod_path,
            mod_name=info["name"],
            is_enabled=is_enabled,
            is_external=info["external"],
            is_folder_mod=is_folder_mod,
            is_regulation=has_regulation,
            mod_type=mod_type,
            type_icon=type_icon,
            item_bg_color="transparent",
            text_color=text_color,
            is_regulation_active=regulation_active,
            has_advanced_options=has_advanced_options,
            is_nested=is_nested,
            has_children=has_children,
            is_expanded=is_expanded,
        )

        # Connect signals to the GamePage's delegating methods
        mod_widget.toggled.connect(gp.toggle_mod)
        if not is_nested:
            mod_widget.delete_requested.connect(gp.delete_mod)
            mod_widget.clicked.connect(gp.on_local_mod_selected)
        mod_widget.edit_config_requested.connect(gp.open_config_editor)
        mod_widget.open_folder_requested.connect(gp.open_mod_folder)
        mod_widget.advanced_options_requested.connect(gp.open_advanced_options)
        if has_regulation:
            mod_widget.regulation_activate_requested.connect(gp.activate_regulation_mod)
        return mod_widget

    def _on_mod_expand_requested(self, mod_path: str, expanded: bool):
        """Handles expand/collapse requests for parent mods."""
        gp = self.game_page
        if not hasattr(gp, "expanded_states"):
            gp.expanded_states = {}
        gp.expanded_states[mod_path] = expanded
        gp.update_pagination()
