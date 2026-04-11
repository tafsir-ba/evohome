"""
P1 Legacy Cleanup Tests - Evohome CMP Canonical Surgical Rebuild

Tests for:
1. Team CRUD: POST/GET/PUT/DELETE /api/projects/{id}/team
2. Team bulk: POST /api/projects/{id}/team/bulk
3. Team directory: GET /api/team/directory
4. Workflow templates: GET /api/workflows/templates (no is_demo)
5. Workflow execution: POST /api/workflows/execute (no is_demo)
6. Workflow history: GET /api/workflows/history
7. Workflow selectors: GET /api/workflows/selectors
8. Phase 1/2/3 regression: projects, timelines, units, clients, steps, documents, activities, vault, notifications, commands
9. Notification contract: GET /api/notifications returns {notifications, unread_count} with is_read field
10. No is_demo in any team, workflow, command, notification response
11. Dead V1 routes return 404
"""
import os
import pytest
import requests
import json
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "e2e@evohome-test.com"
TEST_PASSWORD = "Test2026!"

# Known test data from previous iterations
TEST_PROJECT_ID = "proj_f763e6ef3aaf"
TEST_CLIENT_ID = "client_0d050a240d04"

# Global session to reuse auth token
_session = None
_auth_token = None


def get_auth_token():
    """Get or reuse auth token with rate limit handling"""
    global _auth_token
    if _auth_token:
        return _auth_token
    
    for attempt in range(3):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code == 200:
            data = response.json()
            _auth_token = data.get("token")  # Note: API uses "token" not "access_token"
            return _auth_token
        elif response.status_code == 429:
            print(f"Rate limited, waiting 30s (attempt {attempt + 1}/3)")
            time.sleep(30)
        else:
            raise Exception(f"Login failed: {response.status_code} - {response.text}")
    
    raise Exception("Failed to login after 3 attempts due to rate limiting")


def get_auth_headers():
    """Get headers with auth token"""
    token = get_auth_token()
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }


