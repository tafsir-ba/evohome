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

logger = logging.getLogger(__name__)


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

    # Create recipient records for tracking
    client_ids = decision["coverage"].get("client_ids", [])
    if not client_ids:
        # If coverage is project-wide, get all clients in the project
        clients = await db.clients.find(
            {"project_id": decision["project_id"], "agent_id": agent_id},
            {"_id": 0, "client_id": 1}
        ).to_list(100)
        client_ids = [c["client_id"] for c in clients]

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

    allowed = {"title", "description", "deadline", "attachments", "external_link", "coverage"}
    filtered = {k: v for k, v in updates.items() if k in allowed}
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

    # Update recipient record
    await db.decision_recipients.update_one(
        {"decision_id": decision_id, "client_id": client_id},
        {"$set": {
            "status": action,
            "responded_at": now,
            "comment": comment,
        }},
        upsert=True,
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
    client_ids = [r["client_id"] for r in recipients]
    if client_ids:
        clients = await db.clients.find(
            {"client_id": {"$in": client_ids}}, {"_id": 0, "client_id": 1, "name": 1, "email": 1}
        ).to_list(len(client_ids))
        client_map = {c["client_id"]: c for c in clients}
        for r in recipients:
            cl = client_map.get(r["client_id"], {})
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
    project_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    """List decisions for an agent."""
    query = {"agent_id": agent_id}
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
    dec_ids = [d["decision_id"] for d in items]
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
    # Find client records for this buyer (by buyer_id or by email match)
    buyer = await db.users.find_one({"user_id": buyer_id}, {"_id": 0, "email": 1})
    buyer_email = buyer.get("email") if buyer else None

    query = {"buyer_id": buyer_id}
    if buyer_email:
        query = {"$or": [{"buyer_id": buyer_id}, {"email": buyer_email}]}

    clients = await db.clients.find(
        query, {"_id": 0, "client_id": 1, "project_id": 1}
    ).to_list(50)
    client_ids = [c["client_id"] for c in clients]

    if not client_ids:
        return []

    # Find decisions where buyer is a recipient
    recipient_records = await db.decision_recipients.find(
        {"client_id": {"$in": client_ids}}, {"_id": 0}
    ).to_list(200)

    decision_ids = list({r["decision_id"] for r in recipient_records})
    if not decision_ids:
        return []

    decisions = await db.decisions.find(
        {"decision_id": {"$in": decision_ids}, "status": {"$ne": "draft"}},
        {"_id": 0}
    ).sort("updated_at", -1).to_list(100)

    # Enrich
    for d in decisions:
        recs = [r for r in recipient_records if r["decision_id"] == d["decision_id"]]
        buyer_rec = next((r for r in recs if r["client_id"] in client_ids), None)
        d["buyer_status"] = buyer_rec["status"] if buyer_rec else "pending"
        d["buyer_comment"] = buyer_rec.get("comment") if buyer_rec else None

    return decisions
