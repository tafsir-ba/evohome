"""
Auth Stabilization Sprint - Phase 2 Tests
Tests for new requirements:
1. Token has 'type':'access' field (old tokens didn't have this)
2. is_demo is NOT in the token - comes from DB lookup
3. Buyer login and vault access
4. Demo login endpoints
5. Vault buyer access for shared documents
"""

import pytest
import requests
import jwt
import os
import time

# Get BASE_URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL')
if not BASE_URL:
    raise ValueError("REACT_APP_BACKEND_URL environment variable not set")

BASE_URL = BASE_URL.rstrip('/')

# Test credentials provided by main agent
DEMO_AGENT_EMAIL = "demo.agent@upgradeflow.com"
DEMO_AGENT_PASSWORD = "demo123"


class TestTokenStructure:
    """Test that tokens have proper structure with type:access field"""
    
    def test_agent_login_token_has_type_access_field(self):
        """Agent login should return token with 'type':'access' field"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": DEMO_AGENT_EMAIL, "password": DEMO_AGENT_PASSWORD}
        )
        
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data, "Response should contain token"
        
        # Decode token WITHOUT verification to inspect payload
        token = data["token"]
        # JWT is base64, we can decode payload without verifying signature
        parts = token.split('.')
        assert len(parts) == 3, "JWT should have 3 parts"
        
        # Decode payload (middle part)
        import base64
        payload_b64 = parts[1]
        # Add padding if needed
        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += '=' * padding
        payload_json = base64.b64decode(payload_b64)
        import json
        payload = json.loads(payload_json)
        
        # CRITICAL: Token must have 'type' field with value 'access'
        assert "type" in payload, "Token payload must have 'type' field"
        assert payload["type"] == "access", f"Token type should be 'access', got: {payload.get('type')}"
        
        # Verify other expected fields
        assert "user_id" in payload, "Token should have user_id"
        assert "role" in payload, "Token should have role"
        assert payload["role"] == "agent", "Role should be agent"
        assert "exp" in payload, "Token should have expiration"
        assert "iat" in payload, "Token should have issued-at"
        
    def test_token_does_not_have_is_demo_field(self):
        """Token payload should NOT contain is_demo - it comes from DB"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": DEMO_AGENT_EMAIL, "password": DEMO_AGENT_PASSWORD}
        )
        
        assert response.status_code == 200
        token = response.json()["token"]
        
        # Decode payload
        import base64
        import json
        parts = token.split('.')
        payload_b64 = parts[1]
        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += '=' * padding
        payload = json.loads(base64.b64decode(payload_b64))
        
        # is_demo should NOT be in token
        assert "is_demo" not in payload, "Token should NOT contain is_demo field - it should come from DB lookup"


class TestDemoLogin:
    """Test demo login endpoints for agents and buyers"""
    
    def test_demo_agent_login_returns_token(self):
        """POST /api/auth/demo/agent should return valid token"""
        response = requests.post(f"{BASE_URL}/api/demo/enter", json={"persona": "agent", "fresh": False})
        
        if response.status_code == 404:
            pytest.skip("Demo data not seeded - run /api/demo/seed first")
        
        assert response.status_code == 200, f"Demo agent login failed: {response.text}"
        
        data = response.json()
        assert "token" in data, "Response should contain token"
        assert "user_id" in data, "Response should contain user_id"
        assert "role" in data, "Response should contain role"
        assert data["role"] == "agent", "Role should be agent"
        
        # Verify token works
        session_response = requests.get(
            f"{BASE_URL}/api/auth/session",
            headers={"Authorization": f"Bearer {data['token']}"}
        )
        assert session_response.status_code == 200, "Demo agent token should work"
        
    def test_demo_buyer_login_returns_token(self):
        """POST /api/auth/demo/buyer should return valid token"""
        response = requests.post(
            f"{BASE_URL}/api/demo/enter",
            json={"persona": "buyer", "buyer_slot": 1, "fresh": False},
        )
        
        if response.status_code == 404:
            pytest.skip("Demo data not seeded - run /api/demo/seed first")
        
        assert response.status_code == 200, f"Demo buyer login failed: {response.text}"
        
        data = response.json()
        assert "token" in data, "Response should contain token"
        assert "user_id" in data, "Response should contain user_id"
        assert "role" in data, "Response should contain role"
        assert data["role"] == "buyer", "Role should be buyer"
        
        # Verify token works
        session_response = requests.get(
            f"{BASE_URL}/api/auth/session",
            headers={"Authorization": f"Bearer {data['token']}"}
        )
        assert session_response.status_code == 200, "Demo buyer token should work"


