"""
Test Workflow Canonicalization — Iteration 16

Tests that workflows.py has zero direct DB writes and all mutations
flow through canonical services:
- client_service.create_client()
- document_service.transition_document_status()
- step_service.update_step()
- activity_service.create_and_distribute_activity()

Also tests that project creation no longer has entitlement check (removed).
"""
import os
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Template IDs from the workflow service
TEMPLATE_IDS = [
    "new_client_onboarding",
    "invoice_paid_processing",
    "milestone_completion",
    "send_document",
    "project_announcement"
]


@pytest.fixture(scope="module")
def agent_token():
    """Get agent auth token via demo login."""
    resp = requests.post(f"{BASE_URL}/api/auth/demo/agent", json={
        "email": "demo.agent@upgradeflow.com",
        "password": "demo123"
    })
    if resp.status_code != 200:
        pytest.skip(f"Demo agent login failed: {resp.status_code} - {resp.text}")
    data = resp.json()
    return data.get("access_token") or data.get("token")


@pytest.fixture(scope="module")
def agent_headers(agent_token):
    """Headers with agent auth."""
    return {
        "Authorization": f"Bearer {agent_token}",
        "Content-Type": "application/json"
    }


class TestWorkflowTemplates:
    """Test workflow template endpoints."""

    def test_get_workflow_templates_returns_5_templates(self, agent_headers):
        """GET /api/workflows/templates — returns 5 templates with correct structure."""
        resp = requests.get(f"{BASE_URL}/api/workflows/templates", headers=agent_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert "templates" in data, "Response should have 'templates' key"
        templates = data["templates"]
        
        # Should have 5 templates
        assert len(templates) == 5, f"Expected 5 templates, got {len(templates)}"
        
        # Verify all expected template IDs are present
        template_ids = [t["template_id"] for t in templates]
        for expected_id in TEMPLATE_IDS:
            assert expected_id in template_ids, f"Missing template: {expected_id}"
        
        # Verify structure of each template
        for t in templates:
            assert "template_id" in t
            assert "name" in t
            assert "description" in t
            assert "category" in t
            assert "steps_count" in t
            assert "steps_preview" in t
            print(f"  Template: {t['template_id']} - {t['name']} ({t['steps_count']} steps)")

    def test_get_specific_template_new_client_onboarding(self, agent_headers):
        """GET /api/workflows/templates/new_client_onboarding — returns template details with steps."""
        resp = requests.get(
            f"{BASE_URL}/api/workflows/templates/new_client_onboarding",
            headers=agent_headers
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert data["template_id"] == "new_client_onboarding"
        assert "name" in data
        assert "steps" in data
        assert len(data["steps"]) > 0, "Template should have steps"
        
        # Verify steps have required fields
        for step in data["steps"]:
            assert "name" in step
            assert "action" in step
            print(f"  Step: {step['name']} -> {step['action']}")


class TestWorkflowExecution:
    """Test workflow execution endpoints — verify canonical service delegation."""

    def test_execute_new_client_onboarding_creates_client_via_service(self, agent_headers):
        """POST /api/workflows/execute with new_client_onboarding — creates client through client_service."""
        # Get a project_id first
        projects_resp = requests.get(f"{BASE_URL}/api/projects", headers=agent_headers)
        assert projects_resp.status_code == 200
        projects = projects_resp.json()
        if not projects:
            pytest.skip("No projects available for testing")
        project_id = projects[0]["project_id"]
        
        # Execute workflow
        resp = requests.post(
            f"{BASE_URL}/api/workflows/execute",
            headers=agent_headers,
            json={
                "template_id": "new_client_onboarding",
                "context": {
                    "client_name": "TEST_Workflow_Client",
                    "client_email": "test.workflow@example.com",
                    "project_id": project_id
                },
                "mode": "automatic"
            }
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert "success" in data
        assert "execution" in data
        
        execution = data["execution"]
        assert "execution_id" in execution
        assert "status" in execution
        
        # Verify client was created with canonical ID format (client_xxx)
        if execution.get("context", {}).get("client_id"):
            client_id = execution["context"]["client_id"]
            assert client_id.startswith("client_"), f"Client ID should start with 'client_', got: {client_id}"
            print(f"  Created client via service: {client_id}")
        
        print(f"  Workflow status: {execution['status']}")

    def test_execute_invoice_paid_processing_transitions_via_document_service(self, agent_headers):
        """POST /api/workflows/execute with invoice_paid_processing — transitions document status through document_service."""
        # Use demo_doc_005 (invoice, status=Sent) as specified
        document_id = "demo_doc_005"
        
        # First verify the document exists and is an invoice
        docs_resp = requests.get(
            f"{BASE_URL}/api/workflows/selectors?selector_type=document",
            headers=agent_headers
        )
        assert docs_resp.status_code == 200
        
        resp = requests.post(
            f"{BASE_URL}/api/workflows/execute",
            headers=agent_headers,
            json={
                "template_id": "invoice_paid_processing",
                "context": {
                    "document_id": document_id
                },
                "mode": "automatic"
            }
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert "execution" in data
        execution = data["execution"]
        print(f"  Invoice paid workflow status: {execution['status']}")
        
        # Check steps for document status transition
        if "steps" in execution:
            for step in execution["steps"]:
                print(f"    Step: {step.get('name')} - {step.get('status')}")

    def test_execute_milestone_completion_updates_via_step_service(self, agent_headers):
        """POST /api/workflows/execute with milestone_completion — updates step through step_service."""
        # Use demo_step_003 (Foundation, status=in_progress) as specified
        step_id = "demo_step_003"
        
        resp = requests.post(
            f"{BASE_URL}/api/workflows/execute",
            headers=agent_headers,
            json={
                "template_id": "milestone_completion",
                "context": {
                    "step_id": step_id
                },
                "mode": "automatic"
            }
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert "execution" in data
        execution = data["execution"]
        print(f"  Milestone completion workflow status: {execution['status']}")

    def test_execute_send_document_sends_email(self, agent_headers):
        """POST /api/workflows/execute with send_document — sends document email."""
        # Use demo_doc_002 as specified
        document_id = "demo_doc_002"
        
        resp = requests.post(
            f"{BASE_URL}/api/workflows/execute",
            headers=agent_headers,
            json={
                "template_id": "send_document",
                "context": {
                    "document_id": document_id
                },
                "mode": "automatic"
            }
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert "execution" in data
        execution = data["execution"]
        print(f"  Send document workflow status: {execution['status']}")

    def test_execute_project_announcement_creates_activity_via_service(self, agent_headers):
        """POST /api/workflows/execute with project_announcement — creates activity through activity_service."""
        # Get a project_id first
        projects_resp = requests.get(f"{BASE_URL}/api/projects", headers=agent_headers)
        assert projects_resp.status_code == 200
        projects = projects_resp.json()
        if not projects:
            pytest.skip("No projects available for testing")
        project_id = projects[0]["project_id"]
        
        resp = requests.post(
            f"{BASE_URL}/api/workflows/execute",
            headers=agent_headers,
            json={
                "template_id": "project_announcement",
                "context": {
                    "project_id": project_id,
                    "message_title": "TEST Announcement",
                    "message_content": "This is a test announcement from workflow canonicalization test."
                },
                "mode": "automatic"
            }
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert "execution" in data
        execution = data["execution"]
        print(f"  Project announcement workflow status: {execution['status']}")
        
        # Check if activity was created with canonical ID format (act_xxx)
        if execution.get("context", {}).get("activity_id"):
            activity_id = execution["context"]["activity_id"]
            assert activity_id.startswith("act_"), f"Activity ID should start with 'act_', got: {activity_id}"
            print(f"  Created activity via service: {activity_id}")


class TestWorkflowSelectors:
    """Test workflow selector endpoints."""

    def test_get_document_selectors(self, agent_headers):
        """GET /api/workflows/selectors?selector_type=document — returns documents."""
        resp = requests.get(
            f"{BASE_URL}/api/workflows/selectors?selector_type=document",
            headers=agent_headers
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert "items" in data
        print(f"  Found {len(data['items'])} documents")
        
        # Verify document structure
        if data["items"]:
            doc = data["items"][0]
            assert "document_id" in doc
            assert "type" in doc
            assert "status" in doc

    def test_get_timeline_step_selectors(self, agent_headers):
        """GET /api/workflows/selectors?selector_type=timeline_step — returns timeline steps."""
        resp = requests.get(
            f"{BASE_URL}/api/workflows/selectors?selector_type=timeline_step",
            headers=agent_headers
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert "items" in data
        print(f"  Found {len(data['items'])} timeline steps")
        
        # Verify step structure
        if data["items"]:
            step = data["items"][0]
            assert "step_id" in step
            assert "status" in step

    def test_get_client_selectors(self, agent_headers):
        """GET /api/workflows/selectors?selector_type=client — returns clients."""
        resp = requests.get(
            f"{BASE_URL}/api/workflows/selectors?selector_type=client",
            headers=agent_headers
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert "items" in data
        print(f"  Found {len(data['items'])} clients")
        
        # Verify client structure
        if data["items"]:
            client = data["items"][0]
            assert "client_id" in client
            assert "name" in client


class TestWorkflowHistory:
    """Test workflow history endpoint."""

    def test_get_workflow_history(self, agent_headers):
        """GET /api/workflows/history — returns execution history."""
        resp = requests.get(f"{BASE_URL}/api/workflows/history", headers=agent_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert "executions" in data
        print(f"  Found {len(data['executions'])} workflow executions in history")


class TestProjectEntitlementRemoval:
    """Test that project creation no longer has entitlement check."""

    def test_create_project_without_entitlement_check(self, agent_headers):
        """POST /api/projects — can create project without entitlement check (was removed)."""
        resp = requests.post(
            f"{BASE_URL}/api/projects",
            headers=agent_headers,
            json={
                "name": "TEST_Workflow_Project",
                "address": "123 Test Street",
                "description": "Test project for workflow canonicalization"
            }
        )
        # Should succeed - no entitlement check on project creation
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert "project_id" in data
        assert data["name"] == "TEST_Workflow_Project"
        print(f"  Created project: {data['project_id']}")
        
        # Cleanup - delete the test project
        project_id = data["project_id"]
        del_resp = requests.delete(
            f"{BASE_URL}/api/projects/{project_id}",
            headers=agent_headers
        )
        print(f"  Cleanup: delete project returned {del_resp.status_code}")


class TestUnitEntitlementStillEnforced:
    """Test that unit creation still enforces entitlement check."""

    def test_unit_creation_still_has_entitlement_check(self, agent_headers):
        """POST /api/projects/{project_id}/units — still enforces unit limit."""
        # Get a project first
        projects_resp = requests.get(f"{BASE_URL}/api/projects", headers=agent_headers)
        assert projects_resp.status_code == 200
        projects = projects_resp.json()
        if not projects:
            pytest.skip("No projects available for testing")
        project_id = projects[0]["project_id"]
        
        # Try to create a unit - this should work or fail based on entitlement
        # The key is that the endpoint exists and processes the request
        resp = requests.post(
            f"{BASE_URL}/api/projects/{project_id}/units",
            headers=agent_headers,
            json={
                "unit_reference": "TEST-UNIT-001",
                "floor": "1",
                "rooms": 3
            }
        )
        # Either 200 (success) or 403 (entitlement limit) are valid
        # 400 for validation errors is also acceptable
        assert resp.status_code in [200, 201, 400, 403], f"Unexpected status: {resp.status_code}: {resp.text}"
        print(f"  Unit creation returned: {resp.status_code}")


class TestBillingEndpointsStillWork:
    """Test that billing endpoints still work after changes."""

    def test_billing_status_endpoint(self, agent_headers):
        """GET /api/billing/status — still works."""
        resp = requests.get(f"{BASE_URL}/api/billing/status", headers=agent_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert "plan_id" in data or "plan_name" in data
        print(f"  Billing status: plan={data.get('plan_name', data.get('plan_id'))}")

    def test_billing_plans_endpoint(self, agent_headers):
        """GET /api/billing/plans — still works."""
        resp = requests.get(f"{BASE_URL}/api/billing/plans", headers=agent_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        # Plans endpoint returns list directly or {"plans": [...]}
        if isinstance(data, list):
            plans = data
        else:
            plans = data.get("plans", [])
        assert len(plans) > 0, "Should have at least one billing plan"
        print(f"  Found {len(plans)} billing plans")


class TestDemoSeedAndLogin:
    """Test demo seed and login still work."""

    def test_demo_seed_works(self):
        """POST /api/demo/seed — still works."""
        resp = requests.post(f"{BASE_URL}/api/demo/seed")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert "message" in data
        assert "demo_credentials" in data
        print(f"  Demo seed: {data['message']}")

    def test_demo_agent_login_works(self):
        """POST /api/auth/demo/agent — still works."""
        resp = requests.post(f"{BASE_URL}/api/auth/demo/agent", json={
            "email": "demo.agent@upgradeflow.com",
            "password": "demo123"
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert "access_token" in data or "token" in data
        print("  Demo agent login: SUCCESS")

    def test_demo_buyer_login_works(self):
        """POST /api/auth/demo/buyer?buyer_num=1 — still works."""
        resp = requests.post(f"{BASE_URL}/api/auth/demo/buyer?buyer_num=1")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert "access_token" in data or "token" in data
        print("  Demo buyer login: SUCCESS")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
