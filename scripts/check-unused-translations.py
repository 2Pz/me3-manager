#!/usr/bin/env python3
"""
Find translation keys in resources/translations/*.json that are not referenced by the codebase.

Default behavior:
- Scans Python source for calls like tr("some_key") and *.tr("some_key") where the key is a literal string.
- Compares those "used keys" to keys present in translation JSON files.
- If unused keys are found, prompts whether to delete them (from ALL translation JSON files).
- Runs scripts/sync-translations.py afterwards (unless --no-sync).

Usage (from project root):
  python scripts/check-unused-translations.py
  uv run python scripts/check-unused-translations.py

Non-interactive / CI:
  python scripts/check-unused-translations.py --delete --yes
  python scripts/check-unused-translations.py --check-only

Enhanced options:
  python scripts/check-unused-translations.py --check-only --group    # Group unused keys by prefix
  python scripts/check-unused-translations.py --check-only --verbose  # Show where used keys are found
  python scripts/check-unused-translations.py --check-only --all      # Show all unused keys (no limit)
"""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def iter_python_files(paths: Iterable[Path]) -> Iterable[Path]:
    for base in paths:
        if not base.exists():
            continue
        if base.is_file() and base.suffix == ".py":
            yield base
            continue
        for p in base.rglob("*.py"):
            # Skip common noisy dirs even if present in repo
            parts = set(p.parts)
            if {"__pycache__", ".venv", "venv", "dist", "build"} & parts:
                continue
            yield p


class _TrKeyCollector(ast.NodeVisitor):
    """
    Collects translation keys from:
      - tr("key", ...)
      - something.tr("key", ...)
    when the first positional argument is a literal string.

    Also collects *any* string literal in code that exactly matches a known
    translation key. This avoids false "unused" reports for code that passes
    translation keys through helpers (e.g. add_stat_row("nexus_endorsements_label", ...)).

    Tracks file path and line numbers for verbose output.
    """

    def __init__(self, known_keys: set[str], file_path: Path) -> None:
        self._known_keys = known_keys
        self._file_path = file_path
        self.keys: set[str] = set()
        # Maps key -> list of (file, line) tuples
        self.key_locations: dict[str, list[tuple[Path, int]]] = defaultdict(list)

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802 (ast API)
        func = node.func

        is_tr_call = isinstance(func, ast.Name) and func.id == "tr"
        is_attr_tr_call = isinstance(func, ast.Attribute) and func.attr == "tr"

        if (is_tr_call or is_attr_tr_call) and node.args:
            first = node.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                self.keys.add(first.value)
                self.key_locations[first.value].append((self._file_path, first.lineno))

        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:  # noqa: N802 (ast API)
        if isinstance(node.value, str) and node.value in self._known_keys:
            self.keys.add(node.value)
            self.key_locations[node.value].append((self._file_path, node.lineno))
        self.generic_visit(node)


def collect_used_translation_keys(
    py_files: Iterable[Path], known_keys: set[str], verbose: bool = False
) -> tuple[set[str], dict[str, list[tuple[Path, int]]]]:
    """
    Collect used translation keys and optionally their locations.

    Returns:
        Tuple of (used_keys set, key_locations dict mapping key -> [(file, line), ...])
    """
    used: set[str] = set()
    all_locations: dict[str, list[tuple[Path, int]]] = defaultdict(list)

    for path in py_files:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            # Fallback for odd encodings; we only care about string literals,
            # so ignore bad bytes.
            text = path.read_text(encoding="utf-8", errors="ignore")

        try:
            tree = ast.parse(text, filename=str(path))
        except SyntaxError:
            # If any file can't be parsed (unlikely), skip it rather than failing.
            continue

        v = _TrKeyCollector(known_keys=known_keys, file_path=path)
        v.visit(tree)
        used |= v.keys
        if verbose:
            for key, locs in v.key_locations.items():
                all_locations[key].extend(locs)

    # Keys referenced directly in code without tr("...") calls.
    used.add("language_name")

    return used, all_locations


def load_json(path: Path) -> dict[str, object]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object at the top level.")
    return data


def save_json(path: Path, data: dict[str, object]) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def list_translation_files(translations_dir: Path) -> list[Path]:
    if not translations_dir.exists():
        return []
    return sorted(translations_dir.glob("*.json"))


def prompt_yes_no(question: str, default_no: bool = True) -> bool:
    suffix = " [y/N] " if default_no else " [Y/n] "
    ans = input(question + suffix).strip().lower()
    if ans == "":
        return not default_no
    return ans in {"y", "yes"}


def run_sync_script(root: Path) -> int:
    sync_script = root / "scripts" / "sync-translations.py"
    if not sync_script.exists():
        print(f"Sync script not found: {sync_script}", file=sys.stderr)
        return 2

    print("\nRunning translation sync...")
    proc = subprocess.run([sys.executable, str(sync_script)], cwd=str(root))
    return int(proc.returncode)


