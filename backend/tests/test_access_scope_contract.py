import asyncio
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from core.access_control import (
    can_access_project,
    get_accessible_project_ids,
    init_access_control,
)
from core.access_scope import resolve_agent_access_scope


class _FakeCursor:
    def __init__(self, rows):
        self._rows = rows

    async def to_list(self, _limit):
        return list(self._rows)


def _matches(doc, query):
    for key, expected in query.items():
        value = doc.get(key)
        if isinstance(expected, dict):
            if "$in" in expected:
                if value not in expected["$in"]:
                    return False
            else:
                return False
        elif value != expected:
            return False
    return True


class _FakeCollection:
    def __init__(self, rows):
        self._rows = rows

    async def find_one(self, query, _projection=None):
        for row in self._rows:
            if _matches(row, query):
                return dict(row)
        return None

    def find(self, query, _projection=None):
        rows = [dict(row) for row in self._rows if _matches(row, query)]
        return _FakeCursor(rows)


class _FakeDb:
    def __init__(self):
        self.projects = _FakeCollection(
            [
                {"project_id": "p1", "agent_id": "owner_1"},
                {"project_id": "p2", "agent_id": "owner_1"},
                {"project_id": "p3", "agent_id": "owner_2"},
            ]
        )
        self.clients = _FakeCollection([])


def _run(coro):
    return asyncio.run(coro)


def test_member_with_empty_explicit_assignment_has_no_project_access():
    init_access_control(_FakeDb())
    member = {
        "role": "agent",
        "user_id": "member_1",
        "workspace_owner_id": "owner_1",
        "workspace_role": "member",
        "assigned_project_ids": [],
    }

    assert _run(get_accessible_project_ids(member)) == []
    assert _run(can_access_project(member, "p1")) is False

    scope = _run(resolve_agent_access_scope(member))
    assert scope.can_access_all_projects is False
    assert scope.accessible_project_ids == []
    assert scope.project_filter() == {"project_id": {"$in": []}}


def test_admin_with_empty_explicit_assignment_has_full_workspace_access():
    init_access_control(_FakeDb())
    admin = {
        "role": "agent",
        "user_id": "admin_1",
        "workspace_owner_id": "owner_1",
        "workspace_role": "admin",
        "assigned_project_ids": [],
    }

    assert _run(can_access_project(admin, "p1")) is True
    assert _run(can_access_project(admin, "p2")) is True
    assert _run(can_access_project(admin, "p3")) is False

    scope = _run(resolve_agent_access_scope(admin))
    assert scope.can_access_all_projects is True
    assert scope.project_filter() == {}


def test_member_with_assigned_projects_only_gets_assigned_subset():
    init_access_control(_FakeDb())
    member = {
        "role": "agent",
        "user_id": "member_2",
        "workspace_owner_id": "owner_1",
        "workspace_role": "member",
        "assigned_project_ids": ["p2"],
    }

    assert _run(get_accessible_project_ids(member)) == ["p2"]
    assert _run(can_access_project(member, "p1")) is False
    assert _run(can_access_project(member, "p2")) is True

    scope = _run(resolve_agent_access_scope(member))
    assert scope.can_access_all_projects is False
    assert scope.project_filter() == {"project_id": {"$in": ["p2"]}}


def test_owner_has_full_workspace_access():
    init_access_control(_FakeDb())
    owner = {
        "role": "agent",
        "user_id": "owner_1",
    }

    assert _run(get_accessible_project_ids(owner)) == ["p1", "p2"]
    assert _run(can_access_project(owner, "p1")) is True
    assert _run(can_access_project(owner, "p3")) is False

    scope = _run(resolve_agent_access_scope(owner))
    assert scope.is_owner is True
    assert scope.can_access_all_projects is True
    assert scope.project_filter() == {}
