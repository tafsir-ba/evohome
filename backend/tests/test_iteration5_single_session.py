"""
Iteration 5 - Comprehensive Post-Fix Testing (Rate-Limit Aware)
Tests all features after Phase 3 modularization fixes.
Uses a single agent session to avoid rate limiting.
"""
import pytest
import requests
import os
import uuid
import base64
import io
import time
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Single test agent for all tests
TEST_EMAIL = f"test.agent.iter5.{uuid.uuid4().hex[:8]}@evohome-test.com"
TEST_PASSWORD = "TestPass123!"
TEST_NAME = "Test Agent Iteration 5"


@pytest.fixture(scope="module")
def agent_session():
    """Create a single authenticated agent session for all tests"""
    session = requests.Session()
    
    # Register new agent
    response = session.post(f"{BASE_URL}/api/auth/register", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD,
        "name": TEST_NAME,
        "role": "agent"
    })
    assert response.status_code == 200, f"Registration failed: {response.text}"
    data = response.json()
    token = data.get('token')
    assert token, "No token in registration response"
    
    session.headers.update({"Authorization": f"Bearer {token}"})
    print(f"\n✓ Agent registered: {TEST_EMAIL}")
    
    # Store user data
    session.user_data = data
    return session


@pytest.fixture(scope="module")
def project_data(agent_session):
    """Create a project with units and client for testing"""
    # Create project
    proj_response = agent_session.post(f"{BASE_URL}/api/projects", json={
        "name": "Iteration 5 Test Project",
        "address": "123 Test Street, Geneva",
        "description": "Test project for iteration 5 comprehensive testing"
    })
    assert proj_response.status_code == 200, f"Project creation failed: {proj_response.text}"
    project = proj_response.json()
    project_id = project.get('project_id')
    print(f"✓ Project created: {project_id}")
    
    # Create unit
    unit_response = agent_session.post(f"{BASE_URL}/api/projects/{project_id}/units", json={
        "unit_reference": "Unit A1"
    })
    assert unit_response.status_code == 200, f"Unit creation failed: {unit_response.text}"
    unit = unit_response.json()
    unit_id = unit.get('unit_id')
    print(f"✓ Unit created: {unit_id}")
    
    # Create client
    client_response = agent_session.post(f"{BASE_URL}/api/clients", json={
        "name": "Test Client Iter5",
        "email": f"client.iter5.{uuid.uuid4().hex[:6]}@test.com",
        "phone": "+41 79 123 4567",
        "project_id": project_id,
        "unit_id": unit_id
    })
    assert client_response.status_code == 200, f"Client creation failed: {client_response.text}"
    client = client_response.json()
    client_id = client.get('client_id')
    print(f"✓ Client created: {client_id}")
    
    return {
        "project_id": project_id,
        "unit_id": unit_id,
        "client_id": client_id
    }


