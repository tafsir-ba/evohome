"""
Canonical File Service — Unified Upload / Media System.

Single source of truth for all file upload, validation, storage, and deletion.
No other module should handle file I/O directly.

Storage: DigitalOcean Spaces (S3-compatible) for persistent storage.
Falls back to local disk if Spaces is not configured.
Parent entities persist: url, stored_filename, original_filename, file_size, content_type.
Never persist absolute disk paths.
"""
import os
import uuid
import logging
import mimetypes
from pathlib import Path
from typing import Dict, Any, Set, Optional, Tuple
from urllib.parse import urlparse

import boto3
from botocore.exceptions import ClientError
from fastapi import UploadFile, HTTPException

logger = logging.getLogger(__name__)

# ── Storage Configuration ──

SPACES_KEY = os.environ.get("SPACES_KEY", "")
SPACES_SECRET = os.environ.get("SPACES_SECRET", "")
SPACES_BUCKET = os.environ.get("SPACES_BUCKET", "")
SPACES_REGION = os.environ.get("SPACES_REGION", "fra1")
SPACES_ENDPOINT = os.environ.get("SPACES_ENDPOINT", f"https://{SPACES_REGION}.digitaloceanspaces.com")
SPACES_CDN_URL = os.environ.get("SPACES_CDN_URL", f"https://{SPACES_BUCKET}.{SPACES_REGION}.digitaloceanspaces.com")
SPACES_PREFIX = "uploads/"

USE_SPACES = bool(SPACES_KEY and SPACES_SECRET and SPACES_BUCKET)

# Local fallback
UPLOAD_DIR = Path("/app/backend/uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# S3 client (initialized lazily)
_s3_client = None


def _get_s3():
    global _s3_client
    if _s3_client is None and USE_SPACES:
        session = boto3.session.Session()
        _s3_client = session.client(
            "s3",
            region_name=SPACES_REGION,
            endpoint_url=SPACES_ENDPOINT,
            aws_access_key_id=SPACES_KEY,
            aws_secret_access_key=SPACES_SECRET,
        )
    return _s3_client


if USE_SPACES:
    logger.info(f"File storage: DigitalOcean Spaces ({SPACES_BUCKET}.{SPACES_REGION})")
else:
    logger.warning("File storage: LOCAL DISK (files will NOT persist across deploys)")


# ── Frozen Validation Rules ──

IMAGE_MIME_TYPES: Set[str] = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
    "image/gif",
    "image/heic",
    "image/heif",
}
IMAGE_EXTENSIONS: Set[str] = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".heic", ".heif"}

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
MAX_SIZE_ACTIVITY = 20 * 1024 * 1024  # activity feed image/PDF (matches activities route)


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

    # Accept if MIME matches OR if extension is valid (browsers sometimes send wrong MIME)
    mime_ok = content_type in allowed_mimes
    ext_ok = ext and ext in allowed_extensions

    if not mime_ok and not ext_ok:
        _upload_error(
            "invalid_file_type",
            f"File type '{content_type}' with extension '{ext}' is not allowed. Accepted types: {', '.join(sorted(allowed_mimes))}",
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
    Uses Spaces if configured, local disk otherwise.
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

    if USE_SPACES:
        url = _upload_to_spaces(stored_filename, content, file.content_type or "application/octet-stream")
    else:
        (UPLOAD_DIR / stored_filename).write_bytes(content)
        url = f"/api/uploads/{stored_filename}"

    # Record trace metadata
    from core.trace import set_trace_request_summary
    set_trace_request_summary({
        "original_filename": file.filename,
        "file_size": len(content),
        "content_type": file.content_type,
        "prefix": prefix,
        "stored_filename": stored_filename,
        "storage": "spaces" if USE_SPACES else "local",
    })

    return {
        "url": url,
        "stored_filename": stored_filename,
        "original_filename": file.filename or stored_filename,
        "file_size": len(content),
        "content_type": file.content_type or "application/octet-stream",
    }


def _upload_to_spaces(stored_filename: str, content: bytes, content_type: str) -> str:
    """Upload file to DigitalOcean Spaces. Returns public URL."""
    s3 = _get_s3()
    key = f"{SPACES_PREFIX}{stored_filename}"
    try:
        s3.put_object(
            Bucket=SPACES_BUCKET,
            Key=key,
            Body=content,
            ContentType=content_type,
            ACL="public-read",
        )
        return f"{SPACES_CDN_URL}/{key}"
    except ClientError as e:
        logger.error(f"Spaces upload failed for {stored_filename}: {e}")
        raise HTTPException(status_code=500, detail={
            "error": "storage_error",
            "message": "File upload to storage failed. Please try again.",
        })


def get_file_url(stored_filename: str) -> Optional[str]:
    """Get the public URL for a stored file."""
    if not stored_filename:
        return None
    if USE_SPACES:
        return f"{SPACES_CDN_URL}/{SPACES_PREFIX}{stored_filename}"
    return f"/api/uploads/{stored_filename}"


def get_local_path(stored_filename: str) -> Path:
    """
    Get a local file path for processing (e.g., AI extraction).
    If using Spaces, downloads to local temp first.
    If using local storage, returns the path directly.
    """
    local_path = UPLOAD_DIR / stored_filename
    if local_path.exists():
        return local_path
    if USE_SPACES:
        s3 = _get_s3()
        key = f"{SPACES_PREFIX}{stored_filename}"
        try:
            response = s3.get_object(Bucket=SPACES_BUCKET, Key=key)
            content = response["Body"].read()
            local_path.write_bytes(content)
            return local_path
        except ClientError as e:
            logger.error(f"Failed to download {stored_filename} from Spaces: {e}")
    return local_path


def resolve_path(stored_filename: str) -> Path:
    """Resolve stored_filename to absolute disk path. Local storage only."""
    return UPLOAD_DIR / stored_filename


def stored_filename_from_public_url(url: str) -> Optional[str]:
    """
    Extract stored_filename (e.g. activities_a1b2c3d4.png) from a public CDN or /api/uploads URL.
    Used when activity rows have file_url but no stored_filename (legacy / backfill).
    """
    if not url or not isinstance(url, str):
        return None
    u = url.strip().split("?")[0].split("#")[0]
    if u.startswith("http://") or u.startswith("https://"):
        path = urlparse(u).path.lstrip("/")
    elif u.startswith("/api/uploads/"):
        path = u[len("/api/uploads/") :].lstrip("/")
    else:
        return None
    if path.startswith("uploads/"):
        path = path[len("uploads/") :]
    seg = path.split("/")[0] if path else ""
    if not seg or ".." in seg:
        return None
    return seg


def read_stored_file_bytes(stored_filename: str) -> Tuple[bytes, str]:
    """Load file bytes from Spaces or local uploads/. Raises FileNotFoundError if missing."""
    if (
        not stored_filename
        or ".." in stored_filename
        or "/" in stored_filename
        or "\\" in stored_filename
    ):
        raise ValueError("invalid stored_filename")
    if USE_SPACES:
        s3 = _get_s3()
        key = f"{SPACES_PREFIX}{stored_filename}"
        try:
            r = s3.get_object(Bucket=SPACES_BUCKET, Key=key)
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "")
            if code in ("404", "NoSuchKey", "NotFound"):
                raise FileNotFoundError(key) from e
            raise
        body = r["Body"].read()
        ct = r.get("ContentType") or mimetypes.guess_type(stored_filename)[0] or "application/octet-stream"
        return body, ct
    path = UPLOAD_DIR / stored_filename
    if not path.is_file():
        raise FileNotFoundError(stored_filename)
    ct = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    return path.read_bytes(), ct


