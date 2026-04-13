"""
Buyer Portal Service — Single Source of Truth for the buyer's entire world.

One call, everything resolved. No scattered queries, no frontend stitching.
All URLs, names, enrichments computed server-side.
"""
import logging
from typing import Dict, Any, Optional, List
from database import db
from services import file_service
from services.recipient_scope_service import get_buyer_scope
from services.decision_service import sync_missing_decision_recipients_for_client_ids

logger = logging.getLogger(__name__)


def _sort_vault_docs(docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Architect plans are pinned first, then newest."""
    def _key(doc: Dict[str, Any]):
        is_architect = doc.get("doc_type") == "architect_plan" or doc.get("category") == "architect_plans"
        created = doc.get("created_at") or ""
        return (1 if is_architect else 0, created)

    return sorted(docs, key=_key, reverse=True)


async def _get_buyer_client_scope(buyer_id: str) -> Dict[str, Any]:
    """
    Resolve buyer client scope including same-unit peer client records.
    This keeps multi-owner unit views consistent across legacy + new rows.
    """
    return await get_buyer_scope(buyer_id, include_unit_peers=True)


async def get_buyer_portal(buyer_id: str) -> Dict[str, Any]:
    """
    Returns the buyer's complete portal state in one response.
    Everything pre-resolved: URLs, project names, unit references, team, vault, decisions.
    """

    # ── Step 1: Find buyer's clients and linked entities ──
    scope = await _get_buyer_client_scope(buyer_id)
    clients = scope["clients"]
    client_ids = scope["client_ids"]
    peer_client_ids = scope["peer_client_ids"]
    if not clients:
        return _empty_portal()

    await sync_missing_decision_recipients_for_client_ids(peer_client_ids)

    primary_client = clients[0]
    project_id = primary_client.get("project_id")
    unit_id = primary_client.get("unit_id")

    # ── Step 2: Resolve project + unit (single lookups, done once) ──
    project = None
    if project_id:
        project = await db.projects.find_one({"project_id": project_id}, {"_id": 0})

    unit_reference = primary_client.get("unit_reference")
    if not unit_reference and unit_id:
        unit = await db.units.find_one({"unit_id": unit_id}, {"_id": 0, "unit_reference": 1})
        if unit:
            unit_reference = unit.get("unit_reference")

    project_info = {
        "project_id": project_id,
        "name": project.get("name", "") if project else "",
        "address": project.get("address", "") if project else "",
        "unit_reference": unit_reference or "",
        "unit_id": unit_id or "",
    }

    # ── Step 3: Documents (quotes + invoices visible to buyer) ──
    docs = await db.documents.find(
        {
            "status": {"$ne": "Draft"},
            "$or": [
                {"client_id": {"$in": peer_client_ids}},
                {"recipient_client_ids": {"$in": peer_client_ids}},
            ],
        },
        {"_id": 0}
    ).sort("created_at", -1).to_list(200)

    documents = [_format_document(d) for d in docs]

    # ── Step 4: Vault files (shared with buyer's clients) ──
    vault_query = {"access_level": "shared", "$or": [
        {"buyer_ids": buyer_id},
        {"client_ids": {"$in": peer_client_ids}},
    ]}
    vault_docs = await db.vault_documents.find(vault_query, {"_id": 0}).sort("created_at", -1).to_list(200)
    vault_docs = _sort_vault_docs(vault_docs)
    vault_files = [_format_vault_doc(v) for v in vault_docs]

    # ── Step 5: Change requests on buyer's documents ──
    doc_ids = [d["document_id"] for d in docs]
    change_requests = []
    if doc_ids:
        crs = await db.change_requests.find(
            {"entity_id": {"$in": doc_ids}},
            {"_id": 0}
        ).sort("created_at", -1).to_list(200)
        change_requests = [{
            "change_request_id": cr["change_request_id"],
            "entity_type": cr.get("entity_type"),
            "entity_id": cr.get("entity_id"),
            "status": cr.get("status"),
            "messages": cr.get("messages", []),
            "created_at": cr.get("created_at"),
            "resolved_at": cr.get("resolved_at"),
        } for cr in crs]

    # ── Step 5b: Activity feed posts shared with buyer scope ──
    recipient_rows = await db.activity_recipients.find(
        {"client_id": {"$in": peer_client_ids}},
        {"_id": 0, "activity_id": 1},
    ).to_list(5000)
    activity_ids = list({r.get("activity_id") for r in recipient_rows if r.get("activity_id")})
    activities: List[Dict[str, Any]] = []
    if activity_ids:
        raw_activities = await db.activities.find(
            {"activity_id": {"$in": activity_ids}, "is_draft": {"$ne": True}},
            {"_id": 0}
        ).sort("created_at", -1).to_list(200)

        author_ids = list({a.get("author_id") for a in raw_activities if a.get("author_id")})
        author_map: Dict[str, str] = {}
        if author_ids:
            authors = await db.users.find(
                {"user_id": {"$in": author_ids}},
                {"_id": 0, "user_id": 1, "name": 1},
            ).to_list(len(author_ids))
            author_map = {u["user_id"]: u.get("name", "Agent") for u in authors}

        activities = [{
            "activity_id": a.get("activity_id"),
            "type": a.get("type", "message"),
            "title": a.get("title", ""),
            "content": a.get("content", ""),
            "file_url": file_service.get_file_url(a["stored_filename"]) if a.get("stored_filename") else a.get("file_url"),
            "file_name": a.get("file_name"),
            "file_type": a.get("file_type"),
            "author_id": a.get("author_id"),
            "author_name": author_map.get(a.get("author_id"), "Agent"),
            "project_id": a.get("project_id"),
            "unit_id": a.get("unit_id"),
            "created_at": a.get("created_at"),
            "updated_at": a.get("updated_at"),
        } for a in raw_activities]

    # ── Step 6: Decisions requiring buyer response ──
    # Query via decision_recipients (linked by client_id); group by decision for multi-client buyers
    pending_recipients = await db.decision_recipients.find(
        {"client_id": {"$in": peer_client_ids}},
        {"_id": 0}
    ).to_list(200)
    by_decision: Dict[str, List[Dict[str, Any]]] = {}
    for r in pending_recipients:
        did = r.get("decision_id")
        if did:
            by_decision.setdefault(did, []).append(r)
    decision_ids = list(by_decision.keys())

    decisions = []
    if decision_ids:
        decisions_raw = await db.decisions.find(
            {
                "decision_id": {"$in": decision_ids},
                "status": {"$nin": ["draft"]},
            },
            {"_id": 0}
        ).sort("created_at", -1).to_list(50)
        for d in decisions_raw:
            recs = [
                r for r in by_decision.get(d["decision_id"], [])
                if r.get("client_id") in peer_client_ids
            ]
            pending_rec = next((x for x in recs if x.get("status") == "pending"), None)
            chosen = pending_rec or (recs[0] if recs else None)
            buyer_status = chosen.get("status", "pending") if chosen else "pending"
            decisions.append({
                "decision_id": d["decision_id"],
                "title": d.get("title", ""),
                "description": d.get("description", ""),
                "options": d.get("options", []),
                "status": d.get("status"),
                "buyer_status": buyer_status,
                "deadline": d.get("deadline"),
                "created_at": d.get("created_at"),
                "external_link": d.get("external_link"),
                "attachments": d.get("attachments", []),
            })

    # ── Step 7: Team members on buyer's project ──
    team = []
    if project_id:
        team_raw = await db.team_members.find(
            {"project_id": project_id}, {"_id": 0}
        ).to_list(50)
        team = [{
            "name": t.get("name", ""),
            "role": t.get("role", ""),
            "email": t.get("email", ""),
            "phone": t.get("phone", ""),
        } for t in team_raw]

    # ── Step 8: Construction timeline ──
    construction_timeline = None
    if project_id:
        timeline = await db.timelines.find_one(
            {"project_id": project_id}, {"_id": 0}
        )
        if timeline:
            steps = await db.timeline_steps.find(
                {"timeline_id": timeline["timeline_id"]}, {"_id": 0}
            ).sort("order", 1).to_list(100)
            construction_timeline = {
                "timeline_id": timeline["timeline_id"],
                "name": timeline.get("name", ""),
                "steps": [{
                    "step_id": s["step_id"],
                    "title": s.get("title", ""),
                    "status": s.get("status", "pending"),
                    "order": s.get("order", 0),
                    "start_date": s.get("start_date"),
                    "end_date": s.get("end_date"),
                    "notes": s.get("notes", ""),
                } for s in steps],
            }

    # ── Step 9: Notifications / unread count ──
    unread_count = await db.notifications.count_documents(
        {"user_id": buyer_id, "read": False}
    )

    # ── Step 10: Agent branding ──
    agent_id = primary_client.get("agent_id") or (project.get("agent_id") if project else None)
    branding = {}
    if agent_id:
        agent = await db.users.find_one({"user_id": agent_id}, {"_id": 0, "company_name": 1, "company_logo_url": 1})
        if agent:
            logo_url = agent.get("company_logo_url")
            if logo_url and not logo_url.startswith("http"):
                logo_url = file_service.get_file_url(logo_url.replace("/api/uploads/", "")) if "/api/uploads/" in logo_url else logo_url
            branding = {
                "company_name": agent.get("company_name", ""),
                "logo_url": logo_url or "",
            }

    return {
        "project": project_info,
        "branding": branding,
        "documents": documents,
        "vault_files": vault_files,
        "activities": activities,
        "change_requests": change_requests,
        "decisions": decisions,
        "team": team,
        "construction_timeline": construction_timeline,
        "unread_count": unread_count,
    }


def _format_document(d: Dict[str, Any]) -> Dict[str, Any]:
    """Format a document for the buyer portal. All URLs resolved."""
    hero_url = d.get("hero_image_url")
    if hero_url and not hero_url.startswith("http"):
        stored = d.get("hero_image_stored_filename")
        if stored:
            hero_url = file_service.get_file_url(stored)

    return {
        "id": d["document_id"],
        "documentNumber": d.get("document_number", ""),
        "type": d["type"],
        "title": d.get("title", ""),
        "status": d.get("status", ""),
        "amount": d.get("amount", 0),
        "currency": d.get("currency", "CHF"),
        "items": d.get("items", []),
        "summary": d.get("summary", ""),
        "supplierName": d.get("supplier_name"),
        "heroImageUrl": hero_url,
        "hasSourcePdf": bool(d.get("pdf_stored_filename")),
        "dueDate": d.get("due_date"),
        "changeComment": d.get("change_request_comment"),
        "actionRequired": (
            (d["type"] == "quote" and d.get("status") == "Sent") or
            (d["type"] == "invoice" and d.get("status") == "Sent")
        ),
        "parentDocumentId": d.get("parent_document_id"),
        "date": d.get("updated_at") or d.get("created_at"),
    }


def _format_vault_doc(v: Dict[str, Any]) -> Dict[str, Any]:
    """Format a vault document for the buyer portal. URL resolved."""
    url = None
    if v.get("stored_filename"):
        url = file_service.get_file_url(v["stored_filename"])

    return {
        "vault_id": v["vault_document_id"],
        "vault_document_id": v["vault_document_id"],
        "title": v.get("title", ""),
        "category": v.get("category", ""),
        "doc_type": v.get("doc_type", ""),
        "is_architect_plan": (
            v.get("doc_type") == "architect_plan" or v.get("category") == "architect_plans"
        ),
        "content_type": v.get("content_type", ""),
        "file_size": v.get("file_size", 0),
        "original_filename": v.get("original_filename", ""),
        "url": url,
        "created_at": v.get("created_at"),
        "description": v.get("description", ""),
    }


def _empty_portal() -> Dict[str, Any]:
    return {
        "project": None,
        "branding": {},
        "documents": [],
        "vault_files": [],
        "activities": [],
        "change_requests": [],
        "decisions": [],
        "team": [],
        "construction_timeline": None,
        "unread_count": 0,
    }


async def process_buyer_action(
    buyer_id: str,
    action: str,
    document_id: str = None,
    decision_id: str = None,
    comment: str = None,
    option_id: str = None,
) -> Dict[str, Any]:
    """
    Single mutation handler for all buyer→agent actions.
    Processes the action, then returns the updated portal state.
    """
    from services.document_service import document_action
    from services import decision_service

    user = await db.users.find_one({"user_id": buyer_id}, {"_id": 0})
    user_name = user.get("name", "") if user else ""

    if action in ("approve", "reject", "request_change", "confirm_payment"):
        if not document_id:
            raise ValueError("document_id required for document actions")
        result = await document_action(
            document_id=document_id,
            action=action,
            user_id=buyer_id,
            user_role="buyer",
            user_name=user_name,
            comment=comment,
        )

    elif action == "respond_decision":
        if not decision_id:
            raise ValueError("decision_id required")
        if not option_id:
            raise ValueError("option_id required")
        if option_id not in ("approved", "rejected", "request_change"):
            raise ValueError("Invalid option_id for decision response")

        scope = await _get_buyer_client_scope(buyer_id)
        buyer_cids = scope["peer_client_ids"]
        if not buyer_cids:
            raise ValueError("No client record found for this buyer")

        rec = await db.decision_recipients.find_one(
            {"decision_id": decision_id, "client_id": {"$in": buyer_cids}},
            {"_id": 0, "client_id": 1},
        )
        if not rec:
            raise ValueError("You are not a recipient for this decision")

        await decision_service.buyer_respond(
            decision_id=decision_id,
            buyer_id=buyer_id,
            client_id=rec["client_id"],
            action=option_id,
            comment=comment,
        )

    elif action == "mark_seen":
        await db.notifications.update_many(
            {"user_id": buyer_id, "read": False},
            {"$set": {"read": True}},
        )

    else:
        raise ValueError(f"Unknown action: {action}")

    # Return fresh portal state after mutation
    return await get_buyer_portal(buyer_id)
