"""
Tests for new features in iteration 24:
- Email CTA validation
- Agent Profile (Settings)
- Document Vault
- AI Timeline Extraction endpoints
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://invoice-track-20.preview.emergentagent.com').rstrip('/')

# Credentials
DEMO_AGENT_EMAIL = "demo.agent@upgradeflow.com"
DEMO_AGENT_PASSWORD = "demo123"


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def agent_token(api_client):
    """Get authentication token for demo agent"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "email": DEMO_AGENT_EMAIL,
        "password": DEMO_AGENT_PASSWORD
    })
    if response.status_code == 200:
        data = response.json()
        return data.get("token")
    # Try demo login if direct login fails
    response = api_client.post(f"{BASE_URL}/api/auth/demo/agent")
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip("Authentication failed - skipping authenticated tests")


@pytest.fixture(scope="module")
def authenticated_client(api_client, agent_token):
    """Session with auth header"""
    api_client.headers.update({"Authorization": f"Bearer {agent_token}"})
    return api_client


# ====================
# EMAIL CTA VALIDATION TESTS
# ====================

class TestEmailCTAValidation:
    """Test email template CTA button validation"""
    
    def test_email_template_document_sent(self, api_client):
        """Test document_sent template CTA validation"""
        response = api_client.get(f"{BASE_URL}/api/test/email-template/document_sent")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "cta_valid" in data, "Response should include cta_valid"
        assert data["cta_valid"] == True, f"CTA should be valid for document_sent, got: {data.get('cta_validation')}"
        assert data.get("cta_validation", {}).get("has_bg_color") == True
        assert data.get("cta_validation", {}).get("has_text_color") == True
        print(f"✓ document_sent template CTA validation passed: {data['cta_validation']}")
    
    def test_email_template_quote_approved(self, api_client):
        """Test quote_approved template CTA validation"""
        response = api_client.get(f"{BASE_URL}/api/test/email-template/quote_approved")
        assert response.status_code == 200
        
        data = response.json()
        assert data["cta_valid"] == True, f"CTA should be valid for quote_approved"
        print(f"✓ quote_approved template CTA valid")
    
    def test_email_template_payment_confirmed(self, api_client):
        """Test payment_confirmed template CTA validation"""
        response = api_client.get(f"{BASE_URL}/api/test/email-template/payment_confirmed")
        assert response.status_code == 200
        
        data = response.json()
        assert data["cta_valid"] == True, f"CTA should be valid for payment_confirmed"
        print(f"✓ payment_confirmed template CTA valid")
    
    def test_email_template_welcome(self, api_client):
        """Test welcome template CTA validation (if exists)"""
        response = api_client.get(f"{BASE_URL}/api/test/email-template/welcome")
        assert response.status_code == 200
        
        data = response.json()
        assert data["cta_valid"] == True, f"CTA should be valid for welcome"
        print(f"✓ welcome template CTA valid")
    
    def test_email_template_invalid_type(self, api_client):
        """Test invalid template type returns 400"""
        response = api_client.get(f"{BASE_URL}/api/test/email-template/invalid_template")
        assert response.status_code == 400, f"Expected 400 for invalid template, got {response.status_code}"
        print("✓ Invalid template type correctly returns 400")


# ====================
# AGENT PROFILE / SETTINGS TESTS
# ====================

