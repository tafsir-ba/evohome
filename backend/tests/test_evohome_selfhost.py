"""
Evohome Self-Hosting Verification Tests
Tests to verify the app is ready for self-hosting at app.evo-home.ch
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://invoice-track-20.preview.emergentagent.com').rstrip('/')


class TestHealthAndBasics:
    """Basic health check endpoints"""
    
    def test_health_endpoint(self):
        """Verify /api/health endpoint works"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        print(f"✓ Health endpoint: {data}")
    

class TestDemoLogin:
    """Demo login endpoints for testing without OAuth"""
    
    def test_demo_agent_login(self):
        """Verify demo agent login works"""
        response = requests.post(f"{BASE_URL}/api/demo/enter", json={"persona": "agent", "fresh": False})
        assert response.status_code == 200
        data = response.json()
        assert data.get("role") == "agent"
        assert "token" in data
        assert "user_id" in data
        print(f"✓ Demo agent login: {data.get('name')} ({data.get('email')})")
        return data.get("token")
    
    def test_demo_buyer_login(self):
        """Verify demo buyer login works"""
        response = requests.post(
            f"{BASE_URL}/api/demo/enter",
            json={"persona": "buyer", "buyer_slot": 1, "fresh": False},
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("role") == "buyer"
        assert "token" in data
        assert "user_id" in data
        print(f"✓ Demo buyer login: {data.get('name')} ({data.get('email')})")
        return data.get("token")
    
    def test_demo_buyer_login_with_buyer_num(self):
        """Verify demo buyer login with buyer_num parameter works"""
        response = requests.post(f"{BASE_URL}/api/demo/enter", json={"persona": "buyer", "buyer_slot": 2, "fresh": False})
        assert response.status_code == 200
        data = response.json()
        assert data.get("role") == "buyer"
        print(f"✓ Demo buyer 2 login: {data.get('name')} ({data.get('email')})")


class TestGoogleOAuth:
    """Google OAuth callback endpoint tests"""
    
    def test_google_callback_missing_code(self):
        """Verify /api/auth/google/callback requires code"""
        response = requests.post(
            f"{BASE_URL}/api/auth/google/callback",
            json={"redirect_uri": "https://app.evo-home.ch/auth/google/callback"}
        )
        assert response.status_code == 400
        data = response.json()
        assert "code" in data.get("detail", "").lower() or "required" in data.get("detail", "").lower()
        print(f"✓ Google callback requires code: {data}")
    
    def test_google_callback_missing_secret(self):
        """Verify /api/auth/google/callback reports missing client secret"""
        response = requests.post(
            f"{BASE_URL}/api/auth/google/callback",
            json={
                "code": "test_code",
                "redirect_uri": "https://app.evo-home.ch/auth/google/callback"
            }
        )
        # Should return 500 with "missing client secret" message
        assert response.status_code == 500 or response.status_code == 400
        data = response.json()
        assert "client secret" in data.get("detail", "").lower() or "configured" in data.get("detail", "").lower()
        print(f"✓ Google OAuth reports missing secret: {data}")


class TestEmailPasswordAuth:
    """Email/password authentication endpoints"""
    
    def test_agent_register(self):
        """Test agent registration endpoint"""
        import uuid
        test_email = f"test_agent_{uuid.uuid4().hex[:8]}@example.com"
        response = requests.post(
            f"{BASE_URL}/api/auth/register",
            json={
                "email": test_email,
                "password": "TestPassword123",
                "name": "Test Agent"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("role") == "agent"
        assert data.get("email") == test_email
        print(f"✓ Agent registration: {data.get('email')}")
    
    def test_agent_login_invalid_credentials(self):
        """Test agent login with invalid credentials"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={
                "email": "nonexistent@example.com",
                "password": "WrongPassword"
            }
        )
        assert response.status_code == 401
        print("✓ Invalid credentials returns 401")
    
    def test_buyer_register(self):
        """Test buyer registration endpoint"""
        import uuid
        test_email = f"test_buyer_{uuid.uuid4().hex[:8]}@example.com"
        response = requests.post(
            f"{BASE_URL}/api/auth/buyer/register",
            json={
                "email": test_email,
                "password": "TestPassword123",
                "name": "Test Buyer"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("role") == "buyer"
        assert data.get("email") == test_email
        print(f"✓ Buyer registration: {data.get('email')}")


class TestAuthenticatedEndpoints:
    """Test authenticated agent endpoints"""
    
    @pytest.fixture
    def agent_token(self):
        """Get agent token for authenticated requests"""
        response = requests.post(f"{BASE_URL}/api/demo/enter", json={"persona": "agent", "fresh": False})
        return response.json().get("token")
    
    @pytest.fixture
    def buyer_token(self):
        """Get buyer token for authenticated requests"""
        response = requests.post(
            f"{BASE_URL}/api/demo/enter",
            json={"persona": "buyer", "buyer_slot": 1, "fresh": False},
        )
        return response.json().get("token")
    
    def test_auth_me_with_token(self, agent_token):
        """Test /api/auth/me returns user data"""
        headers = {"Authorization": f"Bearer {agent_token}"}
        response = requests.get(f"{BASE_URL}/api/auth/me", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("role") == "agent"
        print(f"✓ Auth me endpoint: {data.get('name')}")
    
    def test_agent_projects(self, agent_token):
        """Test agent can list projects"""
        headers = {"Authorization": f"Bearer {agent_token}"}
        response = requests.get(f"{BASE_URL}/api/projects", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Agent projects: {len(data)} projects")
    
    def test_agent_clients(self, agent_token):
        """Test agent can list clients"""
        headers = {"Authorization": f"Bearer {agent_token}"}
        response = requests.get(f"{BASE_URL}/api/clients", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Agent clients: {len(data)} clients")
    
    def test_agent_quotes(self, agent_token):
        """Test agent can list quotes"""
        headers = {"Authorization": f"Bearer {agent_token}"}
        response = requests.get(f"{BASE_URL}/api/documents?type=quote", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Agent quotes: {len(data)} quotes")
    
    def test_agent_invoices(self, agent_token):
        """Test agent can list invoices"""
        headers = {"Authorization": f"Bearer {agent_token}"}
        response = requests.get(f"{BASE_URL}/api/documents?type=invoice", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Agent invoices: {len(data)} invoices")
    
    def test_buyer_timeline(self, buyer_token):
        """Test buyer can access their timeline"""
        headers = {"Authorization": f"Bearer {buyer_token}"}
        response = requests.get(f"{BASE_URL}/api/buyer/timeline", headers=headers)
        assert response.status_code == 200
        data = response.json()
        print(f"✓ Buyer timeline accessible")


class TestSubscriptionEndpoints:
    """Test subscription/billing endpoints"""
    
    @pytest.fixture
    def agent_token(self):
        """Get agent token for authenticated requests"""
        response = requests.post(f"{BASE_URL}/api/demo/enter", json={"persona": "agent", "fresh": False})
        return response.json().get("token")
    
    def test_subscription_plans(self, agent_token):
        """Test getting subscription plans"""
        headers = {"Authorization": f"Bearer {agent_token}"}
        response = requests.get(f"{BASE_URL}/api/billing/plans", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "free" in data or len(data) > 0
        print(f"✓ Subscription plans: {list(data.keys()) if isinstance(data, dict) else 'list format'}")
    
    def test_subscription_status(self, agent_token):
        """Test getting subscription status"""
        headers = {"Authorization": f"Bearer {agent_token}"}
        response = requests.get(f"{BASE_URL}/api/billing/status", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "plan_id" in data or "plan_name" in data
        print(f"✓ Subscription status: {data.get('plan_name', data.get('plan_id'))}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
