from pathlib import Path
from typing import Any

from me3_manager.core.conflict_scanner import (
    ConflictScannerService,
    categorize_relative_path,
)


def _build_mock_config(
    mocker, mods_dir: Path, profile_path: Path, config_data: dict[str, Any]
):
    """Helper to construct a mocked config facade for conflict tests."""
    mock = mocker.MagicMock()
    mock.get_mods_dir.return_value = mods_dir
    mock.get_profile_path.return_value = profile_path
    mock._parse_toml_config.return_value = config_data
    return mock


def test_categorize_relative_path():
    assert categorize_relative_path("regulation.bin") == "regulation.bin"
    assert categorize_relative_path("regulation.bin.bak") == "regulation.bin"
    assert categorize_relative_path("chr/c0000.chrbnd.dcx") == "chr"
    assert categorize_relative_path("CHR/c0000.chrbnd.dcx") == "chr"
    assert categorize_relative_path("parts/wp_a_0100.partsbnd.dcx") == "parts"
    assert categorize_relative_path("msg/engus/item.msg.bnd.dcx") == "msg"
    assert categorize_relative_path("map/mapstudio/m10_00_00_00.msb.dcx") == "map"
    assert categorize_relative_path("sound/fdp_main.fsb") == "sound"
    assert categorize_relative_path("sd/en/cs_01.fsb") == "sd"
    assert categorize_relative_path("material/all_material.bnd.dcx") == "material"
    assert categorize_relative_path("event/common.emevd.dcx") == "event"
    assert categorize_relative_path("action/player.tae.dcx") == "action"
    assert categorize_relative_path("movie/opening.bk2") == "movie"
    assert categorize_relative_path("custom_folder/sub/file.txt") == "custom_folder"
    assert categorize_relative_path("root_file.txt") == "other"


def test_conflict_scanner_no_conflicts(tmp_path: Path):
    mod_a = tmp_path / "ModA"
    mod_a.mkdir()
    (mod_a / "chr").mkdir()
    (mod_a / "chr" / "c1000.chrbnd.dcx").write_text("dummy a")

    mod_b = tmp_path / "ModB"
    mod_b.mkdir()
    (mod_b / "parts").mkdir()
    (mod_b / "parts" / "wp_a_0100.partsbnd.dcx").write_text("dummy b")

    scanner = ConflictScannerService()
    entries = [
        ("Mod A", "ModA", mod_a, 0),
        ("Mod B", "ModB", mod_b, 1),
    ]

    result = scanner.scan_entries(entries, game_name="Elden Ring")
    assert not result.has_conflicts
    assert result.total_conflicts == 0
    assert len(result.conflicts) == 0


def test_conflict_scanner_with_overlaps(tmp_path: Path):
    # Mod A has priority 0 (winner)
    mod_a = tmp_path / "ModA"
    mod_a.mkdir()
    (mod_a / "regulation.bin").write_text("reg a")
    (mod_a / "chr").mkdir()
    (mod_a / "chr" / "c0000.chrbnd.dcx").write_text("chr a")

    # Mod B has priority 1 (overwritten by Mod A)
    mod_b = tmp_path / "ModB"
    mod_b.mkdir()
    (mod_b / "regulation.bin").write_text("reg b")
    (mod_b / "chr").mkdir()
    (mod_b / "chr" / "c0000.chrbnd.dcx").write_text("chr b")
    (mod_b / "parts").mkdir()
    (mod_b / "parts" / "wp_a_0100.partsbnd.dcx").write_text("parts b unique")

    # Mod C has priority 2 (overwritten by Mod A on chr)
    mod_c = tmp_path / "ModC"
    mod_c.mkdir()
    (mod_c / "chr").mkdir()
    (mod_c / "chr" / "c0000.chrbnd.dcx").write_text("chr c")

    scanner = ConflictScannerService()
    entries = [
        ("Mod A", "ModA", mod_a, 0),
        ("Mod B", "ModB", mod_b, 1),
        ("Mod C", "ModC", mod_c, 2),
    ]

    result = scanner.scan_entries(entries, game_name="Elden Ring")
    assert result.has_conflicts
    assert result.total_conflicts == 2  # regulation.bin and chr/c0000.chrbnd.dcx

    # Check regulation conflict
    reg_conflicts = result.conflicts_by_category["regulation.bin"]
    assert len(reg_conflicts) == 1
    reg_conflict = reg_conflicts[0]
    assert reg_conflict.relative_path == "regulation.bin"
    assert reg_conflict.winning_mod_name == "Mod A"
    assert len(reg_conflict.overwritten_records) == 1
    assert reg_conflict.overwritten_records[0].mod_name == "Mod B"

    # Check chr conflict
    chr_conflicts = result.conflicts_by_category["chr"]
    assert len(chr_conflicts) == 1
    chr_conflict = chr_conflicts[0]
    assert chr_conflict.relative_path == "chr/c0000.chrbnd.dcx"
    assert chr_conflict.winning_mod_name == "Mod A"
    assert len(chr_conflict.overwritten_records) == 2  # Mod B and Mod C overwritten
    assert chr_conflict.overwritten_records[0].mod_name == "Mod B"
    assert chr_conflict.overwritten_records[1].mod_name == "Mod C"

    # Check mod summaries
    summary_a = result.conflicts_by_mod["ModA"]
    assert summary_a.overwrites_count == 2
    assert summary_a.overwritten_by_count == 0

    summary_b = result.conflicts_by_mod["ModB"]
    assert summary_b.overwrites_count == 0
    assert summary_b.overwritten_by_count == 2

    summary_c = result.conflicts_by_mod["ModC"]
    assert summary_c.overwrites_count == 0
    assert summary_c.overwritten_by_count == 1


