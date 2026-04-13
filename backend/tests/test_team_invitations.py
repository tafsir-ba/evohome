"""
Test Team Member Invitations Feature
- POST /api/team/invitations - create new invitation
- GET /api/team/invitations - list invitations
- DELETE /api/team/invitations/{id} - cancel invitation
- GET /api/team/members - list team members
- POST /api/team/accept - accept invitation
- POST /api/team/register-invited - register new user from invitation
- DELETE /api/team/members/{id} - remove team member
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestTeamInvitations:
    """Test Team Member Invitations endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token before each test"""
        # Login as demo agent
        res = requests.post(f"{BASE_URL}/api/demo/enter", json={"persona": "agent", "fresh": False})
        assert res.status_code == 200, f"Demo login failed: {res.text}"
        data = res.json()
        self.token = data.get('token')
        self.user_id = data.get('user_id')
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        yield
    
    def test_01_list_team_members(self):
        """GET /api/team/members - should return list with current agent as owner"""
        res = requests.get(f"{BASE_URL}/api/team/members", headers=self.headers)
        assert res.status_code == 200, f"Failed to get team members: {res.text}"
        
        members = res.json()
        assert isinstance(members, list), "Response should be a list"
        
        # Should include current user as owner
        current_user = next((m for m in members if m['user_id'] == self.user_id), None)
        assert current_user is not None, "Current user should be in team members list"
        assert current_user.get('team_role') == 'owner', "Current user should have owner role"
        
        print(f"✓ Found {len(members)} team members, current user is owner")
    
    def test_02_list_invitations_empty_or_existing(self):
        """GET /api/team/invitations - should return list of invitations"""
        res = requests.get(f"{BASE_URL}/api/team/invitations", headers=self.headers)
        assert res.status_code == 200, f"Failed to get invitations: {res.text}"
        
        invitations = res.json()
        assert isinstance(invitations, list), "Response should be a list"
        
        # Check structure of any existing invitations
        for inv in invitations:
            assert 'invitation_id' in inv, "Invitation should have invitation_id"
            assert 'email' in inv, "Invitation should have email"
            assert 'status' in inv, "Invitation should have status"
            assert 'role' in inv, "Invitation should have role"
        
        print(f"✓ Found {len(invitations)} invitations")
    
    def test_03_create_invitation(self):
        """POST /api/team/invitations - should create a new invitation"""
        test_email = f"test_invite_{os.urandom(4).hex()}@example.com"
        
        res = requests.post(
            f"{BASE_URL}/api/team/invitations",
            headers=self.headers,
            json={
                "email": test_email,
                "role": "member",
                "message": "Welcome to the team!"
            }
        )
        assert res.status_code == 200, f"Failed to create invitation: {res.text}"
        
        data = res.json()
        assert 'invitation_id' in data, "Response should have invitation_id"
        assert data['email'] == test_email.lower(), "Email should match"
        assert data['role'] == 'member', "Role should be member"
        assert data['status'] == 'pending', "Status should be pending"
        assert 'invited_by' in data, "Should have invited_by field"
        assert 'expires_at' in data, "Should have expires_at field"
        
        # Store for cleanup
        self.__class__.test_invitation_id = data['invitation_id']
        self.__class__.test_email = test_email
        
        print(f"✓ Created invitation {data['invitation_id']} for {test_email}")
    
    def test_04_create_invitation_duplicate(self):
        """POST /api/team/invitations - should fail for duplicate invitation"""
        if not hasattr(self.__class__, 'test_email'):
            pytest.skip("No test email from previous test")
        
        res = requests.post(
            f"{BASE_URL}/api/team/invitations",
            headers=self.headers,
            json={
                "email": self.__class__.test_email,
                "role": "admin"
            }
        )
        assert res.status_code == 400, f"Should fail with 400: {res.text}"
        assert 'already been sent' in res.json().get('detail', '').lower(), "Should indicate duplicate"
        
        print("✓ Duplicate invitation rejected correctly")
    
    def test_05_create_invitation_admin_role(self):
        """POST /api/team/invitations - should create admin invitation"""
        admin_email = f"test_admin_{os.urandom(4).hex()}@example.com"
        
        res = requests.post(
            f"{BASE_URL}/api/team/invitations",
            headers=self.headers,
            json={
                "email": admin_email,
                "role": "admin"
            }
        )
        assert res.status_code == 200, f"Failed to create admin invitation: {res.text}"
        
        data = res.json()
        assert data['role'] == 'admin', "Role should be admin"
        
        self.__class__.admin_invitation_id = data['invitation_id']
        
        print(f"✓ Created admin invitation for {admin_email}")
    
    def test_06_list_invitations_after_creation(self):
        """GET /api/team/invitations - should include new invitations"""
        res = requests.get(f"{BASE_URL}/api/team/invitations", headers=self.headers)
        assert res.status_code == 200, f"Failed to get invitations: {res.text}"
        
        invitations = res.json()
        
        # Should find our test invitation
        if hasattr(self.__class__, 'test_invitation_id'):
            found = any(i['invitation_id'] == self.__class__.test_invitation_id for i in invitations)
            assert found, "Should find test invitation in list"
        
        # Count pending invitations
        pending = [i for i in invitations if i['status'] == 'pending']
        print(f"✓ Found {len(pending)} pending invitations")
    
    def test_07_cancel_invitation(self):
        """DELETE /api/team/invitations/{id} - should cancel pending invitation"""
        if not hasattr(self.__class__, 'admin_invitation_id'):
            pytest.skip("No admin invitation to cancel")
        
        res = requests.delete(
            f"{BASE_URL}/api/team/invitations/{self.__class__.admin_invitation_id}",
            headers=self.headers
        )
        assert res.status_code == 200, f"Failed to cancel invitation: {res.text}"
        
        data = res.json()
        assert 'message' in data, "Response should have message"
        
        print(f"✓ Cancelled invitation {self.__class__.admin_invitation_id}")
    
    def test_08_cancel_nonexistent_invitation(self):
        """DELETE /api/team/invitations/{id} - should fail for nonexistent invitation"""
        res = requests.delete(
            f"{BASE_URL}/api/team/invitations/invite_nonexistent123",
            headers=self.headers
        )
        assert res.status_code == 404, f"Should fail with 404: {res.text}"
        
        print("✓ Nonexistent invitation returns 404")
    
    def test_09_accept_invitation_invalid_token(self):
        """POST /api/team/accept - should fail for invalid token"""
        res = requests.post(f"{BASE_URL}/api/team/accept?token=invalid_token_123")
        assert res.status_code == 404, f"Should fail with 404: {res.text}"
        assert 'not found' in res.json().get('detail', '').lower()
        
        print("✓ Invalid token returns 404")
    
    def test_10_team_members_requires_auth(self):
        """GET /api/team/members - should require authentication"""
        res = requests.get(f"{BASE_URL}/api/team/members")
        assert res.status_code == 401, f"Should require auth: {res.text}"
        
        print("✓ Team members endpoint requires auth")
    
    def test_11_invitations_requires_auth(self):
        """GET /api/team/invitations - should require authentication"""
        res = requests.get(f"{BASE_URL}/api/team/invitations")
        assert res.status_code == 401, f"Should require auth: {res.text}"
        
        print("✓ Invitations endpoint requires auth")
    
    def test_12_create_invitation_requires_auth(self):
        """POST /api/team/invitations - should require authentication"""
        res = requests.post(
            f"{BASE_URL}/api/team/invitations",
            json={"email": "test@test.com", "role": "member"}
        )
        assert res.status_code == 401, f"Should require auth: {res.text}"
        
        print("✓ Create invitation requires auth")
    
    def test_13_create_invitation_invalid_email(self):
        """POST /api/team/invitations - should validate email format"""
        res = requests.post(
            f"{BASE_URL}/api/team/invitations",
            headers=self.headers,
            json={"email": "not-a-valid-email", "role": "member"}
        )
        assert res.status_code == 422, f"Should fail validation: {res.text}"
        
        print("✓ Invalid email format rejected")
    
    def test_14_cleanup_test_invitation(self):
        """Cleanup: Cancel the test invitation"""
        if hasattr(self.__class__, 'test_invitation_id'):
            res = requests.delete(
                f"{BASE_URL}/api/team/invitations/{self.__class__.test_invitation_id}",
                headers=self.headers
            )
            # May fail if already cancelled, that's ok
            if res.status_code == 200:
                print(f"✓ Cleaned up test invitation")
            else:
                print(f"✓ Test invitation already cleaned up or not found")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
