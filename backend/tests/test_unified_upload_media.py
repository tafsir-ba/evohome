"""
Test Suite: Unified Upload / Media System (Organ 1)
Tests the rebuilt file upload handling: vault documents, hero images, company logos.
Canonical file_service.py, vault_service.py, vault_v2.py routes, documents_v2.py routes, settings.py logo routes.
"""
import os
import pytest
import requests
import io
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://evo-access.preview.emergentagent.com')

# Test credentials
AGENT_EMAIL = "agent@evohome-test.ch"
AGENT_PASSWORD = "Evohome2026!"
BUYER_EMAIL = "buyer@evohome-test.ch"
BUYER_PASSWORD = "Evohome2026!"


class TestAuthSetup:
    """Authentication setup for tests"""
    
    @pytest.fixture(scope="class")
    def agent_session(self):
        """Get authenticated agent session"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
        res = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": AGENT_EMAIL,
            "password": AGENT_PASSWORD
        })
        assert res.status_code == 200, f"Agent login failed: {res.text}"
        data = res.json()
        token = data.get("access_token") or data.get("token")
        assert token, "No token in login response"
        session.headers.update({"Authorization": f"Bearer {token}"})
        return session
    
    @pytest.fixture(scope="class")
    def buyer_session(self):
        """Get authenticated buyer session"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
        res = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": BUYER_EMAIL,
            "password": BUYER_PASSWORD
        })
        if res.status_code != 200:
            pytest.skip(f"Buyer login failed: {res.text}")
        data = res.json()
        token = data.get("access_token") or data.get("token")
        if not token:
            pytest.skip("No token in buyer login response")
        session.headers.update({"Authorization": f"Bearer {token}"})
        return session


class TestVaultUpload(TestAuthSetup):
    """Test vault document upload functionality"""
    
    created_vault_doc_id = None
    
    def test_vault_upload_pdf(self, agent_session):
        """POST /api/vault/upload with PDF file returns canonical fields"""
        # Create a test PDF file
        pdf_content = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF"
        files = {
            'file': ('test_document.pdf', io.BytesIO(pdf_content), 'application/pdf')
        }
        data = {
            'title': 'TEST_Vault_Upload_Document',
            'category': 'contracts',
            'access_level': 'private',
            'project_id': '',
            'client_ids': '',
            'description': 'Test vault upload'
        }
        
        # Remove Content-Type header for multipart
        headers = {k: v for k, v in agent_session.headers.items() if k.lower() != 'content-type'}
        
        res = requests.post(
            f"{BASE_URL}/api/vault/upload",
            files=files,
            data=data,
            headers=headers
        )
        
        assert res.status_code == 200, f"Vault upload failed: {res.text}"
        result = res.json()
        
        # Verify canonical fields
        assert "vault_document_id" in result, "Missing vault_document_id"
        assert "title" in result, "Missing title"
        assert "stored_filename" in result, "Missing stored_filename"
        assert "original_filename" in result, "Missing original_filename"
        assert "file_size" in result, "Missing file_size"
        assert "content_type" in result, "Missing content_type"
        assert "category" in result, "Missing category"
        assert "access_level" in result, "Missing access_level"
        
        # Verify values
        assert result["title"] == "TEST_Vault_Upload_Document"
        assert result["category"] == "contracts"
        assert result["access_level"] == "private"
        assert result["content_type"] == "application/pdf"
        
        # Store for later tests
        TestVaultUpload.created_vault_doc_id = result["vault_document_id"]
        print(f"Created vault document: {result['vault_document_id']}")
    
    def test_vault_upload_image(self, agent_session):
        """POST /api/vault/upload with image file"""
        # Create a minimal PNG file
        png_content = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
        files = {
            'file': ('test_image.png', io.BytesIO(png_content), 'image/png')
        }
        data = {
            'title': 'TEST_Vault_Image',
            'category': 'plans',
            'access_level': 'private'
        }
        
        headers = {k: v for k, v in agent_session.headers.items() if k.lower() != 'content-type'}
        
        res = requests.post(
            f"{BASE_URL}/api/vault/upload",
            files=files,
            data=data,
            headers=headers
        )
        
        assert res.status_code == 200, f"Vault image upload failed: {res.text}"
        result = res.json()
        assert result["content_type"] == "image/png"
        assert result["category"] == "plans"
    
    def test_vault_upload_invalid_type_rejected(self, agent_session):
        """POST /api/vault/upload rejects invalid file types"""
        # Try to upload a text file (not allowed)
        files = {
            'file': ('test.txt', io.BytesIO(b'Hello World'), 'text/plain')
        }
        data = {
            'title': 'TEST_Invalid_File',
            'category': 'other'
        }
        
        headers = {k: v for k, v in agent_session.headers.items() if k.lower() != 'content-type'}
        
        res = requests.post(
            f"{BASE_URL}/api/vault/upload",
            files=files,
            data=data,
            headers=headers
        )
        
        assert res.status_code == 400, f"Expected 400 for invalid file type, got {res.status_code}"


