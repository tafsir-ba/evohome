"""
Batch 3 Feature Tests: Landing, Auth, Settings, Demo Plan
Tests:
1. Landing page accessibility (frontend test)
2. Buyer email/password registration (POST /api/auth/buyer/register)
3. Buyer email/password login (POST /api/auth/buyer/login)
4. Agent settings endpoints (GET/PUT /api/settings)
5. Logo upload for Pro agents (POST /api/settings/logo)
6. Demo agent Pro plan verification
7. Document upload endpoint (POST /api/documents/upload?doc_type=quote)
"""

import pytest
import requests
import os
import uuid
from datetime import datetime

# Get BASE_URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    raise RuntimeError("REACT_APP_BACKEND_URL environment variable not set")


class TestBuyerAuth:
    """Tests for buyer email/password authentication"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.test_email = f"test_buyer_{uuid.uuid4().hex[:8]}@example.com"
        self.test_password = "testpass123"
        self.test_name = "Test Buyer"
    
    def test_buyer_register_success(self):
        """POST /api/auth/buyer/register should create buyer account"""
        response = self.session.post(f"{BASE_URL}/api/auth/buyer/register", json={
            "email": self.test_email,
            "password": self.test_password,
            "name": self.test_name
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "user_id" in data, "Response should contain user_id"
        assert data["email"] == self.test_email, "Email should match"
        assert data["name"] == self.test_name, "Name should match"
        assert data["role"] == "buyer", "Role should be buyer"
        assert "token" in data, "Response should contain token"
    
    def test_buyer_register_duplicate_email(self):
        """POST /api/auth/buyer/register should fail for duplicate email"""
        # First registration
        self.session.post(f"{BASE_URL}/api/auth/buyer/register", json={
            "email": self.test_email,
            "password": self.test_password,
            "name": self.test_name
        })
        
        # Second registration with same email
        response = self.session.post(f"{BASE_URL}/api/auth/buyer/register", json={
            "email": self.test_email,
            "password": "anotherpass",
            "name": "Another Name"
        })
        
        assert response.status_code == 400, f"Expected 400 for duplicate email, got {response.status_code}"
    
    def test_buyer_login_success(self):
        """POST /api/auth/buyer/login should authenticate buyer"""
        # First register
        reg_response = self.session.post(f"{BASE_URL}/api/auth/buyer/register", json={
            "email": self.test_email,
            "password": self.test_password,
            "name": self.test_name
        })
        assert reg_response.status_code == 200, "Registration should succeed first"
        
        # Then login
        response = self.session.post(f"{BASE_URL}/api/auth/buyer/login", json={
            "email": self.test_email,
            "password": self.test_password
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "user_id" in data, "Response should contain user_id"
        assert data["email"] == self.test_email, "Email should match"
        assert data["role"] == "buyer", "Role should be buyer"
        assert "token" in data, "Response should contain token"
    
    def test_buyer_login_invalid_credentials(self):
        """POST /api/auth/buyer/login should fail for invalid credentials"""
        response = self.session.post(f"{BASE_URL}/api/auth/buyer/login", json={
            "email": "nonexistent@example.com",
            "password": "wrongpassword"
        })
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"


class TestAgentSettings:
    """Tests for agent settings endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        # Login as demo agent
        response = self.session.post(f"{BASE_URL}/api/demo/enter", json={"persona": "agent", "fresh": False})
        if response.status_code == 200:
            data = response.json()
            self.token = data.get('token')
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        else:
            pytest.skip("Demo agent login failed")
    
    def test_get_settings(self):
        """GET /api/settings should return agent settings"""
        response = self.session.get(f"{BASE_URL}/api/settings")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "language" in data, "Response should contain language"
        assert "currency" in data, "Response should contain currency"
        assert "company_name" in data, "Response should contain company_name"
        
        # Verify default values for demo agent
        assert data["language"] in ['en', 'de', 'fr', 'it'], "Language should be valid"
        assert data["currency"] in ['CHF', 'EUR', 'USD'], "Currency should be valid"
    
    def test_update_settings_language(self):
        """PUT /api/settings should update language"""
        response = self.session.put(f"{BASE_URL}/api/settings", json={
            "language": "de"
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Verify change persisted
        get_response = self.session.get(f"{BASE_URL}/api/settings")
        data = get_response.json()
        assert data["language"] == "de", "Language should be updated to German"
    
    def test_update_settings_currency(self):
        """PUT /api/settings should update currency"""
        response = self.session.put(f"{BASE_URL}/api/settings", json={
            "currency": "EUR"
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Verify change persisted
        get_response = self.session.get(f"{BASE_URL}/api/settings")
        data = get_response.json()
        assert data["currency"] == "EUR", "Currency should be updated to EUR"
    
    def test_update_settings_company_name(self):
        """PUT /api/settings should update company name"""
        test_company = f"Test Company {uuid.uuid4().hex[:6]}"
        response = self.session.put(f"{BASE_URL}/api/settings", json={
            "company_name": test_company
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Verify change persisted
        get_response = self.session.get(f"{BASE_URL}/api/settings")
        data = get_response.json()
        assert data["company_name"] == test_company, "Company name should be updated"
    
    def test_update_settings_invalid_language(self):
        """PUT /api/settings should reject invalid language"""
        response = self.session.put(f"{BASE_URL}/api/settings", json={
            "language": "invalid"
        })
        
        assert response.status_code == 400, f"Expected 400 for invalid language, got {response.status_code}"
    
    def test_update_settings_invalid_currency(self):
        """PUT /api/settings should reject invalid currency"""
        response = self.session.put(f"{BASE_URL}/api/settings", json={
            "currency": "INVALID"
        })
        
        assert response.status_code == 400, f"Expected 400 for invalid currency, got {response.status_code}"


class TestDemoAgentProPlan:
    """Tests for demo agent having Pro subscription"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        # Login as demo agent
        response = self.session.post(f"{BASE_URL}/api/demo/enter", json={"persona": "agent", "fresh": False})
        if response.status_code == 200:
            data = response.json()
            self.token = data.get('token')
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        else:
            pytest.skip("Demo agent login failed")
    
    def test_demo_agent_has_pro_plan(self):
        """Demo agent should have Pro subscription"""
        response = self.session.get(f"{BASE_URL}/api/billing/status")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["plan_id"] == "pro", f"Demo agent should have Pro plan, got {data['plan_id']}"
        assert data["plan_name"] == "Pro", f"Plan name should be Pro, got {data['plan_name']}"
        assert data["property_limit"] == 50, f"Pro plan should have 50 property limit, got {data['property_limit']}"


class TestLogoUpload:
    """Tests for logo upload feature (Pro plan required)"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        # Login as demo agent (has Pro plan)
        response = self.session.post(f"{BASE_URL}/api/demo/enter", json={"persona": "agent", "fresh": False})
        if response.status_code == 200:
            data = response.json()
            self.token = data.get('token')
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        else:
            pytest.skip("Demo agent login failed")
    
    def test_logo_upload_pro_agent(self):
        """POST /api/settings/logo should work for Pro agents"""
        # Create a minimal PNG file (1x1 transparent pixel)
        png_data = bytes([
            0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0x00, 0x00, 0x00, 0x0d,
            0x49, 0x48, 0x44, 0x52, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
            0x08, 0x06, 0x00, 0x00, 0x00, 0x1f, 0x15, 0xc4, 0x89, 0x00, 0x00, 0x00,
            0x0d, 0x49, 0x44, 0x41, 0x54, 0x08, 0xd7, 0x63, 0x60, 0x60, 0x60, 0x60,
            0x00, 0x00, 0x00, 0x05, 0x00, 0x01, 0x87, 0xa1, 0xa4, 0x9c, 0x00, 0x00,
            0x00, 0x00, 0x49, 0x45, 0x4e, 0x44, 0xae, 0x42, 0x60, 0x82
        ])
        
        files = {
            'file': ('test_logo.png', png_data, 'image/png')
        }
        
        # Remove Content-Type from headers for multipart upload
        headers = {"Authorization": f"Bearer {self.token}"}
        
        response = requests.post(
            f"{BASE_URL}/api/settings/logo",
            files=files,
            headers=headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "logo_url" in data, "Response should contain logo_url"
        assert data["logo_url"].startswith("/uploads/"), "Logo URL should be in uploads directory"
    
    def test_logo_upload_invalid_type(self):
        """POST /api/settings/logo should reject non-image files"""
        files = {
            'file': ('test.txt', b'not an image', 'text/plain')
        }
        
        headers = {"Authorization": f"Bearer {self.token}"}
        
        response = requests.post(
            f"{BASE_URL}/api/settings/logo",
            files=files,
            headers=headers
        )
        
        assert response.status_code == 400, f"Expected 400 for invalid file type, got {response.status_code}"
    
    def test_logo_delete(self):
        """DELETE /api/settings/logo should remove the logo"""
        response = self.session.delete(f"{BASE_URL}/api/settings/logo")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"


class TestLogoUploadPlanRestriction:
    """Tests for logo upload plan restriction (Free/Starter should get 403)"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        # Register a new agent (will have Free plan by default)
        self.test_email = f"test_agent_{uuid.uuid4().hex[:8]}@example.com"
        response = self.session.post(f"{BASE_URL}/api/auth/register", json={
            "email": self.test_email,
            "password": "testpass123",
            "name": "Test Agent Free Plan"
        })
        if response.status_code == 200:
            data = response.json()
            self.token = data.get('token')
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        else:
            pytest.skip("Agent registration failed")
    
    def test_logo_upload_free_agent_forbidden(self):
        """POST /api/settings/logo should return 403 for Free plan agents"""
        # Create a minimal PNG file
        png_data = bytes([
            0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0x00, 0x00, 0x00, 0x0d,
            0x49, 0x48, 0x44, 0x52, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
            0x08, 0x06, 0x00, 0x00, 0x00, 0x1f, 0x15, 0xc4, 0x89, 0x00, 0x00, 0x00,
            0x0d, 0x49, 0x44, 0x41, 0x54, 0x08, 0xd7, 0x63, 0x60, 0x60, 0x60, 0x60,
            0x00, 0x00, 0x00, 0x05, 0x00, 0x01, 0x87, 0xa1, 0xa4, 0x9c, 0x00, 0x00,
            0x00, 0x00, 0x49, 0x45, 0x4e, 0x44, 0xae, 0x42, 0x60, 0x82
        ])
        
        files = {
            'file': ('test_logo.png', png_data, 'image/png')
        }
        
        headers = {"Authorization": f"Bearer {self.token}"}
        
        response = requests.post(
            f"{BASE_URL}/api/settings/logo",
            files=files,
            headers=headers
        )
        
        assert response.status_code == 403, f"Expected 403 for Free plan agent, got {response.status_code}: {response.text}"


class TestDocumentUploadEndpoint:
    """Tests for document upload with doc_type query parameter"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        # Login as demo agent
        response = self.session.post(f"{BASE_URL}/api/demo/enter", json={"persona": "agent", "fresh": False})
        if response.status_code == 200:
            data = response.json()
            self.token = data.get('token')
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
            
            # Get a client for document upload
            clients_response = self.session.get(f"{BASE_URL}/api/clients")
            if clients_response.status_code == 200:
                clients = clients_response.json()
                if clients:
                    self.client_id = clients[0]['client_id']
                else:
                    pytest.skip("No demo clients available")
            else:
                pytest.skip("Failed to get clients")
        else:
            pytest.skip("Demo agent login failed")
    
    def test_document_upload_quote_type(self):
        """POST /api/documents/upload?doc_type=quote should create a quote"""
        # Create a minimal PDF file
        pdf_content = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
        
        files = {
            'file': ('test_quote.pdf', pdf_content, 'application/pdf')
        }
        
        data = {
            'client_id': self.client_id
        }
        
        headers = {"Authorization": f"Bearer {self.token}"}
        
        response = requests.post(
            f"{BASE_URL}/api/documents/upload?doc_type=quote",
            files=files,
            data=data,
            headers=headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        doc_data = response.json()
        assert doc_data["type"] == "quote", f"Document type should be 'quote', got {doc_data['type']}"
        assert doc_data["document_number"].startswith("QT-"), "Quote number should start with QT-"
    
    def test_document_upload_invoice_type(self):
        """POST /api/documents/upload?doc_type=invoice should create an invoice"""
        # Create a minimal PDF file
        pdf_content = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
        
        files = {
            'file': ('test_invoice.pdf', pdf_content, 'application/pdf')
        }
        
        data = {
            'client_id': self.client_id
        }
        
        headers = {"Authorization": f"Bearer {self.token}"}
        
        response = requests.post(
            f"{BASE_URL}/api/documents/upload?doc_type=invoice",
            files=files,
            data=data,
            headers=headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        doc_data = response.json()
        assert doc_data["type"] == "invoice", f"Document type should be 'invoice', got {doc_data['type']}"
        assert doc_data["document_number"].startswith("INV-"), "Invoice number should start with INV-"


class TestNavigationHasSettings:
    """Test that navigation has Settings link instead of Billing"""
    
    def test_navigation_check(self):
        """This is a frontend test - just verify settings endpoint exists"""
        session = requests.Session()
        
        # Login as demo agent
        response = session.post(f"{BASE_URL}/api/demo/enter", json={"persona": "agent", "fresh": False})
        assert response.status_code == 200, "Demo agent login should work"
        
        token = response.json().get('token')
        session.headers.update({"Authorization": f"Bearer {token}"})
        
        # Verify settings endpoint is accessible
        response = session.get(f"{BASE_URL}/api/settings")
        assert response.status_code == 200, "Settings endpoint should be accessible"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
