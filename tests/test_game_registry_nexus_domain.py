import tempfile
import unittest
from pathlib import Path

from me3_manager.core.settings.game_registry import GameRegistry
from me3_manager.core.settings.settings_manager import SettingsManager


class TestGameRegistryNexusDomain(unittest.TestCase):
    def test_empty_nexus_domain_auto_migration(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sfile = Path(tmpdir) / "settings.json"
            sm = SettingsManager(sfile)

            # Simulate existing config with empty nexus_domain string
            sm.set(
                "games",
                {
                    "Sekiro": {
                        "mods_dir": "sekiro-mods",
                        "profile": "sekiro-default.me3",
                        "cli_id": "sekiro",
                        "executable": "sekiro.exe",
                        "nexus_domain": "",
                    },
                    "Dark Souls 3": {
                        "mods_dir": "darksouls3-mods",
                        "profile": "darksouls3-default.me3",
                        "cli_id": "ds3",
                        "executable": "DarkSoulsIII.exe",
                        "nexus_domain": "",
                    },
                    "Armoredcore6": {
                        "mods_dir": "armoredcore6-mods",
                        "profile": "armoredcore6-default.me3",
                        "cli_id": "armoredcore6",
                        "executable": "armoredcore6.exe",
                        "nexus_domain": "",
                    },
                },
            )

            gr = GameRegistry(sm)
            expected = {
                "Sekiro": "sekiro",
                "Dark Souls 3": "darksouls3",
                "Armoredcore6": "armoredcore6firesofrubicon",
            }
            for game, domain in expected.items():
                self.assertEqual(gr.get_game_nexus_domain(game), domain)

            saved_games = sm.get("games")
            for game, domain in expected.items():
                self.assertEqual(saved_games[game]["nexus_domain"], domain)

    def test_get_nexus_domain_fallback(self):
        expected_defaults = {
            "Elden Ring": "eldenring",
            "Nightreign": "eldenringnightreign",
            "Sekiro": "sekiro",
            "Dark Souls 3": "darksouls3",
            "Armoredcore6": "armoredcore6firesofrubicon",
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            sfile = Path(tmpdir) / "settings.json"
            sm = SettingsManager(sfile)
            gr = GameRegistry(sm)

            for game, domain in expected_defaults.items():
                self.assertEqual(gr.get_game_nexus_domain(game), domain)


if __name__ == "__main__":
    unittest.main()
