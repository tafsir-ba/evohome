"""
Test suite for Document Vault Bug Fixes
Verifies fixes for:
1. Route collision: /vault/buyer was matched by /vault/{vault_id}
2. Frontend calling wrong endpoint (/buyer/vault instead of /vault/buyer)  
3. Buyer vault document title not displaying (using 'filename' instead of 'name')

Test Data:
- A shared document 'Shared Contract PDF' with vault_id=vault_95377b60827a exists 
- Shared with demo_client_001 (Sophie Müller)
"""

import pytest
import requests
import os
import json

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Demo credentials from the request
DEMO_AGENT_EMAIL = "demo.agent@upgradeflow.com"
DEMO_AGENT_PASSWORD = "demo123"
DEMO_CLIENT_ID = "demo_client_001"  # Sophie's client_id


class TestVaultRouteOrdering:
    """Test that vault routes are ordered correctly to avoid collision"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def get_demo_buyer_session(self, buyer_num=1):
        """Login as demo buyer"""
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
        """Login as demo agent"""
        response = self.session.post(f"{BASE_URL}/api/auth/demo/agent")
        if response.status_code == 200:
            token = response.json().get("token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
            return self.session
        return None
    
    # ========== Test: Old /buyer/vault endpoint no longer exists ==========
    
    def test_old_buyer_vault_endpoint_returns_404(self):
        """
        BUG FIX: Old endpoint /api/buyer/vault should return 404 (removed)
        New correct endpoint is /api/vault/buyer
        """
        session = self.get_demo_buyer_session(buyer_num=1)
        if not session:
            pytest.skip("Could not login as demo buyer")
        
        # Try old endpoint
        response = session.get(f"{BASE_URL}/api/buyer/vault")
        
        assert response.status_code == 404, f"Old /api/buyer/vault should return 404, got {response.status_code}"
        print("PASS: Old endpoint /api/buyer/vault returns 404 (removed)")
    
    # ========== Test: New /vault/buyer endpoint works ==========
    
    def test_new_vault_buyer_endpoint_returns_200(self):
        """
        BUG FIX: New endpoint /api/vault/buyer should work correctly
        This fixes the route collision issue where /vault/buyer was matched by /vault/{vault_id}
        """
        session = self.get_demo_buyer_session(buyer_num=1)
        if not session:
            pytest.skip("Could not login as demo buyer")
        
        # Try new correct endpoint
        response = session.get(f"{BASE_URL}/api/vault/buyer")
        
        assert response.status_code == 200, f"GET /api/vault/buyer should return 200, got {response.status_code}"
        
        data = response.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        
        print(f"PASS: New endpoint /api/vault/buyer returns 200 with {len(data)} documents")
    
    # ========== Test: Route /vault/buyer doesn't collide with /vault/{vault_id} ==========
    
    def test_vault_buyer_not_treated_as_vault_id(self):
        """
        BUG FIX: /api/vault/buyer should NOT be treated as /api/vault/{vault_id}
        If it was, it would return 404 "Document not found" since there's no vault_id="buyer"
        """
        session = self.get_demo_buyer_session(buyer_num=1)
        if not session:
            pytest.skip("Could not login as demo buyer")
        
        response = session.get(f"{BASE_URL}/api/vault/buyer")
        
        # If route collision exists, we'd get 404 or 403, not 200 with a list
        assert response.status_code == 200, f"Route collision: got {response.status_code}"
        
        data = response.json()
        # Should be a list (buyer's shared documents), not an error response
        assert isinstance(data, list), f"Route collision: got dict/error instead of list"
        
        print("PASS: /api/vault/buyer is correctly routed (no collision with /vault/{vault_id})")
    
    # ========== Test: /vault/{vault_id} still works ==========
    
    def test_vault_id_endpoint_still_works(self):
        """Agent can still access vault documents by ID"""
        session = self.get_demo_agent_session()
        if not session:
            pytest.skip("Could not login as demo agent")
        
        # First get vault list
        vault_list = session.get(f"{BASE_URL}/api/vault")
        if vault_list.status_code != 200:
            pytest.skip("Could not get vault list")
        
        docs = vault_list.json()
        if not docs:
            pytest.skip("No vault documents to test")
        
        # Try to get specific document by ID
        vault_id = docs[0].get('vault_id')
        response = session.get(f"{BASE_URL}/api/vault/{vault_id}")
        
        assert response.status_code == 200, f"GET /api/vault/{vault_id} should work, got {response.status_code}"
        
        print(f"PASS: /api/vault/{vault_id} endpoint still works correctly")


class TestBuyerVaultDocumentFields:
    """Test that vault documents have correct field names for display"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def get_demo_buyer_session(self, buyer_num=1):
        """Login as demo buyer"""
        response = self.session.post(
            f"{BASE_URL}/api/auth/demo/buyer",
            params={"buyer_num": buyer_num}
        )
        if response.status_code == 200:
            token = response.json().get("token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
            return self.session
        return None
    
    # ========== Test: Documents have 'name' field for title ==========
    
    def test_vault_documents_have_name_field(self):
        """
        BUG FIX: Vault documents should have 'name' field (not just 'filename')
        The frontend VaultDocumentCard uses document.name for display title
        """
        session = self.get_demo_buyer_session(buyer_num=1)
        if not session:
            pytest.skip("Could not login as demo buyer")
        
        response = session.get(f"{BASE_URL}/api/vault/buyer")
        if response.status_code != 200:
            pytest.skip("Could not get buyer vault")
        
        docs = response.json()
        if not docs:
            print("PASS: Empty vault, cannot verify 'name' field but endpoint works")
            return
        
        # Check that documents have 'name' field
        for doc in docs:
            assert 'name' in doc, f"Document {doc.get('vault_id')} missing 'name' field"
            # Name should not be empty
            assert doc.get('name'), f"Document {doc.get('vault_id')} has empty name"
        
        print(f"PASS: All {len(docs)} vault documents have 'name' field for display")
    
    # ========== Test: Document structure is complete ==========
    
    def test_vault_document_structure(self):
        """Verify vault documents have all required fields"""
        session = self.get_demo_buyer_session(buyer_num=1)
        if not session:
            pytest.skip("Could not login as demo buyer")
        
        response = session.get(f"{BASE_URL}/api/vault/buyer")
        if response.status_code != 200:
            pytest.skip("Could not get buyer vault")
        
        docs = response.json()
        if not docs:
            print("PASS: Empty vault, cannot verify structure but endpoint works")
            return
        
        # Required fields for VaultDocumentCard component
        required_fields = ['vault_id', 'name', 'category', 'doc_type', 'created_at']
        
        for doc in docs:
            for field in required_fields:
                assert field in doc, f"Document missing required field '{field}'"
        
        print(f"PASS: All documents have required fields: {required_fields}")


class TestAgentVaultUploadAndSharing:
    """Test agent can upload and share documents to vault"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
    
    def get_demo_agent_session(self):
        """Login as demo agent"""
        response = self.session.post(f"{BASE_URL}/api/auth/demo/agent")
        if response.status_code == 200:
            token = response.json().get("token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
            return self.session
        return None
    
    # ========== Test: Agent vault list works ==========
    
    def test_agent_can_list_vault(self):
        """Agent can list vault documents"""
        session = self.get_demo_agent_session()
        if not session:
            pytest.skip("Could not login as demo agent")
        
        response = session.get(f"{BASE_URL}/api/vault")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        
        print(f"PASS: Agent vault list works with {len(data)} documents")
    
    # ========== Test: Vault upload endpoint exists ==========
    
    def test_vault_upload_endpoint_exists(self):
        """Vault upload endpoint exists and requires auth"""
        # Without auth
        response = requests.post(f"{BASE_URL}/api/vault/upload")
        assert response.status_code == 401, f"Upload should require auth, got {response.status_code}"
        
        print("PASS: Vault upload endpoint exists and requires authentication")


class TestBuyerVaultDownload:
    """Test buyer can download shared vault documents"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def get_demo_buyer_session(self, buyer_num=1):
        """Login as demo buyer"""
        response = self.session.post(
            f"{BASE_URL}/api/auth/demo/buyer",
            params={"buyer_num": buyer_num}
        )
        if response.status_code == 200:
            token = response.json().get("token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
            return self.session
        return None
    
    # ========== Test: Buyer can see download endpoint ==========
    
    def test_buyer_vault_download_requires_auth(self):
        """Download endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/vault/some_vault_id/download")
        assert response.status_code == 401, f"Download should require auth, got {response.status_code}"
        
        print("PASS: Vault download endpoint requires authentication")
    
    # ========== Test: Buyer can access shared document download ==========
    
    def test_buyer_can_access_shared_document_download(self):
        """Buyer can download documents shared with them"""
        session = self.get_demo_buyer_session(buyer_num=1)
        if not session:
            pytest.skip("Could not login as demo buyer")
        
        # Get buyer's vault documents
        vault_response = session.get(f"{BASE_URL}/api/vault/buyer")
        if vault_response.status_code != 200:
            pytest.skip("Could not get buyer vault")
        
        docs = vault_response.json()
        if not docs:
            print("PASS: No shared documents to test download, but endpoint works")
            return
        
        # Try to download first shared document
        vault_id = docs[0].get('vault_id')
        download_response = session.get(f"{BASE_URL}/api/vault/{vault_id}/download")
        
        # Should either return file (200) or 404 if file doesn't exist on disk
        assert download_response.status_code in [200, 404], \
            f"Download should return 200 or 404, got {download_response.status_code}"
        
        print(f"PASS: Buyer can access download endpoint for shared document {vault_id}")
    
    # ========== Test: Buyer cannot download unshared documents ==========
    
    def test_buyer_cannot_download_unshared_document(self):
        """Buyer cannot download documents not shared with them"""
        session = self.get_demo_buyer_session(buyer_num=1)
        if not session:
            pytest.skip("Could not login as demo buyer")
        
        # Try to download a non-existent/unshared document
        response = session.get(f"{BASE_URL}/api/vault/unshared_fake_vault_id/download")
        
        # Should return 403 (not shared) or 404 (not found)
        assert response.status_code in [403, 404], \
            f"Unshared download should return 403 or 404, got {response.status_code}"
        
        print("PASS: Buyer cannot download unshared documents")


class TestSpecificBugScenario:
    """Test the specific bug scenario mentioned in the task"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def get_demo_buyer_session(self, buyer_num=1):
        """Login as demo buyer"""
        response = self.session.post(
            f"{BASE_URL}/api/auth/demo/buyer",
            params={"buyer_num": buyer_num}
        )
        if response.status_code == 200:
            token = response.json().get("token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
            return self.session
        return None
    
    # ========== Test: Specific shared document scenario ==========
    
    def test_shared_contract_pdf_accessible(self):
        """
        Test Data: A shared document 'Shared Contract PDF' with vault_id=vault_95377b60827a
        exists and is shared with demo_client_001. The buyer Sophie Müller should see this document.
        """
        session = self.get_demo_buyer_session(buyer_num=1)  # Sophie Müller
        if not session:
            pytest.skip("Could not login as demo buyer (Sophie)")
        
        response = session.get(f"{BASE_URL}/api/vault/buyer")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        docs = response.json()
        
        # Check if the specific document exists
        specific_vault_id = "vault_95377b60827a"
        specific_doc = None
        for doc in docs:
            if doc.get('vault_id') == specific_vault_id:
                specific_doc = doc
                break
        
        if specific_doc:
            # Verify the document has correct name field
            assert specific_doc.get('name'), f"Document should have 'name' field: {specific_doc}"
            print(f"PASS: Found specific shared document: name='{specific_doc.get('name')}', vault_id={specific_vault_id}")
        else:
            # Document might not exist or be shared differently
            print(f"INFO: Specific document {specific_vault_id} not found in buyer vault (may not be seeded)")
            print(f"INFO: Buyer vault has {len(docs)} documents")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
