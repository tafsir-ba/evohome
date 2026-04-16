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


def get_workspace_owner_id(user: Dict[str, Any]) -> str:
    """Return effective workspace owner id for agent-scoped access."""
    return user.get('workspace_owner_id') or user.get('user_id')


def is_workspace_owner(user: Dict[str, Any]) -> bool:
    """Workspace owner has no workspace_owner_id set."""
    return not bool(user.get('workspace_owner_id'))


def is_workspace_admin(user: Dict[str, Any]) -> bool:
    """Workspace admin includes owner and invited admin role."""
    return is_workspace_owner(user) or user.get('workspace_role') == 'admin'


def _normalized_assigned_project_ids(user: Dict[str, Any]) -> List[str]:
    assigned = user.get("assigned_project_ids") or []
    return [project_id for project_id in assigned if project_id]


# ── Project access ──

async def can_access_project(user: Dict[str, Any], project_id: str) -> bool:
    db = get_db()
    if user['role'] == 'agent':
        scope_agent_id = get_workspace_owner_id(user)
        project = await db.projects.find_one(
            {"project_id": project_id, "agent_id": scope_agent_id}
        )
        if project is None:
            return False
        if is_workspace_owner(user):
            return True
        assigned_project_ids = _normalized_assigned_project_ids(user)
        return not assigned_project_ids or project_id in assigned_project_ids
    elif user['role'] == 'buyer':
        return await db.clients.find_one(
            {"buyer_id": user['user_id'], "project_id": project_id}
        ) is not None
    return False


async def get_accessible_project_ids(user: Dict[str, Any]) -> List[str]:
    db = get_db()
    if user['role'] == 'agent':
        scope_agent_id = get_workspace_owner_id(user)
        projects = await db.projects.find(
            {"agent_id": scope_agent_id}, {"project_id": 1}
        ).to_list(1000)
        project_ids = [p['project_id'] for p in projects]
        if is_workspace_owner(user):
            return project_ids
        assigned_project_ids = set(_normalized_assigned_project_ids(user))
        if not assigned_project_ids:
            return project_ids
        return [project_id for project_id in project_ids if project_id in assigned_project_ids]
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
        scope_agent_id = get_workspace_owner_id(user)
        client = await db.clients.find_one(
            {"client_id": client_id, "agent_id": scope_agent_id},
            {"_id": 0, "project_id": 1},
        )
        if client is None:
            return False
        project_id = client.get("project_id")
        if not project_id:
            return is_workspace_owner(user)
        return await can_access_project(user, project_id)
    elif user['role'] == 'buyer':
        return await db.clients.find_one(
            {"client_id": client_id, "buyer_id": user['user_id']}
        ) is not None
    return False


async def get_accessible_client_ids(user: Dict[str, Any]) -> List[str]:
    db = get_db()
    if user['role'] == 'agent':
        accessible_project_ids = await get_accessible_project_ids(user)
        query: Dict[str, Any] = {"agent_id": get_workspace_owner_id(user)}
        if accessible_project_ids:
            query["project_id"] = {"$in": accessible_project_ids}
        elif not is_workspace_owner(user):
            return []
        clients = await db.clients.find(query, {"client_id": 1}).to_list(1000)
        return [c['client_id'] for c in clients]
    elif user['role'] == 'buyer':
        clients = await db.clients.find(
            {"buyer_id": user['user_id']}, {"client_id": 1}
        ).to_list(100)
        return [c['client_id'] for c in clients]
    return []


# ── Vault access ──

async def can_access_vault_doc(user: Dict[str, Any], vault_document_id: str) -> bool:
    db = get_db()
    if user['role'] == 'agent':
        scope_agent_id = get_workspace_owner_id(user)
        doc = await db.vault_documents.find_one(
            {"vault_document_id": vault_document_id, "agent_id": scope_agent_id},
            {"_id": 0, "project_id": 1},
        )
        if doc is None:
            return False
        project_id = doc.get("project_id")
        if not project_id:
            return is_workspace_owner(user)
        return await can_access_project(user, project_id)
    elif user['role'] == 'buyer':
        client = await db.clients.find_one(
            {"buyer_id": user['user_id']}, {"client_id": 1, "agent_id": 1}
        )
        if not client:
            return False
        return await db.vault_documents.find_one({
            "vault_document_id": vault_document_id,
            "agent_id": client.get('agent_id'),
            "access_level": "shared",
            "$or": [
                {"buyer_ids": user['user_id']},
                {"client_ids": client.get('client_id')},
            ]
        }) is not None
    return False


# ── Document access ──

async def can_access_document(user: Dict[str, Any], document_id: str) -> bool:
    db = get_db()
    if user['role'] == 'agent':
        scope_agent_id = get_workspace_owner_id(user)
        doc = await db.documents.find_one(
            {"document_id": document_id, "agent_id": scope_agent_id},
            {"_id": 0, "project_id": 1},
        )
        if doc is None:
            return False
        project_id = doc.get("project_id")
        if not project_id:
            return is_workspace_owner(user)
        return await can_access_project(user, project_id)
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


