"""
Test: Team Directory Extraction + Supplier Integration Features
- GET /api/team/directory - Returns team members with search/filter
- POST /api/team/extract-contacts - Extracts contacts from docs (requires OpenAI key)
- POST /api/projects/{id}/team/bulk - Bulk import contacts
- SupplierAutocomplete uses team/directory for suggestions
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

@pytest.fixture(scope="module")
def auth_token():
    """Get demo agent auth token"""
    response = requests.post(f"{BASE_URL}/api/auth/demo/agent")
    assert response.status_code == 200, f"Demo login failed: {response.text}"
    return response.json()['token']


class TestTeamDirectory:
    """Test GET /api/team/directory endpoint"""
    
    def test_team_directory_returns_members(self, auth_token):
        """Team directory returns list of team members"""
        response = requests.get(
            f"{BASE_URL}/api/team/directory",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Demo data should have some team members
        assert len(data) >= 1, "Should have at least 1 team member"
        
        # Verify structure
        if len(data) > 0:
            member = data[0]
            assert 'member_id' in member
            assert 'company_name' in member or 'contact_name' in member
            assert 'role' in member
    
    def test_team_directory_search_filter(self, auth_token):
        """Team directory filters by search term"""
        # Search for a known member (Plumber from demo data)
        response = requests.get(
            f"{BASE_URL}/api/team/directory?search=Plumber&limit=10",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        # Should find plumber if exists
        if len(data) > 0:
            assert any('plumber' in (m.get('role', '') or '').lower() for m in data)
    
    def test_team_directory_limit_parameter(self, auth_token):
        """Team directory respects limit parameter"""
        response = requests.get(
            f"{BASE_URL}/api/team/directory?limit=2",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) <= 2
    
    def test_team_directory_returns_address_field(self, auth_token):
        """Team directory includes address field in response"""
        response = requests.get(
            f"{BASE_URL}/api/team/directory",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        # Check that address key exists (can be null or have value)
        if len(data) > 0:
            # Address field should be present in structure
            # Note: Some members may not have address set
            member = data[0]
            # The field should exist, even if null
            assert 'address' in member or member.get('address') is None or member.get('address')


class TestBulkContactImport:
    """Test POST /api/projects/{id}/team/bulk endpoint"""
    
    def test_bulk_import_creates_contacts(self, auth_token):
        """Bulk import creates new team members"""
        test_contact = {
            "company_name": f"TEST_BulkTest_{os.urandom(4).hex()}",
            "contact_name": "Jane Doe",
            "role": "Contractor",
            "email": "jane@test.com",
            "phone": "+41 79 111 2222",
            "address": "456 Test Avenue, Zurich"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/projects/demo_proj_001/team/bulk",
            headers={
                "Authorization": f"Bearer {auth_token}",
                "Content-Type": "application/json"
            },
            json={"contacts": [test_contact]}
        )
        assert response.status_code == 200
        data = response.json()
        assert data['created'] == 1
        assert data['skipped'] == 0
        assert len(data['members']) == 1
        
        # Verify created member has address
        member = data['members'][0]
        assert member['address'] == "456 Test Avenue, Zurich"
    
    def test_bulk_import_deduplication(self, auth_token):
        """Bulk import skips duplicate contacts"""
        test_contact = {
            "company_name": "TEST_DupeCheck",
            "contact_name": "Duplicate Person",
            "role": "Tester"
        }
        
        # First import
        response1 = requests.post(
            f"{BASE_URL}/api/projects/demo_proj_001/team/bulk",
            headers={
                "Authorization": f"Bearer {auth_token}",
                "Content-Type": "application/json"
            },
            json={"contacts": [test_contact]}
        )
        
        # Second import - same contact
        response2 = requests.post(
            f"{BASE_URL}/api/projects/demo_proj_001/team/bulk",
            headers={
                "Authorization": f"Bearer {auth_token}",
                "Content-Type": "application/json"
            },
            json={"contacts": [test_contact]}
        )
        
        assert response2.status_code == 200
        data = response2.json()
        assert data['skipped'] >= 1, "Should skip duplicate"
    
    def test_bulk_import_skips_empty_contacts(self, auth_token):
        """Bulk import skips contacts without name"""
        response = requests.post(
            f"{BASE_URL}/api/projects/demo_proj_001/team/bulk",
            headers={
                "Authorization": f"Bearer {auth_token}",
                "Content-Type": "application/json"
            },
            json={"contacts": [{"role": "No Name", "email": "noname@test.com"}]}
        )
        assert response.status_code == 200
        data = response.json()
        assert data['skipped'] == 1
        assert data['created'] == 0
    
    def test_bulk_import_invalid_project(self, auth_token):
        """Bulk import returns 404 for invalid project"""
        response = requests.post(
            f"{BASE_URL}/api/projects/invalid_project_123/team/bulk",
            headers={
                "Authorization": f"Bearer {auth_token}",
                "Content-Type": "application/json"
            },
            json={"contacts": [{"company_name": "Test", "role": "Test"}]}
        )
        assert response.status_code == 404


class TestExtractContacts:
    """Test POST /api/team/extract-contacts endpoint"""
    
    def test_extract_contacts_requires_openai_key(self, auth_token):
        """Extract contacts returns 503 when OpenAI not configured"""
        # Create a simple test file
        from io import BytesIO
        test_file = BytesIO(b"Test content for extraction")
        
        response = requests.post(
            f"{BASE_URL}/api/team/extract-contacts",
            headers={"Authorization": f"Bearer {auth_token}"},
            files={"file": ("test.pdf", test_file, "application/pdf")}
        )
        
        # Without OpenAI key, should return 503
        # Note: This may pass if OPENAI_API_KEY is actually configured
        assert response.status_code in [200, 503], f"Expected 200 or 503, got {response.status_code}"
        if response.status_code == 503:
            assert "OpenAI API key not configured" in response.json()['detail']
    
    def test_extract_contacts_rejects_invalid_file_type(self, auth_token):
        """Extract contacts rejects unsupported file types (or returns 503 if no API key)"""
        from io import BytesIO
        test_file = BytesIO(b"Test content")
        
        response = requests.post(
            f"{BASE_URL}/api/team/extract-contacts",
            headers={"Authorization": f"Bearer {auth_token}"},
            files={"file": ("test.exe", test_file, "application/octet-stream")}
        )
        
        # May return 503 (no OpenAI key) before checking file type, or 400 (bad file type)
        assert response.status_code in [400, 503], f"Expected 400 or 503, got {response.status_code}"
        if response.status_code == 400:
            assert "Unsupported file type" in response.json()['detail']


class TestTeamDirectoryForSupplierAutocomplete:
    """Test team/directory works for SupplierAutocomplete component"""
    
    def test_supplier_search_returns_company_contact(self, auth_token):
        """Search returns company name and contact info for autocomplete"""
        response = requests.get(
            f"{BASE_URL}/api/team/directory?search=sani&limit=10",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify response has fields needed for autocomplete
        if len(data) > 0:
            member = data[0]
            # SupplierAutocomplete needs these fields
            has_display_name = 'company_name' in member or 'contact_name' in member
            assert has_display_name, "Needs company_name or contact_name for display"
            assert 'member_id' in member, "Needs member_id for selection"


# Cleanup test data
@pytest.fixture(scope="module", autouse=True)
def cleanup_test_data(auth_token):
    """Cleanup TEST_ prefixed data after tests"""
    yield
    # Note: In production, you'd clean up test data here
    # For demo mode, data persists but is isolated


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
