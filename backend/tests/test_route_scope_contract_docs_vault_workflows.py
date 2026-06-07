"""
Route-level contract tests: documents_v2, vault_v2, workflows (scope / access).
Stubs optional deps before importing route modules (matches test_route_scope_contract pattern).
"""
import asyncio
import sys
from pathlib import Path
import types

# file_service mkdirs a hardcoded /app path at import; skip when that path is unavailable.
from pathlib import Path as _Path

_orig_mkdir = _Path.mkdir


def _mkdir_noop(self, mode=0o777, parents=False, exist_ok=False):
    try:
        return _orig_mkdir(self, mode=mode, parents=parents, exist_ok=exist_ok)
    except FileNotFoundError:
        if str(self).startswith("/app/"):
            return
        raise


_Path.mkdir = _mkdir_noop

import pytest
from fastapi import HTTPException
sys.path.append(str(Path(__file__).resolve().parents[1]))

# documents_v2 uses File/Form; FastAPI requires python-multipart.
pytest.importorskip("multipart")

# --- stubs for heavy optional imports pulled in via services / routes ---
qrbill_stub = types.ModuleType("qrbill")
qrbill_stub.QRBill = object
sys.modules.setdefault("qrbill", qrbill_stub)

fitz_stub = types.ModuleType("fitz")
fitz_stub.open = lambda *_a, **_k: None
fitz_stub.Matrix = object
sys.modules.setdefault("fitz", fitz_stub)

openai_stub = types.ModuleType("openai")
openai_stub.OpenAI = object
sys.modules.setdefault("openai", openai_stub)

stripe_stub = types.ModuleType("stripe")
sys.modules.setdefault("stripe", stripe_stub)

boto3_stub = types.ModuleType("boto3")
boto3_stub.client = lambda *a, **k: None
sys.modules.setdefault("boto3", boto3_stub)
botocore_exc = types.ModuleType("botocore.exceptions")


class _ClientError(Exception):
    pass


botocore_exc.ClientError = _ClientError
sys.modules.setdefault("botocore.exceptions", botocore_exc)

from routes import documents_v2, vault_v2, workflows


def _run(coro):
    return asyncio.run(coro)


class _Scope:
    def __init__(
        self,
        workspace_owner_id="owner_1",
        accessible_project_ids=None,
        can_access_all_projects=False,
        denied_project_ids=None,
    ):
        self.workspace_owner_id = workspace_owner_id
        self.accessible_project_ids = accessible_project_ids or []
        self.can_access_all_projects = can_access_all_projects
        self.denied_project_ids = set(denied_project_ids or [])
        self.checked = []

    def ensure_project_access(self, project_id):
        self.checked.append(project_id)
        if project_id in self.denied_project_ids:
            raise HTTPException(status_code=403, detail="Access denied")

    def project_filter(self, field="project_id"):
        if self.can_access_all_projects:
            return {}
        if not self.accessible_project_ids:
            return {field: {"$in": []}}
        return {field: {"$in": self.accessible_project_ids}}


# --- documents_v2 ---


def test_get_document_agent_denied_when_can_access_document_false(monkeypatch):
    async def deny(_user, _doc_id):
        return False

    async def never_called(*_a, **_k):
        raise AssertionError("get_document should not be called")

    monkeypatch.setattr(documents_v2, "can_access_document", deny)
    monkeypatch.setattr(documents_v2.document_service, "get_document", never_called)

    with pytest.raises(HTTPException) as exc:
        _run(
            documents_v2.get_document(
                "doc_1",
                user={"role": "agent", "user_id": "m1", "workspace_owner_id": "owner_1"},
            )
        )
    assert exc.value.status_code == 403


def test_get_documents_passes_scope_project_ids_to_list_documents(monkeypatch):
    scope = _Scope(workspace_owner_id="owner_1", accessible_project_ids=["p1", "p2"])
    captured = {}

    async def _resolve_scope(_user):
        return scope

    async def _list_documents(uid, role, doc_type, status, project_scope):
        captured["project_scope"] = project_scope
        return []

    monkeypatch.setattr(documents_v2, "resolve_agent_access_scope", _resolve_scope)
    monkeypatch.setattr(documents_v2.document_service, "list_documents", _list_documents)

    _run(
        documents_v2.get_documents(
            doc_type=None,
            status=None,
            user={"role": "agent", "user_id": "m1", "workspace_owner_id": "owner_1"},
        )
    )
    assert captured["project_scope"] == ["p1", "p2"]