class TestHealthAndReadiness:
    """Health and readiness checks"""
    
    def test_health_check(self):
        """GET /api/health - must return alive status"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get('status') == 'alive'
        print(f"✓ Health check passed: {data}")
    
    def test_readiness_check(self):
        """GET /api/ready - must show database: ok, all features enabled"""
        response = requests.get(f"{BASE_URL}/api/ready")
        assert response.status_code == 200
        data = response.json()
        assert data.get('status') == 'ready'
        assert data.get('database') == 'ok'
        features = data.get('features', {})
        assert features.get('email') == True
        assert features.get('billing') == True
        assert features.get('ai_extraction') == True
        print(f"✓ Readiness check passed: {data}")


class TestAuthFlow:
    """Authentication flow tests"""
    
    def test_register_and_login(self, agent_session):
        """POST /api/auth/register and POST /api/auth/login"""
        # Registration already done in fixture
        assert agent_session.user_data.get('user_id')
        assert agent_session.user_data.get('email') == TEST_EMAIL
        assert agent_session.user_data.get('role') == 'agent'
        print(f"✓ Agent registration verified: user_id={agent_session.user_data.get('user_id')}")
        
        # Test login with new session
        login_session = requests.Session()
        response = login_session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert 'token' in data
        print(f"✓ Agent login successful")


class TestProjectAndUnits:
    """Project and unit tests"""
    
    def test_create_project(self, project_data):
        """POST /api/projects - create project"""
        assert project_data['project_id'].startswith('proj_')
        print(f"✓ Project creation verified: {project_data['project_id']}")
    
    def test_get_project_context(self, agent_session, project_data):
        """GET /api/projects/{id}/context - verify units and clients appear"""
        response = agent_session.get(f"{BASE_URL}/api/projects/{project_data['project_id']}/context")
        assert response.status_code == 200, f"Context fetch failed: {response.text}"
        data = response.json()
        
        assert 'project' in data
        assert 'units' in data
        assert 'clients' in data
        assert data['project']['project_id'] == project_data['project_id']
        assert len(data.get('units', [])) >= 1
        assert len(data.get('clients', [])) >= 1
        print(f"✓ Project context retrieved: {len(data.get('units', []))} units, {len(data.get('clients', []))} clients")


class TestDocumentOperations:
    """Document creation, hero image upload, and PDF generation tests"""
    
    def test_create_document_with_items(self, agent_session, project_data):
        """POST /api/documents/create - create document with items"""
        response = agent_session.post(f"{BASE_URL}/api/documents/create", json={
            "type": "quote",
            "client_id": project_data['client_id'],
            "title": "Kitchen Renovation Quote",
            "amount": 15000.00,
            "items": [
                {"description": "Cabinet installation", "quantity": 1, "unit_price": 8000, "total": 8000},
                {"description": "Countertop", "quantity": 1, "unit_price": 5000, "total": 5000},
                {"description": "Labor", "quantity": 10, "unit_price": 200, "total": 2000}
            ],
            "supplier_name": "Kitchen Pro SA"
        })
        assert response.status_code == 200, f"Document creation failed: {response.text}"
        data = response.json()
        assert data.get('document_id')
        assert data.get('type') == 'quote'
        assert data.get('amount') == 15000.00
        print(f"✓ Document created: {data.get('document_id')}")
        return data.get('document_id')
    
    def test_upload_hero_image(self, agent_session, project_data):
        """POST /api/documents/{id}/hero-image - upload hero image"""
        # First create a document
        doc_response = agent_session.post(f"{BASE_URL}/api/documents/create", json={
            "type": "quote",
            "client_id": project_data['client_id'],
            "title": "Hero Image Test Quote",
            "amount": 5000.00
        })
        assert doc_response.status_code == 200
        document_id = doc_response.json().get('document_id')
        
        # Create a minimal PNG image (1x1 pixel red)
        png_data = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="
        )
        
        files = {'file': ('test_hero.png', io.BytesIO(png_data), 'image/png')}
        response = agent_session.post(f"{BASE_URL}/api/documents/{document_id}/hero-image", files=files)
        assert response.status_code == 200, f"Hero image upload failed: {response.text}"
        data = response.json()
        assert 'hero_image_url' in data
        print(f"✓ Hero image uploaded: {data.get('hero_image_url')}")
    
    def test_generate_pdf(self, agent_session, project_data):
        """GET /api/documents/{id}/pdf - generate PDF for document"""
        # First create a document
        doc_response = agent_session.post(f"{BASE_URL}/api/documents/create", json={
            "type": "invoice",
            "client_id": project_data['client_id'],
            "title": "PDF Generation Test Invoice",
            "amount": 7500.00,
            "items": [
                {"description": "Service fee", "quantity": 1, "unit_price": 7500, "total": 7500}
            ]
        })
        assert doc_response.status_code == 200
        document_id = doc_response.json().get('document_id')
        
        # Generate PDF
        response = agent_session.get(f"{BASE_URL}/api/documents/{document_id}/pdf")
        assert response.status_code == 200, f"PDF generation failed: {response.text}"
        assert response.headers.get('content-type') == 'application/pdf'
        assert len(response.content) > 0
        print(f"✓ PDF generated: {len(response.content)} bytes")


class TestClientPreview:
    """Client preview endpoint test"""
    
    def test_client_preview(self, agent_session, project_data):
        """GET /api/clients/{id}/preview - verify no crash"""
        response = agent_session.get(f"{BASE_URL}/api/clients/{project_data['client_id']}/preview")
        assert response.status_code == 200, f"Client preview failed: {response.text}"
        data = response.json()
        assert 'client' in data
        assert 'project' in data
        assert data.get('is_preview') == True
        print(f"✓ Client preview works: client={project_data['client_id']}")


class TestCommandCenterOperations:
    """Command center document classification and extraction tests"""
    
    def test_classify_document_image(self, agent_session):
        """POST /api/command/classify-document - classify PNG file"""
        # Create a minimal PNG image
        png_data = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="
        )
        
        files = {'file': ('test_document.png', io.BytesIO(png_data), 'image/png')}
        response = agent_session.post(f"{BASE_URL}/api/command/classify-document", files=files)
        assert response.status_code == 200, f"Document classification failed: {response.text}"
        data = response.json()
        assert 'document_type' in data
        assert 'confidence' in data
        assert 'file_path' in data
        print(f"✓ Document classified: type={data.get('document_type')}, confidence={data.get('confidence')}")
        return data.get('file_path')
    
    def test_extract_document_type_unknown(self, agent_session):
        """POST /api/command/extract-document with document_type=unknown - must NOT return 400"""
        # First classify a document to get a file_path
        png_data = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="
        )
        
        files = {'file': ('test_unknown.png', io.BytesIO(png_data), 'image/png')}
        classify_response = agent_session.post(f"{BASE_URL}/api/command/classify-document", files=files)
        assert classify_response.status_code == 200
        file_path = classify_response.json().get('file_path')
        
        # Now extract with type=unknown - this should NOT return 400
        response = agent_session.post(f"{BASE_URL}/api/command/extract-document", data={
            "file_path": file_path,
            "document_type": "unknown",
            "context": "{}"
        })
        # Should NOT be 400 - unknown type should fall back to quote extraction
        assert response.status_code != 400, f"Extract with type=unknown returned 400: {response.text}"
        assert response.status_code == 200, f"Extract failed: {response.text}"
        data = response.json()
        assert 'intent' in data or 'extracted_data' in data
        print(f"✓ Extract with type=unknown succeeded (fallback to quote)")
    
    def test_extract_document_type_quote(self, agent_session):
        """POST /api/command/extract-document with document_type=quote"""
        # First classify a document to get a file_path
        png_data = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="
        )
        
        files = {'file': ('test_quote.png', io.BytesIO(png_data), 'image/png')}
        classify_response = agent_session.post(f"{BASE_URL}/api/command/classify-document", files=files)
        assert classify_response.status_code == 200
        file_path = classify_response.json().get('file_path')
        
        # Extract with type=quote
        response = agent_session.post(f"{BASE_URL}/api/command/extract-document", data={
            "file_path": file_path,
            "document_type": "quote",
            "context": "{}"
        })
        assert response.status_code == 200, f"Extract with type=quote failed: {response.text}"
        data = response.json()
        assert 'intent' in data or 'extracted_data' in data
        print(f"✓ Extract with type=quote succeeded")


class TestDocumentUpload:
    """Document upload tests (PDF)"""
    
    def test_upload_pdf_document(self, agent_session, project_data):
        """POST /api/documents/upload - upload PDF file"""
        # Create a minimal PDF
        pdf_content = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\nxref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000052 00000 n \n0000000101 00000 n \ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n178\n%%EOF"
        
        files = {'file': ('test.pdf', io.BytesIO(pdf_content), 'application/pdf')}
        data = {'client_id': project_data['client_id']}
        
        response = agent_session.post(f"{BASE_URL}/api/documents/upload", files=files, data=data)
        assert response.status_code == 200, f"PDF upload failed: {response.text}"
        result = response.json()
        assert 'preview_id' in result or 'title' in result
        print(f"✓ PDF document uploaded successfully")


class TestVaultUpload:
    """Vault document upload tests"""
    
    def test_upload_vault_document(self, agent_session):
        """POST /api/vault/upload - upload vault document"""
        # Create a minimal PDF for vault
        pdf_content = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\nxref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000052 00000 n \n0000000101 00000 n \ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n178\n%%EOF"
        
        files = {'file': ('vault_test.pdf', io.BytesIO(pdf_content), 'application/pdf')}
        data = {
            'name': 'Test Vault Document',
            'category': 'Contracts',
            'description': 'Test vault document for iteration 5'
        }
        
        response = agent_session.post(f"{BASE_URL}/api/vault/upload", files=files, data=data)
        assert response.status_code == 200, f"Vault upload failed: {response.text}"
        result = response.json()
        assert result.get('vault_id')
        assert result.get('name') == 'Test Vault Document'
        print(f"✓ Vault document uploaded: {result.get('vault_id')}")


class TestActivities:
    """Activity posting tests"""
    
    def test_post_activity_with_form_data(self, agent_session, project_data):
        """POST /api/activities - post activity with form data"""
        # Post activity with form data
        response = agent_session.post(f"{BASE_URL}/api/activities", data={
            "type": "message",
            "project_id": project_data['project_id'],
            "client_ids": project_data['client_id'],
            "title": "Test Activity",
            "content": "This is a test activity message"
        })
        assert response.status_code == 200, f"Activity posting failed: {response.text}"
        result = response.json()
        assert result.get('activity_id')
        assert result.get('type') == 'message'
        print(f"✓ Activity posted: {result.get('activity_id')}")


class TestBillingCheckout:
    """Billing checkout tests"""
    
    def test_create_checkout_session(self, agent_session):
        """POST /api/billing/create-checkout-session - create Stripe checkout session"""
        # Create checkout session with plan_id=starter
        response = agent_session.post(f"{BASE_URL}/api/billing/create-checkout-session", json={
            "plan_id": "starter",
            "origin_url": "https://evo-access.preview.emergentagent.com"
        })
        assert response.status_code == 200, f"Checkout session creation failed: {response.text}"
        result = response.json()
        assert 'checkout_url' in result
        assert 'session_id' in result
        assert 'checkout.stripe.com' in result.get('checkout_url', '')
        print(f"✓ Stripe checkout session created: {result.get('session_id')[:20]}...")


class TestTimelineSteps:
    """Timeline steps CRUD tests"""
    
    def test_timeline_steps_crud(self, agent_session, project_data):
        """POST/GET /api/projects/{id}/steps - timeline steps CRUD"""
        project_id = project_data['project_id']
        
        # Create step (planned_end is required by schema)
        step_response = agent_session.post(f"{BASE_URL}/api/projects/{project_id}/steps", json={
            "title": "Foundation Work",
            "description": "Lay foundation for the building",
            "order_index": 1,
            "planned_start": "2026-05-01",
            "planned_end": "2026-06-01"
        })
        assert step_response.status_code == 200, f"Step creation failed: {step_response.text}"
        step_data = step_response.json()
        assert step_data.get('step_id')
        assert step_data.get('title') == 'Foundation Work'
        step_id = step_data.get('step_id')
        print(f"✓ Step created: {step_id}")
        
        # Get steps
        get_response = agent_session.get(f"{BASE_URL}/api/projects/{project_id}/steps")
        assert get_response.status_code == 200
        steps_data = get_response.json()
        assert 'steps' in steps_data
        assert len(steps_data['steps']) >= 1
        print(f"✓ Steps retrieved: {len(steps_data['steps'])} steps")


class TestNotifications:
    """Notifications list test"""
    
    def test_get_notifications(self, agent_session):
        """GET /api/notifications - get notifications list"""
        response = agent_session.get(f"{BASE_URL}/api/notifications")
        assert response.status_code == 200, f"Notifications fetch failed: {response.text}"
        data = response.json()
        # API returns object with notifications key
        if isinstance(data, dict):
            assert 'notifications' in data
            notifications = data.get('notifications', [])
        else:
            notifications = data
        assert isinstance(notifications, list)
        print(f"✓ Notifications retrieved: {len(notifications)} notifications")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
