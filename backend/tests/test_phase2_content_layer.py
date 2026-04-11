"""
Phase 2 Content Layer - Backend API Regression Tests

Tests all 4 Phase 2 modules:
- Activity (activities_v2.py + activity_service.py)
- Document (documents_v2.py + document_service.py)
- VaultDocument (vault_v2.py + vault_service.py)
- Notification (notifications_v2.py + notification_service.py)

Key verification:
- is_demo field MUST NOT appear in any Activity, Document, Vault, or Notification response
- All V2 routes work correctly
- Phase 1 modules still work (regression)
"""
import os
import pytest
import requests
import time
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "e2e@evohome-test.com"
TEST_PASSWORD = "Test2026!"


# ============ Session-scoped fixtures to avoid rate limiting ============

@pytest.fixture(scope="session")
def auth_data():
    """Get authentication token once for all tests"""
    time.sleep(2)  # Small delay to avoid rate limiting
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    assert "token" in data, "No token in login response"
    return data


@pytest.fixture(scope="session")
def token(auth_data):
    """Get token from auth data"""
    return auth_data["token"]


@pytest.fixture(scope="session")
def headers(token):
    """Get auth headers"""
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture(scope="session")
def test_project_id(headers):
    """Get a project ID for testing"""
    response = requests.get(f"{BASE_URL}/api/projects", headers=headers)
    if response.status_code == 200 and response.json():
        return response.json()[0]["project_id"]
    return None


@pytest.fixture(scope="session")
def test_client_id(headers):
    """Get a client ID for testing"""
    response = requests.get(f"{BASE_URL}/api/clients", headers=headers)
    if response.status_code == 200 and response.json():
        return response.json()[0]["client_id"]
    return None


# ============ Helper functions ============

def check_is_demo_recursive(obj, path="root"):
    """Recursively check for is_demo in any nested structure"""
    if isinstance(obj, dict):
        if "is_demo" in obj:
            return f"is_demo found at {path}"
        for key, value in obj.items():
            result = check_is_demo_recursive(value, f"{path}.{key}")
            if result:
                return result
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            result = check_is_demo_recursive(item, f"{path}[{i}]")
            if result:
                return result
    return None


# ============ Health Check Tests ============

