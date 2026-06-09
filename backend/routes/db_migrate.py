"""
One-shot evohome → crc migration for DigitalOcean App Platform.

No SSH/droplet required: the running backend already has MONGO_URL.
Enable temporarily with MIGRATION_SECRET, call the endpoint, then remove the secret.
"""
from __future__ import annotations

import os
import secrets

from fastapi import APIRouter, Header, HTTPException, Query

from core.config import get_config
from services.mongo_migrate import run_migration

router = APIRouter(tags=["internal"])


def _check_migration_secret(provided: str | None) -> None:
    expected = (os.environ.get("MIGRATION_SECRET") or "").strip()
    if not expected:
        raise HTTPException(
            status_code=404,
            detail="Migration endpoint disabled (set MIGRATION_SECRET on backend to enable)",
        )
    if not provided or not secrets.compare_digest(provided, expected):
        raise HTTPException(status_code=403, detail="Invalid migration secret")


@router.get("/internal/migrate-evohome-to-crc")
@router.post("/internal/migrate-evohome-to-crc")
async def migrate_evohome_to_crc(
    dry_run: bool = Query(True, description="Preview counts only; set false to copy data"),
    drop_target: bool = Query(
        False,
        description="Drop target collections first — do NOT use if crc has data to keep",
    ),
    x_migration_secret: str | None = Header(None, alias="X-Migration-Secret"),
):
    _check_migration_secret(x_migration_secret)

    config = get_config()
    source_db = (os.environ.get("MIGRATION_SOURCE_DB") or "evohome").strip()
    target_db = config.DB_NAME

    if source_db == target_db:
        raise HTTPException(status_code=400, detail="Source and target database names must differ")

    try:
        report = run_migration(
            mongo_url=config.MONGO_URL,
            source_db_name=source_db,
            target_db_name=target_db,
            profile="crc",
            dry_run=dry_run,
            drop_target=drop_target,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Migration failed: {exc}") from exc

    return report
