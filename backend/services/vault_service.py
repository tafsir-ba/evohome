"""
Vault Service — Canonical Implementation.

No is_demo. VaultDocument is separate from Document.
Vault is storage/shared repository logic.
"""
import os
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from database import db
from services.notification_service import emit_notification

logger = logging.getLogger(__name__)

VAULT_CATEGORIES = ["general", "action_required"]


# ── Core CRUD ──

async def create_vault_document(
    agent_id: str,
    project_id: str,
    client_ids: List[str],
    title: str,
    category: str,
    description: Optional[str],
    filename: str,
    file_path: str,
    file_size: int,
) -> Dict[str, Any]:
    """Create a vault document shared with one or more clients."""
    doc_id = f"vault_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()

    # Resolve buyer_ids from clients
    buyer_ids = []
    for cid in client_ids:
        c = await db.clients.find_one({"client_id": cid}, {"_id": 0, "buyer_id": 1})
        if c and c.get('buyer_id'):
            buyer_ids.append(c['buyer_id'])

    doc = {
        "vault_document_id": doc_id,
        "agent_id": agent_id,
        "project_id": project_id,
        "client_ids": client_ids,
        "buyer_ids": buyer_ids,
        "title": title,
        "category": category,
        "description": description or '',
        "filename": filename,
        "file_path": file_path,
        "file_size": file_size,
        "created_at": now,
        "updated_at": now,
    }
    await db.vault_documents.insert_one(doc)
    doc.pop('_id', None)

    # Notify buyers
    for bid in buyer_ids:
        await emit_notification(
            user_id=bid,
            title="New Document Shared",
            message=f"Your agent shared '{title}' with you",
            notification_type="vault_document",
            link="/buyer/vault",
            metadata={"vault_document_id": doc_id},
        )

    return doc


async def list_vault_documents(agent_id: str, project_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """List vault documents for an agent."""
    query = {"agent_id": agent_id}
    if project_id:
        query["project_id"] = project_id
    return await db.vault_documents.find(query, {"_id": 0, "is_demo": 0}).sort("created_at", -1).to_list(200)


async def list_buyer_vault(buyer_id: str) -> List[Dict[str, Any]]:
    """List vault documents shared with a buyer."""
    return await db.vault_documents.find(
        {"buyer_ids": buyer_id}, {"_id": 0, "is_demo": 0}
    ).sort("created_at", -1).to_list(200)


async def get_vault_document(vault_document_id: str) -> Optional[Dict[str, Any]]:
    """Get a single vault document."""
    return await db.vault_documents.find_one(
        {"vault_document_id": vault_document_id}, {"_id": 0, "is_demo": 0}
    )


async def update_vault_document(
    vault_document_id: str, agent_id: str, updates: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """Update title, description, category of a vault document."""
    query = {"vault_document_id": vault_document_id, "agent_id": agent_id}
    doc = await db.vault_documents.find_one(query, {"_id": 0})
    if not doc:
        return None

    allowed = {"title", "description", "category"}
    filtered = {k: v for k, v in updates.items() if k in allowed and v is not None}
    filtered["updated_at"] = datetime.now(timezone.utc).isoformat()

    await db.vault_documents.update_one(query, {"$set": filtered})
    return await db.vault_documents.find_one(query, {"_id": 0, "is_demo": 0})


async def delete_vault_document(vault_document_id: str, agent_id: str) -> bool:
    """Delete a vault document and its file."""
    query = {"vault_document_id": vault_document_id, "agent_id": agent_id}
    doc = await db.vault_documents.find_one(query, {"_id": 0})
    if not doc:
        return False

    if doc.get('file_path') and os.path.exists(doc['file_path']):
        try:
            os.remove(doc['file_path'])
        except Exception:
            pass

    await db.vault_documents.delete_one(query)
    return True


async def get_categories() -> List[Dict[str, str]]:
    """Return vault document category options."""
    return [
        {"value": "general", "label": "General Documents"},
        {"value": "action_required", "label": "Action Required"},
    ]