class TestVaultList(TestAuthSetup):
    """Test vault document listing"""
    
    def test_vault_list_returns_array(self, agent_session):
        """GET /api/vault/documents returns array with canonical field names"""
        res = agent_session.get(f"{BASE_URL}/api/vault/documents")
        
        assert res.status_code == 200, f"Vault list failed: {res.text}"
        result = res.json()
        
        assert isinstance(result, list), "Expected array response"
        
        if len(result) > 0:
            doc = result[0]
            # Verify canonical field names
            assert "vault_document_id" in doc, "Missing vault_document_id in list item"
            assert "title" in doc, "Missing title in list item"
            assert "stored_filename" in doc, "Missing stored_filename in list item"
            assert "content_type" in doc, "Missing content_type in list item"
            print(f"Found {len(result)} vault documents")
    
    def test_vault_list_with_project_filter(self, agent_session):
        """GET /api/vault/documents?project_id=xxx filters by project"""
        res = agent_session.get(f"{BASE_URL}/api/vault/documents?project_id=nonexistent")
        
        assert res.status_code == 200
        result = res.json()
        assert isinstance(result, list)


class TestVaultCRUD(TestAuthSetup):
    """Test vault document CRUD operations"""
    
    test_doc_id = None
    
    @pytest.fixture(autouse=True)
    def setup_test_doc(self, agent_session):
        """Create a test document for CRUD operations"""
        pdf_content = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF"
        files = {
            'file': ('crud_test.pdf', io.BytesIO(pdf_content), 'application/pdf')
        }
        data = {
            'title': 'TEST_CRUD_Document',
            'category': 'reports',
            'access_level': 'private'
        }
        
        headers = {k: v for k, v in agent_session.headers.items() if k.lower() != 'content-type'}
        
        res = requests.post(
            f"{BASE_URL}/api/vault/upload",
            files=files,
            data=data,
            headers=headers
        )
        
        if res.status_code == 200:
            TestVaultCRUD.test_doc_id = res.json()["vault_document_id"]
        yield
    
    def test_vault_get_single(self, agent_session):
        """GET /api/vault/documents/{vault_document_id} returns document"""
        if not TestVaultCRUD.test_doc_id:
            pytest.skip("No test document created")
        
        res = agent_session.get(f"{BASE_URL}/api/vault/documents/{TestVaultCRUD.test_doc_id}")
        
        assert res.status_code == 200, f"Get vault doc failed: {res.text}"
        result = res.json()
        assert result["vault_document_id"] == TestVaultCRUD.test_doc_id
    
    def test_vault_update(self, agent_session):
        """PUT /api/vault/documents/{vault_document_id} updates metadata"""
        if not TestVaultCRUD.test_doc_id:
            pytest.skip("No test document created")
        
        update_data = {
            "title": "TEST_CRUD_Document_Updated",
            "category": "permits",
            "description": "Updated description",
            "access_level": "private"
        }
        
        res = agent_session.put(
            f"{BASE_URL}/api/vault/documents/{TestVaultCRUD.test_doc_id}",
            json=update_data
        )
        
        assert res.status_code == 200, f"Update vault doc failed: {res.text}"
        result = res.json()
        assert result["title"] == "TEST_CRUD_Document_Updated"
        assert result["category"] == "permits"
        assert result["description"] == "Updated description"
    
    def test_vault_download(self, agent_session):
        """GET /api/vault/documents/{vault_document_id}/download serves file with auth"""
        if not TestVaultCRUD.test_doc_id:
            pytest.skip("No test document created")
        
        res = agent_session.get(f"{BASE_URL}/api/vault/documents/{TestVaultCRUD.test_doc_id}/download")
        
        assert res.status_code == 200, f"Download vault doc failed: {res.text}"
        assert "application/pdf" in res.headers.get("content-type", "")
    
    def test_vault_download_requires_auth(self):
        """GET /api/vault/documents/{id}/download requires authentication"""
        if not TestVaultCRUD.test_doc_id:
            pytest.skip("No test document created")
        
        # Request without auth
        res = requests.get(f"{BASE_URL}/api/vault/documents/{TestVaultCRUD.test_doc_id}/download")
        
        assert res.status_code in [401, 403], f"Expected 401/403 without auth, got {res.status_code}"
    
    def test_vault_delete(self, agent_session):
        """DELETE /api/vault/documents/{vault_document_id} removes document and file"""
        if not TestVaultCRUD.test_doc_id:
            pytest.skip("No test document created")
        
        res = agent_session.delete(f"{BASE_URL}/api/vault/documents/{TestVaultCRUD.test_doc_id}")
        
        assert res.status_code == 200, f"Delete vault doc failed: {res.text}"
        
        # Verify document is gone
        res2 = agent_session.get(f"{BASE_URL}/api/vault/documents/{TestVaultCRUD.test_doc_id}")
        assert res2.status_code == 404, "Document should be deleted"


