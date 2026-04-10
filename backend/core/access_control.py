"""
Centralized Access Control Module

All access control decisions should flow through this module.
This prevents scattered inline role checks and ensures consistent authorization.

Usage:
    from core.access_control import can_access_project, can_access_vault_doc
    
    if not await can_access_project(user, project_id):
        raise HTTPException(status_code=403, detail="Access denied")
"""

from typing import Dict, Any, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase

# Database reference - set by main app
_db: Optional[AsyncIOMotorDatabase] = None


def init_access_control(db: AsyncIOMotorDatabase):
    """Initialize access control module with database reference"""
    global _db
    _db = db


def get_db() -> AsyncIOMotorDatabase:
    """Get database reference"""
    if _db is None:
        raise RuntimeError("Access control module not initialized. Call init_access_control(db) first.")
    return _db


# ==================== PROJECT ACCESS ====================

async def can_access_project(user: Dict[str, Any], project_id: str) -> bool:
    """
    Check if user can access a project.
    - Agents: can access projects they own
    - Buyers: can access projects they are associated with via client record
    """
    db = get_db()
    is_demo = user.get('is_demo', False)
    
    if user['role'] == 'agent':
        project = await db.projects.find_one(
            {"project_id": project_id, "agent_id": user['user_id'], "is_demo": is_demo}
        )
        return project is not None
    
    elif user['role'] == 'buyer':
        client = await db.clients.find_one(
            {"buyer_id": user['user_id'], "project_id": project_id, "is_demo": is_demo}
        )
        return client is not None
    
    return False


async def get_accessible_project_ids(user: Dict[str, Any]) -> list:
    """
    Get list of project IDs the user can access.
    """
    db = get_db()
    is_demo = user.get('is_demo', False)
    
    if user['role'] == 'agent':
        projects = await db.projects.find(
            {"agent_id": user['user_id'], "is_demo": is_demo},
            {"project_id": 1}
        ).to_list(1000)
        return [p['project_id'] for p in projects]
    
    elif user['role'] == 'buyer':
        clients = await db.clients.find(
            {"buyer_id": user['user_id'], "is_demo": is_demo},
            {"project_id": 1}
        ).to_list(100)
        return list(set(c['project_id'] for c in clients if c.get('project_id')))
    
    return []


# ==================== CLIENT ACCESS ====================

async def can_access_client(user: Dict[str, Any], client_id: str) -> bool:
    """
    Check if user can access a client record.
    - Agents: can access clients they created/own
    - Buyers: can access only their own client record
    """
    db = get_db()
    is_demo = user.get('is_demo', False)
    
    if user['role'] == 'agent':
        client = await db.clients.find_one(
            {"client_id": client_id, "agent_id": user['user_id'], "is_demo": is_demo}
        )
        return client is not None
    
    elif user['role'] == 'buyer':
        client = await db.clients.find_one(
            {"client_id": client_id, "buyer_id": user['user_id'], "is_demo": is_demo}
        )
        return client is not None
    
    return False


async def get_accessible_client_ids(user: Dict[str, Any]) -> list:
    """
    Get list of client IDs the user can access.
    """
    db = get_db()
    is_demo = user.get('is_demo', False)
    
    if user['role'] == 'agent':
        clients = await db.clients.find(
            {"agent_id": user['user_id'], "is_demo": is_demo},
            {"client_id": 1}
        ).to_list(1000)
        return [c['client_id'] for c in clients]
    
    elif user['role'] == 'buyer':
        clients = await db.clients.find(
            {"buyer_id": user['user_id'], "is_demo": is_demo},
            {"client_id": 1}
        ).to_list(100)
        return [c['client_id'] for c in clients]
    
    return []


# ==================== VAULT ACCESS ====================

async def can_access_vault_doc(user: Dict[str, Any], vault_id: str) -> bool:
    """
    Check if user can access a vault document.
    - Agents: can access vault docs they own
    - Buyers: can access vault docs shared with them
    """
    db = get_db()
    is_demo = user.get('is_demo', False)
    
    if user['role'] == 'agent':
        doc = await db.vault_documents.find_one(
            {"vault_id": vault_id, "agent_id": user['user_id'], "is_demo": is_demo}
        )
        return doc is not None
    
    elif user['role'] == 'buyer':
        # Get buyer's client record
        client = await db.clients.find_one(
            {"buyer_id": user['user_id'], "is_demo": is_demo},
            {"client_id": 1, "agent_id": 1}
        )
        if not client:
            return False
        
        # Check if vault doc is shared with this buyer's client
        doc = await db.vault_documents.find_one({
            "vault_id": vault_id,
            "agent_id": client.get('agent_id'),
            "is_demo": is_demo,
            "access_level": "shared",
            "shared_with_clients": client.get('client_id')
        })
        return doc is not None
    
    return False


# ==================== DOCUMENT ACCESS ====================

async def can_access_document(user: Dict[str, Any], document_id: str) -> bool:
    """
    Check if user can access a document (quote/invoice).
    - Agents: can access documents they created
    - Buyers: can access documents sent to their client record
    """
    db = get_db()
    is_demo = user.get('is_demo', False)
    
    if user['role'] == 'agent':
        doc = await db.documents.find_one(
            {"document_id": document_id, "agent_id": user['user_id'], "is_demo": is_demo}
        )
        return doc is not None
    
    elif user['role'] == 'buyer':
        # Get buyer's client IDs
        clients = await db.clients.find(
            {"buyer_id": user['user_id'], "is_demo": is_demo},
            {"client_id": 1}
        ).to_list(100)
        client_ids = [c['client_id'] for c in clients]
        
        if not client_ids:
            return False
        
        doc = await db.documents.find_one({
            "document_id": document_id,
            "client_id": {"$in": client_ids},
            "is_demo": is_demo
        })
        return doc is not None
    
    return False


# ==================== HELPER FUNCTIONS ====================

def is_agent(user: Dict[str, Any]) -> bool:
    """Check if user is an agent"""
    return user.get('role') == 'agent'


def is_buyer(user: Dict[str, Any]) -> bool:
    """Check if user is a buyer"""
    return user.get('role') == 'buyer'


def get_is_demo(user: Dict[str, Any]) -> bool:
    """Get is_demo flag from user"""
    return user.get('is_demo', False)
