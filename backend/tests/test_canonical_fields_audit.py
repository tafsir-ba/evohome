"""
Test Suite: Canonical Field Audit - Iteration 4
Tests that backend APIs return canonical field names without legacy aliases.

Key validations:
1. GET /api/documents - returns 'amount' and 'type' (NOT total_amount, document_type)
2. GET /api/projects/{id}/steps - returns step_id, title, order_index (NOT stage_id, name, order)
3. All other endpoints return expected canonical fields
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "demo.agent@upgradeflow.com"
TEST_PASSWORD = "demo123"


class TestAuthAndSession:
    """Authentication tests"""
    
    @pytest.fixture(scope="class")
    def session(self):
        """Create authenticated session"""
        s = requests.Session()
        s.headers.update({"Content-Type": "application/json"})
        return s
    
    @pytest.fixture(scope="class")
    def auth_session(self, session):
        """Login and return authenticated session"""
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "user_id" in data
        assert "token" in data
        return session
    
    def test_login_returns_canonical_fields(self, session):
        """Test POST /api/auth/login returns canonical user fields"""
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        
        # Canonical fields
        assert "user_id" in data
        assert "email" in data
        assert "name" in data
        assert "role" in data
        assert "token" in data
        
        # Verify values
        assert data["email"] == TEST_EMAIL
        assert data["role"] == "agent"


class TestDocumentsCanonicalFields:
    """Test documents endpoint returns canonical fields without legacy aliases"""
    
    @pytest.fixture(scope="class")
    def auth_session(self):
        """Create authenticated session"""
        s = requests.Session()
        s.headers.update({"Content-Type": "application/json"})
        response = s.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200
        return s
    
    def test_documents_list_canonical_fields(self, auth_session):
        """GET /api/documents should return canonical fields only"""
        response = auth_session.get(f"{BASE_URL}/api/documents")
        assert response.status_code == 200
        
        docs = response.json()
        assert isinstance(docs, list)
        
        if len(docs) > 0:
            doc = docs[0]
            
            # MUST have canonical fields
            assert "document_id" in doc, "Missing canonical field: document_id"
            assert "type" in doc, "Missing canonical field: type"
            assert "amount" in doc, "Missing canonical field: amount"
            assert "status" in doc, "Missing canonical field: status"
            
            # MUST NOT have legacy aliases
            assert "total_amount" not in doc, "Legacy field 'total_amount' should be removed"
            assert "document_type" not in doc, "Legacy field 'document_type' should be removed"
            assert "quote_id" not in doc, "Legacy field 'quote_id' should be removed"
            assert "invoice_id" not in doc, "Legacy field 'invoice_id' should be removed"
            
            # Verify type is valid
            assert doc["type"] in ["quote", "invoice"], f"Invalid type: {doc['type']}"
            
            # Verify amount is numeric
            assert isinstance(doc["amount"], (int, float)), f"Amount should be numeric: {doc['amount']}"
            
            print(f"✓ Document {doc['document_id']} has canonical fields: type={doc['type']}, amount={doc['amount']}")
    
    def test_documents_quotes_filter(self, auth_session):
        """GET /api/documents?doc_type=quote returns only quotes with canonical fields"""
        response = auth_session.get(f"{BASE_URL}/api/documents?doc_type=quote")
        assert response.status_code == 200
        
        docs = response.json()
        for doc in docs:
            assert doc["type"] == "quote", f"Expected quote, got {doc['type']}"
            assert "amount" in doc
            assert "total_amount" not in doc
    
    def test_documents_invoices_filter(self, auth_session):
        """GET /api/documents?doc_type=invoice returns only invoices with canonical fields"""
        response = auth_session.get(f"{BASE_URL}/api/documents?doc_type=invoice")
        assert response.status_code == 200
        
        docs = response.json()
        for doc in docs:
            assert doc["type"] == "invoice", f"Expected invoice, got {doc['type']}"
            assert "amount" in doc
            assert "total_amount" not in doc


class TestProjectStepsCanonicalFields:
    """Test project steps endpoint returns canonical fields"""
    
    @pytest.fixture(scope="class")
    def auth_session(self):
        """Create authenticated session"""
        s = requests.Session()
        s.headers.update({"Content-Type": "application/json"})
        response = s.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200
        return s
    
    @pytest.fixture(scope="class")
    def project_id(self, auth_session):
        """Get first project ID"""
        response = auth_session.get(f"{BASE_URL}/api/projects")
        assert response.status_code == 200
        projects = response.json()
        if len(projects) > 0:
            return projects[0]["project_id"]
        pytest.skip("No projects available for testing")
    
    def test_project_steps_canonical_fields(self, auth_session, project_id):
        """GET /api/projects/{id}/steps returns canonical step fields"""
        response = auth_session.get(f"{BASE_URL}/api/projects/{project_id}/steps")
        assert response.status_code == 200
        
        data = response.json()
        assert "project" in data
        assert "steps" in data
        
        steps = data["steps"]
        if len(steps) > 0:
            step = steps[0]
            
            # MUST have canonical fields
            assert "step_id" in step, "Missing canonical field: step_id"
            assert "title" in step, "Missing canonical field: title"
            assert "order_index" in step, "Missing canonical field: order_index"
            assert "status" in step, "Missing canonical field: status"
            
            # MUST NOT have legacy aliases
            assert "stage_id" not in step, "Legacy field 'stage_id' should be removed"
            assert "name" not in step, "Legacy field 'name' should be removed (use 'title')"
            assert "order" not in step, "Legacy field 'order' should be removed (use 'order_index')"
            
            # Verify status is canonical (not 'upcoming')
            valid_statuses = ["pending", "in_progress", "completed", "delayed"]
            assert step["status"] in valid_statuses, f"Invalid status: {step['status']} (should be one of {valid_statuses})"
            
            print(f"✓ Step {step['step_id']} has canonical fields: title={step['title']}, status={step['status']}")
    
    def test_project_timeline_full_canonical_fields(self, auth_session, project_id):
        """GET /api/projects/{id}/timeline/full returns canonical step fields"""
        response = auth_session.get(f"{BASE_URL}/api/projects/{project_id}/timeline/full")
        assert response.status_code == 200
        
        data = response.json()
        assert "project" in data
        assert "steps" in data
        
        steps = data["steps"]
        for step in steps:
            # Canonical fields only
            assert "step_id" in step
            assert "title" in step
            assert "order_index" in step
            
            # No legacy fields
            assert "stage_id" not in step
            assert "name" not in step


class TestDashboardCanonicalFields:
    """Test dashboard endpoint returns canonical fields"""
    
    @pytest.fixture(scope="class")
    def auth_session(self):
        """Create authenticated session"""
        s = requests.Session()
        s.headers.update({"Content-Type": "application/json"})
        response = s.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200
        return s
    
    def test_agent_dashboard_canonical_fields(self, auth_session):
        """GET /api/agent/dashboard returns canonical fields"""
        response = auth_session.get(f"{BASE_URL}/api/agent/dashboard")
        assert response.status_code == 200
        
        data = response.json()
        assert "projects" in data
        assert "recent_work" in data
        
        # Check recent_work items use canonical 'type' field
        for item in data.get("recent_work", []):
            assert "type" in item
            # Should be 'document', 'client', etc. - not 'document_type'
            assert "document_type" not in item


class TestOtherEndpointsCanonicalFields:
    """Test other endpoints return expected fields"""
    
    @pytest.fixture(scope="class")
    def auth_session(self):
        """Create authenticated session"""
        s = requests.Session()
        s.headers.update({"Content-Type": "application/json"})
        response = s.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200
        return s
    
    def test_projects_list(self, auth_session):
        """GET /api/projects returns project list"""
        response = auth_session.get(f"{BASE_URL}/api/projects")
        assert response.status_code == 200
        
        projects = response.json()
        assert isinstance(projects, list)
        
        if len(projects) > 0:
            project = projects[0]
            assert "project_id" in project
            assert "name" in project
    
    def test_clients_list(self, auth_session):
        """GET /api/clients returns client list"""
        response = auth_session.get(f"{BASE_URL}/api/clients")
        assert response.status_code == 200
        
        clients = response.json()
        assert isinstance(clients, list)
        
        if len(clients) > 0:
            client = clients[0]
            assert "client_id" in client
            assert "name" in client
    
    def test_notifications_list(self, auth_session):
        """GET /api/notifications returns notifications"""
        response = auth_session.get(f"{BASE_URL}/api/notifications")
        assert response.status_code == 200
        
        data = response.json()
        # Can be list or dict with notifications key
        if isinstance(data, dict):
            assert "notifications" in data or "items" in data
    
    def test_billing_status(self, auth_session):
        """GET /api/billing/status returns subscription status"""
        response = auth_session.get(f"{BASE_URL}/api/billing/status")
        assert response.status_code == 200
        
        data = response.json()
        # Billing status returns various fields - just verify it's a dict with expected structure
        assert isinstance(data, dict)
        # Should have some billing-related fields
        assert any(key in data for key in ["plan", "subscription", "status", "can_create_property", "current_period_end"])
    
    def test_analytics(self, auth_session):
        """GET /api/analytics returns analytics data"""
        response = auth_session.get(f"{BASE_URL}/api/analytics")
        assert response.status_code == 200


class TestHealthAndBasicEndpoints:
    """Test basic health and root endpoints"""
    
    def test_health_endpoint(self):
        """GET /api/health returns 200"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
    
    def test_root_endpoint(self):
        """GET /api/ returns 200"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
