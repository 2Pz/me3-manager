from __future__ import annotations

import shutil
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from me3_manager.core.profiles.profile_manager import ProfileManager
from me3_manager.core.profiles.toml_profile_writer import TomlProfileWriter


class ExportService:
    """Create a portable archive of the current profile and its referenced mods."""

    @staticmethod
    def _rel_to_mods(path_str: str, mods_dir: Path, mods_dir_name: str | None) -> Path:
        """Return path relative to mods_dir. Handles absolute paths and mods_dir_name stripping."""
        p = Path(path_str)
        if p.is_absolute():
            try:
                return p.resolve().relative_to(mods_dir.resolve())
            except Exception:
                return Path(p.name)
        # relative path
        parts = p.parts
        if mods_dir_name and parts and parts[0] == mods_dir_name:
            return Path(*parts[1:]) if len(parts) > 1 else Path("")
        return p

    @staticmethod
    def _sanitize_profile_for_export(
        profile_data: dict[str, Any], mods_dir: Path, mods_dir_name: str | None
    ) -> dict[str, Any]:
        """
        Return a profile dict with all path-like fields made relative to export root.
        - packages[*].path => top-level folder name (relative to mods root)
        - natives[*].path => relative path under mods root
        """
        data = {
            "profileVersion": profile_data.get("profileVersion", "v1"),
        }

        # Optional globals
        if profile_data.get("savefile"):
            data["savefile"] = profile_data["savefile"]
        if "start_online" in profile_data:
            data["start_online"] = profile_data["start_online"]
        if "disable_arxan" in profile_data:
            data["disable_arxan"] = profile_data["disable_arxan"]

        # Natives (files)
        natives = []
        for native in profile_data.get("natives", []):
            if isinstance(native, dict) and native.get("path"):
                rel_path = ExportService._rel_to_mods(
                    native["path"], mods_dir, mods_dir_name
                )
                rel = rel_path.as_posix()
                # Expectation in export: everything is under 'mods/'
                entry: dict[str, Any] = {"path": f"mods/{rel}"}
                if native.get("optional") is True:
                    entry["optional"] = True
                if native.get("load_before"):
                    entry["load_before"] = native["load_before"]
                if native.get("load_after"):
                    entry["load_after"] = native["load_after"]
                if native.get("initializer"):
                    entry["initializer"] = native["initializer"]
                if native.get("finalizer"):
                    entry["finalizer"] = native["finalizer"]
                if native.get("config"):
                    # Relativize config path if under mods_dir, otherwise keep original
                    raw_cfgs = native["config"]
                    if isinstance(raw_cfgs, str):
                        raw_cfgs = [raw_cfgs]

                    new_cfgs = []
                    for raw_cfg in raw_cfgs:
                        try:
                            rel_cfg = ExportService._rel_to_mods(
                                raw_cfg, mods_dir, mods_dir_name
                            )

                            if (
                                Path(raw_cfg).is_absolute()
                                and rel_cfg.as_posix() != Path(raw_cfg).name
                            ):
                                new_cfgs.append(f"mods/{rel_cfg.as_posix()}")
                            else:
                                new_cfgs.append(raw_cfg)
                        except Exception:
                            new_cfgs.append(raw_cfg)

                    # Return single string if input was single string, else list
                    if isinstance(native["config"], str) and len(new_cfgs) == 1:
                        entry["config"] = new_cfgs[0]
                    else:
                        entry["config"] = new_cfgs
                natives.append(entry)
            elif isinstance(native, str):
                rel_path = ExportService._rel_to_mods(native, mods_dir, mods_dir_name)
                natives.append({"path": f"mods/{rel_path.as_posix()}"})
        if natives:
            data["natives"] = natives

        # Packages (folders)
        packages = []
        for package in profile_data.get("packages", []):
            if not isinstance(package, dict):
                continue
            pkg = {}
            if package.get("id"):
                pkg["id"] = package["id"]
            # Prefer 'path', fallback to legacy 'source'
            raw_path = package.get("path") or package.get("source")
            if raw_path:
                # Use shared logic to find relative path; taking the top-level folder
                rel = ExportService._rel_to_mods(raw_path, mods_dir, mods_dir_name)
                top = rel.parts[0] if rel.parts else rel.as_posix()
                pkg["path"] = f"mods/{top}"

            if package.get("load_before"):
                pkg["load_before"] = package["load_before"]
            if package.get("load_after"):
                pkg["load_after"] = package["load_after"]
            if pkg:
                packages.append(pkg)
        if packages:
            data["packages"] = packages

        return data

    @staticmethod
    def _append_note_preserving_line_ending(line: str, note: str) -> str:
        """Append a note to a line while preserving its original line ending."""
        if line.endswith("\r\n"):
            return line[:-2] + note + "\r\n"
        elif line.endswith("\n"):
            return line[:-1] + note + "\n"
        else:
            return line + note

    @staticmethod
    def export_profile_and_mods(
        *,
        game_name: str,
        config_manager,
        destination_zip: Path,
    ) -> tuple[bool, str]:
        """
        Build an export .zip containing referenced mods and a sanitized profile.
        The archive layout:
          <root>/[package folders and/or native files]
          <root>/<profile_name>.me3
        """
        try:
            profile_path = config_manager.get_profile_path(game_name)
            mods_dir = config_manager.get_mods_dir(game_name)
            try:
                mods_dir_name = config_manager.get_game_mods_dir_name(game_name)
            except Exception:
                mods_dir_name = None
            if not profile_path.exists():
                return False, "Profile not found"
            profile_data = ProfileManager.read_profile(profile_path)

            sanitized = ExportService._sanitize_profile_for_export(
                profile_data, mods_dir, mods_dir_name
            )

            # Collect referenced source items from original profile data
            package_sources: list[tuple[Path, str]] = []  # (src_folder, dest_name)
            external_packages: list[
                tuple[str, str]
            ] = []  # (expected_mods_path, original)

            for pkg in profile_data.get("packages", []):
                if not isinstance(pkg, dict):
                    continue
                raw_path = pkg.get("path") or pkg.get("source")
                if not raw_path:
                    continue

                # Check for external paths (absolute and outside mods_dir)
                p = Path(raw_path)
                if p.is_absolute():
                    try:
                        p.resolve().relative_to(mods_dir.resolve())
                    except Exception:
                        external_packages.append((f"mods/{p.name}", str(p)))
                        continue

                # Resolved relative path inside mods directory
                rel = ExportService._rel_to_mods(raw_path, mods_dir, mods_dir_name)
                if not rel.parts or str(rel) == ".":
                    continue

                root_name = rel.parts[0]
                src_folder = (mods_dir / root_name).resolve()
                package_sources.append((src_folder, root_name))

            native_sources: list[tuple[Path, Path]] = []  # (src_file, dest_rel)
            external_natives: list[
                tuple[str, str]
            ] = []  # (expected_mods_path, original)

            for nat in profile_data.get("natives", []):
                raw_path = nat.get("path") if isinstance(nat, dict) else nat
                if not raw_path:
                    continue

                p = Path(raw_path)
                if p.is_absolute():
                    try:
                        p.resolve().relative_to(mods_dir.resolve())
                    except Exception:
                        external_natives.append((f"mods/{p.name}", str(p)))
                        continue

                rel = ExportService._rel_to_mods(raw_path, mods_dir, mods_dir_name)
                src_file = (mods_dir / rel).resolve()
                native_sources.append((src_file, rel))

            # Create build tree and zip
            with TemporaryDirectory() as tmp_dir:
                tmp_root = Path(tmp_dir)

                # Copy packages to mods/<dest_name>
                for src_folder, dest_name in package_sources:
                    if src_folder.exists() and src_folder.is_dir():
                        (tmp_root / "mods").mkdir(parents=True, exist_ok=True)
                        shutil.copytree(
                            src_folder,
                            tmp_root / "mods" / dest_name,
                            symlinks=False,
                            ignore_dangling_symlinks=True,
                        )

                # Copy native files that are not already inside a copied package
                for src_file, dest_rel in native_sources:
                    try:
                        # If the native is inside one of the copied package folders, skip it
                        if any(
                            src_folder in src_file.resolve().parents
                            for src_folder, _ in package_sources
                        ):
                            continue
                    except Exception:
                        pass
                    if src_file.exists() and src_file.is_file():
                        (tmp_root / "mods").mkdir(parents=True, exist_ok=True)
                        target = tmp_root / "mods" / dest_rel
                        target.parent.mkdir(parents=True, exist_ok=True)
                        if src_file.resolve() == target.resolve():
                            # Avoid copying a file onto itself
                            continue
                        shutil.copy2(src_file, target)

                        # Also include associated config folder and files next to the DLL
                        try:
                            stem = src_file.stem
                            src_dir = src_file.parent
                            # 1) Config folder with same stem
                            cfg_dir = src_dir / stem
                            if cfg_dir.is_dir():
                                dst_cfg_dir = target.parent / stem
                                if not dst_cfg_dir.exists():
                                    shutil.copytree(
                                        cfg_dir,
                                        dst_cfg_dir,
                                        symlinks=False,
                                        ignore_dangling_symlinks=True,
                                    )
                            # 2) Common config files with same stem
                            for ext in (".ini", ".cfg", ".toml", ".json"):
                                src_cfg = src_dir / f"{stem}{ext}"
                                if src_cfg.is_file():
                                    dst_cfg = target.parent / src_cfg.name
                                    if not (
                                        dst_cfg.exists()
                                        and dst_cfg.resolve() == src_cfg.resolve()
                                    ):
                                        shutil.copy2(src_cfg, dst_cfg)
                        except Exception:
                            pass

                # Ensure mods/ exists so it appears in the archive even if empty
                (tmp_root / "mods").mkdir(parents=True, exist_ok=True)

                # Write sanitized profile (and prepend external notes)
                out_profile = tmp_root / profile_path.name
                TomlProfileWriter.write_profile(out_profile, sanitized, game_name)
                if external_packages or external_natives:
                    try:
                        text = out_profile.read_text(encoding="utf-8")
                        inline_note = " # Missing content not included in export"
                        # Build set of expected missing 'mods/...' paths
                        missing_paths = {
                            p for (p, _orig) in (external_packages + external_natives)
                        }

                        # Prefer inline note on the specific missing entry lines
                        is_v2 = (
                            "\n[mods]\n" in text
                            or text.strip().startswith("[mods]\n")
                            or "\n[mods]\r\n" in text
                        )
                        lines = text.splitlines(True)  # keep line endings
                        modified = False

                        if is_v2:
                            # Scan lines under [mods] and annotate the ones whose path matches a missing path
                            in_mods = False
                            for i, ln in enumerate(lines):
                                stripped = ln.strip()
                                if stripped.startswith("[") and stripped == "[mods]":
                                    in_mods = True
                                    continue
                                if stripped.startswith("[") and stripped != "[mods]":
                                    if in_mods:
                                        in_mods = False
                                if not in_mods:
                                    continue
                                # Look for path = "..."
                                comp = stripped.replace(" ", "")
                                for miss in list(missing_paths):
                                    # Match either inline table {path="..."} or dotted key ident.path="..."
                                    if (f'path="{miss}"' in comp) or (
                                        f'.path="{miss}"' in comp
                                    ):
                                        # Append inline note once
                                        if inline_note.strip() not in stripped:
                                            lines[i] = (
                                                ExportService._append_note_preserving_line_ending(
                                                    ln, inline_note
                                                )
                                            )
                                            modified = True
                                        missing_paths.remove(miss)
                                        break
                        else:
                            # v1: annotate matching path lines inside [[natives]]/[[packages]] tables
                            for i, ln in enumerate(lines):
                                stripped = ln.strip()
                                if not stripped or stripped.startswith("#"):
                                    continue
                                for miss in list(missing_paths):
                                    if (
                                        stripped.startswith("path = ")
                                        and f'"{miss}"' in stripped
                                    ):
                                        if inline_note.strip() not in stripped:
                                            lines[i] = (
                                                ExportService._append_note_preserving_line_ending(
                                                    ln, inline_note
                                                )
                                            )
                                            modified = True
                                        missing_paths.remove(miss)
                                        break

                        if modified:
                            out_profile.write_text("".join(lines), encoding="utf-8")
                        else:
                            # Fallback: Add a single header/footer note
                            note_line = "# Missing content not included in export"
                            insert_pos = text.find("[[")
                            if insert_pos == -1:
                                if not text.endswith("\n\n"):
                                    text = text.rstrip("\n") + "\n\n"
                                new_text = text + note_line + "\n"
                            else:
                                before = text[:insert_pos]
                                after = text[insert_pos:]
                                if not before.endswith("\n\n"):
                                    if before.endswith("\n"):
                                        before = before + "\n"
                                    else:
                                        before = before + "\n\n"
                                new_text = before + note_line + "\n" + after
                            out_profile.write_text(new_text, encoding="utf-8")
                    except Exception:
                        pass

                # Zip the export
                destination_zip.parent.mkdir(parents=True, exist_ok=True)
                with zipfile.ZipFile(destination_zip, "w", zipfile.ZIP_DEFLATED) as zf:
                    # Add explicit directory entry for mods/
                    zf.writestr("mods/", "")
                    for item in tmp_root.rglob("*"):
                        if item.is_file():
                            zf.write(
                                item, arcname=item.relative_to(tmp_root).as_posix()
                            )

            return True, ""
        except Exception as e:
            return False, str(e)