class TestHeroImage(TestAuthSetup):
    """Test hero image upload/delete functionality"""
    
    test_document_id = None
    
    @pytest.fixture(autouse=True)
    def get_test_document(self, agent_session):
        """Get or create a test document for hero image tests"""
        # Get existing documents
        res = agent_session.get(f"{BASE_URL}/api/documents")
        if res.status_code == 200:
            docs = res.json()
            if docs and len(docs) > 0:
                TestHeroImage.test_document_id = docs[0].get("document_id")
        yield
    
    def test_hero_image_upload(self, agent_session):
        """POST /api/documents/{document_id}/hero-image returns {url, filename, size}"""
        if not TestHeroImage.test_document_id:
            pytest.skip("No test document available")
        
        # Create a minimal PNG file
        png_content = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
        files = {
            'file': ('hero_test.png', io.BytesIO(png_content), 'image/png')
        }
        
        headers = {k: v for k, v in agent_session.headers.items() if k.lower() != 'content-type'}
        
        res = requests.post(
            f"{BASE_URL}/api/documents/{TestHeroImage.test_document_id}/hero-image",
            files=files,
            headers=headers
        )
        
        assert res.status_code == 200, f"Hero image upload failed: {res.text}"
        result = res.json()
        
        # Verify response structure
        assert "url" in result, "Missing url in response"
        assert "filename" in result, "Missing filename in response"
        assert "size" in result, "Missing size in response"
        
        # Verify URL format
        assert result["url"].startswith("/api/uploads/"), f"URL should start with /api/uploads/, got {result['url']}"
        print(f"Hero image uploaded: {result['url']}")
    
    def test_hero_image_public_access(self, agent_session):
        """GET /api/uploads/{stored_filename} serves image WITHOUT auth"""
        if not TestHeroImage.test_document_id:
            pytest.skip("No test document available")
        
        # Get document to find hero image URL
        res = agent_session.get(f"{BASE_URL}/api/documents/{TestHeroImage.test_document_id}")
        if res.status_code != 200:
            pytest.skip("Could not get document")
        
        doc = res.json()
        hero_url = doc.get("hero_image_url")
        if not hero_url:
            pytest.skip("No hero image on document")
        
        # Access without auth
        full_url = f"{BASE_URL}{hero_url}"
        res = requests.get(full_url)
        
        assert res.status_code == 200, f"Hero image should be publicly accessible, got {res.status_code}"
        assert "image" in res.headers.get("content-type", ""), "Should return image content type"
    
    def test_hero_image_delete(self, agent_session):
        """DELETE /api/documents/{document_id}/hero-image removes image"""
        if not TestHeroImage.test_document_id:
            pytest.skip("No test document available")
        
        res = agent_session.delete(f"{BASE_URL}/api/documents/{TestHeroImage.test_document_id}/hero-image")
        
        assert res.status_code == 200, f"Hero image delete failed: {res.text}"
        
        # Verify hero image is removed
        res2 = agent_session.get(f"{BASE_URL}/api/documents/{TestHeroImage.test_document_id}")
        if res2.status_code == 200:
            doc = res2.json()
            assert doc.get("hero_image_url") is None, "Hero image URL should be null after delete"
    
    def test_hero_image_rejects_non_image(self, agent_session):
        """POST /api/documents/{document_id}/hero-image rejects non-image files"""
        if not TestHeroImage.test_document_id:
            pytest.skip("No test document available")
        
        # Try to upload a PDF as hero image
        pdf_content = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF"
        files = {
            'file': ('not_an_image.pdf', io.BytesIO(pdf_content), 'application/pdf')
        }
        
        headers = {k: v for k, v in agent_session.headers.items() if k.lower() != 'content-type'}
        
        res = requests.post(
            f"{BASE_URL}/api/documents/{TestHeroImage.test_document_id}/hero-image",
            files=files,
            headers=headers
        )
        
        assert res.status_code == 400, f"Expected 400 for non-image file, got {res.status_code}"


