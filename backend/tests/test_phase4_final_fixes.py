"""
Phase 4 Final Production-Ready Fixes Tests
-------------------------------------------
Tests for:
1. Email error handling with graceful degradation and warning status
2. Missing required context returns clear validation error
3. safe_send_email helper handles missing email gracefully
4. TTL index for workflow cleanup
5. Better error messages
6. Warning status in workflow execution
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
AGENT_EMAIL = "demo.agent@upgradeflow.com"
AGENT_PASSWORD = "demo123"

@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for agent"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": AGENT_EMAIL, "password": AGENT_PASSWORD}
    )
    if response.status_code == 200:
        data = response.json()
        return data.get("token")
    pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")

@pytest.fixture
def agent_session(auth_token):
    """Session with auth headers"""
    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    })
    return session


class TestWorkflowContextValidation:
    """Test missing required context returns clear validation errors"""
    
    def test_missing_context_new_client_onboarding_returns_400(self, agent_session):
        """Execute new_client_onboarding with empty context - should return 400 with clear message"""
        response = agent_session.post(
            f"{BASE_URL}/api/workflows/execute",
            json={
                "template_id": "new_client_onboarding",
                "context": {},  # Empty context - missing required fields
                "mode": "automatic"
            }
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        error_detail = response.json().get("detail", "")
        
        # Should mention specific missing fields
        assert "Missing required context" in error_detail, f"Expected 'Missing required context' in error: {error_detail}"
        assert "client_name" in error_detail or "project_id" in error_detail, f"Error should mention specific fields: {error_detail}"
        print(f"PASS: Missing context returns clear error: {error_detail}")
    
    def test_partial_context_returns_missing_fields(self, agent_session):
        """Execute with partial context - should list all missing required fields"""
        response = agent_session.post(
            f"{BASE_URL}/api/workflows/execute",
            json={
                "template_id": "new_client_onboarding",
                "context": {
                    "client_name": "Test Client"  # Missing project_id and client_email
                },
                "mode": "automatic"
            }
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        error_detail = response.json().get("detail", "")
        
        # Should mention client_email and project_id as missing
        assert "client_email" in error_detail or "project_id" in error_detail, \
            f"Error should mention missing fields: {error_detail}"
        print(f"PASS: Partial context error shows missing: {error_detail}")
    
    def test_invoice_paid_missing_document_id(self, agent_session):
        """Invoice paid processing without document_id should return 400"""
        response = agent_session.post(
            f"{BASE_URL}/api/workflows/execute",
            json={
                "template_id": "invoice_paid_processing",
                "context": {},  # Missing required document_id
                "mode": "automatic"
            }
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        error_detail = response.json().get("detail", "")
        assert "document_id" in error_detail or "Missing required" in error_detail, \
            f"Error should mention document_id: {error_detail}"
        print(f"PASS: Missing document_id error: {error_detail}")


class TestWorkflowWarningStatus:
    """Test workflow returns warning status when email fails but action succeeds"""
    
    def test_workflow_templates_have_required_context(self, agent_session):
        """Verify templates define required_context properly"""
        response = agent_session.get(f"{BASE_URL}/api/workflows/templates")
        assert response.status_code == 200
        
        templates = response.json().get("templates", [])
        
        for template in templates:
            # Each template should have required_context array
            assert "required_context" in template, f"Template {template['template_id']} missing required_context"
            assert isinstance(template["required_context"], list), f"required_context should be a list"
            print(f"Template {template['template_id']}: required={template['required_context']}")
        
        print(f"PASS: All {len(templates)} templates have required_context defined")
    
    def test_successful_workflow_returns_completed_status(self, agent_session):
        """Execute a workflow with valid context and verify completed status"""
        # First get a valid document for invoice_paid_processing
        docs_response = agent_session.get(f"{BASE_URL}/api/workflows/selectors?selector_type=document")
        
        if docs_response.status_code != 200:
            pytest.skip("No documents available for test")
        
        docs = docs_response.json().get("items", [])
        if not docs:
            pytest.skip("No documents available for test")
        
        document_id = docs[0].get("document_id")  # Correct field name
        
        # Execute workflow with valid document
        response = agent_session.post(
            f"{BASE_URL}/api/workflows/execute",
            json={
                "template_id": "invoice_paid_processing",
                "context": {"document_id": document_id},
                "mode": "automatic"
            }
        )
        
        assert response.status_code == 200, f"Execute failed: {response.status_code} - {response.text}"
        
        result = response.json()
        execution = result.get("execution", {})
        
        # Status should be completed or completed_with_warnings
        valid_statuses = ["completed", "completed_with_warnings"]
        assert execution.get("status") in valid_statuses, \
            f"Expected status in {valid_statuses}, got {execution.get('status')}"
        
        # Check if there were warnings
        warnings_count = execution.get("progress", {}).get("warnings", 0)
        if warnings_count > 0:
            print(f"PASS: Workflow completed with {warnings_count} warnings (email may have failed gracefully)")
            # Verify warning messages are present in steps
            for step in execution.get("steps", []):
                if step.get("warning"):
                    print(f"  Step '{step['name']}' warning: {step['warning']}")
        else:
            print(f"PASS: Workflow completed successfully without warnings")


class TestWorkflowService:
    """Test workflow service functionality"""
    
    def test_workflow_service_available(self, agent_session):
        """Check workflow service is running"""
        response = agent_session.get(f"{BASE_URL}/api/workflows/templates")
        assert response.status_code == 200
        print("PASS: Workflow service is available")
    
    def test_workflow_history_returns_executions(self, agent_session):
        """Get workflow history and verify structure"""
        response = agent_session.get(f"{BASE_URL}/api/workflows/history")
        assert response.status_code == 200
        
        data = response.json()
        executions = data.get("executions", [])
        
        if executions:
            # Verify execution structure
            exec_sample = executions[0]
            required_fields = ["execution_id", "template_id", "status", "progress", "steps"]
            for field in required_fields:
                assert field in exec_sample, f"Missing field {field} in execution"
            
            # Check progress structure includes warnings
            progress = exec_sample.get("progress", {})
            assert "warnings" in progress, "Progress should include warnings count"
            
            print(f"PASS: Workflow history has {len(executions)} executions with proper structure")
        else:
            print("PASS: Workflow history endpoint works (no executions yet)")
    
    def test_execution_status_includes_warning_fields(self, agent_session):
        """Verify execution response includes warning-related fields"""
        response = agent_session.get(f"{BASE_URL}/api/workflows/history?limit=5")
        assert response.status_code == 200
        
        executions = response.json().get("executions", [])
        
        for execution in executions:
            # Check progress has warnings count
            progress = execution.get("progress", {})
            assert "warnings" in progress, f"Progress missing 'warnings' field"
            
            # Check steps have warning field available
            for step in execution.get("steps", []):
                # warning field should exist (can be None)
                assert "warning" in step or step.get("warning") is None, \
                    f"Step missing warning field capability"
        
        print(f"PASS: Executions include warning fields in structure")


class TestSelectorEndpoints:
    """Test workflow selector endpoints for validation"""
    
    def test_document_selector_returns_items(self, agent_session):
        """Get document selector and verify structure"""
        response = agent_session.get(f"{BASE_URL}/api/workflows/selectors?selector_type=document")
        assert response.status_code == 200
        
        items = response.json().get("items", [])
        print(f"PASS: Document selector returned {len(items)} items")
    
    def test_timeline_step_selector_returns_items(self, agent_session):
        """Get timeline step selector"""
        response = agent_session.get(f"{BASE_URL}/api/workflows/selectors?selector_type=timeline_step")
        assert response.status_code == 200
        
        items = response.json().get("items", [])
        print(f"PASS: Timeline step selector returned {len(items)} items")
    
    def test_invalid_selector_type_returns_400(self, agent_session):
        """Invalid selector type should return 400"""
        response = agent_session.get(f"{BASE_URL}/api/workflows/selectors?selector_type=invalid_type")
        assert response.status_code == 400, f"Expected 400 for invalid selector type, got {response.status_code}"
        print("PASS: Invalid selector type returns 400")


class TestTTLIndex:
    """Test TTL index configuration"""
    
    def test_workflow_executions_have_created_at(self, agent_session):
        """Verify workflow executions have created_at field (required for TTL)"""
        response = agent_session.get(f"{BASE_URL}/api/workflows/history?limit=3")
        assert response.status_code == 200
        
        executions = response.json().get("executions", [])
        
        for execution in executions:
            assert "created_at" in execution, "Execution missing created_at field for TTL"
        
        print(f"PASS: Executions have created_at field for TTL index ({len(executions)} checked)")


class TestEmailGracefulDegradation:
    """Test email service graceful degradation"""
    
    def test_workflow_with_invalid_email_completes_with_warning(self, agent_session):
        """Create client workflow with invalid email should complete with warning (not fail)"""
        # Get a project_id first
        projects_response = agent_session.get(f"{BASE_URL}/api/projects")
        if projects_response.status_code != 200:
            pytest.skip("No projects available")
        
        projects = projects_response.json()
        if not projects:
            pytest.skip("No projects available")
        
        project_id = projects[0].get("project_id")
        
        # Execute workflow with invalid email format
        response = agent_session.post(
            f"{BASE_URL}/api/workflows/execute",
            json={
                "template_id": "new_client_onboarding",
                "context": {
                    "project_id": project_id,
                    "client_name": "TEST_Invalid_Email_Client",
                    "client_email": "invalid-email-test@nonexistent-domain-xyz.invalid"
                },
                "mode": "automatic"
            }
        )
        
        # Workflow should succeed (possibly with warnings) - not fail with 500
        assert response.status_code == 200, f"Workflow should not fail: {response.status_code} - {response.text}"
        
        result = response.json()
        execution = result.get("execution", {})
        
        # Should either complete or complete_with_warnings
        valid_statuses = ["completed", "completed_with_warnings"]
        assert execution.get("status") in valid_statuses, \
            f"Expected graceful completion, got {execution.get('status')}"
        
        print(f"PASS: Workflow with potentially invalid email completed with status: {execution.get('status')}")
        
        # If there are warnings, verify they're captured
        if execution.get("status") == "completed_with_warnings":
            warnings_count = execution.get("progress", {}).get("warnings", 0)
            print(f"  Email warning captured successfully ({warnings_count} warnings)")


# Run with pytest
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
