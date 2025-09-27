from __future__ import annotations

import shutil
import struct
import sys
from pathlib import Path
from typing import Any


class _BinaryKV:
    """
    Minimal Binary KeyValues (VDF) reader/writer sufficient for Steam shortcuts.vdf.

    Supported types:
      - 0x00: nested object
      - 0x01: string (null-terminated)
      - 0x02: int32 (little endian)
      - 0x07: uint64 (little endian)  [not used, but supported for completeness]
      - 0x08: end of object
    """

    TYPE_OBJECT = 0x00
    TYPE_STRING = 0x01
    TYPE_INT32 = 0x02
    TYPE_UINT64 = 0x07
    TYPE_END = 0x08

    @staticmethod
    def _read_cstring(buf: bytes, offset: int) -> tuple[str, int]:
        end = buf.find(b"\x00", offset)
        if end == -1:
            raise ValueError("Invalid VDF: unterminated string")
        return buf[offset:end].decode("utf-8", errors="ignore"), end + 1

    @classmethod
    def _read_node(cls, buf: bytes, offset: int) -> tuple[dict[str, Any], int]:
        result: dict[str, Any] = {}
        while True:
            if offset >= len(buf):
                raise ValueError("Invalid VDF: unexpected EOF")
            t = buf[offset]
            offset += 1

            if t == cls.TYPE_END:
                break

            key, offset = cls._read_cstring(buf, offset)

            if t == cls.TYPE_OBJECT:
                value, offset = cls._read_node(buf, offset)
            elif t == cls.TYPE_STRING:
                value, offset = cls._read_cstring(buf, offset)
            elif t == cls.TYPE_INT32:
                if offset + 4 > len(buf):
                    raise ValueError("Invalid VDF: truncated int32")
                value = int.from_bytes(buf[offset : offset + 4], "little", signed=True)
                offset += 4
            elif t == cls.TYPE_UINT64:
                if offset + 8 > len(buf):
                    raise ValueError("Invalid VDF: truncated uint64")
                value = int.from_bytes(buf[offset : offset + 8], "little", signed=False)
                offset += 8
            else:
                raise ValueError(f"Unsupported VDF type: {t}")

            result[key] = value

        return result, offset

    @classmethod
    def loads(cls, data: bytes) -> dict[str, Any]:
        # Root should be a single object (e.g., key 'shortcuts')
        obj, offset = cls._read_node(data, 0)
        if offset != len(data):
            # Some files may have trailing bytes; tolerate
            pass
        return obj

    @staticmethod
    def _write_cstring(s: str) -> bytes:
        return s.encode("utf-8") + b"\x00"

    @classmethod
    def _dump_node(cls, obj: dict[str, Any]) -> bytes:
        out = bytearray()
        for key, value in obj.items():
            if isinstance(value, dict):
                out.append(cls.TYPE_OBJECT)
                out += cls._write_cstring(key)
                out += cls._dump_node(value)
            elif isinstance(value, str):
                out.append(cls.TYPE_STRING)
                out += cls._write_cstring(key)
                out += cls._write_cstring(value)
            elif isinstance(value, bool):
                out.append(cls.TYPE_INT32)
                out += cls._write_cstring(key)
                out += struct.pack("<i", 1 if value else 0)
            elif isinstance(value, int):
                # Use int32 if fits, else uint64
                if -(2**31) <= value < 2**31:
                    out.append(cls.TYPE_INT32)
                    out += cls._write_cstring(key)
                    out += struct.pack("<i", value)
                else:
                    out.append(cls.TYPE_UINT64)
                    out += cls._write_cstring(key)
                    out += struct.pack("<Q", value)
            else:
                raise ValueError(
                    f"Unsupported value type for key '{key}': {type(value)}"
                )
        out.append(cls.TYPE_END)
        return bytes(out)

    @classmethod
    def dumps(cls, obj: dict[str, Any]) -> bytes:
        return cls._dump_node(obj)


