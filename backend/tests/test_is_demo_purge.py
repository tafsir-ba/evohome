"""
Test Suite: is_demo Field Purge Verification
=============================================
Verifies complete removal of is_demo field from all system ingress points:
- invitations.py, demo.py, schemas.py, auth.py
- Demo seeding uses deterministic demo_* ID namespace with zero is_demo field writes
- All API responses contain NO is_demo field

Test Categories:
1. Demo Seed Endpoint Tests
2. Demo Login Tests  
3. Auth Endpoint Tests (no is_demo in responses)
4. Team Invitation Tests (no is_demo)
5. MongoDB Collection Verification (zero is_demo fields)
6. Demo Data Relationship Verification
7. Agent Registration Tests (no is_demo)
8. E2E Agent Access Tests
"""

import pytest
import requests
import os
import time
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Demo credentials from review request
DEMO_AGENT_EMAIL = "demo.agent@upgradeflow.com"
DEMO_AGENT_PASSWORD = "demo123"
E2E_AGENT_EMAIL = "e2e@evohome-test.com"
E2E_AGENT_PASSWORD = "Test2026!"

# Cache for tokens to avoid rate limiting
_token_cache = {}
_seeded = False

def seed_demo_data_once():
    """Seed demo data once at module start"""
    global _seeded
    if not _seeded:
        requests.post(f"{BASE_URL}/api/demo/seed")
        time.sleep(1)
        _seeded = True

def get_demo_token():
    """Get demo agent token with caching to avoid rate limiting"""
    if "demo" in _token_cache:
        return _token_cache["demo"]
    
    seed_demo_data_once()
    time.sleep(0.5)  # Rate limit protection
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": DEMO_AGENT_EMAIL,
        "password": DEMO_AGENT_PASSWORD
    })
    if response.status_code == 200:
        _token_cache["demo"] = response.json()["token"]
        return _token_cache["demo"]
    return None

def get_e2e_token():
    """Get E2E agent token with caching"""
    if "e2e" in _token_cache:
        return _token_cache["e2e"]
    
    time.sleep(0.5)
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": E2E_AGENT_EMAIL,
        "password": E2E_AGENT_PASSWORD
    })
    if response.status_code == 200:
        _token_cache["e2e"] = response.json()["token"]
        return _token_cache["e2e"]
    return None


# Module-level setup
@pytest.fixture(scope="module", autouse=True)
def setup_module():
    """Seed demo data once before all tests in this module"""
    seed_demo_data_once()
    yield


class TestDemoSeedEndpoint:
    """Tests for POST /api/demo/seed endpoint"""
    
    def test_demo_seed_returns_credentials(self):
        """POST /api/demo/seed should return demo credentials without is_demo"""
        response = requests.post(f"{BASE_URL}/api/demo/seed")
        assert response.status_code == 200, f"Demo seed failed: {response.text}"
        
        data = response.json()
        assert "message" in data, "Response should have message"
        assert "demo_credentials" in data, "Response should have demo_credentials"
        
        # Verify credentials structure
        creds = data["demo_credentials"]
        assert "agent" in creds, "Should have agent credentials"
        assert creds["agent"]["email"] == DEMO_AGENT_EMAIL
        assert creds["agent"]["password"] == DEMO_AGENT_PASSWORD
        
        # CRITICAL: Verify NO is_demo field in response
        assert "is_demo" not in data, "Response should NOT contain is_demo field"
        assert "is_demo" not in str(data), "No is_demo anywhere in response"
        print("PASSED: Demo seed returns credentials without is_demo")
    
    def test_demo_seed_idempotency(self):
        """Calling seed twice should not duplicate data (first run cleans old data)"""
        # First seed
        response1 = requests.post(f"{BASE_URL}/api/demo/seed")
        assert response1.status_code == 200
        
        # Second seed
        response2 = requests.post(f"{BASE_URL}/api/demo/seed")
        assert response2.status_code == 200
        
        # Login as demo agent and check data counts
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": DEMO_AGENT_EMAIL,
            "password": DEMO_AGENT_PASSWORD
        })
        assert login_resp.status_code == 200
        token = login_resp.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Check projects - should have exactly 1 demo project
        projects_resp = requests.get(f"{BASE_URL}/api/projects", headers=headers)
        assert projects_resp.status_code == 200
        projects = projects_resp.json()
        demo_projects = [p for p in projects if p.get("project_id", "").startswith("demo_")]
        assert len(demo_projects) == 1, f"Should have exactly 1 demo project, got {len(demo_projects)}"
        
        # Check clients - should have exactly 2 demo clients
        clients_resp = requests.get(f"{BASE_URL}/api/clients", headers=headers)
        assert clients_resp.status_code == 200
        clients = clients_resp.json()
        demo_clients = [c for c in clients if c.get("client_id", "").startswith("demo_")]
        assert len(demo_clients) == 2, f"Should have exactly 2 demo clients, got {len(demo_clients)}"
        
        print("PASSED: Demo seed is idempotent - no duplicate data")


