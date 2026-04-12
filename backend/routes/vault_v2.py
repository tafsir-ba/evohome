"""
Vault Routes — Canonical Implementation.

Thin route layer. File I/O delegated to file_service.
All data operations delegate to vault_service.
"""
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, Request
from fastapi.responses import FileResponse

from database import db
from core.auth import get_current_user, get_current_agent
from services import vault_service
from services import file_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/vault/upload")
async def upload_vault_document(
    file: UploadFile = File(...),
    project_id: str = Form(""),
    client_ids: str = Form(""),
    title: str = Form(...),
    category: str = Form("other"),
    description: Optional[str] = Form(None),
    access_level: Optional[str] = Form("private"),
    doc_type: Optional[str] = Form("general"),
    user: dict = Depends(get_current_agent),
):
    """Upload a document to the vault."""
    from core.trace import set_trace_action, set_trace_entity, set_trace_request_summary, trace_service

    set_trace_action("vault_upload")
    trace_service("routes.vault_v2.upload_vault_document")
    set_trace_request_summary({
        "title": title,
        "category": category,
        "access_level": access_level,
        "project_id": project_id or None,
        "client_count": len([c for c in client_ids.split(",") if c.strip()]),
    })
    if project_id:
        project = await db.projects.find_one(
            {"project_id": project_id, "agent_id": user["user_id"]}
        )
        if not project:
            raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Project not found"})

    parsed_ids = [cid.strip() for cid in client_ids.split(",") if cid.strip()]
    for cid in parsed_ids:
        c = await db.clients.find_one({"client_id": cid, "agent_id": user["user_id"]})
        if not c:
            raise HTTPException(status_code=400, detail={"error": "not_found", "message": f"Client {cid} not found"})

    result = await file_service.save_vault_file(file)
    trace_service("services.file_service.save_vault_file")

    doc = await vault_service.create_vault_document(
        agent_id=user["user_id"],
        project_id=project_id,
        client_ids=parsed_ids,
        title=title,
        category=category,
        description=description,
        access_level=access_level or "private",
        doc_type=doc_type or "general",
        stored_filename=result["stored_filename"],
        original_filename=result["original_filename"],
        file_size=result["file_size"],
        content_type=result["content_type"],
    )

    set_trace_entity("vault_document", doc.get("vault_document_id", ""))
    return doc


@router.get("/vault/documents")
async def list_vault_documents(
    project_id: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    if user["role"] == "buyer":
        return await vault_service.list_buyer_vault(user["user_id"])
    return await vault_service.list_vault_documents(user["user_id"], project_id)


@router.get("/vault/categories")
async def get_vault_categories(user: dict = Depends(get_current_agent)):
    return await vault_service.get_categories()


@router.get("/vault/documents/{vault_document_id}")
async def get_vault_document(vault_document_id: str, user: dict = Depends(get_current_user)):
    doc = await vault_service.get_vault_document(vault_document_id)
    if not doc:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Vault document not found"})

    if user["role"] == "agent" and doc.get("agent_id") != user["user_id"]:
        raise HTTPException(status_code=403, detail={"error": "forbidden", "message": "Access denied"})
    if user["role"] == "buyer" and user["user_id"] not in doc.get("buyer_ids", []):
        raise HTTPException(status_code=403, detail={"error": "forbidden", "message": "Access denied"})

    return doc


@router.put("/vault/documents/{vault_document_id}")
async def update_vault_document(vault_document_id: str, request: Request, user: dict = Depends(get_current_agent)):
    body = await request.json()
    result = await vault_service.update_vault_document(vault_document_id, user["user_id"], body)
    if not result:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Vault document not found"})
    return result


@router.delete("/vault/documents/{vault_document_id}")
async def delete_vault_document(vault_document_id: str, user: dict = Depends(get_current_agent)):
    stored_filename = await vault_service.delete_vault_document(vault_document_id, user["user_id"])
    if stored_filename is None:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Vault document not found"})
    file_service.delete_file(stored_filename)
    return {"message": "Vault document deleted"}


@router.get("/vault/documents/{vault_document_id}/download")
async def download_vault_document(vault_document_id: str, user: dict = Depends(get_current_user)):
    doc = await vault_service.get_vault_document(vault_document_id)
    if not doc:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Vault document not found"})

    if user["role"] == "agent" and doc.get("agent_id") != user["user_id"]:
        raise HTTPException(status_code=403, detail={"error": "forbidden", "message": "Access denied"})
    if user["role"] == "buyer" and user["user_id"] not in doc.get("buyer_ids", []):
        raise HTTPException(status_code=403, detail={"error": "forbidden", "message": "Access denied"})

    stored = doc.get("stored_filename")
    if not stored:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "File not found"})

    if file_service.USE_SPACES:
        from fastapi.responses import RedirectResponse
        url = file_service.get_file_url(stored)
        return RedirectResponse(url=url)

    path = file_service.resolve_path(stored)
    if not path.exists():
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "File not found on disk"})

    return FileResponse(
        str(path),
        filename=doc.get("original_filename", stored),
        media_type=doc.get("content_type", "application/octet-stream"),
    )