def get_key_prefix(key: str) -> str:
    """Extract prefix from a translation key (text before first underscore)."""
    if "_" in key:
        return key.split("_")[0]
    return key


def print_grouped_keys(keys: list[str], root: Path) -> None:
    """Print keys grouped by their prefix for easier review."""
    grouped: dict[str, list[str]] = defaultdict(list)
    for key in keys:
        prefix = get_key_prefix(key)
        grouped[prefix].append(key)

    # Sort groups by size (largest first) for better visibility
    sorted_groups = sorted(grouped.items(), key=lambda x: (-len(x[1]), x[0]))

    for prefix, group_keys in sorted_groups:
        print(f"\n  [{prefix}] ({len(group_keys)} keys)")
        for k in sorted(group_keys):
            print(f"    - {k}")


def print_flat_keys(keys: list[str], limit: int | None = None) -> None:
    """Print keys in a flat list."""
    display_keys = keys if limit is None else keys[:limit]
    for k in display_keys:
        print(f"  - {k}")
    if limit and len(keys) > limit:
        print(f"  ... and {len(keys) - limit} more (use --all to show all)")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Check for unused translation keys in resources/translations/*.json"
    )
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Delete unused keys (otherwise just report). If not provided, you will be prompted when unused keys exist.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Assume 'yes' for prompts (only meaningful with --delete).",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Only check/report; do not prompt and do not delete keys.",
    )
    parser.add_argument(
        "--no-sync",
        action="store_true",
        help="Do not run scripts/sync-translations.py after the check (or deletion).",
    )
    parser.add_argument(
        "--paths",
        nargs="*",
        default=["src", "scripts"],
        help="Paths (relative to repo root) to scan for tr('key') usages. Defaults to: src scripts",
    )
    parser.add_argument(
        "--group",
        action="store_true",
        help="Group unused keys by prefix (e.g., 'nexus_', 'import_') for easier review.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Show all unused keys instead of limiting to 50.",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show where each used key is referenced in the code.",
    )

    args = parser.parse_args(argv)

    if args.check_only:
        # "Check-only" should not mutate the repo (sync script writes files).
        args.no_sync = True

    root = repo_root()
    translations_dir = root / "resources" / "translations"
    translation_files = list_translation_files(translations_dir)

    if not translation_files:
        print(f"No translation files found in: {translations_dir}")
        return 1

    # Use English as the authoritative set of possible keys.
    master_en = translations_dir / "en.json"
    if not master_en.exists():
        print(f"Master translation file not found: {master_en}", file=sys.stderr)
        return 1
    known_keys = set(load_json(master_en).keys())

    scan_paths = [root / p for p in args.paths]
    used_keys, key_locations = collect_used_translation_keys(
        iter_python_files(scan_paths), known_keys, verbose=args.verbose
    )

    all_keys: set[str] = set()
    per_file_keys: dict[Path, set[str]] = {}
    for f in translation_files:
        data = load_json(f)
        keys = set(data.keys())
        per_file_keys[f] = keys
        all_keys |= keys

    unused_keys = sorted(all_keys - used_keys)

    print(f"Translation files: {len(translation_files)}")
    print(f"Keys referenced in code (static): {len(used_keys)}")
    print(f"Keys present in translation JSONs: {len(all_keys)}")
    print(f"Unused keys found: {len(unused_keys)}")

    if unused_keys:
        if args.group:
            print_grouped_keys(unused_keys, root)
        else:
            limit = None if args.all else 50
            print_flat_keys(unused_keys, limit)

    # Verbose mode: show where used keys are found
    if args.verbose and key_locations:
        print(f"\n{'=' * 60}")
        print("Used keys and their locations:")
        print(f"{'=' * 60}")
        for key in sorted(key_locations.keys()):
            locs = key_locations[key]
            print(f"\n  {key}")
            for file_path, line in locs[:5]:  # Limit to 5 locations per key
                rel_path = file_path.relative_to(root)
                print(f"    └─ {rel_path}:{line}")
            if len(locs) > 5:
                print(f"    └─ ... and {len(locs) - 5} more locations")

    # Decide whether to delete
    do_delete = False
    if unused_keys and not args.check_only:
        if args.delete and args.yes:
            do_delete = True
        elif args.delete:
            do_delete = prompt_yes_no(
                "\nDelete these "
                f"{len(unused_keys)} unused key(s) from ALL translation files?",
                default_no=True,
            )
        else:
            do_delete = prompt_yes_no(
                "\nUnused keys detected. Delete them from ALL translation files?",
                default_no=True,
            )

    if do_delete:
        changed_files: list[Path] = []
        for f in translation_files:
            data = load_json(f)
            before = set(data.keys())
            for k in unused_keys:
                data.pop(k, None)
            after = set(data.keys())
            if after != before:
                save_json(f, data)
                changed_files.append(f)

        print(f"\nDeleted {len(unused_keys)} key(s) from {len(changed_files)} file(s).")

    if not args.no_sync:
        rc = run_sync_script(root)
        if rc != 0:
            return rc

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
