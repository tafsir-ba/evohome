"""
Gantt Chart — upload, AI extraction, and draft lifecycle (Phase 3).
Standalone; no CMP coupling.
"""
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from database import db
from services import file_service
from services.gantt_constants import (
    ALLOWED_UPLOAD_EXTENSIONS,
    GANTT_REVIEW_MESSAGE,
    GANTT_TEMP_SUBDIR,
    MAX_UPLOAD_SIZE_BYTES,
    UPLOAD_RETENTION_HOURS,
    IMAGE_EXTENSIONS,
)
from services.gantt_parsers import (
    parse_csv_milestones,
    parse_image_vision,
    parse_pdf_text,
)
from services.gantt_validation import GanttValidationError, validate_draft_tasks

logger = logging.getLogger(__name__)


def _legacy_upload_root() -> Path:
    """Legacy local-only path (pre-Spaces fix). Kept for read/delete fallback."""
    root = Path(__file__).resolve().parent.parent / "uploads" / GANTT_TEMP_SUBDIR
    root.mkdir(parents=True, exist_ok=True)
    return root


def _stored_filename(file_id: str, ext: str) -> str:
    return f"gantt_{file_id}{ext}"


def _persist_upload_bytes(
    stored_filename: str,
    content: bytes,
    content_type: Optional[str],
) -> None:
    """Persist via canonical file_service (Spaces when configured, else shared uploads/)."""
    file_service.write_vault_bytes(
        stored_filename,
        content,
        content_type or "application/octet-stream",
    )


def _resolve_upload_path(stored_filename: str) -> str:
    """
    Resolve an uploaded gantt file to a local path for parsers.
    Downloads from Spaces when needed; falls back to legacy gantt_temp/ path.
    """
    local_path = file_service.get_local_path(stored_filename)
    if local_path.is_file():
        return str(local_path)

    legacy_path = _legacy_upload_root() / stored_filename
    if legacy_path.is_file():
        return str(legacy_path)

    bare_name = stored_filename.removeprefix("gantt_")
    legacy_bare = _legacy_upload_root() / bare_name
    if legacy_bare.is_file():
        return str(legacy_bare)

    raise GanttValidationError(
        f"Uploaded file not found in storage ({stored_filename}). "
        "Please upload the document again."
    )


def _delete_stored_file(stored_filename: str) -> None:
    file_service.delete_file(stored_filename)
    for candidate in (
        _legacy_upload_root() / stored_filename,
        _legacy_upload_root() / stored_filename.removeprefix("gantt_"),
    ):
        try:
            if candidate.exists():
                candidate.unlink()
        except OSError as exc:
            logger.warning("Failed to delete legacy gantt upload %s: %s", candidate, exc)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _expires_at_dt() -> datetime:
    return _now() + timedelta(hours=UPLOAD_RETENTION_HOURS)


def _serialize_upload(doc: Dict[str, Any]) -> Dict[str, Any]:
    result = {**doc}
    if isinstance(result.get("expires_at"), datetime):
        result["expires_at"] = result["expires_at"].isoformat()
    if isinstance(result.get("created_at"), datetime):
        result["created_at"] = result["created_at"].isoformat()
    return result


def _serialize_draft(doc: Dict[str, Any]) -> Dict[str, Any]:
    result = {**doc}
    for field in ("expires_at", "created_at", "updated_at"):
        if isinstance(result.get(field), datetime):
            result[field] = result[field].isoformat()
    return result


def _is_expired(expires_at: Any) -> bool:
    try:
        if isinstance(expires_at, datetime):
            expiry = expires_at
        else:
            expiry = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        return _now() >= expiry
    except (ValueError, TypeError):
        return True


def _make_file_id() -> str:
    return f"gfu_{uuid.uuid4().hex[:12]}"


def _make_draft_id() -> str:
    return f"gd_{uuid.uuid4().hex[:12]}"


def _normalize_extension(filename: str) -> str:
    return os.path.splitext(filename)[1].lower()


def _source_type_for_extension(ext: str) -> str:
    if ext == ".csv":
        return "csv"
    if ext == ".pdf":
        return "pdf"
    if ext in IMAGE_EXTENSIONS:
        return "image"
    raise GanttValidationError(f"Unsupported file extension: {ext}")


def _task_source_for_draft(source_type: str) -> str:
    return "imported" if source_type == "csv" else "ai_generated"


