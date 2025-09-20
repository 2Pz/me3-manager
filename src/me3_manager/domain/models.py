from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class GameConfig:
    name: str
    mods_dir: str
    profile: str
    cli_id: str
    executable: str


@dataclass(frozen=True)
class Profile:
    id: str
    name: str
    profile_path: str
    mods_path: str

    def profile_file(self) -> Path:
        return Path(self.profile_path)

    def mods_dir(self) -> Path:
        return Path(self.mods_path)