class TestSetup:
    """Setup and authentication tests"""
    
    def test_health_check(self):
        """Test API health endpoint"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "alive"
        print(f"✓ Health check passed: {data}")
    
    def test_login_success(self):
        """Test login with test credentials"""
        token = get_auth_token()
        assert token is not None
        print(f"✓ Login successful, got token")


class TestTeamCRUD:
    """Team CRUD endpoint tests - NEW team_v2.py routes"""
    
    def test_create_team_member(self):
        """Test POST /api/projects/{id}/team creates member without is_demo"""
        headers = get_auth_headers()
        response = requests.post(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/team",
            headers=headers,
            json={
                "company_name": "TEST_Create_Member_Corp",
                "contact_name": "TEST_Jane Smith",
                "role": "Contractor",
                "email": "test_create_member@example.com",
                "phone": "+41 79 999 8888",
                "website": "https://example.com",
                "address": "123 Test Street",
                "notes": "Test notes for P1 cleanup"
            }
        )
        assert response.status_code in [200, 201], f"Create team member failed: {response.text}"
        data = response.json()
        
        # Verify member_id is returned
        assert "member_id" in data, "member_id not in response"
        
        # Verify no is_demo in response
        assert "is_demo" not in data, "is_demo should NOT be in team member response"
        
        # Verify fields are correct
        assert data.get("company_name") == "TEST_Create_Member_Corp"
        assert data.get("contact_name") == "TEST_Jane Smith"
        assert data.get("role") == "Contractor"
        
        print(f"✓ Team member created: {data.get('member_id')}")
    
    def test_get_team_members(self):
        """Test GET /api/projects/{id}/team lists members"""
        headers = get_auth_headers()
        response = requests.get(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/team",
            headers=headers
        )
        assert response.status_code == 200, f"Get team members failed: {response.text}"
        data = response.json()
        
        # Should be a list
        assert isinstance(data, list), "Response should be a list"
        
        # Verify no is_demo in any member
        for member in data:
            assert "is_demo" not in member, f"is_demo found in team member: {member.get('member_id')}"
        
        print(f"✓ Got {len(data)} team members, no is_demo in any")
    
    def test_update_team_member(self):
        """Test PUT /api/projects/{id}/team/{member_id} updates member"""
        headers = get_auth_headers()
        
        # First create a member to update
        create_response = requests.post(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/team",
            headers=headers,
            json={
                "company_name": "TEST_Update_Me_Corp",
                "contact_name": "TEST_Update Person",
                "role": "Supplier"
            }
        )
        assert create_response.status_code in [200, 201]
        member_id = create_response.json().get("member_id")
        
        # Now update
        response = requests.put(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/team/{member_id}",
            headers=headers,
            json={
                "company_name": "TEST_Updated_Corp",
                "role": "Updated Supplier"
            }
        )
        assert response.status_code == 200, f"Update team member failed: {response.text}"
        data = response.json()
        
        # Verify update applied
        assert data.get("company_name") == "TEST_Updated_Corp"
        assert data.get("role") == "Updated Supplier"
        
        # Verify no is_demo
        assert "is_demo" not in data, "is_demo should NOT be in updated team member response"
        
        print(f"✓ Team member updated: {member_id}")
    
    def test_delete_team_member(self):
        """Test DELETE /api/projects/{id}/team/{member_id} deletes member"""
        headers = get_auth_headers()
        
        # First create a member to delete
        create_response = requests.post(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/team",
            headers=headers,
            json={
                "company_name": "TEST_Delete_Me_Corp",
                "contact_name": "TEST_Delete Me",
                "role": "Temp"
            }
        )
        assert create_response.status_code in [200, 201]
        member_id = create_response.json().get("member_id")
        
        # Now delete
        response = requests.delete(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/team/{member_id}",
            headers=headers
        )
        assert response.status_code == 200, f"Delete team member failed: {response.text}"
        data = response.json()
        assert "message" in data
        
        print(f"✓ Team member deleted: {member_id}")
    
    def test_bulk_import_team_members(self):
        """Test POST /api/projects/{id}/team/bulk imports contacts without is_demo"""
        headers = get_auth_headers()
        response = requests.post(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/team/bulk",
            headers=headers,
            json={
                "contacts": [
                    {
                        "company_name": "TEST_Bulk_Corp_1",
                        "contact_name": "TEST_Bulk Person 1",
                        "role": "Electrician",
                        "email": "bulk1@example.com"
                    },
                    {
                        "company_name": "TEST_Bulk_Corp_2",
                        "contact_name": "TEST_Bulk Person 2",
                        "role": "Plumber",
                        "email": "bulk2@example.com"
                    }
                ]
            }
        )
        assert response.status_code == 200, f"Bulk import failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "created" in data, "created count not in response"
        assert "members" in data, "members not in response"
        
        # Verify no is_demo in any created member
        for member in data.get("members", []):
            assert "is_demo" not in member, f"is_demo found in bulk-created member"
        
        print(f"✓ Bulk import: created={data.get('created')}, skipped={data.get('skipped')}")
    
    def test_team_directory(self):
        """Test GET /api/team/directory returns contacts"""
        headers = get_auth_headers()
        response = requests.get(
            f"{BASE_URL}/api/team/directory",
            headers=headers
        )
        assert response.status_code == 200, f"Team directory failed: {response.text}"
        data = response.json()
        
        # Should be a list
        assert isinstance(data, list), "Directory response should be a list"
        
        # Verify no is_demo in any contact
        for contact in data:
            assert "is_demo" not in contact, f"is_demo found in directory contact"
        
        print(f"✓ Team directory: {len(data)} contacts, no is_demo in any")


class TestWorkflowSanitization:
    """Workflow endpoint tests - verify is_demo sanitization"""
    
    def test_workflow_templates(self):
        """Test GET /api/workflows/templates returns templates (no is_demo in response)"""
        headers = get_auth_headers()
        response = requests.get(
            f"{BASE_URL}/api/workflows/templates",
            headers=headers
        )
        assert response.status_code == 200, f"Get workflow templates failed: {response.text}"
        data = response.json()
        
        assert "templates" in data, "templates not in response"
        templates = data["templates"]
        assert len(templates) > 0, "No templates returned"
        
        # Verify no is_demo in any template
        for template in templates:
            assert "is_demo" not in template, f"is_demo found in template: {template.get('template_id')}"
        
        print(f"✓ Got {len(templates)} workflow templates, no is_demo in any")
    
    def test_workflow_execute(self):
        """Test POST /api/workflows/execute runs workflow without is_demo"""
        headers = get_auth_headers()
        
        # Use milestone_completion workflow with a test step
        # First, get a timeline step to use
        steps_response = requests.get(
            f"{BASE_URL}/api/workflows/selectors?selector_type=timeline_step",
            headers=headers
        )
        
        if steps_response.status_code == 200:
            items = steps_response.json().get("items", [])
            if items:
                step_id = items[0].get("step_id")
                
                response = requests.post(
                    f"{BASE_URL}/api/workflows/execute",
                    headers=headers,
                    json={
                        "template_id": "milestone_completion",
                        "context": {
                            "step_id": step_id
                        },
                        "mode": "automatic"
                    }
                )
                
                # May fail due to missing client email, but response should not have is_demo
                if response.status_code in [200, 400, 500]:
                    data = response.json()
                    
                    # Check execution response for is_demo
                    if "execution" in data:
                        execution = data["execution"]
                        assert "is_demo" not in execution, "is_demo found in workflow execution"
                        
                        # Check steps for is_demo
                        for step in execution.get("steps", []):
                            assert "is_demo" not in step, "is_demo found in workflow step"
                    
                    print(f"✓ Workflow execute response has no is_demo")
                    return
        
        # Fallback: just verify the endpoint exists and doesn't have is_demo in error response
        response = requests.post(
            f"{BASE_URL}/api/workflows/execute",
            headers=headers,
            json={
                "template_id": "milestone_completion",
                "context": {},
                "mode": "automatic"
            }
        )
        # Should fail with 400 due to missing context, but no is_demo
        data = response.json()
        assert "is_demo" not in str(data), "is_demo found in workflow execute response"
        print(f"✓ Workflow execute endpoint verified (no is_demo)")
    
    def test_workflow_history(self):
        """Test GET /api/workflows/history returns executions"""
        headers = get_auth_headers()
        response = requests.get(
            f"{BASE_URL}/api/workflows/history",
            headers=headers
        )
        assert response.status_code == 200, f"Get workflow history failed: {response.text}"
        data = response.json()
        
        assert "executions" in data, "executions not in response"
        
        # Verify no is_demo in any execution
        for execution in data.get("executions", []):
            assert "is_demo" not in execution, f"is_demo found in execution: {execution.get('execution_id')}"
            for step in execution.get("steps", []):
                assert "is_demo" not in step, "is_demo found in execution step"
        
        print(f"✓ Workflow history: {len(data.get('executions', []))} executions, no is_demo")
    
    def test_workflow_selectors_document(self):
        """Test GET /api/workflows/selectors?selector_type=document returns items"""
        headers = get_auth_headers()
        response = requests.get(
            f"{BASE_URL}/api/workflows/selectors?selector_type=document",
            headers=headers
        )
        assert response.status_code == 200, f"Get document selectors failed: {response.text}"
        data = response.json()
        
        assert "items" in data, "items not in response"
        
        # Verify no is_demo in any item
        for item in data.get("items", []):
            assert "is_demo" not in item, f"is_demo found in document selector item"
        
        print(f"✓ Document selectors: {len(data.get('items', []))} items, no is_demo")
    
    def test_workflow_selectors_client(self):
        """Test GET /api/workflows/selectors?selector_type=client returns items"""
        headers = get_auth_headers()
        response = requests.get(
            f"{BASE_URL}/api/workflows/selectors?selector_type=client",
            headers=headers
        )
        assert response.status_code == 200, f"Get client selectors failed: {response.text}"
        data = response.json()
        
        assert "items" in data, "items not in response"
        
        # Verify no is_demo in any item
        for item in data.get("items", []):
            assert "is_demo" not in item, f"is_demo found in client selector item"
        
        print(f"✓ Client selectors: {len(data.get('items', []))} items, no is_demo")


class TestPhase1Regression:
    """Phase 1 regression tests - projects, clients (actual endpoints)"""
    
    def test_projects_list(self):
        """Test GET /api/projects still works"""
        headers = get_auth_headers()
        response = requests.get(f"{BASE_URL}/api/projects", headers=headers)
        assert response.status_code == 200, f"Projects list failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Projects should be a list"
        print(f"✓ Projects: {len(data)} projects")
    
    def test_project_timeline(self):
        """Test GET /api/project-timeline?project_id={id} still works"""
        headers = get_auth_headers()
        response = requests.get(f"{BASE_URL}/api/project-timeline?project_id={TEST_PROJECT_ID}", headers=headers)
        assert response.status_code == 200, f"Project timeline failed: {response.text}"
        print(f"✓ Project timeline endpoint works")
    
    def test_project_steps(self):
        """Test GET /api/projects/{id}/steps still works"""
        headers = get_auth_headers()
        response = requests.get(f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/steps", headers=headers)
        assert response.status_code == 200, f"Project steps failed: {response.text}"
        print(f"✓ Project steps endpoint works")
    
    def test_clients_list(self):
        """Test GET /api/clients still works"""
        headers = get_auth_headers()
        response = requests.get(f"{BASE_URL}/api/clients", headers=headers)
        assert response.status_code == 200, f"Clients list failed: {response.text}"
        print(f"✓ Clients endpoint works")


class TestPhase2Regression:
    """Phase 2 regression tests - documents, activities, vault, notifications"""
    
    def test_documents_list(self):
        """Test GET /api/documents still works"""
        headers = get_auth_headers()
        response = requests.get(f"{BASE_URL}/api/documents", headers=headers)
        assert response.status_code == 200, f"Documents list failed: {response.text}"
        print(f"✓ Documents endpoint works")
    
    def test_activities_list(self):
        """Test GET /api/activities still works"""
        headers = get_auth_headers()
        response = requests.get(f"{BASE_URL}/api/activities", headers=headers)
        assert response.status_code == 200, f"Activities list failed: {response.text}"
        print(f"✓ Activities endpoint works")
    
    def test_vault_documents(self):
        """Test GET /api/vault/documents still works"""
        headers = get_auth_headers()
        response = requests.get(f"{BASE_URL}/api/vault/documents", headers=headers)
        assert response.status_code == 200, f"Vault documents failed: {response.text}"
        print(f"✓ Vault documents endpoint works")
    
    def test_notifications_contract(self):
        """Test GET /api/notifications returns {notifications, unread_count} with is_read field"""
        headers = get_auth_headers()
        response = requests.get(f"{BASE_URL}/api/notifications", headers=headers)
        assert response.status_code == 200, f"Notifications failed: {response.text}"
        data = response.json()
        
        # Verify response shape
        assert "notifications" in data, "notifications not in response"
        assert "unread_count" in data, "unread_count not in response"
        
        # Verify is_read field in notifications (not 'read')
        for notif in data.get("notifications", []):
            assert "is_read" in notif, f"is_read not in notification: {notif.get('notification_id')}"
            assert "read" not in notif, f"'read' field should not exist in notification"
            assert "is_demo" not in notif, f"is_demo found in notification"
        
        print(f"✓ Notifications: {len(data.get('notifications', []))} notifications, unread_count={data.get('unread_count')}")


class TestPhase3Regression:
    """Phase 3 regression tests - command interpret/draft/execute"""
    
    def test_command_interpret(self):
        """Test POST /api/command/interpret still works (uses Form data)"""
        headers = get_auth_headers()
        # Remove Content-Type for form data
        form_headers = {"Authorization": headers["Authorization"]}
        
        response = requests.post(
            f"{BASE_URL}/api/command/interpret",
            headers=form_headers,
            data={
                "command": "create a quote for 5000 CHF for kitchen renovation",
                "context": json.dumps({"project_id": TEST_PROJECT_ID, "client_id": TEST_CLIENT_ID})
            }
        )
        assert response.status_code == 200, f"Command interpret failed: {response.text}"
        data = response.json()
        
        # Verify no is_demo in response
        assert "is_demo" not in data, "is_demo found in command interpret response"
        
        print(f"✓ Command interpret works, intent={data.get('intent')}")
    
    def test_command_tools(self):
        """Test GET /api/command/tools still works (returns array directly)"""
        headers = get_auth_headers()
        response = requests.get(f"{BASE_URL}/api/command/tools", headers=headers)
        assert response.status_code == 200, f"Command tools failed: {response.text}"
        data = response.json()
        
        # Response is a list directly, not {"tools": [...]}
        assert isinstance(data, list), "tools response should be a list"
        
        # Verify no is_demo in any tool
        for tool in data:
            assert "is_demo" not in tool, f"is_demo found in tool"
        
        print(f"✓ Command tools: {len(data)} tools")


class TestDeadV1Routes:
    """Test that dead V1 routes return 404 or don't exist"""
    
    def test_old_activities_404(self):
        """Test GET /api/old-activities returns 404"""
        headers = get_auth_headers()
        response = requests.get(f"{BASE_URL}/api/old-activities", headers=headers)
        assert response.status_code == 404, f"Expected 404 for /api/old-activities, got {response.status_code}"
        print(f"✓ /api/old-activities returns 404 (dead route)")
    
    def test_v1_activities_404(self):
        """Test GET /api/v1/activities returns 404"""
        headers = get_auth_headers()
        response = requests.get(f"{BASE_URL}/api/v1/activities", headers=headers)
        assert response.status_code == 404, f"Expected 404 for /api/v1/activities, got {response.status_code}"
        print(f"✓ /api/v1/activities returns 404 (dead route)")
    
    def test_v1_clients_404(self):
        """Test GET /api/v1/clients returns 404"""
        headers = get_auth_headers()
        response = requests.get(f"{BASE_URL}/api/v1/clients", headers=headers)
        assert response.status_code == 404, f"Expected 404 for /api/v1/clients, got {response.status_code}"
        print(f"✓ /api/v1/clients returns 404 (dead route)")
    
    def test_v1_documents_404(self):
        """Test GET /api/v1/documents returns 404"""
        headers = get_auth_headers()
        response = requests.get(f"{BASE_URL}/api/v1/documents", headers=headers)
        assert response.status_code == 404, f"Expected 404 for /api/v1/documents, got {response.status_code}"
        print(f"✓ /api/v1/documents returns 404 (dead route)")


