"""
Canonical Change Request Service.

Single source of truth for all change request operations.
One change_requests collection. Message history embedded inside the CR document.
No second hidden comment system anywhere else.

Supports: quotes, invoices, decisions, and any future entity types.
Quote and invoice behavior is IDENTICAL. No entity-specific logic except
for the revert status on resolve (Sent for documents, none for decisions).
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from database import db

logger = logging.getLogger(__name__)

# ── Allowed state transitions ──
ALLOWED_TRANSITIONS = {
    "open": {"under_review", "resolved"},
    "under_review": {"resolved"},
    "resolved": {"closed"},
    # closed is terminal — no transitions out
}


def _can_transition(current: str, target: str) -> bool:
    return target in ALLOWED_TRANSITIONS.get(current, set())


# ── Entity mapping ──

def _get_entity_collection(entity_type: str) -> Optional[str]:
    return {"quote": "documents", "invoice": "documents", "document": "documents", "decision": "decisions"}.get(entity_type)


def _get_entity_id_field(entity_type: str) -> Optional[str]:
    return {"quote": "document_id", "invoice": "document_id", "document": "document_id", "decision": "decision_id"}.get(entity_type)


# ── Core operations ──

async def supersede_open_change_requests_for_entity(
    entity_type: str,
    entity_id: str,
    resolution_note: str,
    resolved_by_user_id: str,
    author_role_for_note: str = "buyer",
) -> int:
    """
    Mark open/under_review CRs for this entity as resolved without touching the entity row.
    Used before a new CR, after resend, or when the agent moves the document to Draft.
    """
    now = datetime.now(timezone.utc).isoformat()
    query = {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "status": {"$in": ["open", "under_review"]},
    }
    crs = await db.change_requests.find(query, {"_id": 0, "change_request_id": 1}).to_list(50)
    n = 0
    for row in crs:
        cid = row["change_request_id"]
        msg = {
            "message_id": f"msg_{uuid.uuid4().hex[:8]}",
            "content": resolution_note,
            "author_id": resolved_by_user_id,
            "author_role": author_role_for_note,
            "created_at": now,
            "attachments": [],
        }
        await db.change_requests.update_one(
            {"change_request_id": cid},
            {
                "$set": {
                    "status": "resolved",
                    "resolved_at": now,
                    "updated_at": now,
                },
                "$push": {"messages": msg},
            },
        )
        n += 1
    return n


async def resolve_open_change_requests_after_sent_document(
    entity_type: str,
    document_id: str,
    agent_id: str,
    resolution_note: str = "Addressed by sending an updated document.",
) -> int:
    """After send_document from Change Requested: close out open CR threads without changing the document again."""
    return await supersede_open_change_requests_for_entity(
        entity_type,
        document_id,
        resolution_note,
        resolved_by_user_id=agent_id,
        author_role_for_note="agent",
    )


async def create_change_request(
    entity_type: str,
    entity_id: str,
    message: str,
    created_by: str,
    created_by_role: str,
    agent_id: str,
    project_id: Optional[str] = None,
    attachments: Optional[List[dict]] = None,
    *,
    update_entity: bool = True,
    notify_agent_on_buyer_create: bool = True,
    supersede_prior_open: bool = True,
) -> Dict[str, Any]:
    """Create a new change request on any entity.

    When ``update_entity`` is False, the caller has already updated the entity (e.g. document_action);
    skip duplicate writes and use ``notify_agent_on_buyer_create`` to avoid duplicate agent notifications.
    For quote/invoice, prior open CRs are superseded when ``supersede_prior_open`` is True.
    """
    cr_id = f"cr_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()

    if supersede_prior_open and entity_type in ("quote", "invoice"):
        await supersede_open_change_requests_for_entity(
            entity_type,
            entity_id,
            resolution_note="Superseded by a new change request.",
            resolved_by_user_id=created_by,
            author_role_for_note=created_by_role,
        )

    # Resolve buyer_id from the entity's client relationship
    buyer_id = None
    if created_by_role == "buyer":
        buyer_id = created_by
    else:
        # Agent creating a CR — resolve buyer from entity
        collection = _get_entity_collection(entity_type)
        id_field = _get_entity_id_field(entity_type)
        if collection and id_field:
            entity = await db[collection].find_one({id_field: entity_id}, {"_id": 0, "buyer_id": 1, "client_id": 1})
            if entity:
                buyer_id = entity.get("buyer_id")
                if not buyer_id and entity.get("client_id"):
                    client = await db.clients.find_one({"client_id": entity["client_id"]}, {"_id": 0, "buyer_id": 1})
                    buyer_id = client.get("buyer_id") if client else None

    change_request = {
        "change_request_id": cr_id,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "agent_id": agent_id,
        "buyer_id": buyer_id,
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

    # Trace
    from core.trace import trace_service, trace_db_mutation, trace_side_effect, set_trace_entity, trace_related_entity
    trace_service("services.change_request_service.create_change_request")
    trace_db_mutation("change_requests", "insert_one", cr_id)
    set_trace_entity("change_request", cr_id)
    trace_related_entity(entity_type, entity_id)

    # Update entity status to 'Change Requested' + denormalized comment
    if update_entity:
        collection = _get_entity_collection(entity_type)
        id_field = _get_entity_id_field(entity_type)
        if collection and id_field:
            await db[collection].update_one(
                {id_field: entity_id},
                {"$set": {"status": "Change Requested", "change_request_comment": message, "updated_at": now}}
            )

    logger.info(f"Change request {cr_id} created on {entity_type}/{entity_id} by {created_by}")
    change_request.pop("_id", None)

    # Notify agent when buyer creates a CR
    if (
        notify_agent_on_buyer_create
        and created_by_role == "buyer"
        and agent_id
    ):
        await _notify(
            user_id=agent_id,
            title="New Change Request",
            message_text=f"Change requested on {entity_type}: {message[:100]}",
            notification_type="change_request_created",
            data={"change_request_id": cr_id, "entity_type": entity_type, "entity_id": entity_id},
        )

    return change_request


async def respond_to_change_request(
    change_request_id: str,
    message: str,
    author_id: str,
    author_role: str,
    attachments: Optional[List[dict]] = None,
    agent_scope_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Add a response message to a change request."""
    cr = await db.change_requests.find_one({"change_request_id": change_request_id}, {"_id": 0})
    if not cr:
        raise ValueError(f"Change request {change_request_id} not found")
    if cr["status"] not in ("open", "under_review"):
        raise ValueError(f"Cannot respond to change request in status '{cr['status']}'")

    if author_role == "agent" and cr.get("agent_id") not in {author_id, agent_scope_id}:
        raise ValueError("Not authorized to respond to this change request")
    if author_role == "buyer":
        buyer_ref = cr.get("buyer_id") or cr.get("created_by")
        if buyer_ref != author_id:
            raise ValueError("Not authorized to respond to this change request")

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

    from core.trace import trace_service, trace_db_mutation, trace_side_effect
    trace_service("services.change_request_service.respond_to_change_request")
    trace_db_mutation("change_requests", "find_one_and_update", change_request_id)

    # Notify the other party
    if author_role == "agent":
        buyer_id = result.get("buyer_id") or result.get("created_by")
        if buyer_id and buyer_id != author_id:
            await _notify(
                user_id=buyer_id,
                title="Change Request Response",
                message_text=f"Your agent responded: {message[:100]}",
                notification_type="change_request_response",
                data={"change_request_id": change_request_id, "entity_type": result.get("entity_type"), "entity_id": result.get("entity_id")},
            )
            trace_side_effect("notification", target=buyer_id, detail="change_request_response")
    elif author_role == "buyer":
        agent_id = result.get("agent_id")
        if agent_id:
            await _notify(
                user_id=agent_id,
                title="New Change Request Message",
                message_text=f"Buyer sent a message: {message[:100]}",
                notification_type="change_request_message",
                data={"change_request_id": change_request_id, "entity_type": result.get("entity_type"), "entity_id": result.get("entity_id")},
            )
            trace_side_effect("notification", target=agent_id, detail="change_request_message")

    logger.info(f"Response added to {change_request_id} by {author_id}")
    return result


