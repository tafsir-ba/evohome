#!/usr/bin/env python3
"""
Copy MongoDB data from a source cluster to the DigitalOcean / Atlas target.

Typical use — copy Gantt data from evohome into crc (same cluster, keep crc rows):

  export SOURCE_MONGO_URL='mongodb+srv://USER:PASS@cluster/...'
  export TARGET_MONGO_URL="$SOURCE_MONGO_URL"
  export SOURCE_DB_NAME='evohome'
  export TARGET_DB_NAME='crc'
  export CONFIRM_TARGET='yes'

  python backend/scripts/migrate_mongo.py --profile crc --dry-run
  python backend/scripts/migrate_mongo.py --profile crc
  # Do NOT use --drop-target if crc already has data you want to keep.

On DigitalOcean App Platform (no droplet / SSH), use the HTTP endpoint instead —
see DEPLOYMENT.md section "Migrate via App Platform".

Profiles:
  crc   — users + gantt collections (Caribbean RE-Connect site)
  full  — every collection in the source database
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Allow `python backend/scripts/migrate_mongo.py` from repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.mongo_migrate import run_migration


def _require_env(name: str) -> str:
    value = (os.environ.get(name) or "").strip()
    if not value:
        print(f"ERROR: {name} is required", file=sys.stderr)
        sys.exit(1)
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate MongoDB data to DO/Atlas target")
    parser.add_argument(
        "--profile",
        choices=("crc", "full"),
        default="crc",
        help="crc = users + gantt only; full = all source collections",
    )
    parser.add_argument("--dry-run", action="store_true", help="Report counts only")
    parser.add_argument(
        "--drop-target",
        action="store_true",
        help="Drop each target collection before copy (destructive — avoid if crc has data)",
    )
    args = parser.parse_args()

    source_url = _require_env("SOURCE_MONGO_URL")
    target_url = _require_env("TARGET_MONGO_URL")
    source_db_name = _require_env("SOURCE_DB_NAME")
    target_db_name = _require_env("TARGET_DB_NAME")

    if not args.dry_run and os.environ.get("CONFIRM_TARGET", "").strip().lower() != "yes":
        print(
            "ERROR: Set CONFIRM_TARGET=yes to write to the target database.",
            file=sys.stderr,
        )
        return 1

    try:
        report = run_migration(
            mongo_url=source_url,
            target_mongo_url=target_url,
            source_db_name=source_db_name,
            target_db_name=target_db_name,
            profile=args.profile,
            dry_run=args.dry_run,
            drop_target=args.drop_target,
        )
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"Source: {report['source_db']}")
    print(f"Target: {report['target_db']}")
    print(f"Profile: {report['profile']} | dry_run={report['dry_run']}")
    if report.get("missing_collections"):
        for name in report["missing_collections"]:
            print(f"WARN: source has no collection '{name}' — skipping")
    print("-" * 72)

    for result in report["collections"]:
        skip_note = ""
        if result.get("merged_skipped"):
            skip_note = f" merge_skipped={result['merged_skipped']}"
        status = "skip" if result.get("dry_run") else "ok"
        print(
            f"[{status}] {result['collection']}: source={result['source']} "
            f"target_before={result['target_before']} "
            f"copied={result['copied']}{skip_note} target_after={result['target_after']}"
        )

    print("-" * 72)
    if args.dry_run:
        print("Dry run complete. Re-run with CONFIRM_TARGET=yes and without --dry-run to copy.")
    else:
        print("Migration complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
