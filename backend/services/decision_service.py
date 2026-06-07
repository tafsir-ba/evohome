"""
Canonical Decision Service.

Single source of truth for all decision operations.
Decisions are formal requests sent by agents to buyers requiring approval.
Change requests on decisions use the canonical change_request_service.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from database import db
from services.notification_service import emit_realtime
from services.recipient_scope_service import expand_client_ids_to_unit_peers

logger = logging.getLogger(__name__)


def _collect_string_ids(rows: List[Dict[str, Any]], key: str) -> List[str]:
    """Collect non-empty string IDs from rows without raising KeyError."""
    ids: List[str] = []
    for row in rows:
        value = row.get(key)
        if isinstance(value, str) and value:
            ids.append(value)
    return ids


def _sanitize_contact_person(contact_person: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not contact_person or not isinstance(contact_person, dict):
        return None

    cleaned = {
        "contact_id": str(contact_person.get("contact_id") or "").strip(),
        "source": str(contact_person.get("source") or "").strip(),
        "name": str(contact_person.get("name") or "").strip(),
        "company_name": str(contact_person.get("company_name") or "").strip(),
        "role": str(contact_person.get("role") or "").strip(),
        "email": str(contact_person.get("email") or "").strip(),
        "phone": str(contact_person.get("phone") or "").strip(),
    }
    if not cleaned["name"] and not cleaned["email"] and not cleaned["phone"]:
        return None
    return cleaned


async def _buyer_user_ids_from_client_ids(client_ids: List[str]) -> List[str]:
    """Resolve distinct buyer user_ids for the given client records."""
    out: List[str] = []
    for cid in client_ids:
        c = await db.clients.find_one({"client_id": cid}, {"_id": 0, "buyer_id": 1})
        if c and c.get("buyer_id"):
            out.append(c["buyer_id"])
    return list(dict.fromkeys(out))


async def _emit_decision_updated(
    decision_id: str,
    event: str,
    *,
    agent_id: Optional[str] = None,
    title: Optional[str] = None,
    buyer_ids: Optional[List[str]] = None,
) -> None:
    """Notify agent and/or buyers over WebSocket so UIs refetch."""
    payload: Dict[str, Any] = {"decision_id": decision_id, "event": event}
    if title:
        payload["title"] = title
    if agent_id:
        await emit_realtime([agent_id], "decision_updated", payload)
    if buyer_ids:
        await emit_realtime(buyer_ids, "decision_updated", payload)


async def resolve_recipient_client_ids_for_send(decision: Dict[str, Any], agent_id: str) -> List[str]:
    """
    Who should receive this decision when sent: explicit clients, units, or whole project.
    """
    cov = decision.get("coverage") or {}
    ctype = str(cov.get("type") or "project").lower()
    explicit = cov.get("client_ids") or []
    unit_ids = cov.get("unit_ids") or []
    pid = decision.get("project_id")
    if not pid:
        return []

    if ctype == "clients":
        if not explicit:
            return []
        clients = await db.clients.find(
            {"client_id": {"$in": explicit}, "project_id": pid, "agent_id": agent_id},
            {"_id": 0, "client_id": 1},
        ).to_list(len(explicit))
        return list(dict.fromkeys(c["client_id"] for c in clients if c.get("client_id")))

    if ctype == "units" or unit_ids:
        if not unit_ids:
            return []
        clients = await db.clients.find(
            {"project_id": pid, "agent_id": agent_id, "unit_id": {"$in": unit_ids}},
            {"_id": 0, "client_id": 1},
        ).to_list(200)
        return _collect_string_ids(clients, "client_id")

    # project-wide
    clients = await db.clients.find(
        {"project_id": pid, "agent_id": agent_id},
        {"_id": 0, "client_id": 1},
    ).to_list(200)
    return _collect_string_ids(clients, "client_id")


def _client_should_receive_open_decision(client: Dict[str, Any], decision: Dict[str, Any]) -> bool:
    """Whether a client record should have a recipient row for this open (sent) decision."""
    cov = decision.get("coverage") or {}
    ctype = str(cov.get("type") or "project").lower()
    explicit = cov.get("client_ids") or []
    unit_ids = cov.get("unit_ids") or []
    cid = client.get("client_id")
    if not cid or client.get("project_id") != decision.get("project_id"):
        return False

    if ctype == "clients":
        return cid in explicit if explicit else False

    if ctype == "units" or unit_ids:
        u = client.get("unit_id")
        return bool(u and unit_ids and u in unit_ids)

    return True


async def sync_missing_decision_recipients_for_client_ids(client_ids: List[str]) -> int:
    """
    Backfill decision_recipients for clients added after a decision was sent (project / unit coverage).
    Idempotent. Returns number of new rows inserted.
    """
    inserted = 0
    for cid in client_ids:
        client = await db.clients.find_one(
            {"client_id": cid},
            {"_id": 0, "client_id": 1, "project_id": 1, "agent_id": 1, "unit_id": 1},
        )
        if not client or not client.get("project_id"):
            continue

        open_decisions = await db.decisions.find(
            {
                "project_id": client["project_id"],
                "status": {"$in": ["pending", "Change Requested"]},
                "sent_at": {"$ne": None},
            },
            {"_id": 0},
        ).to_list(100)

        for d in open_decisions:
            if not _client_should_receive_open_decision(client, d):
                continue
            exists = await db.decision_recipients.find_one(
                {"decision_id": d["decision_id"], "client_id": cid}
            )
            if exists:
                continue
            await db.decision_recipients.insert_one(
                {
                    "decision_id": d["decision_id"],
                    "client_id": cid,
                    "status": "pending",
                    "responded_at": None,
                    "comment": None,
                }
            )
            inserted += 1
    return inserted


async def create_decision(
    agent_id: str,
    project_id: str,
    title: str,
    description: str,
    deadline: Optional[str] = None,
    attachments: Optional[List[dict]] = None,
    external_link: Optional[str] = None,
    coverage_type: str = "project",
    unit_ids: Optional[List[str]] = None,
    client_ids: Optional[List[str]] = None,
    contact_person: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create a new decision."""
    decision_id = f"dec_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()

    decision = {
        "decision_id": decision_id,
        "agent_id": agent_id,
        "project_id": project_id,
        "title": title,
        "description": description,
        "deadline": deadline,
        "attachments": attachments or [],
        "external_link": external_link,
        "coverage": {
            "type": coverage_type,
            "unit_ids": unit_ids or [],
            "client_ids": client_ids or [],
        },
        "contact_person": _sanitize_contact_person(contact_person),
        "status": "draft",
        "created_at": now,
        "updated_at": now,
        "sent_at": None,
        "resolved_at": None,
    }

    await db.decisions.insert_one(decision)
    decision.pop("_id", None)

    logger.info(f"Decision {decision_id} created by {agent_id}")
    return decision


