"""
Canonical File Service — Unified Upload / Media System.

Single source of truth for all file upload, validation, storage, and deletion.
No other module should handle file I/O directly.

Storage: All files → /app/backend/uploads/ with prefixed stored_filenames.
Parent entities persist: url, stored_filename, original_filename, file_size, content_type.
Never persist absolute disk paths.
"""
import uuid
import logging
from pathlib import Path
from typing import Dict, Any, Set

from fastapi import UploadFile, HTTPException

logger = logging.getLogger(__name__)

UPLOAD_DIR = Path("/app/backend/uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


# ── Frozen Validation Rules ──

IMAGE_MIME_TYPES: Set[str] = {"image/jpeg", "image/png", "image/webp"}
IMAGE_EXTENSIONS: Set[str] = {".jpg", ".jpeg", ".png", ".webp"}

VAULT_MIME_TYPES: Set[str] = {
    "image/jpeg", "image/png", "image/webp",
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}
VAULT_EXTENSIONS: Set[str] = {".jpg", ".jpeg", ".png", ".webp", ".pdf", ".doc", ".docx", ".xls", ".xlsx"}

PDF_MIME_TYPES: Set[str] = {"application/pdf"}
PDF_EXTENSIONS: Set[str] = {".pdf"}

MAX_SIZE_LOGO = 2 * 1024 * 1024       # 2 MB
MAX_SIZE_HERO = 5 * 1024 * 1024       # 5 MB
MAX_SIZE_VAULT = 50 * 1024 * 1024     # 50 MB
MAX_SIZE_PDF = 20 * 1024 * 1024       # 20 MB


# ── Canonical error ──

def _upload_error(code: str, message: str):
    raise HTTPException(status_code=400, detail={"error": code, "message": message})


# ── Validation ──

def _validate(
    filename: str,
    content_type: str,
    size: int,
    allowed_mimes: Set[str],
    allowed_extensions: Set[str],
    max_size: int,
):
    ext = Path(filename).suffix.lower() if filename else ""

    if content_type not in allowed_mimes:
        _upload_error(
            "invalid_file_type",
            f"File type '{content_type}' is not allowed. Accepted: {', '.join(sorted(allowed_mimes))}",
        )

    if ext and ext not in allowed_extensions:
        _upload_error(
            "invalid_file_type",
            f"Extension '{ext}' is not allowed. Accepted: {', '.join(sorted(allowed_extensions))}",
        )

    if size > max_size:
        max_mb = max_size / (1024 * 1024)
        _upload_error("file_too_large", f"File exceeds maximum size of {max_mb:.0f} MB")


# ── Core ──

async def save_upload(
    file: UploadFile,
    prefix: str,
    max_size: int,
    allowed_mimes: Set[str],
    allowed_extensions: Set[str],
    identifier: str = "",
) -> Dict[str, Any]:
    """
    Save an uploaded file. Returns canonical metadata dict.

    Caller stores the returned fields on the parent entity.
    Never returns or stores absolute disk paths.
    """
    content = await file.read()

    _validate(
        filename=file.filename or "",
        content_type=file.content_type or "application/octet-stream",
        size=len(content),
        allowed_mimes=allowed_mimes,
        allowed_extensions=allowed_extensions,
        max_size=max_size,
    )

    ext = Path(file.filename).suffix.lower() if file.filename else ""
    hash_part = uuid.uuid4().hex[:8]
    id_part = f"_{identifier}" if identifier else ""
    stored_filename = f"{prefix}{id_part}_{hash_part}{ext}"

    (UPLOAD_DIR / stored_filename).write_bytes(content)

    return {
        "url": f"/api/uploads/{stored_filename}",
        "stored_filename": stored_filename,
        "original_filename": file.filename or stored_filename,
        "file_size": len(content),
        "content_type": file.content_type or "application/octet-stream",
    }


def resolve_path(stored_filename: str) -> Path:
    """Resolve stored_filename to absolute disk path. Internal use only."""
    return UPLOAD_DIR / stored_filename


def delete_file(stored_filename: str) -> bool:
    """Delete a file by stored_filename. Returns True if removed."""
    if not stored_filename:
        return False
    path = resolve_path(stored_filename)
    if path.exists():
        try:
            path.unlink()
            return True
        except OSError as e:
            logger.warning(f"Failed to delete {stored_filename}: {e}")
    return False


# ── Preset entry points (frozen validation rules) ──

async def save_logo(file: UploadFile, user_id: str) -> Dict[str, Any]:
    """Company logo. 2 MB max, image only."""
    return await save_upload(file, "logo", MAX_SIZE_LOGO, IMAGE_MIME_TYPES, IMAGE_EXTENSIONS, user_id)


async def save_hero_image(file: UploadFile, document_id: str) -> Dict[str, Any]:
    """Document hero/banner image. 5 MB max, image only."""
    return await save_upload(file, "hero", MAX_SIZE_HERO, IMAGE_MIME_TYPES, IMAGE_EXTENSIONS, document_id)


async def save_vault_file(file: UploadFile) -> Dict[str, Any]:
    """Vault document. 50 MB max, PDF/images/Office docs."""
    return await save_upload(file, "vault", MAX_SIZE_VAULT, VAULT_MIME_TYPES, VAULT_EXTENSIONS)


async def save_pdf(file: UploadFile) -> Dict[str, Any]:
    """Source PDF for document extraction. 20 MB max, PDF only."""
    return await save_upload(file, "pdf", MAX_SIZE_PDF, PDF_MIME_TYPES, PDF_EXTENSIONS)
