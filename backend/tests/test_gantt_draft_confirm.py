"""
Gantt draft confirm — unit tests (no live API; mocked MongoDB).
"""
import importlib
import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_services_dir = Path(__file__).resolve().parents[1] / "services"


@pytest.fixture(scope="module")
def gantt_service_module():
    """Load gantt_service with a stubbed database module."""
    if "database" not in sys.modules:
        db_mock = MagicMock()
        db_mock.gantt_projects = MagicMock()
        db_mock.gantt_tasks = MagicMock()
        db_mock.gantt_audit_events = MagicMock()
        db_module = types.ModuleType("database")
        db_module.db = db_mock
        sys.modules["database"] = db_module

    if "services.gantt_audit" not in sys.modules:
        audit_mod = types.ModuleType("services.gantt_audit")
        audit_mod.log_gantt_event = AsyncMock()
        sys.modules["services.gantt_audit"] = audit_mod

    # Ensure services package exists without pulling qr_service etc.
    if "services" not in sys.modules:
        pkg = types.ModuleType("services")
        pkg.__path__ = [str(_services_dir)]
        sys.modules["services"] = pkg

    for name in ("gantt_constants", "gantt_validation"):
        full = f"services.{name}"
        if full not in sys.modules:
            mod = importlib.import_module(full)

    # Force reload so patches apply cleanly across tests
    if "services.gantt_service" in sys.modules:
        return importlib.reload(sys.modules["services.gantt_service"])

    return importlib.import_module("services.gantt_service")


class TestCreateTasksFromDraft:
    @pytest.mark.asyncio
    async def test_confirm_uses_now_string_without_isoformat_crash(
        self, gantt_service_module
    ):
        """Regression: _now() returns str; create_tasks_from_draft must not call .isoformat()."""
        svc = gantt_service_module

        svc._get_project_for_owner = AsyncMock(
            return_value={"gantt_project_id": "gp_test", "owner_user_id": "u1"}
        )
        svc._list_tasks_raw = AsyncMock(return_value=[])
        svc._next_task_order = AsyncMock(return_value=0)

        inserted: dict = {}

        async def fake_insert_many(docs):
            inserted["docs"] = docs

        mock_tasks = MagicMock()
        mock_tasks.insert_many = AsyncMock(side_effect=fake_insert_many)
        mock_projects = MagicMock()
        mock_projects.update_one = AsyncMock()

        with patch.object(svc, "db") as mock_db:
            mock_db.gantt_tasks = mock_tasks
            mock_db.gantt_projects = mock_projects

            created = await svc.create_tasks_from_draft(
                gantt_project_id="gp_test",
                owner_user_id="u1",
                draft_tasks=[
                    {
                        "temp_id": "t1",
                        "type": "task",
                        "title": "Foundation",
                        "start_date": "2026-03-01",
                        "end_date": "2026-03-10",
                        "dependencies": [],
                    }
                ],
                source="imported",
            )

        assert len(created) == 1
        assert created[0]["source"] == "imported"
        assert isinstance(created[0]["created_at"], str)
        assert isinstance(created[0]["updated_at"], str)
        assert created[0]["created_at"] == created[0]["updated_at"]
        mock_tasks.insert_many.assert_awaited_once()
        mock_projects.update_one.assert_awaited_once()

    def test_now_helper_returns_iso_string(self, gantt_service_module):
        from datetime import datetime

        result = gantt_service_module._now()
        assert isinstance(result, str)
        datetime.fromisoformat(result.replace("Z", "+00:00"))
