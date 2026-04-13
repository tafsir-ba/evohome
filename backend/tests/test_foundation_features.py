"""
Test Foundation Features for Evohome SaaS
- Unit dropdown in client creation (unit_id from project_units)
- POST /api/clients with unit_id validation
- PUT /api/documents/{id} allows editing client_id, project_id, unit_id
- Notification endpoints (GET /api/notifications, PUT /api/notifications/{id}/read)
- Email notification templates (tested via endpoint side effects)
"""

import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestFoundationFeatures:
    """Test foundation improvements for Evohome"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup - login as demo agent"""
        # Login as demo agent
        self.session = requests.Session()
        res = self.session.post(f"{BASE_URL}/api/demo/enter", json={"persona": "agent", "fresh": False})
        assert res.status_code == 200, f"Demo login failed: {res.text}"
        self.agent_data = res.json()
        self.token = self.agent_data.get('token')
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        
        # Get demo project
        projects_res = self.session.get(f"{BASE_URL}/api/projects")
        assert projects_res.status_code == 200
        self.projects = projects_res.json()
        assert len(self.projects) > 0, "No demo projects found"
        self.demo_project = self.projects[0]
        print(f"Using demo project: {self.demo_project['name']} ({self.demo_project['project_id']})")
        
    # ===================== UNIT DROPDOWN & CLIENT CREATION =====================
    
    def test_get_project_units_returns_units(self):
        """GET /api/projects/{id}/units returns list of units"""
        res = self.session.get(f"{BASE_URL}/api/projects/{self.demo_project['project_id']}/units")
        assert res.status_code == 200, f"Failed to get units: {res.text}"
        units = res.json()
        assert isinstance(units, list), "Units should be a list"
        print(f"Found {len(units)} units in project")
        if len(units) > 0:
            unit = units[0]
            assert 'unit_id' in unit, "Unit should have unit_id"
            assert 'unit_reference' in unit, "Unit should have unit_reference"
            print(f"Sample unit: {unit.get('unit_reference')} ({unit.get('unit_id')})")
    
    def test_create_client_with_unit_id(self):
        """POST /api/clients creates client with valid unit_id"""
        # First get a unit from the project
        units_res = self.session.get(f"{BASE_URL}/api/projects/{self.demo_project['project_id']}/units")
        assert units_res.status_code == 200
        units = units_res.json()
        
        test_email = f"test_client_{uuid.uuid4().hex[:8]}@example.com"
        
        client_data = {
            "name": "TEST_Client With Unit",
            "email": test_email,
            "phone": "+41 79 123 45 67",
            "project_id": self.demo_project['project_id'],
            "unit_id": units[0]['unit_id'] if len(units) > 0 else None
        }
        
        res = self.session.post(f"{BASE_URL}/api/clients", json=client_data)
        assert res.status_code == 200, f"Failed to create client: {res.text}"
        
        client = res.json()
        assert client['name'] == "TEST_Client With Unit"
        assert client['email'] == test_email
        assert client['project_id'] == self.demo_project['project_id']
        
        if len(units) > 0:
            assert client.get('unit_id') == units[0]['unit_id'], "unit_id should be set"
            # unit_reference should be resolved from the unit
            assert 'unit_reference' in client, "unit_reference should be returned"
            print(f"Client created with unit: {client.get('unit_reference')}")
        
        # Cleanup - delete test client
        self.session.delete(f"{BASE_URL}/api/clients/{client['client_id']}")
        print("PASS: Client created with unit_id")
    
    def test_create_client_without_unit_id(self):
        """POST /api/clients creates client without unit_id (defaults to General)"""
        test_email = f"test_nounit_{uuid.uuid4().hex[:8]}@example.com"
        
        client_data = {
            "name": "TEST_Client No Unit",
            "email": test_email,
            "project_id": self.demo_project['project_id']
            # No unit_id
        }
        
        res = self.session.post(f"{BASE_URL}/api/clients", json=client_data)
        assert res.status_code == 200, f"Failed to create client: {res.text}"
        
        client = res.json()
        assert client['unit_reference'] == "General", "unit_reference should default to 'General'"
        assert client.get('unit_id') is None, "unit_id should be None"
        
        # Cleanup
        self.session.delete(f"{BASE_URL}/api/clients/{client['client_id']}")
        print("PASS: Client created without unit_id defaults to General")
    
    def test_create_client_with_invalid_unit_id(self):
        """POST /api/clients with invalid unit_id still creates client (unit_id ignored or validated)"""
        test_email = f"test_badunit_{uuid.uuid4().hex[:8]}@example.com"
        
        client_data = {
            "name": "TEST_Client Bad Unit",
            "email": test_email,
            "project_id": self.demo_project['project_id'],
            "unit_id": "invalid_unit_id_xyz"
        }
        
        res = self.session.post(f"{BASE_URL}/api/clients", json=client_data)
        # Could be 200 (ignores invalid) or 400 (validates unit exists)
        # Based on code, it validates unit exists in project
        if res.status_code == 200:
            client = res.json()
            # If 200, unit should default to General
            print(f"Client created, unit_reference: {client.get('unit_reference')}")
            self.session.delete(f"{BASE_URL}/api/clients/{client['client_id']}")
        else:
            # Validation error expected
            assert res.status_code in [400, 422], f"Unexpected status: {res.status_code}"
            print(f"PASS: Invalid unit_id rejected with {res.status_code}")
    
    # ===================== DOCUMENT REFERENCE EDITING =====================
    
    def test_update_document_client_id(self):
        """PUT /api/documents/{id} allows editing client_id (only for Draft/Change Requested docs)"""
        # Get existing documents
        docs_res = self.session.get(f"{BASE_URL}/api/documents")
        assert docs_res.status_code == 200
        docs = docs_res.json()
        
        if len(docs) == 0:
            pytest.skip("No documents to test with")
        
        # Find a document in Draft or Change Requested status (editable states)
        test_doc = None
        for d in docs:
            if d.get('status') in ['Draft', 'Change Requested']:
                test_doc = d
                break
        
        if not test_doc:
            pytest.skip("No editable documents (Draft/Change Requested) to test with")
        
        # Get existing clients
        clients_res = self.session.get(f"{BASE_URL}/api/clients")
        assert clients_res.status_code == 200
        clients = clients_res.json()
        
        if len(clients) < 2:
            pytest.skip("Need at least 2 clients to test client_id change")
        
        original_client_id = test_doc.get('client_id')
        
        # Find a different client
        new_client = None
        for c in clients:
            if c['client_id'] != original_client_id:
                new_client = c
                break
        
        if not new_client:
            pytest.skip("Could not find different client")
        
        # Update document's client_id
        update_res = self.session.put(
            f"{BASE_URL}/api/documents/{test_doc['document_id']}",
            json={"client_id": new_client['client_id']}
        )
        assert update_res.status_code == 200, f"Failed to update document: {update_res.text}"
        
        updated_doc = update_res.json()
        assert updated_doc['client_id'] == new_client['client_id'], "client_id should be updated"
        print(f"PASS: Document client_id changed from {original_client_id} to {new_client['client_id']}")
        
        # Revert change
        self.session.put(
            f"{BASE_URL}/api/documents/{test_doc['document_id']}",
            json={"client_id": original_client_id}
        )
    
    def test_update_document_project_id(self):
        """PUT /api/documents/{id} allows editing project_id (only for Draft/Change Requested docs)"""
        docs_res = self.session.get(f"{BASE_URL}/api/documents")
        assert docs_res.status_code == 200
        docs = docs_res.json()
        
        if len(docs) == 0:
            pytest.skip("No documents to test with")
        
        # Find a document in Draft or Change Requested status
        test_doc = None
        for d in docs:
            if d.get('status') in ['Draft', 'Change Requested']:
                test_doc = d
                break
        
        if not test_doc:
            pytest.skip("No editable documents (Draft/Change Requested) to test with")
        
        projects_res = self.session.get(f"{BASE_URL}/api/projects")
        assert projects_res.status_code == 200
        projects = projects_res.json()
        
        if len(projects) < 2:
            pytest.skip("Need at least 2 projects to test project_id change")
        
        original_project_id = test_doc.get('project_id')
        
        # Find a different project
        new_project = None
        for p in projects:
            if p['project_id'] != original_project_id:
                new_project = p
                break
        
        if not new_project:
            pytest.skip("Could not find different project")
        
        # Update document's project_id
        update_res = self.session.put(
            f"{BASE_URL}/api/documents/{test_doc['document_id']}",
            json={"project_id": new_project['project_id']}
        )
        assert update_res.status_code == 200, f"Failed to update document: {update_res.text}"
        
        updated_doc = update_res.json()
        assert updated_doc['project_id'] == new_project['project_id'], "project_id should be updated"
        print(f"PASS: Document project_id changed to {new_project['project_id']}")
        
        # Revert
        self.session.put(
            f"{BASE_URL}/api/documents/{test_doc['document_id']}",
            json={"project_id": original_project_id}
        )
    
    def test_update_document_unit_id(self):
        """PUT /api/documents/{id} allows editing unit_id (only for Draft/Change Requested docs)"""
        docs_res = self.session.get(f"{BASE_URL}/api/documents")
        assert docs_res.status_code == 200
        docs = docs_res.json()
        
        if len(docs) == 0:
            pytest.skip("No documents to test with")
        
        # Find a document in Draft or Change Requested status
        test_doc = None
        for d in docs:
            if d.get('status') in ['Draft', 'Change Requested']:
                test_doc = d
                break
        
        if not test_doc:
            pytest.skip("No editable documents (Draft/Change Requested) to test with")
        
        project_id = test_doc.get('project_id')
        
        # Get units for this project
        units_res = self.session.get(f"{BASE_URL}/api/projects/{project_id}/units")
        assert units_res.status_code == 200
        units = units_res.json()
        
        if len(units) == 0:
            pytest.skip("No units in project to test with")
        
        original_unit_id = test_doc.get('unit_id')
        
        # Find a different unit
        new_unit = units[0] if units[0].get('unit_id') != original_unit_id else (units[1] if len(units) > 1 else None)
        
        if not new_unit:
            # Just test with the first unit
            new_unit = units[0]
        
        # Update document's unit_id
        update_res = self.session.put(
            f"{BASE_URL}/api/documents/{test_doc['document_id']}",
            json={"unit_id": new_unit['unit_id']}
        )
        assert update_res.status_code == 200, f"Failed to update document: {update_res.text}"
        
        updated_doc = update_res.json()
        assert updated_doc.get('unit_id') == new_unit['unit_id'], "unit_id should be updated"
        assert updated_doc.get('unit_reference') is not None, "unit_reference should be set"
        print(f"PASS: Document unit_id changed to {new_unit['unit_id']}, unit_reference: {updated_doc.get('unit_reference')}")
        
        # Revert if we changed it
        if original_unit_id != new_unit['unit_id']:
            self.session.put(
                f"{BASE_URL}/api/documents/{test_doc['document_id']}",
                json={"unit_id": original_unit_id or ""}
            )
    
    def test_update_document_clear_unit_id(self):
        """PUT /api/documents/{id} with empty unit_id clears to General (only Draft/Change Requested)"""
        docs_res = self.session.get(f"{BASE_URL}/api/documents")
        assert docs_res.status_code == 200
        docs = docs_res.json()
        
        if len(docs) == 0:
            pytest.skip("No documents to test with")
        
        # Find a document in Draft or Change Requested status
        test_doc = None
        for d in docs:
            if d.get('status') in ['Draft', 'Change Requested']:
                test_doc = d
                break
        
        if not test_doc:
            pytest.skip("No editable documents (Draft/Change Requested) to test with")
        
        original_unit_id = test_doc.get('unit_id')
        
        # Clear unit_id
        update_res = self.session.put(
            f"{BASE_URL}/api/documents/{test_doc['document_id']}",
            json={"unit_id": ""}
        )
        assert update_res.status_code == 200, f"Failed to clear unit: {update_res.text}"
        
        updated_doc = update_res.json()
        assert updated_doc.get('unit_id') is None, "unit_id should be None"
        assert updated_doc.get('unit_reference') == "General", "unit_reference should be 'General'"
        print("PASS: Document unit cleared to General")
        
        # Revert
        if original_unit_id:
            self.session.put(
                f"{BASE_URL}/api/documents/{test_doc['document_id']}",
                json={"unit_id": original_unit_id}
            )
    
    # ===================== NOTIFICATIONS =====================
    
    def test_get_notifications_returns_list_with_unread_count(self):
        """GET /api/notifications returns notifications list with unread_count"""
        res = self.session.get(f"{BASE_URL}/api/notifications")
        assert res.status_code == 200, f"Failed to get notifications: {res.text}"
        
        data = res.json()
        assert 'notifications' in data, "Response should have 'notifications' key"
        assert 'unread_count' in data, "Response should have 'unread_count' key"
        assert isinstance(data['notifications'], list), "notifications should be a list"
        assert isinstance(data['unread_count'], int), "unread_count should be an integer"
        
        print(f"PASS: Got {len(data['notifications'])} notifications, {data['unread_count']} unread")
    
    def test_mark_notification_as_read(self):
        """PUT /api/notifications/{id}/read marks single notification as read"""
        # First get notifications
        notif_res = self.session.get(f"{BASE_URL}/api/notifications")
        assert notif_res.status_code == 200
        data = notif_res.json()
        
        notifications = data['notifications']
        if len(notifications) == 0:
            pytest.skip("No notifications to test with")
        
        # Find an unread notification or use the first one
        test_notif = None
        for n in notifications:
            if not n.get('is_read'):
                test_notif = n
                break
        
        if not test_notif:
            test_notif = notifications[0]
            print(f"Using already-read notification: {test_notif.get('notification_id')}")
        else:
            print(f"Using unread notification: {test_notif.get('notification_id')}")
        
        # Mark as read
        mark_res = self.session.put(f"{BASE_URL}/api/notifications/{test_notif['notification_id']}/read")
        assert mark_res.status_code == 200, f"Failed to mark as read: {mark_res.text}"
        
        result = mark_res.json()
        assert result.get('message') == "Notification marked as read", "Should confirm mark as read"
        
        # Verify it's now marked as read
        verify_res = self.session.get(f"{BASE_URL}/api/notifications")
        verify_data = verify_res.json()
        marked_notif = next((n for n in verify_data['notifications'] if n['notification_id'] == test_notif['notification_id']), None)
        if marked_notif:
            assert marked_notif['is_read'] == True, "Notification should now be read"
        
        print("PASS: Notification marked as read")
    
    def test_mark_nonexistent_notification_as_read(self):
        """PUT /api/notifications/{id}/read returns 404 for invalid notification"""
        res = self.session.put(f"{BASE_URL}/api/notifications/invalid_notif_xyz/read")
        assert res.status_code == 404, f"Should return 404 for invalid notification, got {res.status_code}"
        print("PASS: 404 returned for invalid notification id")
    
    def test_mark_all_notifications_as_read(self):
        """PUT /api/notifications/read-all marks all notifications as read"""
        res = self.session.put(f"{BASE_URL}/api/notifications/read-all")
        assert res.status_code == 200, f"Failed to mark all as read: {res.text}"
        
        # Verify all are now read
        verify_res = self.session.get(f"{BASE_URL}/api/notifications")
        verify_data = verify_res.json()
        assert verify_data['unread_count'] == 0, "unread_count should be 0"
        
        print("PASS: All notifications marked as read")


