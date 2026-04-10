"""
Test Workflow Phase 4 improvements:
- Database persistence of workflow executions
- Document/Step selectors endpoint
- Workflow history endpoint
- Context enrichment (auto-fetch client email from document)
- Real email sending via Resend (may be mocked if key not configured)
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestWorkflowSelectors:
    """Test /api/workflows/selectors endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup_session(self):
        """Setup authenticated session"""
        self.session = requests.Session()
        # Login as demo agent
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "demo.agent@upgradeflow.com",
            "password": "demo123"
        })
        if login_resp.status_code != 200:
            pytest.skip("Could not login as demo agent")
        yield
        self.session.close()
    
    def test_get_document_selectors(self):
        """GET /api/workflows/selectors?selector_type=document returns documents"""
        resp = self.session.get(f"{BASE_URL}/api/workflows/selectors?selector_type=document")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert "items" in data, "Response should have 'items' key"
        
        # If there are documents, validate structure
        if len(data["items"]) > 0:
            doc = data["items"][0]
            assert "document_id" in doc, "Document should have document_id"
            assert "type" in doc, "Document should have type"
            # title may be optional but should be present
            print(f"Found {len(data['items'])} documents for selector")
        else:
            print("No documents found - may need to seed data first")
    
    def test_get_timeline_step_selectors(self):
        """GET /api/workflows/selectors?selector_type=timeline_step returns steps"""
        resp = self.session.get(f"{BASE_URL}/api/workflows/selectors?selector_type=timeline_step")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert "items" in data, "Response should have 'items' key"
        
        # If there are steps, validate structure
        if len(data["items"]) > 0:
            step = data["items"][0]
            assert "step_id" in step, "Step should have step_id"
            assert "name" in step, "Step should have name"
            print(f"Found {len(data['items'])} timeline steps for selector")
        else:
            print("No timeline steps found - may need to seed data first")
    
    def test_get_client_selectors(self):
        """GET /api/workflows/selectors?selector_type=client returns clients"""
        resp = self.session.get(f"{BASE_URL}/api/workflows/selectors?selector_type=client")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert "items" in data, "Response should have 'items' key"
        print(f"Found {len(data['items'])} clients for selector")
    
    def test_invalid_selector_type_returns_400(self):
        """Invalid selector_type should return 400"""
        resp = self.session.get(f"{BASE_URL}/api/workflows/selectors?selector_type=invalid")
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"


