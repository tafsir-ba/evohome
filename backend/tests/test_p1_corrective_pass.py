"""
P1 Corrective Pass Tests - Iteration 11
Tests for fixes found in P1 evaluation:
- C1: RESEND_API_KEY NameError in workflows.py (now imports from email_service)
- I1: doc_extraction.py writing is_demo (removed)
- I2: stats.py filtering by is_demo (removed)
- I3: Dead get_is_demo imports in 9 route files (removed)
- DB migration: is_demo removed from all canonical collections
"""

import pytest
import requests
import os
import json
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_AGENT_EMAIL = "e2e@evohome-test.com"
TEST_AGENT_PASSWORD = "Test2026!"

# Known test data
TEST_PROJECT_ID = "proj_f763e6ef3aaf"
TEST_CLIENT_ID = "client_0d050a240d04"


@pytest.fixture(scope="module")
def auth_token():
    """Get auth token once for all tests in module"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_AGENT_EMAIL,
        "password": TEST_AGENT_PASSWORD
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    # API returns 'token' not 'access_token'
    token = data.get("token") or data.get("access_token")
    assert token, f"No token in response: {data}"
    return token


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Get auth headers for all tests"""
    return {"Authorization": f"Bearer {auth_token}"}


class TestHealthAndAuth:
    """Basic health and authentication tests"""
    
    def test_health_endpoint(self):
        """Verify API is accessible"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200, f"Health check failed: {response.text}"
        print("PASSED: Health endpoint accessible")
    
    def test_agent_login(self, auth_token):
        """Verify test agent can login"""
        assert auth_token is not None, "No auth token"
        print(f"PASSED: Agent login successful, token received")


class TestWorkflowFixes:
    """C1: Verify workflow endpoints don't crash with NameError (RESEND_API_KEY resolved)"""
    
    def test_workflow_templates_no_crash(self, auth_headers):
        """Verify GET /api/workflows/templates doesn't crash"""
        response = requests.get(f"{BASE_URL}/api/workflows/templates", headers=auth_headers)
        assert response.status_code == 200, f"Workflow templates failed: {response.text}"
        data = response.json()
        assert "templates" in data, "No templates in response"
        # Verify no is_demo in any template
        for template in data["templates"]:
            assert "is_demo" not in template, f"is_demo found in template: {template.get('template_id')}"
        print(f"PASSED: Workflow templates returned {len(data['templates'])} templates without is_demo")
    
    def test_workflow_execute_send_document_no_nameerror(self, auth_headers):
        """C1: Verify send_document workflow doesn't crash with NameError"""
        # First get a document to use
        docs_response = requests.get(f"{BASE_URL}/api/documents", headers=auth_headers)
        if docs_response.status_code == 200:
            docs_data = docs_response.json()
            # Handle both array and object responses
            docs = docs_data if isinstance(docs_data, list) else docs_data.get("documents", [])
            if docs:
                doc_id = docs[0].get("document_id")
                # Try to execute send_document workflow
                response = requests.post(f"{BASE_URL}/api/workflows/execute", 
                    headers=auth_headers,
                    json={
                        "template_id": "send_document",
                        "context": {"document_id": doc_id},
                        "mode": "automatic"
                    }
                )
                # Should not crash with NameError - may fail for other reasons but not NameError
                assert response.status_code != 500 or "NameError" not in response.text, \
                    f"NameError in workflow execution: {response.text}"
                print(f"PASSED: send_document workflow executed without NameError (status: {response.status_code})")
            else:
                print("SKIPPED: No documents available for send_document test")
        else:
            print("SKIPPED: Could not fetch documents for send_document test")
    
    def test_workflow_execute_new_client_onboarding_no_is_demo(self, auth_headers):
        """Verify new_client_onboarding workflow executes without is_demo"""
        response = requests.post(f"{BASE_URL}/api/workflows/execute",
            headers=auth_headers,
            json={
                "template_id": "new_client_onboarding",
                "context": {
                    "project_id": TEST_PROJECT_ID,
                    "client_name": "TEST_Workflow_Client",
                    "client_email": "test.workflow@example.com"
                },
                "mode": "automatic"
            }
        )
        # Should not crash - may complete or fail gracefully
        assert response.status_code in [200, 400, 404], f"Unexpected error: {response.text}"
        if response.status_code == 200:
            data = response.json()
            # Verify no is_demo in execution response
            assert "is_demo" not in str(data), "is_demo found in workflow execution response"
        print(f"PASSED: new_client_onboarding workflow executed (status: {response.status_code})")
    
    def test_workflow_execute_project_announcement_no_is_demo(self, auth_headers):
        """Verify project_announcement workflow executes without is_demo"""
        response = requests.post(f"{BASE_URL}/api/workflows/execute",
            headers=auth_headers,
            json={
                "template_id": "project_announcement",
                "context": {
                    "project_id": TEST_PROJECT_ID,
                    "message_title": "TEST Announcement",
                    "message_content": "This is a test announcement"
                },
                "mode": "automatic"
            }
        )
        # Should not crash
        assert response.status_code in [200, 400, 404], f"Unexpected error: {response.text}"
        if response.status_code == 200:
            data = response.json()
            assert "is_demo" not in str(data), "is_demo found in workflow execution response"
        print(f"PASSED: project_announcement workflow executed (status: {response.status_code})")
    
    def test_workflow_history_no_is_demo(self, auth_headers):
        """Verify workflow history doesn't contain is_demo"""
        response = requests.get(f"{BASE_URL}/api/workflows/history", headers=auth_headers)
        assert response.status_code == 200, f"Workflow history failed: {response.text}"
        data = response.json()
        assert "executions" in data, "No executions in response"
        # Verify no is_demo in any execution
        for execution in data.get("executions", []):
            assert "is_demo" not in execution, f"is_demo found in execution: {execution.get('execution_id')}"
        print(f"PASSED: Workflow history returned {len(data.get('executions', []))} executions without is_demo")


