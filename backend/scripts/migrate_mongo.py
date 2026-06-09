#!/usr/bin/env python3
"""
Copy MongoDB data from a source cluster to the DigitalOcean / Atlas target.

Typical use (Emergent or legacy app.carib-recon.org → DO squid-app):

  export SOURCE_MONGO_URL='mongodb+srv://USER:PASS@source-cluster/...'
  export SOURCE_DB_NAME='evohome'
  export TARGET_MONGO_URL='mongodb+srv://USER:PASS@target-cluster/...'
  export TARGET_DB_NAME='evohome'
  export CONFIRM_TARGET='yes'

  python backend/scripts/migrate_mongo.py --profile crc

Profiles:
  crc   — users + gantt collections (Caribbean RE-Connect site)
  full  — every collection in the source database

Dry run (counts only, no writes):

  python backend/scripts/migrate_mongo.py --profile crc --dry-run
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import Iterable

from pymongo import MongoClient
from pymongo.errors import BulkWriteError

CRC_COLLECTIONS = (
    "users",
    "gantt_projects",
    "gantt_tasks",
    "gantt_audit_logs",
    "gantt_extraction_drafts",
    "gantt_uploaded_files",
)


def _require_env(name: str) -> str:
    value = (os.environ.get(name) or "").strip()
    if not value:
        print(f"ERROR: {name} is required", file=sys.stderr)
        sys.exit(1)
    return value


def _batch(iterable: Iterable, size: int = 500):
    batch = []
    for item in iterable:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def copy_collection(source_db, target_db, name: str, *, dry_run: bool, drop_target: bool) -> dict:
    src = source_db[name]
    tgt = target_db[name]
    source_count = src.count_documents({})
    target_before = tgt.count_documents({})

    if dry_run:
        return {
            "collection": name,
            "source": source_count,
            "target_before": target_before,
            "copied": 0,
            "target_after": target_before,
            "skipped": True,
        }

    if drop_target and target_before:
        tgt.drop()
        target_before = 0

    copied = 0
    for chunk in _batch(src.find({}), 500):
        try:
            if chunk:
                tgt.insert_many(chunk, ordered=False)
                copied += len(chunk)
        except BulkWriteError as exc:
            # Partial success on duplicate _id when not dropping target
            copied += exc.details.get("nInserted", 0)

    target_after = tgt.count_documents({})
    return {
        "collection": name,
        "source": source_count,
        "target_before": target_before,
        "copied": copied,
        "target_after": target_after,
        "skipped": False,
    }


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
        help="Drop each target collection before copy (recommended for clean migrate)",
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

    source_client = MongoClient(source_url, serverSelectionTimeoutMS=15000)
    target_client = MongoClient(target_url, serverSelectionTimeoutMS=15000)

    source_client.admin.command("ping")
    target_client.admin.command("ping")

    source_db = source_client[source_db_name]
    target_db = target_client[target_db_name]

    if args.profile == "full":
        collections = sorted(source_db.list_collection_names())
    else:
        existing = set(source_db.list_collection_names())
        collections = [c for c in CRC_COLLECTIONS if c in existing]
        missing = [c for c in CRC_COLLECTIONS if c not in existing]
        for name in missing:
            print(f"WARN: source has no collection '{name}' — skipping")

    if not collections:
        print("ERROR: no collections to migrate", file=sys.stderr)
        return 1

    print(f"Source: {source_db_name} @ {source_url.split('@')[-1]}")
    print(f"Target: {target_db_name} @ {target_url.split('@')[-1]}")
    print(f"Profile: {args.profile} | collections: {', '.join(collections)}")
    mode = "DRY RUN" if args.dry_run else "COPY"
    drop_note = " + drop target" if args.drop_target else ""
    print(f"Mode: {mode}{drop_note}")
    print("-" * 72)

    results = []
    for name in collections:
        result = copy_collection(
            source_db,
            target_db,
            name,
            dry_run=args.dry_run,
            drop_target=args.drop_target,
        )
        results.append(result)
        status = "skip" if result["skipped"] else "ok"
        print(
            f"[{status}] {name}: source={result['source']} "
            f"target_before={result['target_before']} "
            f"copied={result['copied']} target_after={result['target_after']}"
        )

    print("-" * 72)
    if args.dry_run:
        print("Dry run complete. Re-run with CONFIRM_TARGET=yes and without --dry-run to copy.")
    else:
        print("Migration complete. Redeploy squid-app backend if it was already running.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
