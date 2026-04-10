"""
Test suite for UpgradeFlow Project Stages (Timeline) Feature
Tests:
- GET /api/projects/{project_id}/stages - Get stages for buyer
- POST /api/projects/{project_id}/stages - Create new stage (agent only)
- PUT /api/projects/{project_id}/stages/{stage_id} - Update stage (agent only)
- DELETE /api/projects/{project_id}/stages/{stage_id} - Delete stage (agent only)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://invoice-track-20.preview.emergentagent.com')

class TestProjectStagesAPI:
    """Project Stages API endpoint tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures - seed demo data and get auth tokens"""
        self.base_url = BASE_URL.rstrip('/')
        
        # Seed demo data first
        seed_response = requests.post(f"{self.base_url}/api/demo/seed")
        assert seed_response.status_code == 200, f"Failed to seed demo data: {seed_response.text}"
        
        # Login as demo agent
        agent_response = requests.post(f"{self.base_url}/api/auth/demo/agent")
        assert agent_response.status_code == 200, f"Failed agent login: {agent_response.text}"
        agent_data = agent_response.json()
        self.agent_token = agent_data.get('token')
        
        # Login as demo buyer 1
        buyer_response = requests.post(f"{self.base_url}/api/auth/demo/buyer?buyer_num=1")
        assert buyer_response.status_code == 200, f"Failed buyer login: {buyer_response.text}"
        buyer_data = buyer_response.json()
        self.buyer_token = buyer_data.get('token')
        
        # Store demo project ID
        self.demo_project_id = "demo_proj_001"
        
    def get_agent_headers(self):
        return {"Authorization": f"Bearer {self.agent_token}", "Content-Type": "application/json"}
    
    def get_buyer_headers(self):
        return {"Authorization": f"Bearer {self.buyer_token}", "Content-Type": "application/json"}
    
    # ==================== BUYER TESTS ====================
    
    def test_buyer_can_get_project_stages(self):
        """Test buyer can retrieve project stages (read-only)"""
        response = requests.get(
            f"{self.base_url}/api/projects/{self.demo_project_id}/stages",
            headers=self.get_buyer_headers()
        )
        
        assert response.status_code == 200, f"Failed to get stages: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "project" in data, "Response should contain project info"
        assert "stages" in data, "Response should contain stages array"
        
        # Verify project info
        project = data["project"]
        assert project["project_id"] == self.demo_project_id
        assert project["name"] == "Residenza Lago Vista"
        
        # Verify stages
        stages = data["stages"]
        assert len(stages) == 6, f"Expected 6 demo stages, got {len(stages)}"
        
        # Verify stage structure
        first_stage = stages[0]
        assert "stage_id" in first_stage
        assert "name" in first_stage
        assert "status" in first_stage
        assert "planned_start" in first_stage
        assert "planned_end" in first_stage
        assert "progress_percent" in first_stage
        
        print(f"✅ Buyer can get project stages - {len(stages)} stages returned")
    
    def test_stages_are_ordered_correctly(self):
        """Test that stages are returned in correct order"""
        response = requests.get(
            f"{self.base_url}/api/projects/{self.demo_project_id}/stages",
            headers=self.get_buyer_headers()
        )
        
        assert response.status_code == 200
        stages = response.json()["stages"]
        
        # Verify order by 'order' field
        expected_order = ["Permits & Approvals", "Foundation", "Structure", 
                        "MEP Rough-In", "Interior Finishes", "Final Handover"]
        actual_names = [s["name"] for s in stages]
        assert actual_names == expected_order, f"Stages not in correct order: {actual_names}"
        
        # Verify order numbers are sequential
        for i, stage in enumerate(stages):
            assert stage["order"] == i + 1, f"Stage {stage['name']} has incorrect order"
        
        print("✅ Stages are correctly ordered")
    
    def test_stages_have_correct_statuses(self):
        """Test that demo stages have expected statuses"""
        response = requests.get(
            f"{self.base_url}/api/projects/{self.demo_project_id}/stages",
            headers=self.get_buyer_headers()
        )
        
        assert response.status_code == 200
        stages = response.json()["stages"]
        
        # Check expected statuses
        expected_statuses = {
            "Permits & Approvals": "completed",
            "Foundation": "completed",
            "Structure": "in_progress",
            "MEP Rough-In": "upcoming",
            "Interior Finishes": "upcoming",
            "Final Handover": "upcoming"
        }
        
        for stage in stages:
            expected = expected_statuses.get(stage["name"])
            assert stage["status"] == expected, f"{stage['name']} has status {stage['status']}, expected {expected}"
        
        print("✅ Stages have correct statuses")
    
    def test_buyer_cannot_create_stage(self):
        """Test that buyer cannot create stages"""
        response = requests.post(
            f"{self.base_url}/api/projects/{self.demo_project_id}/stages",
            headers=self.get_buyer_headers(),
            json={
                "name": "Test Stage",
                "order": 7,
                "planned_start": "2026-03-01",
                "planned_end": "2026-03-31"
            }
        )
        
        # Should return 403 Forbidden
        assert response.status_code == 403, f"Buyer should not be able to create stages: {response.status_code}"
        print("✅ Buyer correctly denied stage creation")
    
    def test_buyer_cannot_update_stage(self):
        """Test that buyer cannot update stages"""
        response = requests.put(
            f"{self.base_url}/api/projects/{self.demo_project_id}/stages/demo_stage_001",
            headers=self.get_buyer_headers(),
            json={"status": "in_progress"}
        )
        
        # Should return 403 Forbidden
        assert response.status_code == 403, f"Buyer should not be able to update stages: {response.status_code}"
        print("✅ Buyer correctly denied stage update")
    
    def test_buyer_cannot_delete_stage(self):
        """Test that buyer cannot delete stages"""
        response = requests.delete(
            f"{self.base_url}/api/projects/{self.demo_project_id}/stages/demo_stage_001",
            headers=self.get_buyer_headers()
        )
        
        # Should return 403 Forbidden
        assert response.status_code == 403, f"Buyer should not be able to delete stages: {response.status_code}"
        print("✅ Buyer correctly denied stage deletion")
    
    # ==================== AGENT TESTS ====================
    
    def test_agent_can_get_project_stages(self):
        """Test agent can retrieve project stages"""
        response = requests.get(
            f"{self.base_url}/api/projects/{self.demo_project_id}/stages",
            headers=self.get_agent_headers()
        )
        
        assert response.status_code == 200, f"Failed to get stages: {response.text}"
        data = response.json()
        
        assert "project" in data
        assert "stages" in data
        assert len(data["stages"]) == 6
        
        print("✅ Agent can get project stages")
    
    def test_agent_can_create_stage(self):
        """Test agent can create a new stage"""
        new_stage = {
            "name": "TEST_Quality Inspection",
            "description": "Final quality inspection before handover",
            "order": 7,
            "planned_start": "2026-04-01",
            "planned_end": "2026-04-15"
        }
        
        response = requests.post(
            f"{self.base_url}/api/projects/{self.demo_project_id}/stages",
            headers=self.get_agent_headers(),
            json=new_stage
        )
        
        assert response.status_code == 200, f"Failed to create stage: {response.text}"
        created = response.json()
        
        # Verify created stage data
        assert "stage_id" in created
        assert created["name"] == new_stage["name"]
        assert created["description"] == new_stage["description"]
        assert created["order"] == 7
        assert created["status"] == "upcoming"
        assert created["progress_percent"] == 0
        
        self.created_stage_id = created["stage_id"]
        
        # Verify by GET
        get_response = requests.get(
            f"{self.base_url}/api/projects/{self.demo_project_id}/stages",
            headers=self.get_agent_headers()
        )
        assert get_response.status_code == 200
        stages = get_response.json()["stages"]
        assert len(stages) == 7, "Should now have 7 stages"
        
        print(f"✅ Agent can create stage: {created['stage_id']}")
        
        # Clean up - delete the test stage
        requests.delete(
            f"{self.base_url}/api/projects/{self.demo_project_id}/stages/{created['stage_id']}",
            headers=self.get_agent_headers()
        )
    
    def test_agent_can_update_stage_status(self):
        """Test agent can update stage status"""
        # Create a test stage first
        create_response = requests.post(
            f"{self.base_url}/api/projects/{self.demo_project_id}/stages",
            headers=self.get_agent_headers(),
            json={
                "name": "TEST_Update Stage",
                "order": 8,
                "planned_start": "2026-05-01",
                "planned_end": "2026-05-31"
            }
        )
        assert create_response.status_code == 200
        stage_id = create_response.json()["stage_id"]
        
        # Update the stage status
        update_response = requests.put(
            f"{self.base_url}/api/projects/{self.demo_project_id}/stages/{stage_id}",
            headers=self.get_agent_headers(),
            json={
                "status": "in_progress",
                "progress_percent": 25,
                "notes": "Work has begun",
                "actual_start": "2026-05-02"
            }
        )
        
        assert update_response.status_code == 200, f"Failed to update stage: {update_response.text}"
        updated = update_response.json()
        
        # Verify updates
        assert updated["status"] == "in_progress"
        assert updated["progress_percent"] == 25
        assert updated["notes"] == "Work has begun"
        assert updated["actual_start"] == "2026-05-02"
        
        print("✅ Agent can update stage status and progress")
        
        # Clean up
        requests.delete(
            f"{self.base_url}/api/projects/{self.demo_project_id}/stages/{stage_id}",
            headers=self.get_agent_headers()
        )
    
    def test_agent_can_update_stage_dates(self):
        """Test agent can update stage planned and actual dates"""
        # Update demo stage 004 (MEP Rough-In)
        update_response = requests.put(
            f"{self.base_url}/api/projects/{self.demo_project_id}/stages/demo_stage_004",
            headers=self.get_agent_headers(),
            json={
                "planned_start": "2026-02-01",
                "planned_end": "2026-02-28",
                "notes": "Updated schedule"
            }
        )
        
        assert update_response.status_code == 200, f"Failed to update stage: {update_response.text}"
        updated = update_response.json()
        
        assert updated["planned_start"] == "2026-02-01"
        assert updated["planned_end"] == "2026-02-28"
        assert updated["notes"] == "Updated schedule"
        
        print("✅ Agent can update stage dates")
    
    def test_agent_can_delete_stage(self):
        """Test agent can delete a stage"""
        # Create a test stage first
        create_response = requests.post(
            f"{self.base_url}/api/projects/{self.demo_project_id}/stages",
            headers=self.get_agent_headers(),
            json={
                "name": "TEST_Delete Stage",
                "order": 9,
                "planned_start": "2026-06-01",
                "planned_end": "2026-06-30"
            }
        )
        assert create_response.status_code == 200
        stage_id = create_response.json()["stage_id"]
        
        # Delete the stage
        delete_response = requests.delete(
            f"{self.base_url}/api/projects/{self.demo_project_id}/stages/{stage_id}",
            headers=self.get_agent_headers()
        )
        
        assert delete_response.status_code == 200, f"Failed to delete stage: {delete_response.text}"
        assert delete_response.json()["message"] == "Stage deleted"
        
        # Verify deletion
        get_response = requests.get(
            f"{self.base_url}/api/projects/{self.demo_project_id}/stages",
            headers=self.get_agent_headers()
        )
        stages = get_response.json()["stages"]
        stage_ids = [s["stage_id"] for s in stages]
        assert stage_id not in stage_ids, "Stage should be deleted"
        
        print("✅ Agent can delete stage")
    
    def test_delete_nonexistent_stage_returns_404(self):
        """Test deleting non-existent stage returns 404"""
        response = requests.delete(
            f"{self.base_url}/api/projects/{self.demo_project_id}/stages/nonexistent_stage",
            headers=self.get_agent_headers()
        )
        
        assert response.status_code == 404, f"Expected 404 for non-existent stage: {response.status_code}"
        print("✅ Delete non-existent stage returns 404")
    
    def test_update_nonexistent_stage_returns_404(self):
        """Test updating non-existent stage returns 404"""
        response = requests.put(
            f"{self.base_url}/api/projects/{self.demo_project_id}/stages/nonexistent_stage",
            headers=self.get_agent_headers(),
            json={"status": "completed"}
        )
        
        assert response.status_code == 404, f"Expected 404 for non-existent stage: {response.status_code}"
        print("✅ Update non-existent stage returns 404")
    
    # ==================== EDGE CASES ====================
    
    def test_unauthorized_access_to_stages(self):
        """Test that unauthenticated requests are rejected"""
        response = requests.get(
            f"{self.base_url}/api/projects/{self.demo_project_id}/stages"
        )
        
        assert response.status_code == 401, f"Expected 401 for unauthorized: {response.status_code}"
        print("✅ Unauthorized access correctly rejected")
    
    def test_invalid_project_id_returns_404(self):
        """Test that invalid project ID returns 404"""
        response = requests.get(
            f"{self.base_url}/api/projects/invalid_project/stages",
            headers=self.get_agent_headers()
        )
        
        assert response.status_code == 404, f"Expected 404 for invalid project: {response.status_code}"
        print("✅ Invalid project ID returns 404")


class TestProjectsAPI:
    """Test projects endpoint for dropdown functionality"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures"""
        self.base_url = BASE_URL.rstrip('/')
        
        # Seed demo data
        requests.post(f"{self.base_url}/api/demo/seed")
        
        # Login as demo agent
        agent_response = requests.post(f"{self.base_url}/api/auth/demo/agent")
        assert agent_response.status_code == 200
        self.agent_token = agent_response.json().get('token')
    
    def get_agent_headers(self):
        return {"Authorization": f"Bearer {self.agent_token}", "Content-Type": "application/json"}
    
    def test_agent_can_get_projects(self):
        """Test agent can get projects list for dropdown"""
        response = requests.get(
            f"{self.base_url}/api/projects",
            headers=self.get_agent_headers()
        )
        
        assert response.status_code == 200, f"Failed to get projects: {response.text}"
        projects = response.json()
        
        assert isinstance(projects, list)
        assert len(projects) >= 1, "Should have at least 1 demo project"
        
        # Verify project structure
        project = projects[0]
        assert "project_id" in project
        assert "name" in project
        assert "address" in project
        
        print(f"✅ Agent can get projects list - {len(projects)} projects")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
