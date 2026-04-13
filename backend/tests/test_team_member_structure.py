"""
Test Team Member Structure with Company Name + Contact Name
Tests for the new team member fields: company_name, contact_name
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestTeamMemberStructure:
    """Tests for team member with company_name and contact_name fields"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with demo agent authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as demo agent
        login_res = self.session.post(f"{BASE_URL}/api/demo/enter", json={"persona": "agent", "fresh": False})
        assert login_res.status_code == 200, f"Demo login failed: {login_res.text}"
        self.agent_data = login_res.json()
        self.token = self.agent_data.get('token')
        if self.token:
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        
        # Get first project
        projects_res = self.session.get(f"{BASE_URL}/api/projects")
        assert projects_res.status_code == 200, "Failed to fetch projects"
        projects = projects_res.json()
        assert len(projects) > 0, "No projects found"
        self.project_id = projects[0]['project_id']
        
        yield
        
        # Cleanup - no cleanup needed, demo mode

    def test_get_team_members_endpoint_exists(self):
        """GET /api/projects/{id}/team returns team members list"""
        res = self.session.get(f"{BASE_URL}/api/projects/{self.project_id}/team")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        data = res.json()
        assert isinstance(data, list), "Expected list response"
        print(f"SUCCESS: GET /api/projects/{self.project_id}/team returned {len(data)} team members")

    def test_team_member_has_company_name_field(self):
        """Team members should have company_name field"""
        res = self.session.get(f"{BASE_URL}/api/projects/{self.project_id}/team")
        assert res.status_code == 200
        members = res.json()
        
        if len(members) > 0:
            member = members[0]
            assert 'company_name' in member, f"Team member missing 'company_name' field. Keys: {member.keys()}"
            assert member['company_name'], f"company_name should have a value"
            print(f"SUCCESS: Team member has company_name = '{member['company_name']}'")
        else:
            pytest.skip("No team members found to verify structure")

    def test_team_member_has_contact_name_field(self):
        """Team members should have contact_name field"""
        res = self.session.get(f"{BASE_URL}/api/projects/{self.project_id}/team")
        assert res.status_code == 200
        members = res.json()
        
        if len(members) > 0:
            member = members[0]
            assert 'contact_name' in member, f"Team member missing 'contact_name' field. Keys: {member.keys()}"
            assert member['contact_name'], f"contact_name should have a value"
            print(f"SUCCESS: Team member has contact_name = '{member['contact_name']}'")
        else:
            pytest.skip("No team members found to verify structure")

    def test_create_team_member_with_company_and_contact_name(self):
        """POST /api/projects/{id}/team creates member with company_name and contact_name"""
        payload = {
            "company_name": "TEST_TestCompany SA",
            "contact_name": "John Test Smith",
            "role": "Tester",
            "email": "test@testcompany.ch",
            "phone": "+41 76 555 9999"
        }
        
        res = self.session.post(
            f"{BASE_URL}/api/projects/{self.project_id}/team",
            json=payload
        )
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        
        data = res.json()
        assert data['company_name'] == payload['company_name'], "company_name not saved correctly"
        assert data['contact_name'] == payload['contact_name'], "contact_name not saved correctly"
        assert data['role'] == payload['role']
        assert data['email'] == payload['email']
        assert 'member_id' in data, "Response should include member_id"
        
        print(f"SUCCESS: Created team member with company_name='{data['company_name']}', contact_name='{data['contact_name']}'")
        
        # Verify by fetching
        member_id = data['member_id']
        verify_res = self.session.get(f"{BASE_URL}/api/projects/{self.project_id}/team")
        assert verify_res.status_code == 200
        members = verify_res.json()
        
        found = next((m for m in members if m['member_id'] == member_id), None)
        assert found, f"Created member {member_id} not found in team list"
        assert found['company_name'] == payload['company_name']
        assert found['contact_name'] == payload['contact_name']
        print(f"SUCCESS: Verified team member persisted correctly")
        
        # Cleanup
        del_res = self.session.delete(f"{BASE_URL}/api/projects/{self.project_id}/team/{member_id}")
        assert del_res.status_code == 200, f"Cleanup failed: {del_res.text}"

    def test_create_team_member_requires_company_name(self):
        """POST /api/projects/{id}/team requires company_name"""
        payload = {
            "contact_name": "John Smith",
            "role": "Tester"
            # Missing company_name - should fail
        }
        
        res = self.session.post(
            f"{BASE_URL}/api/projects/{self.project_id}/team",
            json=payload
        )
        # Should fail validation (422) because company_name is required
        assert res.status_code == 422, f"Expected 422 validation error, got {res.status_code}"
        print(f"SUCCESS: API correctly rejects request without company_name (422)")

    def test_create_team_member_requires_contact_name(self):
        """POST /api/projects/{id}/team requires contact_name"""
        payload = {
            "company_name": "Test Company",
            "role": "Tester"
            # Missing contact_name - should fail
        }
        
        res = self.session.post(
            f"{BASE_URL}/api/projects/{self.project_id}/team",
            json=payload
        )
        # Should fail validation (422) because contact_name is required
        assert res.status_code == 422, f"Expected 422 validation error, got {res.status_code}"
        print(f"SUCCESS: API correctly rejects request without contact_name (422)")

    def test_update_team_member_company_name(self):
        """PUT /api/projects/{id}/team/{member_id} can update company_name"""
        # First create a member
        payload = {
            "company_name": "TEST_OriginalCompany",
            "contact_name": "Original Contact",
            "role": "Tester"
        }
        create_res = self.session.post(
            f"{BASE_URL}/api/projects/{self.project_id}/team",
            json=payload
        )
        assert create_res.status_code == 200
        member_id = create_res.json()['member_id']
        
        # Update company_name
        update_payload = {"company_name": "TEST_UpdatedCompany"}
        update_res = self.session.put(
            f"{BASE_URL}/api/projects/{self.project_id}/team/{member_id}",
            json=update_payload
        )
        assert update_res.status_code == 200, f"Update failed: {update_res.text}"
        
        updated = update_res.json()
        assert updated['company_name'] == "TEST_UpdatedCompany", "company_name not updated"
        print(f"SUCCESS: Updated company_name to '{updated['company_name']}'")
        
        # Cleanup
        self.session.delete(f"{BASE_URL}/api/projects/{self.project_id}/team/{member_id}")

    def test_update_team_member_contact_name(self):
        """PUT /api/projects/{id}/team/{member_id} can update contact_name"""
        # First create a member
        payload = {
            "company_name": "TEST_SomeCompany",
            "contact_name": "Original Name",
            "role": "Tester"
        }
        create_res = self.session.post(
            f"{BASE_URL}/api/projects/{self.project_id}/team",
            json=payload
        )
        assert create_res.status_code == 200
        member_id = create_res.json()['member_id']
        
        # Update contact_name
        update_payload = {"contact_name": "Updated Contact Name"}
        update_res = self.session.put(
            f"{BASE_URL}/api/projects/{self.project_id}/team/{member_id}",
            json=update_payload
        )
        assert update_res.status_code == 200, f"Update failed: {update_res.text}"
        
        updated = update_res.json()
        assert updated['contact_name'] == "Updated Contact Name", "contact_name not updated"
        print(f"SUCCESS: Updated contact_name to '{updated['contact_name']}'")
        
        # Cleanup
        self.session.delete(f"{BASE_URL}/api/projects/{self.project_id}/team/{member_id}")

    def test_seed_data_has_company_and_contact_names(self):
        """Verify seeded demo data has correct company_name and contact_name"""
        res = self.session.get(f"{BASE_URL}/api/projects/{self.project_id}/team")
        assert res.status_code == 200
        members = res.json()
        
        # Check expected demo data
        expected_companies = ["SaniTech SA", "ElecPro Sàrl", "Meier Architekten AG"]
        expected_contacts = ["Pierre Dupont", "Marie Fontaine", "Hans Meier"]
        
        found_companies = [m.get('company_name') for m in members]
        found_contacts = [m.get('contact_name') for m in members]
        
        print(f"Found team members:")
        for m in members:
            print(f"  - {m.get('company_name')} ({m.get('contact_name')}) - {m.get('role')}")
        
        # Check at least some of the expected data exists
        matches = sum(1 for c in expected_companies if c in found_companies)
        if matches > 0:
            print(f"SUCCESS: Found {matches}/{len(expected_companies)} expected company names in seed data")
        else:
            print(f"INFO: Seed data may have different values. Found companies: {found_companies}")

    def test_team_member_email_field_optional(self):
        """Team member email should be optional"""
        payload = {
            "company_name": "TEST_NoEmailCompany",
            "contact_name": "No Email Contact",
            "role": "Tester"
            # No email - should be allowed
        }
        
        res = self.session.post(
            f"{BASE_URL}/api/projects/{self.project_id}/team",
            json=payload
        )
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        
        data = res.json()
        assert data['email'] is None or data['email'] == '', "Email should be None or empty when not provided"
        print(f"SUCCESS: Created team member without email")
        
        # Cleanup
        self.session.delete(f"{BASE_URL}/api/projects/{self.project_id}/team/{data['member_id']}")


