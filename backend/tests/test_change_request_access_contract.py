import asyncio
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
import types

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(BACKEND_DIR))
MODULE_PATH = BACKEND_DIR / "services" / "change_request_access.py"

# Avoid importing the heavy services package (requires optional deps like qrbill).
services_stub = types.ModuleType("services")
recipient_scope_stub = types.ModuleType("services.recipient_scope_service")

async def _default_buyer_scope(_buyer_user_id, include_unit_peers=True):
    return {"peer_client_ids": []}

recipient_scope_stub.get_buyer_scope = _default_buyer_scope
services_stub.recipient_scope_service = recipient_scope_stub
_old_services = sys.modules.get("services")
_old_recipient_scope = sys.modules.get("services.recipient_scope_service")
sys.modules["services"] = services_stub
sys.modules["services.recipient_scope_service"] = recipient_scope_stub

spec = importlib.util.spec_from_file_location("change_request_access_test_module", MODULE_PATH)
change_request_access = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(change_request_access)

# Restore global module registry so this test file doesn't affect others.
if _old_services is not None:
    sys.modules["services"] = _old_services
else:
    sys.modules.pop("services", None)
if _old_recipient_scope is not None:
    sys.modules["services.recipient_scope_service"] = _old_recipient_scope
else:
    sys.modules.pop("services.recipient_scope_service", None)


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


def _run(coro):
    return asyncio.run(coro)


def _scope(owner_id, project_ids, can_access_all=False):
    return SimpleNamespace(
        workspace_owner_id=owner_id,
        accessible_project_ids=project_ids,
        can_access_all_projects=can_access_all,
    )


def test_agent_can_access_document_only_inside_scope(monkeypatch):
    fake_db = SimpleNamespace(
        documents=_FakeCollection(
            [
                {"document_id": "d1", "agent_id": "owner_1", "project_id": "p1", "client_id": "c1"},
                {"document_id": "d2", "agent_id": "owner_1", "project_id": "p2", "client_id": "c2"},
            ]
        ),
        decisions=_FakeCollection([]),
        decision_recipients=_FakeCollection([]),
    )
    monkeypatch.setattr(change_request_access, "db", fake_db)
    async def _resolve_scope(_user):
        return _scope("owner_1", ["p1"], can_access_all=False)

    monkeypatch.setattr(change_request_access, "resolve_agent_access_scope", _resolve_scope)

    user = {"role": "agent", "user_id": "member_1"}
    assert _run(change_request_access.user_can_access_entity(user, "document", "d1")) is True
    assert _run(change_request_access.user_can_access_entity(user, "document", "d2")) is False


def test_agent_decision_access_requires_workspace_owner_id(monkeypatch):
    fake_db = SimpleNamespace(
        documents=_FakeCollection([]),
        decisions=_FakeCollection(
            [
                {"decision_id": "dec_ok", "agent_id": "owner_1", "project_id": "p1"},
                {"decision_id": "dec_other_owner", "agent_id": "owner_2", "project_id": "p1"},
            ]
        ),
        decision_recipients=_FakeCollection([]),
    )
    monkeypatch.setattr(change_request_access, "db", fake_db)
    async def _resolve_scope(_user):
        return _scope("owner_1", ["p1"], can_access_all=False)

    monkeypatch.setattr(change_request_access, "resolve_agent_access_scope", _resolve_scope)

    user = {"role": "agent", "user_id": "member_1"}
    assert _run(change_request_access.user_can_access_entity(user, "decision", "dec_ok")) is True
    assert _run(change_request_access.user_can_access_entity(user, "decision", "dec_other_owner")) is False


def test_buyer_decision_access_requires_recipient_overlap(monkeypatch):
    fake_db = SimpleNamespace(
        documents=_FakeCollection([]),
        decisions=_FakeCollection([{"decision_id": "dec1", "agent_id": "owner_1", "project_id": "p1"}]),
        decision_recipients=_FakeCollection(
            [
                {"decision_id": "dec1", "client_id": "c1"},
                {"decision_id": "dec1", "client_id": "c2"},
            ]
        ),
    )
    monkeypatch.setattr(change_request_access, "db", fake_db)
    async def _buyer_scope_allow(_buyer_id):
        return ["c2"]

    monkeypatch.setattr(change_request_access, "_buyer_scope_client_ids", _buyer_scope_allow)

    buyer_user = {"role": "buyer", "user_id": "buyer_1"}
    assert _run(change_request_access.user_can_access_entity(buyer_user, "decision", "dec1")) is True

    async def _buyer_scope_deny(_buyer_id):
        return ["c9"]

    monkeypatch.setattr(change_request_access, "_buyer_scope_client_ids", _buyer_scope_deny)
    assert _run(change_request_access.user_can_access_entity(buyer_user, "decision", "dec1")) is False
