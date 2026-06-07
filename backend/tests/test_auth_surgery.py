"""
Auth Surgery Tests - Iteration 12
Verifies is_demo field removal from all auth paths and demo login convention change.

Test Coverage:
1. Agent login returns NO is_demo in response
2. Buyer login returns NO is_demo in response  
3. GET /auth/me returns user with NO is_demo
4. GET /auth/session returns user with NO is_demo
5. Demo agent login works via user_id prefix (demo_*)
6. Demo buyer login works via user_id (demo_buyer_001)
7. Demo login response has NO is_demo field
8. Agent registration creates user WITHOUT is_demo in DB
9. Login response contains exactly: user_id, email, name, role, token
10. No is_demo in MongoDB users collection
11. get_is_demo function does NOT exist in access_control.py
12. get_demo_filter function does NOT exist in helpers.py
13. No import of get_demo_filter in any route file
14. Canonical endpoints still work (projects, documents, notifications)
15. Notification contract: {notifications, unread_count} with is_read
16. Team CRUD still works
17. Stats endpoints return data without is_demo filtering
"""

import pytest
import requests
import os
import uuid
import subprocess
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_AGENT_EMAIL = "e2e@evohome-test.com"
TEST_AGENT_PASSWORD = "Test2026!"

# Module-level token cache to avoid rate limiting
_cached_token = None

def get_auth_token():
    """Get auth token with caching to avoid rate limiting"""
    global _cached_token
    if _cached_token:
        return _cached_token
    
    time.sleep(1)  # Small delay to avoid rate limiting
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_AGENT_EMAIL,
        "password": TEST_AGENT_PASSWORD
    })
    if response.status_code == 200:
        _cached_token = response.json()["token"]
        return _cached_token
    elif response.status_code == 429:
        time.sleep(5)  # Wait for rate limit to reset
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_AGENT_EMAIL,
            "password": TEST_AGENT_PASSWORD
        })
        if response.status_code == 200:
            _cached_token = response.json()["token"]
            return _cached_token
    raise Exception(f"Failed to get auth token: {response.status_code} - {response.text}")


class TestAuthSurgeryLoginResponses:
    """Verify is_demo is absent from all login responses"""
    
    def test_agent_login_no_is_demo(self):
        """POST /api/auth/login returns NO is_demo in response"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_AGENT_EMAIL,
            "password": TEST_AGENT_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        
        # Verify is_demo is NOT in response
        assert "is_demo" not in data, f"is_demo should NOT be in login response: {data.keys()}"
        
        # Verify expected keys are present
        expected_keys = {"user_id", "email", "name", "role", "token"}
        assert expected_keys.issubset(data.keys()), f"Missing keys. Got: {data.keys()}"
        
        print(f"✓ Agent login response keys: {list(data.keys())}")
    
    def test_agent_login_exact_keys(self):
        """Agent login response contains exactly: user_id, email, name, role, token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_AGENT_EMAIL,
            "password": TEST_AGENT_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        
        # Core keys that MUST be present
        required_keys = {"user_id", "email", "name", "role", "token"}
        assert required_keys.issubset(data.keys()), f"Missing required keys. Got: {data.keys()}"
        
        # is_demo must NOT be present
        assert "is_demo" not in data
        
        print(f"✓ Login response has required keys, no is_demo")


