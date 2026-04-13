"""
Backend tests for Timeline Step Add/Delete functionality
Features tested:
- POST /api/timeline/{timeline_id}/steps - Add a new step to an existing timeline
- DELETE /api/timeline/steps/{step_id} - Delete a step from timeline
"""

import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestTimelineStepCRUD:
    """Timeline Step Add/Delete tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: Get demo agent session token"""
        response = requests.post(f"{BASE_URL}/api/demo/enter", json={"persona": "agent", "fresh": False})
        assert response.status_code == 200, f"Demo auth failed: {response.text}"
        data = response.json()
        self.token = data.get('token')
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        # Demo timeline ID from test context
        self.timeline_id = "timeline_demo_001"
        self.project_id = "demo_proj_001"
    
    def test_1_get_existing_timeline(self):
        """Verify demo timeline exists with steps"""
        response = requests.get(
            f"{BASE_URL}/api/project-timeline",
            params={"project_id": self.project_id},
            headers=self.headers
        )
        assert response.status_code == 200, f"Failed to get timeline: {response.text}"
        data = response.json()
        
        # Verify timeline exists
        assert data.get('timeline') is not None, "Timeline should exist"
        timeline = data['timeline']
        timeline_id = timeline.get('timeline_id') or timeline.get('project_timeline_id')
        assert timeline_id is not None, "Timeline should have an ID"
        
        # Verify steps exist
        steps = data.get('steps', [])
        print(f"Found timeline {timeline_id} with {len(steps)} steps")
        assert len(steps) > 0, "Demo timeline should have existing steps"
    
    def test_2_add_step_to_timeline_success(self):
        """POST /api/timeline/{timeline_id}/steps creates a new step"""
        unique_suffix = uuid.uuid4().hex[:6]
        step_data = {
            "title": f"TEST_Step_{unique_suffix}",
            "description": "Test step added via API",
            "planned_date": "March 2026"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/timeline/{self.timeline_id}/steps",
            json=step_data,
            headers=self.headers
        )
        
        assert response.status_code == 200, f"Failed to add step: {response.text}"
        data = response.json()
        
        # Verify returned step data
        assert "step_id" in data, "Response should contain step_id"
        assert data.get('title') == step_data['title'], "Title should match"
        assert data.get('description') == step_data['description'], "Description should match"
        assert data.get('planned_date') == step_data['planned_date'], "Planned date should match"
        assert data.get('status') == "pending", "New step should have 'pending' status"
        
        # Store for cleanup
        self.created_step_id = data['step_id']
        print(f"Created step: {self.created_step_id}")
        
        # Verify step appears in timeline
        verify_response = requests.get(
            f"{BASE_URL}/api/project-timeline",
            params={"project_id": self.project_id},
            headers=self.headers
        )
        assert verify_response.status_code == 200
        verify_data = verify_response.json()
        steps = verify_data.get('steps', [])
        step_ids = [s['step_id'] for s in steps]
        assert data['step_id'] in step_ids, "New step should appear in timeline steps"
    
    def test_3_add_step_minimal_data(self):
        """POST /api/timeline/{timeline_id}/steps works with title only"""
        unique_suffix = uuid.uuid4().hex[:6]
        step_data = {
            "title": f"TEST_MinimalStep_{unique_suffix}"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/timeline/{self.timeline_id}/steps",
            json=step_data,
            headers=self.headers
        )
        
        assert response.status_code == 200, f"Failed to add minimal step: {response.text}"
        data = response.json()
        
        assert data.get('title') == step_data['title'], "Title should match"
        assert data.get('status') == "pending", "Status should be pending"
        assert "step_id" in data, "Should have step_id"
        
        # Store for later deletion test
        self.minimal_step_id = data['step_id']
        print(f"Created minimal step: {self.minimal_step_id}")
    
    def test_4_add_step_nonexistent_timeline(self):
        """POST /api/timeline/{timeline_id}/steps returns 404 for invalid timeline"""
        step_data = {"title": "Test Step"}
        
        response = requests.post(
            f"{BASE_URL}/api/timeline/nonexistent_timeline_xyz/steps",
            json=step_data,
            headers=self.headers
        )
        
        assert response.status_code == 404, f"Should return 404, got {response.status_code}"
        data = response.json()
        assert "not found" in data.get('detail', '').lower(), "Should indicate timeline not found"
    
    def test_5_add_step_order_index_increments(self):
        """New steps get incrementing order_index"""
        # Get current max order
        response = requests.get(
            f"{BASE_URL}/api/project-timeline",
            params={"project_id": self.project_id},
            headers=self.headers
        )
        assert response.status_code == 200
        steps = response.json().get('steps', [])
        max_order = max([s.get('order_index', 0) for s in steps]) if steps else 0
        
        # Add a new step
        unique_suffix = uuid.uuid4().hex[:6]
        step_data = {"title": f"TEST_OrderCheck_{unique_suffix}"}
        
        add_response = requests.post(
            f"{BASE_URL}/api/timeline/{self.timeline_id}/steps",
            json=step_data,
            headers=self.headers
        )
        
        assert add_response.status_code == 200
        new_step = add_response.json()
        
        # Verify order_index is higher than previous max
        assert new_step.get('order_index', 0) > max_order, \
            f"New step order_index ({new_step.get('order_index')}) should be > {max_order}"
        
        self.order_check_step_id = new_step['step_id']
        print(f"Created step with order_index {new_step.get('order_index')}")
    
    def test_6_delete_step_success(self):
        """DELETE /api/timeline/steps/{step_id} removes a step"""
        # First create a step to delete
        unique_suffix = uuid.uuid4().hex[:6]
        step_data = {"title": f"TEST_ToDelete_{unique_suffix}"}
        
        create_response = requests.post(
            f"{BASE_URL}/api/timeline/{self.timeline_id}/steps",
            json=step_data,
            headers=self.headers
        )
        assert create_response.status_code == 200
        step_id = create_response.json()['step_id']
        print(f"Created step to delete: {step_id}")
        
        # Now delete it
        delete_response = requests.delete(
            f"{BASE_URL}/api/timeline/steps/{step_id}",
            headers=self.headers
        )
        
        assert delete_response.status_code == 200, f"Delete failed: {delete_response.text}"
        data = delete_response.json()
        assert data.get('step_id') == step_id, "Should return deleted step_id"
        assert "deleted" in data.get('message', '').lower(), "Should confirm deletion"
        
        # Verify step no longer in timeline
        verify_response = requests.get(
            f"{BASE_URL}/api/project-timeline",
            params={"project_id": self.project_id},
            headers=self.headers
        )
        assert verify_response.status_code == 200
        steps = verify_response.json().get('steps', [])
        step_ids = [s['step_id'] for s in steps]
        assert step_id not in step_ids, "Deleted step should not appear in timeline"
        print(f"Verified step {step_id} was deleted")
    
    def test_7_delete_nonexistent_step(self):
        """DELETE /api/timeline/steps/{step_id} returns 404 for invalid step"""
        response = requests.delete(
            f"{BASE_URL}/api/timeline/steps/nonexistent_step_xyz",
            headers=self.headers
        )
        
        assert response.status_code == 404, f"Should return 404, got {response.status_code}"
        data = response.json()
        assert "not found" in data.get('detail', '').lower(), "Should indicate step not found"
    
    def test_8_delete_requires_auth(self):
        """DELETE /api/timeline/steps/{step_id} requires authentication"""
        response = requests.delete(
            f"{BASE_URL}/api/timeline/steps/some_step_id"
            # No auth headers
        )
        
        assert response.status_code == 401, f"Should return 401 without auth, got {response.status_code}"
    
    def test_9_add_step_requires_auth(self):
        """POST /api/timeline/{timeline_id}/steps requires authentication"""
        step_data = {"title": "Test Step"}
        
        response = requests.post(
            f"{BASE_URL}/api/timeline/{self.timeline_id}/steps",
            json=step_data
            # No auth headers
        )
        
        assert response.status_code == 401, f"Should return 401 without auth, got {response.status_code}"
    
    def test_10_cleanup_test_steps(self):
        """Cleanup: Delete any TEST_ prefixed steps created during tests"""
        # Get all steps
        response = requests.get(
            f"{BASE_URL}/api/project-timeline",
            params={"project_id": self.project_id},
            headers=self.headers
        )
        
        if response.status_code == 200:
            steps = response.json().get('steps', [])
            test_steps = [s for s in steps if s.get('title', '').startswith('TEST_')]
            
            deleted_count = 0
            for step in test_steps:
                delete_response = requests.delete(
                    f"{BASE_URL}/api/timeline/steps/{step['step_id']}",
                    headers=self.headers
                )
                if delete_response.status_code == 200:
                    deleted_count += 1
            
            print(f"Cleanup: deleted {deleted_count} test steps")
        
        assert True  # Cleanup always passes


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