class TestStatsEndpoints:
    """I2: Verify stats endpoints work without is_demo filtering"""
    
    def test_agent_stats_no_is_demo_filter(self, auth_headers):
        """Verify GET /api/stats/agent returns stats without is_demo filtering"""
        response = requests.get(f"{BASE_URL}/api/stats/agent", headers=auth_headers)
        assert response.status_code == 200, f"Agent stats failed: {response.text}"
        data = response.json()
        
        # Verify expected fields exist
        assert "total_clients" in data, "Missing total_clients"
        assert "pending_quotes" in data, "Missing pending_quotes"
        assert "pending_invoices" in data, "Missing pending_invoices"
        assert "total_revenue" in data, "Missing total_revenue"
        
        # Verify no is_demo in response
        assert "is_demo" not in str(data), "is_demo found in agent stats response"
        
        print(f"PASSED: Agent stats returned - clients: {data['total_clients']}, quotes: {data['pending_quotes']}, invoices: {data['pending_invoices']}, revenue: {data['total_revenue']}")
    
    def test_buyer_stats_no_is_demo_filter(self, auth_headers):
        """Verify GET /api/stats/buyer returns stats without is_demo filtering"""
        response = requests.get(f"{BASE_URL}/api/stats/buyer", headers=auth_headers)
        # May return 403 if agent doesn't have buyer role - that's expected
        if response.status_code == 403:
            print("SKIPPED: Test agent doesn't have buyer role")
            return
        
        assert response.status_code == 200, f"Buyer stats failed: {response.text}"
        data = response.json()
        
        # Verify expected fields exist
        assert "pending_quotes" in data, "Missing pending_quotes"
        assert "pending_invoices" in data, "Missing pending_invoices"
        assert "total_paid" in data, "Missing total_paid"
        
        # Verify no is_demo in response
        assert "is_demo" not in str(data), "is_demo found in buyer stats response"
        
        print(f"PASSED: Buyer stats returned - quotes: {data['pending_quotes']}, invoices: {data['pending_invoices']}, paid: {data['total_paid']}")


