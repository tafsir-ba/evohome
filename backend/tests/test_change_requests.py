"""
Test suite for FEAT-002: Unified Change Request System
Tests the full lifecycle: create, respond, resolve, close
"""
import pytest
import requests
import os
import uuid
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
DEMO_AGENT_EMAIL = "demo.agent@upgradeflow.com"
DEMO_AGENT_PASSWORD = "demo123"

# Shared token cache to avoid rate limiting
_token_cache = {}

def get_auth_token():
    """Get authentication token with caching and retry"""
    if "token" in _token_cache:
        return _token_cache["token"]
    
    for attempt in range(3):
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": DEMO_AGENT_EMAIL, "password": DEMO_AGENT_PASSWORD}
        )
        if response.status_code == 200:
            data = response.json()
            token = data.get("access_token") or data.get("token")
            _token_cache["token"] = token
            return token
        time.sleep(1)  # Wait before retry
    
    raise Exception(f"Login failed after 3 attempts: {response.text}")


class TestChangeRequestLifecycle:
    """Full lifecycle tests for change request system"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token for demo agent"""
        return get_auth_token()
    
    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        """Auth headers for requests"""
        return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}
    
    @pytest.fixture(scope="class")
    def test_invoice_id(self, auth_headers):
        """Get a test invoice ID from the demo data"""
        response = requests.get(
            f"{BASE_URL}/api/documents?type=invoice&limit=1",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed to get invoices: {response.text}"
        data = response.json()
        # API may return list directly or wrapped in 'documents'
        documents = data.get("documents", data) if isinstance(data, dict) else data
        if not documents:
            pytest.skip("No invoices found in demo data")
        return documents[0]["document_id"]
    
    def test_01_create_change_request(self, auth_headers, test_invoice_id):
        """Test POST /api/change-requests creates a change request"""
        unique_msg = f"TEST_CR_{uuid.uuid4().hex[:8]}: Please review the line items"
        
        response = requests.post(
            f"{BASE_URL}/api/change-requests",
            headers=auth_headers,
            json={
                "entity_type": "invoice",
                "entity_id": test_invoice_id,
                "message": unique_msg
            }
        )
        
        assert response.status_code == 200, f"Create CR failed: {response.text}"
        data = response.json()
        
        # Verify response shape
        assert "change_request_id" in data, "Missing change_request_id"
        assert data["entity_type"] == "invoice"
        assert data["entity_id"] == test_invoice_id
        assert data["status"] == "open"
        assert "messages" in data
        assert len(data["messages"]) == 1
        assert data["messages"][0]["content"] == unique_msg
        
        # Store for subsequent tests
        TestChangeRequestLifecycle.created_cr_id = data["change_request_id"]
        print(f"Created change request: {data['change_request_id']}")
    
    def test_02_list_change_requests(self, auth_headers):
        """Test GET /api/change-requests lists change requests for agent"""
        response = requests.get(
            f"{BASE_URL}/api/change-requests",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"List CRs failed: {response.text}"
        data = response.json()
        
        assert "change_requests" in data
        assert "total" in data
        assert isinstance(data["change_requests"], list)
        
        # Verify our created CR is in the list
        cr_ids = [cr["change_request_id"] for cr in data["change_requests"]]
        assert TestChangeRequestLifecycle.created_cr_id in cr_ids, "Created CR not in list"
        print(f"Found {data['total']} change requests")
    
    def test_03_get_entity_change_requests(self, auth_headers, test_invoice_id):
        """Test GET /api/change-requests/entity/{type}/{id} returns change requests for entity"""
        response = requests.get(
            f"{BASE_URL}/api/change-requests/entity/invoice/{test_invoice_id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Get entity CRs failed: {response.text}"
        data = response.json()
        
        assert "change_requests" in data
        assert isinstance(data["change_requests"], list)
        
        # Our created CR should be here
        cr_ids = [cr["change_request_id"] for cr in data["change_requests"]]
        assert TestChangeRequestLifecycle.created_cr_id in cr_ids, "Created CR not found for entity"
        print(f"Found {len(data['change_requests'])} change requests for invoice")
    
    def test_04_respond_to_change_request(self, auth_headers):
        """Test POST /api/change-requests/{id}/respond adds a message"""
        cr_id = TestChangeRequestLifecycle.created_cr_id
        response_msg = f"TEST_RESPONSE_{uuid.uuid4().hex[:8]}: We will review this"
        
        response = requests.post(
            f"{BASE_URL}/api/change-requests/{cr_id}/respond",
            headers=auth_headers,
            json={"message": response_msg}
        )
        
        assert response.status_code == 200, f"Respond failed: {response.text}"
        data = response.json()
        
        # Verify response added
        assert len(data["messages"]) == 2, "Response message not added"
        assert data["messages"][1]["content"] == response_msg
        assert data["status"] == "under_review", "Status should be under_review after response"
        print(f"Added response to CR, now has {len(data['messages'])} messages")
    
    def test_05_resolve_change_request(self, auth_headers):
        """Test POST /api/change-requests/{id}/resolve marks as resolved"""
        cr_id = TestChangeRequestLifecycle.created_cr_id
        
        response = requests.post(
            f"{BASE_URL}/api/change-requests/{cr_id}/resolve",
            headers=auth_headers,
            json={"resolution_note": "Changes have been made"}
        )
        
        assert response.status_code == 200, f"Resolve failed: {response.text}"
        data = response.json()
        
        assert data["status"] == "resolved"
        assert data["resolved_at"] is not None
        # Resolution note should be added as a message
        assert len(data["messages"]) == 3, "Resolution note not added as message"
        print(f"Resolved CR, status: {data['status']}")
    
    def test_06_close_change_request(self, auth_headers):
        """Test POST /api/change-requests/{id}/close marks as closed"""
        cr_id = TestChangeRequestLifecycle.created_cr_id
        
        response = requests.post(
            f"{BASE_URL}/api/change-requests/{cr_id}/close",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Close failed: {response.text}"
        data = response.json()
        
        assert data["status"] == "closed"
        print(f"Closed CR, final status: {data['status']}")
    
    def test_07_get_single_change_request(self, auth_headers):
        """Test GET /api/change-requests/{id} returns single CR"""
        cr_id = TestChangeRequestLifecycle.created_cr_id
        
        response = requests.get(
            f"{BASE_URL}/api/change-requests/{cr_id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Get single CR failed: {response.text}"
        data = response.json()
        
        assert data["change_request_id"] == cr_id
        assert data["status"] == "closed"
        print(f"Retrieved CR: {cr_id}")


class TestStatsEndpoint:
    """Test stats endpoint includes change request counts"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token for demo agent"""
        return get_auth_token()
    
    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}
    
    def test_stats_includes_change_requests(self, auth_headers):
        """Test /api/stats/agent includes open_change_requests count"""
        response = requests.get(
            f"{BASE_URL}/api/stats/agent",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Stats failed: {response.text}"
        data = response.json()
        
        # Verify change request fields exist
        assert "change_requests" in data, "Missing change_requests field"
        assert "open_change_requests" in data, "Missing open_change_requests count"
        assert isinstance(data["open_change_requests"], int)
        print(f"Stats: open_change_requests={data['open_change_requests']}, change_requests count={len(data['change_requests'])}")


class TestAuthHeaderAudit:
    """Test that pages load without 401 errors (auth header audit)"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token for demo agent"""
        return get_auth_token()
    
    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}
    
    def test_documents_endpoint(self, auth_headers):
        """Test /api/documents works with auth"""
        response = requests.get(f"{BASE_URL}/api/documents", headers=auth_headers)
        assert response.status_code == 200, f"Documents endpoint failed: {response.text}"
    
    def test_projects_endpoint(self, auth_headers):
        """Test /api/projects works with auth"""
        response = requests.get(f"{BASE_URL}/api/projects", headers=auth_headers)
        assert response.status_code == 200, f"Projects endpoint failed: {response.text}"
    
    def test_clients_endpoint(self, auth_headers):
        """Test /api/clients works with auth"""
        response = requests.get(f"{BASE_URL}/api/clients", headers=auth_headers)
        assert response.status_code == 200, f"Clients endpoint failed: {response.text}"
    
    def test_activities_endpoint(self, auth_headers):
        """Test /api/activities works with auth"""
        response = requests.get(f"{BASE_URL}/api/activities", headers=auth_headers)
        assert response.status_code == 200, f"Activities endpoint failed: {response.text}"
    
    def test_notifications_endpoint(self, auth_headers):
        """Test /api/notifications works with auth"""
        response = requests.get(f"{BASE_URL}/api/notifications", headers=auth_headers)
        assert response.status_code == 200, f"Notifications endpoint failed: {response.text}"
    
    def test_vault_endpoint(self, auth_headers):
        """Test /api/vault/documents works with auth"""
        response = requests.get(f"{BASE_URL}/api/vault/documents", headers=auth_headers)
        assert response.status_code == 200, f"Vault endpoint failed: {response.text}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
