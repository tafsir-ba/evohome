"""
Vault Routes — Canonical Implementation.

Thin route layer. File I/O delegated to file_service.
All data operations delegate to vault_service.
"""
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, Request, Response

from database import db
from core.auth import get_current_user, get_current_agent
from core.access_control import get_workspace_owner_id, get_accessible_project_ids, can_access_project, can_access_vault_doc, can_access_client
from services import vault_service
from services import file_service

logger = logging.getLogger(__name__)

router = APIRouter()



async def _buyer_can_access_vault(buyer_id: str, doc: dict) -> bool:
    """Check if buyer can access vault doc via buyer_ids or client linkage."""
    if buyer_id in doc.get("buyer_ids", []):
        return True
    buyer_clients = await db.clients.find(
        {"buyer_id": buyer_id}, {"_id": 0, "client_id": 1}
    ).to_list(100)
    buyer_client_ids = {c["client_id"] for c in buyer_clients}
    return bool(buyer_client_ids & set(doc.get("client_ids", [])))



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
    scope_agent_id = get_workspace_owner_id(user)
    if project_id:
        if not await can_access_project(user, project_id):
            raise HTTPException(status_code=403, detail={"error": "forbidden", "message": "Access denied"})

    parsed_ids = [cid.strip() for cid in client_ids.split(",") if cid.strip()]
    for cid in parsed_ids:
        c = await db.clients.find_one({"client_id": cid, "agent_id": scope_agent_id})
        if not c:
            raise HTTPException(status_code=400, detail={"error": "not_found", "message": f"Client {cid} not found"})
        if not await can_access_client(user, cid):
            raise HTTPException(status_code=403, detail={"error": "forbidden", "message": f"Access denied to client {cid}"})
        if project_id and c.get("project_id") != project_id:
            raise HTTPException(status_code=400, detail={"error": "invalid_request", "message": f"Client {cid} is not in the selected project"})

    result = await file_service.save_vault_file(file)
    trace_service("services.file_service.save_vault_file")

    doc = await vault_service.create_vault_document(
        agent_id=scope_agent_id,
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
    if project_id and not await can_access_project(user, project_id):
        raise HTTPException(status_code=403, detail={"error": "forbidden", "message": "Access denied"})
    return await vault_service.list_vault_documents(
        get_workspace_owner_id(user),
        project_id,
        None if project_id else await get_accessible_project_ids(user),
    )


@router.get("/vault/categories")
async def get_vault_categories(user: dict = Depends(get_current_agent)):
    return await vault_service.get_categories()


@router.get("/vault/documents/{vault_document_id}")
async def get_vault_document(vault_document_id: str, user: dict = Depends(get_current_user)):
    doc = await vault_service.get_vault_document(vault_document_id)
    if not doc:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Vault document not found"})

    if user["role"] == "agent" and not await can_access_vault_doc(user, vault_document_id):
        raise HTTPException(status_code=403, detail={"error": "forbidden", "message": "Access denied"})
    if user["role"] == "buyer" and not await _buyer_can_access_vault(user["user_id"], doc):
        raise HTTPException(status_code=403, detail={"error": "forbidden", "message": "Access denied"})

    return doc


@router.put("/vault/documents/{vault_document_id}")
async def update_vault_document(vault_document_id: str, request: Request, user: dict = Depends(get_current_agent)):
    if not await can_access_vault_doc(user, vault_document_id):
        raise HTTPException(status_code=403, detail={"error": "forbidden", "message": "Access denied"})
    body = await request.json()
    result = await vault_service.update_vault_document(vault_document_id, get_workspace_owner_id(user), body)
    if not result:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Vault document not found"})
    return result


@router.delete("/vault/documents/{vault_document_id}")
async def delete_vault_document(vault_document_id: str, user: dict = Depends(get_current_agent)):
    if not await can_access_vault_doc(user, vault_document_id):
        raise HTTPException(status_code=403, detail={"error": "forbidden", "message": "Access denied"})
    stored_filename = await vault_service.delete_vault_document(vault_document_id, get_workspace_owner_id(user))
    if stored_filename is None:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Vault document not found"})
    file_service.delete_file(stored_filename)
    return {"message": "Vault document deleted"}


@router.get("/vault/documents/{vault_document_id}/download")
async def download_vault_document(vault_document_id: str, user: dict = Depends(get_current_user)):
    doc = await vault_service.get_vault_document(vault_document_id)
    if not doc:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Vault document not found"})

    if user["role"] == "agent" and not await can_access_vault_doc(user, vault_document_id):
        raise HTTPException(status_code=403, detail={"error": "forbidden", "message": "Access denied"})
    if user["role"] == "buyer" and not await _buyer_can_access_vault(user["user_id"], doc):
        raise HTTPException(status_code=403, detail={"error": "forbidden", "message": "Access denied"})

    stored = doc.get("stored_filename")
    if not stored:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "File not found"})

    try:
        data, detected_media = file_service.read_stored_file_bytes(stored)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "File not found in storage"})
    except ValueError:
        raise HTTPException(status_code=400, detail={"error": "invalid_request", "message": "Invalid file reference"})
    except Exception as e:
        logger.exception("vault download read failed: %s", stored)
        raise HTTPException(status_code=502, detail={"error": "storage_error", "message": str(e)})

    media = doc.get("content_type") or detected_media or "application/octet-stream"
    fname = doc.get("original_filename") or stored
    return Response(
        content=data,
        media_type=media,
        headers={"Content-Disposition": f'inline; filename="{fname}"'},
    )