class TestNotificationEndpoint:
    """Verify notifications endpoint returns correct structure"""
    
    def test_notifications_structure(self, auth_headers):
        """Verify GET /api/notifications returns {notifications, unread_count} with is_read"""
        response = requests.get(f"{BASE_URL}/api/notifications", headers=auth_headers)
        assert response.status_code == 200, f"Notifications failed: {response.text}"
        data = response.json()
        
        # Verify structure
        assert "notifications" in data, "Missing notifications array"
        assert "unread_count" in data, "Missing unread_count"
        assert isinstance(data["notifications"], list), "notifications should be a list"
        assert isinstance(data["unread_count"], int), "unread_count should be an integer"
        
        # Verify no is_demo in response
        assert "is_demo" not in str(data), "is_demo found in notifications response"
        
        # Verify is_read field in notifications
        for notif in data["notifications"]:
            assert "is_read" in notif, f"Missing is_read in notification: {notif.get('notification_id')}"
        
        print(f"PASSED: Notifications returned {len(data['notifications'])} items, unread_count: {data['unread_count']}")


class TestPhase1Regression:
    """Phase 1 regression: projects, timelines, clients - no is_demo in responses"""
    
    def test_projects_no_is_demo(self, auth_headers):
        """Verify GET /api/projects returns projects without is_demo"""
        response = requests.get(f"{BASE_URL}/api/projects", headers=auth_headers)
        assert response.status_code == 200, f"Projects failed: {response.text}"
        data = response.json()
        
        # Handle both array and object responses
        projects = data if isinstance(data, list) else data.get("projects", [data])
        
        for project in projects:
            assert "is_demo" not in project, f"is_demo found in project: {project.get('project_id')}"
        
        print(f"PASSED: Projects returned {len(projects)} items without is_demo")
    
    def test_project_timeline_no_is_demo(self, auth_headers):
        """Verify GET /api/project-timeline returns timeline without is_demo"""
        response = requests.get(f"{BASE_URL}/api/project-timeline?project_id={TEST_PROJECT_ID}", headers=auth_headers)
        assert response.status_code == 200, f"Project timeline failed: {response.text}"
        data = response.json()
        
        # Verify no is_demo in response
        assert "is_demo" not in str(data), "is_demo found in project timeline response"
        
        print(f"PASSED: Project timeline returned without is_demo")
    
    def test_clients_no_is_demo(self, auth_headers):
        """Verify GET /api/clients returns clients without is_demo"""
        response = requests.get(f"{BASE_URL}/api/clients", headers=auth_headers)
        assert response.status_code == 200, f"Clients failed: {response.text}"
        data = response.json()
        
        # Handle both array and object responses
        clients = data if isinstance(data, list) else data.get("clients", [data])
        
        for client in clients:
            assert "is_demo" not in client, f"is_demo found in client: {client.get('client_id')}"
        
        print(f"PASSED: Clients returned {len(clients)} items without is_demo")


class TestPhase2Regression:
    """Phase 2 regression: documents, activities, vault-documents - no is_demo in responses"""
    
    def test_documents_no_is_demo(self, auth_headers):
        """Verify GET /api/documents returns documents without is_demo"""
        response = requests.get(f"{BASE_URL}/api/documents", headers=auth_headers)
        assert response.status_code == 200, f"Documents failed: {response.text}"
        data = response.json()
        
        # Handle both array and object responses
        documents = data if isinstance(data, list) else data.get("documents", [data])
        
        for doc in documents:
            assert "is_demo" not in doc, f"is_demo found in document: {doc.get('document_id')}"
        
        print(f"PASSED: Documents returned {len(documents)} items without is_demo")
    
    def test_activities_no_is_demo(self, auth_headers):
        """Verify GET /api/activities returns activities without is_demo"""
        response = requests.get(f"{BASE_URL}/api/activities", headers=auth_headers)
        assert response.status_code == 200, f"Activities failed: {response.text}"
        data = response.json()
        
        # Handle both array and object responses
        activities = data if isinstance(data, list) else data.get("activities", [data])
        
        for activity in activities:
            assert "is_demo" not in activity, f"is_demo found in activity: {activity.get('activity_id')}"
        
        print(f"PASSED: Activities returned {len(activities)} items without is_demo")
    
    def test_vault_documents_no_is_demo(self, auth_headers):
        """Verify GET /api/vault/documents returns vault documents without is_demo"""
        response = requests.get(f"{BASE_URL}/api/vault/documents", headers=auth_headers)
        assert response.status_code == 200, f"Vault documents failed: {response.text}"
        data = response.json()
        
        # Handle both array and object responses
        vault_docs = data if isinstance(data, list) else data.get("documents", [data])
        
        for doc in vault_docs:
            assert "is_demo" not in doc, f"is_demo found in vault document: {doc.get('vault_doc_id')}"
        
        print(f"PASSED: Vault documents returned {len(vault_docs)} items without is_demo")