def test_conflict_scanner_caching(tmp_path: Path):
    d_one = tmp_path / "ModOne"
    d_one.mkdir()
    (d_one / "regulation.bin").write_text("reg 1")

    d_two = tmp_path / "ModTwo"
    d_two.mkdir()
    (d_two / "regulation.bin").write_text("reg 2")

    scanner = ConflictScannerService()
    mod_list = [("One", "ModOne", d_one, 0), ("Two", "ModTwo", d_two, 1)]

    res1 = scanner.scan_entries(mod_list)
    assert res1.total_conflicts == 1

    # Second scan should hit cache
    res2 = scanner.scan_entries(mod_list)
    assert res2.total_conflicts == 1


def _setup_two_regulation_mods(tmp_path: Path, mocker):
    mods_dir = tmp_path / "eldenring-mods"
    mods_dir.mkdir()
    (mods_dir / "mod1").mkdir()
    (mods_dir / "mod1" / "regulation.bin").write_text("reg 1")
    (mods_dir / "mod2").mkdir()
    (mods_dir / "mod2" / "regulation.bin").write_text("reg 2")

    return _build_mock_config(
        mocker,
        mods_dir,
        tmp_path / "profile.me3",
        {
            "packages": [
                {"id": "mod1", "path": "mod1", "enabled": True},
                {"id": "mod2", "path": "mod2", "enabled": True},
            ]
        },
    )


def test_scan_game_profile(tmp_path: Path, mocker):
    mock_cfg = _setup_two_regulation_mods(tmp_path, mocker)

    scanner = ConflictScannerService()
    result = scanner.scan_game_profile("Elden Ring", mock_cfg)
    assert result.has_conflicts
    assert result.total_conflicts == 1
    assert result.conflicts[0].winning_mod_name == "mod1"


def test_conflict_inspector_dialog_init(qtbot, tmp_path: Path, mocker):
    from me3_manager.ui.dialogs.conflict_inspector_dialog import (
        ConflictInspectorDialog,
    )

    mods_dir = tmp_path / "mods"
    mods_dir.mkdir()

    mock_cfg = _build_mock_config(
        mocker, mods_dir, tmp_path / "profile.me3", {"packages": []}
    )

    dialog = ConflictInspectorDialog("Elden Ring", mock_cfg)
    qtbot.addWidget(dialog)
    dialog.show()
    assert dialog.windowTitle().startswith("File Conflict")
    assert not dialog.empty_label.isHidden()


def test_conflict_inspector_dialog_with_conflicts(qtbot, tmp_path: Path, mocker):
    from me3_manager.ui.dialogs.conflict_inspector_dialog import (
        ConflictInspectorDialog,
    )

    mock_cfg = _setup_two_regulation_mods(tmp_path, mocker)

    dialog = ConflictInspectorDialog("Elden Ring", mock_cfg)
    qtbot.addWidget(dialog)
    dialog.show()

    assert dialog.scan_result.has_conflicts
    assert dialog.table.rowCount() == 1
    assert not dialog.table.isHidden()

    # Test filtering
    dialog.search_edit.setText("regulation")
    assert dialog.table.rowCount() == 1

    dialog.search_edit.setText("non_existent_query")
    assert dialog.table.rowCount() == 0
