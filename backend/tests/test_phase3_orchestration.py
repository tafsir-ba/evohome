"""
Phase 3 Canonical Surgical Rebuild — Orchestration Tests

Tests for:
1. Command service orchestration (interpret, draft, execute)
2. Notification canonicalization (no is_demo)
3. Document/Activity creation via command/execute routes to canonical services
4. Draft idempotency and cancellation
5. No notification_bridge.py imports anywhere
"""
import os
import pytest
import requests
import time
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_AGENT_EMAIL = "e2e@evohome-test.com"
TEST_AGENT_PASSWORD = "Test2026!"

# Known test data from main agent context
TEST_PROJECT_ID = "proj_f763e6ef3aaf"
TEST_CLIENT_ID = "client_0d050a240d04"


# Module-level session to avoid rate limiting
_session = None
_auth_headers = None


def get_auth_headers():
    """Get auth headers, reusing session to avoid rate limiting"""
    global _session, _auth_headers
    if _auth_headers is not None:
        return _auth_headers
    
    _session = requests.Session()
    response = _session.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_AGENT_EMAIL,
        "password": TEST_AGENT_PASSWORD
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    # API returns 'token' not 'access_token'
    token = data.get("token") or data.get("access_token")
    assert token, f"No token in response: {data}"
    _auth_headers = {"Authorization": f"Bearer {token}"}
    return _auth_headers