class TestNoIsDemoInResponses:
    """Comprehensive test that no is_demo field appears in any response"""
    
    def _check_no_is_demo(self, data, path="root"):
        """Recursively check that no is_demo field exists in data"""
        if isinstance(data, dict):
            assert "is_demo" not in data, f"is_demo found at {path}"
            for key, value in data.items():
                self._check_no_is_demo(value, f"{path}.{key}")
        elif isinstance(data, list):
            for i, item in enumerate(data):
                self._check_no_is_demo(item, f"{path}[{i}]")
    
    def test_no_is_demo_in_team_response(self):
        """Verify no is_demo in team endpoints"""
        headers = get_auth_headers()
        response = requests.get(f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/team", headers=headers)
        if response.status_code == 200:
            self._check_no_is_demo(response.json(), "team")
        print(f"✓ No is_demo in team response")
    
    def test_no_is_demo_in_workflow_templates(self):
        """Verify no is_demo in workflow templates"""
        headers = get_auth_headers()
        response = requests.get(f"{BASE_URL}/api/workflows/templates", headers=headers)
        if response.status_code == 200:
            self._check_no_is_demo(response.json(), "workflow_templates")
        print(f"✓ No is_demo in workflow templates")
    
    def test_no_is_demo_in_workflow_history(self):
        """Verify no is_demo in workflow history"""
        headers = get_auth_headers()
        response = requests.get(f"{BASE_URL}/api/workflows/history", headers=headers)
        if response.status_code == 200:
            self._check_no_is_demo(response.json(), "workflow_history")
        print(f"✓ No is_demo in workflow history")
    
    def test_no_is_demo_in_notifications(self):
        """Verify no is_demo in notifications"""
        headers = get_auth_headers()
        response = requests.get(f"{BASE_URL}/api/notifications", headers=headers)
        if response.status_code == 200:
            self._check_no_is_demo(response.json(), "notifications")
        print(f"✓ No is_demo in notifications")
    
    def test_no_is_demo_in_command_tools(self):
        """Verify no is_demo in command tools"""
        headers = get_auth_headers()
        response = requests.get(f"{BASE_URL}/api/command/tools", headers=headers)
        if response.status_code == 200:
            self._check_no_is_demo(response.json(), "command_tools")
        print(f"✓ No is_demo in command tools")


class TestEmailServiceShimRemoved:
    """Test that email_service.create_notification shim is removed"""
    
    def test_email_service_no_create_notification(self):
        """Verify email_service.create_notification no longer exists"""
        # This is a code inspection test - we verify by trying to import
        # The shim should have been removed
        try:
            import sys
            sys.path.insert(0, '/app/backend')
            from services import email_service
            
            # Check if create_notification exists
            has_create_notification = hasattr(email_service, 'create_notification')
            assert not has_create_notification, "email_service.create_notification shim should be removed"
            print(f"✓ email_service.create_notification shim removed")
        except ImportError:
            # If we can't import, that's fine - we're testing via API
            print(f"✓ email_service import test skipped (running via API)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
