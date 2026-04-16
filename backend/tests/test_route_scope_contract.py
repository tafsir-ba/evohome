import asyncio
import sys
from pathlib import Path
import types

import pytest
from fastapi import HTTPException

sys.path.append(str(Path(__file__).resolve().parents[1]))

# Optional dependency used by services.qr_service; not needed for these tests.
qrbill_stub = types.ModuleType("qrbill")
qrbill_stub.QRBill = object
sys.modules.setdefault("qrbill", qrbill_stub)

# Optional AI dependencies imported by services package init.
fitz_stub = types.ModuleType("fitz")
fitz_stub.open = lambda *_args, **_kwargs: None
fitz_stub.Matrix = object
sys.modules.setdefault("fitz", fitz_stub)
openai_stub = types.ModuleType("openai")
openai_stub.OpenAI = object
sys.modules.setdefault("openai", openai_stub)
stripe_stub = types.ModuleType("stripe")
sys.modules.setdefault("stripe", stripe_stub)

from routes import projects_v2, steps_v2


def _run(coro):
    return asyncio.run(coro)


class _Scope:
    def __init__(self, workspace_owner_id="owner_1", accessible_project_ids=None, denied_project_ids=None):
        self.workspace_owner_id = workspace_owner_id
        self.accessible_project_ids = accessible_project_ids or []
        self.denied_project_ids = set(denied_project_ids or [])
        self.checked = []

    def ensure_project_access(self, project_id):
        self.checked.append(project_id)
        if project_id in self.denied_project_ids:
            raise HTTPException(status_code=403, detail="Access denied")


def test_projects_get_project_denies_when_scope_rejects(monkeypatch):
    scope = _Scope(denied_project_ids={"p_denied"})

    async def _resolve_scope(_user):
        return scope

    monkeypatch.setattr(projects_v2, "resolve_agent_access_scope", _resolve_scope)

    with pytest.raises(HTTPException) as exc:
        _run(projects_v2.get_project("p_denied", user={"role": "agent", "user_id": "u1"}))

    assert exc.value.status_code == 403
    assert scope.checked == ["p_denied"]


def test_projects_get_project_returns_data_when_scope_allows(monkeypatch):
    scope = _Scope()
    fake_project = {"project_id": "p1", "name": "Allowed"}

    async def _resolve_scope(_user):
        return scope

    async def _get_project(project_id):
        assert project_id == "p1"
        return fake_project

    monkeypatch.setattr(projects_v2, "resolve_agent_access_scope", _resolve_scope)
    monkeypatch.setattr(projects_v2.project_service, "get_project", _get_project)

    result = _run(projects_v2.get_project("p1", user={"role": "agent", "user_id": "u1"}))
    assert result == fake_project
    assert scope.checked == ["p1"]


def test_steps_list_for_agent_uses_scope(monkeypatch):
    scope = _Scope(denied_project_ids={"p_blocked"})

    async def _resolve_scope(_user):
        return scope

    monkeypatch.setattr(steps_v2, "resolve_agent_access_scope", _resolve_scope)

    with pytest.raises(HTTPException) as exc:
        _run(steps_v2.list_steps("p_blocked", user={"role": "agent", "user_id": "u1"}))

    assert exc.value.status_code == 403
    assert scope.checked == ["p_blocked"]


def test_steps_list_for_buyer_skips_agent_scope(monkeypatch):
    async def _list_steps_by_project(project_id):
        assert project_id == "p1"
        return [{"step_id": "s1", "project_id": "p1"}]

    monkeypatch.setattr(steps_v2.step_service, "list_steps_by_project", _list_steps_by_project)

    result = _run(steps_v2.list_steps("p1", user={"role": "buyer", "user_id": "buyer_1"}))
    assert result["total"] == 1
    assert result["steps"][0]["step_id"] == "s1"