class TestLogoUpload(TestAuthSetup):
    """Test company logo upload/delete functionality"""
    
    def test_logo_upload(self, agent_session):
        """POST /api/settings/logo returns {url, filename, size}"""
        # Create a minimal PNG file
        png_content = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
        files = {
            'file': ('logo_test.png', io.BytesIO(png_content), 'image/png')
        }
        
        headers = {k: v for k, v in agent_session.headers.items() if k.lower() != 'content-type'}
        
        res = requests.post(
            f"{BASE_URL}/api/settings/logo",
            files=files,
            headers=headers
        )
        
        # Logo upload requires Pro plan - may return 403
        if res.status_code == 403:
            error = res.json()
            if "plan_required" in str(error):
                pytest.skip("Logo upload requires Pro plan")
        
        assert res.status_code == 200, f"Logo upload failed: {res.text}"
        result = res.json()
        
        # Verify response structure
        assert "url" in result, "Missing url in response"
        assert "filename" in result, "Missing filename in response"
        assert "size" in result, "Missing size in response"
        
        print(f"Logo uploaded: {result['url']}")
    
    def test_logo_public_access(self, agent_session):
        """Logo URL accessible without auth header"""
        # Get settings to find logo URL
        res = agent_session.get(f"{BASE_URL}/api/settings")
        if res.status_code != 200:
            pytest.skip("Could not get settings")
        
        settings = res.json()
        logo_url = settings.get("company_logo_url")
        if not logo_url:
            pytest.skip("No logo uploaded")
        
        # Access without auth
        full_url = f"{BASE_URL}{logo_url}"
        res = requests.get(full_url)
        
        assert res.status_code == 200, f"Logo should be publicly accessible, got {res.status_code}"
        assert "image" in res.headers.get("content-type", ""), "Should return image content type"
    
    def test_logo_delete(self, agent_session):
        """DELETE /api/settings/logo removes logo"""
        res = agent_session.delete(f"{BASE_URL}/api/settings/logo")
        
        assert res.status_code == 200, f"Logo delete failed: {res.text}"
        
        # Verify logo is removed
        res2 = agent_session.get(f"{BASE_URL}/api/settings")
        if res2.status_code == 200:
            settings = res2.json()
            assert settings.get("company_logo_url") is None, "Logo URL should be null after delete"
    
    def test_logo_rejects_non_image(self, agent_session):
        """POST /api/settings/logo rejects non-image files"""
        # Try to upload a PDF as logo
        pdf_content = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF"
        files = {
            'file': ('not_an_image.pdf', io.BytesIO(pdf_content), 'application/pdf')
        }
        
        headers = {k: v for k, v in agent_session.headers.items() if k.lower() != 'content-type'}
        
        res = requests.post(
            f"{BASE_URL}/api/settings/logo",
            files=files,
            headers=headers
        )
        
        # May return 403 for plan restriction or 400 for invalid file
        assert res.status_code in [400, 403], f"Expected 400/403 for non-image file, got {res.status_code}"