class TestAgentSettings:
    """Test Agent Profile/Settings endpoints"""
    
    def test_get_settings_returns_profile(self, authenticated_client):
        """GET /api/settings should return profile object"""
        response = authenticated_client.get(f"{BASE_URL}/api/settings")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "profile" in data, f"Response should include 'profile' object, got: {data.keys()}"
        
        profile = data["profile"]
        assert "display_name" in profile, "profile should have display_name"
        assert "contact_email" in profile, "profile should have contact_email"
        assert "contact_phone" in profile, "profile should have contact_phone"
        
        print(f"✓ GET /api/settings returns profile: {profile}")
    
    def test_get_settings_returns_billing(self, authenticated_client):
        """GET /api/settings should return billing info"""
        response = authenticated_client.get(f"{BASE_URL}/api/settings")
        assert response.status_code == 200
        
        data = response.json()
        assert "billing" in data, "Response should include 'billing'"
        assert "language" in data, "Response should include 'language'"
        assert "currency" in data, "Response should include 'currency'"
        print(f"✓ GET /api/settings includes billing, language, currency")
    
    def test_update_settings_profile(self, authenticated_client):
        """PUT /api/settings with profile data should update"""
        update_data = {
            "profile": {
                "display_name": "Test Agent Name",
                "contact_email": "test.contact@example.com",
                "contact_phone": "+41 12 345 67 89"
            }
        }
        
        response = authenticated_client.put(f"{BASE_URL}/api/settings", json=update_data)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Verify the update persisted
        verify_response = authenticated_client.get(f"{BASE_URL}/api/settings")
        assert verify_response.status_code == 200
        
        verify_data = verify_response.json()
        profile = verify_data.get("profile", {})
        assert profile.get("display_name") == "Test Agent Name", f"display_name not updated: {profile}"
        assert profile.get("contact_email") == "test.contact@example.com", f"contact_email not updated: {profile}"
        assert profile.get("contact_phone") == "+41 12 345 67 89", f"contact_phone not updated: {profile}"
        
        print(f"✓ PUT /api/settings updates profile correctly")
    
    def test_update_settings_language(self, authenticated_client):
        """PUT /api/settings with language should update"""
        response = authenticated_client.put(f"{BASE_URL}/api/settings", json={"language": "de"})
        assert response.status_code == 200
        
        verify = authenticated_client.get(f"{BASE_URL}/api/settings")
        assert verify.json().get("language") == "de"
        
        # Restore to en
        authenticated_client.put(f"{BASE_URL}/api/settings", json={"language": "en"})
        print("✓ Language update works")
    
    def test_update_settings_invalid_language(self, authenticated_client):
        """PUT /api/settings with invalid language should fail"""
        response = authenticated_client.put(f"{BASE_URL}/api/settings", json={"language": "invalid"})
        assert response.status_code == 400, f"Expected 400 for invalid language, got {response.status_code}"
        print("✓ Invalid language correctly returns 400")
    
    def test_settings_requires_auth(self, api_client):
        """Settings endpoint requires authentication"""
        # Remove auth header temporarily
        original_headers = api_client.headers.copy()
        api_client.headers.pop("Authorization", None)
        
        response = api_client.get(f"{BASE_URL}/api/settings")
        assert response.status_code == 401, f"Expected 401 without auth, got {response.status_code}"
        
        api_client.headers = original_headers
        print("✓ Settings correctly requires authentication")


# ====================
# DOCUMENT VAULT TESTS
# ====================

