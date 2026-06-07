"""
Gantt Chart — idempotent MongoDB index creation.
"""
import logging
from typing import Any

logger = logging.getLogger(__name__)


async def ensure_gantt_indexes(db: Any) -> None:
    """Create gantt collection indexes if they do not exist."""
    try:
        await db.gantt_projects.create_index([("owner_user_id", 1), ("updated_at", -1)])
        await db.gantt_projects.create_index(
            [("gantt_project_id", 1), ("owner_user_id", 1)],
            unique=True,
        )
        await db.gantt_tasks.create_index([("gantt_project_id", 1), ("order", 1)])
        await db.gantt_tasks.create_index("task_id", unique=True)
        await db.gantt_tasks.create_index([("gantt_project_id", 1), ("phase", 1), ("order", 1)])
        await db.gantt_tasks.create_index([("owner_user_id", 1), ("gantt_project_id", 1)])

        # Phase 3 — upload & draft collections
        await db.gantt_extraction_drafts.create_index(
            [("owner_user_id", 1), ("status", 1), ("created_at", -1)]
        )
        await db.gantt_extraction_drafts.create_index(
            [("draft_id", 1), ("owner_user_id", 1)],
            unique=True,
        )
        await db.gantt_extraction_drafts.create_index(
            "expires_at",
            expireAfterSeconds=0,
        )
        await db.gantt_uploaded_files.create_index([("owner_user_id", 1), ("created_at", -1)])
        await db.gantt_uploaded_files.create_index(
            [("file_id", 1), ("owner_user_id", 1)],
            unique=True,
        )
        await db.gantt_uploaded_files.create_index(
            "expires_at",
            expireAfterSeconds=0,
        )
        logger.info("Gantt indexes created/verified")
    except Exception as exc:
        logger.warning(f"Gantt index creation warning: {exc}")
