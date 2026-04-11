"""
Vault Routes — Canonical Implementation.

Thin route layer. No is_demo. File I/O stays here.
"""
import uuid
import logging
from pathlib import Path
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import FileResponse

from database import db
from core.auth import get_current_user, get_current_agent
from services import vault_service

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).parent.parent
UPLOAD_DIR = ROOT_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

router = APIRouter()


@router.post("/vault/upload")
async def upload_vault_document(
    file: UploadFile = File(...),
    project_id: str = Form(...),
    client_ids: str = Form(...),
    title: str = Form(...),
    category: str = Form("general"),
    description: Optional[str] = Form(None),
    user: dict = Depends(get_current_agent),
):
    """Upload a document to the vault. Agent only."""
    project = await db.projects.find_one(
        {"project_id": project_id, "agent_id": user['user_id']}
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    parsed_ids = [cid.strip() for cid in client_ids.split(',') if cid.strip()]
    if not parsed_ids:
        raise HTTPException(status_code=400, detail="At least one client_id required")

    for cid in parsed_ids:
        c = await db.clients.find_one({"client_id": cid, "agent_id": user['user_id']})
        if not c:
            raise HTTPException(status_code=400, detail=f"Client {cid} not found")

    if category not in vault_service.VAULT_CATEGORIES:
        category = "general"

    content = await file.read()
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 50MB)")

    file_id = uuid.uuid4().hex[:12]
    ext = Path(file.filename).suffix if file.filename else '.pdf'
    filename = f"vault_{file_id}{ext}"
    file_path = UPLOAD_DIR / filename
    file_path.write_bytes(content)

    return await vault_service.create_vault_document(
        agent_id=user['user_id'],
        project_id=project_id,
        client_ids=parsed_ids,
        title=title,
        category=category,
        description=description,
        filename=file.filename or filename,
        file_path=str(file_path),
        file_size=len(content),
    )


@router.get("/vault/documents")
async def list_vault_documents(
    project_id: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    """List vault documents for current user."""
    if user['role'] == 'buyer':
        return await vault_service.list_buyer_vault(user['user_id'])
    return await vault_service.list_vault_documents(user['user_id'], project_id)


@router.get("/vault/categories")
async def get_vault_categories(user: dict = Depends(get_current_agent)):
    """Get vault document categories."""
    return await vault_service.get_categories()


@router.get("/vault/documents/{vault_document_id}")
async def get_vault_document(vault_document_id: str, user: dict = Depends(get_current_user)):
    """Get a single vault document."""
    doc = await vault_service.get_vault_document(vault_document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Vault document not found")

    if user['role'] == 'agent' and doc.get('agent_id') != user['user_id']:
        raise HTTPException(status_code=403, detail="Access denied")
    if user['role'] == 'buyer' and user['user_id'] not in doc.get('buyer_ids', []):
        raise HTTPException(status_code=403, detail="Access denied")

    return doc


@router.put("/vault/documents/{vault_document_id}")
async def update_vault_document(vault_document_id: str, request_data: dict, user: dict = Depends(get_current_agent)):
    """Update vault document metadata."""
    result = await vault_service.update_vault_document(vault_document_id, user['user_id'], request_data)
    if not result:
        raise HTTPException(status_code=404, detail="Vault document not found")
    return result


@router.delete("/vault/documents/{vault_document_id}")
async def delete_vault_document(vault_document_id: str, user: dict = Depends(get_current_agent)):
    """Delete a vault document."""
    deleted = await vault_service.delete_vault_document(vault_document_id, user['user_id'])
    if not deleted:
        raise HTTPException(status_code=404, detail="Vault document not found")
    return {"message": "Vault document deleted"}


@router.get("/vault/documents/{vault_document_id}/download")
async def download_vault_document(vault_document_id: str, user: dict = Depends(get_current_user)):
    """Download a vault document file."""
    doc = await vault_service.get_vault_document(vault_document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Vault document not found")

    if user['role'] == 'agent' and doc.get('agent_id') != user['user_id']:
        raise HTTPException(status_code=403, detail="Access denied")
    if user['role'] == 'buyer' and user['user_id'] not in doc.get('buyer_ids', []):
        raise HTTPException(status_code=403, detail="Access denied")

    import os
    if not doc.get('file_path') or not os.path.exists(doc['file_path']):
        raise HTTPException(status_code=404, detail="File not found on disk")

    return FileResponse(
        doc['file_path'],
        filename=doc.get('filename', 'download'),
        media_type='application/octet-stream'
    )