class TestAgentProjectsAccess:
    """Test that agent can fetch projects with proper is_demo filtering"""
    
    def test_agent_can_fetch_projects(self):
        """Agent should be able to fetch /api/projects"""
        # Login as agent
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": DEMO_AGENT_EMAIL, "password": DEMO_AGENT_PASSWORD}
        )
        assert login_response.status_code == 200
        token = login_response.json()["token"]
        is_demo = login_response.json().get("is_demo", False)
        
        # Fetch projects
        projects_response = requests.get(
            f"{BASE_URL}/api/projects",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert projects_response.status_code == 200, f"Projects fetch failed: {projects_response.text}"
        
        data = projects_response.json()
        assert isinstance(data, list), "Projects response should be a list"
        
        # If demo user, all projects should have is_demo matching
        if is_demo and len(data) > 0:
            for project in data:
                assert project.get("is_demo") == is_demo, "Projects should match is_demo filter"


class TestBuyerVaultAccess:
    """Test buyer can access vault endpoints"""
    
    def test_buyer_can_fetch_vault_list(self):
        """Buyer should be able to fetch /api/vault/buyer"""
        # Login as demo buyer
        login_response = requests.post(
            f"{BASE_URL}/api/demo/enter",
            json={"persona": "buyer", "buyer_slot": 1, "fresh": False},
        )
        
        if login_response.status_code == 404:
            pytest.skip("Demo data not seeded")
        
        assert login_response.status_code == 200, f"Buyer login failed: {login_response.text}"
        token = login_response.json()["token"]
        
        # Fetch vault documents
        vault_response = requests.get(
            f"{BASE_URL}/api/vault/buyer",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert vault_response.status_code == 200, f"Vault fetch failed: {vault_response.text}"
        
        data = vault_response.json()
        assert isinstance(data, list), "Vault response should be a list"
    
    def test_buyer_vault_access_requires_auth(self):
        """Vault endpoint should require authentication"""
        response = requests.get(f"{BASE_URL}/api/vault/buyer")
        
        assert response.status_code == 401, "Vault endpoint should require auth"


class TestLogoutInvalidation:
    """Test logout properly invalidates session"""
    
    def test_logout_invalidates_session_completely(self):
        """After logout, ALL subsequent requests with that token should fail"""
        # Login
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": DEMO_AGENT_EMAIL, "password": DEMO_AGENT_PASSWORD}
        )
        assert login_response.status_code == 200
        token = login_response.json()["token"]
        
        # Verify token works
        session1 = requests.get(
            f"{BASE_URL}/api/auth/session",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert session1.status_code == 200, "Token should work before logout"
        
        # Logout
        logout_response = requests.post(
            f"{BASE_URL}/api/auth/logout",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert logout_response.status_code == 200, "Logout should succeed"
        
        # Try session check - should fail
        session2 = requests.get(
            f"{BASE_URL}/api/auth/session",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert session2.status_code == 401, "Session check should fail after logout"
        
        # Try refresh - should fail
        refresh = requests.post(
            f"{BASE_URL}/api/auth/refresh",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert refresh.status_code == 401, "Refresh should fail after logout"
        
        # Try projects - should fail
        projects = requests.get(
            f"{BASE_URL}/api/projects",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert projects.status_code == 401, "Projects should fail after logout"


class TestRefreshTokenFlow:
    """Test token refresh endpoint"""
    
    def test_refresh_returns_new_token_with_type_access(self):
        """Refresh should return new token with type:access"""
        # Login
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": DEMO_AGENT_EMAIL, "password": DEMO_AGENT_PASSWORD}
        )
        assert login_response.status_code == 200
        token = login_response.json()["token"]
        
        # Refresh
        refresh_response = requests.post(
            f"{BASE_URL}/api/auth/refresh",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert refresh_response.status_code == 200
        data = refresh_response.json()
        assert data.get("success") == True
        assert "token" in data
        
        new_token = data["token"]
        
        # Verify new token has type:access
        import base64
        import json
        parts = new_token.split('.')
        payload_b64 = parts[1]
        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += '=' * padding
        payload = json.loads(base64.b64decode(payload_b64))
        
        assert payload.get("type") == "access", "Refreshed token should have type:access"


class TestSessionIsDemoFromDB:
    """Test that session endpoint returns is_demo from database"""
    
    def test_session_is_demo_value_from_database(self):
        """Session's is_demo should come from database, not token"""
        # Login as demo agent
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": DEMO_AGENT_EMAIL, "password": DEMO_AGENT_PASSWORD}
        )
        assert login_response.status_code == 200
        token = login_response.json()["token"]
        login_is_demo = login_response.json().get("is_demo")
        
        # Get session
        session_response = requests.get(
            f"{BASE_URL}/api/auth/session",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert session_response.status_code == 200
        
        session_data = session_response.json()
        assert session_data["authenticated"] == True
        
        # is_demo should be in user object
        user = session_data["user"]
        assert "is_demo" in user, "Session user should have is_demo field from DB"
        
        # The value should match (both come from DB now)
        assert user["is_demo"] == login_is_demo, "is_demo should be consistent"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