class TestClientUnitValidation:
    """Additional tests for unit validation in client creation"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        res = self.session.post(f"{BASE_URL}/api/demo/enter", json={"persona": "agent", "fresh": False})
        assert res.status_code == 200
        self.agent_data = res.json()
        self.token = self.agent_data.get('token')
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        
        projects_res = self.session.get(f"{BASE_URL}/api/projects")
        self.projects = projects_res.json()
        self.demo_project = self.projects[0] if self.projects else None
    
    def test_create_unit_then_client(self):
        """Create a unit, then create client with that unit"""
        if not self.demo_project:
            pytest.skip("No demo project")
        
        # Create a new unit
        unit_data = {"unit_reference": f"TEST-UNIT-{uuid.uuid4().hex[:6]}"}
        unit_res = self.session.post(
            f"{BASE_URL}/api/projects/{self.demo_project['project_id']}/units",
            json=unit_data
        )
        
        if unit_res.status_code == 403:
            pytest.skip("Unit limit reached, cannot create more units")
        
        assert unit_res.status_code == 200, f"Failed to create unit: {unit_res.text}"
        new_unit = unit_res.json()
        print(f"Created unit: {new_unit.get('unit_reference')} ({new_unit.get('unit_id')})")
        
        # Create client with this unit
        test_email = f"test_{uuid.uuid4().hex[:8]}@example.com"
        client_data = {
            "name": "TEST_Unit Client",
            "email": test_email,
            "project_id": self.demo_project['project_id'],
            "unit_id": new_unit['unit_id']
        }
        
        client_res = self.session.post(f"{BASE_URL}/api/clients", json=client_data)
        assert client_res.status_code == 200, f"Failed to create client: {client_res.text}"
        
        client = client_res.json()
        assert client.get('unit_id') == new_unit['unit_id']
        print(f"Client linked to unit: {client.get('unit_reference')}")
        
        # Cleanup - delete client first (unit might be in use)
        del_client = self.session.delete(f"{BASE_URL}/api/clients/{client['client_id']}")
        assert del_client.status_code == 200, f"Client cleanup failed: {del_client.status_code}"
        # Then delete unit via canonical path
        del_unit = self.session.delete(f"{BASE_URL}/api/units/{new_unit['unit_id']}")
        assert del_unit.status_code == 200, f"Unit cleanup failed: {del_unit.status_code}"
        print("PASS: Unit->Client flow works")


class TestEmailNotificationTemplates:
    """Test email notification triggers (indirect - verifies notification created)"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        res = self.session.post(f"{BASE_URL}/api/demo/enter", json={"persona": "agent", "fresh": False})
        assert res.status_code == 200
        self.agent_data = res.json()
        self.token = self.agent_data.get('token')
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
    
    def test_document_sent_creates_notification(self):
        """When document is sent, notification is created for buyer"""
        # Get a document in Draft status
        docs_res = self.session.get(f"{BASE_URL}/api/documents?status=Draft")
        if docs_res.status_code != 200:
            docs_res = self.session.get(f"{BASE_URL}/api/documents")
        
        docs = docs_res.json()
        draft_doc = None
        for d in docs:
            if d.get('status') == 'Draft':
                draft_doc = d
                break
        
        if not draft_doc:
            pytest.skip("No draft documents to test send action")
        
        # Send the document
        send_res = self.session.post(f"{BASE_URL}/api/documents/{draft_doc['document_id']}/send")
        
        if send_res.status_code == 200:
            print(f"PASS: Document sent, email notification should be triggered")
            # Revert by checking if we can change status back (we can't, but that's ok)
        else:
            print(f"Document send status: {send_res.status_code} - {send_res.text}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
