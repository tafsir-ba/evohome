"""
Gantt Chart Phase 3 — E2E integration tests (require live backend + MongoDB).

Run explicitly: pytest -m e2e backend/tests/test_gantt_phase3.py
"""
import io
import os
from datetime import datetime, timedelta, timezone

import pytest
import requests

pytestmark = pytest.mark.e2e

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")

TEST_EMAIL = os.environ.get("TEST_E2E_AGENT_EMAIL", "e2e@evohome-test.com")
TEST_PASSWORD = os.environ.get("TEST_E2E_AGENT_PASSWORD", "Test2026!")


@pytest.fixture(scope="module")
def auth_token():
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
    )
    if response.status_code != 200:
        pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")
    token = response.json().get("token")
    if not token:
        pytest.skip("No token in login response")
    return token


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    return {
        "Authorization": f"Bearer {auth_token}",
    }


@pytest.fixture
def gantt_project(auth_headers):
    response = requests.post(
        f"{BASE_URL}/api/gantt/projects",
        headers={**auth_headers, "Content-Type": "application/json"},
        json={"title": "TEST_Gantt_Phase3", "description": "Phase 3 test project"},
    )
    assert response.status_code == 200, response.text
    project = response.json()
    yield project
    requests.delete(
        f"{BASE_URL}/api/gantt/projects/{project['gantt_project_id']}",
        headers={**auth_headers, "Content-Type": "application/json"},
    )


def _upload_csv(auth_headers, project_id, csv_content, filename="milestones.csv"):
    return requests.post(
        f"{BASE_URL}/api/gantt/upload",
        headers=auth_headers,
        data={"gantt_project_id": project_id},
        files={"file": (filename, csv_content, "text/csv")},
    )


def _extract_draft(auth_headers, project_id, file_id):
    return requests.post(
        f"{BASE_URL}/api/gantt/extract",
        headers={**auth_headers, "Content-Type": "application/json"},
        json={"file_id": file_id, "gantt_project_id": project_id},
    )


SAMPLE_CSV = b"""title,phase,start_date,end_date,type
Foundation,Phase 1,2026-03-01,2026-03-10,task
Framing,Phase 1,2026-03-11,2026-03-25,task
Inspection,Phase 2,2026-03-26,2026-03-26,milestone
"""

AMBIGUOUS_CSV = b"""title,start_date,end_date
Task A,Spring 2026,Q4 2027
Task B,not-a-date,2026-05-01
"""


