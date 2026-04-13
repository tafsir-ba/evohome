"""
Document Service — Canonical Implementation.

No is_demo. Document is the master transactional/shared object.
Status machine is explicit and finite. Attachments belong to document.
PDF/QR generation are utilities, not domain truth.
AI extraction is assistive only, never source of truth.
"""
import os
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any

from database import db
from helpers import validate_transition
from services.notification_service import emit_notification, emit_email, emit_realtime
from pymongo import ReturnDocument

logger = logging.getLogger(__name__)

VALID_DOC_TYPES = {"quote", "invoice"}
FINALIZED_STATUSES = {"Approved", "Paid"}


def _coerce_client_ids(values: Optional[List[str]]) -> List[str]:
    if not values:
        return []
    seen = set()
    out: List[str] = []
    for v in values:
        cid = str(v or "").strip()
        if cid and cid not in seen:
            seen.add(cid)
            out.append(cid)
    return out


# ── Core CRUD ──

async def _next_document_number(agent_id: str, doc_type: str) -> str:
    """Generate document numbers atomically to avoid concurrent collisions."""
    year = datetime.now(timezone.utc).year
    prefix = "INV" if doc_type == "invoice" else "QT"
    counter_key = f"docnum:{agent_id}:{doc_type}:{year}"

    counter = await db.counters.find_one_and_update(
        {"counter_key": counter_key},
        {
            "$inc": {"value": 1},
            "$setOnInsert": {
                "counter_key": counter_key,
                "agent_id": agent_id,
                "doc_type": doc_type,
                "year": year,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        },
        upsert=True,
        return_document=ReturnDocument.AFTER,
        projection={"_id": 0, "value": 1},
    )
    sequence = int(counter.get("value", 1))
    return f"{prefix}-{year}-{str(sequence).zfill(4)}"

async def create_document(
    agent_id: str,
    doc_type: str,
    client_id: str,
    title: str,
    amount: float,
    items: List[dict],
    supplier_name: Optional[str] = None,
    notes: Optional[str] = None,
    summary: Optional[str] = None,
    due_date: Optional[str] = None,
    pdf_filename: Optional[str] = None,
    pdf_stored_filename: Optional[str] = None,
    ai_extraction_confidence: Optional[str] = None,
    approver_client_ids: Optional[List[str]] = None,
    approval_required_count: Optional[int] = None,
) -> Dict[str, Any]:
    """Create a document. Returns the created document dict."""
    client = await db.clients.find_one(
        {"client_id": client_id, "agent_id": agent_id}, {"_id": 0}
    )
    if not client:
        raise ValueError("Client not found")

    if doc_type not in VALID_DOC_TYPES:
        raise ValueError("Invalid document type")
    doc_number = await _next_document_number(agent_id, doc_type)

    doc_id = f"doc_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()

    parsed_due = _parse_due_date(due_date, doc_type)

    # Resolve unit_reference from unit_id if client has one
    unit_id = client.get('unit_id')
    unit_reference = client.get('unit_reference', 'General')
    if not unit_reference or unit_reference == 'General':
        if unit_id:
            unit = await db.units.find_one({"unit_id": unit_id}, {"_id": 0, "unit_reference": 1})
            if unit:
                unit_reference = unit.get('unit_reference', 'General')

    # Resolve project_name
    project_name = None
    project_id = client.get('project_id')
    if project_id:
        project = await db.projects.find_one({"project_id": project_id}, {"_id": 0, "name": 1})
        if project:
            project_name = project.get('name')

    draft_approvers = _coerce_client_ids(approver_client_ids or [client_id]) or [client_id]
    draft_required = int(approval_required_count or 1)
    draft_required = max(1, min(draft_required, len(draft_approvers)))

    doc = {
        "document_id": doc_id,
        "document_number": doc_number,
        "type": doc_type,
        "status": "Draft",
        "agent_id": agent_id,
        "client_id": client_id,
        "buyer_id": client.get('buyer_id'),
        "project_id": project_id,
        "project_name": project_name,
        "unit_id": unit_id,
        "unit_reference": unit_reference,
        "recipient_client_ids": [client_id],
        "approver_client_ids": draft_approvers,
        "approval_required_count": draft_required,
        "approvals_received_client_ids": [],
        "title": title,
        "amount": float(amount),
        "items": items,
        "currency": "CHF",
        "supplier_name": supplier_name,
        "notes": notes,
        "summary": summary or '',
        "hero_image_url": None,
        "hero_image_stored_filename": None,
        "change_request_comment": None,
        "pdf_filename": pdf_filename,
        "pdf_stored_filename": pdf_stored_filename,
        "ai_extraction_confidence": ai_extraction_confidence,
        "parent_document_id": None,
        "due_date": parsed_due,
        "paid_date": None,
        "created_at": now,
        "updated_at": now,
    }
    await db.documents.insert_one(doc)

    # Trace: document creation
    try:
        from core.trace import trace_service, trace_db_mutation, set_trace_entity, set_trace_response_summary
        trace_service("services.document_service.create_document")
        trace_db_mutation("documents", "insert_one", doc_id)
        set_trace_entity("document", doc_id)
        set_trace_response_summary({"status": "Draft", "type": doc_type, "amount": float(amount)})
    except Exception:
        pass

    result = await db.documents.find_one({"document_id": doc_id}, {"_id": 0})
    return result


async def get_document(document_id: str, user_id: str, role: str) -> Optional[Dict[str, Any]]:
    """Get a single document, access-scoped."""
    query = {"document_id": document_id}
    if role == 'agent':
        query["agent_id"] = user_id
    else:
        client_ids = await _get_buyer_client_ids(user_id)
        query["$or"] = [
            {"client_id": {"$in": client_ids}},
            {"recipient_client_ids": {"$in": client_ids}},
        ]

    doc = await db.documents.find_one(query, {"_id": 0})
    if not doc:
        return None

    client = await db.clients.find_one({"client_id": doc['client_id']}, {"_id": 0})
    project = await db.projects.find_one({"project_id": doc['project_id']}, {"_id": 0})
    return {**doc, "client": client, "project": project}


async def list_documents(
    user_id: str, role: str,
    doc_type: Optional[str] = None, status: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """List documents for a user, role-scoped."""
    query = {}
    if role == 'agent':
        query["agent_id"] = user_id
    else:
        client_ids = await _get_buyer_client_ids(user_id)
        query["$or"] = [
            {"client_id": {"$in": client_ids}},
            {"recipient_client_ids": {"$in": client_ids}},
        ]

    if doc_type:
        query["type"] = doc_type
    if status:
        query["status"] = status

    docs = await db.documents.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)

    # Batch enrich with project_name and client_name for display
    project_ids = list({d["project_id"] for d in docs if d.get("project_id")})
    client_ids = list({d["client_id"] for d in docs if d.get("client_id")})

    if project_ids:
        projects = await db.projects.find(
            {"project_id": {"$in": project_ids}}, {"_id": 0, "project_id": 1, "name": 1}
        ).to_list(len(project_ids))
        proj_map = {p["project_id"]: p["name"] for p in projects}
        for d in docs:
            if not d.get("project_name"):
                d["project_name"] = proj_map.get(d.get("project_id"))

    if client_ids:
        clients = await db.clients.find(
            {"client_id": {"$in": client_ids}}, {"_id": 0, "client_id": 1, "name": 1}
        ).to_list(len(client_ids))
        client_map = {c["client_id"]: c["name"] for c in clients}
        for d in docs:
            if not d.get("client_name"):
                d["client_name"] = client_map.get(d.get("client_id"))

    return docs


async def update_document(document_id: str, agent_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Update document fields. Agent only. Not allowed on finalized docs."""
    query = {"document_id": document_id, "agent_id": agent_id}
    doc = await db.documents.find_one(query, {"_id": 0})
    if not doc:
        return None
    if doc['status'] in FINALIZED_STATUSES:
        raise ValueError(f"Cannot edit document with status '{doc['status']}'")

    update_data = {}
    # Revert to Draft if editing a rejected or change-requested doc
    if doc['status'] in ('Rejected', 'Change Requested'):
        update_data['status'] = 'Draft'

    for k in ('title', 'amount', 'supplier_name', 'notes', 'summary', 'hero_image_url'):
        if k in updates and updates[k] is not None:
            update_data[k] = updates[k]

    if 'approver_client_ids' in updates and updates['approver_client_ids'] is not None:
        update_data['approver_client_ids'] = _coerce_client_ids(updates.get('approver_client_ids'))
    if 'approval_required_count' in updates and updates['approval_required_count'] is not None:
        update_data['approval_required_count'] = int(updates.get('approval_required_count') or 1)

    if 'items' in updates and updates['items'] is not None:
        update_data['items'] = updates['items']
        if 'amount' not in updates or updates['amount'] is None:
            update_data['amount'] = sum(i.get('total', 0) for i in updates['items'])

    # Reference changes (project, client, unit)
    if 'project_id' in updates and updates['project_id'] and updates['project_id'] != doc.get('project_id'):
        project = await db.projects.find_one({"project_id": updates['project_id'], "agent_id": agent_id})
        if not project:
            raise ValueError("Invalid project")
        update_data['project_id'] = updates['project_id']

    if 'client_id' in updates and updates['client_id'] and updates['client_id'] != doc.get('client_id'):
        client = await db.clients.find_one({"client_id": updates['client_id'], "agent_id": agent_id})
        if not client:
            raise ValueError("Invalid client")
        update_data['client_id'] = updates['client_id']

    if 'unit_id' in updates:
        uid = updates['unit_id']
        if uid == "" or uid is None:
            update_data['unit_id'] = None
            update_data['unit_reference'] = "General"
        else:
            target_pid = updates.get('project_id') or doc.get('project_id')
            unit = await db.units.find_one({"unit_id": uid, "project_id": target_pid})
            if not unit:
                raise ValueError("Invalid unit for this project")
            update_data['unit_id'] = uid
            update_data['unit_reference'] = unit.get('unit_reference', unit.get('name', 'Unit'))

    update_data['updated_at'] = datetime.now(timezone.utc).isoformat()
    await db.documents.update_one(query, {"$set": update_data})

    if doc["status"] == "Change Requested" and update_data.get("status") == "Draft":
        from services.change_request_service import supersede_open_change_requests_for_entity
        et = doc["type"].lower()
        if et in ("quote", "invoice"):
            await supersede_open_change_requests_for_entity(
                et,
                document_id,
                resolution_note="Agent is revising the document in draft.",
                resolved_by_user_id=agent_id,
                author_role_for_note="agent",
            )

    return await db.documents.find_one(query, {"_id": 0})


async def delete_document(document_id: str, agent_id: str, force: bool = False) -> bool:
    """Delete a document with lifecycle safety guards."""
    query = {"document_id": document_id, "agent_id": agent_id}
    doc = await db.documents.find_one(query, {"_id": 0})
    if not doc:
        return False
    if doc['status'] in FINALIZED_STATUSES:
        raise ValueError(f"Cannot delete document with final status '{doc['status']}'")
    if doc['status'] != 'Draft' and not force:
        raise ValueError("Can only delete non-draft document with force=true")

    # Cleanup files via file_service
    from services.file_service import delete_file
    for fk in ('pdf_stored_filename', 'hero_image_stored_filename'):
        if doc.get(fk):
            delete_file(doc[fk])
    # Backward compatibility: clean up legacy absolute paths
    for fk in ('pdf_path', 'hero_image_path'):
        if doc.get(fk) and os.path.exists(doc[fk]):
            try:
                os.remove(doc[fk])
            except Exception:
                pass

    await db.documents.delete_one(query)
    await db.change_requests.delete_many({"entity_id": document_id})
    return True


async def revert_to_draft(document_id: str, agent_id: str) -> Optional[str]:
    """Revert document to Draft. Returns new status or None."""
    query = {"document_id": document_id, "agent_id": agent_id}
    doc = await db.documents.find_one(query, {"_id": 0})
    if not doc:
        return None
    if doc['status'] in FINALIZED_STATUSES:
        raise ValueError(f"Cannot revert from '{doc['status']}'. This status is final.")
    if doc['status'] == 'Draft':
        return "Draft"

    await db.documents.update_one(
        query, {"$set": {"status": "Draft", "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    return "Draft"


# ── Status machine ──

async def send_document(
    document_id: str,
    agent_id: str,
    agent_user: dict,
    approver_client_ids: Optional[List[str]] = None,
    approval_required_count: Optional[int] = None,
    approval_mode: Optional[str] = None,
) -> Dict[str, Any]:
    """Transition document to Sent + notify recipients (unit-scoped)."""
    query = {"document_id": document_id, "agent_id": agent_id}
    doc = await db.documents.find_one(query, {"_id": 0})
    if not doc:
        raise ValueError("Document not found")

    client = await db.clients.find_one({"client_id": doc.get('client_id')}, {"_id": 0})
    if not client:
        raise ValueError("Client not found")
    if not validate_transition(doc['type'], doc['status'], 'Sent'):
        raise ValueError(f"Cannot send document from status: {doc['status']}")

    recipient_rows: List[Dict[str, Any]] = []
    if doc.get("unit_id"):
        recipient_rows = await db.clients.find(
            {
                "agent_id": agent_id,
                "project_id": doc.get("project_id"),
                "unit_id": doc.get("unit_id"),
            },
            {"_id": 0},
        ).to_list(200)
    if not recipient_rows:
        recipient_rows = [client]

    recipient_rows = [r for r in recipient_rows if r.get("client_id")]
    recipient_client_ids = _coerce_client_ids([r.get("client_id") for r in recipient_rows])
    if not recipient_client_ids:
        raise ValueError("No recipients found for this document")

    chosen_approvers = _coerce_client_ids(approver_client_ids or doc.get("approver_client_ids") or [])
    if chosen_approvers:
        invalid = [cid for cid in chosen_approvers if cid not in recipient_client_ids]
        if invalid:
            raise ValueError("Approvers must be selected from recipients")
        approvers = chosen_approvers
    else:
        approvers = recipient_client_ids

    mode = (approval_mode or "custom").lower()
    if mode == "all":
        required = len(approvers)
    elif mode == "any":
        required = 1
    else:
        required = int(approval_required_count or doc.get("approval_required_count") or 1)
    if required < 1 or required > len(approvers):
        raise ValueError(f"approval_required_count must be between 1 and {len(approvers)}")

    now = datetime.now(timezone.utc).isoformat()
    prev_status = doc["status"]
    await db.documents.update_one(
        query,
        {"$set": {
            "status": "Sent",
            "sent_at": now,
            "change_request_comment": None,
            "updated_at": now,
            "recipient_client_ids": recipient_client_ids,
            "approver_client_ids": approvers,
            "approval_required_count": required,
            "approvals_received_client_ids": [],
        }},
    )
    if prev_status == "Change Requested" and doc["type"] in ("quote", "invoice"):
        from services.change_request_service import resolve_open_change_requests_after_sent_document
        await resolve_open_change_requests_after_sent_document(
            doc["type"].lower(), document_id, agent_id
        )

    # Trace: status transition + DB mutation
    try:
        from core.trace import trace_service, trace_db_mutation, set_trace_response_summary
        trace_service("services.document_service.send_document")
        trace_db_mutation("documents", "update_one", document_id)
        set_trace_response_summary({"status": "Sent", "previous_status": doc["status"]})
    except Exception:
        pass

    project = await db.projects.find_one({"project_id": doc.get('project_id')}, {"_id": 0})
    delivery = {"notification_created": False, "websocket_sent": False, "email_sent": False, "email_error": None}
    agent_settings = agent_user.get('settings', {})
    agent_profile = agent_user.get('profile', {})
    notification_sent = 0
    realtime_sent = 0
    email_sent = 0
    warned = []

    for recipient in recipient_rows:
        buyer_id = recipient.get('buyer_id')
        if buyer_id:
            try:
                from core.notification_routing import buyer_query
                await emit_notification(
                    user_id=buyer_id,
                    title=f"New {doc['type'].title()} Received",
                    message=f"You have a new {doc['type']} for {doc['title']} - CHF {doc['amount']:,.2f}",
                    notification_type="document_sent",
                    link=buyer_query("documents", document_id=document_id),
                    metadata={
                        "document_id": document_id,
                        "project_id": doc.get("project_id"),
                        "client_id": recipient.get("client_id"),
                    },
                )
                notification_sent += 1
            except Exception as e:
                warned.append(f"notification:{recipient.get('client_id')}:{str(e)[:40]}")
            try:
                await emit_realtime([buyer_id], "document_sent", {
                    "document_id": document_id, "type": doc['type'],
                    "title": doc['title'], "amount": doc['amount'],
                })
                realtime_sent += 1
            except Exception:
                pass

        if recipient.get('email'):
            result = await emit_email("document_sent", recipient['email'], {
                "doc_type": doc['type'],
                "buyer_name": recipient.get('name', 'there'),
                "agent_name": agent_profile.get('display_name') or agent_user.get('name', 'Your agent'),
                "company_name": agent_settings.get('company_name', 'the agency'),
                "agent_email": agent_profile.get('contact_email', ''),
                "agent_phone": agent_profile.get('contact_phone', ''),
                "title": doc.get('title', 'Document'),
                "summary": doc.get('summary', ''),
                "currency": doc.get('currency', 'CHF'),
                "amount": doc.get('amount', 0),
                "project_name": project.get('name', 'N/A') if project else 'N/A',
                "unit_reference": doc.get('unit_reference', 'N/A'),
                "document_id": document_id,
            })
            if isinstance(result, dict) and result.get("status") == "success":
                email_sent += 1
            elif result is not None:
                warned.append(f"email:{recipient.get('email')}")

    delivery["notification_created"] = notification_sent > 0
    delivery["websocket_sent"] = realtime_sent > 0
    delivery["email_sent"] = email_sent > 0

    return {
        "message": "Document sent successfully",
        "status": "Sent",
        "document_id": document_id,
        "recipient": {
            "count": len(recipient_client_ids),
            "client_ids": recipient_client_ids,
        },
        "approval": {
            "approver_client_ids": approvers,
            "approval_required_count": required,
            "approval_received_count": 0,
        },
        "delivery": delivery,
        "warnings": warned,
    }



async def transition_document_status(document_id: str, agent_id: str, new_status: str) -> Optional[Dict[str, Any]]:
    """
    Workflow-initiated status transition. Used by workflow actions.
    Validates transition against state machine, sets timestamps.
    """
    doc = await db.documents.find_one(
        {"document_id": document_id, "agent_id": agent_id},
        {"_id": 0},
    )
    if not doc:
        return None

    if not validate_transition(doc['type'], doc['status'], new_status):
        raise ValueError(f"Cannot transition {doc['type']} from '{doc['status']}' to '{new_status}'")

    now = datetime.now(timezone.utc).isoformat()
    update_data = {"status": new_status, "updated_at": now}

    if new_status == "Paid":
        update_data["paid_date"] = now
    elif new_status == "Sent":
        update_data["sent_at"] = now

    await db.documents.update_one(
        {"document_id": document_id},
        {"$set": update_data},
    )

    updated = await db.documents.find_one({"document_id": document_id}, {"_id": 0})
    return updated



async def document_action(
    document_id: str, action: str, user_id: str, user_role: str,
    user_name: str = "", comment: Optional[str] = None,
) -> Dict[str, Any]:
    """Perform a status action on a document. Enforces state machine."""
    if user_role == 'agent':
        query = {"document_id": document_id, "agent_id": user_id}
    else:
        client_ids = await _get_buyer_client_ids(user_id)
        query = {
            "document_id": document_id,
            "$or": [
                {"client_id": {"$in": client_ids}},
                {"recipient_client_ids": {"$in": client_ids}},
            ],
        }

    doc = await db.documents.find_one(query, {"_id": 0})
    if not doc:
        raise ValueError("Document not found")

    now = datetime.now(timezone.utc).isoformat()

    # Trace: document action
    try:
        from core.trace import trace_service, trace_db_mutation, set_trace_response_summary
        trace_service("services.document_service.document_action")
    except Exception:
        pass

    buyer_client_ids: List[str] = []
    acting_client_id: Optional[str] = None
    if user_role == 'buyer':
        buyer_client_ids = await _get_buyer_client_ids(user_id)
        acting_client_id = next((cid for cid in buyer_client_ids if cid == doc.get("client_id")), None)
        if not acting_client_id:
            recipients = _coerce_client_ids(doc.get("recipient_client_ids") or [])
            acting_client_id = next((cid for cid in buyer_client_ids if cid in recipients), None)

    if action == 'approve' and doc['type'] == 'quote' and user_role == 'buyer':
        if not validate_transition('quote', doc['status'], 'Approved'):
            raise ValueError("Cannot approve quote in current status")
        approvers = _coerce_client_ids(doc.get("approver_client_ids") or doc.get("recipient_client_ids") or [doc.get("client_id")])
        required_count = int(doc.get("approval_required_count") or 1)
        if not acting_client_id or acting_client_id not in approvers:
            raise ValueError("You are not authorized to approve this quote")
        approvals = _coerce_client_ids(doc.get("approvals_received_client_ids") or [])
        if acting_client_id not in approvals:
            approvals.append(acting_client_id)

        if len(approvals) >= required_count:
            await db.documents.update_one(
                {"document_id": document_id},
                {"$set": {"status": "Approved", "updated_at": now, "approvals_received_client_ids": approvals}},
            )
            new_status = "Approved"
        else:
            await db.documents.update_one(
                {"document_id": document_id},
                {"$set": {"updated_at": now, "approvals_received_client_ids": approvals}},
            )
            new_status = "Sent"
        try:
            trace_db_mutation("documents", "update_one", document_id)
            set_trace_response_summary({"status": new_status, "previous_status": doc["status"], "action": action})
        except Exception:
            pass
        await _notify_agent_action(
            doc,
            "Quote Approval Progress" if new_status != "Approved" else "Quote Approved",
            f"{user_name} approved quote {doc['document_number']}",
            "quote_approved",
            user_name,
            {
                "required_count": required_count,
                "approval_count": len(approvals),
            },
        )
        return {
            "message": "Quote approved" if new_status == "Approved" else "Approval recorded",
            "status": new_status,
            "approval_count": len(approvals),
            "approval_required_count": required_count,
        }

    if action == 'reject' and doc['type'] == 'quote' and user_role == 'buyer':
        if not validate_transition('quote', doc['status'], 'Rejected'):
            raise ValueError("Cannot reject quote in current status")
        approvers = _coerce_client_ids(doc.get("approver_client_ids") or doc.get("recipient_client_ids") or [doc.get("client_id")])
        if not acting_client_id or acting_client_id not in approvers:
            raise ValueError("You are not authorized to reject this quote")
        await db.documents.update_one({"document_id": document_id}, {"$set": {"status": "Rejected", "updated_at": now}})
        try:
            trace_db_mutation("documents", "update_one", document_id)
            set_trace_response_summary({"status": "Rejected", "previous_status": doc["status"], "action": action})
        except Exception:
            pass
        return {"message": "Quote rejected", "status": "Rejected"}

    if action == 'request_change' and user_role == 'buyer':
        if not comment:
            raise ValueError("Comment required for change request")
        target = 'Change Requested'
        if not validate_transition(doc['type'], doc['status'], target):
            raise ValueError("Cannot request changes in current status")
        await db.documents.update_one({"document_id": document_id}, {"$set": {"status": target, "change_request_comment": comment, "updated_at": now}})
        trace_db_mutation("documents", "update_one", document_id)
        set_trace_response_summary({"status": target, "previous_status": doc["status"], "action": action})
        await _notify_agent_action(doc, "Change Requested", f"Changes requested for {doc['type']} {doc['document_number']}", "change_requested", user_name, {"comment": comment})

        # Canonical change request row only (document + agent notify already handled above)
        from services.change_request_service import create_change_request
        entity_type = doc.get('type', 'document').lower()
        cr = await create_change_request(
            entity_type=entity_type,
            entity_id=document_id,
            message=comment,
            created_by=user_id,
            created_by_role="buyer",
            agent_id=doc.get("agent_id", ""),
            project_id=doc.get("project_id"),
            update_entity=False,
            notify_agent_on_buyer_create=False,
        )

        return {"message": "Change requested", "status": target, "change_request_id": cr["change_request_id"]}

    if action == 'confirm_payment' and doc['type'] == 'invoice' and user_role == 'buyer':
        if not validate_transition('invoice', doc['status'], 'Paid'):
            raise ValueError("Cannot confirm payment in current status")
        approvers = _coerce_client_ids(doc.get("approver_client_ids") or doc.get("recipient_client_ids") or [doc.get("client_id")])
        required_count = int(doc.get("approval_required_count") or 1)
        if not acting_client_id or acting_client_id not in approvers:
            raise ValueError("You are not authorized to confirm this payment")
        approvals = _coerce_client_ids(doc.get("approvals_received_client_ids") or [])
        if acting_client_id not in approvals:
            approvals.append(acting_client_id)
        if len(approvals) >= required_count:
            await db.documents.update_one(
                {"document_id": document_id},
                {"$set": {"status": "Paid", "paid_date": now, "updated_at": now, "approvals_received_client_ids": approvals}},
            )
            new_status = "Paid"
        else:
            await db.documents.update_one(
                {"document_id": document_id},
                {"$set": {"updated_at": now, "approvals_received_client_ids": approvals}},
            )
            new_status = "Sent"
        trace_db_mutation("documents", "update_one", document_id)
        set_trace_response_summary({"status": new_status, "previous_status": doc["status"], "action": action})
        await _notify_agent_action(doc, "Payment Confirmed", f"Payment confirmed for invoice {doc['document_number']}", "payment_confirmed", user_name)
        return {
            "message": "Payment confirmed" if new_status == "Paid" else "Payment confirmation recorded",
            "status": new_status,
            "approval_count": len(approvals),
            "approval_required_count": required_count,
        }

    if action == 'convert_to_invoice' and doc['type'] == 'quote' and user_role == 'agent':
        if doc['status'] != 'Approved':
            raise ValueError("Only approved quotes can be converted to invoices")
        return await _convert_quote_to_invoice(doc, user_id, now)

    raise ValueError(f"Invalid action: {action}")


async def reupload_document(
    document_id: str, agent_id: str,
    new_stored_filename: str, new_original_filename: str,
    extraction: dict, original_doc: dict,
) -> Dict[str, Any]:
    """Update a document with a re-uploaded PDF. Returns updated doc."""
    query = {"document_id": document_id, "agent_id": agent_id}
    now = datetime.now(timezone.utc).isoformat()
    current_version = original_doc.get('version', 1)

    version_history = original_doc.get('version_history', []) or []
    if original_doc.get('pdf_stored_filename'):
        version_history.append({
            'version': current_version,
            'pdf_stored_filename': original_doc['pdf_stored_filename'],
            'pdf_filename': original_doc.get('pdf_filename'),
            'title': original_doc.get('title'),
            'amount': original_doc.get('amount'),
            'archived_at': now,
            'archived_by': agent_id,
        })

    items_total = sum(i.get('total', 0) for i in extraction.get('items', []))
    amount = extraction.get('amount') or items_total or original_doc['amount']

    update_data = {
        "title": extraction.get('title') or original_doc['title'],
        "amount": amount,
        "items": extraction.get('items') if extraction.get('items') else original_doc['items'],
        "supplier_name": extraction.get('supplier_name') or original_doc.get('supplier_name'),
        "pdf_filename": new_original_filename,
        "pdf_stored_filename": new_stored_filename,
        "ai_extraction_confidence": extraction.get('confidence', 'low'),
        "updated_at": now,
        "version": current_version + 1,
        "version_history": version_history,
        "status": "Draft" if original_doc['status'] == 'Change Requested' else original_doc['status'],
        "change_request_comment": None,
    }

    await db.documents.update_one(query, {"$set": update_data})
    if original_doc["status"] == "Change Requested":
        from services.change_request_service import supersede_open_change_requests_for_entity
        et = original_doc["type"].lower()
        if et in ("quote", "invoice"):
            await supersede_open_change_requests_for_entity(
                et,
                document_id,
                resolution_note="Agent is revising the document in draft (PDF re-upload).",
                resolved_by_user_id=agent_id,
                author_role_for_note="agent",
            )
    result = await db.documents.find_one(query, {"_id": 0})
    result['extraction_warning'] = extraction.get('extraction_failed', False) or extraction.get('amount') is None
    return result


async def get_document_timeline(user_id: str, role: str) -> Dict[str, Any]:
    """Get unified document timeline for buyer or agent."""
    if role == 'buyer':
        clients = await db.clients.find(
            {"buyer_id": user_id}, {"_id": 0, "client_id": 1, "project_id": 1, "unit_reference": 1}
        ).to_list(100)
        client_ids = [c['client_id'] for c in clients]
        if not client_ids:
            return {"documents": [], "project_info": None}

        docs = await db.documents.find(
            {
                "status": {"$ne": "Draft"},
                "$or": [
                    {"client_id": {"$in": client_ids}},
                    {"recipient_client_ids": {"$in": client_ids}},
                ],
            },
            {"_id": 0}
        ).sort("created_at", -1).to_list(100)

        project_id = clients[0]['project_id'] if clients else None
        project = await db.projects.find_one({"project_id": project_id}, {"_id": 0}) if project_id else None
        if project and clients:
            # Enrich unit_reference from units collection if not on client
            unit_ref = clients[0].get('unit_reference')
            if not unit_ref and clients[0].get('unit_id'):
                unit = await db.units.find_one(
                    {"unit_id": clients[0]['unit_id']}, {"_id": 0, "unit_reference": 1}
                )
                if unit:
                    unit_ref = unit.get('unit_reference')
            project['unit_reference'] = unit_ref or ''

        events = [{
            "id": d['document_id'], "type": d['type'], "title": d['title'],
            "status": d['status'], "amount": d['amount'],
            "date": d.get('updated_at') or d['created_at'],
            "dueDate": d.get('due_date'), "items": d.get('items', []),
            "changeComment": d.get('change_request_comment'),
            "actionRequired": (d['type'] == 'quote' and d['status'] == 'Sent') or (d['type'] == 'invoice' and d['status'] == 'Sent'),
            "hasSourcePdf": bool(d.get('pdf_path')),
            "supplierName": d.get('supplier_name'),
            "documentNumber": d['document_number'],
            "parentDocumentId": d.get('parent_document_id'),
            "summary": d.get('summary', ''),
            "heroImageUrl": d.get('hero_image_url'),
            "currency": d.get('currency', 'CHF'),
        } for d in docs]
        return {"documents": events, "project_info": project}
    else:
        docs = await db.documents.find(
            {"agent_id": user_id}, {"_id": 0}
        ).sort("created_at", -1).to_list(100)
        return {"documents": docs}


# ── Private helpers ──

async def _get_buyer_client_ids(buyer_id: str) -> List[str]:
    """
    Return buyer-linked client_ids plus same-unit peer client_ids.
    Ensures legacy single-recipient records are still visible to co-owners.
    """
    clients = await db.clients.find(
        {"buyer_id": buyer_id}, {"_id": 0, "client_id": 1, "unit_id": 1}
    ).to_list(500)
    direct_ids = [c['client_id'] for c in clients if c.get('client_id')]
    unit_ids = list({c.get("unit_id") for c in clients if c.get("unit_id")})
    if not unit_ids:
        return direct_ids

    peers = await db.clients.find(
        {"unit_id": {"$in": unit_ids}}, {"_id": 0, "client_id": 1}
    ).to_list(2000)
    out = set(direct_ids)
    out.update(c.get("client_id") for c in peers if c.get("client_id"))
    return list(out)


def _parse_due_date(due_date: Optional[str], doc_type: str) -> Optional[str]:
    if due_date:
        try:
            return datetime.fromisoformat(due_date.replace('Z', '+00:00')).isoformat()
        except (ValueError, AttributeError):
            return (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    if doc_type == 'invoice':
        return (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    return None


async def _notify_agent_action(doc, title, message, notification_type, user_name, metadata=None):
    """Notify agent of buyer action on document."""
    if not doc.get('agent_id'):
        return
    meta = {
        "document_id": doc["document_id"],
        "project_id": doc.get("project_id"),
    }
    if metadata:
        meta.update(metadata)
    await emit_notification(
        user_id=doc['agent_id'],
        title=title,
        message=message,
        notification_type=notification_type,
        link=f"/agent/documents/{doc['document_id']}",
        metadata=meta,
    )
    await emit_realtime([doc['agent_id']], notification_type, {
        "document_id": doc['document_id'],
        "title": doc['title'],
        "buyer_name": user_name,
    })

    agent = await db.users.find_one({"user_id": doc['agent_id']}, {"_id": 0, "email": 1})
    if agent and agent.get('email'):
        await emit_email(notification_type, agent['email'], {
            "buyer_name": user_name or 'Your client',
            "document_number": doc.get('document_number', ''),
            "document_id": doc['document_id'],
            "title": doc.get('title', 'Document'),
            "currency": doc.get('currency', 'CHF'),
            "amount": doc.get('amount', 0),
            "comment": metadata.get('comment') if metadata else None,
        })


async def _convert_quote_to_invoice(quote, agent_id, now):
    """Convert an approved quote to a new invoice."""
    invoice_number = await _next_document_number(agent_id, "invoice")
    invoice_id = f"doc_{uuid.uuid4().hex[:12]}"

    invoice_doc = {
        "document_id": invoice_id,
        "document_number": invoice_number,
        "type": "invoice",
        "status": "Draft",
        "agent_id": quote['agent_id'],
        "client_id": quote['client_id'],
        "buyer_id": quote.get('buyer_id'),
        "project_id": quote['project_id'],
        "unit_id": quote.get('unit_id'),
        "unit_reference": quote.get('unit_reference', 'General'),
        "recipient_client_ids": quote.get('recipient_client_ids') or [quote['client_id']],
        "approver_client_ids": quote.get('approver_client_ids') or [quote['client_id']],
        "approval_required_count": quote.get('approval_required_count', 1),
        "approvals_received_client_ids": [],
        "title": quote['title'],
        "amount": quote['amount'],
        "items": quote.get('items', []),
        "currency": quote.get('currency', 'CHF'),
        "supplier_name": quote.get('supplier_name'),
        "notes": quote.get('notes'),
        "change_request_comment": None,
        "pdf_filename": None,
        "pdf_path": None,
        "ai_extraction_confidence": None,
        "parent_document_id": quote['document_id'],
        "due_date": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        "paid_date": None,
        "created_at": now,
        "updated_at": now,
    }
    await db.documents.insert_one(invoice_doc)

    from core.trace import trace_db_mutation, set_trace_response_summary, trace_related_entity
    trace_db_mutation("documents", "insert_one", invoice_id)
    trace_related_entity("document", quote["document_id"])
    set_trace_response_summary({"status": "Draft", "type": "invoice", "converted_from": quote["document_id"], "amount": float(quote["amount"])})

    if quote.get('buyer_id'):
        from core.notification_routing import buyer_query
        await emit_notification(
            user_id=quote['buyer_id'],
            title="Invoice Ready",
            message=f"Invoice {invoice_number} for CHF {quote['amount']:,.2f} is ready for payment",
            notification_type="invoice_created",
            link=buyer_query("documents", document_id=invoice_id),
            metadata={
                "document_id": invoice_id,
                "parent_document_id": quote["document_id"],
                "project_id": quote.get("project_id"),
            },
        )

    return {"message": "Invoice created", "document_id": invoice_id, "document_number": invoice_number}