class TestPhase3Setup:
    """Setup and authentication tests"""
    
    def test_health_check(self):
        """Verify API is healthy"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        print("✓ Health check passed")
    
    def test_login_success(self):
        """Verify login works"""
        headers = get_auth_headers()
        assert headers is not None
        assert "Authorization" in headers
        print("✓ Login successful")


class TestCommandInterpret:
    """Test POST /api/command/interpret endpoint"""
    
    def test_interpret_quote_command(self):
        """Test interpreting a quote creation command"""
        headers = get_auth_headers()
        response = requests.post(
            f"{BASE_URL}/api/command/interpret",
            headers=headers,
            data={
                "command": "Create a quote for 5000 CHF",
                "context": f'{{"project_id": "{TEST_PROJECT_ID}", "client_id": "{TEST_CLIENT_ID}"}}'
            }
        )
        assert response.status_code == 200, f"Interpret failed: {response.text}"
        data = response.json()
        
        # Verify intent classification
        assert data.get("intent") == "create_quote", f"Expected create_quote intent, got: {data.get('intent')}"
        assert "plan_id" in data
        assert "fields" in data
        assert "is_demo" not in data, "is_demo should NOT be in interpret response"
        print(f"✓ Quote command interpreted: intent={data['intent']}, plan_id={data['plan_id']}")
    
    def test_interpret_invoice_command(self):
        """Test interpreting an invoice creation command"""
        headers = get_auth_headers()
        response = requests.post(
            f"{BASE_URL}/api/command/interpret",
            headers=headers,
            data={
                "command": "Create an invoice for 2500 CHF",
                "context": f'{{"project_id": "{TEST_PROJECT_ID}", "client_id": "{TEST_CLIENT_ID}"}}'
            }
        )
        assert response.status_code == 200, f"Interpret failed: {response.text}"
        data = response.json()
        
        assert data.get("intent") == "create_invoice", f"Expected create_invoice intent, got: {data.get('intent')}"
        assert "is_demo" not in data
        print(f"✓ Invoice command interpreted: intent={data['intent']}")
    
    def test_interpret_message_command(self):
        """Test interpreting a message creation command"""
        headers = get_auth_headers()
        response = requests.post(
            f"{BASE_URL}/api/command/interpret",
            headers=headers,
            data={
                "command": "Send a message saying 'Project update: Phase 1 complete'",
                "context": f'{{"project_id": "{TEST_PROJECT_ID}"}}'
            }
        )
        assert response.status_code == 200, f"Interpret failed: {response.text}"
        data = response.json()
        
        assert data.get("intent") == "create_message", f"Expected create_message intent, got: {data.get('intent')}"
        assert "is_demo" not in data
        print(f"✓ Message command interpreted: intent={data['intent']}")


class TestCommandDraft:
    """Test POST /api/command/draft endpoint"""
    
    def test_create_quote_draft(self):
        """Test creating a draft from a quote plan"""
        headers = get_auth_headers()
        
        # First interpret
        interpret_resp = requests.post(
            f"{BASE_URL}/api/command/interpret",
            headers=headers,
            data={
                "command": "Create a quote for 3000 CHF for kitchen renovation",
                "context": f'{{"project_id": "{TEST_PROJECT_ID}", "client_id": "{TEST_CLIENT_ID}"}}'
            }
        )
        assert interpret_resp.status_code == 200
        plan = interpret_resp.json()
        
        # Create draft
        draft_resp = requests.post(
            f"{BASE_URL}/api/command/draft",
            headers=headers,
            json=plan
        )
        assert draft_resp.status_code == 200, f"Draft creation failed: {draft_resp.text}"
        draft = draft_resp.json()
        
        assert "draft_id" in draft
        assert draft.get("status") == "pending"
        assert draft.get("intent") == "create_quote"
        assert "is_demo" not in draft, "is_demo should NOT be in draft response"
        print(f"✓ Quote draft created: draft_id={draft['draft_id']}, status={draft['status']}")


class TestCommandExecute:
    """Test POST /api/command/execute endpoint - routes to canonical services"""
    
    def _create_draft(self, headers, command, context):
        """Helper to create a draft"""
        interpret_resp = requests.post(
            f"{BASE_URL}/api/command/interpret",
            headers=headers,
            data={"command": command, "context": context}
        )
        assert interpret_resp.status_code == 200
        plan = interpret_resp.json()
        
        draft_resp = requests.post(
            f"{BASE_URL}/api/command/draft",
            headers=headers,
            json=plan
        )
        assert draft_resp.status_code == 200
        return draft_resp.json()
    
    def test_execute_quote_routes_to_document_service(self):
        """Test that executing a quote draft routes to document_service.create_document"""
        headers = get_auth_headers()
        context = f'{{"project_id": "{TEST_PROJECT_ID}", "client_id": "{TEST_CLIENT_ID}"}}'
        draft = self._create_draft(headers, "Create a quote for 4500 CHF for bathroom tiles", context)
        draft_id = draft["draft_id"]
        
        # Execute the draft
        exec_resp = requests.post(
            f"{BASE_URL}/api/command/execute",
            headers=headers,
            json={"draft_id": draft_id, "confirmed": True}
        )
        assert exec_resp.status_code == 200, f"Execute failed: {exec_resp.text}"
        result = exec_resp.json()
        
        assert result.get("status") == "executed"
        assert "result" in result
        assert result["result"].get("type") == "quote"
        assert "id" in result["result"]
        assert "is_demo" not in result, "is_demo should NOT be in execute response"
        assert "is_demo" not in result.get("result", {}), "is_demo should NOT be in result"
        
        doc_id = result["result"]["id"]
        print(f"✓ Quote executed via document_service: document_id={doc_id}")
        
        # Verify document exists in GET /api/documents
        docs_resp = requests.get(f"{BASE_URL}/api/documents", headers=headers)
        assert docs_resp.status_code == 200
        docs = docs_resp.json()
        doc_ids = [d.get("document_id") for d in docs]
        assert doc_id in doc_ids, f"Created document {doc_id} not found in documents list"
        
        # Verify no is_demo in the document
        created_doc = next((d for d in docs if d.get("document_id") == doc_id), None)
        assert created_doc is not None
        assert "is_demo" not in created_doc, "is_demo should NOT be in document"
        print(f"✓ Document verified in GET /api/documents, no is_demo field")
    
    def test_execute_invoice_routes_to_document_service(self):
        """Test that executing an invoice draft routes to document_service.create_document"""
        headers = get_auth_headers()
        context = f'{{"project_id": "{TEST_PROJECT_ID}", "client_id": "{TEST_CLIENT_ID}"}}'
        draft = self._create_draft(headers, "Create an invoice for 7500 CHF for plumbing work", context)
        draft_id = draft["draft_id"]
        
        exec_resp = requests.post(
            f"{BASE_URL}/api/command/execute",
            headers=headers,
            json={"draft_id": draft_id, "confirmed": True}
        )
        assert exec_resp.status_code == 200, f"Execute failed: {exec_resp.text}"
        result = exec_resp.json()
        
        assert result.get("status") == "executed"
        assert result["result"].get("type") == "invoice"
        assert "is_demo" not in result
        assert "is_demo" not in result.get("result", {})
        
        doc_id = result["result"]["id"]
        print(f"✓ Invoice executed via document_service: document_id={doc_id}")
    
    def test_execute_message_routes_to_activity_service(self):
        """Test that executing a message draft routes to activity_service.create_draft_activity"""
        headers = get_auth_headers()
        context = f'{{"project_id": "{TEST_PROJECT_ID}", "client_id": "{TEST_CLIENT_ID}"}}'
        draft = self._create_draft(headers, "Send a message saying 'Construction update: Foundation complete'", context)
        draft_id = draft["draft_id"]
        
        exec_resp = requests.post(
            f"{BASE_URL}/api/command/execute",
            headers=headers,
            json={"draft_id": draft_id, "confirmed": True}
        )
        assert exec_resp.status_code == 200, f"Execute failed: {exec_resp.text}"
        result = exec_resp.json()
        
        assert result.get("status") == "executed"
        assert result["result"].get("type") == "message_draft"
        assert "id" in result["result"]
        assert "is_demo" not in result
        assert "is_demo" not in result.get("result", {})
        
        activity_id = result["result"]["id"]
        print(f"✓ Message executed via activity_service: activity_id={activity_id}")
        
        # Verify activity exists in GET /api/activities
        activities_resp = requests.get(f"{BASE_URL}/api/activities", headers=headers)
        assert activities_resp.status_code == 200
        activities_data = activities_resp.json()
        activities = activities_data.get("activities", [])
        activity_ids = [a.get("activity_id") for a in activities]
        assert activity_id in activity_ids, f"Created activity {activity_id} not found in activities list"
        
        # Verify no is_demo in the activity
        created_activity = next((a for a in activities if a.get("activity_id") == activity_id), None)
        assert created_activity is not None
        assert "is_demo" not in created_activity, "is_demo should NOT be in activity"
        print(f"✓ Activity verified in GET /api/activities, no is_demo field")


class TestDraftIdempotency:
    """Test draft idempotency - executing same draft_id twice returns cached result"""
    
    def test_idempotent_execution(self):
        """Test that executing the same draft twice returns cached result"""
        headers = get_auth_headers()
        
        # Create a draft
        interpret_resp = requests.post(
            f"{BASE_URL}/api/command/interpret",
            headers=headers,
            data={
                "command": "Create a quote for 1500 CHF for idempotency test",
                "context": f'{{"project_id": "{TEST_PROJECT_ID}", "client_id": "{TEST_CLIENT_ID}"}}'
            }
        )
        assert interpret_resp.status_code == 200
        plan = interpret_resp.json()
        
        draft_resp = requests.post(
            f"{BASE_URL}/api/command/draft",
            headers=headers,
            json=plan
        )
        assert draft_resp.status_code == 200
        draft_id = draft_resp.json()["draft_id"]
        
        # First execution
        exec1_resp = requests.post(
            f"{BASE_URL}/api/command/execute",
            headers=headers,
            json={"draft_id": draft_id, "confirmed": True}
        )
        assert exec1_resp.status_code == 200
        result1 = exec1_resp.json()
        assert result1.get("status") == "executed"
        first_doc_id = result1["result"]["id"]
        
        # Second execution - should return cached result
        exec2_resp = requests.post(
            f"{BASE_URL}/api/command/execute",
            headers=headers,
            json={"draft_id": draft_id, "confirmed": True}
        )
        assert exec2_resp.status_code == 200
        result2 = exec2_resp.json()
        assert result2.get("status") == "executed"
        second_doc_id = result2["result"]["id"]
        
        # Should be the same document
        assert first_doc_id == second_doc_id, f"Idempotency failed: {first_doc_id} != {second_doc_id}"
        assert result2["result"].get("already_executed") == True, "Second execution should indicate already_executed"
        print(f"✓ Draft idempotency verified: same document_id={first_doc_id} returned")


class TestDraftCancellation:
    """Test draft cancellation - confirmed=false cancels draft"""
    
    def test_cancel_draft(self):
        """Test that confirmed=false cancels the draft"""
        headers = get_auth_headers()
        
        # Create a draft
        interpret_resp = requests.post(
            f"{BASE_URL}/api/command/interpret",
            headers=headers,
            data={
                "command": "Create a quote for 2000 CHF for cancellation test",
                "context": f'{{"project_id": "{TEST_PROJECT_ID}", "client_id": "{TEST_CLIENT_ID}"}}'
            }
        )
        assert interpret_resp.status_code == 200
        plan = interpret_resp.json()
        
        draft_resp = requests.post(
            f"{BASE_URL}/api/command/draft",
            headers=headers,
            json=plan
        )
        assert draft_resp.status_code == 200
        draft_id = draft_resp.json()["draft_id"]
        
        # Cancel the draft
        cancel_resp = requests.post(
            f"{BASE_URL}/api/command/execute",
            headers=headers,
            json={"draft_id": draft_id, "confirmed": False}
        )
        assert cancel_resp.status_code == 200
        result = cancel_resp.json()
        
        assert result.get("status") == "cancelled"
        assert result.get("draft_id") == draft_id
        print(f"✓ Draft cancellation verified: draft_id={draft_id}, status=cancelled")
        
        # Verify draft status is cancelled
        draft_get_resp = requests.get(
            f"{BASE_URL}/api/command/draft/{draft_id}",
            headers=headers
        )
        assert draft_get_resp.status_code == 200
        draft_data = draft_get_resp.json()
        assert draft_data.get("status") == "cancelled"
        print(f"✓ Draft status confirmed as cancelled in database")


class TestCommandTools:
    """Test GET /api/command/tools endpoint"""
    
    def test_list_tools_returns_7(self):
        """Test that GET /api/command/tools returns 7 tools"""
        headers = get_auth_headers()
        response = requests.get(f"{BASE_URL}/api/command/tools", headers=headers)
        assert response.status_code == 200, f"Tools endpoint failed: {response.text}"
        tools = response.json()
        
        assert isinstance(tools, list)
        assert len(tools) == 7, f"Expected 7 tools, got {len(tools)}: {[t.get('name') for t in tools]}"
        
        tool_names = [t.get("name") for t in tools]
        expected_tools = [
            "create_quote", "create_invoice", "create_message",
            "extract_quote", "extract_invoice", "extract_timeline", "extract_contacts"
        ]
        for expected in expected_tools:
            assert expected in tool_names, f"Missing tool: {expected}"
        
        # Verify no is_demo in tools
        for tool in tools:
            assert "is_demo" not in tool
        
        print(f"✓ GET /api/command/tools returns 7 tools: {tool_names}")


class TestCommandHistory:
    """Test GET /api/command/history endpoint"""
    
    def test_history_no_is_demo(self):
        """Test that GET /api/command/history returns data without is_demo"""
        headers = get_auth_headers()
        response = requests.get(f"{BASE_URL}/api/command/history", headers=headers)
        assert response.status_code == 200, f"History endpoint failed: {response.text}"
        data = response.json()
        
        assert "drafts" in data
        assert "recent_extractions" in data
        
        # Check no is_demo in drafts
        for draft in data.get("drafts", []):
            assert "is_demo" not in draft, f"is_demo found in draft: {draft}"
        
        # Check no is_demo in extractions
        for extraction in data.get("recent_extractions", []):
            assert "is_demo" not in extraction, f"is_demo found in extraction: {extraction}"
        
        print(f"✓ GET /api/command/history: {len(data['drafts'])} drafts, {len(data['recent_extractions'])} extractions, no is_demo")


class TestCommandDrafts:
    """Test GET /api/command/drafts endpoint"""
    
    def test_list_drafts_no_is_demo(self):
        """Test that GET /api/command/drafts returns data without is_demo"""
        headers = get_auth_headers()
        response = requests.get(f"{BASE_URL}/api/command/drafts", headers=headers)
        assert response.status_code == 200, f"Drafts endpoint failed: {response.text}"
        drafts = response.json()
        
        assert isinstance(drafts, list)
        
        for draft in drafts:
            assert "is_demo" not in draft, f"is_demo found in draft: {draft}"
        
        print(f"✓ GET /api/command/drafts: {len(drafts)} drafts, no is_demo")


class TestNotificationCanonicalization:
    """Test notification endpoints - no is_demo field"""
    
    def test_get_notifications_no_is_demo(self):
        """Test that GET /api/notifications returns data without is_demo"""
        headers = get_auth_headers()
        response = requests.get(f"{BASE_URL}/api/notifications", headers=headers)
        assert response.status_code == 200, f"Notifications endpoint failed: {response.text}"
        notifications = response.json()
        
        assert isinstance(notifications, list)
        
        for notif in notifications:
            assert "is_demo" not in notif, f"is_demo found in notification: {notif}"
        
        print(f"✓ GET /api/notifications: {len(notifications)} notifications, no is_demo")
    
    def test_mark_all_read(self):
        """Test PATCH /api/notifications/read-all"""
        headers = get_auth_headers()
        response = requests.patch(f"{BASE_URL}/api/notifications/read-all", headers=headers)
        assert response.status_code == 200, f"Mark all read failed: {response.text}"
        data = response.json()
        
        assert "message" in data or "count" in data
        assert "is_demo" not in data
        print(f"✓ PATCH /api/notifications/read-all: {data}")


class TestNoNotificationBridgeImports:
    """Verify notification_bridge.py is not imported anywhere"""
    
    def test_no_notification_bridge_in_codebase(self):
        """Verify notification_bridge.py doesn't exist and isn't imported"""
        import subprocess
        
        # Check if file exists
        result = subprocess.run(
            ["ls", "-la", "/app/backend/services/notification_bridge.py"],
            capture_output=True, text=True
        )
        assert result.returncode != 0, "notification_bridge.py should NOT exist"
        
        # Check for imports - exclude test files
        result = subprocess.run(
            ["grep", "-r", "--include=*.py", "notification_bridge", "/app/backend/services/", "/app/backend/routes/"],
            capture_output=True, text=True
        )
        # Should find nothing
        assert result.returncode != 0 or result.stdout.strip() == "", f"notification_bridge import found: {result.stdout}"
        
        print("✓ No notification_bridge.py file or imports found in services/routes")


class TestSendMilestoneNotificationSignature:
    """Verify send_milestone_notification no longer takes is_demo parameter"""
    
    def test_send_milestone_notification_no_is_demo_param(self):
        """Verify send_milestone_notification function signature has no is_demo"""
        import subprocess
        
        # Get the function signature
        result = subprocess.run(
            ["grep", "-A", "2", "async def send_milestone_notification", "/app/backend/services/realtime_service.py"],
            capture_output=True, text=True
        )
        assert result.returncode == 0
        signature = result.stdout
        
        assert "is_demo" not in signature, f"is_demo found in send_milestone_notification signature: {signature}"
        print(f"✓ send_milestone_notification signature has no is_demo parameter")


class TestDocumentsCreatedViaCommandVisible:
    """Test that documents created via command/execute are visible in GET /api/documents"""
    
    def test_command_created_document_in_documents_list(self):
        """Verify document created via command is in documents list"""
        headers = get_auth_headers()
        
        # Create via command
        interpret_resp = requests.post(
            f"{BASE_URL}/api/command/interpret",
            headers=headers,
            data={
                "command": "Create a quote for 8888 CHF for visibility test",
                "context": f'{{"project_id": "{TEST_PROJECT_ID}", "client_id": "{TEST_CLIENT_ID}"}}'
            }
        )
        assert interpret_resp.status_code == 200
        plan = interpret_resp.json()
        
        draft_resp = requests.post(
            f"{BASE_URL}/api/command/draft",
            headers=headers,
            json=plan
        )
        assert draft_resp.status_code == 200
        draft_id = draft_resp.json()["draft_id"]
        
        exec_resp = requests.post(
            f"{BASE_URL}/api/command/execute",
            headers=headers,
            json={"draft_id": draft_id, "confirmed": True}
        )
        assert exec_resp.status_code == 200
        doc_id = exec_resp.json()["result"]["id"]
        
        # Verify in documents list
        docs_resp = requests.get(f"{BASE_URL}/api/documents", headers=headers)
        assert docs_resp.status_code == 200
        docs = docs_resp.json()
        
        doc_ids = [d.get("document_id") for d in docs]
        assert doc_id in doc_ids, f"Document {doc_id} not found in GET /api/documents"
        
        # Verify no is_demo
        created_doc = next((d for d in docs if d.get("document_id") == doc_id), None)
        assert "is_demo" not in created_doc
        
        print(f"✓ Document {doc_id} visible in GET /api/documents, no is_demo")


class TestActivitiesCreatedViaCommandQueryable:
    """Test that activities created via command/execute are queryable via GET /api/activities"""
    
    def test_command_created_activity_in_activities_list(self):
        """Verify activity created via command is in activities list"""
        headers = get_auth_headers()
        
        # Create via command
        interpret_resp = requests.post(
            f"{BASE_URL}/api/command/interpret",
            headers=headers,
            data={
                "command": "Send a message saying 'Activity visibility test message'",
                "context": f'{{"project_id": "{TEST_PROJECT_ID}", "client_id": "{TEST_CLIENT_ID}"}}'
            }
        )
        assert interpret_resp.status_code == 200
        plan = interpret_resp.json()
        
        draft_resp = requests.post(
            f"{BASE_URL}/api/command/draft",
            headers=headers,
            json=plan
        )
        assert draft_resp.status_code == 200
        draft_id = draft_resp.json()["draft_id"]
        
        exec_resp = requests.post(
            f"{BASE_URL}/api/command/execute",
            headers=headers,
            json={"draft_id": draft_id, "confirmed": True}
        )
        assert exec_resp.status_code == 200
        activity_id = exec_resp.json()["result"]["id"]
        
        # Verify in activities list
        activities_resp = requests.get(f"{BASE_URL}/api/activities", headers=headers)
        assert activities_resp.status_code == 200
        activities_data = activities_resp.json()
        activities = activities_data.get("activities", [])
        
        activity_ids = [a.get("activity_id") for a in activities]
        assert activity_id in activity_ids, f"Activity {activity_id} not found in GET /api/activities"
        
        # Verify no is_demo
        created_activity = next((a for a in activities if a.get("activity_id") == activity_id), None)
        assert "is_demo" not in created_activity
        
        print(f"✓ Activity {activity_id} visible in GET /api/activities, no is_demo")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
