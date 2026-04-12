"""
Buyer Portal Service — Single Source of Truth for the buyer's entire world.

One call, everything resolved. No scattered queries, no frontend stitching.
All URLs, names, enrichments computed server-side.
"""
import logging
from typing import Dict, Any, Optional, List
from database import db
from services import file_service

logger = logging.getLogger(__name__)


async def get_buyer_portal(buyer_id: str) -> Dict[str, Any]:
    """
    Returns the buyer's complete portal state in one response.
    Everything pre-resolved: URLs, project names, unit references, team, vault, decisions.
    """

    # ── Step 1: Find buyer's clients and linked entities ──
    clients = await db.clients.find(
        {"buyer_id": buyer_id}, {"_id": 0}
    ).to_list(100)

    if not clients:
        return _empty_portal()

    client_ids = [c["client_id"] for c in clients]
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
        {"client_id": {"$in": client_ids}, "status": {"$ne": "Draft"}},
        {"_id": 0}
    ).sort("created_at", -1).to_list(200)

    documents = [_format_document(d) for d in docs]

    # ── Step 4: Vault files (shared with buyer's clients) ──
    vault_query = {"access_level": "shared", "$or": [
        {"buyer_ids": buyer_id},
        {"client_ids": {"$in": client_ids}},
    ]}
    vault_docs = await db.vault_documents.find(vault_query, {"_id": 0}).sort("created_at", -1).to_list(200)
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

    # ── Step 6: Decisions requiring buyer response ──
    decisions_raw = await db.decisions.find(
        {"buyer_id": buyer_id, "status": "pending"},
        {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    decisions = [{
        "decision_id": d["decision_id"],
        "title": d.get("title", ""),
        "description": d.get("description", ""),
        "options": d.get("options", []),
        "status": d.get("status"),
        "due_date": d.get("due_date"),
        "created_at": d.get("created_at"),
    } for d in decisions_raw]

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
        "change_requests": [],
        "decisions": [],
        "team": [],
        "construction_timeline": None,
        "unread_count": 0,
    }