class TestDocumentVault:
    """Test Document Vault endpoints"""
    
    def test_vault_list_empty_or_returns_list(self, authenticated_client):
        """GET /api/vault should return list of documents"""
        response = authenticated_client.get(f"{BASE_URL}/api/vault")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        print(f"✓ GET /api/vault returns list with {len(data)} documents")
    
    def test_vault_categories_list(self, authenticated_client):
        """GET /api/vault/categories/list should return categories"""
        response = authenticated_client.get(f"{BASE_URL}/api/vault/categories/list")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "categories" in data, f"Response should include 'categories', got: {data.keys()}"
        assert isinstance(data["categories"], list), f"categories should be list"
        assert len(data["categories"]) > 0, "categories should not be empty"
        
        print(f"✓ GET /api/vault/categories/list returns: {data['categories']}")
    
    def test_vault_upload_document(self, authenticated_client):
        """POST /api/vault/upload should upload document"""
        # Create a simple test PDF content (minimal valid PDF)
        pdf_content = b'%PDF-1.4\n1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n2 0 obj << /Type /Pages /Kids [] /Count 0 >> endobj\nxref\n0 3\ntrailer << /Size 3 /Root 1 0 R >>\nstartxref\n107\n%%EOF'
        
        files = {'file': ('test_document.pdf', pdf_content, 'application/pdf')}
        data = {
            'name': 'TEST_Vault_Document',
            'category': 'Contracts',
            'description': 'Test document for vault',
            'access_level': 'private'
        }
        
        # Need to remove Content-Type for multipart
        original_headers = authenticated_client.headers.copy()
        authenticated_client.headers.pop("Content-Type", None)
        
        response = authenticated_client.post(f"{BASE_URL}/api/vault/upload", files=files, data=data)
        
        # Restore headers
        authenticated_client.headers = original_headers
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        doc_data = response.json()
        assert "vault_id" in doc_data, f"Response should include vault_id"
        assert doc_data.get("name") == "TEST_Vault_Document"
        assert doc_data.get("category") == "Contracts"
        
        # Store vault_id for cleanup
        TestDocumentVault.test_vault_id = doc_data["vault_id"]
        print(f"✓ POST /api/vault/upload created document: {doc_data['vault_id']}")
    
    def test_vault_get_uploaded_document(self, authenticated_client):
        """GET /api/vault should include uploaded document"""
        vault_id = getattr(TestDocumentVault, 'test_vault_id', None)
        if not vault_id:
            pytest.skip("No test document to verify")
        
        response = authenticated_client.get(f"{BASE_URL}/api/vault")
        assert response.status_code == 200
        
        docs = response.json()
        found = any(d.get("vault_id") == vault_id for d in docs)
        assert found, f"Uploaded document {vault_id} not found in vault list"
        print(f"✓ Uploaded document found in vault list")
    
    def test_vault_delete_document(self, authenticated_client):
        """DELETE /api/vault/{vault_id} should delete document"""
        vault_id = getattr(TestDocumentVault, 'test_vault_id', None)
        if not vault_id:
            pytest.skip("No test document to delete")
        
        response = authenticated_client.delete(f"{BASE_URL}/api/vault/{vault_id}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Verify deletion
        verify_response = authenticated_client.get(f"{BASE_URL}/api/vault")
        docs = verify_response.json()
        found = any(d.get("vault_id") == vault_id for d in docs)
        assert not found, "Document should be deleted from vault"
        
        print(f"✓ DELETE /api/vault/{vault_id} successful")
    
    def test_vault_delete_nonexistent(self, authenticated_client):
        """DELETE /api/vault/{vault_id} returns 404 for nonexistent"""
        response = authenticated_client.delete(f"{BASE_URL}/api/vault/nonexistent_vault_id_12345")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ DELETE nonexistent vault document returns 404")
    
    def test_vault_requires_auth(self, api_client):
        """Vault endpoints require authentication"""
        original_headers = api_client.headers.copy()
        api_client.headers.pop("Authorization", None)
        
        response = api_client.get(f"{BASE_URL}/api/vault")
        assert response.status_code == 401, f"Expected 401 without auth, got {response.status_code}"
        
        api_client.headers = original_headers
        print("✓ Vault correctly requires authentication")


# ====================
# AI TIMELINE EXTRACTION TESTS
# ====================

class TestTimelineExtraction:
    """Test AI Timeline Extraction endpoints"""
    
    def test_timeline_extractions_list(self, authenticated_client):
        """GET /api/timeline/extractions should return list"""
        response = authenticated_client.get(f"{BASE_URL}/api/timeline/extractions")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        print(f"✓ GET /api/timeline/extractions returns list with {len(data)} items")
    
    def test_timeline_extractions_requires_auth(self, api_client):
        """Timeline extractions requires authentication"""
        original_headers = api_client.headers.copy()
        api_client.headers.pop("Authorization", None)
        
        response = api_client.get(f"{BASE_URL}/api/timeline/extractions")
        assert response.status_code == 401, f"Expected 401 without auth, got {response.status_code}"
        
        api_client.headers = original_headers
        print("✓ Timeline extractions correctly requires authentication")
    
    def test_timeline_extraction_not_found(self, authenticated_client):
        """GET /api/timeline/extractions/{id} returns 404 for nonexistent"""
        response = authenticated_client.get(f"{BASE_URL}/api/timeline/extractions/nonexistent_12345")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Nonexistent extraction returns 404")
    
    def test_timeline_templates_list(self, authenticated_client):
        """GET /api/timeline/templates should return list"""
        response = authenticated_client.get(f"{BASE_URL}/api/timeline/templates")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        print(f"✓ GET /api/timeline/templates returns list with {len(data)} templates")


# ====================
# CLEANUP
# ====================

class TestCleanup:
    """Cleanup test data"""
    
    def test_reset_profile_settings(self, authenticated_client):
        """Reset profile settings to original values"""
        update_data = {
            "profile": {
                "display_name": "Marc Dubois",
                "contact_email": "demo.agent@upgradeflow.com",
                "contact_phone": ""
            }
        }
        response = authenticated_client.put(f"{BASE_URL}/api/settings", json=update_data)
        assert response.status_code == 200
        print("✓ Profile settings reset to defaults")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
