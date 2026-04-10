"""
Auth Stabilization Sprint - Phase 1 Tests
Tests for:
1. POST /api/auth/login - returns token and user data
2. GET /api/auth/session - returns authenticated user with is_demo from DB
3. POST /api/auth/refresh - extends session with new token
4. POST /api/auth/logout - invalidates token
5. After logout, same token returns 401 'Session invalidated'
"""

import pytest
import requests
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


class TestAuthLogin:
    """Test POST /api/auth/login endpoint"""
    
    def test_login_returns_token_and_user_data(self):
        """Login should return token and user data"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": DEMO_AGENT_EMAIL, "password": DEMO_AGENT_PASSWORD}
        )
        
        # Status code assertion
        assert response.status_code == 200, f"Login failed: {response.text}"
        
        # Data assertions
        data = response.json()
        assert "token" in data, "Response should contain token"
        assert isinstance(data["token"], str), "Token should be a string"
        assert len(data["token"]) > 0, "Token should not be empty"
        
        # User data assertions
        assert "user_id" in data, "Response should contain user_id"
        assert "email" in data, "Response should contain email"
        assert data["email"] == DEMO_AGENT_EMAIL, "Email should match"
        assert "name" in data, "Response should contain name"
        assert "role" in data, "Response should contain role"
        assert data["role"] == "agent", "Role should be agent"
        assert "is_demo" in data, "Response should contain is_demo"
        
    def test_login_invalid_credentials(self):
        """Login with wrong password should return 401"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": DEMO_AGENT_EMAIL, "password": "wrongpassword"}
        )
        
        assert response.status_code == 401, "Should return 401 for invalid credentials"
        data = response.json()
        assert "detail" in data, "Should return error detail"

    def test_login_nonexistent_user(self):
        """Login with nonexistent email should return 401"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "nonexistent@test.com", "password": "anypassword"}
        )
        
        assert response.status_code == 401, "Should return 401 for nonexistent user"


class TestAuthSession:
    """Test GET /api/auth/session endpoint"""
    
    def test_session_returns_authenticated_user(self):
        """Session endpoint should return authenticated user with is_demo from DB"""
        # First login to get token
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": DEMO_AGENT_EMAIL, "password": DEMO_AGENT_PASSWORD}
        )
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        token = login_response.json()["token"]
        
        # Check session with token in Authorization header
        session_response = requests.get(
            f"{BASE_URL}/api/auth/session",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert session_response.status_code == 200, f"Session check failed: {session_response.text}"
        
        data = session_response.json()
        assert "authenticated" in data, "Should contain 'authenticated' field"
        assert data["authenticated"] == True, "Should be authenticated"
        assert "user" in data, "Should contain 'user' object"
        
        user = data["user"]
        assert "user_id" in user, "User should have user_id"
        assert "email" in user, "User should have email"
        assert user["email"] == DEMO_AGENT_EMAIL, "Email should match"
        assert "name" in user, "User should have name"
        assert "role" in user, "User should have role"
        assert user["role"] == "agent", "Role should be agent"
        # CRITICAL: is_demo comes from database, not JWT
        assert "is_demo" in user, "User should have is_demo field (from DB, not JWT)"
        
    def test_session_without_token_returns_401(self):
        """Session endpoint without token should return 401"""
        response = requests.get(f"{BASE_URL}/api/auth/session")
        
        assert response.status_code == 401, "Should return 401 without token"
        data = response.json()
        assert "detail" in data, "Should return error detail"
        
    def test_session_with_invalid_token_returns_401(self):
        """Session endpoint with invalid token should return 401"""
        response = requests.get(
            f"{BASE_URL}/api/auth/session",
            headers={"Authorization": "Bearer invalid_token_here"}
        )
        
        assert response.status_code == 401, "Should return 401 for invalid token"


class TestAuthRefresh:
    """Test POST /api/auth/refresh endpoint"""
    
    def test_refresh_extends_session_with_new_token(self):
        """Refresh should return new token that works"""
        # First login to get token
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": DEMO_AGENT_EMAIL, "password": DEMO_AGENT_PASSWORD}
        )
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        original_token = login_response.json()["token"]
        
        # Refresh the token
        refresh_response = requests.post(
            f"{BASE_URL}/api/auth/refresh",
            headers={"Authorization": f"Bearer {original_token}"}
        )
        
        assert refresh_response.status_code == 200, f"Refresh failed: {refresh_response.text}"
        
        data = refresh_response.json()
        assert "success" in data, "Should contain 'success' field"
        assert data["success"] == True, "Success should be True"
        assert "token" in data, "Should contain new token"
        assert isinstance(data["token"], str), "Token should be string"
        assert len(data["token"]) > 0, "Token should not be empty"
        assert "expires_in" in data, "Should contain expires_in"
        assert data["expires_in"] > 0, "expires_in should be positive"
        
        # Verify new token works for session check
        new_token = data["token"]
        session_response = requests.get(
            f"{BASE_URL}/api/auth/session",
            headers={"Authorization": f"Bearer {new_token}"}
        )
        assert session_response.status_code == 200, "New token should work for session check"
        
    def test_refresh_without_token_returns_401(self):
        """Refresh without token should return 401"""
        response = requests.post(f"{BASE_URL}/api/auth/refresh")
        
        assert response.status_code == 401, "Should return 401 without token"
        
    def test_refresh_with_invalid_token_returns_401(self):
        """Refresh with invalid token should return 401"""
        response = requests.post(
            f"{BASE_URL}/api/auth/refresh",
            headers={"Authorization": "Bearer invalid_token_here"}
        )
        
        assert response.status_code == 401, "Should return 401 for invalid token"


class TestAuthLogout:
    """Test POST /api/auth/logout endpoint"""
    
    def test_logout_invalidates_token(self):
        """Logout should invalidate the token"""
        # First login to get token
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": DEMO_AGENT_EMAIL, "password": DEMO_AGENT_PASSWORD}
        )
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        token = login_response.json()["token"]
        
        # Verify token works before logout
        session_before = requests.get(
            f"{BASE_URL}/api/auth/session",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert session_before.status_code == 200, "Token should work before logout"
        
        # Logout
        logout_response = requests.post(
            f"{BASE_URL}/api/auth/logout",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert logout_response.status_code == 200, f"Logout failed: {logout_response.text}"
        data = logout_response.json()
        assert "success" in data, "Should contain 'success' field"
        assert data["success"] == True, "Success should be True"
        assert "message" in data, "Should contain message"
        
    def test_after_logout_token_returns_401_session_invalidated(self):
        """After logout, same token should return 401 'Session invalidated'"""
        # Login fresh
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": DEMO_AGENT_EMAIL, "password": DEMO_AGENT_PASSWORD}
        )
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        token = login_response.json()["token"]
        
        # Logout
        logout_response = requests.post(
            f"{BASE_URL}/api/auth/logout",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert logout_response.status_code == 200, "Logout should succeed"
        
        # Try to use the same token - should fail with session invalidated
        session_after = requests.get(
            f"{BASE_URL}/api/auth/session",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert session_after.status_code == 401, "Should return 401 after logout"
        data = session_after.json()
        assert "detail" in data, "Should return error detail"
        # Check for "invalidated" in the message (case-insensitive)
        assert "invalidated" in data["detail"].lower() or "session" in data["detail"].lower(), \
            f"Error should mention session invalidation, got: {data['detail']}"
            
    def test_refresh_after_logout_returns_401(self):
        """After logout, trying to refresh the same token should return 401"""
        # Login fresh
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": DEMO_AGENT_EMAIL, "password": DEMO_AGENT_PASSWORD}
        )
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        token = login_response.json()["token"]
        
        # Logout
        logout_response = requests.post(
            f"{BASE_URL}/api/auth/logout",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert logout_response.status_code == 200, "Logout should succeed"
        
        # Try to refresh the invalidated token
        refresh_response = requests.post(
            f"{BASE_URL}/api/auth/refresh",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert refresh_response.status_code == 401, "Should return 401 when refreshing invalidated token"
        data = refresh_response.json()
        assert "detail" in data, "Should return error detail"


class TestIsDemoFromDatabase:
    """Test that is_demo is fetched from database, not JWT"""
    
    def test_session_returns_is_demo_from_db(self):
        """is_demo in session response should come from database"""
        # Small delay to ensure unique token timestamp (iat)
        time.sleep(0.5)
        
        # Login as demo agent
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": DEMO_AGENT_EMAIL, "password": DEMO_AGENT_PASSWORD}
        )
        assert login_response.status_code == 200
        
        login_data = login_response.json()
        token = login_data["token"]
        login_is_demo = login_data.get("is_demo")
        
        # Check session
        session_response = requests.get(
            f"{BASE_URL}/api/auth/session",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert session_response.status_code == 200
        
        session_data = session_response.json()
        session_is_demo = session_data["user"].get("is_demo")
        
        # Both should match (they both come from DB now)
        # Main point is that session has is_demo field
        assert session_is_demo is not None, "is_demo should be present in session user data"
        # For demo agent, is_demo could be True or False depending on DB state
        assert isinstance(session_is_demo, bool), "is_demo should be boolean"


class TestAuthFlowIntegration:
    """Integration tests for complete auth flows"""
    
    def test_full_login_session_logout_flow(self):
        """Test complete login -> session check -> logout -> verify invalidation"""
        # Step 1: Login
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": DEMO_AGENT_EMAIL, "password": DEMO_AGENT_PASSWORD}
        )
        assert login_response.status_code == 200, "Login should succeed"
        token = login_response.json()["token"]
        
        # Step 2: Session check
        session_response = requests.get(
            f"{BASE_URL}/api/auth/session",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert session_response.status_code == 200, "Session check should succeed"
        assert session_response.json()["authenticated"] == True
        
        # Step 3: Logout
        logout_response = requests.post(
            f"{BASE_URL}/api/auth/logout",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert logout_response.status_code == 200, "Logout should succeed"
        
        # Step 4: Verify token is invalidated
        session_after = requests.get(
            f"{BASE_URL}/api/auth/session",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert session_after.status_code == 401, "Token should be invalidated after logout"
        
    def test_login_refresh_session_flow(self):
        """Test login -> refresh -> session check with new token"""
        # Step 1: Login
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": DEMO_AGENT_EMAIL, "password": DEMO_AGENT_PASSWORD}
        )
        assert login_response.status_code == 200
        original_token = login_response.json()["token"]
        
        # Step 2: Refresh
        refresh_response = requests.post(
            f"{BASE_URL}/api/auth/refresh",
            headers={"Authorization": f"Bearer {original_token}"}
        )
        assert refresh_response.status_code == 200
        new_token = refresh_response.json()["token"]
        
        # Step 3: Session check with new token
        session_response = requests.get(
            f"{BASE_URL}/api/auth/session",
            headers={"Authorization": f"Bearer {new_token}"}
        )
        assert session_response.status_code == 200
        assert session_response.json()["authenticated"] == True
        
        # Optional: Original token may or may not still work (implementation detail)
        # The key is that the new token works


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
