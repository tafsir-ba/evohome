"""
Canonical Change Request Service.

Single source of truth for all change request operations.
Supports: quotes, invoices, documents, decisions, and any future entity types.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from database import db

logger = logging.getLogger(__name__)


async def create_change_request(
    entity_type: str,
    entity_id: str,
    message: str,
    created_by: str,
    created_by_role: str,
    agent_id: str,
    project_id: Optional[str] = None,
    attachments: Optional[List[dict]] = None,
) -> Dict[str, Any]:
    """Create a new change request on any entity."""
    cr_id = f"cr_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()

    change_request = {
        "change_request_id": cr_id,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "agent_id": agent_id,
        "project_id": project_id,
        "status": "open",
        "messages": [
            {
                "message_id": f"msg_{uuid.uuid4().hex[:8]}",
                "content": message,
                "author_id": created_by,
                "author_role": created_by_role,
                "created_at": now,
                "attachments": attachments or [],
            }
        ],
        "created_by": created_by,
        "created_by_role": created_by_role,
        "created_at": now,
        "updated_at": now,
        "resolved_at": None,
    }

    await db.change_requests.insert_one(change_request)

    # Also update entity status to 'Change Requested' for backwards compatibility
    collection = _get_entity_collection(entity_type)
    id_field = _get_entity_id_field(entity_type)
    if collection and id_field:
        await db[collection].update_one(
            {id_field: entity_id},
            {"$set": {"status": "Change Requested", "change_request_comment": message, "updated_at": now}}
        )

    logger.info(f"Change request {cr_id} created on {entity_type}/{entity_id} by {created_by}")
    change_request.pop("_id", None)
    return change_request


async def respond_to_change_request(
    change_request_id: str,
    message: str,
    author_id: str,
    author_role: str,
    attachments: Optional[List[dict]] = None,
) -> Dict[str, Any]:
    """Add a response message to a change request."""
    now = datetime.now(timezone.utc).isoformat()

    new_message = {
        "message_id": f"msg_{uuid.uuid4().hex[:8]}",
        "content": message,
        "author_id": author_id,
        "author_role": author_role,
        "created_at": now,
        "attachments": attachments or [],
    }

    result = await db.change_requests.find_one_and_update(
        {"change_request_id": change_request_id},
        {
            "$push": {"messages": new_message},
            "$set": {"status": "under_review", "updated_at": now},
        },
        return_document=True,
        projection={"_id": 0},
    )

    if not result:
        raise ValueError(f"Change request {change_request_id} not found")

    logger.info(f"Response added to {change_request_id} by {author_id}")
    return result


async def resolve_change_request(
    change_request_id: str,
    resolved_by: str,
    resolution_note: Optional[str] = None,
) -> Dict[str, Any]:
    """Mark a change request as resolved."""
    now = datetime.now(timezone.utc).isoformat()

    update = {
        "$set": {"status": "resolved", "resolved_at": now, "updated_at": now}
    }

    if resolution_note:
        update["$push"] = {
            "messages": {
                "message_id": f"msg_{uuid.uuid4().hex[:8]}",
                "content": resolution_note,
                "author_id": resolved_by,
                "author_role": "agent",
                "created_at": now,
                "attachments": [],
            }
        }

    result = await db.change_requests.find_one_and_update(
        {"change_request_id": change_request_id},
        update,
        return_document=True,
        projection={"_id": 0},
    )

    if not result:
        raise ValueError(f"Change request {change_request_id} not found")

    # Update entity status back
    collection = _get_entity_collection(result["entity_type"])
    id_field = _get_entity_id_field(result["entity_type"])
    if collection and id_field:
        await db[collection].update_one(
            {id_field: result["entity_id"]},
            {"$set": {"status": "Draft", "change_request_comment": None, "updated_at": now}}
        )

    logger.info(f"Change request {change_request_id} resolved by {resolved_by}")
    return result


async def close_change_request(
    change_request_id: str,
    closed_by: str,
) -> Dict[str, Any]:
    """Close a change request (final state)."""
    now = datetime.now(timezone.utc).isoformat()

    result = await db.change_requests.find_one_and_update(
        {"change_request_id": change_request_id},
        {"$set": {"status": "closed", "updated_at": now}},
        return_document=True,
        projection={"_id": 0},
    )

    if not result:
        raise ValueError(f"Change request {change_request_id} not found")

    logger.info(f"Change request {change_request_id} closed by {closed_by}")
    return result


async def list_change_requests(
    agent_id: str,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    """List change requests for an agent with optional filters."""
    query = {"agent_id": agent_id}
    if entity_type:
        query["entity_type"] = entity_type
    if entity_id:
        query["entity_id"] = entity_id
    if status:
        query["status"] = status

    total = await db.change_requests.count_documents(query)
    items = await db.change_requests.find(
        query, {"_id": 0}
    ).sort("updated_at", -1).skip(offset).limit(limit).to_list(limit)

    return {"change_requests": items, "total": total}


async def get_change_request(change_request_id: str) -> Optional[Dict[str, Any]]:
    """Get a single change request by ID."""
    cr = await db.change_requests.find_one(
        {"change_request_id": change_request_id}, {"_id": 0}
    )
    return cr


async def get_change_requests_for_entity(entity_type: str, entity_id: str) -> List[Dict[str, Any]]:
    """Get all change requests for a specific entity."""
    items = await db.change_requests.find(
        {"entity_type": entity_type, "entity_id": entity_id},
        {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    return items


def _get_entity_collection(entity_type: str) -> Optional[str]:
    """Map entity type to MongoDB collection."""
    mapping = {
        "quote": "documents",
        "invoice": "documents",
        "document": "documents",
        "decision": "decisions",
    }
    return mapping.get(entity_type)


def _get_entity_id_field(entity_type: str) -> Optional[str]:
    """Map entity type to its ID field name."""
    mapping = {
        "quote": "document_id",
        "invoice": "document_id",
        "document": "document_id",
        "decision": "decision_id",
    }
    return mapping.get(entity_type)