class TestWorkflowHistory:
    """Test /api/workflows/history endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup_session(self):
        """Setup authenticated session"""
        self.session = requests.Session()
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "demo.agent@upgradeflow.com",
            "password": "demo123"
        })
        if login_resp.status_code != 200:
            pytest.skip("Could not login as demo agent")
        yield
        self.session.close()
    
    def test_get_workflow_history(self):
        """GET /api/workflows/history returns persisted executions"""
        resp = self.session.get(f"{BASE_URL}/api/workflows/history")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert "executions" in data, "Response should have 'executions' key"
        assert isinstance(data["executions"], list), "executions should be a list"
        
        print(f"Found {len(data['executions'])} workflow executions in history")
        
        # If there are executions, validate structure
        if len(data["executions"]) > 0:
            exec_summary = data["executions"][0]
            assert "execution_id" in exec_summary
            assert "template_id" in exec_summary
            assert "status" in exec_summary
            assert "progress" in exec_summary


class TestWorkflowTemplatesWithUISelectors:
    """Test templates have ui_selectors field"""
    
    @pytest.fixture(autouse=True)
    def setup_session(self):
        """Setup authenticated session"""
        self.session = requests.Session()
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "demo.agent@upgradeflow.com",
            "password": "demo123"
        })
        if login_resp.status_code != 200:
            pytest.skip("Could not login as demo agent")
        yield
        self.session.close()
    
    def test_templates_have_ui_selectors_field(self):
        """All templates should have ui_selectors field"""
        resp = self.session.get(f"{BASE_URL}/api/workflows/templates")
        assert resp.status_code == 200
        
        data = resp.json()
        templates = data.get("templates", [])
        
        for template in templates:
            assert "ui_selectors" in template, f"Template {template['template_id']} missing ui_selectors"
            assert isinstance(template["ui_selectors"], list), "ui_selectors should be a list"
    
    def test_invoice_paid_processing_has_document_selector(self):
        """invoice_paid_processing template should have document ui_selector"""
        resp = self.session.get(f"{BASE_URL}/api/workflows/templates/invoice_paid_processing")
        assert resp.status_code == 200
        
        # Check template details - ui_selectors may not be in detail view, check templates list
        resp_list = self.session.get(f"{BASE_URL}/api/workflows/templates")
        data = resp_list.json()
        
        template = next((t for t in data["templates"] if t["template_id"] == "invoice_paid_processing"), None)
        assert template is not None, "invoice_paid_processing template should exist"
        assert "document" in template.get("ui_selectors", []), "Should have document ui_selector"
    
    def test_milestone_completion_has_timeline_step_selector(self):
        """milestone_completion template should have timeline_step ui_selector"""
        resp = self.session.get(f"{BASE_URL}/api/workflows/templates")
        assert resp.status_code == 200
        
        data = resp.json()
        template = next((t for t in data["templates"] if t["template_id"] == "milestone_completion"), None)
        assert template is not None, "milestone_completion template should exist"
        assert "timeline_step" in template.get("ui_selectors", []), "Should have timeline_step ui_selector"


class TestWorkflowExecutionPersistence:
    """Test that workflow executions are persisted in MongoDB"""
    
    @pytest.fixture(autouse=True)
    def setup_session(self):
        """Setup authenticated session"""
        self.session = requests.Session()
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "demo.agent@upgradeflow.com",
            "password": "demo123"
        })
        if login_resp.status_code != 200:
            pytest.skip("Could not login as demo agent")
        
        # Get a project for testing
        proj_resp = self.session.get(f"{BASE_URL}/api/projects")
        if proj_resp.status_code == 200:
            projects_data = proj_resp.json()
            # API may return list directly or wrapped in "projects" key
            if isinstance(projects_data, list):
                projects = projects_data
            else:
                projects = projects_data.get("projects", [])
            self.project_id = projects[0]["project_id"] if projects else None
        else:
            self.project_id = None
        
        yield
        self.session.close()
    
    def test_execute_workflow_and_verify_in_history(self):
        """Execute a workflow and verify it appears in history"""
        if not self.project_id:
            pytest.skip("No project available for testing")
        
        # Execute new_client_onboarding workflow
        context = {
            "project_id": self.project_id,
            "client_name": f"TEST_Phase4_Client_{int(time.time())}",
            "client_email": "test.phase4@example.com"
        }
        
        exec_resp = self.session.post(f"{BASE_URL}/api/workflows/execute", json={
            "template_id": "new_client_onboarding",
            "context": context,
            "mode": "automatic"
        })
        
        assert exec_resp.status_code == 200, f"Workflow execution failed: {exec_resp.text}"
        exec_data = exec_resp.json()
        
        assert exec_data.get("success") or exec_data.get("execution", {}).get("status") in ["completed", "in_progress"]
        execution_id = exec_data.get("execution", {}).get("execution_id")
        assert execution_id, "Execution should have an ID"
        
        # Verify it appears in history
        history_resp = self.session.get(f"{BASE_URL}/api/workflows/history")
        assert history_resp.status_code == 200
        
        history = history_resp.json().get("executions", [])
        matching = [e for e in history if e.get("execution_id") == execution_id]
        assert len(matching) > 0, f"Execution {execution_id} should appear in history"
        
        print(f"Verified workflow execution {execution_id} persisted in database")
    
    def test_get_specific_execution(self):
        """Get a specific execution by ID"""
        if not self.project_id:
            pytest.skip("No project available for testing")
        
        # Execute a workflow first
        context = {
            "project_id": self.project_id,
            "client_name": f"TEST_ExecGet_{int(time.time())}",
            "client_email": "test.exec@example.com"
        }
        
        exec_resp = self.session.post(f"{BASE_URL}/api/workflows/execute", json={
            "template_id": "new_client_onboarding",
            "context": context,
            "mode": "automatic"
        })
        
        if exec_resp.status_code != 200:
            pytest.skip("Could not execute workflow")
        
        execution_id = exec_resp.json().get("execution", {}).get("execution_id")
        
        # Get the specific execution
        get_resp = self.session.get(f"{BASE_URL}/api/workflows/executions/{execution_id}")
        assert get_resp.status_code == 200, f"Failed to get execution: {get_resp.text}"
        
        data = get_resp.json()
        assert data.get("execution_id") == execution_id
        assert data.get("template_id") == "new_client_onboarding"


class TestContextEnrichment:
    """Test that execute_workflow enriches context with document/client details"""
    
    @pytest.fixture(autouse=True)
    def setup_session(self):
        """Setup authenticated session"""
        self.session = requests.Session()
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "demo.agent@upgradeflow.com",
            "password": "demo123"
        })
        if login_resp.status_code != 200:
            pytest.skip("Could not login as demo agent")
        yield
        self.session.close()
    
    def test_invoice_paid_with_document_id_fetches_client_email(self):
        """When executing invoice_paid_processing with document_id, client email should be auto-fetched"""
        # Get a document first
        selectors_resp = self.session.get(f"{BASE_URL}/api/workflows/selectors?selector_type=document")
        if selectors_resp.status_code != 200:
            pytest.skip("Could not get document selectors")
        
        documents = selectors_resp.json().get("items", [])
        if not documents:
            pytest.skip("No documents available for testing")
        
        # Find an invoice with a client
        test_doc = documents[0]
        document_id = test_doc.get("document_id")
        
        # Execute invoice_paid_processing - the workflow should auto-enrich with client details
        exec_resp = self.session.post(f"{BASE_URL}/api/workflows/execute", json={
            "template_id": "invoice_paid_processing",
            "context": {"document_id": document_id},
            "mode": "automatic"
        })
        
        assert exec_resp.status_code == 200, f"Workflow failed: {exec_resp.text}"
        result = exec_resp.json()
        
        # The workflow should complete (or fail gracefully if email not configured)
        status = result.get("execution", {}).get("status")
        assert status in ["completed", "failed"], f"Unexpected status: {status}"
        
        # If failed, it should be because of email not because of missing client data
        if status == "failed":
            error = result.get("execution", {}).get("error", "")
            assert "client_email" not in error.lower(), "Should have auto-fetched client_email"
        
        print(f"Invoice paid processing completed with status: {status}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