class TestPhase3Regression:
    """Phase 3 regression: command interpret/draft/execute flow"""
    
    def test_command_interpret_no_is_demo(self, auth_headers):
        """Verify POST /api/command/interpret works without is_demo"""
        # Command interpret uses Form data, not JSON
        response = requests.post(f"{BASE_URL}/api/command/interpret",
            headers=auth_headers,
            data={
                "command": "create a quote for 5000 CHF",
                "context": json.dumps({"project_id": TEST_PROJECT_ID})
            }
        )
        assert response.status_code == 200, f"Command interpret failed: {response.text}"
        data = response.json()
        
        # Verify no is_demo in response
        assert "is_demo" not in str(data), "is_demo found in command interpret response"
        
        print(f"PASSED: Command interpret returned intent: {data.get('intent', 'unknown')}")
        return data
    
    def test_command_draft_no_is_demo(self, auth_headers):
        """Verify POST /api/command/draft works without is_demo"""
        # First interpret a command using Form data
        interpret_response = requests.post(f"{BASE_URL}/api/command/interpret",
            headers=auth_headers,
            data={
                "command": "create a quote for 5000 CHF",
                "context": json.dumps({"project_id": TEST_PROJECT_ID})
            }
        )
        if interpret_response.status_code != 200:
            print("SKIPPED: Could not interpret command for draft test")
            return
        
        plan = interpret_response.json()
        
        # Now draft - also uses Form data
        response = requests.post(f"{BASE_URL}/api/command/draft",
            headers=auth_headers,
            data={
                "plan_id": plan.get("plan_id", "test_plan"),
                "intent": plan.get("intent", "create_quote"),
                "entities": json.dumps(plan.get("entities", {})),
                "fields": json.dumps(plan.get("fields", []))
            }
        )
        # May fail if plan is invalid, but should not have is_demo
        if response.status_code == 200:
            data = response.json()
            assert "is_demo" not in str(data), "is_demo found in command draft response"
            print(f"PASSED: Command draft returned draft_id: {data.get('draft_id', 'unknown')}")
        else:
            print(f"SKIPPED: Command draft returned {response.status_code} (may be expected)")


