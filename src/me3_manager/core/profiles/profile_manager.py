from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from me3_manager.core.profiles.toml_profile_writer import TomlProfileWriter

log = logging.getLogger(__name__)


class ProfileManager:
    """
    Central profile read/write/migration utility.
    Wraps TOML I/O and provides helpers used by UI/services.
    """

    @staticmethod
    def read_profile(profile_path: Path) -> dict[str, Any]:
        try:
            import tomllib

            if not profile_path.exists():
                return {
                    "profileVersion": "v1",
                    "natives": [],
                    "packages": [],
                    "supports": [],
                }
            with open(profile_path, "rb") as f:
                return tomllib.load(f)
        except Exception as e:
            log.error("Error reading profile %s: %s", profile_path, e)
            return {
                "profileVersion": "v1",
                "natives": [],
                "packages": [],
                "supports": [],
            }

    @staticmethod
    def write_profile(
        profile_path: Path, config_data: dict[str, Any], game_name: str | None = None
    ) -> None:
        TomlProfileWriter.write_profile(profile_path, config_data, game_name)

    @staticmethod
    def ensure_format(profile_path: Path) -> None:
        """If the profile uses old inline arrays, migrate to AOT using TomlProfileWriter."""
        try:
            if not profile_path.exists():
                return
            with open(profile_path, "r", encoding="utf-8") as f:
                content = f.read()
            if "natives = [" in content and "{path" in content:
                data = ProfileManager.read_profile(profile_path)
                TomlProfileWriter.write_profile(profile_path, data)
                log.debug(
                    "Migrated profile %s to array-of-tables format", profile_path.name
                )
        except Exception as e:
            log.error("Error ensuring profile format %s: %s", profile_path, e)