async def _get_project_for_owner(
    gantt_project_id: str,
    owner_user_id: str,
) -> Optional[Dict[str, Any]]:
    return await db.gantt_projects.find_one(
        {"gantt_project_id": gantt_project_id, "owner_user_id": owner_user_id},
        {"_id": 0},
    )


async def _get_uploaded_file(
    file_id: str,
    owner_user_id: str,
) -> Optional[Dict[str, Any]]:
    return await db.gantt_uploaded_files.find_one(
        {"file_id": file_id, "owner_user_id": owner_user_id},
        {"_id": 0},
    )


async def _get_draft(
    draft_id: str,
    owner_user_id: str,
) -> Optional[Dict[str, Any]]:
    return await db.gantt_extraction_drafts.find_one(
        {"draft_id": draft_id, "owner_user_id": owner_user_id},
        {"_id": 0},
    )


def _delete_file_from_disk(stored_filename: str) -> None:
    _delete_stored_file(stored_filename)


async def _delete_upload_record(file_id: str, owner_user_id: str) -> None:
    record = await _get_uploaded_file(file_id, owner_user_id)
    if record:
        _delete_file_from_disk(record["stored_filename"])
    await db.gantt_uploaded_files.delete_one(
        {"file_id": file_id, "owner_user_id": owner_user_id}
    )


async def cleanup_project_imports(gantt_project_id: str, owner_user_id: str) -> None:
    """Delete uploads and drafts tied to a project, including temp files on disk."""
    uploads = await db.gantt_uploaded_files.find(
        {"gantt_project_id": gantt_project_id, "owner_user_id": owner_user_id},
        {"_id": 0, "stored_filename": 1},
    ).to_list(500)
    for upload in uploads:
        _delete_file_from_disk(upload["stored_filename"])

    await db.gantt_uploaded_files.delete_many(
        {"gantt_project_id": gantt_project_id, "owner_user_id": owner_user_id}
    )
    await db.gantt_extraction_drafts.delete_many(
        {"gantt_project_id": gantt_project_id, "owner_user_id": owner_user_id}
    )


async def upload_file(
    owner_user_id: str,
    gantt_project_id: str,
    filename: str,
    content: bytes,
    content_type: Optional[str] = None,
) -> Dict[str, Any]:
    """Store an uploaded planning document with 24h retention."""
    project = await _get_project_for_owner(gantt_project_id, owner_user_id)
    if not project:
        raise PermissionError("Project not found or access denied")

    if len(content) > MAX_UPLOAD_SIZE_BYTES:
        raise GanttValidationError(
            f"File exceeds maximum size of {MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)} MB"
        )

    ext = _normalize_extension(filename)
    if ext not in ALLOWED_UPLOAD_EXTENSIONS:
        raise GanttValidationError(
            f"Unsupported file type: {ext}. "
            f"Allowed: {', '.join(sorted(ALLOWED_UPLOAD_EXTENSIONS))}"
        )

    file_id = _make_file_id()
    stored_filename = _stored_filename(file_id, ext)
    _persist_upload_bytes(stored_filename, content, content_type)

    now = _now()
    doc = {
        "file_id": file_id,
        "owner_user_id": owner_user_id,
        "gantt_project_id": gantt_project_id,
        "original_filename": filename,
        "stored_filename": stored_filename,
        "content_type": content_type,
        "file_size_bytes": len(content),
        "extension": ext,
        "created_at": now,
        "expires_at": _expires_at_dt(),
    }
    await db.gantt_uploaded_files.insert_one(doc)
    doc.pop("_id", None)
    return _serialize_upload(doc)


