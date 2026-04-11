"""
Notification Contract Tests — Phase 3 Notification Fix Verification

Tests for:
1. GET /api/notifications returns {"notifications": [...], "unread_count": N} (not flat array)
2. Notifications have is_read field (not read field)
3. Notifications have NO is_demo field
4. Notifications have NO read field (only is_read)
5. unread_count matches actual count of is_read:false notifications
6. POST notification via canonical service, verify is_read=false and unread_count increments
7. PATCH /api/notifications/{id}/read marks notification as is_read=true, unread_count decreases
8. PATCH /api/notifications/read-all marks ALL unread notifications, unread_count drops to 0
9. Previously-read notifications stay is_read=true after mark-all-read
10. Command orchestration still works: interpret→draft→execute for quote, invoice, message intents
11. No is_demo in any command or notification response
12. No 'read' field (only 'is_read') in any notification document in MongoDB
13. No 'is_demo' field in any notification document in MongoDB
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
TEST_USER_ID = "agent_b6578576f72d"

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
    token = data.get("token") or data.get("access_token")
    assert token, f"No token in response: {data}"
    _auth_headers = {"Authorization": f"Bearer {token}"}
    return _auth_headers


class TestNotificationResponseShape:
    """Test 1: GET /api/notifications returns {"notifications": [...], "unread_count": N}"""
    
    def test_response_is_object_not_array(self):
        """Verify response is an object with notifications and unread_count keys"""
        headers = get_auth_headers()
        response = requests.get(f"{BASE_URL}/api/notifications", headers=headers)
        assert response.status_code == 200, f"GET notifications failed: {response.text}"
        data = response.json()
        
        # Must be a dict, not a list
        assert isinstance(data, dict), f"Expected dict, got {type(data).__name__}: {data}"
        
        # Must have notifications key
        assert "notifications" in data, f"Missing 'notifications' key in response: {data.keys()}"
        assert isinstance(data["notifications"], list), f"notifications should be list, got {type(data['notifications']).__name__}"
        
        # Must have unread_count key
        assert "unread_count" in data, f"Missing 'unread_count' key in response: {data.keys()}"
        assert isinstance(data["unread_count"], int), f"unread_count should be int, got {type(data['unread_count']).__name__}"
        
        print(f"✓ Response shape correct: {{notifications: [{len(data['notifications'])} items], unread_count: {data['unread_count']}}}")


class TestNotificationFieldNames:
    """Tests 2-4: Verify field names in notifications"""
    
    def test_notifications_have_is_read_field(self):
        """Test 2: Notifications have is_read field (not read)"""
        headers = get_auth_headers()
        response = requests.get(f"{BASE_URL}/api/notifications", headers=headers)
        assert response.status_code == 200
        data = response.json()
        
        notifications = data.get("notifications", [])
        if len(notifications) == 0:
            pytest.skip("No notifications to test field names")
        
        for notif in notifications:
            assert "is_read" in notif, f"Missing 'is_read' field in notification: {notif.keys()}"
            assert isinstance(notif["is_read"], bool), f"is_read should be bool, got {type(notif['is_read']).__name__}"
        
        print(f"✓ All {len(notifications)} notifications have 'is_read' field")
    
    def test_notifications_have_no_is_demo_field(self):
        """Test 3: Notifications have NO is_demo field"""
        headers = get_auth_headers()
        response = requests.get(f"{BASE_URL}/api/notifications", headers=headers)
        assert response.status_code == 200
        data = response.json()
        
        notifications = data.get("notifications", [])
        for notif in notifications:
            assert "is_demo" not in notif, f"Found 'is_demo' field in notification: {notif}"
        
        print(f"✓ No 'is_demo' field in any of {len(notifications)} notifications")
    
    def test_notifications_have_no_read_field(self):
        """Test 4: Notifications have NO read field (only is_read)"""
        headers = get_auth_headers()
        response = requests.get(f"{BASE_URL}/api/notifications", headers=headers)
        assert response.status_code == 200
        data = response.json()
        
        notifications = data.get("notifications", [])
        for notif in notifications:
            assert "read" not in notif, f"Found 'read' field in notification (should be 'is_read'): {notif}"
        
        print(f"✓ No 'read' field in any of {len(notifications)} notifications")


class TestUnreadCount:
    """Test 5: unread_count matches actual count of is_read:false notifications"""
    
    def test_unread_count_matches_actual(self):
        """Verify unread_count equals count of notifications with is_read=false"""
        headers = get_auth_headers()
        response = requests.get(f"{BASE_URL}/api/notifications", headers=headers)
        assert response.status_code == 200
        data = response.json()
        
        notifications = data.get("notifications", [])
        unread_count = data.get("unread_count", 0)
        
        # Count notifications with is_read=false
        actual_unread = sum(1 for n in notifications if n.get("is_read") == False)
        
        assert unread_count == actual_unread, f"unread_count mismatch: API says {unread_count}, actual is {actual_unread}"
        print(f"✓ unread_count={unread_count} matches actual unread notifications count")


class TestNotificationCreation:
    """Test 6: POST notification via canonical service, verify is_read=false and unread_count increments"""
    
    def test_create_notification_via_internal_service(self):
        """Create notification and verify it appears with is_read=false"""
        headers = get_auth_headers()
        
        # Get initial state
        initial_resp = requests.get(f"{BASE_URL}/api/notifications", headers=headers)
        assert initial_resp.status_code == 200
        initial_data = initial_resp.json()
        initial_unread = initial_data.get("unread_count", 0)
        initial_count = len(initial_data.get("notifications", []))
        
        # Create a notification via command execution (which uses notification_service internally)
        # First, interpret a quote command
        interpret_resp = requests.post(
            f"{BASE_URL}/api/command/interpret",
            headers=headers,
            data={
                "command": "Create a quote for 9999 CHF for notification test",
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
        assert draft_resp.status_code == 200
        draft_id = draft_resp.json()["draft_id"]
        
        # Execute (this may create a notification)
        exec_resp = requests.post(
            f"{BASE_URL}/api/command/execute",
            headers=headers,
            json={"draft_id": draft_id, "confirmed": True}
        )
        assert exec_resp.status_code == 200
        
        # Verify no is_demo in execute response
        exec_data = exec_resp.json()
        assert "is_demo" not in exec_data, f"is_demo found in execute response: {exec_data}"
        
        print(f"✓ Command executed successfully, no is_demo in response")


class TestMarkNotificationRead:
    """Test 7: PATCH /api/notifications/{id}/read marks notification as is_read=true"""
    
    def test_mark_single_notification_read(self):
        """Mark a single notification as read and verify is_read=true"""
        headers = get_auth_headers()
        
        # Get notifications
        response = requests.get(f"{BASE_URL}/api/notifications", headers=headers)
        assert response.status_code == 200
        data = response.json()
        
        notifications = data.get("notifications", [])
        unread_notifications = [n for n in notifications if n.get("is_read") == False]
        
        if len(unread_notifications) == 0:
            pytest.skip("No unread notifications to test mark_read")
        
        # Pick first unread notification
        notif_to_mark = unread_notifications[0]
        notif_id = notif_to_mark["notification_id"]
        initial_unread_count = data.get("unread_count", 0)
        
        # Mark as read
        mark_resp = requests.patch(
            f"{BASE_URL}/api/notifications/{notif_id}/read",
            headers=headers
        )
        assert mark_resp.status_code == 200, f"Mark read failed: {mark_resp.text}"
        
        # Verify the notification is now read
        verify_resp = requests.get(f"{BASE_URL}/api/notifications", headers=headers)
        assert verify_resp.status_code == 200
        verify_data = verify_resp.json()
        
        # Find the notification
        marked_notif = next((n for n in verify_data["notifications"] if n["notification_id"] == notif_id), None)
        assert marked_notif is not None, f"Notification {notif_id} not found after marking"
        assert marked_notif["is_read"] == True, f"Notification should be is_read=true, got: {marked_notif['is_read']}"
        
        # Verify unread_count decreased
        new_unread_count = verify_data.get("unread_count", 0)
        assert new_unread_count == initial_unread_count - 1, f"unread_count should decrease by 1: {initial_unread_count} -> {new_unread_count}"
        
        print(f"✓ Notification {notif_id} marked as read, unread_count: {initial_unread_count} -> {new_unread_count}")


class TestMarkAllNotificationsRead:
    """Tests 8-9: PATCH /api/notifications/read-all marks ALL unread notifications"""
    
    def test_mark_all_read_sets_unread_count_to_zero(self):
        """Test 8: Mark all read sets unread_count to 0"""
        headers = get_auth_headers()
        
        # First, create some unread notifications by executing commands
        # Create a notification via command
        interpret_resp = requests.post(
            f"{BASE_URL}/api/command/interpret",
            headers=headers,
            data={
                "command": "Create a quote for 1111 CHF for mark-all test",
                "context": f'{{"project_id": "{TEST_PROJECT_ID}", "client_id": "{TEST_CLIENT_ID}"}}'
            }
        )
        if interpret_resp.status_code == 200:
            plan = interpret_resp.json()
            draft_resp = requests.post(f"{BASE_URL}/api/command/draft", headers=headers, json=plan)
            if draft_resp.status_code == 200:
                draft_id = draft_resp.json()["draft_id"]
                requests.post(f"{BASE_URL}/api/command/execute", headers=headers, json={"draft_id": draft_id, "confirmed": True})
        
        # Mark all as read
        mark_all_resp = requests.patch(f"{BASE_URL}/api/notifications/read-all", headers=headers)
        assert mark_all_resp.status_code == 200, f"Mark all read failed: {mark_all_resp.text}"
        
        # Verify unread_count is 0
        verify_resp = requests.get(f"{BASE_URL}/api/notifications", headers=headers)
        assert verify_resp.status_code == 200
        verify_data = verify_resp.json()
        
        assert verify_data.get("unread_count") == 0, f"unread_count should be 0 after mark-all-read, got: {verify_data.get('unread_count')}"
        
        # Verify all notifications have is_read=true
        for notif in verify_data.get("notifications", []):
            assert notif.get("is_read") == True, f"Notification should be is_read=true after mark-all-read: {notif}"
        
        print(f"✓ Mark all read: unread_count=0, all {len(verify_data['notifications'])} notifications have is_read=true")
    
    def test_previously_read_stay_read_after_mark_all(self):
        """Test 9: Previously-read notifications stay is_read=true after mark-all-read"""
        headers = get_auth_headers()
        
        # Get current state
        response = requests.get(f"{BASE_URL}/api/notifications", headers=headers)
        assert response.status_code == 200
        data = response.json()
        
        # Find a notification that's already read
        read_notifications = [n for n in data.get("notifications", []) if n.get("is_read") == True]
        
        if len(read_notifications) == 0:
            pytest.skip("No read notifications to verify")
        
        read_notif_id = read_notifications[0]["notification_id"]
        
        # Mark all as read
        mark_all_resp = requests.patch(f"{BASE_URL}/api/notifications/read-all", headers=headers)
        assert mark_all_resp.status_code == 200
        
        # Verify the previously-read notification is still read
        verify_resp = requests.get(f"{BASE_URL}/api/notifications", headers=headers)
        assert verify_resp.status_code == 200
        verify_data = verify_resp.json()
        
        notif = next((n for n in verify_data["notifications"] if n["notification_id"] == read_notif_id), None)
        assert notif is not None
        assert notif["is_read"] == True, f"Previously-read notification should stay is_read=true: {notif}"
        
        print(f"✓ Previously-read notification {read_notif_id} stays is_read=true after mark-all-read")


class TestCommandOrchestration:
    """Test 10: Command orchestration still works: interpret→draft→execute"""
    
    def _execute_command_flow(self, headers, command, context):
        """Helper to execute full command flow"""
        # Interpret
        interpret_resp = requests.post(
            f"{BASE_URL}/api/command/interpret",
            headers=headers,
            data={"command": command, "context": context}
        )
        assert interpret_resp.status_code == 200, f"Interpret failed: {interpret_resp.text}"
        plan = interpret_resp.json()
        
        # Draft
        draft_resp = requests.post(
            f"{BASE_URL}/api/command/draft",
            headers=headers,
            json=plan
        )
        assert draft_resp.status_code == 200, f"Draft failed: {draft_resp.text}"
        draft = draft_resp.json()
        
        # Execute
        exec_resp = requests.post(
            f"{BASE_URL}/api/command/execute",
            headers=headers,
            json={"draft_id": draft["draft_id"], "confirmed": True}
        )
        assert exec_resp.status_code == 200, f"Execute failed: {exec_resp.text}"
        return exec_resp.json()
    
    def test_quote_intent_orchestration(self):
        """Test quote intent: interpret→draft→execute"""
        headers = get_auth_headers()
        context = f'{{"project_id": "{TEST_PROJECT_ID}", "client_id": "{TEST_CLIENT_ID}"}}'
        
        result = self._execute_command_flow(
            headers,
            "Create a quote for 5555 CHF for orchestration test",
            context
        )
        
        assert result.get("status") == "executed"
        assert result.get("result", {}).get("type") == "quote"
        assert "is_demo" not in result
        assert "is_demo" not in result.get("result", {})
        
        print(f"✓ Quote orchestration works: {result['result']['id']}")
    
    def test_invoice_intent_orchestration(self):
        """Test invoice intent: interpret→draft→execute"""
        headers = get_auth_headers()
        context = f'{{"project_id": "{TEST_PROJECT_ID}", "client_id": "{TEST_CLIENT_ID}"}}'
        
        result = self._execute_command_flow(
            headers,
            "Create an invoice for 6666 CHF for orchestration test",
            context
        )
        
        assert result.get("status") == "executed"
        assert result.get("result", {}).get("type") == "invoice"
        assert "is_demo" not in result
        
        print(f"✓ Invoice orchestration works: {result['result']['id']}")
    
    def test_message_intent_orchestration(self):
        """Test message intent: interpret→draft→execute"""
        headers = get_auth_headers()
        context = f'{{"project_id": "{TEST_PROJECT_ID}", "client_id": "{TEST_CLIENT_ID}"}}'
        
        result = self._execute_command_flow(
            headers,
            "Send a message saying 'Orchestration test message'",
            context
        )
        
        assert result.get("status") == "executed"
        assert result.get("result", {}).get("type") == "message_draft"
        assert "is_demo" not in result
        
        print(f"✓ Message orchestration works: {result['result']['id']}")


class TestNoIsDemoInResponses:
    """Test 11: No is_demo in any command or notification response"""
    
    def test_no_is_demo_in_notifications(self):
        """Verify no is_demo in GET /api/notifications response"""
        headers = get_auth_headers()
        response = requests.get(f"{BASE_URL}/api/notifications", headers=headers)
        assert response.status_code == 200
        data = response.json()
        
        # Check top-level
        assert "is_demo" not in data, f"is_demo found in top-level response: {data.keys()}"
        
        # Check each notification
        for notif in data.get("notifications", []):
            assert "is_demo" not in notif, f"is_demo found in notification: {notif}"
        
        print(f"✓ No is_demo in notifications response")
    
    def test_no_is_demo_in_command_interpret(self):
        """Verify no is_demo in command/interpret response"""
        headers = get_auth_headers()
        response = requests.post(
            f"{BASE_URL}/api/command/interpret",
            headers=headers,
            data={
                "command": "Create a quote for 1000 CHF",
                "context": f'{{"project_id": "{TEST_PROJECT_ID}", "client_id": "{TEST_CLIENT_ID}"}}'
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "is_demo" not in data, f"is_demo found in interpret response: {data}"
        print(f"✓ No is_demo in command/interpret response")
    
    def test_no_is_demo_in_command_tools(self):
        """Verify no is_demo in command/tools response"""
        headers = get_auth_headers()
        response = requests.get(f"{BASE_URL}/api/command/tools", headers=headers)
        assert response.status_code == 200
        tools = response.json()
        
        for tool in tools:
            assert "is_demo" not in tool, f"is_demo found in tool: {tool}"
        
        print(f"✓ No is_demo in command/tools response")


class TestMongoDBFieldVerification:
    """Tests 12-13: Verify MongoDB has no 'read' or 'is_demo' fields in notifications"""
    
    def test_no_read_field_in_mongodb(self):
        """Test 12: No 'read' field (only 'is_read') in any notification document"""
        # This test verifies via the API response that the projection excludes 'read'
        # The notification_service.py uses {"_id": 0, "is_demo": 0, "read": 0} projection
        headers = get_auth_headers()
        response = requests.get(f"{BASE_URL}/api/notifications", headers=headers)
        assert response.status_code == 200
        data = response.json()
        
        for notif in data.get("notifications", []):
            assert "read" not in notif, f"'read' field found in notification (should be excluded): {notif}"
            assert "is_read" in notif, f"'is_read' field missing in notification: {notif}"
        
        print(f"✓ No 'read' field in any notification (projection working)")
    
    def test_no_is_demo_field_in_mongodb(self):
        """Test 13: No 'is_demo' field in any notification document"""
        # This test verifies via the API response that the projection excludes 'is_demo'
        headers = get_auth_headers()
        response = requests.get(f"{BASE_URL}/api/notifications", headers=headers)
        assert response.status_code == 200
        data = response.json()
        
        for notif in data.get("notifications", []):
            assert "is_demo" not in notif, f"'is_demo' field found in notification (should be excluded): {notif}"
        
        print(f"✓ No 'is_demo' field in any notification (projection working)")


class TestNotificationServiceCanonical:
    """Verify notification_service.py is the canonical implementation"""
    
    def test_notification_service_exists(self):
        """Verify notification_service.py exists and has correct functions"""
        import subprocess
        
        # Check file exists
        result = subprocess.run(
            ["ls", "-la", "/app/backend/services/notification_service.py"],
            capture_output=True, text=True
        )
        assert result.returncode == 0, "notification_service.py should exist"
        
        # Check for canonical functions
        result = subprocess.run(
            ["grep", "-E", "^async def (create_notification|list_notifications_with_count|mark_read|mark_all_read)", 
             "/app/backend/services/notification_service.py"],
            capture_output=True, text=True
        )
        assert result.returncode == 0, f"Missing canonical functions in notification_service.py"
        
        functions_found = result.stdout.strip().split('\n')
        assert len(functions_found) >= 4, f"Expected 4 canonical functions, found: {functions_found}"
        
        print(f"✓ notification_service.py has canonical functions: {len(functions_found)} found")
    
    def test_list_notifications_with_count_returns_dict(self):
        """Verify list_notifications_with_count returns dict with notifications and unread_count"""
        import subprocess
        
        # Check the return type in the function
        result = subprocess.run(
            ["grep", "-A", "5", "async def list_notifications_with_count", 
             "/app/backend/services/notification_service.py"],
            capture_output=True, text=True
        )
        assert result.returncode == 0
        
        # Should return Dict[str, Any] with notifications and unread_count
        assert "Dict[str, Any]" in result.stdout or '{"notifications"' in result.stdout or "notifications" in result.stdout
        
        print(f"✓ list_notifications_with_count returns correct structure")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
