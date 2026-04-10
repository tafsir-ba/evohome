"""
Phase F: Deprecation Cleanup Validation Tests
==============================================
Tests to verify Phase F cleanup was successful:
1. Health endpoint works
2. Auth login with demo credentials
3. Projects endpoint returns data
4. Units endpoint uses canonical 'units' collection
5. /stages route should return 404 (REMOVED in Phase F)
6. /steps route works (canonical route)
7. project-timeline returns timeline_id, NO project_timeline_id
8. timeline/full returns timeline_id and steps
9. workflow/full returns timeline_id, steps, and activities
10. Clients endpoint works
11. Documents endpoint works
12. Agent dashboard returns projects
13. Agent stats returns stats object
14. No ObjectId serialization errors
15. No _id fields leaked in responses
"""

import pytest
import requests
import json
import os

# Use the public API URL for testing
BASE_URL = "https://evo-access.preview.emergentagent.com"

# Demo credentials from test_credentials.md
DEMO_EMAIL = "demo.agent@upgradeflow.com"
DEMO_PASSWORD = "demo123"

# Known project ID from previous tests
DEMO_PROJECT_ID = "demo_proj_001"


class TestPhaseF:
    """Phase F Deprecation Cleanup Validation Tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token for demo agent"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD}
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data, "No token in login response"
        return data["token"]
    
    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        """Get headers with auth token"""
        return {"Authorization": f"Bearer {auth_token}"}
    
    # ==================== BASIC HEALTH & AUTH ====================
    
    def test_01_health_endpoint(self):
        """Test GET /api/health returns healthy status"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200, f"Health check failed: {response.status_code}"
        data = response.json()
        assert data.get("status") == "healthy", f"Unexpected health status: {data}"
        print(f"PASS: Health endpoint returns {data}")
    
    def test_02_auth_login(self):
        """Test POST /api/auth/login with demo credentials returns JWT token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD}
        )
        assert response.status_code == 200, f"Login failed: {response.status_code} - {response.text}"
        data = response.json()
        assert "token" in data, "No token in response"
        assert len(data["token"]) > 0, "Token is empty"
        # Verify no _id leaked
        assert "_id" not in data, "_id leaked in login response"
        print(f"PASS: Login successful, token received (length: {len(data['token'])})")
    
    # ==================== PROJECTS & UNITS ====================
    
    def test_03_get_projects(self, auth_headers):
        """Test GET /api/projects returns project list (non-empty)"""
        response = requests.get(f"{BASE_URL}/api/projects", headers=auth_headers)
        assert response.status_code == 200, f"Get projects failed: {response.status_code}"
        data = response.json()
        assert isinstance(data, list), "Projects should be a list"
        assert len(data) > 0, "Projects list should not be empty"
        # Verify no _id leaked
        for project in data:
            assert "_id" not in project, f"_id leaked in project: {project.get('project_id')}"
        print(f"PASS: Got {len(data)} projects")
    
    def test_04_get_project_units(self, auth_headers):
        """Test GET /api/projects/{id}/units returns units from canonical 'units' collection"""
        response = requests.get(
            f"{BASE_URL}/api/projects/{DEMO_PROJECT_ID}/units",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Get units failed: {response.status_code}"
        data = response.json()
        assert isinstance(data, list), "Units should be a list"
        # Verify no _id leaked
        for unit in data:
            assert "_id" not in unit, f"_id leaked in unit: {unit.get('unit_id')}"
        print(f"PASS: Got {len(data)} units from canonical 'units' collection")
    
    # ==================== PHASE F: /stages REMOVED ====================
    
    def test_05_stages_route_removed(self, auth_headers):
        """Test GET /api/projects/{id}/stages should return 404 (route REMOVED in Phase F)"""
        response = requests.get(
            f"{BASE_URL}/api/projects/{DEMO_PROJECT_ID}/stages",
            headers=auth_headers
        )
        # Phase F removed /stages route - should return 404 or 405
        assert response.status_code in [404, 405, 422], \
            f"Expected 404/405 for removed /stages route, got {response.status_code}: {response.text}"
        print(f"PASS: /stages route correctly returns {response.status_code} (removed in Phase F)")
    
    # ==================== CANONICAL /steps ROUTE ====================
    
    def test_06_steps_route_works(self, auth_headers):
        """Test GET /api/projects/{id}/steps returns steps (canonical route)"""
        response = requests.get(
            f"{BASE_URL}/api/projects/{DEMO_PROJECT_ID}/steps",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Get steps failed: {response.status_code}"
        data = response.json()
        # Response should have project and stages keys
        assert "project" in data or "stages" in data, f"Unexpected response structure: {data.keys()}"
        # Verify no _id leaked
        if "stages" in data:
            for stage in data["stages"]:
                assert "_id" not in stage, f"_id leaked in stage"
        print(f"PASS: /steps route works, got {len(data.get('stages', []))} steps")
    
    # ==================== TIMELINE ENDPOINTS ====================
    
    def test_07_project_timeline_has_timeline_id(self, auth_headers):
        """Test GET /api/project-timeline?project_id={id} returns timeline_id, NO project_timeline_id"""
        response = requests.get(
            f"{BASE_URL}/api/project-timeline",
            params={"project_id": DEMO_PROJECT_ID},
            headers=auth_headers
        )
        assert response.status_code == 200, f"Get project-timeline failed: {response.status_code}"
        data = response.json()
        
        # Response structure is {timeline: {...}, steps: [...]}
        assert "timeline" in data, f"timeline object missing from response: {data.keys()}"
        timeline = data["timeline"]
        
        # Check for timeline_id presence in timeline object
        assert "timeline_id" in timeline, f"timeline_id missing from timeline object: {timeline.keys()}"
        
        # CRITICAL: project_timeline_id should NOT be present (Phase F cleanup)
        assert "project_timeline_id" not in timeline, \
            f"project_timeline_id should be removed but found in timeline object"
        assert "project_timeline_id" not in data, \
            f"project_timeline_id should be removed but found in response root"
        
        # Verify no _id leaked
        assert "_id" not in data, "_id leaked in response root"
        assert "_id" not in timeline, "_id leaked in timeline object"
        
        print(f"PASS: project-timeline has timeline_id={timeline['timeline_id']}, no project_timeline_id")
    
    def test_08_project_timeline_steps_have_timeline_id(self, auth_headers):
        """Test GET /api/project-timeline steps have timeline_id, NO project_timeline_id"""
        response = requests.get(
            f"{BASE_URL}/api/project-timeline",
            params={"project_id": DEMO_PROJECT_ID},
            headers=auth_headers
        )
        assert response.status_code == 200, f"Get project-timeline failed: {response.status_code}"
        data = response.json()
        
        steps = data.get("steps", [])
        for step in steps:
            # Each step should have timeline_id
            assert "timeline_id" in step, f"Step missing timeline_id: {step.get('step_id')}"
            # CRITICAL: project_timeline_id should NOT be present
            assert "project_timeline_id" not in step, \
                f"project_timeline_id found in step {step.get('step_id')}"
            # Verify no _id leaked
            assert "_id" not in step, f"_id leaked in step: {step.get('step_id')}"
        
        print(f"PASS: All {len(steps)} steps have timeline_id, no project_timeline_id")
    
    def test_09_timeline_full_endpoint(self, auth_headers):
        """Test GET /api/projects/{id}/timeline/full returns timeline_id and steps"""
        response = requests.get(
            f"{BASE_URL}/api/projects/{DEMO_PROJECT_ID}/timeline/full",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Get timeline/full failed: {response.status_code}"
        data = response.json()
        
        # Should have timeline_id (can be None if no timeline exists)
        assert "timeline_id" in data or data.get("timeline_id") is None, \
            f"timeline_id field missing from response"
        
        # Should have steps array
        assert "steps" in data, "steps field missing from response"
        
        # CRITICAL: No project_timeline_id anywhere
        assert "project_timeline_id" not in data, "project_timeline_id found in timeline/full"
        
        # Check steps for project_timeline_id
        for step in data.get("steps", []):
            assert "project_timeline_id" not in step, \
                f"project_timeline_id found in step {step.get('step_id')}"
            assert "_id" not in step, f"_id leaked in step"
        
        print(f"PASS: timeline/full has timeline_id={data.get('timeline_id')}, {len(data.get('steps', []))} steps")
    
    def test_10_workflow_full_endpoint(self, auth_headers):
        """Test GET /api/projects/{id}/workflow/full returns timeline_id, steps, and activities"""
        response = requests.get(
            f"{BASE_URL}/api/projects/{DEMO_PROJECT_ID}/workflow/full",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Get workflow/full failed: {response.status_code}"
        data = response.json()
        
        # Should have timeline_id
        assert "timeline_id" in data or data.get("timeline_id") is None, \
            "timeline_id field missing from response"
        
        # Should have steps and activities
        assert "steps" in data, "steps field missing from response"
        assert "activities" in data, "activities field missing from response"
        
        # CRITICAL: No project_timeline_id anywhere
        assert "project_timeline_id" not in data, "project_timeline_id found in workflow/full"
        
        # Check steps for project_timeline_id
        for step in data.get("steps", []):
            assert "project_timeline_id" not in step, \
                f"project_timeline_id found in step"
            assert "_id" not in step, "_id leaked in step"
        
        # Check activities for _id
        for activity in data.get("activities", []):
            assert "_id" not in activity, "_id leaked in activity"
        
        print(f"PASS: workflow/full has timeline_id={data.get('timeline_id')}, "
              f"{len(data.get('steps', []))} steps, {len(data.get('activities', []))} activities")
    
    # ==================== OTHER ENDPOINTS ====================
    
    def test_11_get_clients(self, auth_headers):
        """Test GET /api/clients returns client list"""
        response = requests.get(f"{BASE_URL}/api/clients", headers=auth_headers)
        assert response.status_code == 200, f"Get clients failed: {response.status_code}"
        data = response.json()
        assert isinstance(data, list), "Clients should be a list"
        # Verify no _id leaked
        for client in data:
            assert "_id" not in client, f"_id leaked in client: {client.get('client_id')}"
        print(f"PASS: Got {len(data)} clients")
    
    def test_12_get_documents(self, auth_headers):
        """Test GET /api/documents returns document list"""
        response = requests.get(f"{BASE_URL}/api/documents", headers=auth_headers)
        assert response.status_code == 200, f"Get documents failed: {response.status_code}"
        data = response.json()
        assert isinstance(data, list), "Documents should be a list"
        # Verify no _id leaked
        for doc in data:
            assert "_id" not in doc, f"_id leaked in document: {doc.get('document_id')}"
        print(f"PASS: Got {len(data)} documents")
    
    def test_13_agent_dashboard(self, auth_headers):
        """Test GET /api/agent/dashboard returns projects array"""
        response = requests.get(f"{BASE_URL}/api/agent/dashboard", headers=auth_headers)
        assert response.status_code == 200, f"Get agent dashboard failed: {response.status_code}"
        data = response.json()
        assert "projects" in data, "Dashboard should have projects field"
        assert isinstance(data["projects"], list), "projects should be a list"
        # Verify no _id leaked
        for project in data["projects"]:
            assert "_id" not in project, f"_id leaked in dashboard project"
        print(f"PASS: Agent dashboard has {len(data['projects'])} projects")
    
    def test_14_agent_stats(self, auth_headers):
        """Test GET /api/stats/agent returns stats object with total_clients"""
        response = requests.get(f"{BASE_URL}/api/stats/agent", headers=auth_headers)
        assert response.status_code == 200, f"Get agent stats failed: {response.status_code}"
        data = response.json()
        assert "total_clients" in data, "Stats should have total_clients field"
        # Verify no _id leaked
        assert "_id" not in data, "_id leaked in stats response"
        print(f"PASS: Agent stats has total_clients={data['total_clients']}")
    
    # ==================== DEEP VALIDATION ====================
    
    def test_15_no_objectid_serialization_errors(self, auth_headers):
        """Test that no endpoint returns ObjectId serialization errors"""
        endpoints = [
            "/api/health",
            "/api/projects",
            f"/api/projects/{DEMO_PROJECT_ID}/units",
            f"/api/projects/{DEMO_PROJECT_ID}/steps",
            f"/api/project-timeline?project_id={DEMO_PROJECT_ID}",
            f"/api/projects/{DEMO_PROJECT_ID}/timeline/full",
            f"/api/projects/{DEMO_PROJECT_ID}/workflow/full",
            "/api/clients",
            "/api/documents",
            "/api/agent/dashboard",
            "/api/stats/agent"
        ]
        
        errors = []
        for endpoint in endpoints:
            try:
                if "?" in endpoint:
                    url = f"{BASE_URL}{endpoint}"
                else:
                    url = f"{BASE_URL}{endpoint}"
                response = requests.get(url, headers=auth_headers)
                
                # Check for ObjectId serialization error in response
                if response.status_code == 500:
                    if "ObjectId" in response.text or "not JSON serializable" in response.text:
                        errors.append(f"{endpoint}: ObjectId serialization error")
                
                # Try to parse JSON - will fail if ObjectId not serialized
                try:
                    response.json()
                except json.JSONDecodeError as e:
                    errors.append(f"{endpoint}: JSON decode error - {str(e)}")
                    
            except Exception as e:
                errors.append(f"{endpoint}: {str(e)}")
        
        assert len(errors) == 0, f"ObjectId serialization errors found: {errors}"
        print(f"PASS: No ObjectId serialization errors in {len(endpoints)} endpoints")
    
    def test_16_no_id_fields_leaked(self, auth_headers):
        """Test that no _id fields are leaked in any JSON response"""
        endpoints_to_check = [
            ("/api/projects", "list"),
            (f"/api/projects/{DEMO_PROJECT_ID}/units", "list"),
            (f"/api/projects/{DEMO_PROJECT_ID}/steps", "dict"),
            (f"/api/project-timeline?project_id={DEMO_PROJECT_ID}", "dict"),
            (f"/api/projects/{DEMO_PROJECT_ID}/timeline/full", "dict"),
            (f"/api/projects/{DEMO_PROJECT_ID}/workflow/full", "dict"),
            ("/api/clients", "list"),
            ("/api/documents", "list"),
            ("/api/agent/dashboard", "dict"),
            ("/api/stats/agent", "dict")
        ]
        
        def check_for_id(obj, path=""):
            """Recursively check for _id in object"""
            issues = []
            if isinstance(obj, dict):
                if "_id" in obj:
                    issues.append(f"{path}._id found")
                for key, value in obj.items():
                    issues.extend(check_for_id(value, f"{path}.{key}"))
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    issues.extend(check_for_id(item, f"{path}[{i}]"))
            return issues
        
        all_issues = []
        for endpoint, resp_type in endpoints_to_check:
            try:
                url = f"{BASE_URL}{endpoint}"
                response = requests.get(url, headers=auth_headers)
                if response.status_code == 200:
                    data = response.json()
                    issues = check_for_id(data, endpoint)
                    all_issues.extend(issues)
            except Exception as e:
                all_issues.append(f"{endpoint}: Error - {str(e)}")
        
        assert len(all_issues) == 0, f"_id fields leaked: {all_issues}"
        print(f"PASS: No _id fields leaked in {len(endpoints_to_check)} endpoints")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
