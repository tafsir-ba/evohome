"""Merge MongoDB collections (evohome → crc) — used by CLI script and one-shot API."""
from __future__ import annotations

from typing import Iterable, Literal

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

MERGE_KEY_FIELDS = {
    "users": "user_id",
    "gantt_projects": "gantt_project_id",
    "gantt_tasks": "task_id",
    "gantt_extraction_drafts": "draft_id",
    "gantt_uploaded_files": "file_id",
}

Profile = Literal["crc", "full"]


def _batch(iterable: Iterable, size: int = 500):
    batch = []
    for item in iterable:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def _existing_keys(tgt, field: str) -> set:
    if not field:
        return set()
    return {doc[field] for doc in tgt.find({}, {field: 1, "_id": 0}) if field in doc}


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
            "merged_skipped": 0,
            "target_after": target_before,
            "dry_run": True,
        }

    if drop_target and target_before:
        tgt.drop()
        target_before = 0

    merge_field = None if drop_target else MERGE_KEY_FIELDS.get(name)
    seen = _existing_keys(tgt, merge_field) if merge_field else set()

    copied = 0
    merged_skipped = 0
    pending = []

    def flush_pending():
        nonlocal copied
        if not pending:
            return
        try:
            tgt.insert_many(pending, ordered=False)
            copied += len(pending)
        except BulkWriteError as exc:
            copied += exc.details.get("nInserted", 0)
        pending.clear()

    for doc in src.find({}):
        if merge_field:
            key = doc.get(merge_field)
            if key is not None and key in seen:
                merged_skipped += 1
                continue
            if key is not None:
                seen.add(key)
        pending.append(doc)
        if len(pending) >= 500:
            flush_pending()

    flush_pending()

    target_after = tgt.count_documents({})
    return {
        "collection": name,
        "source": source_count,
        "target_before": target_before,
        "copied": copied,
        "merged_skipped": merged_skipped,
        "target_after": target_after,
        "dry_run": False,
    }


def run_migration(
    *,
    mongo_url: str,
    source_db_name: str,
    target_db_name: str,
    target_mongo_url: str | None = None,
    profile: Profile = "crc",
    dry_run: bool = False,
    drop_target: bool = False,
) -> dict:
    target_url = (target_mongo_url or mongo_url).strip()
    source_client = MongoClient(mongo_url, serverSelectionTimeoutMS=15000)
    target_client = source_client if target_url == mongo_url else MongoClient(
        target_url, serverSelectionTimeoutMS=15000
    )
    source_client.admin.command("ping")
    if target_client is not source_client:
        target_client.admin.command("ping")

    source_db = source_client[source_db_name]
    target_db = target_client[target_db_name]

    if profile == "full":
        collections = sorted(source_db.list_collection_names())
        missing = []
    else:
        existing = set(source_db.list_collection_names())
        collections = [c for c in CRC_COLLECTIONS if c in existing]
        missing = [c for c in CRC_COLLECTIONS if c not in existing]

    if not collections:
        raise ValueError("no collections to migrate")

    results = []
    for name in collections:
        results.append(
            copy_collection(
                source_db,
                target_db,
                name,
                dry_run=dry_run,
                drop_target=drop_target,
            )
        )

    return {
        "source_db": source_db_name,
        "target_db": target_db_name,
        "profile": profile,
        "dry_run": dry_run,
        "drop_target": drop_target,
        "missing_collections": missing,
        "collections": results,
    }
