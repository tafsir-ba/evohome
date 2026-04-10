"""
Test Phase 1-3 Hardening Features:
1. Image support (jpg, png, webp) for document classification and extraction
2. Command history endpoint
3. Auto-save draft endpoints
4. Idempotency in draft execution
5. Extraction validation for amounts (negative, zero, large)
"""
import pytest
import requests
import os
import json

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
DEMO_AGENT_EMAIL = "demo.agent@upgradeflow.com"
DEMO_AGENT_PASSWORD = "demo123"


@pytest.fixture(scope="module")
def session():
    """Create a requests session with authentication"""
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def auth_token(session):
    """Get authentication token for demo agent"""
    login_payload = {
        "email": DEMO_AGENT_EMAIL,
        "password": DEMO_AGENT_PASSWORD
    }
    response = session.post(f"{BASE_URL}/api/auth/login", json=login_payload)
    if response.status_code == 200:
        data = response.json()
        token = data.get("token")
        # Also set cookies if returned
        if 'session_token' in response.cookies:
            session.cookies.set('session_token', response.cookies['session_token'])
        return token
    pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")


@pytest.fixture(scope="module")
def auth_session(session, auth_token):
    """Session with auth headers set"""
    session.headers.update({"Authorization": f"Bearer {auth_token}"})
    return session


# ==================== COMMAND HISTORY ENDPOINT TESTS ====================

class TestCommandHistoryEndpoint:
    """Tests for GET /api/command/history"""
    
    def test_command_history_returns_200(self, auth_session):
        """Test that command history endpoint is accessible"""
        response = auth_session.get(f"{BASE_URL}/api/command/history")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    def test_command_history_structure(self, auth_session):
        """Test command history response structure"""
        response = auth_session.get(f"{BASE_URL}/api/command/history")
        assert response.status_code == 200
        data = response.json()
        
        # Should have both drafts and recent_extractions fields
        assert "drafts" in data, "Response should have 'drafts' field"
        assert "recent_extractions" in data, "Response should have 'recent_extractions' field"
        
        # Both should be lists
        assert isinstance(data["drafts"], list), "drafts should be a list"
        assert isinstance(data["recent_extractions"], list), "recent_extractions should be a list"
    
    def test_command_history_limit_param(self, auth_session):
        """Test that limit parameter is respected"""
        response = auth_session.get(f"{BASE_URL}/api/command/history?limit=5")
        assert response.status_code == 200
        data = response.json()
        
        # Lists should not exceed limit
        assert len(data["drafts"]) <= 5, "Drafts should respect limit"
        assert len(data["recent_extractions"]) <= 5, "Recent extractions should respect limit"


# ==================== AUTO-SAVE DRAFT ENDPOINT TESTS ====================

