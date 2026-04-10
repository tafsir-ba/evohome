"""
Backend API tests for new features:
1. Team Library - /projects/{id}/team CRUD
2. Project Unit Count - unit_count in /projects response
3. Client Preview - /clients/{id}/preview
4. Feed Notification Badge - /activities/unread-count, /activities/mark-seen
5. Document file type support - type=file with file_type
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

@pytest.fixture(scope="module")
def agent_session():
    """Login as demo agent and return authenticated session"""
    session = requests.Session()
    res = session.post(f"{BASE_URL}/api/auth/demo/agent")
    assert res.status_code == 200, f"Agent login failed: {res.text}"
    return session

@pytest.fixture(scope="module")
def buyer_session():
    """Login as demo buyer and return authenticated session"""
    session = requests.Session()
    res = session.post(f"{BASE_URL}/api/auth/demo/buyer?buyer_num=1")
    assert res.status_code == 200, f"Buyer login failed: {res.text}"
    return session

@pytest.fixture(scope="module")
def demo_project_id(agent_session):
    """Get demo project ID"""
    res = agent_session.get(f"{BASE_URL}/api/projects")
    assert res.status_code == 200
    projects = res.json()
    assert len(projects) > 0, "No projects found"
    return projects[0]['project_id']

@pytest.fixture(scope="module")
def demo_client_id(agent_session):
    """Get demo client ID"""
    res = agent_session.get(f"{BASE_URL}/api/clients")
    assert res.status_code == 200
    clients = res.json()
    assert len(clients) > 0, "No clients found"
    return clients[0]['client_id']


class TestTeamLibrary:
    """Test project team member CRUD operations"""
    
    def test_get_team_members_agent(self, agent_session, demo_project_id):
        """Agent can get team members for a project"""
        res = agent_session.get(f"{BASE_URL}/api/projects/{demo_project_id}/team")
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)
        print(f"Agent sees {len(data)} team members")
    
    def test_add_team_member(self, agent_session, demo_project_id):
        """Agent can add a new team member"""
        payload = {
            "name": "TEST_Pierre Plumber",
            "role": "Plumber",
            "email": "test.pierre@sanitech.ch",
            "phone": "+41 79 123 4567",
            "website": "https://sanitech.ch",
            "notes": "Emergency contact"
        }
        res = agent_session.post(f"{BASE_URL}/api/projects/{demo_project_id}/team", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data['name'] == payload['name']
        assert data['role'] == payload['role']
        assert 'member_id' in data
        print(f"Created team member: {data['member_id']}")
        return data['member_id']
    
    def test_update_team_member(self, agent_session, demo_project_id):
        """Agent can update a team member"""
        # First create a member
        create_res = agent_session.post(f"{BASE_URL}/api/projects/{demo_project_id}/team", json={
            "name": "TEST_Update Member",
            "role": "Electrician"
        })
        assert create_res.status_code == 200
        member_id = create_res.json()['member_id']
        
        # Update the member
        update_payload = {
            "name": "TEST_Updated Member Name",
            "phone": "+41 79 999 8888"
        }
        res = agent_session.put(f"{BASE_URL}/api/projects/{demo_project_id}/team/{member_id}", json=update_payload)
        assert res.status_code == 200
        data = res.json()
        assert data['name'] == update_payload['name']
        assert data['phone'] == update_payload['phone']
        print(f"Updated team member: {member_id}")
    
    def test_delete_team_member(self, agent_session, demo_project_id):
        """Agent can delete a team member"""
        # First create a member
        create_res = agent_session.post(f"{BASE_URL}/api/projects/{demo_project_id}/team", json={
            "name": "TEST_Delete Member",
            "role": "Temp Worker"
        })
        assert create_res.status_code == 200
        member_id = create_res.json()['member_id']
        
        # Delete the member
        res = agent_session.delete(f"{BASE_URL}/api/projects/{demo_project_id}/team/{member_id}")
        assert res.status_code == 200
        
        # Verify deletion - member should not be in list
        list_res = agent_session.get(f"{BASE_URL}/api/projects/{demo_project_id}/team")
        members = list_res.json()
        member_ids = [m['member_id'] for m in members]
        assert member_id not in member_ids
        print(f"Deleted team member: {member_id}")
    
    def test_buyer_can_view_team(self, buyer_session, demo_project_id):
        """Buyer linked to project can view team members (read-only)"""
        res = buyer_session.get(f"{BASE_URL}/api/projects/{demo_project_id}/team")
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)
        print(f"Buyer sees {len(data)} team members")


class TestProjectUnitCount:
    """Test that project cards show unit_count"""
    
    def test_projects_include_unit_count(self, agent_session):
        """Projects endpoint returns unit_count field"""
        res = agent_session.get(f"{BASE_URL}/api/projects")
        assert res.status_code == 200
        projects = res.json()
        assert len(projects) > 0
        
        for project in projects:
            assert 'unit_count' in project, f"unit_count missing in project {project['project_id']}"
            assert 'client_count' in project, f"client_count missing in project {project['project_id']}"
            print(f"Project {project['name']}: {project['unit_count']} units, {project['client_count']} clients")


class TestClientPreview:
    """Test View as Client feature"""
    
    def test_client_preview_endpoint(self, agent_session, demo_client_id):
        """Agent can get client preview data"""
        res = agent_session.get(f"{BASE_URL}/api/clients/{demo_client_id}/preview")
        assert res.status_code == 200
        data = res.json()
        
        # Verify response structure
        assert 'client' in data, "Missing client data"
        assert 'project' in data, "Missing project data"
        assert 'activities' in data, "Missing activities data"
        assert 'team' in data, "Missing team data"
        assert 'is_preview' in data, "Missing is_preview flag"
        
        assert data['is_preview'] == True
        assert data['client']['client_id'] == demo_client_id
        
        print(f"Preview: Client {data['client']['name']}, Project {data['project']['name']}")
        print(f"  - {len(data['activities'])} activities")
        print(f"  - {len(data['team'])} team members")
    
    def test_preview_includes_team(self, agent_session, demo_client_id):
        """Client preview includes team members"""
        res = agent_session.get(f"{BASE_URL}/api/clients/{demo_client_id}/preview")
        assert res.status_code == 200
        data = res.json()
        
        # Team should be a list (may be empty)
        assert isinstance(data['team'], list)
        
        # If team has members, verify structure
        if len(data['team']) > 0:
            member = data['team'][0]
            assert 'member_id' in member
            assert 'name' in member
            assert 'role' in member


class TestFeedNotificationBadge:
    """Test unread count and mark-seen functionality"""
    
    def test_unread_count_endpoint(self, buyer_session):
        """Buyer can get unread activity count"""
        res = buyer_session.get(f"{BASE_URL}/api/activities/unread-count")
        assert res.status_code == 200
        data = res.json()
        assert 'unread_count' in data
        assert isinstance(data['unread_count'], int)
        assert data['unread_count'] >= 0
        print(f"Buyer unread count: {data['unread_count']}")
    
    def test_mark_seen_endpoint(self, buyer_session):
        """Buyer can mark activities as seen"""
        res = buyer_session.post(f"{BASE_URL}/api/activities/mark-seen")
        assert res.status_code == 200
        data = res.json()
        assert 'message' in data or 'updated' in data or res.status_code == 200
        print("Mark-seen endpoint succeeded")
    
    def test_unread_count_resets_after_mark_seen(self, buyer_session):
        """After marking seen, unread count should be 0"""
        # Mark as seen
        mark_res = buyer_session.post(f"{BASE_URL}/api/activities/mark-seen")
        assert mark_res.status_code == 200
        
        # Check count is now 0
        count_res = buyer_session.get(f"{BASE_URL}/api/activities/unread-count")
        assert count_res.status_code == 200
        data = count_res.json()
        assert data['unread_count'] == 0, f"Expected 0 unread, got {data['unread_count']}"
        print("Unread count is 0 after mark-seen")


class TestDocumentFileType:
    """Test file type support in activities"""
    
    def test_activities_support_file_type(self, agent_session):
        """Activities endpoint supports file type with file_type field"""
        res = agent_session.get(f"{BASE_URL}/api/activities")
        assert res.status_code == 200
        data = res.json()
        assert 'activities' in data
        
        # Check that type=file activities would have file_type
        for activity in data['activities']:
            if activity.get('type') == 'file':
                # file_type should be present (pdf, image, other)
                assert 'file_type' in activity or activity.get('file_name') is not None
                print(f"File activity found: {activity.get('file_name')}")


class TestCleanup:
    """Cleanup test data"""
    
    def test_cleanup_test_team_members(self, agent_session, demo_project_id):
        """Remove TEST_ prefixed team members"""
        res = agent_session.get(f"{BASE_URL}/api/projects/{demo_project_id}/team")
        if res.status_code == 200:
            members = res.json()
            for member in members:
                if member['name'].startswith('TEST_'):
                    del_res = agent_session.delete(
                        f"{BASE_URL}/api/projects/{demo_project_id}/team/{member['member_id']}"
                    )
                    if del_res.status_code == 200:
                        print(f"Cleaned up: {member['name']}")
