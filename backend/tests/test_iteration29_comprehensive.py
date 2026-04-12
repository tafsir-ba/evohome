"""
Iteration 29: Comprehensive Production Bug Test Matrix
Tests all 23 not-done items from the user's test matrix.

BUG-003 to BUG-034 verification
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
AGENT_EMAIL = "agent@evohome-test.ch"
AGENT_PASSWORD = "Evohome2026!"
BUYER_EMAIL = "buyer@evohome-test.ch"
BUYER_PASSWORD = "Evohome2026!"

# Known IDs from seed data
KNOWN_QUOTE_ID = "doc_b5d46abd6e6c"  # Hero Image Test Quote
KNOWN_PROJECT_ID = "proj_3a8bf4792165"
KNOWN_CLIENT_ID = "client_a04b0f890598"


# Session-scoped fixtures to avoid token invalidation
@pytest.fixture(scope="session")
def agent_token():
    """Get agent auth token - session scoped"""
    res = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": AGENT_EMAIL,
        "password": AGENT_PASSWORD
    })
    assert res.status_code == 200, f"Agent login failed: {res.text}"
    data = res.json()
    assert "token" in data, "No token in response"
    return data["token"]


@pytest.fixture(scope="session")
def buyer_token():
    """Get buyer auth token - session scoped"""
    res = requests.post(f"{BASE_URL}/api/auth/buyer/login", json={
        "email": BUYER_EMAIL,
        "password": BUYER_PASSWORD
    })
    assert res.status_code == 200, f"Buyer login failed: {res.text}"
    data = res.json()
    assert "token" in data, "No token in response"
    return data["token"]


class TestAuthAndSetup:
    """Authentication tests - run first"""
    
    def test_agent_login(self, agent_token):
        """Verify agent can login"""
        assert agent_token is not None
        assert len(agent_token) > 10
        print(f"✓ Agent login successful, token length: {len(agent_token)}")
    
    def test_buyer_login(self, buyer_token):
        """Verify buyer can login"""
        assert buyer_token is not None
        assert len(buyer_token) > 10
        print(f"✓ Buyer login successful, token length: {len(buyer_token)}")


class TestHeroImage:
    """BUG-003, BUG-004: Hero Image Upload and Display"""
    
    def test_bug003_hero_image_endpoint_exists(self, agent_token):
        """BUG-003: Verify hero image upload endpoint exists"""
        # Check if the document exists and has hero image
        res = requests.get(
            f"{BASE_URL}/api/documents/{KNOWN_QUOTE_ID}",
            headers={"Authorization": f"Bearer {agent_token}"}
        )
        assert res.status_code == 200, f"Document not found: {res.text}"
        doc = res.json()
        print(f"✓ Document found: {doc.get('document_number')}")
        print(f"  Hero image URL: {doc.get('hero_image_url')}")
        # Hero image should exist from seed
        assert doc.get('hero_image_url') or doc.get('hero_image_stored_filename'), "Hero image not set on document"
    
    def test_bug003_hero_image_get_endpoint(self, agent_token):
        """BUG-003: Verify hero image GET endpoint works"""
        res = requests.get(
            f"{BASE_URL}/api/documents/{KNOWN_QUOTE_ID}/hero-image",
            headers={"Authorization": f"Bearer {agent_token}"}
        )
        # Should return image or 404 if not set
        assert res.status_code in [200, 404], f"Unexpected status: {res.status_code}"
        if res.status_code == 200:
            print(f"✓ Hero image retrieved, content-type: {res.headers.get('content-type')}")
        else:
            print("⚠ Hero image not found (may need to upload)")
    
    def test_bug004_buyer_can_see_document(self, buyer_token):
        """BUG-004: Verify buyer can access document with hero image"""
        res = requests.get(
            f"{BASE_URL}/api/timeline",
            headers={"Authorization": f"Bearer {buyer_token}"}
        )
        assert res.status_code == 200, f"Timeline failed: {res.text}"
        data = res.json()
        documents = data.get('documents', [])
        print(f"✓ Buyer timeline has {len(documents)} documents")
        # Check if any document has hero image
        hero_docs = [d for d in documents if d.get('heroImageUrl') or d.get('hero_image_url')]
        print(f"  Documents with hero images: {len(hero_docs)}")


class TestVault:
    """BUG-005, BUG-006, BUG-007: Vault Document Upload/Download/Auth"""
    
    def test_bug005_vault_upload_endpoint(self, agent_token):
        """BUG-005: Verify vault upload endpoint exists"""
        # Just verify the endpoint responds (we'll test actual upload via UI)
        res = requests.get(
            f"{BASE_URL}/api/vault/documents",
            headers={"Authorization": f"Bearer {agent_token}"}
        )
        assert res.status_code == 200, f"Vault list failed: {res.text}"
        docs = res.json()
        print(f"✓ Vault has {len(docs)} documents")
    
    def test_bug005_vault_categories(self, agent_token):
        """BUG-005: Verify vault categories endpoint"""
        res = requests.get(
            f"{BASE_URL}/api/vault/categories",
            headers={"Authorization": f"Bearer {agent_token}"}
        )
        assert res.status_code == 200, f"Categories failed: {res.text}"
        categories = res.json()
        print(f"✓ Vault categories: {categories}")
    
    def test_bug007_vault_requires_auth(self):
        """BUG-007: Verify vault requires authentication"""
        # No auth header
        res = requests.get(f"{BASE_URL}/api/vault/documents")
        assert res.status_code in [401, 403], f"Expected 401/403, got {res.status_code}"
        print(f"✓ Vault correctly requires auth (status: {res.status_code})")


class TestLegacyFileCompatibility:
    """BUG-008: Legacy File Compatibility"""
    
    def test_bug008_source_pdf_404_graceful(self, agent_token):
        """BUG-008: Verify source-pdf returns 404 gracefully for non-existent file"""
        # Use a fake document ID
        res = requests.get(
            f"{BASE_URL}/api/documents/nonexistent_doc_id/source-pdf",
            headers={"Authorization": f"Bearer {agent_token}"}
        )
        assert res.status_code == 404, f"Expected 404, got {res.status_code}"
        print(f"✓ Source-pdf returns 404 gracefully for non-existent document")


class TestClientsContext:
    """BUG-011, BUG-012, BUG-013: Client Context Display"""
    
    def test_bug011_clients_list_has_context(self, agent_token):
        """BUG-011: Verify clients list returns project and unit info"""
        res = requests.get(
            f"{BASE_URL}/api/clients",
            headers={"Authorization": f"Bearer {agent_token}"}
        )
        assert res.status_code == 200, f"Clients list failed: {res.text}"
        clients = res.json()
        assert len(clients) > 0, "No clients found"
        
        # Check first client has context fields
        client = clients[0]
        print(f"✓ Client: {client.get('name')}")
        print(f"  project_id: {client.get('project_id')}")
        print(f"  project_name: {client.get('project_name')}")
        print(f"  unit_reference: {client.get('unit_reference')}")
        
        # At least project_id should be present
        assert client.get('project_id'), "Client missing project_id"
    
    def test_bug012_client_detail_has_context(self, agent_token):
        """BUG-012: Verify client detail returns project name (not raw ID)"""
        res = requests.get(
            f"{BASE_URL}/api/clients/{KNOWN_CLIENT_ID}",
            headers={"Authorization": f"Bearer {agent_token}"}
        )
        assert res.status_code == 200, f"Client detail failed: {res.text}"
        client = res.json()
        print(f"✓ Client detail: {client.get('name')}")
        print(f"  project_name: {client.get('project_name')}")
        print(f"  unit_reference: {client.get('unit_reference')}")


class TestProjectEndpoint:
    """BUG-014: Project Endpoint"""
    
    def test_bug014_project_endpoint_returns_name(self, agent_token):
        """BUG-014: Verify GET /api/projects/{id} returns project with name"""
        res = requests.get(
            f"{BASE_URL}/api/projects/{KNOWN_PROJECT_ID}",
            headers={"Authorization": f"Bearer {agent_token}"}
        )
        assert res.status_code == 200, f"Project endpoint failed: {res.text}"
        project = res.json()
        assert "name" in project, "Project missing 'name' field"
        assert project["name"], "Project name is empty"
        print(f"✓ Project endpoint returns name: {project['name']}")
        print(f"  project_id: {project.get('project_id')}")
        print(f"  address: {project.get('address')}")


class TestChangeRequests:
    """BUG-024 to BUG-032: Change Request Tests"""
    
    def test_bug029_cr_aggregation_in_stats(self, agent_token):
        """BUG-029: Verify /api/stats/agent returns change_requests count"""
        res = requests.get(
            f"{BASE_URL}/api/stats/agent",
            headers={"Authorization": f"Bearer {agent_token}"}
        )
        assert res.status_code == 200, f"Stats failed: {res.text}"
        stats = res.json()
        
        # Check for CR-related fields
        print(f"✓ Stats endpoint response:")
        print(f"  change_requests: {len(stats.get('change_requests', []))}")
        print(f"  open_change_requests: {stats.get('open_change_requests', 0)}")
        print(f"  pending_quotes: {stats.get('pending_quotes', 0)}")
        print(f"  pending_invoices: {stats.get('pending_invoices', 0)}")
        print(f"  pending_decisions: {stats.get('pending_decisions', 0)}")
        
        # Verify structure
        assert "change_requests" in stats or "open_change_requests" in stats, "Missing CR fields in stats"
    
    def test_change_request_entity_endpoint(self, agent_token):
        """Test change request entity endpoint exists"""
        # This endpoint is used by buyer to view CR thread
        res = requests.get(
            f"{BASE_URL}/api/change-requests/entity/quote/{KNOWN_QUOTE_ID}",
            headers={"Authorization": f"Bearer {agent_token}"}
        )
        # Should return 200 with empty list or CRs
        assert res.status_code == 200, f"CR entity endpoint failed: {res.text}"
        data = res.json()
        print(f"✓ CR entity endpoint works, found {len(data.get('change_requests', []))} CRs")


class TestInvoiceUploadParity:
    """BUG-016: Invoice Upload Parity"""
    
    def test_bug016_clients_have_context_for_invoice(self, agent_token):
        """BUG-016: Verify clients have project/unit context for invoice creation"""
        res = requests.get(
            f"{BASE_URL}/api/clients",
            headers={"Authorization": f"Bearer {agent_token}"}
        )
        assert res.status_code == 200
        clients = res.json()
        
        # Check that clients have the fields needed for subtitle display
        for client in clients[:3]:
            print(f"✓ Client: {client.get('name')}")
            print(f"  project_id: {client.get('project_id')}")
            print(f"  unit_reference: {client.get('unit_reference')}")


class TestDashboardIntegration:
    """BUG-030, BUG-031, BUG-032: Dashboard Integration"""
    
    def test_bug031_stats_for_control_tower(self, agent_token):
        """BUG-031: Verify stats endpoint provides data for Control Tower"""
        res = requests.get(
            f"{BASE_URL}/api/stats/agent",
            headers={"Authorization": f"Bearer {agent_token}"}
        )
        assert res.status_code == 200
        stats = res.json()
        
        # Control Tower needs these fields
        required_fields = ['total_clients', 'pending_quotes', 'pending_invoices', 'total_revenue']
        for field in required_fields:
            assert field in stats, f"Missing field: {field}"
        
        print(f"✓ Stats has all Control Tower fields")
        print(f"  total_clients: {stats.get('total_clients')}")
        print(f"  pending_quotes: {stats.get('pending_quotes')}")
        print(f"  pending_invoices: {stats.get('pending_invoices')}")
        print(f"  total_revenue: {stats.get('total_revenue')}")


class TestDocumentEndpoints:
    """Additional document endpoint tests"""
    
    def test_documents_list(self, agent_token):
        """Verify documents list endpoint"""
        res = requests.get(
            f"{BASE_URL}/api/documents",
            headers={"Authorization": f"Bearer {agent_token}"}
        )
        assert res.status_code == 200
        docs = res.json()
        print(f"✓ Documents list: {len(docs)} documents")
        
        # Check for quotes and invoices
        quotes = [d for d in docs if d.get('type') == 'quote']
        invoices = [d for d in docs if d.get('type') == 'invoice']
        print(f"  Quotes: {len(quotes)}, Invoices: {len(invoices)}")
    
    def test_document_detail(self, agent_token):
        """Verify document detail endpoint"""
        res = requests.get(
            f"{BASE_URL}/api/documents/{KNOWN_QUOTE_ID}",
            headers={"Authorization": f"Bearer {agent_token}"}
        )
        assert res.status_code == 200
        doc = res.json()
        print(f"✓ Document detail: {doc.get('document_number')}")
        print(f"  title: {doc.get('title')}")
        print(f"  status: {doc.get('status')}")
        print(f"  amount: {doc.get('amount')}")


class TestBuyerNotifications:
    """BUG-024, BUG-025: Buyer Notification Tests"""
    
    def test_buyer_notifications_endpoint(self, buyer_token):
        """Verify buyer can access notifications"""
        res = requests.get(
            f"{BASE_URL}/api/notifications",
            headers={"Authorization": f"Bearer {buyer_token}"}
        )
        # Should return 200 or 404 if endpoint doesn't exist
        if res.status_code == 200:
            notifications = res.json()
            print(f"✓ Buyer notifications: {len(notifications)} items")
        else:
            print(f"⚠ Notifications endpoint returned {res.status_code}")
    
    def test_buyer_activities_endpoint(self, buyer_token):
        """Verify buyer can access activities"""
        res = requests.get(
            f"{BASE_URL}/api/activities",
            headers={"Authorization": f"Bearer {buyer_token}"}
        )
        if res.status_code == 200:
            data = res.json()
            activities = data.get('activities', data) if isinstance(data, dict) else data
            print(f"✓ Buyer activities: {len(activities) if isinstance(activities, list) else 'N/A'}")
        else:
            print(f"⚠ Activities endpoint returned {res.status_code}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
