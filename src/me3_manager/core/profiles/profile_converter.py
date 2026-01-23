"""
ProfileConverter: version-aware normalization and serialization helpers.

Goals:
- Normalize any supported on-disk schema (v1, v2) into a canonical in-memory dict
  used by the app today: { profileVersion, savefile, start_online, disable_arxan,
  natives: [ {path, optional?, initializer?, finalizer?, load_before?, load_after?} ],
  packages: [ {id, path, load_before?, load_after?} ] }
- Serialize canonical dict back to either v1 or v2 TOML payloads.

Assumptions:
- v1: current app schema: globals at root + [[natives]] and [[packages]] sections.
- v2: examples provided use: profileVersion, optional [game] table, and [mods]
  table with flexible dotted keys like "my_dll.initializer.function" or inline table.

This module does NOT do TOML I/O; it only transforms dicts.
"""

from __future__ import annotations

from typing import Any


class ProfileConverter:
    @staticmethod
    def normalize(data: dict[str, Any] | None) -> dict[str, Any]:
        """
        Normalize loaded TOML dict to the canonical internal structure.
        Preserves the declared profileVersion when present.
        """
        if not isinstance(data, dict):
            return {
                "profileVersion": "v1",
                "natives": [],
                "packages": [],
                "supports": [],
            }

        version = str(data.get("profileVersion", "v1")).lower()
        # If a mods table exists, prefer parsing it regardless of declared version
        # to ensure smooth v1<->v2 transitions when only profileVersion is edited.
        if isinstance(data.get("mods"), dict):
            result = ProfileConverter._normalize_v2(data)
            # Preserve declared version
            result["profileVersion"] = data.get("profileVersion", "v1")
            return result

        if version == "v2":
            return ProfileConverter._normalize_v2(data)
        # Default: treat as v1
        return ProfileConverter._normalize_v1(data)

    @staticmethod
    def _normalize_v1(data: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {
            "profileVersion": data.get("profileVersion", "v1"),
            "natives": [],
            "packages": [],
        }

        # Pass through known globals
        for key in ("savefile", "start_online", "disable_arxan", "supports"):
            if key in data:
                result[key] = data.get(key)

        # Natives
        for nat in data.get("natives", []) or []:
            # Check for path or nexus link
            nexus_link = nat.get("nexus_link")

            if isinstance(nat, dict) and (nat.get("path") or nexus_link):
                entry: dict[str, Any] = {}
                if nat.get("path"):
                    entry["path"] = nat.get("path")

                if nexus_link:
                    entry["nexus_link"] = nexus_link

                # Copy known optional fields
                for k in (
                    "enabled",
                    "optional",
                    "load_early",
                    "initializer",
                    "finalizer",
                    "config",
                    "load_before",
                    "load_after",
                ):
                    if k in nat and nat[k] not in (None, []):
                        entry[k] = nat[k]
                result["natives"].append(entry)
            elif isinstance(nat, str):
                result["natives"].append({"path": nat})

        # Packages
        for pkg in data.get("packages", []) or []:
            if isinstance(pkg, dict):
                pkg_id = pkg.get("id")
                # Prefer path over legacy source
                path = pkg.get("path") or pkg.get("source")
                nexus_link = pkg.get("nexus_link")

                # If no ID, derive from path (if available)
                if not pkg_id and path:
                    from pathlib import Path

                    pkg_id = Path(path).name

                # Allow packages with either: (id + path) OR nexus-link
                if pkg_id or nexus_link:
                    entry: dict[str, Any] = {}
                    if pkg_id:
                        entry["id"] = str(pkg_id)
                    if "enabled" in pkg:
                        entry["enabled"] = pkg.get("enabled")

                    if path:
                        entry["path"] = path

                    if nexus_link:
                        entry["nexus_link"] = nexus_link

                    for k in ("load_before", "load_after"):
                        if k in pkg and pkg[k] not in (None, []):
                            entry[k] = pkg[k]
                    result["packages"].append(entry)

        return result

    @staticmethod
    def _normalize_v2(data: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {
            "profileVersion": "v2",
            "natives": [],
            "packages": [],
        }

        # [game] table → root globals
        game_tbl = data.get("game", {}) if isinstance(data.get("game"), dict) else {}
        if "savefile" in game_tbl:
            result["savefile"] = game_tbl.get("savefile")
        if "disable_arxan" in game_tbl:
            result["disable_arxan"] = bool(game_tbl.get("disable_arxan"))
        if "start_online" in game_tbl:
            result["start_online"] = bool(game_tbl.get("start_online"))

        # [mods] table: flat keys or inline tables
        deps = data.get("mods")
        if isinstance(deps, dict):
            # Build per-id accumulator of fields
            accum: dict[str, dict[str, Any]] = {}
            for dep_key, dep_val in deps.items():
                # dep_key like "my_mod.path" or "my_dll" when dep_val is an inline table
                if "." in dep_key:
                    ident, dotted = dep_key.split(".", 1)
                    table = accum.setdefault(ident, {})
                    ProfileConverter._assign_dotted(table, dotted, dep_val)
                else:
                    # Whole inline table for this dependency
                    table = accum.setdefault(dep_key, {})
                    if isinstance(dep_val, dict):
                        # Merge keys possibly including nested dotted fields like initializer.function
                        for k, v in dep_val.items():
                            if isinstance(k, str) and "." in k:
                                ProfileConverter._assign_dotted(table, k, v)
                            else:
                                table[k] = v
                    else:
                        # Unknown scalar; ignore
                        pass

            # Classify each accumulated dependency as native (DLL-like) or package (folder)
            for ident, table in accum.items():
                path = table.get("path")
                if not path or not isinstance(path, str):
                    continue

                # Basic heuristic: .dll paths → native; .me3 or folders → packages
                lower_path = path.lower()
                if lower_path.endswith(".dll"):
                    entry: dict[str, Any] = {"path": path}
                    # optional/disabled are v2 additions; map optional only
                    if table.get("optional") is True:
                        entry["optional"] = True
                    if table.get("load_early") is True:
                        entry["load_early"] = True
                    if table.get("enabled") is False:
                        entry["enabled"] = False
                    # Map initializer/finalizer possibly provided via nested keys
                    if isinstance(table.get("initializer"), dict) or isinstance(
                        table.get("initializer"), str
                    ):
                        entry["initializer"] = table.get("initializer")
                    if isinstance(table.get("finalizer"), dict) or isinstance(
                        table.get("finalizer"), str
                    ):
                        entry["finalizer"] = table.get("finalizer")
                    if table.get("config"):
                        entry["config"] = table.get("config")
                    # Map load order arrays if present
                    for k in ("load_before", "load_after"):
                        if k in table and table[k] not in (None, []):
                            entry[k] = table[k]
                    result["natives"].append(entry)
                else:
                    # Treat everything else as a package-like dependency
                    entry = {
                        "id": ident,
                        "path": path,
                    }
                    if table.get("enabled") is False:
                        entry["enabled"] = False
                    # Disabled flag is v2-specific; we omit entirely if False to match current schema
                    for k in ("load_before", "load_after"):
                        if k in table and table[k] not in (None, []):
                            entry[k] = table[k]
                    result["packages"].append(entry)

        # Fallback: if [mods] is absent but legacy sections exist, keep them
        if not isinstance(deps, dict) and (data.get("natives") or data.get("packages")):
            v1_like = ProfileConverter._normalize_v1(data)
            v1_like["profileVersion"] = "v2"
            return v1_like
        return result

    @staticmethod
    def _assign_dotted(target: dict[str, Any], dotted_key: str, value: Any) -> None:
        """
        Assign a dotted key into a nested dict structure, e.g. "initializer.delay.ms".
        """
        parts = dotted_key.split(".")
        current = target
        for part in parts[:-1]:
            nxt = current.get(part)
            if not isinstance(nxt, dict):
                nxt = {}
                current[part] = nxt
            current = nxt
        current[parts[-1]] = value

    @staticmethod
    def to_v1(data: dict[str, Any]) -> dict[str, Any]:
        """Return a v1-shaped dict from canonical data (no I/O)."""
        # v1 matches the canonical layout already
        result = ProfileConverter._normalize_v1(data)
        result["profileVersion"] = "v1"
        return result

    @staticmethod
    def to_v2(data: dict[str, Any], game_name: str | None = None) -> dict[str, Any]:
        """
        Return a v2-shaped dict from canonical data, building [game] and [mods].
        """
        base: dict[str, Any] = {"profileVersion": "v2"}

        # [game]
        game_tbl: dict[str, Any] = {}
        if data.get("savefile"):
            game_tbl["savefile"] = data["savefile"]
        if "disable_arxan" in data:
            game_tbl["disable_arxan"] = bool(data["disable_arxan"])
        if "start_online" in data:
            game_tbl["start_online"] = bool(data["start_online"])
        if game_name:
            # Optionally set launch to a slug if provided
            # Keep simple: remove spaces, lowercase
            slug = "".join(ch for ch in game_name.lower() if ch.isalnum())
            if slug:
                game_tbl["launch"] = slug
        if game_tbl:
            base["game"] = game_tbl

        # [mods]
        deps: dict[str, Any] = {}

        # Natives as mods with path and optional advanced options
        for nat in data.get("natives", []) or []:
            if not isinstance(nat, dict) or not nat.get("path"):
                continue
            # Use file stem as identifier if possible; fall back to sanitized key
            identifier = (
                ProfileConverter._derive_identifier_from_path(nat["path"]) or "native"
            )
            # Build inline table with possible dotted nested fields
            inline: dict[str, Any] = {"path": nat["path"]}
            if nat.get("enabled") is False:
                inline["enabled"] = False
            if nat.get("optional") is True:
                inline["optional"] = True
            if nat.get("load_early") is True:
                inline["load_early"] = True
            if nat.get("initializer") is not None:
                inline["initializer"] = nat["initializer"]
            if nat.get("finalizer") is not None:
                inline["finalizer"] = nat["finalizer"]
            if nat.get("config"):
                inline["config"] = nat["config"]
            # Load order arrays
            for k in ("load_before", "load_after"):
                if k in nat and nat[k] not in (None, []):
                    inline[k] = nat[k]
            # Store as whole inline table under key
            deps[identifier] = inline

        # Packages as mods by id
        for pkg in data.get("packages", []) or []:
            if not isinstance(pkg, dict) or not pkg.get("id") or not pkg.get("path"):
                continue
            ident = str(pkg["id"])
            inline = {"path": pkg["path"]}
            if pkg.get("enabled") is False:
                inline["enabled"] = False
            for k in ("load_before", "load_after"):
                if k in pkg and pkg[k] not in (None, []):
                    inline[k] = pkg[k]
            deps[ident] = inline

        if deps:
            base["mods"] = deps

        return base

    @staticmethod
    def _derive_identifier_from_path(path_str: str) -> str:
        try:
            import os

            stem = os.path.splitext(os.path.basename(path_str))[0]
            ident = "".join(ch for ch in stem if ch.isalnum() or ch in ("_", "-"))
            return ident or stem
        except Exception:
            return ""