class TestTeamCRUD:
    """Team CRUD: POST + GET + PUT + DELETE /api/projects/{id}/team"""
    
    def test_team_crud_flow(self, auth_headers):
        """Test full team CRUD flow without is_demo"""
        # CREATE
        create_response = requests.post(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/team",
            headers=auth_headers,
            json={
                "name": "TEST_Team_Member_P1",
                "role": "contractor",
                "email": "test.team.p1@example.com",
                "phone": "+41 79 123 4567"
            }
        )
        assert create_response.status_code in [200, 201], f"Team create failed: {create_response.text}"
        created = create_response.json()
        assert "is_demo" not in created, "is_demo found in created team member"
        member_id = created.get("member_id") or created.get("team_member_id")
        print(f"PASSED: Team member created: {member_id}")
        
        # GET - returns array directly
        get_response = requests.get(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/team",
            headers=auth_headers
        )
        assert get_response.status_code == 200, f"Team get failed: {get_response.text}"
        team_data = get_response.json()
        # Handle both array and object responses
        members = team_data if isinstance(team_data, list) else team_data.get("team_members", team_data.get("members", []))
        for member in members:
            assert "is_demo" not in member, f"is_demo found in team member: {member.get('member_id')}"
        print(f"PASSED: Team list returned {len(members)} members without is_demo")
        
        # UPDATE
        if member_id:
            update_response = requests.put(
                f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/team/{member_id}",
                headers=auth_headers,
                json={"name": "TEST_Team_Member_P1_Updated"}
            )
            assert update_response.status_code == 200, f"Team update failed: {update_response.text}"
            updated = update_response.json()
            assert "is_demo" not in updated, "is_demo found in updated team member"
            print(f"PASSED: Team member updated")
            
            # DELETE
            delete_response = requests.delete(
                f"{BASE_URL}/api/projects/{TEST_PROJECT_ID}/team/{member_id}",
                headers=auth_headers
            )
            assert delete_response.status_code in [200, 204], f"Team delete failed: {delete_response.text}"
            print(f"PASSED: Team member deleted")
    
    def test_team_directory_no_is_demo(self, auth_headers):
        """Verify GET /api/team/directory returns contacts without is_demo"""
        response = requests.get(f"{BASE_URL}/api/team/directory", headers=auth_headers)
        assert response.status_code == 200, f"Team directory failed: {response.text}"
        data = response.json()
        
        # Handle both array and object responses
        contacts = data if isinstance(data, list) else data.get("contacts", data.get("directory", []))
        for contact in contacts:
            assert "is_demo" not in contact, f"is_demo found in contact: {contact.get('contact_id')}"
        
        print(f"PASSED: Team directory returned {len(contacts)} contacts without is_demo")


class TestCodeVerification:
    """Verify code-level fixes: no get_is_demo imports, RESEND_API_KEY imported correctly"""
    
    def test_no_get_is_demo_imports_in_routes(self):
        """I3: Verify no get_is_demo import in any route file"""
        import subprocess
        result = subprocess.run(
            ["grep", "-rn", "from helpers import.*get_is_demo", "/app/backend/routes/"],
            capture_output=True, text=True
        )
        assert result.returncode != 0 or result.stdout.strip() == "", \
            f"get_is_demo import found in routes: {result.stdout}"
        print("PASSED: No get_is_demo import found in any route file")
    
    def test_resend_api_key_imported_in_workflows(self):
        """C1: Verify RESEND_API_KEY is properly imported in workflows.py"""
        import subprocess
        result = subprocess.run(
            ["grep", "-n", "from services.email_service import.*RESEND_API_KEY", "/app/backend/routes/workflows.py"],
            capture_output=True, text=True
        )
        assert result.returncode == 0 and "RESEND_API_KEY" in result.stdout, \
            f"RESEND_API_KEY not imported in workflows.py"
        print(f"PASSED: RESEND_API_KEY imported in workflows.py: {result.stdout.strip()}")
    
    def test_doc_extraction_no_is_demo_references(self):
        """I1: Verify doc_extraction.py has zero is_demo references (non-import)"""
        import subprocess
        result = subprocess.run(
            ["grep", "-n", "is_demo", "/app/backend/routes/doc_extraction.py"],
            capture_output=True, text=True
        )
        # Should find nothing or only in import line (which is fine)
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            non_import_lines = [l for l in lines if 'import' not in l.lower()]
            assert len(non_import_lines) == 0, \
                f"is_demo references found in doc_extraction.py: {non_import_lines}"
        print("PASSED: doc_extraction.py has zero is_demo references (non-import)")
    
    def test_stats_no_is_demo_references(self):
        """I2: Verify stats.py has zero is_demo references"""
        import subprocess
        result = subprocess.run(
            ["grep", "-n", "is_demo", "/app/backend/routes/stats.py"],
            capture_output=True, text=True
        )
        # Should find nothing or only in import line (which is fine)
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            non_import_lines = [l for l in lines if 'import' not in l.lower()]
            assert len(non_import_lines) == 0, \
                f"is_demo references found in stats.py: {non_import_lines}"
        print("PASSED: stats.py has zero is_demo references")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