async def send_decision(decision_id: str, agent_id: str) -> Dict[str, Any]:
    """Send a decision to buyers (changes status from draft to sent/pending)."""
    decision = await get_decision(decision_id)
    if not decision:
        raise ValueError("Decision not found")
    if decision["agent_id"] != agent_id:
        raise ValueError("Not authorized")
    if decision["status"] not in ("draft", "Change Requested"):
        raise ValueError(f"Cannot send decision in '{decision['status']}' status")

    now = datetime.now(timezone.utc).isoformat()
    await db.decisions.update_one(
        {"decision_id": decision_id},
        {"$set": {"status": "pending", "sent_at": now, "updated_at": now}}
    )

    # Create recipient records for tracking (project / clients / units)
    decision = await get_decision(decision_id) or decision
    client_ids = await resolve_recipient_client_ids_for_send(decision, agent_id)

    for cid in client_ids:
        existing = await db.decision_recipients.find_one(
            {"decision_id": decision_id, "client_id": cid}
        )
        if not existing:
            await db.decision_recipients.insert_one({
                "decision_id": decision_id,
                "client_id": cid,
                "status": "pending",
                "responded_at": None,
                "comment": None,
            })

    decision["status"] = "pending"
    decision["sent_at"] = now
    logger.info(f"Decision {decision_id} sent to {len(client_ids)} recipients")

    buyer_ids = await _buyer_user_ids_from_client_ids(client_ids)
    await _emit_decision_updated(
        decision_id,
        "sent",
        title=decision.get("title"),
        buyer_ids=buyer_ids,
    )
    return decision


async def update_decision(
    decision_id: str,
    agent_id: str,
    updates: dict,
) -> Dict[str, Any]:
    """Update a draft decision."""
    decision = await get_decision(decision_id)
    if not decision:
        raise ValueError("Decision not found")
    if decision["agent_id"] != agent_id:
        raise ValueError("Not authorized")
    if decision["status"] not in ("draft", "Change Requested"):
        raise ValueError("Can only edit draft or change-requested decisions")

    allowed = {"title", "description", "deadline", "attachments", "external_link", "coverage", "contact_person"}
    filtered = {k: v for k, v in updates.items() if k in allowed}
    if "contact_person" in filtered:
        filtered["contact_person"] = _sanitize_contact_person(filtered.get("contact_person"))
    filtered["updated_at"] = datetime.now(timezone.utc).isoformat()

    await db.decisions.update_one(
        {"decision_id": decision_id},
        {"$set": filtered}
    )

    return await get_decision(decision_id)