def write_vault_bytes(stored_filename: str, content: bytes, content_type: str = "application/pdf") -> None:
    """
    Persist raw bytes as a vault object (Spaces or local uploads/).
    Used by demo seed so vault rows always resolve via read_stored_file_bytes.
    """
    if (
        not stored_filename
        or ".." in stored_filename
        or "/" in stored_filename
        or "\\" in stored_filename
    ):
        raise ValueError("invalid stored_filename")
    if USE_SPACES:
        _upload_to_spaces(stored_filename, content, content_type)
    else:
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        (UPLOAD_DIR / stored_filename).write_bytes(content)


async def save_activity_attachment(file: UploadFile, activity_kind: str) -> Dict[str, Any]:
    """
    Persist activity feed image or PDF to Spaces (or local uploads/ fallback).
    Same durability path as logos/vault when SPACES_* is set.
    """
    if activity_kind == "image":
        return await save_upload(
            file,
            "activities",
            MAX_SIZE_ACTIVITY,
            IMAGE_MIME_TYPES,
            IMAGE_EXTENSIONS,
        )
    if activity_kind == "pdf":
        return await save_upload(
            file,
            "activities",
            MAX_SIZE_ACTIVITY,
            PDF_MIME_TYPES,
            PDF_EXTENSIONS,
        )
    raise ValueError("activity_kind must be image or pdf")


def delete_file(stored_filename: str) -> bool:
    """Delete a file by stored_filename. Works with both Spaces and local."""
    if not stored_filename:
        return False

    if USE_SPACES:
        return _delete_from_spaces(stored_filename)

    path = resolve_path(stored_filename)
    if path.exists():
        try:
            path.unlink()
            return True
        except OSError as e:
            logger.warning(f"Failed to delete {stored_filename}: {e}")
    return False


def _delete_from_spaces(stored_filename: str) -> bool:
    """Delete file from DigitalOcean Spaces."""
    s3 = _get_s3()
    key = f"{SPACES_PREFIX}{stored_filename}"
    try:
        s3.delete_object(Bucket=SPACES_BUCKET, Key=key)
        return True
    except ClientError as e:
        logger.warning(f"Spaces delete failed for {stored_filename}: {e}")
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
