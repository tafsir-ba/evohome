"""
Centralized Access Control Module — Canonical Rebuild

All access control decisions flow through this module.
Ownership is determined by agent_id/buyer_id — no is_demo branching.
"""
from typing import Dict, Any, Optional, List
from motor.motor_asyncio import AsyncIOMotorDatabase

_db: Optional[AsyncIOMotorDatabase] = None


def init_access_control(db: AsyncIOMotorDatabase):
    global _db
    _db = db


def get_db() -> AsyncIOMotorDatabase:
    if _db is None:
        raise RuntimeError("Access control not initialized")
    return _db


# ── Role checks ──

def is_agent(user: Dict[str, Any]) -> bool:
    return user.get('role') == 'agent'


def is_buyer(user: Dict[str, Any]) -> bool:
    return user.get('role') == 'buyer'


# ── Project access ──

async def can_access_project(user: Dict[str, Any], project_id: str) -> bool:
    db = get_db()
    if user['role'] == 'agent':
        return await db.projects.find_one(
            {"project_id": project_id, "agent_id": user['user_id']}
        ) is not None
    elif user['role'] == 'buyer':
        return await db.clients.find_one(
            {"buyer_id": user['user_id'], "project_id": project_id}
        ) is not None
    return False


async def get_accessible_project_ids(user: Dict[str, Any]) -> List[str]:
    db = get_db()
    if user['role'] == 'agent':
        projects = await db.projects.find(
            {"agent_id": user['user_id']}, {"project_id": 1}
        ).to_list(1000)
        return [p['project_id'] for p in projects]
    elif user['role'] == 'buyer':
        clients = await db.clients.find(
            {"buyer_id": user['user_id']}, {"project_id": 1}
        ).to_list(100)
        return list(set(c['project_id'] for c in clients if c.get('project_id')))
    return []


# ── Client access ──

async def can_access_client(user: Dict[str, Any], client_id: str) -> bool:
    db = get_db()
    if user['role'] == 'agent':
        return await db.clients.find_one(
            {"client_id": client_id, "agent_id": user['user_id']}
        ) is not None
    elif user['role'] == 'buyer':
        return await db.clients.find_one(
            {"client_id": client_id, "buyer_id": user['user_id']}
        ) is not None
    return False


async def get_accessible_client_ids(user: Dict[str, Any]) -> List[str]:
    db = get_db()
    if user['role'] == 'agent':
        clients = await db.clients.find(
            {"agent_id": user['user_id']}, {"client_id": 1}
        ).to_list(1000)
        return [c['client_id'] for c in clients]
    elif user['role'] == 'buyer':
        clients = await db.clients.find(
            {"buyer_id": user['user_id']}, {"client_id": 1}
        ).to_list(100)
        return [c['client_id'] for c in clients]
    return []


# ── Vault access ──

async def can_access_vault_doc(user: Dict[str, Any], vault_id: str) -> bool:
    db = get_db()
    if user['role'] == 'agent':
        return await db.vault_documents.find_one(
            {"vault_id": vault_id, "agent_id": user['user_id']}
        ) is not None
    elif user['role'] == 'buyer':
        client = await db.clients.find_one(
            {"buyer_id": user['user_id']}, {"client_id": 1, "agent_id": 1}
        )
        if not client:
            return False
        return await db.vault_documents.find_one({
            "vault_id": vault_id,
            "agent_id": client.get('agent_id'),
            "access_level": "shared",
            "shared_with_clients": client.get('client_id')
        }) is not None
    return False


# ── Document access ──

async def can_access_document(user: Dict[str, Any], document_id: str) -> bool:
    db = get_db()
    if user['role'] == 'agent':
        return await db.documents.find_one(
            {"document_id": document_id, "agent_id": user['user_id']}
        ) is not None
    elif user['role'] == 'buyer':
        clients = await db.clients.find(
            {"buyer_id": user['user_id']}, {"client_id": 1}
        ).to_list(100)
        client_ids = [c['client_id'] for c in clients]
        if not client_ids:
            return False
        return await db.documents.find_one({
            "document_id": document_id,
            "client_id": {"$in": client_ids}
        }) is not None
    return False


# ── Deprecated stub (removed after all routes rebuilt) ──

def get_is_demo(user: Dict[str, Any]) -> bool:
    """DEPRECATED — returns False. is_demo removed from canonical architecture."""
    return False