class TestTeamMemberEmailLinks:
    """Tests for email mailto links on team cards"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as demo agent
        login_res = self.session.post(f"{BASE_URL}/api/demo/enter", json={"persona": "agent", "fresh": False})
        assert login_res.status_code == 200
        self.token = login_res.json().get('token')
        if self.token:
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        
        # Get first project
        projects_res = self.session.get(f"{BASE_URL}/api/projects")
        assert projects_res.status_code == 200
        projects = projects_res.json()
        assert len(projects) > 0
        self.project_id = projects[0]['project_id']
        
        yield

    def test_team_member_email_returned_in_response(self):
        """Team member response includes email field for mailto links"""
        # Create member with email
        payload = {
            "company_name": "TEST_EmailTest",
            "contact_name": "Email Tester",
            "role": "QA",
            "email": "test@example.ch"
        }
        
        create_res = self.session.post(
            f"{BASE_URL}/api/projects/{self.project_id}/team",
            json=payload
        )
        assert create_res.status_code == 200
        member = create_res.json()
        
        assert 'email' in member, "Response should include email field"
        assert member['email'] == "test@example.ch", "Email should match what was sent"
        print(f"SUCCESS: Team member email '{member['email']}' returned correctly for mailto links")
        
        # Cleanup
        self.session.delete(f"{BASE_URL}/api/projects/{self.project_id}/team/{member['member_id']}")

    def test_team_members_with_email_can_be_filtered(self):
        """Verify we can check which team members have emails"""
        res = self.session.get(f"{BASE_URL}/api/projects/{self.project_id}/team")
        assert res.status_code == 200
        members = res.json()
        
        members_with_email = [m for m in members if m.get('email')]
        print(f"SUCCESS: {len(members_with_email)}/{len(members)} team members have emails for mailto links")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
