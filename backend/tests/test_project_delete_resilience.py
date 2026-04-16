import asyncio
import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace


PROJECT_SERVICE_PATH = Path(__file__).resolve().parents[1] / "services" / "project_service.py"


def _run(coro):
    return asyncio.run(coro)


def _load_project_service_module():
    """Load project_service with lightweight stubs to keep this test isolated."""
    database_stub = types.ModuleType("database")
    database_stub.db = object()

    services_pkg = types.ModuleType("services")
    services_pkg.__path__ = []

    billing_stub = types.ModuleType("services.billing_service")

    async def _get_subscription_status(_agent_id):
        return {}

    billing_stub.get_subscription_status = _get_subscription_status

    file_stub = types.ModuleType("services.file_service")
    file_stub.delete_file = lambda _stored_filename: True

    sys.modules["database"] = database_stub
    sys.modules["services"] = services_pkg
    sys.modules["services.billing_service"] = billing_stub
    sys.modules["services.file_service"] = file_stub

    spec = importlib.util.spec_from_file_location("project_service_under_test", PROJECT_SERVICE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


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


def _project_row(row, projection):
    if not projection:
        return dict(row)
    include_keys = [k for k, v in projection.items() if k != "_id" and v]
    if not include_keys:
        return dict(row)
    return {k: row.get(k) for k in include_keys if k in row}


class _FakeCursor:
    def __init__(self, rows):
        self._rows = rows

    async def to_list(self, _limit):
        return list(self._rows)


class _FakeCollection:
    def __init__(self, rows=None):
        self._rows = list(rows or [])
        self.delete_many_calls = []

    async def find_one(self, query, projection=None):
        for row in self._rows:
            if _matches(row, query):
                return _project_row(row, projection)
        return None

    def find(self, query, projection=None):
        rows = [_project_row(row, projection) for row in self._rows if _matches(row, query)]
        return _FakeCursor(rows)

    async def count_documents(self, query):
        return sum(1 for row in self._rows if _matches(row, query))

    async def delete_many(self, query):
        self.delete_many_calls.append(query)
        before = len(self._rows)
        self._rows = [row for row in self._rows if not _matches(row, query)]
        return SimpleNamespace(deleted_count=before - len(self._rows))

    async def delete_one(self, query):
        for idx, row in enumerate(self._rows):
            if _matches(row, query):
                del self._rows[idx]
                return SimpleNamespace(deleted_count=1)
        return SimpleNamespace(deleted_count=0)


class _FakeDb:
    def __init__(self, *, projects, documents, vault_documents, activities, timelines, timeline_steps, decisions):
        self.projects = _FakeCollection(projects)
        self.documents = _FakeCollection(documents)
        self.vault_documents = _FakeCollection(vault_documents)
        self.activities = _FakeCollection(activities)
        self.activity_recipients = _FakeCollection([])
        self.activity_replies = _FakeCollection([])
        self.timelines = _FakeCollection(timelines)
        self.timeline_steps = _FakeCollection(timeline_steps)
        self.timeline_step_documents = _FakeCollection([])
        self.timeline_step_internal_notes = _FakeCollection([])
        self.decisions = _FakeCollection(decisions)
        self.decision_recipients = _FakeCollection([])
        self.change_requests = _FakeCollection([])
        self.team_members = _FakeCollection([])
        self.clients = _FakeCollection([])
        self.units = _FakeCollection([])


def test_delete_project_filters_invalid_linked_ids():
    project_service = _load_project_service_module()
    fake_db = _FakeDb(
        projects=[{"project_id": "p1", "agent_id": "owner_1"}],
        documents=[
            {"project_id": "p1", "status": "Draft", "document_id": "doc_ok"},
            {"project_id": "p1", "status": "Draft"},
            {"project_id": "p1", "status": "Draft", "document_id": None},
            {"project_id": "p1", "status": "Draft", "document_id": 123},
        ],
        vault_documents=[{"project_id": "p1"}],
        activities=[
            {"project_id": "p1", "activity_id": "act_ok"},
            {"project_id": "p1"},
            {"project_id": "p1", "activity_id": None},
        ],
        timelines=[
            {"project_id": "p1", "timeline_id": "tl_ok"},
            {"project_id": "p1"},
            {"project_id": "p1", "timeline_id": 99},
        ],
        timeline_steps=[
            {"project_id": "p1", "timeline_id": "tl_ok", "step_id": "step_ok"},
            {"project_id": "p1", "timeline_id": "tl_ok"},
            {"project_id": "p1", "timeline_id": "tl_ok", "step_id": 77},
        ],
        decisions=[
            {"project_id": "p1", "decision_id": "dec_ok"},
            {"project_id": "p1"},
            {"project_id": "p1", "decision_id": None},
        ],
    )

    async def _impact(_project_id):
        return {"project_id": "p1", "documents_non_draft": 0, "has_linked_data": True}

    project_service.db = fake_db
    project_service.get_project_delete_impact = _impact

    result = _run(project_service.delete_project("p1", "owner_1", force=True))

    assert result["deleted"] is True
    assert fake_db.activity_recipients.delete_many_calls == [{"activity_id": {"$in": ["act_ok"]}}]
    assert fake_db.activity_replies.delete_many_calls == [{"activity_id": {"$in": ["act_ok"]}}]
    assert fake_db.timeline_step_documents.delete_many_calls == [{"timeline_step_id": {"$in": ["step_ok"]}}]
    assert fake_db.timeline_step_internal_notes.delete_many_calls == [{"timeline_step_id": {"$in": ["step_ok"]}}]
    assert fake_db.decision_recipients.delete_many_calls == [{"decision_id": {"$in": ["dec_ok"]}}]
    assert fake_db.change_requests.delete_many_calls[0] == {"entity_id": {"$in": ["doc_ok"]}}
    assert fake_db.change_requests.delete_many_calls[1] == {"project_id": "p1"}


def test_delete_project_does_not_issue_empty_recipient_deletes():
    project_service = _load_project_service_module()
    fake_db = _FakeDb(
        projects=[{"project_id": "p2", "agent_id": "owner_1"}],
        documents=[{"project_id": "p2", "status": "Draft"}],
        vault_documents=[{"project_id": "p2"}],
        activities=[{"project_id": "p2"}],
        timelines=[{"project_id": "p2"}],
        timeline_steps=[],
        decisions=[{"project_id": "p2"}],
    )

    async def _impact(_project_id):
        return {"project_id": "p2", "documents_non_draft": 0, "has_linked_data": True}

    project_service.db = fake_db
    project_service.get_project_delete_impact = _impact

    result = _run(project_service.delete_project("p2", "owner_1", force=True))

    assert result["deleted"] is True
    assert fake_db.activity_recipients.delete_many_calls == []
    assert fake_db.activity_replies.delete_many_calls == []
    assert fake_db.timeline_step_documents.delete_many_calls == []
    assert fake_db.timeline_step_internal_notes.delete_many_calls == []
    assert fake_db.decision_recipients.delete_many_calls == []
    assert fake_db.change_requests.delete_many_calls == [{"project_id": "p2"}]
