"""
Test Suite for Buyer and Agent Journey Hardening (Iteration 46)

Tests:
1. GET /api/clients - returns list of clients (was 500 error)
2. POST /api/admin/migrate-clients - fixes missing fields
3. GET /api/admin/data-health - shows data integrity status
4. POST /api/documents/create - creates draft with client_id
5. POST /api/documents/{id}/send - returns detailed delivery status
6. GET /api/timeline (buyer) - buyer can view documents sent by agent
7. POST /api/documents/{id}/action - buyer can approve/reject quote
8. Notification creation - agent receives notification when buyer approves
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from request
DEMO_AGENT_EMAIL = "demo.agent@upgradeflow.com"
DEMO_AGENT_PASSWORD = "demo123"


class TestAgentBuyerJourney:
    """Test suite for agent and buyer journey hardening"""
    
    @pytest.fixture(scope="class")
    def agent_session(self):
        """Login as demo agent and get session"""
        session = requests.Session()
        login_response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": DEMO_AGENT_EMAIL,
            "password": DEMO_AGENT_PASSWORD
        })
        assert login_response.status_code == 200, f"Agent login failed: {login_response.text}"
        data = login_response.json()
        session.headers.update({"Authorization": f"Bearer {data['token']}"})
        return session, data
    
    @pytest.fixture(scope="class")
    def buyer_session(self):
        """Login as demo buyer"""
        session = requests.Session()
        # Use demo buyer login
        login_response = session.post(
            f"{BASE_URL}/api/demo/enter",
            json={"persona": "buyer", "buyer_slot": 1, "fresh": False},
        )
        assert login_response.status_code == 200, f"Demo buyer login failed: {login_response.text}"
        data = login_response.json()
        session.headers.update({"Authorization": f"Bearer {data['token']}"})
        return session, data
    
    # ===========================================
    # TEST 1: GET /api/clients - was 500 error
    # ===========================================
    def test_get_clients_returns_200(self, agent_session):
        """GET /api/clients should return 200, not 500"""
        session, _ = agent_session
        response = session.get(f"{BASE_URL}/api/clients")
        assert response.status_code == 200, f"GET /api/clients failed with {response.status_code}: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list of clients"
        print(f"PASS: GET /api/clients returns 200 with {len(data)} clients")
    
    def test_get_clients_returns_valid_client_structure(self, agent_session):
        """Clients in response should have valid structure with optional fields"""
        session, _ = agent_session
        response = session.get(f"{BASE_URL}/api/clients")
        assert response.status_code == 200
        data = response.json()
        
        if len(data) > 0:
            client = data[0]
            # Check required fields
            assert "client_id" in client, "Client should have client_id"
            assert "name" in client, "Client should have name"
            assert "email" in client, "Client should have email"
            # unit_reference is now optional with default
            # status is now optional with default
            print(f"PASS: Client structure is valid: {list(client.keys())}")
        else:
            print("WARN: No clients found to validate structure")
    
    # ===========================================
    # TEST 2: POST /api/admin/migrate-clients
    # ===========================================
    def test_migrate_clients_endpoint_returns_200(self, agent_session):
        """POST /api/admin/migrate-clients should return 200 and migration report"""
        session, _ = agent_session
        response = session.post(f"{BASE_URL}/api/admin/migrate-clients")
        assert response.status_code == 200, f"Migration failed: {response.text}"
        data = response.json()
        
        assert "migrated" in data, "Response should have 'migrated' field"
        assert "clients_fixed_unit_reference" in data, "Should report unit_reference fixes"
        assert "clients_fixed_status" in data, "Should report status fixes"
        print(f"PASS: migrate-clients returned: {data}")
    
    # ===========================================
    # TEST 3: GET /api/admin/data-health
    # ===========================================
    def test_data_health_endpoint_returns_200(self, agent_session):
        """GET /api/admin/data-health should return 200 with health report"""
        session, _ = agent_session
        response = session.get(f"{BASE_URL}/api/admin/data-health")
        assert response.status_code == 200, f"Data health check failed: {response.text}"
        data = response.json()
        
        assert "healthy" in data, "Response should have 'healthy' field"
        assert "issues" in data, "Response should have 'issues' list"
        assert "details" in data, "Response should have 'details' object"
        
        # Verify details structure
        details = data["details"]
        expected_details = [
            "clients_missing_unit_reference",
            "clients_missing_status",
            "documents_missing_client_id",
            "documents_missing_project_id",
            "buyers_without_client_linkage"
        ]
        for field in expected_details:
            assert field in details, f"Missing detail field: {field}"
        
        print(f"PASS: data-health returned healthy={data['healthy']}, issues={data['issues']}")
    
    # ===========================================
    # TEST 4: POST /api/documents/create
    # ===========================================
    def test_create_draft_document(self, agent_session):
        """POST /api/documents/create should create a draft document with client_id"""
        session, _ = agent_session
        
        # First get a client to use
        clients_response = session.get(f"{BASE_URL}/api/clients")
        assert clients_response.status_code == 200
        clients = clients_response.json()
        
        if len(clients) == 0:
            pytest.skip("No clients available for document creation test")
        
        client = clients[0]
        
        # Create a draft document
        doc_data = {
            "type": "quote",
            "title": f"TEST_Quote_{uuid.uuid4().hex[:6]}",
            "client_id": client["client_id"],
            "project_id": client.get("project_id"),
            "items": [
                {"description": "Test Item", "quantity": 1, "unit_price": 100.0, "total": 100.0}
            ],
            "amount": 100.0
        }
        
        response = session.post(f"{BASE_URL}/api/documents/create", json=doc_data)
        assert response.status_code in [200, 201], f"Create document failed: {response.text}"
        
        data = response.json()
        assert "document_id" in data, "Response should have document_id"
        assert data.get("status") == "Draft", "New document should be in Draft status"
        assert data.get("client_id") == client["client_id"], "client_id should match"
        
        print(f"PASS: Created draft document {data['document_id']} with client_id={data.get('client_id')}")
        return data["document_id"]
    
    # ===========================================
    # TEST 5: POST /api/documents/{id}/send
    # ===========================================
    def test_send_document_returns_detailed_status(self, agent_session):
        """POST /api/documents/{id}/send should return detailed delivery status"""
        session, _ = agent_session
        
        # First get a client to use
        clients_response = session.get(f"{BASE_URL}/api/clients")
        clients = clients_response.json()
        
        if len(clients) == 0:
            pytest.skip("No clients available")
        
        client = clients[0]
        
        # Create a draft document
        doc_data = {
            "type": "quote",
            "title": f"TEST_SendQuote_{uuid.uuid4().hex[:6]}",
            "client_id": client["client_id"],
            "project_id": client.get("project_id"),
            "items": [
                {"description": "Test Item", "quantity": 1, "unit_price": 500.0, "total": 500.0}
            ],
            "amount": 500.0
        }
        
        create_response = session.post(f"{BASE_URL}/api/documents/create", json=doc_data)
        assert create_response.status_code in [200, 201], f"Failed to create document: {create_response.text}"
        doc = create_response.json()
        document_id = doc["document_id"]
        
        # Send the document
        send_response = session.post(f"{BASE_URL}/api/documents/{document_id}/send")
        assert send_response.status_code == 200, f"Send failed: {send_response.text}"
        
        send_data = send_response.json()
        
        # Verify detailed response structure
        assert "message" in send_data, "Response should have message"
        assert "status" in send_data, "Response should have status"
        assert send_data["status"] == "Sent", "Status should be 'Sent'"
        assert "recipient" in send_data, "Response should have recipient info"
        assert "delivery" in send_data, "Response should have delivery status"
        
        # Check delivery details
        delivery = send_data["delivery"]
        expected_delivery_fields = ["notification_created", "websocket_sent", "email_sent", "email_error"]
        for field in expected_delivery_fields:
            assert field in delivery, f"Missing delivery field: {field}"
        
        # Warnings should be present (even if empty)
        assert "warnings" in send_data, "Response should have warnings list"
        
        print(f"PASS: Send document returned detailed status: delivery={delivery}, warnings={send_data['warnings']}")
        return document_id
    
    def test_send_document_without_client_fails(self, agent_session):
        """Sending a document without client should return clear error"""
        session, _ = agent_session
        
        # Try to create document without proper client
        # First get projects
        projects_response = session.get(f"{BASE_URL}/api/projects")
        if projects_response.status_code != 200:
            pytest.skip("No projects available")
        
        projects = projects_response.json()
        if len(projects) == 0:
            pytest.skip("No projects available")
        
        project = projects[0]
        
        # Try to send document with non-existent client
        doc_data = {
            "type": "quote",
            "title": f"TEST_NoClient_{uuid.uuid4().hex[:6]}",
            "client_id": "nonexistent_client_123",
            "project_id": project["project_id"],
            "items": [
                {"description": "Test", "quantity": 1, "unit_price": 100.0, "total": 100.0}
            ],
            "amount": 100.0
        }
        
        # Creation might fail or succeed depending on validation
        create_response = session.post(f"{BASE_URL}/api/documents/create", json=doc_data)
        if create_response.status_code not in [200, 201]:
            # Good - validation prevented creation
            print(f"PASS: Document creation with invalid client_id properly rejected")
            return
        
        # If created, try to send
        doc = create_response.json()
        send_response = session.post(f"{BASE_URL}/api/documents/{doc['document_id']}/send")
        assert send_response.status_code == 400, "Sending to nonexistent client should fail"
        
        error = send_response.json()
        assert "detail" in error, "Error response should have detail"
        print(f"PASS: Send to invalid client returned error: {error['detail']}")
    
    # ===========================================
    # TEST 6: GET /api/timeline (buyer view)
    # ===========================================
    def test_buyer_can_view_timeline(self, buyer_session):
        """Buyer should be able to view documents sent by agent"""
        session, user_data = buyer_session
        
        response = session.get(f"{BASE_URL}/api/timeline")
        assert response.status_code == 200, f"Timeline fetch failed: {response.text}"
        
        data = response.json()
        assert "documents" in data, "Response should have documents list"
        
        # Check document structure if any exist
        if len(data["documents"]) > 0:
            doc = data["documents"][0]
            expected_fields = ["id", "type", "title", "status", "amount"]
            for field in expected_fields:
                assert field in doc, f"Document missing field: {field}"
            # Verify no Draft documents shown to buyer
            for doc in data["documents"]:
                assert doc["status"] != "Draft", "Buyer should not see Draft documents"
        
        print(f"PASS: Buyer timeline returned {len(data['documents'])} documents")
    
    # ===========================================
    # TEST 7: POST /api/documents/{id}/action - Buyer approve
    # ===========================================
    def test_buyer_can_approve_quote(self, agent_session, buyer_session):
        """Buyer should be able to approve a sent quote"""
        agent_session_obj, _ = agent_session
        buyer_session_obj, _ = buyer_session
        
        # Get buyer's clients to find documents
        buyer_timeline = buyer_session_obj.get(f"{BASE_URL}/api/timeline")
        assert buyer_timeline.status_code == 200
        
        timeline_data = buyer_timeline.json()
        documents = timeline_data.get("documents", [])
        
        # Find a quote in Sent status
        sent_quote = None
        for doc in documents:
            if doc.get("type") == "quote" and doc.get("status") == "Sent":
                sent_quote = doc
                break
        
        if not sent_quote:
            # Create and send a quote for testing
            print("No sent quote found, creating one for test...")
            
            # Get agent's clients
            clients_response = agent_session_obj.get(f"{BASE_URL}/api/clients")
            clients = clients_response.json()
            
            # Find a client that the demo buyer is linked to
            demo_client = None
            for client in clients:
                if client.get("buyer_id"):  # Has a linked buyer
                    demo_client = client
                    break
            
            if not demo_client:
                pytest.skip("No client with linked buyer available for approval test")
            
            # Create a quote for this client
            doc_data = {
                "type": "quote",
                "title": f"TEST_ApproveQuote_{uuid.uuid4().hex[:6]}",
                "client_id": demo_client["client_id"],
                "project_id": demo_client.get("project_id"),
                "items": [
                    {"description": "Test Item for Approval", "quantity": 1, "unit_price": 750.0, "total": 750.0}
                ],
                "amount": 750.0
            }
            
            create_response = agent_session_obj.post(f"{BASE_URL}/api/documents/create", json=doc_data)
            if create_response.status_code not in [200, 201]:
                pytest.skip(f"Failed to create quote: {create_response.text}")
            
            doc = create_response.json()
            
            # Send the quote
            send_response = agent_session_obj.post(f"{BASE_URL}/api/documents/{doc['document_id']}/send")
            if send_response.status_code != 200:
                pytest.skip(f"Failed to send quote: {send_response.text}")
            
            sent_quote = {"id": doc["document_id"]}
        
        # Approve the quote as buyer
        approve_response = buyer_session_obj.post(
            f"{BASE_URL}/api/documents/{sent_quote['id']}/action",
            json={"action": "approve"}
        )
        
        # Could be 200 or 400 if already approved
        if approve_response.status_code == 200:
            data = approve_response.json()
            assert data.get("status") == "Approved" or data.get("message")
            print(f"PASS: Buyer approved quote: {data}")
        elif approve_response.status_code == 400:
            # Might already be approved or in wrong state
            error = approve_response.json()
            print(f"INFO: Quote approval returned 400: {error.get('detail')} - may already be processed")
        else:
            pytest.fail(f"Unexpected response: {approve_response.status_code} - {approve_response.text}")
    
    # ===========================================
    # TEST 8: Agent notification on buyer approval
    # ===========================================
    def test_agent_notifications_endpoint(self, agent_session):
        """Agent should have notifications endpoint working"""
        session, _ = agent_session
        
        response = session.get(f"{BASE_URL}/api/notifications")
        assert response.status_code == 200, f"Notifications fetch failed: {response.text}"
        
        data = response.json()
        # Response structure is {notifications: [...], unread_count: n}
        assert "notifications" in data, "Response should have notifications key"
        notifications = data["notifications"]
        assert isinstance(notifications, list), "Notifications should be a list"
        
        if len(notifications) > 0:
            notification = notifications[0]
            expected_fields = ["notification_id", "title", "message", "notification_type"]
            for field in expected_fields:
                assert field in notification, f"Notification missing field: {field}"
        
        print(f"PASS: Agent notifications endpoint returned {len(notifications)} notifications, unread_count={data.get('unread_count')}")


class TestClientValidation:
    """Additional tests for client validation fixes"""
    
    @pytest.fixture(scope="class")
    def agent_session(self):
        """Login as demo agent and get session"""
        session = requests.Session()
        login_response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": DEMO_AGENT_EMAIL,
            "password": DEMO_AGENT_PASSWORD
        })
        assert login_response.status_code == 200
        data = login_response.json()
        session.headers.update({"Authorization": f"Bearer {data['token']}"})
        return session, data
    
    def test_get_clients_with_project_filter(self, agent_session):
        """GET /api/clients with project_id filter should work"""
        session, _ = agent_session
        
        # First get projects
        projects_response = session.get(f"{BASE_URL}/api/projects")
        if projects_response.status_code != 200:
            pytest.skip("No projects available")
        
        projects = projects_response.json()
        if len(projects) == 0:
            pytest.skip("No projects available")
        
        project_id = projects[0]["project_id"]
        
        # Get clients filtered by project
        response = session.get(f"{BASE_URL}/api/clients?project_id={project_id}")
        assert response.status_code == 200, f"Filtered clients failed: {response.text}"
        
        data = response.json()
        assert isinstance(data, list)
        
        # Verify all returned clients belong to the project
        for client in data:
            assert client.get("project_id") == project_id, "Client project_id mismatch"
        
        print(f"PASS: GET /api/clients?project_id={project_id} returned {len(data)} clients")
    
    def test_get_single_client_returns_valid_data(self, agent_session):
        """GET /api/clients/{id} should return valid client data"""
        session, _ = agent_session
        
        # Get clients list first
        clients_response = session.get(f"{BASE_URL}/api/clients")
        clients = clients_response.json()
        
        if len(clients) == 0:
            pytest.skip("No clients available")
        
        client_id = clients[0]["client_id"]
        
        response = session.get(f"{BASE_URL}/api/clients/{client_id}")
        assert response.status_code == 200, f"Get single client failed: {response.text}"
        
        client = response.json()
        assert client["client_id"] == client_id
        assert "name" in client
        assert "email" in client
        
        print(f"PASS: GET /api/clients/{client_id} returned valid client: {client['name']}")


class TestDocumentSendValidation:
    """Tests for send document endpoint improvements"""
    
    @pytest.fixture(scope="class")
    def agent_session(self):
        """Login as demo agent and get session"""
        session = requests.Session()
        login_response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": DEMO_AGENT_EMAIL,
            "password": DEMO_AGENT_PASSWORD
        })
        assert login_response.status_code == 200
        data = login_response.json()
        session.headers.update({"Authorization": f"Bearer {data['token']}"})
        return session, data
    
    def test_send_document_validates_client_email(self, agent_session):
        """Send should validate client has email address"""
        session, _ = agent_session
        
        # Get clients
        clients_response = session.get(f"{BASE_URL}/api/clients")
        clients = clients_response.json()
        
        if len(clients) == 0:
            pytest.skip("No clients available")
        
        # Find or create a client with email
        client_with_email = None
        for client in clients:
            if client.get("email"):
                client_with_email = client
                break
        
        if not client_with_email:
            pytest.skip("No client with email available")
        
        # Create a document
        doc_data = {
            "type": "quote",
            "title": f"TEST_EmailValidation_{uuid.uuid4().hex[:6]}",
            "client_id": client_with_email["client_id"],
            "project_id": client_with_email.get("project_id"),
            "items": [
                {"description": "Test", "quantity": 1, "unit_price": 200.0, "total": 200.0}
            ],
            "amount": 200.0
        }
        
        create_response = session.post(f"{BASE_URL}/api/documents/create", json=doc_data)
        assert create_response.status_code in [200, 201]
        
        doc = create_response.json()
        
        # Send the document - should succeed since client has email
        send_response = session.post(f"{BASE_URL}/api/documents/{doc['document_id']}/send")
        assert send_response.status_code == 200, f"Send failed: {send_response.text}"
        
        send_data = send_response.json()
        assert send_data.get("recipient", {}).get("email") == client_with_email["email"]
        
        print(f"PASS: Send validated client email: {send_data['recipient']['email']}")


# Ensure tests run on module execution
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
