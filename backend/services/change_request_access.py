"""
Access control for change request APIs — mirrors document/decision ownership rules.
"""
from typing import Any, Dict

from database import db


async def _buyer_client_ids(buyer_user_id: str):
    clients = await db.clients.find(
        {"buyer_id": buyer_user_id}, {"_id": 0, "client_id": 1}
    ).to_list(100)
    return [c["client_id"] for c in clients]


async def user_can_access_entity(user: Dict[str, Any], entity_type: str, entity_id: str) -> bool:
    """Return True if this user may read/write change requests for the entity."""
    role = user.get("role", "buyer")
    uid = user.get("user_id", "")

    if entity_type in ("quote", "invoice", "document"):
        doc = await db.documents.find_one({"document_id": entity_id}, {"_id": 0, "agent_id": 1, "client_id": 1})
        if not doc:
            return False
        if role == "agent":
            return doc.get("agent_id") == uid
        cids = await _buyer_client_ids(uid)
        return doc.get("client_id") in cids

    if entity_type == "decision":
        dec = await db.decisions.find_one({"decision_id": entity_id}, {"_id": 0, "agent_id": 1})
        if not dec:
            return False
        if role == "agent":
            return dec.get("agent_id") == uid
        # Buyer: must be a recipient client for this decision
        recs = await db.decision_recipients.find(
            {"decision_id": entity_id}, {"_id": 0, "client_id": 1}
        ).to_list(200)
        if not recs:
            return False
        cids = await _buyer_client_ids(uid)
        rec_cids = {r["client_id"] for r in recs}
        return bool(rec_cids.intersection(cids))

    return False


async def user_can_access_change_request(user: Dict[str, Any], cr: Dict[str, Any]) -> bool:
    """Return True if user may view this change request record."""
    et = cr.get("entity_type")
    eid = cr.get("entity_id")
    if not et or not eid:
        return False
    return await user_can_access_entity(user, et, eid)
