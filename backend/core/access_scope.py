"""
Canonical request access scope for agent routes.

This module centralizes workspace/project scope derivation so routes do not
re-implement ownership and project filtering logic ad hoc.
"""

from dataclasses import dataclass
from typing import Dict, Any, List

from fastapi import HTTPException

from core.access_control import (
    get_workspace_owner_id,
    get_accessible_project_ids,
    is_workspace_owner,
    is_workspace_admin,
)


@dataclass
class AgentAccessScope:
    user: Dict[str, Any]
    workspace_owner_id: str
    accessible_project_ids: List[str]
    can_access_all_projects: bool
    is_owner: bool
    is_admin: bool

    def ensure_project_access(self, project_id: str) -> None:
        if not project_id:
            raise HTTPException(status_code=400, detail="project_id is required")
        if self.can_access_all_projects or project_id in set(self.accessible_project_ids):
            return
        raise HTTPException(status_code=403, detail="Access denied")

    def project_filter(self, field: str = "project_id") -> Dict[str, Any]:
        if self.can_access_all_projects:
            return {}
        if not self.accessible_project_ids:
            return {field: {"$in": []}}
        return {field: {"$in": self.accessible_project_ids}}


async def resolve_agent_access_scope(user: Dict[str, Any]) -> AgentAccessScope:
    workspace_owner_id = get_workspace_owner_id(user)
    accessible_project_ids = await get_accessible_project_ids(user)
    owner = is_workspace_owner(user)
    admin = is_workspace_admin(user)
    can_access_all_projects = owner or (admin and not user.get("assigned_project_ids"))
    return AgentAccessScope(
        user=user,
        workspace_owner_id=workspace_owner_id,
        accessible_project_ids=accessible_project_ids,
        can_access_all_projects=can_access_all_projects,
        is_owner=owner,
        is_admin=admin,
    )