async def extract_draft(
    owner_user_id: str,
    file_id: str,
    gantt_project_id: str,
) -> Dict[str, Any]:
    """Run extraction parser and persist a reviewable draft (no tasks written)."""
    project = await _get_project_for_owner(gantt_project_id, owner_user_id)
    if not project:
        raise PermissionError("Project not found or access denied")

    upload = await _get_uploaded_file(file_id, owner_user_id)
    if not upload:
        raise GanttValidationError("Upload not found")
    if upload["gantt_project_id"] != gantt_project_id:
        raise GanttValidationError("Upload does not belong to this project")
    if _is_expired(upload["expires_at"]):
        raise GanttValidationError("Upload has expired; please upload again")

    file_path = _resolve_upload_path(upload["stored_filename"])
    ext = upload["extension"]
    source_type = _source_type_for_extension(ext)

    if source_type == "csv":
        tasks, warnings = await parse_csv_milestones(file_path)
    elif source_type == "pdf":
        tasks, warnings = await parse_pdf_text(file_path)
    else:
        tasks, warnings = await parse_image_vision(file_path)

    draft_id = _make_draft_id()
    now = _now()
    doc = {
        "draft_id": draft_id,
        "owner_user_id": owner_user_id,
        "gantt_project_id": gantt_project_id,
        "file_id": file_id,
        "status": "pending",
        "source_type": source_type,
        "tasks": tasks,
        "warnings": warnings,
        "review_message": GANTT_REVIEW_MESSAGE,
        "created_at": now,
        "updated_at": now,
        "expires_at": _expires_at_dt(),
    }
    await db.gantt_extraction_drafts.insert_one(doc)
    doc.pop("_id", None)
    return _serialize_draft(doc)


async def get_draft(draft_id: str, owner_user_id: str) -> Optional[Dict[str, Any]]:
    draft = await _get_draft(draft_id, owner_user_id)
    if not draft:
        return None
    if draft["status"] == "pending" and _is_expired(draft["expires_at"]):
        await db.gantt_extraction_drafts.update_one(
            {"draft_id": draft_id, "owner_user_id": owner_user_id},
            {"$set": {"status": "expired", "updated_at": _now()}},
        )
        draft["status"] = "expired"
    return _serialize_draft(draft)


async def update_draft(
    draft_id: str,
    owner_user_id: str,
    tasks: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    draft = await get_draft(draft_id, owner_user_id)
    if not draft:
        return None
    if draft["status"] != "pending":
        raise GanttValidationError(f"Cannot edit draft with status: {draft['status']}")

    validate_draft_tasks(tasks)
    now = _now()
    await db.gantt_extraction_drafts.update_one(
        {"draft_id": draft_id, "owner_user_id": owner_user_id},
        {"$set": {"tasks": tasks, "updated_at": now}},
    )
    return await get_draft(draft_id, owner_user_id)


async def confirm_draft(
    draft_id: str,
    owner_user_id: str,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Validate draft, remap tempId → task_id, persist tasks, mark confirmed.
    Rolls back inserted tasks if finalization fails.
    """
    from services import gantt_service

    draft = await get_draft(draft_id, owner_user_id)
    if not draft:
        raise PermissionError("Draft not found or access denied")
    if draft["status"] == "expired":
        raise GanttValidationError("Draft has expired and cannot be confirmed")
    if draft["status"] != "pending":
        raise GanttValidationError(f"Draft cannot be confirmed (status: {draft['status']})")

    normalized = validate_draft_tasks(draft["tasks"])
    source = _task_source_for_draft(draft["source_type"])
    created: List[Dict[str, Any]] = []

    try:
        created = await gantt_service.create_tasks_from_draft(
            gantt_project_id=draft["gantt_project_id"],
            owner_user_id=owner_user_id,
            draft_tasks=normalized,
            source=source,
        )

        now = _now()
        finalize = await db.gantt_extraction_drafts.update_one(
            {
                "draft_id": draft_id,
                "owner_user_id": owner_user_id,
                "status": "pending",
            },
            {"$set": {"status": "confirmed", "updated_at": now}},
        )
        if finalize.matched_count == 0:
            raise GanttValidationError("Draft already processed")

        await _delete_upload_record(draft["file_id"], owner_user_id)
    except Exception:
        if created:
            await db.gantt_tasks.delete_many(
                {"task_id": {"$in": [task["task_id"] for task in created]}}
            )
        raise

    return created, {"draft_id": draft_id, "status": "confirmed"}


async def discard_draft(draft_id: str, owner_user_id: str) -> Optional[Dict[str, Any]]:
    draft = await get_draft(draft_id, owner_user_id)
    if not draft:
        return None
    if draft["status"] in {"confirmed", "discarded"}:
        raise GanttValidationError(f"Draft already {draft['status']}")

    now = _now()
    await db.gantt_extraction_drafts.update_one(
        {"draft_id": draft_id, "owner_user_id": owner_user_id},
        {"$set": {"status": "discarded", "updated_at": now}},
    )
    await _delete_upload_record(draft["file_id"], owner_user_id)
    return {"draft_id": draft_id, "status": "discarded"}
