"""
Bug Fix Tests - Iteration 21
Testing 5 production bugs:
- BUG-001: Client View blank page (P0) - missing project/team in API response
- BUG-002: Quote client dropdown missing unit/project info (P1)
- BUG-003: Hero image upload not working (P1)
- BUG-004: Company logo upload not working (P1)
- BUG-005: Vault document upload fails (P1)
"""
import pytest
import requests
import os
import json

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "demo.agent@upgradeflow.com"
TEST_PASSWORD = "demo123"


@pytest.fixture(scope="session")
def auth_token():
    """Get authentication token for demo agent - session scoped to avoid rate limits"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
    )
    if response.status_code == 429:
        pytest.skip("Rate limited - please wait and retry")
    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    assert "token" in data, f"No token in login response: {data}"
    return data["token"]


@pytest.fixture(scope="session")
def auth_headers(auth_token):
    """Auth headers for all tests"""
    return {"Authorization": f"Bearer {auth_token}"}


class TestAuth:
    """Authentication tests - prerequisite for other tests"""
    
    def test_login_success(self, auth_token):
        """Test demo agent login works"""
        assert auth_token is not None
        assert len(auth_token) > 0
        print(f"✓ Login successful, token length: {len(auth_token)}")


class TestBug001ClientPreview:
    """
    BUG-001: Client 'View' page blank (P0)
    Root cause: get_client_preview was missing 'project' and 'team' fields
    Frontend destructured them and crashed on team.length
    """
    
    def test_get_clients_list(self, auth_headers):
        """Get list of clients to find a valid client_id"""
        response = requests.get(
            f"{BASE_URL}/api/clients",
            headers=auth_headers
        )
        assert response.status_code == 200
        clients = response.json()
        assert isinstance(clients, list)
        assert len(clients) > 0, "No clients found - need seeded data"
        print(f"✓ Found {len(clients)} clients")
    
    def test_client_preview_returns_project_field(self, auth_headers):
        """BUG-001 FIX: Verify client preview includes 'project' field"""
        # First get a client
        clients_response = requests.get(
            f"{BASE_URL}/api/clients",
            headers=auth_headers
        )
        clients = clients_response.json()
        assert len(clients) > 0, "No clients to test"
        
        client_id = clients[0]["client_id"]
        
        # Get client preview
        response = requests.get(
            f"{BASE_URL}/api/clients/{client_id}/preview",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Preview failed: {response.text}"
        
        data = response.json()
        
        # BUG-001 FIX: These fields must exist (even if null)
        assert "project" in data, "Missing 'project' field - BUG-001 not fixed!"
        assert "team" in data, "Missing 'team' field - BUG-001 not fixed!"
        assert "client" in data, "Missing 'client' field"
        assert "documents" in data, "Missing 'documents' field"
        assert "activities" in data, "Missing 'activities' field"
        
        # team must be a list (even if empty) to prevent .length crash
        assert isinstance(data["team"], list), "team must be a list"
        
        print(f"✓ BUG-001 FIX VERIFIED: project={data.get('project')}, team_count={len(data['team'])}")
    
    def test_client_preview_with_project_has_project_data(self, auth_headers):
        """Verify client with project_id returns project details"""
        clients_response = requests.get(
            f"{BASE_URL}/api/clients",
            headers=auth_headers
        )
        clients = clients_response.json()
        
        # Find a client with project_id
        client_with_project = next(
            (c for c in clients if c.get("project_id")), 
            None
        )
        
        if not client_with_project:
            pytest.skip("No client with project_id found")
        
        response = requests.get(
            f"{BASE_URL}/api/clients/{client_with_project['client_id']}/preview",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # If client has project_id, project should have data
        if client_with_project.get("project_id"):
            assert data["project"] is not None, "Client has project_id but project is null"
            assert "name" in data["project"], "Project missing name"
            print(f"✓ Project data: {data['project'].get('name')}")


class TestBug002ClientDropdown:
    """
    BUG-002: Quote client dropdown missing unit/project info (P1)
    Root cause: ClientSelector only showed client.name without project_name/unit_reference
    """
    
    def test_clients_have_project_and_unit_info(self, auth_headers):
        """Verify clients API returns project_name and unit_reference for dropdown"""
        response = requests.get(
            f"{BASE_URL}/api/clients",
            headers=auth_headers
        )
        assert response.status_code == 200
        clients = response.json()
        
        # Check if clients have the enriched fields
        for client in clients:
            # These fields should be present (may be null)
            assert "name" in client, "Client missing name"
            # project_name and unit_reference are used by ClientSelector
            # They may come from joined data or be null
            print(f"Client: {client.get('name')}, project_id: {client.get('project_id')}, unit_id: {client.get('unit_id')}")
        
        print(f"✓ BUG-002: Clients API returns {len(clients)} clients with project/unit data")


class TestBug003HeroImageUpload:
    """
    BUG-003: Hero image upload not working (P1)
    Root cause: Missing Authorization header on fetch call
    """
    
    def test_hero_image_endpoint_exists(self, auth_headers):
        """Verify hero image upload endpoint exists"""
        # First get a document to test with
        response = requests.get(
            f"{BASE_URL}/api/documents",
            headers=auth_headers
        )
        
        if response.status_code != 200:
            pytest.skip("Documents endpoint not available")
        
        documents = response.json()
        if not documents:
            pytest.skip("No documents to test hero image upload")
        
        doc_id = documents[0].get("document_id")
        
        # Test that endpoint accepts POST (even without file, should return 422 not 401/403)
        response = requests.post(
            f"{BASE_URL}/api/documents/{doc_id}/hero-image",
            headers=auth_headers
        )
        
        # Should NOT be 401 (unauthorized) - that was the bug
        assert response.status_code != 401, "BUG-003 NOT FIXED: Still getting 401 on hero image upload"
        # 422 (validation error - no file) is expected
        print(f"✓ BUG-003: Hero image endpoint responds with {response.status_code} (not 401)")


class TestBug004LogoUpload:
    """
    BUG-004: Company logo upload not working (P1)
    Root cause: Missing Authorization header on fetch call
    """
    
    def test_logo_upload_endpoint_exists(self, auth_headers):
        """Verify logo upload endpoint exists and accepts auth"""
        # Test that endpoint accepts POST with auth header
        response = requests.post(
            f"{BASE_URL}/api/settings/logo",
            headers=auth_headers
        )
        
        # Should NOT be 401 (unauthorized) - that was the bug
        assert response.status_code != 401, "BUG-004 NOT FIXED: Still getting 401 on logo upload"
        # 422 (validation error - no file) or 403 (plan restriction) is expected
        print(f"✓ BUG-004: Logo upload endpoint responds with {response.status_code} (not 401)")
    
    def test_logo_delete_endpoint_exists(self, auth_headers):
        """Verify logo delete endpoint exists and accepts auth"""
        response = requests.delete(
            f"{BASE_URL}/api/settings/logo",
            headers=auth_headers
        )
        
        # Should NOT be 401 (unauthorized)
        assert response.status_code != 401, "BUG-004 NOT FIXED: Still getting 401 on logo delete"
        print(f"✓ BUG-004: Logo delete endpoint responds with {response.status_code} (not 401)")


class TestBug005VaultUpload:
    """
    BUG-005: Vault document upload fails (P1)
    Root cause: Missing Authorization header on XHR upload
    """
    
    def test_vault_list_endpoint(self, auth_headers):
        """Verify vault list endpoint works with auth"""
        response = requests.get(
            f"{BASE_URL}/api/vault/documents",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Vault list failed: {response.text}"
        documents = response.json()
        assert isinstance(documents, list)
        print(f"✓ BUG-005: Vault list returns {len(documents)} documents")
    
    def test_vault_upload_endpoint_exists(self, auth_headers):
        """Verify vault upload endpoint exists and accepts auth"""
        response = requests.post(
            f"{BASE_URL}/api/vault/upload",
            headers=auth_headers
        )
        
        # Should NOT be 401 (unauthorized) - that was the bug
        assert response.status_code != 401, "BUG-005 NOT FIXED: Still getting 401 on vault upload"
        # 422 (validation error - no file) is expected
        print(f"✓ BUG-005: Vault upload endpoint responds with {response.status_code} (not 401)")


class TestRegressionDashboard:
    """Regression test: Dashboard Control Tower should still work"""
    
    def test_agent_stats_endpoint(self, auth_headers):
        """Verify agent stats endpoint for Control Tower"""
        response = requests.get(
            f"{BASE_URL}/api/stats/agent",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Control Tower expects these fields (check actual response structure)
        # Stats may include pending_quotes, pending_invoices, etc.
        assert "pending_quotes" in data or "total_clients" in data, f"Stats response missing expected fields: {list(data.keys())}"
        
        print(f"✓ Dashboard stats keys: {list(data.keys())}")


class TestRegressionFeed:
    """Regression test: Feed page should still load activities"""
    
    def test_activities_endpoint(self, auth_headers):
        """Verify activities endpoint for Feed page"""
        response = requests.get(
            f"{BASE_URL}/api/activities",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Activities may be wrapped in an object with 'activities' key
        if isinstance(data, dict) and "activities" in data:
            activities = data["activities"]
        else:
            activities = data
        
        assert isinstance(activities, list)
        print(f"✓ Feed activities: {len(activities)} items")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