class SteamShortcuts:
    """Utility to read/update Steam shortcuts.vdf for non-Steam games."""

    DEFAULT_FIELDS = {
        "icon": "",
        "ShortcutPath": "",
        "IsHidden": 0,
        "AllowDesktopConfig": 1,
        "OpenVR": 0,
        "Devkit": 0,
        "DevkitGameID": "",
        "DevkitOverrideAppID": 0,
        "LastPlayTime": 0,
        "FlatpakAppID": "",  # helps for Flatpak environments
    }

    @staticmethod
    def _resolve_steam_user_config_dirs(steam_dir: Path) -> list[Path]:
        userdata = steam_dir / "userdata"
        if not userdata.exists():
            return []
        user_dirs: list[Path] = []
        for child in userdata.iterdir():
            if child.is_dir() and child.name.isdigit():
                cfg = child / "config"
                if cfg.exists():
                    user_dirs.append(cfg)
        return user_dirs

    @staticmethod
    def _coerce_steam_dir(path: Path | None) -> Path | None:
        if not path:
            return None
        # If a file is passed (e.g., steam executable), take parent
        return path.parent if path.is_file() else path

    @classmethod
    def _load_shortcuts(cls, shortcuts_path: Path) -> dict[str, Any]:
        if not shortcuts_path.exists() or shortcuts_path.stat().st_size == 0:
            # Create an empty root object with 'shortcuts' key
            return {"shortcuts": {}}
        data = shortcuts_path.read_bytes()
        root = _BinaryKV.loads(data)
        # Some files are directly the 'shortcuts' object without a wrapper
        if "shortcuts" not in root and all(isinstance(k, str) for k in root.keys()):
            root = {"shortcuts": root}
        if "shortcuts" not in root or not isinstance(root["shortcuts"], dict):
            root["shortcuts"] = {}
        return root

    @classmethod
    def _dump_shortcuts(cls, root: dict[str, Any]) -> bytes:
        # Ensure ordering by numeric key when writing
        shortcuts = root.get("shortcuts", {})
        ordered: dict[str, Any] = {}
        for k in sorted(shortcuts.keys(), key=lambda s: int(s) if s.isdigit() else 0):
            ordered[k] = shortcuts[k]
        wrapped = {"shortcuts": ordered}
        return _BinaryKV.dumps(wrapped)

    @classmethod
    def _build_entry(
        cls,
        appname: str,
        exe: str,
        startdir: str,
        launch_options: str = "",
        icon: str | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        entry: dict[str, Any] = {
            "appname": appname,
            "Exe": exe,
            "StartDir": startdir,
            "LaunchOptions": launch_options,
            **cls.DEFAULT_FIELDS,
        }
        if icon:
            entry["icon"] = icon
        # Tags are a nested object with numeric string keys
        tag_obj: dict[str, Any] = {}
        if tags:
            for i, t in enumerate(tags):
                tag_obj[str(i)] = t
        entry["tags"] = tag_obj
        return entry

    @classmethod
    def _has_duplicate(cls, entry: dict[str, Any], candidate: dict[str, Any]) -> bool:
        # Consider duplicates by matching Exe + LaunchOptions or appname
        if (
            entry.get("Exe", "").strip() == candidate.get("Exe", "").strip()
            and entry.get("LaunchOptions", "").strip()
            == candidate.get("LaunchOptions", "").strip()
        ):
            return True
        if entry.get("appname", "").strip() == candidate.get("appname", "").strip():
            return True
        return False

    @classmethod
    def add_shortcut_for_all_users(
        cls,
        steam_dir: Path,
        appname: str,
        exe: str,
        startdir: str,
        launch_options: str = "",
        icon: str | None = None,
        tags: list[str] | None = None,
    ) -> tuple[bool, str]:
        steam_dir = cls._coerce_steam_dir(steam_dir)
        if not steam_dir or not steam_dir.exists():
            return False, "Steam directory not found"

        user_cfg_dirs = cls._resolve_steam_user_config_dirs(steam_dir)
        if not user_cfg_dirs:
            return False, "No Steam user directories found under userdata"

        updated_any = False
        for cfg_dir in user_cfg_dirs:
            shortcuts_path = cfg_dir / "shortcuts.vdf"
            # Backup existing
            try:
                if shortcuts_path.exists():
                    backup_path = shortcuts_path.with_suffix(".vdf.bak")
                    if not backup_path.exists():
                        shortcuts_path.replace(backup_path)
                        backup_path.replace(shortcuts_path)
            except Exception:
                # Best-effort; continue without blocking if backup fails
                pass

            root = cls._load_shortcuts(shortcuts_path)
            shortcuts: dict[str, Any] = root.get("shortcuts", {})

            # Prepare per-user icon path inside Steam's user config dir so Steam can access it
            icon_for_user: str | None = None
            try:
                if icon:
                    src = Path(icon)
                    if src.exists():
                        ext = src.suffix.lower() or (
                            ".ico" if sys.platform == "win32" else ".png"
                        )
                        dest = cfg_dir / ("me3-manager" + ext)
                        try:
                            shutil.copyfile(src, dest)
                            icon_for_user = str(dest)
                        except Exception:
                            # Fallback: use source path as-is
                            icon_for_user = str(src)
                    else:
                        icon_for_user = None
            except Exception:
                icon_for_user = None

            # Normalize Windows path separators for Steam on Windows
            if icon_for_user and sys.platform == "win32":
                icon_for_user = str(
                    Path(icon_for_user)
                )  # normpath/backslashes on Windows

            # Build candidate entry per user (icon path differs per user)
            candidate = cls._build_entry(
                appname, exe, startdir, launch_options, icon_for_user, tags
            )

            # Check for duplicate
            for _k, v in shortcuts.items():
                if isinstance(v, dict) and cls._has_duplicate(v, candidate):
                    # Already present for this user; skip writing.
                    break
            else:
                # Determine next numeric key
                indices = [int(k) for k in shortcuts.keys() if k.isdigit()]
                next_index = max(indices) + 1 if indices else 0
                shortcuts[str(next_index)] = candidate
                root["shortcuts"] = shortcuts

                data = cls._dump_shortcuts(root)
                # Ensure parent dir exists
                try:
                    cfg_dir.mkdir(parents=True, exist_ok=True)
                    with open(shortcuts_path, "wb") as f:
                        f.write(data)
                    updated_any = True
                except Exception as e:
                    return False, f"Failed to write {shortcuts_path}: {e}"

        if updated_any:
            return True, "Shortcut added. Restart Steam to see it."
        return True, "Shortcut already exists."


def detect_steam_dir_from_path(path: Path | None) -> Path | None:
    """
    Helper to normalize a Steam path that may point to an executable.
    Returns directory or None if invalid.
    """
    if not path:
        return None
    return path.parent if path.is_file() else path
