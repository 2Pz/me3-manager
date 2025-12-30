"""
Test Nexus API parsing against real responses.

Uses the SAME saved Nexus API key as the app (stored in manager settings).

Usage (PowerShell):
  uv run python scripts/test_nexus_api_parse.py --game eldenringnightreign --mods 78 146

Optional override:
  uv run python scripts/test_nexus_api_parse.py --api-key "..." --game eldenringnightreign --mods 78
"""

from __future__ import annotations

import argparse
import json

from me3_manager.services.nexus_service import NexusService


def _load_saved_api_key() -> str | None:
    try:
        from me3_manager.core.config_facade import ConfigFacade

        cfg = ConfigFacade()
        return cfg.get_nexus_api_key()
    except Exception:
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--game", required=True, help="Nexus game domain, e.g. eldenringnightreign"
    )
    ap.add_argument(
        "--mods", nargs="+", type=int, required=True, help="One or more mod ids"
    )
    ap.add_argument(
        "--api-key",
        default=None,
        help="Optional override API key (otherwise uses saved app key)",
    )
    ap.add_argument(
        "--dump-raw",
        action="store_true",
        help="Dump raw JSON payload keys for the mod endpoint (no API key printed)",
    )
    args = ap.parse_args()

    api_key = (args.api_key or _load_saved_api_key() or "").strip()
    if not api_key:
        print(
            "Missing Nexus API key. Add it in-app (Settings → Nexus Mods) or pass --api-key."
        )
        return 2

    svc = NexusService(api_key)
    user = svc.validate_user()
    print(f"OK: authenticated as {user.name or '(unknown)'}")

    for mod_id in args.mods:
        mod = svc.get_mod(args.game, mod_id)
        files = svc.get_mod_files(args.game, mod_id)
        latest = svc.pick_latest_main_file(files)

        print("\n---")
        print(f"mod_id: {mod_id}")
        print(
            json.dumps(
                {
                    "name": mod.name,
                    "author": mod.author,
                    "version": mod.version,
                    "endorsements": mod.endorsement_count,
                    "unique_downloads": mod.unique_downloads,
                    "total_downloads": mod.total_downloads,
                    "picture_url": mod.picture_url,
                },
                indent=2,
                ensure_ascii=False,
            )
        )

        if latest:
            print(
                json.dumps(
                    {
                        "file_id": latest.file_id,
                        "file_name": latest.name,
                        "file_version": latest.version,
                        "file_size_kb": latest.size_kb,
                        "category": latest.category_name,
                        "uploaded_timestamp": latest.uploaded_timestamp,
                    },
                    indent=2,
                    ensure_ascii=False,
                )
            )
        else:
            print("No files found.")

        if args.dump_raw:
            # Re-fetch raw to inspect keys quickly
            raw = svc._request("GET", f"/games/{args.game}/mods/{mod_id}")
            print("raw_keys:", sorted(list(raw.keys())))
            for k in ("stats", "statistics", "downloads"):
                if isinstance(raw.get(k), dict):
                    print(f"{k}_keys:", sorted(list(raw[k].keys())))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
