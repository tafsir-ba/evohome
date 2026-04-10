"""
Workflow API Tests - Phase 4
Tests for multi-step workflow automation endpoints

Features tested:
- GET /api/workflows/templates - List all workflow templates
- GET /api/workflows/templates/{template_id} - Get specific template
- POST /api/workflows/execute - Execute a workflow (new_client_onboarding, invoice_paid_processing)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestWorkflowSetup:
    """Setup and authentication"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Login and get session token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "demo.agent@upgradeflow.com",
            "password": "demo123"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        return data.get("token")
    
    @pytest.fixture(scope="class")
    def auth_session(self, auth_token):
        """Create authenticated session"""
        session = requests.Session()
        session.headers.update({
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        })
        return session


class TestWorkflowTemplates(TestWorkflowSetup):
    """Test workflow template endpoints"""
    
    def test_get_workflow_templates_returns_5_templates(self, auth_session):
        """GET /api/workflows/templates should return exactly 5 templates"""
        response = auth_session.get(f"{BASE_URL}/api/workflows/templates")
        
        assert response.status_code == 200, f"Failed to get templates: {response.text}"
        data = response.json()
        
        # Should have templates array
        assert "templates" in data, "Response should contain 'templates' key"
        templates = data["templates"]
        
        # Should have exactly 5 templates
        assert len(templates) == 5, f"Expected 5 templates, got {len(templates)}"
        
        # Verify expected template IDs
        expected_ids = {
            "new_client_onboarding",
            "invoice_paid_processing",
            "milestone_completion",
            "document_send_and_track",
            "bulk_client_update"
        }
        actual_ids = {t["template_id"] for t in templates}
        assert actual_ids == expected_ids, f"Missing templates: {expected_ids - actual_ids}"
        
        print(f"✓ GET /api/workflows/templates returned 5 templates: {actual_ids}")
    
    def test_template_structure(self, auth_session):
        """Each template should have required fields"""
        response = auth_session.get(f"{BASE_URL}/api/workflows/templates")
        assert response.status_code == 200
        
        templates = response.json()["templates"]
        
        for template in templates:
            # Check required fields
            assert "template_id" in template, "Missing template_id"
            assert "name" in template, "Missing name"
            assert "description" in template, "Missing description"
            assert "category" in template, "Missing category"
            assert "icon" in template, "Missing icon"
            assert "estimated_duration" in template, "Missing estimated_duration"
            assert "required_context" in template, "Missing required_context"
            assert "steps_count" in template, "Missing steps_count"
            assert "steps_preview" in template, "Missing steps_preview"
            
            # Steps count should be > 0
            assert template["steps_count"] > 0, f"{template['template_id']} has no steps"
        
        print("✓ All templates have required structure")
    
    def test_get_specific_template_new_client_onboarding(self, auth_session):
        """GET /api/workflows/templates/new_client_onboarding should return template details"""
        response = auth_session.get(f"{BASE_URL}/api/workflows/templates/new_client_onboarding")
        
        assert response.status_code == 200, f"Failed: {response.text}"
        template = response.json()
        
        # Check basic fields
        assert template["template_id"] == "new_client_onboarding"
        assert template["name"] == "New Client Onboarding"
        assert template["category"] == "onboarding"
        assert template["icon"] == "UserPlus"
        
        # Check required context
        assert "project_id" in template["required_context"]
        assert "client_name" in template["required_context"]
        assert "client_email" in template["required_context"]
        
        # Check steps
        assert len(template["steps"]) == 3, "Should have 3 steps"
        assert template["steps"][0]["action"] == "create_client"
        
        print(f"✓ new_client_onboarding template has {len(template['steps'])} steps")
    
    def test_get_specific_template_invoice_paid(self, auth_session):
        """GET /api/workflows/templates/invoice_paid_processing should return template details"""
        response = auth_session.get(f"{BASE_URL}/api/workflows/templates/invoice_paid_processing")
        
        assert response.status_code == 200, f"Failed: {response.text}"
        template = response.json()
        
        # Check basic fields
        assert template["template_id"] == "invoice_paid_processing"
        assert template["name"] == "Invoice Paid Processing"
        assert template["category"] == "payment"
        assert template["icon"] == "CreditCard"
        
        # Check required context
        assert "document_id" in template["required_context"]
        
        # Check steps
        assert len(template["steps"]) == 3, "Should have 3 steps"
        assert template["steps"][0]["action"] == "update_document_status"
        
        print(f"✓ invoice_paid_processing template has {len(template['steps'])} steps")
    
    def test_get_nonexistent_template_returns_404(self, auth_session):
        """GET /api/workflows/templates/nonexistent should return 404"""
        response = auth_session.get(f"{BASE_URL}/api/workflows/templates/nonexistent_template")
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Nonexistent template returns 404")


