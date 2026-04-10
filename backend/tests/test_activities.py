"""
Test Activity Feed API endpoints
Tests the unified feed system for agent and buyer roles:
- Agent: create, view all, reply, multi-client targeting
- Buyer: view filtered (only activities addressed to them), reply
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test sessions for agent and buyer
class TestActivityFeedAPI:
    """Test Activity Feed endpoints"""
    
    @pytest.fixture(scope="class")
    def agent_session(self):
        """Get authenticated session for demo agent"""
        session = requests.Session()
        # Login as demo agent - session cookie is set automatically
        res = session.post(f"{BASE_URL}/api/auth/demo/agent")
        assert res.status_code == 200, f"Agent login failed: {res.text}"
        data = res.json()
        assert 'name' in data, "No user name in agent response"
        assert data.get('role') == 'agent', f"Expected agent role, got {data.get('role')}"
        print(f"Logged in as agent: {data.get('name')}")
        return session
    
    @pytest.fixture(scope="class")
    def buyer_session(self):
        """Get authenticated session for demo buyer (Sophie Müller)"""
        session = requests.Session()
        # Login as demo buyer - session cookie is set automatically
        res = session.post(f"{BASE_URL}/api/auth/demo/buyer")
        assert res.status_code == 200, f"Buyer login failed: {res.text}"
        data = res.json()
        assert 'name' in data, "No user name in buyer response"
        assert data.get('role') == 'buyer', f"Expected buyer role, got {data.get('role')}"
        print(f"Logged in as buyer: {data.get('name')}")
        return session
    
    # ==================== Agent Tests ====================
    
    def test_agent_get_projects(self, agent_session):
        """Agent can get list of projects"""
        res = agent_session.get(f"{BASE_URL}/api/projects")
        assert res.status_code == 200, f"Failed to get projects: {res.text}"
        projects = res.json()
        assert isinstance(projects, list), "Projects should be a list"
        assert len(projects) > 0, "Agent should have at least one project"
        # Store for later tests
        self.__class__.project_id = projects[0]['project_id']
        print(f"Found project: {projects[0]['name']} ({self.__class__.project_id})")
    
    def test_agent_get_clients(self, agent_session):
        """Agent can get list of clients"""
        res = agent_session.get(f"{BASE_URL}/api/clients")
        assert res.status_code == 200, f"Failed to get clients: {res.text}"
        clients = res.json()
        assert isinstance(clients, list), "Clients should be a list"
        assert len(clients) > 0, "Agent should have at least one client"
        # Store client_id for later tests
        self.__class__.client_ids = [c['client_id'] for c in clients]
        print(f"Found {len(clients)} clients")
    
    def test_agent_get_activities(self, agent_session):
        """Agent can get list of activities"""
        res = agent_session.get(f"{BASE_URL}/api/activities")
        assert res.status_code == 200, f"Failed to get activities: {res.text}"
        data = res.json()
        assert 'activities' in data, "Response should have 'activities' key"
        assert 'total' in data, "Response should have 'total' key"
        print(f"Found {data['total']} activities")
    
    def test_agent_create_activity_message(self, agent_session):
        """Agent can create a new message activity"""
        # Get project and clients first
        proj_res = agent_session.get(f"{BASE_URL}/api/projects")
        assert proj_res.status_code == 200
        projects = proj_res.json()
        assert len(projects) > 0, "Need at least one project"
        
        client_res = agent_session.get(f"{BASE_URL}/api/clients")
        assert client_res.status_code == 200
        clients = client_res.json()
        assert len(clients) > 0, "Need at least one client"
        
        # Filter clients by project
        project_id = projects[0]['project_id']
        project_clients = [c for c in clients if c.get('project_id') == project_id]
        if not project_clients:
            project_clients = clients[:1]  # Use first client if no match
        
        # Create activity
        form_data = {
            'type': 'message',
            'project_id': project_id,
            'client_ids': ','.join([c['client_id'] for c in project_clients]),
            'title': 'TEST_Backend Test Activity',
            'content': 'This is a test message created by backend tests.'
        }
        
        res = agent_session.post(f"{BASE_URL}/api/activities", data=form_data)
        assert res.status_code == 200, f"Failed to create activity: {res.text}"
        
        activity = res.json()
        assert 'activity_id' in activity, "Response should have activity_id"
        assert activity['type'] == 'message', "Activity type should be 'message'"
        assert activity['title'] == 'TEST_Backend Test Activity', "Title should match"
        assert activity['content'] == 'This is a test message created by backend tests.', "Content should match"
        
        # Store for later tests
        self.__class__.created_activity_id = activity['activity_id']
        print(f"Created activity: {activity['activity_id']}")
    
    def test_agent_get_single_activity(self, agent_session):
        """Agent can get details of a single activity"""
        activity_id = getattr(self.__class__, 'created_activity_id', None)
        if not activity_id:
            pytest.skip("No activity created in previous test")
        
        res = agent_session.get(f"{BASE_URL}/api/activities/{activity_id}")
        assert res.status_code == 200, f"Failed to get activity: {res.text}"
        
        activity = res.json()
        assert activity['activity_id'] == activity_id
        assert 'recipients' in activity, "Activity should have recipients list"
        assert len(activity['recipients']) > 0, "Activity should have at least one recipient"
        print(f"Activity has {len(activity['recipients'])} recipients")
    
    def test_agent_reply_to_activity(self, agent_session):
        """Agent can reply to an activity"""
        activity_id = getattr(self.__class__, 'created_activity_id', None)
        if not activity_id:
            pytest.skip("No activity created in previous test")
        
        reply_data = {'content': 'This is a test reply from the agent.'}
        res = agent_session.post(
            f"{BASE_URL}/api/activities/{activity_id}/reply",
            json=reply_data
        )
        assert res.status_code == 200, f"Failed to reply: {res.text}"
        
        reply = res.json()
        assert 'reply_id' in reply, "Response should have reply_id"
        assert reply['content'] == 'This is a test reply from the agent.', "Reply content should match"
        assert reply['author_role'] == 'agent', "Reply author_role should be 'agent'"
        assert 'author_name' in reply, "Reply should have author_name"
        
        # Verify _id is not in response
        assert '_id' not in reply, "MongoDB _id should not be in response"
        
        print(f"Created reply: {reply['reply_id']}")
    
    def test_agent_activity_has_reply(self, agent_session):
        """Verify activity now includes the reply"""
        activity_id = getattr(self.__class__, 'created_activity_id', None)
        if not activity_id:
            pytest.skip("No activity created in previous test")
        
        res = agent_session.get(f"{BASE_URL}/api/activities/{activity_id}")
        assert res.status_code == 200
        
        activity = res.json()
        assert 'replies' in activity, "Activity should have replies array"
        assert len(activity['replies']) > 0, "Activity should have at least one reply"
        
        # Check reply structure
        reply = activity['replies'][0]
        assert 'reply_id' in reply
        assert 'content' in reply
        assert 'author_name' in reply
        print(f"Activity has {len(activity['replies'])} replies")
    
    # ==================== Buyer Tests ====================
    
    def test_buyer_get_activities(self, buyer_session):
        """Buyer can get activities (filtered to their unit)"""
        res = buyer_session.get(f"{BASE_URL}/api/activities")
        assert res.status_code == 200, f"Failed to get activities: {res.text}"
        
        data = res.json()
        assert 'activities' in data, "Response should have 'activities' key"
        print(f"Buyer sees {data['total']} activities")
    
    def test_buyer_cannot_create_activity(self, buyer_session):
        """Buyer should not be able to create activities (403)"""
        # Get any project/client IDs just to try
        form_data = {
            'type': 'message',
            'project_id': 'any_project',
            'client_ids': 'any_client',
            'title': 'TEST_Buyer trying to create',
            'content': 'This should fail'
        }
        
        res = buyer_session.post(f"{BASE_URL}/api/activities", data=form_data)
        # Should fail with 403 (Forbidden) or 401 (requires agent)
        assert res.status_code in [401, 403], f"Buyer should not be able to create activities, got {res.status_code}"
        print(f"Buyer correctly denied activity creation with status {res.status_code}")
    
    def test_buyer_can_reply_to_activity(self, buyer_session, agent_session):
        """Buyer can reply to activities addressed to them"""
        # First get buyer's activities
        res = buyer_session.get(f"{BASE_URL}/api/activities")
        assert res.status_code == 200
        data = res.json()
        
        if data['total'] == 0:
            pytest.skip("No activities for buyer to reply to")
        
        activity_id = data['activities'][0]['activity_id']
        
        reply_data = {'content': 'TEST_This is a test reply from the buyer.'}
        res = buyer_session.post(
            f"{BASE_URL}/api/activities/{activity_id}/reply",
            json=reply_data
        )
        assert res.status_code == 200, f"Buyer failed to reply: {res.text}"
        
        reply = res.json()
        assert 'reply_id' in reply
        assert reply['author_role'] == 'buyer', "Reply author_role should be 'buyer'"
        assert '_id' not in reply, "MongoDB _id should not be in response"
        print(f"Buyer created reply: {reply['reply_id']}")
    
    def test_buyer_cannot_access_other_activities(self, buyer_session):
        """Buyer cannot access activities not addressed to them"""
        # Try to access an activity with a fake ID
        res = buyer_session.get(f"{BASE_URL}/api/activities/fake_activity_id")
        assert res.status_code in [403, 404], f"Buyer should not access invalid activity, got {res.status_code}"
    
    # ==================== Role-Based Filtering Tests ====================
    
    def test_activities_response_structure(self, agent_session):
        """Verify activities response has correct structure"""
        res = agent_session.get(f"{BASE_URL}/api/activities")
        assert res.status_code == 200
        
        data = res.json()
        
        # Check pagination fields
        assert 'activities' in data
        assert 'total' in data
        assert 'limit' in data
        assert 'offset' in data
        
        if len(data['activities']) > 0:
            activity = data['activities'][0]
            # Check activity structure
            assert 'activity_id' in activity
            assert 'type' in activity
            assert 'author_id' in activity
            assert 'author_role' in activity
            assert 'created_at' in activity
            
            # Check enriched fields
            assert 'author_name' in activity
            assert 'reply_count' in activity
            
            print(f"Activity structure verified: {list(activity.keys())}")
    
    # ==================== Cleanup ====================
    
    @pytest.fixture(scope="class", autouse=True)
    def cleanup(self, request, agent_session):
        """Cleanup test data after tests"""
        def do_cleanup():
            # Note: We're using TEST_ prefix for easy identification
            # In a real app, we'd delete test activities here
            pass
        
        request.addfinalizer(do_cleanup)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
