"""
Gantt Chart Phase 2 — E2E integration tests (require live backend + MongoDB).

Run explicitly: pytest -m e2e backend/tests/test_gantt_phase2.py
"""
import csv
import io
import os

import pytest
import requests

pytestmark = pytest.mark.e2e

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")

TEST_EMAIL = os.environ.get("TEST_E2E_AGENT_EMAIL", "e2e@evohome-test.com")
TEST_PASSWORD = os.environ.get("TEST_E2E_AGENT_PASSWORD", "Test2026!")


def _backend_available() -> bool:
    try:
        response = requests.get(f"{BASE_URL}/api/health", timeout=3)
        return response.status_code == 200
    except requests.RequestException:
        return False


@pytest.fixture(scope="module", autouse=True)
def require_backend():
    if not _backend_available():
        pytest.skip(f"Backend not available at {BASE_URL}")


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
        "Content-Type": "application/json",
    }


@pytest.fixture(scope="module")
def demo_auth_headers():
    response = requests.post(f"{BASE_URL}/api/auth/demo/agent")
    if response.status_code != 200:
        pytest.skip(f"Demo auth failed: {response.status_code}")
    token = response.json().get("token")
    if not token:
        pytest.skip("No demo token")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


@pytest.fixture
def gantt_project(auth_headers):
    response = requests.post(
        f"{BASE_URL}/api/gantt/projects",
        headers=auth_headers,
        json={"title": "TEST_Gantt_Phase2", "description": "Phase 2 test project"},
    )
    assert response.status_code == 200, response.text
    project = response.json()
    yield project
    requests.delete(
        f"{BASE_URL}/api/gantt/projects/{project['gantt_project_id']}",
        headers=auth_headers,
    )


