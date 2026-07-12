from me3_manager.ui.dialogs.game_options_dialog import GameOptionsDialog


class MockMe3Info:
    def __init__(self, tmp_path):
        self.tmp_path = tmp_path
        self.system_path = tmp_path / "sys_opt" / "me3"
        self.user_path = tmp_path / "user_home" / "me3.toml"
        self.user_dir = tmp_path / "user_home"

        # Ensure user dir exists but sys_opt is treated as system
        self.user_dir.mkdir(parents=True, exist_ok=True)
        self.system_path.mkdir(parents=True, exist_ok=True)

    def get_available_config_paths(self):
        # Return a system path and a user path
        return [self.system_path / "me3.toml", self.user_path]


class MockConfigManager:
    def __init__(self, tmp_path):
        self.me3_info = MockMe3Info(tmp_path)

    def get_me3_game_settings(self, game_name):
        return {}

    def get_me3_config_path(self, game_name):
        return None


def test_iter_user_config_paths(qtbot, tmp_path, monkeypatch):
    dialog = GameOptionsDialog("TestGame", MockConfigManager(tmp_path))
    qtbot.addWidget(dialog)

    # Mock _is_system_path since we're generating custom test paths
    def mock_is_system_path(path):
        return "sys_opt" in str(path)

    monkeypatch.setattr(dialog, "_is_system_path", mock_is_system_path)

    paths = list(dialog._iter_user_config_paths())
    assert len(paths) == 1
    assert "user_home" in str(paths[0])
    assert "sys_opt" not in str(paths[0])


def test_get_writable_config_path(qtbot, tmp_path, monkeypatch):
    dialog = GameOptionsDialog("TestGame", MockConfigManager(tmp_path))
    qtbot.addWidget(dialog)

    def mock_is_system_path(path):
        return "sys_opt" in str(path)

    monkeypatch.setattr(dialog, "_is_system_path", mock_is_system_path)

    # User path doesn't exist yet but the parent directory is writable
    writable_path = dialog._get_writable_config_path()
    assert writable_path is not None
    assert "user_home" in str(writable_path)

    # It should have created the file
    assert writable_path.exists()
