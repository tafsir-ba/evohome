"""
Test Activity Feed Performance Optimization (Iteration 19)

Tests the batch_enrich_activities() optimization:
- Verifies all enrichment fields are present (author_name, project_name, recipients with client_name, reply_count)
- Verifies response shape {activities, total, limit, offset}
- Verifies individual activity detail endpoint still works with full enrichment
- Measures response time (should be under 3 seconds)
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestActivitiesPerformanceOptimization:
    """Test Activity Feed batch enrichment optimization"""
    
    @pytest.fixture(scope="class")
    def agent_session(self):
        """Get authenticated session for demo agent"""
        session = requests.Session()
        res = session.post(f"{BASE_URL}/api/auth/demo/agent")
        assert res.status_code == 200, f"Agent login failed: {res.text}"
        data = res.json()
        assert data.get('role') == 'agent', f"Expected agent role, got {data.get('role')}"
        print(f"Logged in as agent: {data.get('name')}")
        return session
    
    def test_activities_endpoint_response_shape(self, agent_session):
        """Verify /api/activities returns correct response shape {activities, total, limit, offset}"""
        res = agent_session.get(f"{BASE_URL}/api/activities")
        assert res.status_code == 200, f"Failed to get activities: {res.text}"
        
        data = res.json()
        
        # Verify response shape
        assert 'activities' in data, "Response must have 'activities' key"
        assert 'total' in data, "Response must have 'total' key"
        assert 'limit' in data, "Response must have 'limit' key"
        assert 'offset' in data, "Response must have 'offset' key"
        
        assert isinstance(data['activities'], list), "'activities' must be a list"
        assert isinstance(data['total'], int), "'total' must be an integer"
        assert isinstance(data['limit'], int), "'limit' must be an integer"
        assert isinstance(data['offset'], int), "'offset' must be an integer"
        
        print(f"Response shape verified: activities={len(data['activities'])}, total={data['total']}, limit={data['limit']}, offset={data['offset']}")
    
    def test_activities_enrichment_fields_present(self, agent_session):
        """Verify all enrichment fields are present in activity objects"""
        res = agent_session.get(f"{BASE_URL}/api/activities")
        assert res.status_code == 200, f"Failed to get activities: {res.text}"
        
        data = res.json()
        activities = data['activities']
        
        if len(activities) == 0:
            pytest.skip("No activities to test enrichment")
        
        # Check each activity has required enrichment fields
        for i, activity in enumerate(activities):
            # Core fields
            assert 'activity_id' in activity, f"Activity {i} missing activity_id"
            assert 'type' in activity, f"Activity {i} missing type"
            assert 'author_id' in activity, f"Activity {i} missing author_id"
            assert 'created_at' in activity, f"Activity {i} missing created_at"
            
            # Enrichment fields (from batch_enrich_activities)
            assert 'author_name' in activity, f"Activity {i} missing author_name (enrichment field)"
            assert activity['author_name'] is not None, f"Activity {i} has null author_name"
            assert activity['author_name'] != 'Unknown', f"Activity {i} has 'Unknown' author_name - enrichment may have failed"
            
            assert 'project_name' in activity, f"Activity {i} missing project_name (enrichment field)"
            # project_name can be None if no project
            
            assert 'recipients' in activity, f"Activity {i} missing recipients (enrichment field)"
            assert isinstance(activity['recipients'], list), f"Activity {i} recipients must be a list"
            
            # Check recipients have client_name
            for j, recipient in enumerate(activity['recipients']):
                assert 'client_id' in recipient, f"Activity {i} recipient {j} missing client_id"
                assert 'client_name' in recipient, f"Activity {i} recipient {j} missing client_name (enrichment field)"
            
            assert 'reply_count' in activity, f"Activity {i} missing reply_count (enrichment field)"
            assert isinstance(activity['reply_count'], int), f"Activity {i} reply_count must be an integer"
            
            # Optional: unit_reference if unit_id is present
            if activity.get('unit_id'):
                assert 'unit_reference' in activity, f"Activity {i} has unit_id but missing unit_reference"
        
        print(f"All {len(activities)} activities have correct enrichment fields")
    
    def test_activities_load_time_under_3_seconds(self, agent_session):
        """Verify activities endpoint responds in under 3 seconds (was 56s before optimization)"""
        start_time = time.time()
        res = agent_session.get(f"{BASE_URL}/api/activities")
        elapsed = time.time() - start_time
        
        assert res.status_code == 200, f"Failed to get activities: {res.text}"
        
        # Performance requirement: under 3 seconds
        assert elapsed < 3.0, f"Activities endpoint took {elapsed:.2f}s, expected under 3s"
        
        data = res.json()
        print(f"Activities endpoint responded in {elapsed:.2f}s with {len(data['activities'])} activities (total: {data['total']})")
    
    def test_activity_detail_endpoint_enrichment(self, agent_session):
        """Verify individual activity detail /api/activities/{id} returns full enrichment with replies"""
        # First get list of activities
        res = agent_session.get(f"{BASE_URL}/api/activities")
        assert res.status_code == 200
        data = res.json()
        
        if len(data['activities']) == 0:
            pytest.skip("No activities to test detail endpoint")
        
        activity_id = data['activities'][0]['activity_id']
        
        # Get activity detail
        detail_res = agent_session.get(f"{BASE_URL}/api/activities/{activity_id}")
        assert detail_res.status_code == 200, f"Failed to get activity detail: {detail_res.text}"
        
        activity = detail_res.json()
        
        # Verify enrichment fields
        assert 'author_name' in activity, "Detail missing author_name"
        assert 'project_name' in activity, "Detail missing project_name"
        assert 'recipients' in activity, "Detail missing recipients"
        assert 'reply_count' in activity, "Detail missing reply_count"
        
        # Detail view should include replies array
        assert 'replies' in activity, "Detail view should include 'replies' array"
        assert isinstance(activity['replies'], list), "'replies' must be a list"
        
        # Check replies have author_name enrichment
        for i, reply in enumerate(activity['replies']):
            assert 'reply_id' in reply, f"Reply {i} missing reply_id"
            assert 'content' in reply, f"Reply {i} missing content"
            assert 'author_name' in reply, f"Reply {i} missing author_name (enrichment field)"
        
        print(f"Activity detail {activity_id} has {len(activity['replies'])} replies with full enrichment")
    
    def test_activities_no_mongodb_id_leak(self, agent_session):
        """Verify MongoDB _id is not leaked in responses"""
        res = agent_session.get(f"{BASE_URL}/api/activities")
        assert res.status_code == 200
        data = res.json()
        
        for activity in data['activities']:
            assert '_id' not in activity, f"MongoDB _id leaked in activity {activity.get('activity_id')}"
            
            for recipient in activity.get('recipients', []):
                assert '_id' not in recipient, f"MongoDB _id leaked in recipient"
        
        print("No MongoDB _id leaks detected")
    
    def test_activities_pagination_works(self, agent_session):
        """Verify pagination parameters work correctly"""
        # Get first page
        res1 = agent_session.get(f"{BASE_URL}/api/activities?limit=5&offset=0")
        assert res1.status_code == 200
        data1 = res1.json()
        
        assert data1['limit'] == 5, f"Expected limit=5, got {data1['limit']}"
        assert data1['offset'] == 0, f"Expected offset=0, got {data1['offset']}"
        
        if data1['total'] > 5:
            # Get second page
            res2 = agent_session.get(f"{BASE_URL}/api/activities?limit=5&offset=5")
            assert res2.status_code == 200
            data2 = res2.json()
            
            assert data2['offset'] == 5, f"Expected offset=5, got {data2['offset']}"
            
            # Verify different activities on different pages
            ids1 = {a['activity_id'] for a in data1['activities']}
            ids2 = {a['activity_id'] for a in data2['activities']}
            assert ids1.isdisjoint(ids2), "Pagination returned duplicate activities"
            
            print(f"Pagination verified: page1={len(data1['activities'])}, page2={len(data2['activities'])}")
        else:
            print(f"Only {data1['total']} activities, skipping pagination overlap test")


class TestActivitiesCreateAndVerify:
    """Test creating activity and verifying enrichment"""
    
    @pytest.fixture(scope="class")
    def agent_session(self):
        """Get authenticated session for demo agent"""
        session = requests.Session()
        res = session.post(f"{BASE_URL}/api/auth/demo/agent")
        assert res.status_code == 200, f"Agent login failed: {res.text}"
        return session
    
    def test_create_activity_returns_enriched_response(self, agent_session):
        """Verify creating activity returns enriched response"""
        # Get project and clients
        proj_res = agent_session.get(f"{BASE_URL}/api/projects")
        assert proj_res.status_code == 200
        projects = proj_res.json()
        
        if len(projects) == 0:
            pytest.skip("No projects available")
        
        client_res = agent_session.get(f"{BASE_URL}/api/clients")
        assert client_res.status_code == 200
        clients = client_res.json()
        
        if len(clients) == 0:
            pytest.skip("No clients available")
        
        project_id = projects[0]['project_id']
        client_id = clients[0]['client_id']
        
        # Create activity
        form_data = {
            'type': 'message',
            'project_id': project_id,
            'client_ids': client_id,
            'title': 'TEST_Performance Test Activity',
            'content': 'Testing batch enrichment optimization'
        }
        
        res = agent_session.post(f"{BASE_URL}/api/activities", data=form_data)
        assert res.status_code == 200, f"Failed to create activity: {res.text}"
        
        activity = res.json()
        
        # Verify enrichment in create response
        assert 'activity_id' in activity
        assert 'author_name' in activity, "Create response missing author_name"
        assert 'project_name' in activity, "Create response missing project_name"
        assert 'recipients' in activity, "Create response missing recipients"
        assert 'reply_count' in activity, "Create response missing reply_count"
        
        # Store for cleanup
        self.__class__.created_activity_id = activity['activity_id']
        
        print(f"Created activity {activity['activity_id']} with enrichment: author={activity['author_name']}, project={activity['project_name']}")
    
    def test_created_activity_appears_in_feed(self, agent_session):
        """Verify created activity appears in feed with enrichment"""
        activity_id = getattr(self.__class__, 'created_activity_id', None)
        if not activity_id:
            pytest.skip("No activity created in previous test")
        
        res = agent_session.get(f"{BASE_URL}/api/activities")
        assert res.status_code == 200
        data = res.json()
        
        # Find our activity
        found = None
        for activity in data['activities']:
            if activity['activity_id'] == activity_id:
                found = activity
                break
        
        assert found is not None, f"Created activity {activity_id} not found in feed"
        
        # Verify enrichment
        assert found.get('author_name'), "Activity in feed missing author_name"
        assert found.get('recipients') is not None, "Activity in feed missing recipients"
        assert 'reply_count' in found, "Activity in feed missing reply_count"
        
        print(f"Activity {activity_id} found in feed with enrichment")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