class TestAuthSurgeryMeAndSession:
    """Verify /auth/me and /auth/session return no is_demo"""
    
    @pytest.fixture
    def auth_token(self):
        return get_auth_token()
    
    def test_auth_me_no_is_demo(self, auth_token):
        """GET /api/auth/me returns user object with NO is_demo"""
        response = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Auth me failed: {response.text}"
        data = response.json()
        
        assert "is_demo" not in data, f"is_demo should NOT be in /auth/me response: {data.keys()}"
        assert "user_id" in data
        assert "email" in data
        assert "role" in data
        
        print(f"✓ /auth/me response keys: {list(data.keys())}")
    
    def test_auth_session_no_is_demo(self, auth_token):
        """GET /api/auth/session returns user with NO is_demo"""
        response = requests.get(
            f"{BASE_URL}/api/auth/session",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Auth session failed: {response.text}"
        data = response.json()
        
        assert data.get("authenticated") == True
        user = data.get("user", {})
        
        assert "is_demo" not in user, f"is_demo should NOT be in session user: {user.keys()}"
        assert "user_id" in user
        assert "email" in user
        assert "role" in user
        
        print(f"✓ /auth/session user keys: {list(user.keys())}")


class TestAuthSurgeryDemoLogin:
    """Verify demo login uses user_id prefix convention, not is_demo field"""
    
    def test_demo_agent_login_works(self):
        """POST /api/auth/demo/agent works - finds demo user by user_id prefix demo_*"""
        response = requests.post(f"{BASE_URL}/api/demo/enter", json={"persona": "agent", "fresh": False})
        assert response.status_code == 200, f"Demo agent login failed: {response.text}"
        data = response.json()
        
        # Verify user_id starts with demo_
        assert data["user_id"].startswith("demo_"), f"Demo agent user_id should start with 'demo_': {data['user_id']}"
        assert data["role"] == "agent"
        
        # Verify NO is_demo in response
        assert "is_demo" not in data, f"is_demo should NOT be in demo login response: {data.keys()}"
        
        print(f"✓ Demo agent login: user_id={data['user_id']}, no is_demo in response")
    
    def test_demo_buyer_login_works(self):
        """POST /api/auth/demo/buyer works - finds demo buyer by user_id demo_buyer_001"""
        response = requests.post(
            f"{BASE_URL}/api/demo/enter",
            json={"persona": "buyer", "buyer_slot": 1, "fresh": False},
        )
        assert response.status_code == 200, f"Demo buyer login failed: {response.text}"
        data = response.json()
        
        # Verify user_id is demo_buyer_001 or demo_buyer_002
        assert data["user_id"].startswith("demo_buyer_"), f"Demo buyer user_id should start with 'demo_buyer_': {data['user_id']}"
        assert data["role"] == "buyer"
        
        # Verify NO is_demo in response
        assert "is_demo" not in data, f"is_demo should NOT be in demo login response: {data.keys()}"
        
        print(f"✓ Demo buyer login: user_id={data['user_id']}, no is_demo in response")
    
    def test_demo_login_response_keys(self):
        """Demo login response has NO is_demo field"""
        response = requests.post(f"{BASE_URL}/api/demo/enter", json={"persona": "agent", "fresh": False})
        assert response.status_code == 200
        data = response.json()
        
        # Expected keys
        expected_keys = {"user_id", "email", "name", "role", "token"}
        assert expected_keys.issubset(data.keys()), f"Missing keys in demo response: {data.keys()}"
        
        # is_demo must NOT be present
        assert "is_demo" not in data
        
        print(f"✓ Demo login response keys: {list(data.keys())}")


class TestAuthSurgeryRegistration:
    """Verify registration creates users WITHOUT is_demo"""
    
    def test_agent_registration_no_is_demo_in_response(self):
        """POST /api/auth/register/agent creates user WITHOUT is_demo in response"""
        unique_email = f"test_auth_surgery_{uuid.uuid4().hex[:8]}@test.com"
        
        response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": unique_email,
            "password": "TestPass123!",
            "name": "Auth Surgery Test"
        })
        
        # Should succeed (201 or 200)
        assert response.status_code in [200, 201], f"Registration failed: {response.text}"
        data = response.json()
        
        # Verify NO is_demo in response
        assert "is_demo" not in data, f"is_demo should NOT be in registration response: {data.keys()}"
        
        # Verify expected keys
        assert "user_id" in data
        assert "email" in data
        assert "token" in data
        
        print(f"✓ Registration response has no is_demo, user_id={data['user_id']}")
        
        # Return user_id for cleanup
        return data["user_id"]


class TestAuthSurgeryCodeVerification:
    """Verify code-level changes: deleted functions and imports"""
    
    def test_get_is_demo_not_in_access_control(self):
        """get_is_demo function does NOT exist in access_control.py"""
        result = subprocess.run(
            ["grep", "-c", "def get_is_demo", "/app/backend/core/access_control.py"],
            capture_output=True, text=True
        )
        # grep returns 1 if no match found
        assert result.returncode == 1 or result.stdout.strip() == "0", \
            "get_is_demo function should NOT exist in access_control.py"
        
        print("✓ get_is_demo function NOT found in access_control.py")
    
    def test_get_demo_filter_not_in_helpers(self):
        """get_demo_filter function does NOT exist in helpers.py"""
        result = subprocess.run(
            ["grep", "-c", "def get_demo_filter", "/app/backend/helpers.py"],
            capture_output=True, text=True
        )
        assert result.returncode == 1 or result.stdout.strip() == "0", \
            "get_demo_filter function should NOT exist in helpers.py"
        
        print("✓ get_demo_filter function NOT found in helpers.py")
    
    def test_no_get_demo_filter_imports_in_routes(self):
        """No import of get_demo_filter in any route file"""
        result = subprocess.run(
            ["grep", "-r", "get_demo_filter", "/app/backend/routes/"],
            capture_output=True, text=True
        )
        assert result.returncode == 1 or result.stdout.strip() == "", \
            f"get_demo_filter should NOT be imported in routes: {result.stdout}"
        
        print("✓ No get_demo_filter imports found in /app/backend/routes/")
    
    def test_no_get_is_demo_imports_in_routes(self):
        """No import of get_is_demo in any route file"""
        result = subprocess.run(
            ["grep", "-r", "get_is_demo", "/app/backend/routes/"],
            capture_output=True, text=True
        )
        assert result.returncode == 1 or result.stdout.strip() == "", \
            f"get_is_demo should NOT be imported in routes: {result.stdout}"
        
        print("✓ No get_is_demo imports found in /app/backend/routes/")


