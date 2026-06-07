"""
Recipient Scope Service.

Single authority for resolving buyer/client recipient scope, including
same-unit co-owner expansion used across documents, activities, decisions,
and buyer portal aggregations.
"""
from typing import Dict, Any, List

from database import db


def _dedupe_ids(values: List[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for value in values:
        cid = str(value or "").strip()
        if cid and cid not in seen:
            seen.add(cid)
            out.append(cid)
    return out


async def expand_client_ids_to_unit_peers(client_ids: List[str]) -> List[str]:
    """
    Expand explicit client_ids with all peer clients sharing the same unit(s).
    """
    base_ids = _dedupe_ids(client_ids or [])
    if not base_ids:
        return []

    selected_clients = await db.clients.find(
        {"client_id": {"$in": base_ids}},
        {"_id": 0, "unit_id": 1},
    ).to_list(len(base_ids))
    unit_ids = _dedupe_ids([c.get("unit_id") for c in selected_clients if c.get("unit_id")])
    if not unit_ids:
        return base_ids

    peers = await db.clients.find(
        {"unit_id": {"$in": unit_ids}},
        {"_id": 0, "client_id": 1},
    ).to_list(2000)
    peer_ids = _dedupe_ids([p.get("client_id") for p in peers if p.get("client_id")])
    return _dedupe_ids(base_ids + peer_ids)


async def get_buyer_scope(buyer_id: str, include_unit_peers: bool = True) -> Dict[str, Any]:
    """
    Resolve buyer scope:
    - direct client rows (`client_ids`)
    - optionally same-unit peer client rows (`peer_client_ids`)
    """
    clients = await db.clients.find(
        {"buyer_id": buyer_id},
        {"_id": 0},
    ).to_list(500)
    if not clients:
        return {"clients": [], "client_ids": [], "peer_client_ids": [], "unit_ids": []}

    client_ids = _dedupe_ids([c.get("client_id") for c in clients if c.get("client_id")])
    unit_ids = _dedupe_ids([c.get("unit_id") for c in clients if c.get("unit_id")])

    if include_unit_peers and unit_ids:
        peer_client_ids = await expand_client_ids_to_unit_peers(client_ids)
    else:
        peer_client_ids = client_ids

    return {
        "clients": clients,
        "client_ids": client_ids,
        "peer_client_ids": peer_client_ids,
        "unit_ids": unit_ids,
    }