class TestGanttPhase3:
    def test_19_extract_creates_draft_only(self, auth_headers, gantt_project):
        project_id = gantt_project["gantt_project_id"]

        upload_resp = _upload_csv(auth_headers, project_id, SAMPLE_CSV)
        assert upload_resp.status_code == 200, upload_resp.text
        file_id = upload_resp.json()["file_id"]

        extract_resp = _extract_draft(auth_headers, project_id, file_id)
        assert extract_resp.status_code == 200, extract_resp.text
        draft = extract_resp.json()
        assert draft["draft_id"].startswith("gd_")
        assert draft["status"] == "pending"
        assert len(draft["tasks"]) >= 2
        assert draft["review_message"]

        tasks_resp = requests.get(
            f"{BASE_URL}/api/gantt/projects/{project_id}/tasks",
            headers={**auth_headers, "Content-Type": "application/json"},
        )
        assert tasks_resp.status_code == 200
        assert tasks_resp.json() == []

        requests.post(
            f"{BASE_URL}/api/gantt/drafts/{draft['draft_id']}/discard",
            headers={**auth_headers, "Content-Type": "application/json"},
        )

    def test_20_confirm_remaps_temp_ids_and_dependencies(self, auth_headers, gantt_project):
        project_id = gantt_project["gantt_project_id"]

        upload_resp = _upload_csv(auth_headers, project_id, SAMPLE_CSV)
        file_id = upload_resp.json()["file_id"]
        draft = _extract_draft(auth_headers, project_id, file_id).json()

        # Add dependency between draft tasks using temp_ids
        tasks = draft["tasks"]
        assert len(tasks) >= 2
        tasks[1]["dependencies"] = [
            {"temp_task_id": tasks[0]["temp_id"], "type": "finish_to_start"}
        ]
        patch_resp = requests.patch(
            f"{BASE_URL}/api/gantt/drafts/{draft['draft_id']}",
            headers={**auth_headers, "Content-Type": "application/json"},
            json={"tasks": tasks},
        )
        assert patch_resp.status_code == 200, patch_resp.text

        confirm_resp = requests.post(
            f"{BASE_URL}/api/gantt/drafts/{draft['draft_id']}/confirm",
            headers={**auth_headers, "Content-Type": "application/json"},
        )
        assert confirm_resp.status_code == 200, confirm_resp.text
        result = confirm_resp.json()
        assert result["created_task_count"] >= 2
        created = result["tasks"]
        assert all(t["task_id"].startswith("gt_") for t in created)
        assert all(t["source"] == "imported" for t in created)

        successor = next(t for t in created if t["title"] == tasks[1]["title"])
        predecessor = next(t for t in created if t["title"] == tasks[0]["title"])
        assert successor["dependencies"] == [
            {"task_id": predecessor["task_id"], "type": "finish_to_start"}
        ]

    def test_21_discard_does_not_create_tasks(self, auth_headers, gantt_project):
        project_id = gantt_project["gantt_project_id"]
        upload_resp = _upload_csv(auth_headers, project_id, SAMPLE_CSV)
        draft = _extract_draft(
            auth_headers, project_id, upload_resp.json()["file_id"]
        ).json()

        discard_resp = requests.post(
            f"{BASE_URL}/api/gantt/drafts/{draft['draft_id']}/discard",
            headers={**auth_headers, "Content-Type": "application/json"},
        )
        assert discard_resp.status_code == 200
        assert discard_resp.json()["status"] == "discarded"

        tasks_resp = requests.get(
            f"{BASE_URL}/api/gantt/projects/{project_id}/tasks",
            headers={**auth_headers, "Content-Type": "application/json"},
        )
        assert tasks_resp.json() == []

    def test_22_expired_draft_cannot_confirm(self, auth_headers, gantt_project):
        try:
            from pymongo import MongoClient
        except ImportError:
            pytest.skip("pymongo not installed")

        mongo_url = (os.environ.get("MONGO_URL") or "").strip() or "mongodb://127.0.0.1:27017"
        db_name = os.environ.get("DB_NAME", "evohome_pytest")

        project_id = gantt_project["gantt_project_id"]
        upload_resp = _upload_csv(auth_headers, project_id, SAMPLE_CSV)
        draft = _extract_draft(
            auth_headers, project_id, upload_resp.json()["file_id"]
        ).json()

        client = MongoClient(mongo_url, serverSelectionTimeoutMS=3000)
        db = client[db_name]
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        db.gantt_extraction_drafts.update_one(
            {"draft_id": draft["draft_id"]},
            {"$set": {"expires_at": past}},
        )
        client.close()

        confirm_resp = requests.post(
            f"{BASE_URL}/api/gantt/drafts/{draft['draft_id']}/confirm",
            headers={**auth_headers, "Content-Type": "application/json"},
        )
        assert confirm_resp.status_code == 400
        assert "expired" in confirm_resp.json().get("detail", "").lower()

    def test_23_low_confidence_fields_flagged(self, auth_headers, gantt_project):
        project_id = gantt_project["gantt_project_id"]
        upload_resp = _upload_csv(auth_headers, project_id, AMBIGUOUS_CSV)
        draft = _extract_draft(
            auth_headers, project_id, upload_resp.json()["file_id"]
        ).json()

        assert draft["tasks"]
        low_confidence_found = False
        for task in draft["tasks"]:
            confidence = task.get("field_confidence") or {}
            warnings = task.get("warnings") or []
            if any(v < 0.6 for v in confidence.values() if isinstance(v, (int, float))):
                low_confidence_found = True
            if any("Low confidence" in w or "Could not parse" in w for w in warnings):
                low_confidence_found = True
        assert low_confidence_found, "Expected low-confidence flags in draft response"

        requests.post(
            f"{BASE_URL}/api/gantt/drafts/{draft['draft_id']}/discard",
            headers={**auth_headers, "Content-Type": "application/json"},
        )

    def test_24_upload_rejects_unsupported_extension(self, auth_headers, gantt_project):
        project_id = gantt_project["gantt_project_id"]
        response = requests.post(
            f"{BASE_URL}/api/gantt/upload",
            headers=auth_headers,
            data={"gantt_project_id": project_id},
            files={"file": ("plan.xlsx", b"fake", "application/octet-stream")},
        )
        assert response.status_code == 400
        assert "unsupported" in response.json().get("detail", "").lower()

    def test_25_upload_rejects_oversize_file(self, auth_headers, gantt_project):
        project_id = gantt_project["gantt_project_id"]
        oversized = b"x" * (15 * 1024 * 1024 + 1)
        response = requests.post(
            f"{BASE_URL}/api/gantt/upload",
            headers=auth_headers,
            data={"gantt_project_id": project_id},
            files={"file": ("big.csv", oversized, "text/csv")},
        )
        assert response.status_code == 400
        assert "size" in response.json().get("detail", "").lower()
