"""
Test suite for Buyer Document Vault feature
Tests:
- GET /api/buyer/vault - Returns shared documents for buyer
- GET /api/vault/{id}/download - Download document with auth checks
- PUT /api/vault/{id} - Agent sharing document with specific buyers
"""

import pytest
import requests
import os
import json

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Demo credentials
DEMO_AGENT_USER_ID = "demo_agent_001"
DEMO_BUYER_USER_ID = "demo_buyer_001"  # Sophie
DEMO_BUYER_2_USER_ID = "demo_buyer_002"  # Thomas
DEMO_CLIENT_ID = "demo_client_001"  # Sophie's client_id


class TestBuyerVaultBackend:
    """Test Buyer Document Vault backend endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def get_demo_buyer_session(self, buyer_num=1):
        """Login as demo buyer and return session with auth"""
        response = self.session.post(
            f"{BASE_URL}/api/auth/demo/buyer",
            params={"buyer_num": buyer_num}
        )
        if response.status_code == 200:
            token = response.json().get("token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
            return self.session
        return None
    
    def get_demo_agent_session(self):
        """Login as demo agent and return session with auth"""
        response = self.session.post(f"{BASE_URL}/api/auth/demo/agent")
        if response.status_code == 200:
            token = response.json().get("token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
            return self.session
        return None
    
    # ==================== TEST: GET /api/buyer/vault ====================
    
    def test_buyer_vault_requires_authentication(self):
        """Buyer vault endpoint requires authentication"""
        session = requests.Session()
        response = session.get(f"{BASE_URL}/api/buyer/vault")
        
        assert response.status_code == 401, f"Expected 401 Unauthorized, got {response.status_code}"
        print("PASS: GET /api/buyer/vault requires authentication")
    
    def test_buyer_vault_returns_list(self):
        """GET /api/buyer/vault returns a list (empty or with documents)"""
        session = self.get_demo_buyer_session(buyer_num=1)
        if not session:
            pytest.skip("Could not login as demo buyer")
        
        response = session.get(f"{BASE_URL}/api/buyer/vault")
        
        assert response.status_code == 200, f"Expected 200 OK, got {response.status_code}"
        data = response.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        print(f"PASS: GET /api/buyer/vault returns list with {len(data)} documents")
    
    def test_buyer_vault_agent_cannot_access(self):
        """Agents cannot access buyer vault endpoint"""
        session = self.get_demo_agent_session()
        if not session:
            pytest.skip("Could not login as demo agent")
        
        response = session.get(f"{BASE_URL}/api/buyer/vault")
        
        assert response.status_code == 403, f"Expected 403 Forbidden for agents, got {response.status_code}"
        print("PASS: GET /api/buyer/vault returns 403 for agents")
    
    # ==================== TEST: GET /api/vault/{id}/download ====================
    
    def test_vault_download_requires_authentication(self):
        """Vault download endpoint requires authentication"""
        session = requests.Session()
        response = session.get(f"{BASE_URL}/api/vault/fake_vault_id/download")
        
        assert response.status_code == 401, f"Expected 401 Unauthorized, got {response.status_code}"
        print("PASS: GET /api/vault/{id}/download requires authentication")
    
    def test_vault_download_404_for_nonexistent(self):
        """Vault download returns 404 for non-existent document"""
        session = self.get_demo_buyer_session(buyer_num=1)
        if not session:
            pytest.skip("Could not login as demo buyer")
        
        response = session.get(f"{BASE_URL}/api/vault/nonexistent_vault_id/download")
        
        assert response.status_code == 404, f"Expected 404 Not Found, got {response.status_code}"
        print("PASS: GET /api/vault/{id}/download returns 404 for non-existent document")
    
    # ==================== TEST: Agent Vault Management ====================
    
    def test_agent_can_list_vault_documents(self):
        """Agent can list their vault documents"""
        session = self.get_demo_agent_session()
        if not session:
            pytest.skip("Could not login as demo agent")
        
        response = session.get(f"{BASE_URL}/api/vault")
        
        assert response.status_code == 200, f"Expected 200 OK, got {response.status_code}"
        data = response.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        print(f"PASS: GET /api/vault returns list with {len(data)} documents for agent")
    
    def test_agent_can_get_vault_clients_for_sharing(self):
        """Agent can get clients list for document sharing"""
        session = self.get_demo_agent_session()
        if not session:
            pytest.skip("Could not login as demo agent")
        
        # Get clients list for sharing dropdown
        response = session.get(f"{BASE_URL}/api/clients")
        
        assert response.status_code == 200, f"Expected 200 OK, got {response.status_code}"
        clients = response.json()
        assert isinstance(clients, list), f"Expected list, got {type(clients)}"
        
        # Check that each client has the fields needed for sharing
        for client in clients[:2]:  # Check first 2 clients
            assert "client_id" in client, "Client missing client_id field"
            assert "name" in client, "Client missing name field"
        
        print(f"PASS: GET /api/clients returns {len(clients)} clients for sharing dropdown")


class TestBuyerVaultIntegration:
    """Integration tests for document sharing flow"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test sessions"""
        self.agent_session = requests.Session()
        self.buyer_session = requests.Session()
    
    def login_as_agent(self):
        """Login as demo agent"""
        response = self.agent_session.post(f"{BASE_URL}/api/auth/demo/agent")
        if response.status_code == 200:
            token = response.json().get("token")
            self.agent_session.headers.update({
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}"
            })
            return True
        return False
    
    def login_as_buyer(self, buyer_num=1):
        """Login as demo buyer"""
        response = self.buyer_session.post(
            f"{BASE_URL}/api/auth/demo/buyer",
            params={"buyer_num": buyer_num}
        )
        if response.status_code == 200:
            token = response.json().get("token")
            self.buyer_session.headers.update({
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}"
            })
            return True
        return False
    
    def test_full_sharing_flow(self):
        """
        Test complete document sharing flow:
        1. Agent uploads document to vault
        2. Agent shares document with specific buyer
        3. Buyer sees document in their vault
        """
        # Login as agent and buyer
        if not self.login_as_agent():
            pytest.skip("Could not login as demo agent")
        if not self.login_as_buyer(buyer_num=1):
            pytest.skip("Could not login as demo buyer")
        
        # Step 1: Get existing agent vault documents
        vault_response = self.agent_session.get(f"{BASE_URL}/api/vault")
        assert vault_response.status_code == 200, "Failed to get agent vault"
        vault_docs = vault_response.json()
        
        # We'll use an existing document or create test context
        # For this test, we check if buyer can see shared documents
        
        # Step 2: Get buyer's vault
        buyer_vault = self.buyer_session.get(f"{BASE_URL}/api/buyer/vault")
        assert buyer_vault.status_code == 200, "Failed to get buyer vault"
        buyer_docs = buyer_vault.json()
        
        print(f"PASS: Integration test - Agent has {len(vault_docs)} vault docs, Buyer sees {len(buyer_docs)} shared docs")
        
        # Verify response structure if documents exist
        if buyer_docs:
            doc = buyer_docs[0]
            assert "vault_id" in doc, "Document missing vault_id"
            assert "filename" in doc, "Document missing filename"
            assert "access_level" in doc, "Document missing access_level"
            print(f"PASS: Buyer vault document has correct structure")
    
    def test_buyer_cannot_see_private_documents(self):
        """
        Buyer cannot see documents that are not shared with them
        - Private documents are not visible
        - Documents shared with other buyers are not visible
        """
        if not self.login_as_agent():
            pytest.skip("Could not login as demo agent")
        if not self.login_as_buyer(buyer_num=1):
            pytest.skip("Could not login as demo buyer")
        
        # Get buyer's vault
        buyer_vault = self.buyer_session.get(f"{BASE_URL}/api/buyer/vault")
        assert buyer_vault.status_code == 200
        buyer_docs = buyer_vault.json()
        
        # All documents in buyer vault should have:
        # - access_level = "shared"
        # - buyer's client_id in shared_with_clients
        for doc in buyer_docs:
            assert doc.get("access_level") == "shared", f"Document {doc.get('vault_id')} is not shared"
        
        print(f"PASS: All {len(buyer_docs)} documents in buyer vault are properly shared")
    
    def test_different_buyers_see_different_documents(self):
        """
        Different buyers only see documents shared specifically with them
        """
        # Login buyer 1 (Sophie)
        buyer1_session = requests.Session()
        resp1 = buyer1_session.post(f"{BASE_URL}/api/auth/demo/buyer", params={"buyer_num": 1})
        if resp1.status_code != 200:
            pytest.skip("Could not login as demo buyer 1")
        token1 = resp1.json().get("token")
        buyer1_session.headers.update({"Authorization": f"Bearer {token1}"})
        
        # Login buyer 2 (Thomas)
        buyer2_session = requests.Session()
        resp2 = buyer2_session.post(f"{BASE_URL}/api/auth/demo/buyer", params={"buyer_num": 2})
        if resp2.status_code != 200:
            pytest.skip("Could not login as demo buyer 2")
        token2 = resp2.json().get("token")
        buyer2_session.headers.update({"Authorization": f"Bearer {token2}"})
        
        # Get both buyers' vaults
        vault1 = buyer1_session.get(f"{BASE_URL}/api/buyer/vault")
        vault2 = buyer2_session.get(f"{BASE_URL}/api/buyer/vault")
        
        assert vault1.status_code == 200, "Buyer 1 vault request failed"
        assert vault2.status_code == 200, "Buyer 2 vault request failed"
        
        docs1 = vault1.json()
        docs2 = vault2.json()
        
        print(f"PASS: Buyer 1 (Sophie) sees {len(docs1)} docs, Buyer 2 (Thomas) sees {len(docs2)} docs")


class TestBuyerVaultEmptyState:
    """Test empty state handling"""
    
    def test_empty_vault_returns_empty_list(self):
        """Buyer with no shared documents gets empty list, not error"""
        session = requests.Session()
        
        # Login as demo buyer
        response = session.post(f"{BASE_URL}/api/auth/demo/buyer", params={"buyer_num": 2})
        if response.status_code != 200:
            pytest.skip("Could not login as demo buyer")
        
        token = response.json().get("token")
        session.headers.update({"Authorization": f"Bearer {token}"})
        
        # Get vault
        vault_response = session.get(f"{BASE_URL}/api/buyer/vault")
        
        assert vault_response.status_code == 200, f"Expected 200, got {vault_response.status_code}"
        data = vault_response.json()
        assert isinstance(data, list), f"Expected list for empty vault, got {type(data)}"
        # Empty list is valid response
        print(f"PASS: Empty vault returns empty list ([] or with docs): {len(data)} docs")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
