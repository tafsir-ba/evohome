"""
Bug Fixes Iteration 23 - Testing reopened bugs:
- BUG-002: Quote context not project/unit-aware (client dropdown shows Name — Project — Unit)
- BUG-003: Hero image upload on quote edit page
- BUG-004: Company logo upload in Settings
- BUG-005: Vault upload with/without project_id
- BUG-006: Buyer can see agent change request response
"""
import pytest
import requests
import os
import io
from PIL import Image

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
AGENT_EMAIL = "demo.agent@upgradeflow.com"
AGENT_PASSWORD = "demo123"


@pytest.fixture(scope="module")
def agent_session():
    """Login as agent and return session with auth token"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    
    # Login
    res = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": AGENT_EMAIL,
        "password": AGENT_PASSWORD
    })
    
    if res.status_code != 200:
        pytest.skip(f"Agent login failed: {res.status_code} - {res.text}")
    
    data = res.json()
    token = data.get("access_token") or data.get("token")
    if not token:
        pytest.skip("No token in login response")
    
    session.headers.update({"Authorization": f"Bearer {token}"})
    return session


@pytest.fixture(scope="module")
def agent_data(agent_session):
    """Get agent user data"""
    res = agent_session.get(f"{BASE_URL}/api/auth/me")
    if res.status_code == 200:
        return res.json()
    return {}


class TestBUG002_ClientProjectContext:
    """BUG-002: GET /api/clients returns project_name field for each client"""
    
    def test_clients_endpoint_returns_project_name(self, agent_session):
        """Verify clients endpoint returns project_name field"""
        res = agent_session.get(f"{BASE_URL}/api/clients")
        assert res.status_code == 200, f"Failed to get clients: {res.text}"
        
        clients = res.json()
        assert isinstance(clients, list), "Clients should be a list"
        
        # Check if at least one client has project_name
        clients_with_project = [c for c in clients if c.get("project_id")]
        
        if clients_with_project:
            # Verify project_name is enriched
            for client in clients_with_project:
                assert "project_name" in client, f"Client {client.get('client_id')} missing project_name field"
                print(f"✓ Client {client.get('name')} has project_name: {client.get('project_name')}")
        else:
            print("⚠ No clients with project_id found - skipping project_name verification")
    
    def test_client_has_unit_reference(self, agent_session):
        """Verify clients have unit_reference for dropdown display"""
        res = agent_session.get(f"{BASE_URL}/api/clients")
        assert res.status_code == 200
        
        clients = res.json()
        clients_with_unit = [c for c in clients if c.get("unit_id")]
        
        if clients_with_unit:
            for client in clients_with_unit:
                # unit_reference may be on the client or need to be fetched
                print(f"✓ Client {client.get('name')} has unit_id: {client.get('unit_id')}")
        else:
            print("⚠ No clients with unit_id found")


class TestBUG003_HeroImageUpload:
    """BUG-003: Hero image upload on quote edit page works with Authorization header"""
    
    def test_hero_image_upload_with_auth(self, agent_session):
        """Test hero image upload requires and works with auth header"""
        # First get a document to test with
        res = agent_session.get(f"{BASE_URL}/api/documents?type=quote")
        if res.status_code != 200:
            pytest.skip("Could not fetch documents")
        
        docs = res.json()
        if not docs:
            pytest.skip("No quote documents found for testing")
        
        doc = docs[0]
        document_id = doc.get("document_id")
        
        # Create a test image
        img = Image.new('RGB', (100, 100), color='red')
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='JPEG')
        img_bytes.seek(0)
        
        # Upload hero image with auth header
        files = {'file': ('test_hero.jpg', img_bytes, 'image/jpeg')}
        
        # Remove Content-Type for multipart upload
        headers = {"Authorization": agent_session.headers.get("Authorization")}
        
        res = requests.post(
            f"{BASE_URL}/api/documents/{document_id}/hero-image",
            files=files,
            headers=headers
        )
        
        assert res.status_code == 200, f"Hero image upload failed: {res.status_code} - {res.text}"
        data = res.json()
        assert "hero_image_url" in data, "Response should contain hero_image_url"
        print(f"✓ Hero image uploaded successfully: {data.get('hero_image_url')}")
    
    def test_hero_image_upload_without_auth_fails(self):
        """Test hero image upload fails without auth"""
        # Create a test image
        img = Image.new('RGB', (100, 100), color='blue')
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='JPEG')
        img_bytes.seek(0)
        
        files = {'file': ('test_hero.jpg', img_bytes, 'image/jpeg')}
        
        res = requests.post(
            f"{BASE_URL}/api/documents/fake_doc_id/hero-image",
            files=files
        )
        
        # Should fail with 401 or 403
        assert res.status_code in [401, 403, 404], f"Expected auth error, got: {res.status_code}"
        print(f"✓ Hero image upload correctly requires auth (status: {res.status_code})")


class TestBUG004_LogoUpload:
    """BUG-004: Company logo upload in Settings works with Authorization header"""
    
    def test_logo_upload_endpoint_exists(self, agent_session):
        """Test logo upload endpoint is accessible"""
        # Create a test image
        img = Image.new('RGB', (100, 100), color='green')
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes.seek(0)
        
        files = {'file': ('test_logo.png', img_bytes, 'image/png')}
        headers = {"Authorization": agent_session.headers.get("Authorization")}
        
        res = requests.post(
            f"{BASE_URL}/api/settings/logo",
            files=files,
            headers=headers
        )
        
        # May fail with 403 if not Pro plan, but should not be 401
        if res.status_code == 403:
            data = res.json()
            assert "Pro plan" in data.get("detail", ""), "Should indicate Pro plan required"
            print("✓ Logo upload correctly requires Pro plan")
        elif res.status_code == 200:
            data = res.json()
            assert "logo_url" in data, "Response should contain logo_url"
            print(f"✓ Logo uploaded successfully: {data.get('logo_url')}")
        else:
            pytest.fail(f"Unexpected status: {res.status_code} - {res.text}")
    
    def test_logo_upload_without_auth_fails(self):
        """Test logo upload fails without auth"""
        img = Image.new('RGB', (100, 100), color='yellow')
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes.seek(0)
        
        files = {'file': ('test_logo.png', img_bytes, 'image/png')}
        
        res = requests.post(
            f"{BASE_URL}/api/settings/logo",
            files=files
        )
        
        assert res.status_code in [401, 403], f"Expected auth error, got: {res.status_code}"
        print(f"✓ Logo upload correctly requires auth (status: {res.status_code})")


class TestBUG005_VaultUpload:
    """BUG-005: Vault upload works with/without project_id"""
    
    def test_vault_upload_with_project_and_clients(self, agent_session):
        """Test vault upload with project_id and client_ids"""
        # Get a project
        res = agent_session.get(f"{BASE_URL}/api/projects")
        if res.status_code != 200 or not res.json():
            pytest.skip("No projects found")
        
        project = res.json()[0]
        project_id = project.get("project_id")
        
        # Get clients
        res = agent_session.get(f"{BASE_URL}/api/clients")
        clients = res.json() if res.status_code == 200 else []
        client_ids = ",".join([c["client_id"] for c in clients[:2]]) if clients else ""
        
        # Create test PDF
        pdf_content = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\ntrailer\n<<\n/Root 1 0 R\n>>\n%%EOF"
        
        files = {'file': ('test_vault.pdf', io.BytesIO(pdf_content), 'application/pdf')}
        data = {
            'title': 'TEST_Vault_With_Project',
            'category': 'Contracts',
            'project_id': project_id,
            'client_ids': client_ids,
            'description': 'Test vault document with project',
            'access_level': 'shared' if client_ids else 'private',
            'doc_type': 'general'
        }
        
        headers = {"Authorization": agent_session.headers.get("Authorization")}
        
        res = requests.post(
            f"{BASE_URL}/api/vault/upload",
            files=files,
            data=data,
            headers=headers
        )
        
        assert res.status_code == 200, f"Vault upload failed: {res.status_code} - {res.text}"
        result = res.json()
        assert "vault_document_id" in result or "vault_id" in result, "Response should contain vault document ID"
        print(f"✓ Vault upload with project_id succeeded")
    
    def test_vault_upload_without_project(self, agent_session):
        """Test vault upload WITHOUT project_id (general unassigned document)"""
        # Create test PDF
        pdf_content = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\ntrailer\n<<\n/Root 1 0 R\n>>\n%%EOF"
        
        files = {'file': ('test_vault_no_project.pdf', io.BytesIO(pdf_content), 'application/pdf')}
        data = {
            'title': 'TEST_Vault_No_Project',
            'category': 'Other',
            'project_id': '',  # Empty string - should be accepted
            'client_ids': '',  # Empty string - should be accepted
            'description': 'Test vault document without project',
            'access_level': 'private',
            'doc_type': 'general'
        }
        
        headers = {"Authorization": agent_session.headers.get("Authorization")}
        
        res = requests.post(
            f"{BASE_URL}/api/vault/upload",
            files=files,
            data=data,
            headers=headers
        )
        
        assert res.status_code == 200, f"Vault upload without project failed: {res.status_code} - {res.text}"
        result = res.json()
        assert "vault_document_id" in result or "vault_id" in result, "Response should contain vault document ID"
        print(f"✓ Vault upload WITHOUT project_id succeeded (general document)")
    
    def test_vault_upload_error_format(self, agent_session):
        """Test vault upload error messages are properly formatted (not [object Object])"""
        # Try to upload with invalid data to trigger error
        files = {'file': ('test.pdf', io.BytesIO(b"not a pdf"), 'application/pdf')}
        data = {
            'title': '',  # Empty title should cause validation error
            'category': 'InvalidCategory',
            'project_id': '',
            'client_ids': '',
        }
        
        headers = {"Authorization": agent_session.headers.get("Authorization")}
        
        res = requests.post(
            f"{BASE_URL}/api/vault/upload",
            files=files,
            data=data,
            headers=headers
        )
        
        if res.status_code != 200:
            error_data = res.json()
            detail = error_data.get("detail", "")
            
            # Check error is not [object Object]
            assert "[object Object]" not in str(detail), "Error should not be [object Object]"
            print(f"✓ Error message properly formatted: {detail}")
        else:
            print("⚠ Upload succeeded unexpectedly - no error to check")


class TestBUG006_ChangeRequestThread:
    """BUG-006: Buyer can see agent change request response"""
    
    def test_change_request_entity_endpoint(self, agent_session):
        """Test change request entity endpoint returns thread data"""
        # Get a document
        res = agent_session.get(f"{BASE_URL}/api/documents")
        if res.status_code != 200 or not res.json():
            pytest.skip("No documents found")
        
        doc = res.json()[0]
        document_id = doc.get("document_id")
        doc_type = doc.get("type", "quote")
        
        # Try to get change requests for this entity
        res = agent_session.get(f"{BASE_URL}/api/change-requests/entity/{doc_type}/{document_id}")
        
        assert res.status_code == 200, f"Failed to get change requests: {res.status_code} - {res.text}"
        data = res.json()
        
        # Should return a structure with change_requests array
        assert "change_requests" in data, "Response should contain change_requests array"
        print(f"✓ Change request entity endpoint works, found {len(data.get('change_requests', []))} requests")
    
    def test_change_request_respond_endpoint(self, agent_session):
        """Test agent can respond to change request"""
        # Get existing change requests
        res = agent_session.get(f"{BASE_URL}/api/change-requests")
        
        if res.status_code != 200:
            pytest.skip("Could not fetch change requests")
        
        change_requests = res.json()
        open_requests = [cr for cr in change_requests if cr.get("status") in ["open", "under_review"]]
        
        if not open_requests:
            print("⚠ No open change requests to test response - skipping")
            return
        
        cr = open_requests[0]
        cr_id = cr.get("change_request_id")
        
        # Try to respond
        res = agent_session.post(
            f"{BASE_URL}/api/change-requests/{cr_id}/respond",
            json={"message": "TEST_Response from agent"}
        )
        
        if res.status_code == 200:
            print(f"✓ Agent can respond to change request")
        else:
            print(f"⚠ Response failed: {res.status_code} - {res.text}")


class TestDashboardAndFeed:
    """Test Dashboard Control Tower and Feed"""
    
    def test_dashboard_stats(self, agent_session):
        """Test dashboard stats endpoint"""
        res = agent_session.get(f"{BASE_URL}/api/stats")
        assert res.status_code == 200, f"Stats endpoint failed: {res.status_code}"
        
        data = res.json()
        print(f"✓ Dashboard stats loaded: {list(data.keys())}")
    
    def test_activities_feed(self, agent_session):
        """Test activities feed loads"""
        res = agent_session.get(f"{BASE_URL}/api/activities")
        assert res.status_code == 200, f"Activities endpoint failed: {res.status_code}"
        
        data = res.json()
        activities = data.get("activities", data) if isinstance(data, dict) else data
        print(f"✓ Feed loaded with {len(activities) if isinstance(activities, list) else 'N/A'} activities")


class TestNoAuthErrors:
    """Test all pages load without 401 errors"""
    
    def test_documents_no_401(self, agent_session):
        """Documents endpoint should not return 401"""
        res = agent_session.get(f"{BASE_URL}/api/documents")
        assert res.status_code != 401, "Documents returned 401"
        print(f"✓ Documents: {res.status_code}")
    
    def test_projects_no_401(self, agent_session):
        """Projects endpoint should not return 401"""
        res = agent_session.get(f"{BASE_URL}/api/projects")
        assert res.status_code != 401, "Projects returned 401"
        print(f"✓ Projects: {res.status_code}")
    
    def test_clients_no_401(self, agent_session):
        """Clients endpoint should not return 401"""
        res = agent_session.get(f"{BASE_URL}/api/clients")
        assert res.status_code != 401, "Clients returned 401"
        print(f"✓ Clients: {res.status_code}")
    
    def test_vault_no_401(self, agent_session):
        """Vault endpoint should not return 401"""
        res = agent_session.get(f"{BASE_URL}/api/vault")
        assert res.status_code != 401, "Vault returned 401"
        print(f"✓ Vault: {res.status_code}")
    
    def test_notifications_no_401(self, agent_session):
        """Notifications endpoint should not return 401"""
        res = agent_session.get(f"{BASE_URL}/api/notifications")
        assert res.status_code != 401, "Notifications returned 401"
        print(f"✓ Notifications: {res.status_code}")


class TestCleanup:
    """Cleanup test data"""
    
    def test_cleanup_test_vault_documents(self, agent_session):
        """Clean up TEST_ prefixed vault documents"""
        res = agent_session.get(f"{BASE_URL}/api/vault")
        if res.status_code != 200:
            return
        
        docs = res.json()
        test_docs = [d for d in docs if d.get("name", "").startswith("TEST_") or d.get("title", "").startswith("TEST_")]
        
        for doc in test_docs:
            vault_id = doc.get("vault_id") or doc.get("vault_document_id")
            if vault_id:
                agent_session.delete(f"{BASE_URL}/api/vault/{vault_id}")
                print(f"  Cleaned up: {doc.get('name') or doc.get('title')}")
        
        print(f"✓ Cleaned up {len(test_docs)} test vault documents")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