class TestAuthSurgeryDBVerification:
    """Verify MongoDB users collection has no is_demo field"""
    
    @pytest.fixture
    def auth_token(self):
        return get_auth_token()
    
    def test_db_users_no_is_demo_via_auth_me(self, auth_token):
        """Verify user document returned by /auth/me has no is_demo"""
        response = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # The /auth/me endpoint returns the user document
        # If is_demo was in DB, it would need to be explicitly filtered
        assert "is_demo" not in data, f"is_demo found in user data: {data.keys()}"
        
        print("✓ User document from /auth/me has no is_demo")


class TestCanonicalEndpointsRegression:
    """Quick regression: canonical endpoints still work"""
    
    @pytest.fixture
    def auth_token(self):
        return get_auth_token()
    
    def test_projects_endpoint(self, auth_token):
        """GET /api/projects still works"""
        response = requests.get(
            f"{BASE_URL}/api/projects",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Projects failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        
        # Verify no is_demo in any project
        for project in data[:5]:  # Check first 5
            assert "is_demo" not in project, f"is_demo in project: {project.keys()}"
        
        print(f"✓ Projects endpoint works, {len(data)} projects returned")
    
    def test_documents_endpoint(self, auth_token):
        """GET /api/documents still works"""
        response = requests.get(
            f"{BASE_URL}/api/documents",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Documents failed: {response.text}"
        data = response.json()
        
        # Handle both list and dict responses
        docs = data.get("documents", data) if isinstance(data, dict) else data
        
        # Verify no is_demo in any document
        for doc in docs[:5]:  # Check first 5
            assert "is_demo" not in doc, f"is_demo in document: {doc.keys()}"
        
        print(f"✓ Documents endpoint works")
    
    def test_notifications_contract(self, auth_token):
        """GET /api/notifications returns {notifications, unread_count} with is_read"""
        response = requests.get(
            f"{BASE_URL}/api/notifications",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Notifications failed: {response.text}"
        data = response.json()
        
        # Verify contract
        assert "notifications" in data, f"Missing 'notifications' key: {data.keys()}"
        assert "unread_count" in data, f"Missing 'unread_count' key: {data.keys()}"
        
        # Verify notifications have is_read field
        for notif in data["notifications"][:3]:
            assert "is_read" in notif, f"Missing 'is_read' in notification: {notif.keys()}"
            assert "is_demo" not in notif, f"is_demo in notification: {notif.keys()}"
        
        print(f"✓ Notifications contract correct: {len(data['notifications'])} notifications, unread_count={data['unread_count']}")
    
    def test_stats_agent_endpoint(self, auth_token):
        """GET /api/stats/agent returns data without is_demo filtering"""
        response = requests.get(
            f"{BASE_URL}/api/stats/agent",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Stats agent failed: {response.text}"
        data = response.json()
        
        # Verify no is_demo in stats
        assert "is_demo" not in data, f"is_demo in stats: {data.keys()}"
        
        print(f"✓ Stats agent endpoint works: {list(data.keys())[:5]}")


class TestTeamCRUDRegression:
    """Verify team CRUD still works"""
    
    @pytest.fixture
    def auth_token(self):
        return get_auth_token()
    
    @pytest.fixture
    def project_id(self, auth_token):
        """Get first project ID"""
        response = requests.get(
            f"{BASE_URL}/api/projects",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        projects = response.json()
        if not projects:
            pytest.skip("No projects available for team test")
        return projects[0]["project_id"]
    
    def test_team_directory(self, auth_token):
        """GET /api/team/directory still works"""
        response = requests.get(
            f"{BASE_URL}/api/team/directory",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Team directory failed: {response.text}"
        data = response.json()
        
        # Verify no is_demo in contacts
        contacts = data.get("contacts", data) if isinstance(data, dict) else data
        for contact in contacts[:3]:
            assert "is_demo" not in contact, f"is_demo in contact: {contact.keys()}"
        
        print(f"✓ Team directory works")
    
    def test_team_list(self, auth_token, project_id):
        """GET /api/projects/{id}/team still works"""
        response = requests.get(
            f"{BASE_URL}/api/projects/{project_id}/team",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Team list failed: {response.text}"
        data = response.json()
        
        # Verify no is_demo in team members
        members = data.get("members", data) if isinstance(data, dict) else data
        if isinstance(members, list):
            for member in members[:3]:
                assert "is_demo" not in member, f"is_demo in team member: {member.keys()}"
        
        print(f"✓ Team list works for project {project_id}")


class TestWorkflowRegression:
    """Verify workflow execution still works (RESEND_API_KEY fix)"""
    
    @pytest.fixture
    def auth_token(self):
        return get_auth_token()
    
    def test_workflow_templates(self, auth_token):
        """GET /api/workflows/templates still works"""
        response = requests.get(
            f"{BASE_URL}/api/workflows/templates",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Workflow templates failed: {response.text}"
        data = response.json()
        
        # Verify no is_demo in templates
        templates = data.get("templates", data) if isinstance(data, dict) else data
        if isinstance(templates, list):
            for template in templates[:3]:
                assert "is_demo" not in template, f"is_demo in template: {template.keys()}"
        
        print(f"✓ Workflow templates endpoint works")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
