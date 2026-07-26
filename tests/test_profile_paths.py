from pathlib import Path

from me3_manager.core.paths.profile_paths import (
    get_default_os_profiles_root,
    get_me3_bin_dir,
    get_me3_profiles_root,
    get_me3_root,
)


def test_default_os_profiles_root():
    root = get_default_os_profiles_root()
    assert isinstance(root, Path)


def test_custom_me3_location_resolution(tmp_path, monkeypatch):
    custom_dir = tmp_path / "custom_me3"
    custom_dir.mkdir()

    monkeypatch.setattr(
        "me3_manager.core.paths.profile_paths.get_custom_me3_location",
        lambda: custom_dir,
    )

    assert get_me3_profiles_root() == custom_dir / "config" / "profiles"
    assert get_me3_root() == custom_dir
    assert get_me3_bin_dir() == custom_dir / "bin"


def test_config_facade_set_custom_me3_location(tmp_path, monkeypatch):
    test_settings_file = tmp_path / "manager_settings.json"
    monkeypatch.setattr(
        "me3_manager.core.paths.profile_paths.get_manager_settings_path",
        lambda: test_settings_file,
    )

    from me3_manager.core.config_facade import ConfigFacade
    from me3_manager.core.settings.settings_manager import SettingsManager

    facade = ConfigFacade()
    facade.settings_manager = SettingsManager(test_settings_file)

    custom_dir = tmp_path / "custom_location"
    facade.set_custom_me3_location(str(custom_dir))
    assert facade.get_custom_me3_location() == str(custom_dir)
    assert facade.config_root == custom_dir / "config" / "profiles"

    facade.set_custom_me3_location(None)
    assert facade.get_custom_me3_location() is None