class TestWorkflowExecution(TestWorkflowSetup):
    """Test workflow execution"""
    
    @pytest.fixture(scope="class")
    def demo_project_id(self, auth_session):
        """Get a demo project ID for testing"""
        response = auth_session.get(f"{BASE_URL}/api/projects")
        if response.status_code == 200:
            projects = response.json()
            if projects and len(projects) > 0:
                return projects[0]["project_id"]
        return None
    
    def test_execute_new_client_onboarding_success(self, auth_session, demo_project_id):
        """POST /api/workflows/execute with new_client_onboarding should succeed"""
        if not demo_project_id:
            pytest.skip("No demo project available")
        
        response = auth_session.post(f"{BASE_URL}/api/workflows/execute", json={
            "template_id": "new_client_onboarding",
            "context": {
                "project_id": demo_project_id,
                "client_name": "TEST_Workflow_Client",
                "client_email": "test.workflow@example.com"
            },
            "mode": "automatic"
        })
        
        assert response.status_code == 200, f"Workflow failed: {response.text}"
        result = response.json()
        
        # Check response structure
        assert "success" in result, "Response should have 'success' field"
        assert "execution" in result, "Response should have 'execution' field"
        
        # Check execution details
        execution = result["execution"]
        assert execution["template_name"] == "New Client Onboarding"
        assert "execution_id" in execution
        assert "steps" in execution
        assert "progress" in execution
        
        # Check progress
        progress = execution["progress"]
        assert progress["total"] == 3, "Should have 3 total steps"
        assert progress["completed"] >= 1, "At least step 1 (create_client) should complete"
        
        # Check step statuses
        steps = execution["steps"]
        assert len(steps) == 3
        assert steps[0]["name"] == "Create Client Record"
        
        print(f"✓ new_client_onboarding executed: {progress['completed']}/{progress['total']} steps completed")
        print(f"  Execution ID: {execution['execution_id']}")
    
    def test_execute_invoice_paid_processing_without_document_fails(self, auth_session, demo_project_id):
        """POST /api/workflows/execute with invoice_paid_processing without document_id should fail"""
        response = auth_session.post(f"{BASE_URL}/api/workflows/execute", json={
            "template_id": "invoice_paid_processing",
            "context": {},  # Missing document_id
            "mode": "automatic"
        })
        
        # Should fail with 400 for missing required context
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        print("✓ invoice_paid_processing correctly requires document_id")
    
    def test_execute_with_document_id(self, auth_session):
        """POST /api/workflows/execute with invoice_paid_processing and document_id"""
        # First, get a document to test with
        doc_response = auth_session.get(f"{BASE_URL}/api/documents")
        
        if doc_response.status_code != 200:
            pytest.skip("Could not fetch documents")
        
        documents = doc_response.json()
        if not documents or len(documents) == 0:
            pytest.skip("No documents available for testing")
        
        # Find an invoice that's not already paid
        invoice = None
        for doc in documents:
            if doc.get("type") == "Invoice" and doc.get("status") != "Paid":
                invoice = doc
                break
        
        if not invoice:
            # Try with any document
            invoice = documents[0]
        
        response = auth_session.post(f"{BASE_URL}/api/workflows/execute", json={
            "template_id": "invoice_paid_processing",
            "context": {
                "document_id": invoice["document_id"]
            },
            "mode": "automatic"
        })
        
        assert response.status_code == 200, f"Workflow failed: {response.text}"
        result = response.json()
        
        assert "execution" in result
        execution = result["execution"]
        
        # Check that steps ran
        progress = execution["progress"]
        assert progress["total"] == 3
        
        print(f"✓ invoice_paid_processing executed for document {invoice['document_id']}")
        print(f"  Status: {execution['status']}, Steps: {progress['completed']}/{progress['total']} completed")
    
    def test_execute_missing_template_returns_400(self, auth_session):
        """POST /api/workflows/execute with invalid template should fail"""
        response = auth_session.post(f"{BASE_URL}/api/workflows/execute", json={
            "template_id": "nonexistent_workflow",
            "context": {},
            "mode": "automatic"
        })
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("✓ Invalid template_id returns 400")
    
    def test_execute_bulk_client_update_missing_context(self, auth_session):
        """POST /api/workflows/execute with bulk_client_update missing required context"""
        response = auth_session.post(f"{BASE_URL}/api/workflows/execute", json={
            "template_id": "bulk_client_update",
            "context": {
                "project_id": "some_project"
                # Missing message_title and message_content
            },
            "mode": "automatic"
        })
        
        assert response.status_code == 400, f"Expected 400 for missing context, got {response.status_code}"
        print("✓ bulk_client_update correctly validates required context")


class TestWorkflowCategories(TestWorkflowSetup):
    """Test workflow template filtering by category"""
    
    def test_filter_by_onboarding_category(self, auth_session):
        """GET /api/workflows/templates?category=onboarding should filter results"""
        response = auth_session.get(f"{BASE_URL}/api/workflows/templates", params={"category": "onboarding"})
        
        assert response.status_code == 200
        templates = response.json()["templates"]
        
        # All returned templates should be onboarding category
        for t in templates:
            assert t["category"] == "onboarding", f"Template {t['template_id']} has wrong category"
        
        # Should include new_client_onboarding
        ids = [t["template_id"] for t in templates]
        assert "new_client_onboarding" in ids
        
        print(f"✓ Category filter returned {len(templates)} onboarding template(s)")
    
    def test_filter_by_payment_category(self, auth_session):
        """GET /api/workflows/templates?category=payment should filter results"""
        response = auth_session.get(f"{BASE_URL}/api/workflows/templates", params={"category": "payment"})
        
        assert response.status_code == 200
        templates = response.json()["templates"]
        
        # All returned templates should be payment category
        for t in templates:
            assert t["category"] == "payment"
        
        # Should include invoice_paid_processing
        ids = [t["template_id"] for t in templates]
        assert "invoice_paid_processing" in ids
        
        print(f"✓ Category filter returned {len(templates)} payment template(s)")


# Cleanup test data
@pytest.fixture(scope="session", autouse=True)
def cleanup_test_clients():
    """Cleanup TEST_ prefixed clients after all tests"""
    yield
    # Cleanup would happen here if needed


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