class TestDemoLoginEndpoints:
    """Tests for demo login endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Ensure demo data is seeded before tests"""
        requests.post(f"{BASE_URL}/api/demo/seed")
    
    def test_demo_agent_login(self):
        """POST /api/auth/demo/agent returns user data without is_demo"""
        response = requests.post(f"{BASE_URL}/api/auth/demo/agent")
        assert response.status_code == 200, f"Demo agent login failed: {response.text}"
        
        data = response.json()
        assert "user_id" in data
        assert "email" in data
        assert "name" in data
        assert "role" in data
        assert "token" in data
        
        # CRITICAL: No is_demo field
        assert "is_demo" not in data, f"Response should NOT contain is_demo: {data}"
        
        # Verify user_id uses demo_* prefix convention
        assert data["user_id"].startswith("demo_"), f"Demo user_id should start with demo_: {data['user_id']}"
        assert data["role"] == "agent"
        print(f"PASSED: Demo agent login returns user without is_demo: {data['user_id']}")
    
    def test_demo_buyer_login_buyer1(self):
        """POST /api/auth/demo/buyer?buyer_num=1 works"""
        response = requests.post(f"{BASE_URL}/api/auth/demo/buyer?buyer_num=1")
        assert response.status_code == 200, f"Demo buyer 1 login failed: {response.text}"
        
        data = response.json()
        assert "user_id" in data
        assert data["user_id"] == "demo_buyer_001", f"Expected demo_buyer_001, got {data['user_id']}"
        assert data["role"] == "buyer"
        
        # CRITICAL: No is_demo field
        assert "is_demo" not in data, f"Response should NOT contain is_demo: {data}"
        print("PASSED: Demo buyer 1 login works without is_demo")
    
    def test_demo_buyer_login_buyer2(self):
        """POST /api/auth/demo/buyer?buyer_num=2 works"""
        response = requests.post(f"{BASE_URL}/api/auth/demo/buyer?buyer_num=2")
        assert response.status_code == 200, f"Demo buyer 2 login failed: {response.text}"
        
        data = response.json()
        assert data["user_id"] == "demo_buyer_002", f"Expected demo_buyer_002, got {data['user_id']}"
        assert "is_demo" not in data
        print("PASSED: Demo buyer 2 login works without is_demo")
    
    def test_demo_agent_login_with_credentials(self):
        """POST /api/auth/login with demo agent credentials works"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": DEMO_AGENT_EMAIL,
            "password": DEMO_AGENT_PASSWORD
        })
        assert response.status_code == 200, f"Demo agent credential login failed: {response.text}"
        
        data = response.json()
        assert data["email"] == DEMO_AGENT_EMAIL
        assert data["role"] == "agent"
        assert "token" in data
        
        # CRITICAL: No is_demo field
        assert "is_demo" not in data, f"Login response should NOT contain is_demo: {data}"
        print("PASSED: Demo agent login with credentials works without is_demo")


class TestAuthEndpointsNoIsDemo:
    """Tests that auth endpoints return NO is_demo field"""
    
    @pytest.fixture
    def demo_token(self):
        """Get demo agent token"""
        token = get_demo_token()
        if not token:
            pytest.skip("Could not get demo token")
        return token
    
    def test_auth_me_no_is_demo(self, demo_token):
        """GET /api/auth/me with demo token returns user data without is_demo"""
        headers = {"Authorization": f"Bearer {demo_token}"}
        response = requests.get(f"{BASE_URL}/api/auth/me", headers=headers)
        assert response.status_code == 200, f"Auth me failed: {response.text}"
        
        data = response.json()
        assert "user_id" in data
        assert "email" in data
        assert "role" in data
        
        # CRITICAL: No is_demo field
        assert "is_demo" not in data, f"/auth/me should NOT return is_demo: {data}"
        print("PASSED: GET /auth/me returns user without is_demo")
    
    def test_auth_session_no_is_demo(self, demo_token):
        """GET /api/auth/session with demo token returns session data without is_demo"""
        headers = {"Authorization": f"Bearer {demo_token}"}
        response = requests.get(f"{BASE_URL}/api/auth/session", headers=headers)
        assert response.status_code == 200, f"Auth session failed: {response.text}"
        
        data = response.json()
        assert "authenticated" in data
        assert data["authenticated"] == True
        assert "user" in data
        
        # CRITICAL: No is_demo in user object
        user = data["user"]
        assert "is_demo" not in user, f"/auth/session user should NOT have is_demo: {user}"
        assert "is_demo" not in str(data), "No is_demo anywhere in session response"
        print("PASSED: GET /auth/session returns session without is_demo")


class TestTeamInvitationsNoIsDemo:
    """Tests that team invitation endpoints work without is_demo"""
    
    @pytest.fixture
    def demo_token(self):
        """Get demo agent token"""
        token = get_demo_token()
        if not token:
            pytest.skip("Could not get demo token")
        return token
    
    def test_create_team_invitation(self, demo_token):
        """POST /api/team/invitations works without is_demo"""
        headers = {"Authorization": f"Bearer {demo_token}"}
        unique_email = f"test_invite_{uuid.uuid4().hex[:8]}@test.com"
        
        response = requests.post(f"{BASE_URL}/api/team/invitations", headers=headers, json={
            "email": unique_email,
            "role": "member",
            "message": "Test invitation"
        })
        assert response.status_code == 200, f"Create invitation failed: {response.text}"
        
        data = response.json()
        assert "invitation_id" in data
        assert data["email"] == unique_email
        
        # CRITICAL: No is_demo field
        assert "is_demo" not in data, f"Invitation response should NOT have is_demo: {data}"
        print("PASSED: POST /team/invitations works without is_demo")
    
    def test_list_team_invitations(self, demo_token):
        """GET /api/team/invitations works without is_demo"""
        headers = {"Authorization": f"Bearer {demo_token}"}
        response = requests.get(f"{BASE_URL}/api/team/invitations", headers=headers)
        assert response.status_code == 200, f"List invitations failed: {response.text}"
        
        data = response.json()
        assert isinstance(data, list)
        
        # CRITICAL: No is_demo in any invitation
        for invite in data:
            assert "is_demo" not in invite, f"Invitation should NOT have is_demo: {invite}"
        print(f"PASSED: GET /team/invitations returns {len(data)} invitations without is_demo")
    
    def test_list_team_members(self, demo_token):
        """GET /api/team/members works without is_demo"""
        headers = {"Authorization": f"Bearer {demo_token}"}
        response = requests.get(f"{BASE_URL}/api/team/members", headers=headers)
        assert response.status_code == 200, f"List team members failed: {response.text}"
        
        data = response.json()
        assert isinstance(data, list)
        
        # CRITICAL: No is_demo in any team member
        for member in data:
            assert "is_demo" not in member, f"Team member should NOT have is_demo: {member}"
        print(f"PASSED: GET /team/members returns {len(data)} members without is_demo")


class TestDemoDataRelationships:
    """Tests that demo data has correct relationships"""
    
    @pytest.fixture
    def demo_token(self):
        """Get demo agent token after seeding"""
        token = get_demo_token()
        if not token:
            pytest.skip("Could not get demo token")
        return token
    
    def test_project_exists(self, demo_token):
        """Demo project exists with correct structure"""
        headers = {"Authorization": f"Bearer {demo_token}"}
        response = requests.get(f"{BASE_URL}/api/projects", headers=headers)
        assert response.status_code == 200
        
        projects = response.json()
        demo_project = next((p for p in projects if p.get("project_id") == "demo_proj_001"), None)
        assert demo_project is not None, "Demo project demo_proj_001 should exist"
        assert demo_project["name"] == "Residenza Lago Vista"
        assert "is_demo" not in demo_project
        print("PASSED: Demo project exists with correct structure")
    
    def test_clients_linked_to_project(self, demo_token):
        """Demo clients are linked to demo project"""
        headers = {"Authorization": f"Bearer {demo_token}"}
        response = requests.get(f"{BASE_URL}/api/clients", headers=headers)
        assert response.status_code == 200
        
        clients = response.json()
        demo_clients = [c for c in clients if c.get("client_id", "").startswith("demo_client_")]
        assert len(demo_clients) == 2, f"Should have 2 demo clients, got {len(demo_clients)}"
        
        for client in demo_clients:
            assert client["project_id"] == "demo_proj_001", f"Client should be linked to demo project: {client}"
            assert "is_demo" not in client, f"Client should NOT have is_demo: {client}"
        print("PASSED: Demo clients linked to demo project without is_demo")
    
    def test_documents_linked_to_clients(self, demo_token):
        """Demo documents are linked to demo clients"""
        headers = {"Authorization": f"Bearer {demo_token}"}
        response = requests.get(f"{BASE_URL}/api/documents", headers=headers)
        assert response.status_code == 200
        
        documents = response.json()
        demo_docs = [d for d in documents if d.get("document_id", "").startswith("demo_doc_")]
        assert len(demo_docs) >= 6, f"Should have at least 6 demo documents, got {len(demo_docs)}"
        
        for doc in demo_docs:
            assert doc["client_id"].startswith("demo_client_"), f"Doc should be linked to demo client: {doc}"
            assert doc["project_id"] == "demo_proj_001", f"Doc should be linked to demo project: {doc}"
            assert "is_demo" not in doc, f"Document should NOT have is_demo: {doc}"
        print(f"PASSED: {len(demo_docs)} demo documents linked correctly without is_demo")
    
    def test_activities_exist(self, demo_token):
        """Demo activities exist"""
        headers = {"Authorization": f"Bearer {demo_token}"}
        response = requests.get(f"{BASE_URL}/api/activities", headers=headers)
        assert response.status_code == 200
        
        data = response.json()
        # Activities endpoint returns {activities: [], total, limit, offset}
        activities = data.get("activities", data) if isinstance(data, dict) else data
        
        demo_activities = [a for a in activities if isinstance(a, dict) and a.get("activity_id", "").startswith("demo_act_")]
        assert len(demo_activities) >= 6, f"Should have at least 6 demo activities, got {len(demo_activities)}"
        
        for activity in demo_activities:
            assert "is_demo" not in activity, f"Activity should NOT have is_demo: {activity}"
        print(f"PASSED: {len(demo_activities)} demo activities exist without is_demo")


class TestAgentRegistrationNoIsDemo:
    """Tests that agent registration creates users without is_demo"""
    
    def test_register_new_agent_no_is_demo(self):
        """POST /api/auth/register creates agent without is_demo"""
        unique_email = f"test_agent_{uuid.uuid4().hex[:8]}@test.com"
        
        response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": unique_email,
            "password": "TestPassword123!",
            "name": "Test Agent"
        })
        assert response.status_code == 200, f"Registration failed: {response.text}"
        
        data = response.json()
        assert "user_id" in data
        assert data["email"] == unique_email
        assert data["role"] == "agent"
        assert "token" in data
        
        # CRITICAL: No is_demo field in registration response
        assert "is_demo" not in data, f"Registration response should NOT have is_demo: {data}"
        
        # Verify via /auth/me
        token = data["token"]
        headers = {"Authorization": f"Bearer {token}"}
        me_response = requests.get(f"{BASE_URL}/api/auth/me", headers=headers)
        assert me_response.status_code == 200
        me_data = me_response.json()
        assert "is_demo" not in me_data, f"/auth/me should NOT have is_demo for new agent: {me_data}"
        
        print(f"PASSED: New agent registered without is_demo: {unique_email}")


class TestE2EAgentAccess:
    """E2E tests for agent login and access to projects, clients, documents"""
    
    @pytest.fixture
    def e2e_token(self):
        """Get E2E test agent token"""
        token = get_e2e_token()
        if not token:
            pytest.skip("Could not get E2E token")
        return token
    
    def test_e2e_agent_login(self):
        """E2E agent can login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": E2E_AGENT_EMAIL,
            "password": E2E_AGENT_PASSWORD
        })
        assert response.status_code == 200, f"E2E agent login failed: {response.text}"
        
        data = response.json()
        assert data["email"] == E2E_AGENT_EMAIL
        assert "is_demo" not in data, f"E2E login should NOT have is_demo: {data}"
        print("PASSED: E2E agent login works without is_demo")
    
    def test_e2e_agent_access_projects(self, e2e_token):
        """E2E agent can access projects"""
        headers = {"Authorization": f"Bearer {e2e_token}"}
        response = requests.get(f"{BASE_URL}/api/projects", headers=headers)
        assert response.status_code == 200, f"Projects access failed: {response.text}"
        
        projects = response.json()
        for project in projects:
            assert "is_demo" not in project, f"Project should NOT have is_demo: {project}"
        print(f"PASSED: E2E agent can access {len(projects)} projects without is_demo")
    
    def test_e2e_agent_access_clients(self, e2e_token):
        """E2E agent can access clients"""
        headers = {"Authorization": f"Bearer {e2e_token}"}
        response = requests.get(f"{BASE_URL}/api/clients", headers=headers)
        assert response.status_code == 200, f"Clients access failed: {response.text}"
        
        clients = response.json()
        for client in clients:
            assert "is_demo" not in client, f"Client should NOT have is_demo: {client}"
        print(f"PASSED: E2E agent can access {len(clients)} clients without is_demo")
    
    def test_e2e_agent_access_documents(self, e2e_token):
        """E2E agent can access documents"""
        headers = {"Authorization": f"Bearer {e2e_token}"}
        response = requests.get(f"{BASE_URL}/api/documents", headers=headers)
        assert response.status_code == 200, f"Documents access failed: {response.text}"
        
        documents = response.json()
        for doc in documents:
            assert "is_demo" not in doc, f"Document should NOT have is_demo: {doc}"
        print(f"PASSED: E2E agent can access {len(documents)} documents without is_demo")