# --- vault_v2 ---


def test_list_vault_documents_denies_project_out_of_scope(monkeypatch):
    scope = _Scope(denied_project_ids={"p_bad"})

    async def _resolve_scope(_user):
        return scope

    async def should_not_run(*_a, **_k):
        raise AssertionError("vault_service.list_vault_documents should not run")

    monkeypatch.setattr(vault_v2, "resolve_agent_access_scope", _resolve_scope)
    monkeypatch.setattr(vault_v2.vault_service, "list_vault_documents", should_not_run)

    with pytest.raises(HTTPException) as exc:
        _run(
            vault_v2.list_vault_documents(
                project_id="p_bad",
                user={"role": "agent", "user_id": "m1"},
            )
        )
    assert exc.value.status_code == 403
    assert scope.checked == ["p_bad"]


def test_list_vault_documents_passes_workspace_and_scope_ids(monkeypatch):
    scope = _Scope(workspace_owner_id="owner_99", accessible_project_ids=["a", "b"])
    captured = {}

    async def _resolve_scope(_user):
        return scope

    async def _list_vault_documents(agent_id, project_id, scoped_ids):
        captured["args"] = (agent_id, project_id, scoped_ids)
        return []

    monkeypatch.setattr(vault_v2, "resolve_agent_access_scope", _resolve_scope)
    monkeypatch.setattr(vault_v2.vault_service, "list_vault_documents", _list_vault_documents)

    _run(
        vault_v2.list_vault_documents(
            project_id=None,
            user={"role": "agent", "user_id": "m1"},
        )
    )
    assert captured["args"] == ("owner_99", None, ["a", "b"])


# --- workflows ---


def test_execute_workflow_denies_context_project_before_workflow_service(monkeypatch):
    """Out-of-scope project_id raises 403 before get_workflow_service."""
    scope = _Scope(denied_project_ids={"p_denied"})

    async def _resolve_scope(_user):
        return scope

    def _boom(*_a, **_k):
        raise AssertionError("get_workflow_service should not be called when project is denied")

    monkeypatch.setattr(workflows, "resolve_agent_access_scope", _resolve_scope)
    monkeypatch.setattr(workflows, "get_workflow_service", _boom)

    req = workflows.WorkflowExecuteRequest(
        template_id="t1",
        context={"project_id": "p_denied"},
        mode="automatic",
    )
    with pytest.raises(HTTPException) as exc:
        _run(workflows.execute_workflow(req, user={"role": "agent", "user_id": "u1"}))
    assert exc.value.status_code == 403
    assert scope.checked == ["p_denied"]


def test_get_workflow_selectors_denies_project_out_of_scope(monkeypatch):
    scope = _Scope(denied_project_ids={"p_x"})

    async def _resolve_scope(_user):
        return scope

    async def _sel(*_a, **_k):
        raise AssertionError("selector should not run")

    monkeypatch.setattr(workflows, "resolve_agent_access_scope", _resolve_scope)
    monkeypatch.setattr(workflows, "_select_documents", _sel)

    with pytest.raises(HTTPException) as exc:
        _run(
            workflows.get_workflow_selectors(
                selector_type="document",
                project_id="p_x",
                user={"role": "agent", "user_id": "u1"},
            )
        )
    assert exc.value.status_code == 403


def test_build_action_executor_create_client_warns_when_project_denied(monkeypatch):
    scope = _Scope(denied_project_ids={"p_forbidden"})

    async def _resolve_scope(_user):
        return scope

    monkeypatch.setattr(workflows, "resolve_agent_access_scope", _resolve_scope)
    warnings = {}
    agent_user = {"role": "agent", "user_id": "member_1", "workspace_owner_id": "owner_1"}

    executor = workflows._build_action_executor(
        "owner_1", "Agent", "a@x.ch", warnings, agent_user
    )

    async def _run_action():
        return await executor(
            "create_client",
            {"project_id": "p_forbidden", "client_name": "X"},
            {},
        )

    result = _run(_run_action())
    assert result.get("_warning") == "Access denied to target project"
    assert warnings.get("create_client") == "Access denied to target project"