async def buyer_respond(
    decision_id: str,
    buyer_id: str,
    client_id: str,
    action: str,
    comment: Optional[str] = None,
) -> Dict[str, Any]:
    """Buyer responds to a decision: approve, reject, or request_change."""
    decision = await get_decision(decision_id)
    if not decision:
        raise ValueError("Decision not found")
    if decision["status"] not in ("pending", "Change Requested"):
        raise ValueError(f"Cannot respond to decision in '{decision['status']}' status")

    now = datetime.now(timezone.utc).isoformat()

    recipient = await db.decision_recipients.find_one(
        {"decision_id": decision_id, "client_id": client_id},
        {"_id": 0, "client_id": 1},
    )
    if not recipient:
        raise ValueError("Buyer is not an authorized recipient for this decision")

    await db.decision_recipients.update_one(
        {"decision_id": decision_id, "client_id": client_id},
        {"$set": {
            "status": action,
            "responded_at": now,
            "comment": comment,
        }},
        upsert=False,
    )

    # Determine overall decision status
    if action == "approved":
        # Check if all recipients have approved
        recipients = await db.decision_recipients.find(
            {"decision_id": decision_id}, {"_id": 0}
        ).to_list(100)
        all_approved = all(r.get("status") == "approved" for r in recipients)
        new_status = "approved" if all_approved else "pending"

    elif action == "rejected":
        new_status = "rejected"

    elif action == "request_change":
        new_status = "Change Requested"
        # Create canonical change request
        from services.change_request_service import create_change_request
        await create_change_request(
            entity_type="decision",
            entity_id=decision_id,
            message=comment or "Change requested",
            created_by=buyer_id,
            created_by_role="buyer",
            agent_id=decision["agent_id"],
            project_id=decision["project_id"],
        )
    else:
        raise ValueError(f"Invalid action: {action}")

    resolved_at = now if new_status in ("approved", "rejected") else None
    await db.decisions.update_one(
        {"decision_id": decision_id},
        {"$set": {"status": new_status, "updated_at": now, "resolved_at": resolved_at}}
    )

    decision["status"] = new_status
    logger.info(f"Decision {decision_id}: buyer {buyer_id} action={action}, new_status={new_status}")

    recs = await db.decision_recipients.find({"decision_id": decision_id}, {"_id": 0, "client_id": 1}).to_list(200)
    cids = _collect_string_ids(recs, "client_id")
    notify_buyers = await _buyer_user_ids_from_client_ids(cids)
    await _emit_decision_updated(
        decision_id,
        "buyer_responded",
        agent_id=decision["agent_id"],
        title=decision.get("title"),
        buyer_ids=notify_buyers,
    )
    return decision


async def close_decision(decision_id: str, agent_id: str) -> Dict[str, Any]:
    """Agent closes a decision (final state)."""
    decision = await get_decision(decision_id)
    if not decision:
        raise ValueError("Decision not found")
    if decision["agent_id"] != agent_id:
        raise ValueError("Not authorized")

    now = datetime.now(timezone.utc).isoformat()
    await db.decisions.update_one(
        {"decision_id": decision_id},
        {"$set": {"status": "closed", "updated_at": now, "resolved_at": now}}
    )

    decision["status"] = "closed"
    recs = await db.decision_recipients.find({"decision_id": decision_id}, {"_id": 0, "client_id": 1}).to_list(200)
    cids = _collect_string_ids(recs, "client_id")
    buyer_ids = await _buyer_user_ids_from_client_ids(cids)
    await _emit_decision_updated(
        decision_id,
        "closed",
        title=decision.get("title"),
        buyer_ids=buyer_ids,
    )
    return decision


async def delete_decision(decision_id: str, agent_id: str) -> bool:
    """Delete a draft decision."""
    decision = await get_decision(decision_id)
    if not decision:
        raise ValueError("Decision not found")
    if decision["agent_id"] != agent_id:
        raise ValueError("Not authorized")
    if decision["status"] != "draft":
        raise ValueError("Can only delete draft decisions")

    from services import file_service

    for att in decision.get("attachments") or []:
        sf = att.get("stored_filename")
        if not sf and att.get("url"):
            sf = file_service.stored_filename_from_public_url(att["url"])
        if sf:
            try:
                file_service.delete_file(sf)
            except Exception:
                pass

    await db.decisions.delete_one({"decision_id": decision_id})
    await db.decision_recipients.delete_many({"decision_id": decision_id})
    return True


async def get_decision(decision_id: str) -> Optional[Dict[str, Any]]:
    """Get a single decision by ID."""
    d = await db.decisions.find_one({"decision_id": decision_id}, {"_id": 0})
    return d


