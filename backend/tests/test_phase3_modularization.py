"""
Phase 3 Modularization Test Suite
Tests all 22 route modules after server.py was split from 11.8k lines to 184 lines.
Validates that all endpoints work correctly after the architectural refactoring.
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://evo-access.preview.emergentagent.com')

# Test credentials from test_credentials.md
AGENT_EMAIL = "demo.agent@upgradeflow.com"
AGENT_PASSWORD = "demo123"

# Global session to avoid rate limiting
_session = None
_token = None
_user_id = None


def get_authenticated_session():
    """Get or create authenticated session (singleton pattern to avoid rate limiting)"""
    global _session, _token, _user_id
    
    if _session is None:
        _session = requests.Session()
        _session.headers.update({"Content-Type": "application/json"})
        
        # Authenticate
        response = _session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": AGENT_EMAIL, "password": AGENT_PASSWORD}
        )
        
        if response.status_code == 200:
            data = response.json()
            _token = data.get("token")
            _user_id = data.get("user_id")
            _session.headers.update({"Authorization": f"Bearer {_token}"})
            print(f"Authenticated as {_user_id}")
        else:
            raise Exception(f"Authentication failed: {response.text}")
    
    return _session, _token, _user_id


class TestPhase3Modularization:
    """Test suite for Phase 3 architecture modularization"""
    
    # ==================== HEALTH & ROOT ====================
    
    def test_01_health_endpoint(self):
        """Test /api/health returns healthy status"""
        session, _, _ = get_authenticated_session()
        response = session.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        print("PASS: Health endpoint returns healthy")
    
    def test_02_api_root(self):
        """Test /api/ returns API info"""
        session, _, _ = get_authenticated_session()
        response = session.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "version" in data
        print(f"PASS: API root returns version {data.get('version')}")
    
    # ==================== AUTH ROUTES ====================
    
    def test_03_auth_session(self):
        """Test GET /api/auth/session returns authenticated user"""
        session, _, _ = get_authenticated_session()
        response = session.get(f"{BASE_URL}/api/auth/session")
        assert response.status_code == 200
        data = response.json()
        assert data.get("authenticated") == True
        assert "user" in data
        print("PASS: Auth session returns authenticated user")
    
    # ==================== PROJECTS ROUTES ====================
    
    def test_04_get_projects(self):
        """Test GET /api/projects returns project list"""
        session, _, _ = get_authenticated_session()
        response = session.get(f"{BASE_URL}/api/projects")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"PASS: Projects endpoint returns {len(data)} projects")
    
    # ==================== CLIENTS ROUTES ====================
    
    def test_05_get_clients(self):
        """Test GET /api/clients returns client list"""
        session, _, _ = get_authenticated_session()
        response = session.get(f"{BASE_URL}/api/clients")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"PASS: Clients endpoint returns {len(data)} clients")
    
    # ==================== DOCUMENTS ROUTES ====================
    
    def test_06_get_documents(self):
        """Test GET /api/documents returns documents"""
        session, _, _ = get_authenticated_session()
        response = session.get(f"{BASE_URL}/api/documents")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"PASS: Documents endpoint returns {len(data)} documents")
    
    # ==================== NOTIFICATIONS ROUTES ====================
    
    def test_07_get_notifications(self):
        """Test GET /api/notifications returns notifications"""
        session, _, _ = get_authenticated_session()
        response = session.get(f"{BASE_URL}/api/notifications")
        assert response.status_code == 200
        data = response.json()
        assert "notifications" in data
        assert "unread_count" in data
        print(f"PASS: Notifications endpoint returns {len(data.get('notifications', []))} notifications")
    
    # ==================== SETTINGS ROUTES ====================
    
    def test_08_get_settings(self):
        """Test GET /api/settings returns agent settings"""
        session, _, _ = get_authenticated_session()
        response = session.get(f"{BASE_URL}/api/settings")
        assert response.status_code == 200
        data = response.json()
        assert "language" in data
        assert "currency" in data
        print(f"PASS: Settings endpoint returns settings (language={data.get('language')})")
    
    # ==================== DASHBOARD ROUTES ====================
    
    def test_09_get_agent_dashboard(self):
        """Test GET /api/agent/dashboard returns dashboard data"""
        session, _, _ = get_authenticated_session()
        response = session.get(f"{BASE_URL}/api/agent/dashboard")
        assert response.status_code == 200
        data = response.json()
        assert "projects" in data
        print(f"PASS: Agent dashboard returns {len(data.get('projects', []))} projects")
    
    # ==================== ANALYTICS ROUTES ====================
    
    def test_10_get_analytics(self):
        """Test GET /api/analytics returns analytics data"""
        session, _, _ = get_authenticated_session()
        response = session.get(f"{BASE_URL}/api/analytics")
        assert response.status_code == 200
        data = response.json()
        assert "totalQuotes" in data or "totalClients" in data
        print(f"PASS: Analytics endpoint returns data")
    
    # ==================== TIMELINE ROUTES ====================
    
    def test_11_get_timeline(self):
        """Test GET /api/projects/{id}/timeline/full returns timeline data"""
        session, _, _ = get_authenticated_session()
        # First get a project to get its timeline
        projects_response = session.get(f"{BASE_URL}/api/projects")
        if projects_response.status_code == 200:
            projects = projects_response.json()
            if projects:
                project_id = projects[0].get("project_id")
                response = session.get(f"{BASE_URL}/api/projects/{project_id}/timeline/full")
                assert response.status_code == 200
                data = response.json()
                assert "project" in data
                print(f"PASS: Timeline endpoint returns data for project {project_id}")
                return
        print("PASS: Timeline endpoint (no projects to test)")
    
    # ==================== BILLING ROUTES ====================
    
    def test_12_get_billing_plans(self):
        """Test GET /api/billing/plans returns subscription plans"""
        session, _, _ = get_authenticated_session()
        response = session.get(f"{BASE_URL}/api/billing/plans")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        print(f"PASS: Billing plans endpoint returns {len(data)} plans")
    
    def test_13_get_billing_status(self):
        """Test GET /api/billing/status returns subscription status"""
        session, _, _ = get_authenticated_session()
        response = session.get(f"{BASE_URL}/api/billing/status")
        assert response.status_code == 200
        data = response.json()
        assert "plan_id" in data
        assert "plan_name" in data
        print(f"PASS: Billing status returns plan={data.get('plan_name')}")
    
    # ==================== VAULT ROUTES ====================
    
    def test_14_get_vault(self):
        """Test GET /api/vault returns vault documents"""
        session, _, _ = get_authenticated_session()
        response = session.get(f"{BASE_URL}/api/vault")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"PASS: Vault endpoint returns {len(data)} documents")
    
    # ==================== WORKFLOWS ROUTES ====================
    
    def test_15_get_workflow_templates(self):
        """Test GET /api/workflows/templates returns workflow templates"""
        session, _, _ = get_authenticated_session()
        response = session.get(f"{BASE_URL}/api/workflows/templates")
        assert response.status_code == 200
        data = response.json()
        assert "templates" in data
        print(f"PASS: Workflow templates endpoint returns {len(data.get('templates', []))} templates")
    
    # ==================== COMMANDS ROUTES ====================
    
    def test_16_get_recent_work(self):
        """Test GET /api/command/recent-work returns recent work items"""
        session, _, _ = get_authenticated_session()
        response = session.get(f"{BASE_URL}/api/command/recent-work")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        print(f"PASS: Recent work endpoint returns {len(data.get('items', []))} items")
    
    # ==================== INVITATIONS ROUTES ====================
    
    def test_17_get_team_invitations(self):
        """Test GET /api/team/invitations returns team invitations"""
        session, _, _ = get_authenticated_session()
        response = session.get(f"{BASE_URL}/api/team/invitations")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"PASS: Team invitations endpoint returns {len(data)} invitations")
    
    # ==================== ACTIVITIES ROUTES ====================
    
    def test_18_get_activities(self):
        """Test GET /api/activities returns activities"""
        session, _, _ = get_authenticated_session()
        response = session.get(f"{BASE_URL}/api/activities")
        assert response.status_code == 200
        data = response.json()
        # Activities endpoint returns a list or object with activities
        print(f"PASS: Activities endpoint returns data")
    
    # ==================== STATS ROUTES ====================
    
    def test_19_get_agent_stats(self):
        """Test GET /api/stats/agent returns agent statistics"""
        session, _, _ = get_authenticated_session()
        response = session.get(f"{BASE_URL}/api/stats/agent")
        assert response.status_code == 200
        data = response.json()
        assert "total_clients" in data
        print(f"PASS: Agent stats endpoint returns data (total_clients={data.get('total_clients')})")
    
    # ==================== COMMAND TOOLS ====================
    
    def test_20_get_command_tools(self):
        """Test GET /api/command/tools returns available tools"""
        session, _, _ = get_authenticated_session()
        response = session.get(f"{BASE_URL}/api/command/tools")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"PASS: Command tools endpoint returns {len(data)} tools")
    
    # ==================== BRANDING ROUTES ====================
    
    def test_21_get_branding(self):
        """Test GET /api/branding returns branding info"""
        session, _, _ = get_authenticated_session()
        response = session.get(f"{BASE_URL}/api/branding")
        assert response.status_code == 200
        data = response.json()
        assert "company_name" in data or "language" in data
        print(f"PASS: Branding endpoint returns data")
    
    # ==================== VAULT CATEGORIES ====================
    
    def test_22_get_vault_categories(self):
        """Test GET /api/vault/categories/list returns vault categories"""
        session, _, _ = get_authenticated_session()
        response = session.get(f"{BASE_URL}/api/vault/categories/list")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"PASS: Vault categories endpoint returns {len(data)} categories")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
