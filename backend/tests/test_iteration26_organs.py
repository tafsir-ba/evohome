"""
Iteration 26 Tests: Three Contaminated Organs Rebuild
- Client context enrichment (unit_reference from units collection)
- Change request thread visibility for buyers
- Auth headers on document send/delete
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://evo-access.preview.emergentagent.com')

# Test credentials
AGENT_EMAIL = "agent@evohome-test.ch"
AGENT_PASSWORD = "Evohome2026!"
BUYER_EMAIL = "buyer@evohome-test.ch"
BUYER_PASSWORD = "Evohome2026!"


@pytest.fixture(scope="module")
def agent_token():
    """Get agent auth token"""
    res = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": AGENT_EMAIL,
        "password": AGENT_PASSWORD
    })
    assert res.status_code == 200, f"Agent login failed: {res.text}"
    return res.json()["token"]


@pytest.fixture(scope="module")
def buyer_token():
    """Get buyer auth token - uses separate endpoint"""
    res = requests.post(f"{BASE_URL}/api/auth/buyer/login", json={
        "email": BUYER_EMAIL,
        "password": BUYER_PASSWORD
    })
    assert res.status_code == 200, f"Buyer login failed: {res.text}"
    return res.json()["token"]


class TestClientContextEnrichment:
    """Test client context enrichment with unit_reference from units collection"""
    
    def test_clients_list_returns_unit_reference(self, agent_token):
        """GET /api/clients should return unit_reference resolved from units collection"""
        res = requests.get(
            f"{BASE_URL}/api/clients",
            headers={"Authorization": f"Bearer {agent_token}"}
        )
        assert res.status_code == 200
        clients = res.json()
        
        # Check that at least one client has unit_reference
        clients_with_unit = [c for c in clients if c.get("unit_reference")]
        assert len(clients_with_unit) > 0, "No clients have unit_reference"
        
        # Verify the format
        for client in clients_with_unit:
            assert client["unit_reference"] is not None
            assert isinstance(client["unit_reference"], str)
            print(f"Client {client['name']}: unit_reference={client['unit_reference']}")
    
    def test_clients_list_returns_project_name(self, agent_token):
        """GET /api/clients should also return project_name"""
        res = requests.get(
            f"{BASE_URL}/api/clients",
            headers={"Authorization": f"Bearer {agent_token}"}
        )
        assert res.status_code == 200
        clients = res.json()
        
        # Check that clients with project_id have project_name
        clients_with_project = [c for c in clients if c.get("project_id")]
        for client in clients_with_project:
            assert "project_name" in client, f"Client {client['name']} missing project_name"
            print(f"Client {client['name']}: project_name={client.get('project_name')}")


class TestChangeRequestThread:
    """Test change request thread visibility for buyers"""
    
    def test_buyer_can_see_change_request_thread(self, buyer_token):
        """Buyer should see full change request thread including agent responses"""
        # Test with known document that has change request
        doc_id = "doc_4f7a267d9b3f"
        res = requests.get(
            f"{BASE_URL}/api/change-requests/entity/quote/{doc_id}",
            headers={"Authorization": f"Bearer {buyer_token}"}
        )
        assert res.status_code == 200
        data = res.json()
        
        change_requests = data.get("change_requests", [])
        assert len(change_requests) > 0, "No change requests found for test document"
        
        # Check the most recent change request
        cr = change_requests[0]
        assert "messages" in cr
        messages = cr["messages"]
        assert len(messages) >= 2, f"Expected at least 2 messages (buyer + agent), got {len(messages)}"
        
        # Verify both buyer and agent messages are present
        roles = [m["author_role"] for m in messages]
        assert "buyer" in roles, "Buyer message not found in thread"
        assert "agent" in roles, "Agent response not found in thread"
        
        print(f"Change request {cr['change_request_id']}: {len(messages)} messages")
        for msg in messages:
            print(f"  - [{msg['author_role']}] {msg['content'][:50]}...")
    
    def test_change_request_status_visible(self, buyer_token):
        """Buyer should see change request status"""
        doc_id = "doc_4f7a267d9b3f"
        res = requests.get(
            f"{BASE_URL}/api/change-requests/entity/quote/{doc_id}",
            headers={"Authorization": f"Bearer {buyer_token}"}
        )
        assert res.status_code == 200
        data = res.json()
        
        cr = data["change_requests"][0]
        assert "status" in cr
        assert cr["status"] in ["open", "under_review", "resolved", "closed"]
        print(f"Change request status: {cr['status']}")


class TestBuyerTimeline:
    """Test buyer timeline API"""
    
    def test_timeline_returns_documents(self, buyer_token):
        """GET /api/timeline should return documents"""
        res = requests.get(
            f"{BASE_URL}/api/timeline",
            headers={"Authorization": f"Bearer {buyer_token}"}
        )
        assert res.status_code == 200
        data = res.json()
        
        assert "documents" in data
        docs = data["documents"]
        assert len(docs) > 0, "No documents in timeline"
        
        # Check document structure
        for doc in docs:
            assert "id" in doc or "document_id" in doc
            assert "title" in doc
            assert "status" in doc
            # heroImageUrl can be None if no hero image uploaded
            assert "heroImageUrl" in doc or "hero_image_url" in doc
            print(f"Timeline doc: {doc['title']}, status={doc['status']}")
    
    def test_timeline_includes_project_info(self, buyer_token):
        """Timeline should include project info"""
        res = requests.get(
            f"{BASE_URL}/api/timeline",
            headers={"Authorization": f"Bearer {buyer_token}"}
        )
        assert res.status_code == 200
        data = res.json()
        
        # Project info should be present
        assert "project_info" in data
        if data["project_info"]:
            print(f"Project info: {data['project_info']}")


class TestAgentDocumentActions:
    """Test agent document actions with auth headers"""
    
    def test_agent_can_get_document(self, agent_token):
        """Agent should be able to get document details"""
        doc_id = "doc_4f7a267d9b3f"
        res = requests.get(
            f"{BASE_URL}/api/documents/{doc_id}",
            headers={"Authorization": f"Bearer {agent_token}"}
        )
        assert res.status_code == 200
        doc = res.json()
        assert doc["title"] == "Kitchen Upgrade Premium"
        assert doc["type"] == "quote"
        print(f"Document: {doc['title']}, status={doc['status']}")
    
    def test_agent_documents_list(self, agent_token):
        """Agent should be able to list documents"""
        res = requests.get(
            f"{BASE_URL}/api/documents",
            headers={"Authorization": f"Bearer {agent_token}"}
        )
        assert res.status_code == 200
        docs = res.json()
        assert isinstance(docs, list)
        print(f"Agent has {len(docs)} documents")


class TestVaultSystem:
    """Test vault document system"""
    
    def test_vault_list_endpoint(self, agent_token):
        """GET /api/vault/documents should work"""
        res = requests.get(
            f"{BASE_URL}/api/vault/documents",
            headers={"Authorization": f"Bearer {agent_token}"}
        )
        assert res.status_code == 200
        docs = res.json()
        assert isinstance(docs, list)
        print(f"Vault has {len(docs)} documents")
    
    def test_vault_upload_endpoint_exists(self, agent_token):
        """POST /api/vault/upload endpoint should exist"""
        # Just check the endpoint exists (don't actually upload)
        res = requests.post(
            f"{BASE_URL}/api/vault/upload",
            headers={"Authorization": f"Bearer {agent_token}"},
            data={}  # Empty data to trigger validation error, not 404
        )
        # Should get 422 (validation error) not 404 (not found)
        assert res.status_code != 404, "Vault upload endpoint not found"
        print(f"Vault upload endpoint exists (status: {res.status_code})")


class TestAuthHeadersOnActions:
    """Test that auth headers are properly included in document actions"""
    
    def test_document_send_requires_auth(self):
        """Document send should require auth"""
        doc_id = "doc_4f7a267d9b3f"
        res = requests.post(f"{BASE_URL}/api/documents/{doc_id}/send")
        assert res.status_code in [401, 403], f"Expected auth error, got {res.status_code}"
    
    def test_document_delete_requires_auth(self):
        """Document delete should require auth"""
        doc_id = "doc_4f7a267d9b3f"
        res = requests.delete(f"{BASE_URL}/api/documents/{doc_id}")
        assert res.status_code in [401, 403], f"Expected auth error, got {res.status_code}"
    
    def test_document_send_with_auth(self, agent_token):
        """Document send should work with auth (but may fail for other reasons)"""
        doc_id = "doc_4f7a267d9b3f"
        res = requests.post(
            f"{BASE_URL}/api/documents/{doc_id}/send",
            headers={"Authorization": f"Bearer {agent_token}"}
        )
        # Should not be 401/403 - may be 400 if already sent or other business logic
        assert res.status_code not in [401, 403], f"Auth should work, got {res.status_code}"
        print(f"Document send with auth: status={res.status_code}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