async def get_decision_with_recipients(decision_id: str) -> Optional[Dict[str, Any]]:
    """Get a decision with enriched recipient data."""
    decision = await get_decision(decision_id)
    if not decision:
        return None

    recipients = await db.decision_recipients.find(
        {"decision_id": decision_id}, {"_id": 0}
    ).to_list(100)

    # Enrich with client names
    client_ids = _collect_string_ids(recipients, "client_id")
    if client_ids:
        clients = await db.clients.find(
            {"client_id": {"$in": client_ids}}, {"_id": 0, "client_id": 1, "name": 1, "email": 1}
        ).to_list(len(client_ids))
        client_map = {c["client_id"]: c for c in clients}
        for r in recipients:
            rid = r.get("client_id")
            cl = client_map.get(rid, {})
            r["client_name"] = cl.get("name", "Unknown")
            r["client_email"] = cl.get("email", "")

    # Enrich with project name
    if decision.get("project_id"):
        project = await db.projects.find_one(
            {"project_id": decision["project_id"]}, {"_id": 0, "name": 1, "address": 1}
        )
        if project:
            decision["project_name"] = project.get("name")
            decision["project_address"] = project.get("address")

    decision["recipients"] = recipients
    return decision


async def list_decisions(
    agent_id: str,
    accessible_project_ids: Optional[List[str]] = None,
    project_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    """List decisions for an agent."""
    query = {"agent_id": agent_id}
    if accessible_project_ids is not None:
        if not accessible_project_ids:
            return {"decisions": [], "total": 0}
        query["project_id"] = {"$in": accessible_project_ids}
    if project_id:
        query["project_id"] = project_id
    if status:
        query["status"] = status

    total = await db.decisions.count_documents(query)
    items = await db.decisions.find(
        query, {"_id": 0}
    ).sort("updated_at", -1).skip(offset).limit(limit).to_list(limit)

    # Batch enrich with project names
    proj_ids = list({d["project_id"] for d in items if d.get("project_id")})
    if proj_ids:
        projects = await db.projects.find(
            {"project_id": {"$in": proj_ids}}, {"_id": 0, "project_id": 1, "name": 1}
        ).to_list(len(proj_ids))
        proj_map = {p["project_id"]: p["name"] for p in projects}
        for d in items:
            d["project_name"] = proj_map.get(d.get("project_id"))

    # Batch count recipients per decision
    dec_ids = _collect_string_ids(items, "decision_id")
    if dec_ids:
        pipeline = [
            {"$match": {"decision_id": {"$in": dec_ids}}},
            {"$group": {"_id": "$decision_id", "total": {"$sum": 1}, "approved": {"$sum": {"$cond": [{"$eq": ["$status", "approved"]}, 1, 0]}}}}
        ]
        counts = await db.decision_recipients.aggregate(pipeline).to_list(len(dec_ids))
        count_map = {c["_id"]: c for c in counts}
        for d in items:
            c = count_map.get(d["decision_id"], {})
            d["recipient_count"] = c.get("total", 0)
            d["approved_count"] = c.get("approved", 0)

    return {"decisions": items, "total": total}


async def list_buyer_decisions(buyer_id: str) -> List[Dict[str, Any]]:
    """List decisions visible to a buyer."""
    query = {"buyer_id": buyer_id}
    clients = await db.clients.find(
        query, {"_id": 0, "client_id": 1, "project_id": 1}
    ).to_list(50)
    client_ids = [c["client_id"] for c in clients if c.get("client_id")]
    scope_client_ids = await expand_client_ids_to_unit_peers(client_ids)

    if not scope_client_ids:
        return []

    await sync_missing_decision_recipients_for_client_ids(scope_client_ids)

    # Find decisions where buyer is a recipient
    recipient_records = await db.decision_recipients.find(
        {"client_id": {"$in": scope_client_ids}}, {"_id": 0}
    ).to_list(200)

    decision_ids = list({
        r.get("decision_id")
        for r in recipient_records
        if isinstance(r.get("decision_id"), str) and r.get("decision_id")
    })
    if not decision_ids:
        return []

    decisions = await db.decisions.find(
        {"decision_id": {"$in": decision_ids}, "status": {"$ne": "draft"}},
        {"_id": 0}
    ).sort("updated_at", -1).to_list(100)

    # Enrich
    for d in decisions:
        did = d.get("decision_id")
        recs = [r for r in recipient_records if r.get("decision_id") == did]
        buyer_rec = next((r for r in recs if r.get("client_id") in scope_client_ids), None)
        d["buyer_status"] = buyer_rec["status"] if buyer_rec else "pending"
        d["buyer_comment"] = buyer_rec.get("comment") if buyer_rec else None

    return decisions
