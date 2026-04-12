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

logger = logging.getLogger(__name__)

VALID_DOC_TYPES = {"quote", "invoice"}
FINALIZED_STATUSES = {"Approved", "Rejected", "Paid"}


# ── Core CRUD ──

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
) -> Dict[str, Any]:
    """Create a document. Returns the created document dict."""
    client = await db.clients.find_one(
        {"client_id": client_id, "agent_id": agent_id}, {"_id": 0}
    )
    if not client:
        raise ValueError("Client not found")

    if doc_type == 'invoice':
        count = await db.documents.count_documents({"agent_id": agent_id, "type": "invoice"})
        doc_number = f"INV-{datetime.now().year}-{str(count + 1).zfill(4)}"
    else:
        count = await db.documents.count_documents({"agent_id": agent_id, "type": "quote"})
        doc_number = f"QT-{datetime.now().year}-{str(count + 1).zfill(4)}"

    doc_id = f"doc_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()

    parsed_due = _parse_due_date(due_date, doc_type)

    # Resolve unit_reference from unit_id if client has one
    unit_reference = client.get('unit_reference', 'General')
    if not unit_reference or unit_reference == 'General':
        unit_id = client.get('unit_id')
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
        "unit_reference": unit_reference,
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
        query["client_id"] = {"$in": client_ids}

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
        query["client_id"] = {"$in": client_ids}

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
    for k in ('title', 'amount', 'supplier_name', 'notes', 'summary', 'hero_image_url'):
        if k in updates and updates[k] is not None:
            update_data[k] = updates[k]

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
    return await db.documents.find_one(query, {"_id": 0})


async def delete_document(document_id: str, agent_id: str, force: bool = False) -> bool:
    """Delete a document. Non-drafts require force=True."""
    query = {"document_id": document_id, "agent_id": agent_id}
    doc = await db.documents.find_one(query, {"_id": 0})
    if not doc:
        return False
    if doc['status'] != 'Draft' and not force:
        raise ValueError("Can only delete Draft documents. Use force=true for others.")

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

