"""
Vault Service — Canonical Implementation.

Single source of truth for vault document operations.
File I/O delegated to file_service. No direct disk access here.
"""
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from database import db
from services.notification_service import emit_notification

logger = logging.getLogger(__name__)

VAULT_CATEGORIES = ["contracts", "plans", "permits", "reports", "other"]


async def create_vault_document(
    agent_id: str,
    project_id: str,
    client_ids: List[str],
    title: str,
    category: str,
    description: Optional[str],
    access_level: str,
    doc_type: str,
    stored_filename: str,
    original_filename: str,
    file_size: int,
    content_type: str,
) -> Dict[str, Any]:
    """Create a vault document. Returns canonical document dict."""
    doc_id = f"vault_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()

    if category not in VAULT_CATEGORIES:
        category = "other"

    if access_level not in ("private", "shared"):
        access_level = "private"

    if doc_type not in ("general", "action_required"):
        doc_type = "general"

    buyer_ids = []
    for cid in client_ids:
        c = await db.clients.find_one({"client_id": cid}, {"_id": 0, "buyer_id": 1})
        if c and c.get("buyer_id"):
            buyer_ids.append(c["buyer_id"])

    doc = {
        "vault_document_id": doc_id,
        "agent_id": agent_id,
        "project_id": project_id,
        "client_ids": client_ids,
        "buyer_ids": buyer_ids,
        "title": title,
        "category": category,
        "doc_type": doc_type,
        "description": description or "",
        "access_level": access_level,
        "stored_filename": stored_filename,
        "original_filename": original_filename,
        "file_size": file_size,
        "content_type": content_type,
        "created_at": now,
        "updated_at": now,
    }
    await db.vault_documents.insert_one(doc)
    doc.pop("_id", None)

    from core.trace import trace_service, trace_db_mutation, trace_side_effect
    trace_service("services.vault_service.create_vault_document")
    trace_db_mutation("vault_documents", "insert_one", doc_id)

    for bid in buyer_ids:
        await emit_notification(
            user_id=bid,
            title="New Document Shared",
            message=f"Your agent shared '{title}' with you",
            notification_type="vault_document",
            link="/buyer/vault",
            metadata={"vault_document_id": doc_id},
        )
        trace_side_effect("notification", target=bid, detail=f"vault_document shared: {title}")

    return doc


async def list_vault_documents(agent_id: str, project_id: Optional[str] = None) -> List[Dict[str, Any]]:
    query = {"agent_id": agent_id}
    if project_id:
        query["project_id"] = project_id
    return await db.vault_documents.find(query, {"_id": 0}).sort("created_at", -1).to_list(200)


async def list_buyer_vault(buyer_id: str) -> List[Dict[str, Any]]:
    # Find all client_ids linked to this buyer
    buyer_clients = await db.clients.find(
        {"buyer_id": buyer_id}, {"_id": 0, "client_id": 1}
    ).to_list(100)
    buyer_client_ids = [c["client_id"] for c in buyer_clients]

    # Match by buyer_ids OR by client_ids (handles race condition where buyer registered after doc was shared)
    query = {"access_level": "shared"}
    if buyer_client_ids:
        query["$or"] = [
            {"buyer_ids": buyer_id},
            {"client_ids": {"$in": buyer_client_ids}},
        ]
    else:
        query["buyer_ids"] = buyer_id

    return await db.vault_documents.find(
        query, {"_id": 0}
    ).sort("created_at", -1).to_list(200)


async def get_vault_document(vault_document_id: str) -> Optional[Dict[str, Any]]:
    return await db.vault_documents.find_one(
        {"vault_document_id": vault_document_id}, {"_id": 0}
    )


async def update_vault_document(
    vault_document_id: str, agent_id: str, updates: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """Update vault document metadata. Supports title, description, category, access_level, client_ids, project_id."""
    query = {"vault_document_id": vault_document_id, "agent_id": agent_id}
    doc = await db.vault_documents.find_one(query, {"_id": 0})
    if not doc:
        return None

    allowed = {"title", "description", "category", "access_level", "client_ids", "project_id", "doc_type"}
    filtered = {}
    for k in allowed:
        if k in updates:
            filtered[k] = updates[k]

    # Validate category
    if "category" in filtered and filtered["category"] not in VAULT_CATEGORIES:
        filtered["category"] = "other"

    # Validate access_level
    if "access_level" in filtered and filtered["access_level"] not in ("private", "shared"):
        filtered["access_level"] = "private"

    # Re-resolve buyer_ids when client_ids change
    if "client_ids" in filtered:
        buyer_ids = []
        for cid in filtered["client_ids"]:
            c = await db.clients.find_one({"client_id": cid}, {"_id": 0, "buyer_id": 1})
            if c and c.get("buyer_id"):
                buyer_ids.append(c["buyer_id"])
        filtered["buyer_ids"] = buyer_ids

    filtered["updated_at"] = datetime.now(timezone.utc).isoformat()

    await db.vault_documents.update_one(query, {"$set": filtered})
    return await db.vault_documents.find_one(query, {"_id": 0})


async def delete_vault_document(vault_document_id: str, agent_id: str) -> Optional[str]:
    """Delete vault document from DB. Returns stored_filename for file cleanup, or None."""
    query = {"vault_document_id": vault_document_id, "agent_id": agent_id}
    doc = await db.vault_documents.find_one(query, {"_id": 0})
    if not doc:
        return None

    await db.vault_documents.delete_one(query)
    return doc.get("stored_filename")


async def get_categories() -> List[Dict[str, str]]:
    return [
        {"value": c, "label": c.replace("_", " ").title()}
        for c in VAULT_CATEGORIES
    ]