class TestOldEndpoints:
    """Test that old endpoints return 404"""
    
    def test_old_vault_endpoint_returns_404(self):
        """GET /api/vault should return 404 (old endpoint)"""
        res = requests.get(f"{BASE_URL}/api/vault")
        
        # Old endpoint should not exist - expect 404 or 401 (if auth required first)
        assert res.status_code in [404, 401, 405], f"Old /api/vault endpoint should return 404, got {res.status_code}"


class TestVaultCategories(TestAuthSetup):
    """Test vault categories endpoint"""
    
    def test_get_vault_categories(self, agent_session):
        """GET /api/vault/categories returns category list"""
        res = agent_session.get(f"{BASE_URL}/api/vault/categories")
        
        assert res.status_code == 200, f"Get categories failed: {res.text}"
        result = res.json()
        
        assert isinstance(result, list), "Expected array response"
        assert len(result) > 0, "Expected at least one category"
        
        # Verify category structure
        for cat in result:
            assert "value" in cat, "Missing value in category"
            assert "label" in cat, "Missing label in category"
        
        # Verify expected categories exist
        values = [c["value"] for c in result]
        assert "contracts" in values, "Missing contracts category"
        assert "plans" in values, "Missing plans category"
        assert "permits" in values, "Missing permits category"
        assert "reports" in values, "Missing reports category"
        assert "other" in values, "Missing other category"


class TestStaticFileServing:
    """Test static file serving for uploads"""
    
    def test_uploads_directory_accessible(self):
        """Verify /api/uploads/ path is accessible"""
        # Try to access a non-existent file - should return 404, not 500
        res = requests.get(f"{BASE_URL}/api/uploads/nonexistent_file.png")
        
        # Should return 404 for missing file, not 500 or other error
        assert res.status_code == 404, f"Expected 404 for missing file, got {res.status_code}"


class TestCleanup(TestAuthSetup):
    """Cleanup test data"""
    
    def test_cleanup_test_vault_documents(self, agent_session):
        """Delete all TEST_ prefixed vault documents"""
        res = agent_session.get(f"{BASE_URL}/api/vault/documents")
        if res.status_code != 200:
            return
        
        docs = res.json()
        deleted = 0
        for doc in docs:
            if doc.get("title", "").startswith("TEST_"):
                del_res = agent_session.delete(f"{BASE_URL}/api/vault/documents/{doc['vault_document_id']}")
                if del_res.status_code == 200:
                    deleted += 1
        
        print(f"Cleaned up {deleted} test vault documents")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