async def send_document(document_id: str, agent_id: str, agent_user: dict) -> Dict[str, Any]:
    """Transition document to Sent + notify buyer."""
    query = {"document_id": document_id, "agent_id": agent_id}
    doc = await db.documents.find_one(query, {"_id": 0})
    if not doc:
        raise ValueError("Document not found")

    client = await db.clients.find_one({"client_id": doc.get('client_id')}, {"_id": 0})
    if not client:
        raise ValueError("Client not found")
    if not client.get('email'):
        raise ValueError("Client has no email address")
    if not validate_transition(doc['type'], doc['status'], 'Sent'):
        raise ValueError(f"Cannot send document from status: {doc['status']}")

    now = datetime.now(timezone.utc).isoformat()
    await db.documents.update_one(query, {
        "$set": {"status": "Sent", "sent_at": now, "change_request_comment": None, "updated_at": now}
    })

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

    buyer_id = doc.get('buyer_id') or client.get('buyer_id')
    if buyer_id:
        try:
            await emit_notification(
                user_id=buyer_id,
                title=f"New {doc['type'].title()} Received",
                message=f"You have a new {doc['type']} for {doc['title']} - CHF {doc['amount']:,.2f}",
                notification_type="document_sent",
                link="/buyer",
            )
            delivery["notification_created"] = True
        except Exception as e:
            logger.warning(f"Notification failed: {e}")

        try:
            await emit_realtime([buyer_id], "document_sent", {
                "document_id": document_id, "type": doc['type'],
                "title": doc['title'], "amount": doc['amount'],
            })
            delivery["websocket_sent"] = True
        except Exception as e:
            logger.warning(f"Realtime failed: {e}")

    if client.get('email'):
        agent_settings = agent_user.get('settings', {})
        agent_profile = agent_user.get('profile', {})
        result = await emit_email("document_sent", client['email'], {
            "doc_type": doc['type'],
            "buyer_name": client.get('name', 'there'),
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
        })
        if isinstance(result, dict):
            delivery["email_sent"] = result.get("status") == "success"
            if not delivery["email_sent"]:
                delivery["email_error"] = result.get("error") or result.get("reason", "Unknown")
        elif result is not None:
            delivery["email_sent"] = True

    return {
        "message": "Document sent successfully",
        "status": "Sent",
        "document_id": document_id,
        "recipient": {"name": client.get('name'), "email": client.get('email')},
        "delivery": delivery,
        "warnings": [] if delivery["email_sent"] else [
            f"Email may not have been delivered: {delivery['email_error'] or 'Unknown'}"
        ],
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
        query = {"document_id": document_id, "client_id": {"$in": client_ids}}

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

    if action == 'approve' and doc['type'] == 'quote' and user_role == 'buyer':
        if not validate_transition('quote', doc['status'], 'Approved'):
            raise ValueError("Cannot approve quote in current status")
        await db.documents.update_one({"document_id": document_id}, {"$set": {"status": "Approved", "updated_at": now}})
        try:
            trace_db_mutation("documents", "update_one", document_id)
            set_trace_response_summary({"status": "Approved", "previous_status": doc["status"], "action": action})
        except Exception:
            pass
        await _notify_agent_action(doc, "Quote Approved", f"{user_name} approved quote {doc['document_number']}", "quote_approved", user_name)
        return {"message": "Quote approved", "status": "Approved"}

    if action == 'reject' and doc['type'] == 'quote' and user_role == 'buyer':
        if not validate_transition('quote', doc['status'], 'Rejected'):
            raise ValueError("Cannot reject quote in current status")
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

        # Create canonical change request
        from services.change_request_service import create_change_request
        entity_type = doc.get('type', 'document').lower()
        await create_change_request(
            entity_type=entity_type,
            entity_id=document_id,
            message=comment,
            created_by=user_id,
            created_by_role="buyer",
            agent_id=doc.get("agent_id", ""),
            project_id=doc.get("project_id"),
        )

        return {"message": "Change requested", "status": target}

    if action == 'confirm_payment' and doc['type'] == 'invoice' and user_role == 'buyer':
        if not validate_transition('invoice', doc['status'], 'Paid'):
            raise ValueError("Cannot confirm payment in current status")
        await db.documents.update_one({"document_id": document_id}, {"$set": {"status": "Paid", "paid_date": now, "updated_at": now}})
        trace_db_mutation("documents", "update_one", document_id)
        set_trace_response_summary({"status": "Paid", "previous_status": doc["status"], "action": action})
        await _notify_agent_action(doc, "Payment Confirmed", f"Payment confirmed for invoice {doc['document_number']}", "payment_confirmed", user_name)
        return {"message": "Payment confirmed", "status": "Paid"}

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
            {"client_id": {"$in": client_ids}, "status": {"$ne": "Draft"}},
            {"_id": 0}
        ).sort("created_at", -1).to_list(100)

        project_id = clients[0]['project_id'] if clients else None
        project = await db.projects.find_one({"project_id": project_id}, {"_id": 0}) if project_id else None
        if project and clients:
            project['unit_reference'] = clients[0].get('unit_reference', '')

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
    clients = await db.clients.find(
        {"buyer_id": buyer_id}, {"_id": 0, "client_id": 1}
    ).to_list(100)
    return [c['client_id'] for c in clients]


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
    await emit_notification(
        user_id=doc['agent_id'],
        title=title,
        message=message,
        notification_type=notification_type,
        link=f"/agent/documents/{doc['document_id']}",
        metadata=metadata,
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
    count = await db.documents.count_documents({"agent_id": agent_id, "type": "invoice"})
    invoice_number = f"INV-{datetime.now().year}-{str(count + 1).zfill(4)}"
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
        "unit_reference": quote.get('unit_reference', 'General'),
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
        await emit_notification(
            user_id=quote['buyer_id'],
            title="Invoice Ready",
            message=f"Invoice {invoice_number} for CHF {quote['amount']:,.2f} is ready for payment",
            notification_type="invoice_created",
            link="/buyer",
        )

    return {"message": "Invoice created", "document_id": invoice_id, "document_number": invoice_number}