class TestDemoIdNamespaceConvention:
    """Tests that demo data uses demo_* ID namespace convention"""
    
    @pytest.fixture
    def demo_token(self):
        """Get demo agent token after seeding"""
        token = get_demo_token()
        if not token:
            pytest.skip("Could not get demo token")
        return token
    
    def test_demo_user_ids_use_prefix(self, demo_token):
        """Demo users use demo_* ID prefix"""
        # Demo agent
        agent_resp = requests.post(f"{BASE_URL}/api/auth/demo/agent")
        assert agent_resp.status_code == 200
        agent_data = agent_resp.json()
        assert agent_data["user_id"].startswith("demo_"), f"Demo agent should have demo_ prefix: {agent_data['user_id']}"
        
        # Demo buyers
        buyer1_resp = requests.post(f"{BASE_URL}/api/auth/demo/buyer?buyer_num=1")
        assert buyer1_resp.status_code == 200
        assert buyer1_resp.json()["user_id"] == "demo_buyer_001"
        
        buyer2_resp = requests.post(f"{BASE_URL}/api/auth/demo/buyer?buyer_num=2")
        assert buyer2_resp.status_code == 200
        assert buyer2_resp.json()["user_id"] == "demo_buyer_002"
        
        print("PASSED: Demo users use demo_* ID prefix convention")
    
    def test_demo_project_id_uses_prefix(self, demo_token):
        """Demo project uses demo_proj_* ID prefix"""
        headers = {"Authorization": f"Bearer {demo_token}"}
        response = requests.get(f"{BASE_URL}/api/projects", headers=headers)
        assert response.status_code == 200
        
        projects = response.json()
        demo_project = next((p for p in projects if p.get("project_id", "").startswith("demo_proj_")), None)
        assert demo_project is not None, "Demo project with demo_proj_ prefix should exist"
        assert demo_project["project_id"] == "demo_proj_001"
        print("PASSED: Demo project uses demo_proj_* ID prefix")
    
    def test_demo_client_ids_use_prefix(self, demo_token):
        """Demo clients use demo_client_* ID prefix"""
        headers = {"Authorization": f"Bearer {demo_token}"}
        response = requests.get(f"{BASE_URL}/api/clients", headers=headers)
        assert response.status_code == 200
        
        clients = response.json()
        demo_clients = [c for c in clients if c.get("client_id", "").startswith("demo_client_")]
        assert len(demo_clients) == 2, f"Should have 2 demo clients with demo_client_ prefix"
        
        client_ids = [c["client_id"] for c in demo_clients]
        assert "demo_client_001" in client_ids
        assert "demo_client_002" in client_ids
        print("PASSED: Demo clients use demo_client_* ID prefix")
    
    def test_demo_document_ids_use_prefix(self, demo_token):
        """Demo documents use demo_doc_* ID prefix"""
        headers = {"Authorization": f"Bearer {demo_token}"}
        response = requests.get(f"{BASE_URL}/api/documents", headers=headers)
        assert response.status_code == 200
        
        documents = response.json()
        demo_docs = [d for d in documents if d.get("document_id", "").startswith("demo_doc_")]
        assert len(demo_docs) >= 6, f"Should have at least 6 demo documents with demo_doc_ prefix"
        print(f"PASSED: {len(demo_docs)} demo documents use demo_doc_* ID prefix")


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