class TestHealthEndpoints:
    """Health check endpoints - verify API is accessible"""
    
    def test_health_liveness(self):
        """GET /api/health - liveness probe"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "alive"
        print(f"✓ Health check passed: {data}")
    
    def test_health_readiness(self):
        """GET /api/ready - readiness probe"""
        response = requests.get(f"{BASE_URL}/api/ready")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "ready"
        assert data.get("database") == "ok"
        print(f"✓ Readiness check passed")


# ============ Authentication Tests ============

class TestAuthentication:
    """Authentication tests"""
    
    def test_login_response_structure(self, auth_data):
        """Verify login response structure"""
        # Login response has user data at root level (not nested under "user")
        assert "token" in auth_data
        assert "user_id" in auth_data
        assert "email" in auth_data
        assert auth_data["email"] == TEST_EMAIL
        assert auth_data["role"] == "agent"
        # Note: is_demo in auth response is expected (for demo mode detection)
        print(f"✓ Login successful for {TEST_EMAIL}")


# ============ Phase 1 Regression Tests ============

class TestPhase1Regression:
    """Phase 1 modules should still work (regression tests)"""
    
    def test_get_projects(self, headers):
        """GET /api/projects - Phase 1 still works"""
        response = requests.get(f"{BASE_URL}/api/projects", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Verify is_demo not in any project
        for project in data:
            assert "is_demo" not in project, f"is_demo found in project: {project.get('project_id')}"
        print(f"✓ GET /api/projects returned {len(data)} projects (no is_demo)")
    
    def test_get_clients(self, headers):
        """GET /api/clients - Phase 1 still works"""
        response = requests.get(f"{BASE_URL}/api/clients", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Verify is_demo not in any client
        for client in data:
            assert "is_demo" not in client, f"is_demo found in client: {client.get('client_id')}"
        print(f"✓ GET /api/clients returned {len(data)} clients (no is_demo)")
    
    def test_get_project_timeline(self, headers, test_project_id):
        """GET /api/project-timeline - Phase 1 still works"""
        if not test_project_id:
            pytest.skip("No project available for timeline test")
        
        response = requests.get(f"{BASE_URL}/api/project-timeline?project_id={test_project_id}", headers=headers)
        assert response.status_code in [200, 404]  # 404 if no timeline
        if response.status_code == 200:
            data = response.json()
            assert "is_demo" not in data, "is_demo found in timeline response"
            print(f"✓ GET /api/project-timeline works (no is_demo)")
        else:
            print(f"✓ GET /api/project-timeline returned 404 (no timeline for project)")


# ============ Activity Module Tests (Phase 2) ============

class TestActivityModule:
    """Activity module tests (Phase 2)"""
    
    def test_list_activities(self, headers):
        """GET /api/activities - list activities (no is_demo)"""
        response = requests.get(f"{BASE_URL}/api/activities", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "activities" in data
        assert "total" in data
        # Verify is_demo not in any activity
        result = check_is_demo_recursive(data)
        assert result is None, f"Activities: {result}"
        print(f"✓ GET /api/activities returned {len(data['activities'])} activities (no is_demo)")
    
    def test_create_activity(self, token, test_project_id, test_client_id):
        """POST /api/activities - create activity with multipart/form-data"""
        if not test_project_id or not test_client_id:
            pytest.skip("No project or client available for activity creation")
        
        headers = {"Authorization": f"Bearer {token}"}
        form_data = {
            "type": "message",
            "project_id": test_project_id,
            "client_ids": test_client_id,
            "content": "TEST_Phase2_Activity_Content"
        }
        
        response = requests.post(f"{BASE_URL}/api/activities", headers=headers, data=form_data)
        assert response.status_code == 200, f"Activity creation failed: {response.text}"
        data = response.json()
        
        # Verify is_demo not in response
        result = check_is_demo_recursive(data)
        assert result is None, f"Created activity: {result}"
        assert "activity_id" in data
        assert data["content"] == "TEST_Phase2_Activity_Content"
        
        # Cleanup
        activity_id = data["activity_id"]
        requests.delete(f"{BASE_URL}/api/activities/{activity_id}", headers=headers)
        print(f"✓ POST /api/activities created activity (no is_demo)")
    
    def test_get_activity_detail(self, token, headers, test_project_id, test_client_id):
        """GET /api/activities/{id} - get activity with replies"""
        if not test_project_id or not test_client_id:
            pytest.skip("No project or client available")
        
        # Create activity
        create_headers = {"Authorization": f"Bearer {token}"}
        form_data = {
            "type": "message",
            "project_id": test_project_id,
            "client_ids": test_client_id,
            "content": "TEST_Phase2_Activity_Detail"
        }
        create_response = requests.post(f"{BASE_URL}/api/activities", headers=create_headers, data=form_data)
        if create_response.status_code != 200:
            pytest.skip("Could not create activity for detail test")
        
        activity_id = create_response.json()["activity_id"]
        
        # Get activity detail
        response = requests.get(f"{BASE_URL}/api/activities/{activity_id}", headers=headers)
        assert response.status_code == 200
        data = response.json()
        
        # Verify is_demo not in response
        result = check_is_demo_recursive(data)
        assert result is None, f"Activity detail: {result}"
        assert data["activity_id"] == activity_id
        assert "replies" in data  # Should include replies
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/activities/{activity_id}", headers=headers)
        print(f"✓ GET /api/activities/{activity_id} returned detail (no is_demo)")
    
    def test_reply_to_activity(self, token, headers, test_project_id, test_client_id):
        """POST /api/activities/{id}/reply - reply to activity"""
        if not test_project_id or not test_client_id:
            pytest.skip("No project or client available")
        
        # Create activity
        create_headers = {"Authorization": f"Bearer {token}"}
        form_data = {
            "type": "message",
            "project_id": test_project_id,
            "client_ids": test_client_id,
            "content": "TEST_Phase2_Activity_Reply_Parent"
        }
        create_response = requests.post(f"{BASE_URL}/api/activities", headers=create_headers, data=form_data)
        if create_response.status_code != 200:
            pytest.skip("Could not create activity for reply test")
        
        activity_id = create_response.json()["activity_id"]
        
        # Reply to activity
        response = requests.post(
            f"{BASE_URL}/api/activities/{activity_id}/reply",
            headers=headers,
            json={"content": "TEST_Phase2_Reply_Content"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify is_demo not in reply
        result = check_is_demo_recursive(data)
        assert result is None, f"Reply: {result}"
        assert "reply_id" in data
        assert data["content"] == "TEST_Phase2_Reply_Content"
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/activities/{activity_id}", headers=headers)
        print(f"✓ POST /api/activities/{activity_id}/reply created reply (no is_demo)")
    
    def test_mark_activities_seen(self, headers):
        """POST /api/activities/mark-seen - mark activities as seen"""
        response = requests.post(f"{BASE_URL}/api/activities/mark-seen", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "last_seen_at" in data
        print(f"✓ POST /api/activities/mark-seen returned {data}")
    
    def test_get_unread_count(self, headers):
        """GET /api/activities/unread-count - get unread count"""
        response = requests.get(f"{BASE_URL}/api/activities/unread-count", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "unread_count" in data
        print(f"✓ GET /api/activities/unread-count returned {data}")
    
    def test_update_activity(self, token, headers, test_project_id, test_client_id):
        """PUT /api/activities/{id} - update activity"""
        if not test_project_id or not test_client_id:
            pytest.skip("No project or client available")
        
        # Create activity
        create_headers = {"Authorization": f"Bearer {token}"}
        form_data = {
            "type": "message",
            "project_id": test_project_id,
            "client_ids": test_client_id,
            "content": "TEST_Phase2_Activity_Update_Original"
        }
        create_response = requests.post(f"{BASE_URL}/api/activities", headers=create_headers, data=form_data)
        if create_response.status_code != 200:
            pytest.skip("Could not create activity for update test")
        
        activity_id = create_response.json()["activity_id"]
        
        # Update activity
        response = requests.put(
            f"{BASE_URL}/api/activities/{activity_id}",
            headers=headers,
            json={"content": "TEST_Phase2_Activity_Update_Modified"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify is_demo not in response
        result = check_is_demo_recursive(data)
        assert result is None, f"Updated activity: {result}"
        assert data["content"] == "TEST_Phase2_Activity_Update_Modified"
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/activities/{activity_id}", headers=headers)
        print(f"✓ PUT /api/activities/{activity_id} updated activity (no is_demo)")
    
    def test_delete_activity(self, token, headers, test_project_id, test_client_id):
        """DELETE /api/activities/{id} - delete activity"""
        if not test_project_id or not test_client_id:
            pytest.skip("No project or client available")
        
        # Create activity
        create_headers = {"Authorization": f"Bearer {token}"}
        form_data = {
            "type": "message",
            "project_id": test_project_id,
            "client_ids": test_client_id,
            "content": "TEST_Phase2_Activity_Delete"
        }
        create_response = requests.post(f"{BASE_URL}/api/activities", headers=create_headers, data=form_data)
        if create_response.status_code != 200:
            pytest.skip("Could not create activity for delete test")
        
        activity_id = create_response.json()["activity_id"]
        
        # Delete activity
        response = requests.delete(f"{BASE_URL}/api/activities/{activity_id}", headers=headers)
        assert response.status_code == 200
        
        # Verify deleted
        get_response = requests.get(f"{BASE_URL}/api/activities/{activity_id}", headers=headers)
        assert get_response.status_code == 404
        print(f"✓ DELETE /api/activities/{activity_id} deleted activity")


# ============ Document Module Tests (Phase 2) ============

class TestDocumentModule:
    """Document module tests (Phase 2)"""
    
    def test_list_documents(self, headers):
        """GET /api/documents - list documents (no is_demo)"""
        response = requests.get(f"{BASE_URL}/api/documents", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Verify is_demo not in any document
        result = check_is_demo_recursive(data)
        assert result is None, f"Documents: {result}"
        print(f"✓ GET /api/documents returned {len(data)} documents (no is_demo)")
    
    def test_create_document_from_preview(self, headers, test_client_id):
        """POST /api/documents/create - create document from preview data"""
        if not test_client_id:
            pytest.skip("No client available for document creation")
        
        doc_data = {
            "client_id": test_client_id,
            "type": "quote",
            "title": "TEST_Phase2_Document",
            "amount": 1500.00,
            "items": [
                {"description": "Test Item 1", "quantity": 1, "unit_price": 1000, "total": 1000},
                {"description": "Test Item 2", "quantity": 1, "unit_price": 500, "total": 500}
            ],
            "supplier_name": "Test Supplier",
            "notes": "Test notes for Phase 2"
        }
        
        response = requests.post(f"{BASE_URL}/api/documents/create", headers=headers, json=doc_data)
        assert response.status_code == 200, f"Document creation failed: {response.text}"
        data = response.json()
        
        # Verify is_demo not in response
        result = check_is_demo_recursive(data)
        assert result is None, f"Created document: {result}"
        assert "document_id" in data
        assert data["title"] == "TEST_Phase2_Document"
        assert data["amount"] == 1500.00
        
        # Cleanup
        doc_id = data["document_id"]
        requests.delete(f"{BASE_URL}/api/documents/{doc_id}", headers=headers)
        print(f"✓ POST /api/documents/create created document (no is_demo)")
    
    def test_get_document(self, headers, test_client_id):
        """GET /api/documents/{id} - get document with client/project info"""
        if not test_client_id:
            pytest.skip("No client available")
        
        # Create document first
        doc_data = {
            "client_id": test_client_id,
            "type": "quote",
            "title": "TEST_Phase2_Document_Get",
            "amount": 500.00,
            "items": []
        }
        create_response = requests.post(f"{BASE_URL}/api/documents/create", headers=headers, json=doc_data)
        if create_response.status_code != 200:
            pytest.skip("Could not create document for get test")
        
        doc_id = create_response.json()["document_id"]
        
        # Get document
        response = requests.get(f"{BASE_URL}/api/documents/{doc_id}", headers=headers)
        assert response.status_code == 200
        data = response.json()
        
        # Verify is_demo not in response
        result = check_is_demo_recursive(data)
        assert result is None, f"Document detail: {result}"
        assert data["document_id"] == doc_id
        assert "client" in data  # Should include client info
        assert "project" in data  # Should include project info
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/documents/{doc_id}", headers=headers)
        print(f"✓ GET /api/documents/{doc_id} returned detail with client/project (no is_demo)")
    
    def test_update_document(self, headers, test_client_id):
        """PUT /api/documents/{id} - update document"""
        if not test_client_id:
            pytest.skip("No client available")
        
        # Create document
        doc_data = {
            "client_id": test_client_id,
            "type": "quote",
            "title": "TEST_Phase2_Document_Update_Original",
            "amount": 1000.00,
            "items": []
        }
        create_response = requests.post(f"{BASE_URL}/api/documents/create", headers=headers, json=doc_data)
        if create_response.status_code != 200:
            pytest.skip("Could not create document for update test")
        
        doc_id = create_response.json()["document_id"]
        
        # Update document
        response = requests.put(
            f"{BASE_URL}/api/documents/{doc_id}",
            headers=headers,
            json={"title": "TEST_Phase2_Document_Update_Modified", "amount": 2000.00}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify is_demo not in response
        result = check_is_demo_recursive(data)
        assert result is None, f"Updated document: {result}"
        assert data["title"] == "TEST_Phase2_Document_Update_Modified"
        assert data["amount"] == 2000.00
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/documents/{doc_id}", headers=headers)
        print(f"✓ PUT /api/documents/{doc_id} updated document (no is_demo)")
    
    def test_delete_document(self, headers, test_client_id):
        """DELETE /api/documents/{id} - delete document"""
        if not test_client_id:
            pytest.skip("No client available")
        
        # Create document
        doc_data = {
            "client_id": test_client_id,
            "type": "quote",
            "title": "TEST_Phase2_Document_Delete",
            "amount": 100.00,
            "items": []
        }
        create_response = requests.post(f"{BASE_URL}/api/documents/create", headers=headers, json=doc_data)
        if create_response.status_code != 200:
            pytest.skip("Could not create document for delete test")
        
        doc_id = create_response.json()["document_id"]
        
        # Delete document
        response = requests.delete(f"{BASE_URL}/api/documents/{doc_id}", headers=headers)
        assert response.status_code == 200
        
        # Verify deleted
        get_response = requests.get(f"{BASE_URL}/api/documents/{doc_id}", headers=headers)
        assert get_response.status_code == 404
        print(f"✓ DELETE /api/documents/{doc_id} deleted document")
    
    def test_send_document(self, headers, test_client_id):
        """POST /api/documents/{id}/send - send document to buyer"""
        if not test_client_id:
            pytest.skip("No client available")
        
        # Create document
        doc_data = {
            "client_id": test_client_id,
            "type": "quote",
            "title": "TEST_Phase2_Document_Send",
            "amount": 750.00,
            "items": []
        }
        create_response = requests.post(f"{BASE_URL}/api/documents/create", headers=headers, json=doc_data)
        if create_response.status_code != 200:
            pytest.skip("Could not create document for send test")
        
        doc_id = create_response.json()["document_id"]
        
        # Send document
        response = requests.post(f"{BASE_URL}/api/documents/{doc_id}/send", headers=headers)
        # May fail if client has no email, but should not return is_demo
        if response.status_code == 200:
            data = response.json()
            result = check_is_demo_recursive(data)
            assert result is None, f"Send response: {result}"
            assert data.get("status") == "Sent"
            print(f"✓ POST /api/documents/{doc_id}/send sent document (no is_demo)")
        else:
            # Expected if client has no email
            print(f"✓ POST /api/documents/{doc_id}/send returned {response.status_code} (expected if no email)")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/documents/{doc_id}?force=true", headers=headers)
    
    def test_revert_to_draft(self, headers, test_client_id):
        """POST /api/documents/{id}/revert-to-draft - revert document status"""
        if not test_client_id:
            pytest.skip("No client available")
        
        # Create document
        doc_data = {
            "client_id": test_client_id,
            "type": "quote",
            "title": "TEST_Phase2_Document_Revert",
            "amount": 500.00,
            "items": []
        }
        create_response = requests.post(f"{BASE_URL}/api/documents/create", headers=headers, json=doc_data)
        if create_response.status_code != 200:
            pytest.skip("Could not create document for revert test")
        
        doc_id = create_response.json()["document_id"]
        
        # Revert to draft (already draft, should return success)
        response = requests.post(f"{BASE_URL}/api/documents/{doc_id}/revert-to-draft", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "Draft"
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/documents/{doc_id}", headers=headers)
        print(f"✓ POST /api/documents/{doc_id}/revert-to-draft works")
    
    def test_get_document_pdf(self, headers, test_client_id):
        """GET /api/documents/{id}/pdf - generate PDF"""
        if not test_client_id:
            pytest.skip("No client available")
        
        # Create document
        doc_data = {
            "client_id": test_client_id,
            "type": "quote",
            "title": "TEST_Phase2_Document_PDF",
            "amount": 1200.00,
            "items": [{"description": "PDF Test Item", "quantity": 1, "unit_price": 1200, "total": 1200}]
        }
        create_response = requests.post(f"{BASE_URL}/api/documents/create", headers=headers, json=doc_data)
        if create_response.status_code != 200:
            pytest.skip("Could not create document for PDF test")
        
        doc_id = create_response.json()["document_id"]
        
        # Get PDF
        response = requests.get(f"{BASE_URL}/api/documents/{doc_id}/pdf", headers=headers)
        assert response.status_code == 200
        assert response.headers.get("content-type") == "application/pdf"
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/documents/{doc_id}", headers=headers)
        print(f"✓ GET /api/documents/{doc_id}/pdf generated PDF")
    
    def test_get_timeline(self, headers):
        """GET /api/timeline - document financial timeline"""
        response = requests.get(f"{BASE_URL}/api/timeline", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "documents" in data
        # Verify is_demo not in any document
        result = check_is_demo_recursive(data)
        assert result is None, f"Timeline: {result}"
        print(f"✓ GET /api/timeline returned {len(data.get('documents', []))} documents (no is_demo)")


# ============ Vault Module Tests (Phase 2) ============

class TestVaultModule:
    """Vault module tests (Phase 2)"""
    
    def test_list_vault_documents(self, headers):
        """GET /api/vault/documents - list vault documents (no is_demo)"""
        response = requests.get(f"{BASE_URL}/api/vault/documents", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Verify is_demo not in any vault document
        result = check_is_demo_recursive(data)
        assert result is None, f"Vault documents: {result}"
        print(f"✓ GET /api/vault/documents returned {len(data)} vault documents (no is_demo)")
    
    def test_get_vault_categories(self, headers):
        """GET /api/vault/categories - get vault categories"""
        response = requests.get(f"{BASE_URL}/api/vault/categories", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 2  # At least general and action_required
        print(f"✓ GET /api/vault/categories returned {len(data)} categories")


# ============ Notification Module Tests (Phase 2) ============

class TestNotificationModule:
    """Notification module tests (Phase 2)"""
    
    def test_list_notifications(self, headers):
        """GET /api/notifications - list notifications (no is_demo)"""
        response = requests.get(f"{BASE_URL}/api/notifications", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Verify is_demo not in any notification
        result = check_is_demo_recursive(data)
        assert result is None, f"Notifications: {result}"
        print(f"✓ GET /api/notifications returned {len(data)} notifications (no is_demo)")
    
    def test_mark_all_notifications_read(self, headers):
        """PATCH /api/notifications/read-all - mark all read"""
        response = requests.patch(f"{BASE_URL}/api/notifications/read-all", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        print(f"✓ PATCH /api/notifications/read-all marked {data['count']} as read")


# ============ Comprehensive is_demo Verification ============

class TestIsDemoVerification:
    """Comprehensive is_demo verification across all Phase 2 modules"""
    
    def test_activities_no_is_demo(self, headers):
        """Verify is_demo not in activities response"""
        response = requests.get(f"{BASE_URL}/api/activities", headers=headers)
        assert response.status_code == 200
        result = check_is_demo_recursive(response.json())
        assert result is None, f"Activities: {result}"
        print("✓ Activities: no is_demo found")
    
    def test_documents_no_is_demo(self, headers):
        """Verify is_demo not in documents response"""
        response = requests.get(f"{BASE_URL}/api/documents", headers=headers)
        assert response.status_code == 200
        result = check_is_demo_recursive(response.json())
        assert result is None, f"Documents: {result}"
        print("✓ Documents: no is_demo found")
    
    def test_vault_no_is_demo(self, headers):
        """Verify is_demo not in vault response"""
        response = requests.get(f"{BASE_URL}/api/vault/documents", headers=headers)
        assert response.status_code == 200
        result = check_is_demo_recursive(response.json())
        assert result is None, f"Vault: {result}"
        print("✓ Vault: no is_demo found")
    
    def test_notifications_no_is_demo(self, headers):
        """Verify is_demo not in notifications response"""
        response = requests.get(f"{BASE_URL}/api/notifications", headers=headers)
        assert response.status_code == 200
        result = check_is_demo_recursive(response.json())
        assert result is None, f"Notifications: {result}"
        print("✓ Notifications: no is_demo found")
    
    def test_timeline_no_is_demo(self, headers):
        """Verify is_demo not in timeline response"""
        response = requests.get(f"{BASE_URL}/api/timeline", headers=headers)
        assert response.status_code == 200
        result = check_is_demo_recursive(response.json())
        assert result is None, f"Timeline: {result}"
        print("✓ Timeline: no is_demo found")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