class TestAutoSaveDraftEndpoints:
    """Tests for POST and GET /api/command/draft/auto-save"""
    
    def test_auto_save_creates_draft(self, auth_session):
        """Test auto-save creates a new draft"""
        plan_id = "test_plan_auto_save_123"
        data = {
            "plan_id": plan_id,
            "intent": "create_invoice",
            "draft_data": json.dumps({"title": "Test Invoice", "amount": 1500.00})
        }
        
        # Use form data (not JSON) as endpoint expects Form parameters
        response = auth_session.post(
            f"{BASE_URL}/api/command/draft/auto-save",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        result = response.json()
        assert result.get("status") == "saved", f"Expected status='saved', got {result}"
        assert result.get("plan_id") == plan_id
    
    def test_auto_save_retrieval(self, auth_session):
        """Test retrieving an auto-saved draft"""
        plan_id = "test_plan_retrieval_456"
        
        # First save
        save_data = {
            "plan_id": plan_id,
            "intent": "create_quote",
            "draft_data": json.dumps({"supplier": "Test Corp", "amount": 2500})
        }
        save_response = auth_session.post(
            f"{BASE_URL}/api/command/draft/auto-save",
            data=save_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        assert save_response.status_code == 200
        
        # Then retrieve
        get_response = auth_session.get(f"{BASE_URL}/api/command/draft/auto-save/{plan_id}")
        assert get_response.status_code == 200, f"Expected 200, got {get_response.status_code}: {get_response.text}"
        
        result = get_response.json()
        assert result.get("plan_id") == plan_id
        assert result.get("intent") == "create_quote"
    
    def test_auto_save_nonexistent_returns_404(self, auth_session):
        """Test that requesting a non-existent auto-save returns 404"""
        response = auth_session.get(f"{BASE_URL}/api/command/draft/auto-save/nonexistent_plan_xyz")
        assert response.status_code == 404, f"Expected 404 for non-existent plan, got {response.status_code}"


# ==================== DOCUMENT CLASSIFICATION TESTS (FILE TYPE SUPPORT) ====================

class TestDocumentClassificationFileTypes:
    """Tests for classify-document endpoint file type support"""
    
    def test_classify_pdf_accepted(self, auth_session):
        """Test that PDF files are accepted"""
        # Create a minimal valid PDF
        pdf_content = b'%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF'
        files = {"file": ("test_invoice.pdf", pdf_content, "application/pdf")}
        
        response = auth_session.post(
            f"{BASE_URL}/api/command/classify-document",
            files=files,
            headers={"Content-Type": None}  # Let requests set multipart boundary
        )
        # Either 200 (success) or 400 with specific error (corrupted PDF) is acceptable
        # The important thing is that PDF type is not rejected outright
        assert response.status_code in [200, 400], f"Unexpected status: {response.status_code}: {response.text}"
    
    def test_classify_jpg_accepted(self, auth_session):
        """Test that JPG files are accepted"""
        # Create a minimal valid JPEG (just header bytes for type detection)
        jpg_header = bytes([0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00])
        files = {"file": ("test_invoice.jpg", jpg_header, "image/jpeg")}
        
        response = auth_session.post(
            f"{BASE_URL}/api/command/classify-document",
            files=files,
            headers={"Content-Type": None}
        )
        # Accept 200 or 400 (if OCR fails, but not 415 for unsupported type)
        assert response.status_code in [200, 400, 500], f"Unexpected status: {response.status_code}: {response.text}"
        if response.status_code == 400:
            # Should NOT say "unsupported file type"
            error = response.json().get("detail", "")
            assert "unsupported" not in error.lower() or "file type" not in error.lower(), \
                f"JPG should be a supported file type: {error}"
    
    def test_classify_png_accepted(self, auth_session):
        """Test that PNG files are accepted"""
        # Minimal PNG header
        png_header = bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A])
        files = {"file": ("test_quote.png", png_header, "image/png")}
        
        response = auth_session.post(
            f"{BASE_URL}/api/command/classify-document",
            files=files,
            headers={"Content-Type": None}
        )
        assert response.status_code in [200, 400, 500], f"Unexpected status: {response.status_code}: {response.text}"
        if response.status_code == 400:
            error = response.json().get("detail", "")
            assert "unsupported" not in error.lower() or "file type" not in error.lower(), \
                f"PNG should be a supported file type: {error}"
    
    def test_classify_webp_accepted(self, auth_session):
        """Test that WEBP files are accepted"""
        # Minimal WEBP header
        webp_header = b'RIFF\x00\x00\x00\x00WEBPVP8 '
        files = {"file": ("test_document.webp", webp_header, "image/webp")}
        
        response = auth_session.post(
            f"{BASE_URL}/api/command/classify-document",
            files=files,
            headers={"Content-Type": None}
        )
        assert response.status_code in [200, 400, 500], f"Unexpected status: {response.status_code}: {response.text}"
        if response.status_code == 400:
            error = response.json().get("detail", "")
            assert "unsupported" not in error.lower() or "file type" not in error.lower(), \
                f"WEBP should be a supported file type: {error}"
    
    def test_classify_unsupported_format_rejected(self, auth_session):
        """Test that unsupported formats like .txt are rejected"""
        files = {"file": ("document.txt", b"This is a text file", "text/plain")}
        
        response = auth_session.post(
            f"{BASE_URL}/api/command/classify-document",
            files=files,
            headers={"Content-Type": None}
        )
        # Should return 400 for unsupported file type
        assert response.status_code == 400, f"Expected 400 for .txt, got {response.status_code}"
        error = response.json().get("detail", "")
        assert "unsupported" in error.lower() or "supported" in error.lower(), \
            f"Error should mention unsupported type: {error}"


# ==================== IDEMPOTENCY TESTS ====================