class TestGanttPhase2:
    def test_01_create_project(self, auth_headers):
        response = requests.post(
            f"{BASE_URL}/api/gantt/projects",
            headers=auth_headers,
            json={"title": "TEST_Create_Project"},
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["title"] == "TEST_Create_Project"
        assert data["gantt_project_id"].startswith("gp_")
        assert data["owner_user_id"]
        requests.delete(
            f"{BASE_URL}/api/gantt/projects/{data['gantt_project_id']}",
            headers=auth_headers,
        )

    def test_02_unauthenticated_401(self):
        response = requests.get(f"{BASE_URL}/api/gantt/projects")
        assert response.status_code == 401

    def test_03_cross_user_access_403(self, auth_headers, demo_auth_headers):
        create_resp = requests.post(
            f"{BASE_URL}/api/gantt/projects",
            headers=auth_headers,
            json={"title": "TEST_Cross_User"},
        )
        assert create_resp.status_code == 200
        project_id = create_resp.json()["gantt_project_id"]

        response = requests.get(
            f"{BASE_URL}/api/gantt/projects/{project_id}",
            headers=demo_auth_headers,
        )
        assert response.status_code == 403

        requests.delete(
            f"{BASE_URL}/api/gantt/projects/{project_id}",
            headers=auth_headers,
        )

    def test_04_create_task_duration_computed(self, auth_headers, gantt_project):
        project_id = gantt_project["gantt_project_id"]
        response = requests.post(
            f"{BASE_URL}/api/gantt/projects/{project_id}/tasks",
            headers=auth_headers,
            json={
                "title": "Foundation Work",
                "type": "task",
                "start_date": "2026-02-01",
                "end_date": "2026-02-05",
            },
        )
        assert response.status_code == 200, response.text
        task = response.json()
        assert task["duration_days"] == 4
        assert task["source"] == "manual"

    def test_05_reject_end_before_start(self, auth_headers, gantt_project):
        project_id = gantt_project["gantt_project_id"]
        response = requests.post(
            f"{BASE_URL}/api/gantt/projects/{project_id}/tasks",
            headers=auth_headers,
            json={
                "title": "Bad Dates",
                "start_date": "2026-03-10",
                "end_date": "2026-03-01",
            },
        )
        assert response.status_code == 400

    def test_06_milestone_duration_zero(self, auth_headers, gantt_project):
        project_id = gantt_project["gantt_project_id"]
        response = requests.post(
            f"{BASE_URL}/api/gantt/projects/{project_id}/tasks",
            headers=auth_headers,
            json={
                "title": "Kickoff",
                "type": "milestone",
                "start_date": "2026-04-01",
            },
        )
        assert response.status_code == 200, response.text
        task = response.json()
        assert task["duration_days"] == 0
        assert task["end_date"] == "2026-04-01"

    def test_07_reject_milestone_differing_dates(self, auth_headers, gantt_project):
        project_id = gantt_project["gantt_project_id"]
        response = requests.post(
            f"{BASE_URL}/api/gantt/projects/{project_id}/tasks",
            headers=auth_headers,
            json={
                "title": "Bad Milestone",
                "type": "milestone",
                "start_date": "2026-04-01",
                "end_date": "2026-04-02",
            },
        )
        assert response.status_code == 400

    def test_08_reject_end_only_task(self, auth_headers, gantt_project):
        project_id = gantt_project["gantt_project_id"]
        response = requests.post(
            f"{BASE_URL}/api/gantt/projects/{project_id}/tasks",
            headers=auth_headers,
            json={"title": "End Only", "end_date": "2026-05-01"},
        )
        assert response.status_code == 400

    def test_09_dependency_must_exist(self, auth_headers, gantt_project):
        project_id = gantt_project["gantt_project_id"]
        response = requests.post(
            f"{BASE_URL}/api/gantt/projects/{project_id}/tasks",
            headers=auth_headers,
            json={
                "title": "Depends on ghost",
                "dependencies": [{"task_id": "gt_nonexistent", "type": "finish_to_start"}],
            },
        )
        assert response.status_code == 400

    def test_10_reject_self_dependency(self, auth_headers, gantt_project):
        project_id = gantt_project["gantt_project_id"]
        create_resp = requests.post(
            f"{BASE_URL}/api/gantt/projects/{project_id}/tasks",
            headers=auth_headers,
            json={"title": "Self Ref"},
        )
        assert create_resp.status_code == 200
        task_id = create_resp.json()["task_id"]

        response = requests.patch(
            f"{BASE_URL}/api/gantt/projects/{project_id}/tasks/{task_id}",
            headers=auth_headers,
            json={"dependencies": [{"task_id": task_id, "type": "finish_to_start"}]},
        )
        assert response.status_code == 400

    def test_11_reject_circular_dependencies(self, auth_headers, gantt_project):
        project_id = gantt_project["gantt_project_id"]

        t1 = requests.post(
            f"{BASE_URL}/api/gantt/projects/{project_id}/tasks",
            headers=auth_headers,
            json={"title": "Task 1"},
        ).json()
        t2 = requests.post(
            f"{BASE_URL}/api/gantt/projects/{project_id}/tasks",
            headers=auth_headers,
            json={
                "title": "Task 2",
                "dependencies": [{"task_id": t1["task_id"], "type": "finish_to_start"}],
            },
        ).json()

        response = requests.patch(
            f"{BASE_URL}/api/gantt/projects/{project_id}/tasks/{t1['task_id']}",
            headers=auth_headers,
            json={"dependencies": [{"task_id": t2["task_id"], "type": "finish_to_start"}]},
        )
        assert response.status_code == 400

    def test_12_reorder_normalizes_order(self, auth_headers, gantt_project):
        project_id = gantt_project["gantt_project_id"]
        ids = []
        for title in ["A", "B", "C"]:
            resp = requests.post(
                f"{BASE_URL}/api/gantt/projects/{project_id}/tasks",
                headers=auth_headers,
                json={"title": title},
            )
            ids.append(resp.json()["task_id"])

        response = requests.post(
            f"{BASE_URL}/api/gantt/projects/{project_id}/tasks/reorder",
            headers=auth_headers,
            json={"task_ids": [ids[2], ids[0], ids[1]]},
        )
        assert response.status_code == 200, response.text
        tasks = response.json()
        assert [t["order"] for t in tasks] == [0, 1, 2]
        assert [t["task_id"] for t in tasks] == [ids[2], ids[0], ids[1]]

    def test_13_reorder_rejects_invalid_id_set(self, auth_headers, gantt_project):
        project_id = gantt_project["gantt_project_id"]
        task = requests.post(
            f"{BASE_URL}/api/gantt/projects/{project_id}/tasks",
            headers=auth_headers,
            json={"title": "Only One"},
        ).json()

        response = requests.post(
            f"{BASE_URL}/api/gantt/projects/{project_id}/tasks/reorder",
            headers=auth_headers,
            json={"task_ids": [task["task_id"], "gt_fake"]},
        )
        assert response.status_code == 400

    def test_13b_reorder_rejects_duplicate_ids(self, auth_headers, gantt_project):
        project_id = gantt_project["gantt_project_id"]
        ids = []
        for title in ["Dup A", "Dup B"]:
            resp = requests.post(
                f"{BASE_URL}/api/gantt/projects/{project_id}/tasks",
                headers=auth_headers,
                json={"title": title},
            )
            ids.append(resp.json()["task_id"])

        response = requests.post(
            f"{BASE_URL}/api/gantt/projects/{project_id}/tasks/reorder",
            headers=auth_headers,
            json={"task_ids": [ids[0], ids[0]]},
        )
        assert response.status_code == 400

    def test_14_delete_with_dependents_409(self, auth_headers, gantt_project):
        project_id = gantt_project["gantt_project_id"]
        parent = requests.post(
            f"{BASE_URL}/api/gantt/projects/{project_id}/tasks",
            headers=auth_headers,
            json={"title": "Parent"},
        ).json()
        child = requests.post(
            f"{BASE_URL}/api/gantt/projects/{project_id}/tasks",
            headers=auth_headers,
            json={
                "title": "Child",
                "dependencies": [{"task_id": parent["task_id"], "type": "finish_to_start"}],
            },
        ).json()

        response = requests.delete(
            f"{BASE_URL}/api/gantt/projects/{project_id}/tasks/{parent['task_id']}",
            headers=auth_headers,
        )
        assert response.status_code == 409
        data = response.json()
        assert "dependent_task_ids" in data
        assert child["task_id"] in data["dependent_task_ids"]
        assert "depend on it" in data["detail"]

    def test_15_delete_without_dependents_200(self, auth_headers, gantt_project):
        project_id = gantt_project["gantt_project_id"]
        task = requests.post(
            f"{BASE_URL}/api/gantt/projects/{project_id}/tasks",
            headers=auth_headers,
            json={"title": "Disposable"},
        ).json()

        response = requests.delete(
            f"{BASE_URL}/api/gantt/projects/{project_id}/tasks/{task['task_id']}",
            headers=auth_headers,
        )
        assert response.status_code == 200

    def test_16_delete_project_cascades(self, auth_headers):
        create_resp = requests.post(
            f"{BASE_URL}/api/gantt/projects",
            headers=auth_headers,
            json={"title": "Cascade Test"},
        )
        project_id = create_resp.json()["gantt_project_id"]
        requests.post(
            f"{BASE_URL}/api/gantt/projects/{project_id}/tasks",
            headers=auth_headers,
            json={"title": "Task 1"},
        )
        requests.post(
            f"{BASE_URL}/api/gantt/projects/{project_id}/tasks",
            headers=auth_headers,
            json={"title": "Task 2"},
        )

        response = requests.delete(
            f"{BASE_URL}/api/gantt/projects/{project_id}",
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["deleted_task_count"] == 2

        tasks_resp = requests.get(
            f"{BASE_URL}/api/gantt/projects/{project_id}/tasks",
            headers=auth_headers,
        )
        assert tasks_resp.status_code == 403

    def test_17_csv_export_correct(self, auth_headers, gantt_project):
        project_id = gantt_project["gantt_project_id"]
        predecessor = requests.post(
            f"{BASE_URL}/api/gantt/projects/{project_id}/tasks",
            headers=auth_headers,
            json={"title": "Predecessor"},
        ).json()
        successor = requests.post(
            f"{BASE_URL}/api/gantt/projects/{project_id}/tasks",
            headers=auth_headers,
            json={
                "title": "Export Task",
                "phase": "Phase 1",
                "start_date": "2026-06-01",
                "end_date": "2026-06-03",
                "dependencies": [
                    {"task_id": predecessor["task_id"], "type": "finish_to_start"}
                ],
            },
        ).json()
        requests.post(
            f"{BASE_URL}/api/gantt/projects/{project_id}/tasks",
            headers=auth_headers,
            json={"title": "Start Only", "start_date": "2026-07-01"},
        )

        response = requests.get(
            f"{BASE_URL}/api/gantt/projects/{project_id}/export.csv",
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert "text/csv" in response.headers.get("Content-Type", "")
        disposition = response.headers.get("Content-Disposition", "")
        assert "attachment" in disposition
        assert "TEST_Gantt_Phase2.csv" in disposition

        rows = list(csv.DictReader(io.StringIO(response.text)))
        assert list(rows[0].keys()) == [
            "order",
            "type",
            "phase",
            "title",
            "description",
            "start_date",
            "end_date",
            "duration_days",
            "status",
            "responsible_party",
            "dependencies",
            "source",
        ]

        export_row = next(row for row in rows if row["title"] == "Export Task")
        assert export_row["phase"] == "Phase 1"
        assert export_row["duration_days"] == "2"
        assert export_row["source"] == "manual"
        assert export_row["dependencies"] == predecessor["task_id"]

        start_only_row = next(row for row in rows if row["title"] == "Start Only")
        assert start_only_row["duration_days"] == ""

    def test_17b_csv_filename_sanitizes_special_characters(self, auth_headers):
        create_resp = requests.post(
            f"{BASE_URL}/api/gantt/projects",
            headers=auth_headers,
            json={"title": "My Project / Q2!"},
        )
        assert create_resp.status_code == 200
        project_id = create_resp.json()["gantt_project_id"]

        response = requests.get(
            f"{BASE_URL}/api/gantt/projects/{project_id}/export.csv",
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert 'filename="My_Project_Q2.csv"' in response.headers.get("Content-Disposition", "")

        requests.delete(
            f"{BASE_URL}/api/gantt/projects/{project_id}",
            headers=auth_headers,
        )

    def test_18_reject_unsupported_dependency_types(self, auth_headers, gantt_project):
        project_id = gantt_project["gantt_project_id"]
        dep = requests.post(
            f"{BASE_URL}/api/gantt/projects/{project_id}/tasks",
            headers=auth_headers,
            json={"title": "Predecessor"},
        ).json()

        response = requests.post(
            f"{BASE_URL}/api/gantt/projects/{project_id}/tasks",
            headers=auth_headers,
            json={
                "title": "Successor",
                "dependencies": [{"task_id": dep["task_id"], "type": "SS"}],
            },
        )
        assert response.status_code == 400