async def resolve_change_request(
    change_request_id: str,
    resolved_by: str,
    resolution_note: Optional[str] = None,
    agent_scope_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Mark a change request as resolved. Document reverts to Sent (NEVER Draft)."""
    # Verify current status allows transition
    cr = await db.change_requests.find_one({"change_request_id": change_request_id}, {"_id": 0, "status": 1, "agent_id": 1})
    if not cr:
        raise ValueError(f"Change request {change_request_id} not found")
    if cr.get("agent_id") not in {resolved_by, agent_scope_id}:
        raise ValueError("Not authorized to resolve this change request")
    if not _can_transition(cr["status"], "resolved"):
        raise ValueError(f"Cannot resolve change request in status '{cr['status']}'")

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

    from core.trace import trace_service, trace_db_mutation, trace_side_effect, trace_related_entity
    trace_service("services.change_request_service.resolve_change_request")
    trace_db_mutation("change_requests", "find_one_and_update", change_request_id)

    # Revert entity status — ALWAYS to Sent for documents, never Draft
    collection = _get_entity_collection(result["entity_type"])
    id_field = _get_entity_id_field(result["entity_type"])
    if collection and id_field:
        revert_status = "Sent" if result["entity_type"] in ("invoice", "quote") else None
        update_fields = {"change_request_comment": None, "updated_at": now}
        if revert_status:
            update_fields["status"] = revert_status
        await db[collection].update_one(
            {id_field: result["entity_id"]},
            {"$set": update_fields}
        )
        trace_db_mutation(collection, "update_one", result["entity_id"])
        trace_related_entity(result["entity_type"], result["entity_id"])

    # Notify buyer that CR is resolved
    buyer_id = result.get("buyer_id") or result.get("created_by")
    if buyer_id and buyer_id != resolved_by:
        await _notify(
            user_id=buyer_id,
            title="Change Request Resolved",
            message_text=f"Your change request on {result.get('entity_type', 'document')} has been resolved",
            notification_type="change_request_resolved",
            data={"change_request_id": change_request_id, "entity_type": result.get("entity_type"), "entity_id": result.get("entity_id")},
        )
        trace_side_effect("notification", target=buyer_id, detail="change_request_resolved")

    logger.info(f"Change request {change_request_id} resolved by {resolved_by}")
    return result


async def close_change_request(
    change_request_id: str,
    closed_by: str,
    agent_scope_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Close a change request (final state). No notification."""
    cr = await db.change_requests.find_one({"change_request_id": change_request_id}, {"_id": 0, "status": 1, "agent_id": 1})
    if not cr:
        raise ValueError(f"Change request {change_request_id} not found")
    if cr.get("agent_id") not in {closed_by, agent_scope_id}:
        raise ValueError("Not authorized to close this change request")
    if not _can_transition(cr["status"], "closed"):
        raise ValueError(f"Cannot close change request in status '{cr['status']}'")

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


# ── Query operations ──

async def list_change_requests(
    agent_id: str,
    accessible_project_ids: Optional[List[str]] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    """List change requests for an agent with optional filters."""
    query = {"agent_id": agent_id}
    if accessible_project_ids is not None:
        if not accessible_project_ids:
            return {"change_requests": [], "total": 0}
        query["project_id"] = {"$in": accessible_project_ids}
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
    return await db.change_requests.find_one(
        {"change_request_id": change_request_id}, {"_id": 0}
    )


async def get_change_requests_for_entity(entity_type: str, entity_id: str) -> List[Dict[str, Any]]:
    return await db.change_requests.find(
        {"entity_type": entity_type, "entity_id": entity_id},
        {"_id": 0}
    ).sort("created_at", -1).to_list(50)


# ── Private helpers ──

async def _notify(user_id: str, title: str, message_text: str, notification_type: str, data: dict):
    """Create a notification. Failure is non-blocking."""
    try:
        from services.notification_service import create_notification
        from core.notification_routing import compute_notification_link

        u = await db.users.find_one({"user_id": user_id}, {"_id": 0, "role": 1})
        role = (u or {}).get("role") or "buyer"
        link = compute_notification_link(notification_type, data, role, None)
        await create_notification(
            user_id=user_id,
            title=title,
            message=message_text,
            notification_type=notification_type,
            link=link,
            metadata=data,
        )
    except Exception as e:
        logger.warning(f"Failed to create notification ({notification_type}): {e}")