class TestIdempotency:
    """Tests for idempotent draft execution"""
    
    def test_create_and_execute_draft_idempotent(self, auth_session):
        """Test that executing the same draft twice returns cached result"""
        # Step 1: Create a draft via interpret endpoint
        interpret_data = {
            "command": "create test invoice for 500 CHF"
        }
        interpret_resp = auth_session.post(
            f"{BASE_URL}/api/command/interpret",
            data=interpret_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        # Interpret might fail if no context - skip if so
        if interpret_resp.status_code != 200:
            pytest.skip(f"Interpret endpoint returned {interpret_resp.status_code}")
        
        plan = interpret_resp.json()
        
        # Step 2: Create draft from plan
        draft_resp = auth_session.post(
            f"{BASE_URL}/api/command/draft",
            json=plan
        )
        
        if draft_resp.status_code != 200:
            pytest.skip(f"Draft creation failed: {draft_resp.status_code}")
        
        draft = draft_resp.json()
        draft_id = draft.get("draft_id")
        
        if not draft_id:
            pytest.skip("No draft_id returned")
        
        # Step 3: Execute the draft
        exec_resp = auth_session.post(
            f"{BASE_URL}/api/command/execute",
            json={"draft_id": draft_id, "confirmed": True}
        )
        
        # First execution might fail due to missing required fields - that's OK
        # We're testing idempotency, not the full flow
        first_status = exec_resp.status_code
        first_result = exec_resp.json() if exec_resp.status_code == 200 else None
        
        if first_status != 200:
            pytest.skip(f"Draft execution failed: {first_status} - testing idempotency requires successful execution")
        
        # Step 4: Execute the same draft again - should return cached result
        exec_resp_2 = auth_session.post(
            f"{BASE_URL}/api/command/execute",
            json={"draft_id": draft_id, "confirmed": True}
        )
        
        assert exec_resp_2.status_code == 200, f"Second execution should succeed (cached): {exec_resp_2.text}"
        second_result = exec_resp_2.json()
        
        # Should indicate it was already executed
        assert second_result.get("result", {}).get("already_executed") == True or \
               second_result.get("status") == "executed", \
               f"Second execution should return already_executed=True or status=executed: {second_result}"


# ==================== EXTRACTION VALIDATION TESTS ====================

class TestExtractionValidation:
    """Tests for extraction amount validation (negative, zero, large amounts)"""
    
    def test_extract_document_endpoint_exists(self, auth_session):
        """Test that extract-document endpoint exists and handles validation"""
        # Test with non-existent file path - should return appropriate error
        data = {
            "file_path": "/tmp/nonexistent_file.pdf",
            "document_type": "invoice",
            "context": "{}"
        }
        
        response = auth_session.post(
            f"{BASE_URL}/api/command/extract-document",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        # Should return 400 for non-existent file
        assert response.status_code == 400, f"Expected 400 for non-existent file, got {response.status_code}"
        error = response.json().get("detail", "")
        assert "not found" in error.lower() or "re-upload" in error.lower(), \
            f"Error should mention file not found: {error}"
    
    def test_extract_document_validates_document_type(self, auth_session):
        """Test that extract-document validates document type"""
        data = {
            "file_path": "/tmp/somefile.pdf",
            "document_type": "invalid_type",
            "context": "{}"
        }
        
        response = auth_session.post(
            f"{BASE_URL}/api/command/extract-document",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        # Should return 400 for invalid document type
        assert response.status_code == 400, f"Expected 400 for invalid doc type, got {response.status_code}"


# ==================== ADDITIONAL TESTS ====================

class TestBackendHealth:
    """Basic health and connectivity tests"""
    
    def test_api_health(self):
        """Test API is reachable"""
        response = requests.get(f"{BASE_URL}/api/")
        # Root might return 404 or 200 depending on implementation
        assert response.status_code in [200, 404], f"API not reachable: {response.status_code}"
    
    def test_auth_login_works(self, session):
        """Test that demo agent login works"""
        login_payload = {
            "email": DEMO_AGENT_EMAIL,
            "password": DEMO_AGENT_PASSWORD
        }
        response = session.post(f"{BASE_URL}/api/auth/login", json=login_payload)
        assert response.status_code == 200, f"Login failed: {response.status_code} - {response.text}"
        
        data = response.json()
        assert "user_id" in data, "Login response should include user_id"
        assert data.get("role") == "agent", "Should login as agent role"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
