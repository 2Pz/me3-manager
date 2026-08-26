from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from me3_manager.core.mod_manager import ModInfo, ModStatus, ModType
from me3_manager.ui.game_page_components.mod_list_handler import ModListHandler
from me3_manager.ui.game_page_components.pagination_handler import PaginationHandler


@pytest.fixture
def mock_game_page(qtbot):
    game_page = MagicMock()
    game_page.mods_per_page = 10
    game_page.current_page = 1
    game_page.total_pages = 1
    game_page.status_label = QLabel()
    game_page.page_label = QLabel()
    game_page.prev_btn = MagicMock()
    game_page.next_btn = MagicMock()

    game_page.mods_widget = QWidget()
    game_page.mods_layout = QVBoxLayout(game_page.mods_widget)
    qtbot.addWidget(game_page.mods_widget)
    qtbot.addWidget(game_page.status_label)

    game_page.mod_list_handler = ModListHandler(game_page)
    game_page._group_mods_for_tree_display = (
        game_page.mod_list_handler._group_mods_for_tree_display
    )
    pagination_handler = PaginationHandler(game_page)
    game_page.pagination_handler = pagination_handler
    return game_page, pagination_handler


def test_pagination_handler_mod_count(mock_game_page):
    game_page, pagination_handler = mock_game_page

    # Simulate 3 installed mods on Elden Ring:
    # 1. SeamlessCoop (container folder with ersc.dll inside)
    # 2. GrandMerchant (folder mod with mod content)
    # 3. SimpleMod (standalone DLL)
    folder1 = "/mods/SeamlessCoop"
    dll1 = "/mods/SeamlessCoop/ersc.dll"
    folder2 = "/mods/GrandMerchant"
    dll3 = "/mods/SimpleMod.dll"

    game_page.mod_infos = {
        folder1: ModInfo(
            path=folder1,
            name="SeamlessCoop",
            mod_type=ModType.FOLDER,
            status=ModStatus.ENABLED,
            is_external=False,
            is_container=True,
            child_count=1,
        ),
        dll1: ModInfo(
            path=dll1,
            name="SeamlessCoop/ersc",
            mod_type=ModType.DLL,
            status=ModStatus.ENABLED,
            is_external=False,
            parent_package="SeamlessCoop",
        ),
        folder2: ModInfo(
            path=folder2,
            name="GrandMerchant",
            mod_type=ModType.FOLDER,
            status=ModStatus.ENABLED,
            is_external=False,
            is_container=False,
            child_count=0,
        ),
        dll3: ModInfo(
            path=dll3,
            name="SimpleMod",
            mod_type=ModType.DLL,
            status=ModStatus.ENABLED,
            is_external=False,
        ),
    }

    # filtered_mods contains all 4 raw entries (folder1, dll1, folder2, dll3)
    game_page.filtered_mods = {
        folder1: {"name": "SeamlessCoop", "enabled": True, "external": False},
        dll1: {"name": "SeamlessCoop/ersc", "enabled": True, "external": False},
        folder2: {"name": "GrandMerchant", "enabled": True, "external": False},
        dll3: {"name": "SimpleMod", "enabled": True, "external": False},
    }

    # Run update_pagination
    pagination_handler.update_pagination()

    # The UI should display 3 mods (SeamlessCoop auto-flattened into ersc.dll, GrandMerchant, SimpleMod)
    # Status label should be: "Showing 1-3 of 3 mods (3 enabled)"
    assert "Showing 1-3 of 3 mods (3 enabled)" in game_page.status_label.text()


def test_pagination_handler_enabled_disabled_count(mock_game_page):
    game_page, pagination_handler = mock_game_page

    # 3 standalone mods: 2 enabled, 1 disabled
    mod1 = "/mods/Mod1.dll"
    mod2 = "/mods/Mod2.dll"
    mod3 = "/mods/Mod3.dll"

    game_page.mod_infos = {
        mod1: ModInfo(
            path=mod1,
            name="Mod1",
            mod_type=ModType.DLL,
            status=ModStatus.ENABLED,
            is_external=False,
        ),
        mod2: ModInfo(
            path=mod2,
            name="Mod2",
            mod_type=ModType.DLL,
            status=ModStatus.DISABLED,
            is_external=False,
        ),
        mod3: ModInfo(
            path=mod3,
            name="Mod3",
            mod_type=ModType.DLL,
            status=ModStatus.ENABLED,
            is_external=False,
        ),
    }

    game_page.filtered_mods = {
        mod1: {"name": "Mod1", "enabled": True, "external": False},
        mod2: {"name": "Mod2", "enabled": False, "external": False},
        mod3: {"name": "Mod3", "enabled": True, "external": False},
    }

    pagination_handler.update_pagination()
    assert "Showing 1-3 of 3 mods (2 enabled)" in game_page.status_label.text()
