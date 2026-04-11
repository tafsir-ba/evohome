"""
Phase 1 Canonical Rebuild - Backend API Tests

Tests all 5 Phase 1 modules (Unit, Project, Timeline, TimelineStep, Client)
with V2 routes and canonical services.

Key validations:
1. All CRUD operations work correctly
2. is_demo field MUST NOT appear in any response
3. Timeline AI extraction endpoints are INTENTIONALLY REMOVED
"""
import pytest
import requests
import os
import json

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://evo-access.preview.emergentagent.com').rstrip('/')

# Test credentials
TEST_EMAIL = "e2e@evohome-test.com"
TEST_PASSWORD = "Test2026!"


class TestHealthEndpoints:
    """Health and readiness checks"""
    
    def test_health_endpoint(self):
        """GET /api/health - liveness probe"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200, f"Health check failed: {response.text}"
        data = response.json()
        assert data.get("status") == "alive"
        print(f"✓ Health check passed: {data}")
    
    def test_ready_endpoint(self):
        """GET /api/ready - readiness probe"""
        response = requests.get(f"{BASE_URL}/api/ready")
        assert response.status_code == 200, f"Readiness check failed: {response.text}"
        data = response.json()
        assert data.get("status") == "ready"
        assert data.get("database") == "ok"
        print(f"✓ Readiness check passed: {data}")


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for test agent"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    if response.status_code != 200:
        pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")
    data = response.json()
    token = data.get("token")
    if not token:
        pytest.skip("No token in login response")
    print(f"✓ Authenticated as {TEST_EMAIL}")
    return token


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Headers with auth token"""
    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }


def assert_no_is_demo(data, context=""):
    """Helper to verify is_demo is NOT in response"""
    if isinstance(data, dict):
        assert "is_demo" not in data, f"is_demo found in {context}: {data.keys()}"
        for key, value in data.items():
            assert_no_is_demo(value, f"{context}.{key}")
    elif isinstance(data, list):
        for i, item in enumerate(data):
            assert_no_is_demo(item, f"{context}[{i}]")


class TestProjectsV2:
    """Project CRUD tests - projects_v2.py"""
    
    def test_list_projects(self, auth_headers):
        """GET /api/projects - list projects for agent"""
        response = requests.get(f"{BASE_URL}/api/projects", headers=auth_headers)
        assert response.status_code == 200, f"List projects failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Expected list of projects"
        assert_no_is_demo(data, "projects_list")
        print(f"✓ Listed {len(data)} projects (no is_demo)")
    
    def test_create_project(self, auth_headers):
        """POST /api/projects - create project"""
        payload = {
            "name": "TEST_Phase1_Project",
            "address": "123 Test Street",
            "description": "Test project for Phase 1 canonical rebuild"
        }
        response = requests.post(f"{BASE_URL}/api/projects", headers=auth_headers, json=payload)
        assert response.status_code == 200, f"Create project failed: {response.text}"
        data = response.json()
        assert data.get("name") == payload["name"]
        assert data.get("project_id"), "No project_id in response"
        assert_no_is_demo(data, "created_project")
        print(f"✓ Created project: {data.get('project_id')} (no is_demo)")
        return data.get("project_id")
    
    def test_update_project(self, auth_headers):
        """PUT /api/projects/{id} - update project"""
        # First create a project
        create_resp = requests.post(f"{BASE_URL}/api/projects", headers=auth_headers, json={
            "name": "TEST_Update_Project"
        })
        assert create_resp.status_code == 200
        project_id = create_resp.json().get("project_id")
        
        # Update it
        update_payload = {"name": "TEST_Updated_Project", "status": "active"}
        response = requests.put(f"{BASE_URL}/api/projects/{project_id}", headers=auth_headers, json=update_payload)
        assert response.status_code == 200, f"Update project failed: {response.text}"
        data = response.json()
        assert data.get("name") == "TEST_Updated_Project"
        assert_no_is_demo(data, "updated_project")
        print(f"✓ Updated project: {project_id} (no is_demo)")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/projects/{project_id}", headers=auth_headers)
    
    def test_delete_project_with_clients_fails(self, auth_headers):
        """DELETE /api/projects/{id} - should fail if clients linked"""
        # Create project
        create_resp = requests.post(f"{BASE_URL}/api/projects", headers=auth_headers, json={
            "name": "TEST_Delete_Project"
        })
        assert create_resp.status_code == 200
        project_id = create_resp.json().get("project_id")
        
        # Create client linked to project
        client_resp = requests.post(f"{BASE_URL}/api/clients", headers=auth_headers, json={
            "name": "TEST_Linked_Client",
            "project_id": project_id
        })
        assert client_resp.status_code == 200
        client_id = client_resp.json().get("client_id")
        
        # Try to delete project - should fail
        delete_resp = requests.delete(f"{BASE_URL}/api/projects/{project_id}", headers=auth_headers)
        assert delete_resp.status_code == 400, f"Expected 400, got {delete_resp.status_code}"
        assert "linked client" in delete_resp.json().get("detail", "").lower()
        print(f"✓ Delete project with clients correctly blocked")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/clients/{client_id}", headers=auth_headers)
        requests.delete(f"{BASE_URL}/api/projects/{project_id}", headers=auth_headers)
    
    def test_delete_project_success(self, auth_headers):
        """DELETE /api/projects/{id} - delete project without clients"""
        # Create project
        create_resp = requests.post(f"{BASE_URL}/api/projects", headers=auth_headers, json={
            "name": "TEST_Delete_Success_Project"
        })
        assert create_resp.status_code == 200
        project_id = create_resp.json().get("project_id")
        
        # Delete it
        delete_resp = requests.delete(f"{BASE_URL}/api/projects/{project_id}", headers=auth_headers)
        assert delete_resp.status_code == 200, f"Delete project failed: {delete_resp.text}"
        print(f"✓ Deleted project: {project_id}")


class TestClientsV2:
    """Client CRUD tests - clients_v2.py"""
    
    def test_list_clients(self, auth_headers):
        """GET /api/clients - list clients"""
        response = requests.get(f"{BASE_URL}/api/clients", headers=auth_headers)
        assert response.status_code == 200, f"List clients failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Expected list of clients"
        assert_no_is_demo(data, "clients_list")
        print(f"✓ Listed {len(data)} clients (no is_demo)")
    
    def test_create_client(self, auth_headers):
        """POST /api/clients - create client"""
        payload = {
            "name": "TEST_Phase1_Client",
            "email": "test.client@example.com",
            "phone": "+1234567890"
        }
        response = requests.post(f"{BASE_URL}/api/clients", headers=auth_headers, json=payload)
        assert response.status_code == 200, f"Create client failed: {response.text}"
        data = response.json()
        assert data.get("name") == payload["name"]
        assert data.get("client_id"), "No client_id in response"
        assert_no_is_demo(data, "created_client")
        print(f"✓ Created client: {data.get('client_id')} (no is_demo)")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/clients/{data.get('client_id')}", headers=auth_headers)
    
    def test_get_client(self, auth_headers):
        """GET /api/clients/{id} - get client detail"""
        # Create client first
        create_resp = requests.post(f"{BASE_URL}/api/clients", headers=auth_headers, json={
            "name": "TEST_Get_Client"
        })
        assert create_resp.status_code == 200
        client_id = create_resp.json().get("client_id")
        
        # Get client
        response = requests.get(f"{BASE_URL}/api/clients/{client_id}", headers=auth_headers)
        assert response.status_code == 200, f"Get client failed: {response.text}"
        data = response.json()
        assert data.get("client_id") == client_id
        assert_no_is_demo(data, "get_client")
        print(f"✓ Got client: {client_id} (no is_demo)")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/clients/{client_id}", headers=auth_headers)
    
    def test_update_client(self, auth_headers):
        """PUT /api/clients/{id} - update client"""
        # Create client
        create_resp = requests.post(f"{BASE_URL}/api/clients", headers=auth_headers, json={
            "name": "TEST_Update_Client"
        })
        assert create_resp.status_code == 200
        client_id = create_resp.json().get("client_id")
        
        # Update
        update_payload = {"name": "TEST_Updated_Client", "email": "updated@example.com"}
        response = requests.put(f"{BASE_URL}/api/clients/{client_id}", headers=auth_headers, json=update_payload)
        assert response.status_code == 200, f"Update client failed: {response.text}"
        data = response.json()
        assert data.get("name") == "TEST_Updated_Client"
        assert_no_is_demo(data, "updated_client")
        print(f"✓ Updated client: {client_id} (no is_demo)")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/clients/{client_id}", headers=auth_headers)
    
    def test_delete_client(self, auth_headers):
        """DELETE /api/clients/{id} - delete client"""
        # Create client
        create_resp = requests.post(f"{BASE_URL}/api/clients", headers=auth_headers, json={
            "name": "TEST_Delete_Client"
        })
        assert create_resp.status_code == 200
        client_id = create_resp.json().get("client_id")
        
        # Delete
        response = requests.delete(f"{BASE_URL}/api/clients/{client_id}", headers=auth_headers)
        assert response.status_code == 200, f"Delete client failed: {response.text}"
        print(f"✓ Deleted client: {client_id}")


class TestUnitsV2:
    """Unit CRUD tests - units.py"""
    
    @pytest.fixture
    def test_project(self, auth_headers):
        """Create a test project for unit tests"""
        resp = requests.post(f"{BASE_URL}/api/projects", headers=auth_headers, json={
            "name": "TEST_Units_Project"
        })
        assert resp.status_code == 200
        project_id = resp.json().get("project_id")
        yield project_id
        # Cleanup
        requests.delete(f"{BASE_URL}/api/projects/{project_id}", headers=auth_headers)
    
    def test_list_units(self, auth_headers, test_project):
        """GET /api/projects/{id}/units - list units"""
        response = requests.get(f"{BASE_URL}/api/projects/{test_project}/units", headers=auth_headers)
        assert response.status_code == 200, f"List units failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Expected list of units"
        assert_no_is_demo(data, "units_list")
        print(f"✓ Listed {len(data)} units (no is_demo)")
    
    def test_create_unit(self, auth_headers, test_project):
        """POST /api/projects/{id}/units - create unit"""
        payload = {"unit_reference": "TEST_Unit_A1", "notes": "Test unit"}
        response = requests.post(f"{BASE_URL}/api/projects/{test_project}/units", headers=auth_headers, json=payload)
        assert response.status_code == 200, f"Create unit failed: {response.text}"
        data = response.json()
        assert data.get("unit_reference") == payload["unit_reference"]
        assert data.get("unit_id"), "No unit_id in response"
        assert_no_is_demo(data, "created_unit")
        print(f"✓ Created unit: {data.get('unit_id')} (no is_demo)")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/units/{data.get('unit_id')}", headers=auth_headers)
    
    def test_get_unit(self, auth_headers, test_project):
        """GET /api/units/{id} - get unit"""
        # Create unit
        create_resp = requests.post(f"{BASE_URL}/api/projects/{test_project}/units", headers=auth_headers, json={
            "unit_reference": "TEST_Get_Unit"
        })
        assert create_resp.status_code == 200
        unit_id = create_resp.json().get("unit_id")
        
        # Get unit
        response = requests.get(f"{BASE_URL}/api/units/{unit_id}", headers=auth_headers)
        assert response.status_code == 200, f"Get unit failed: {response.text}"
        data = response.json()
        assert data.get("unit_id") == unit_id
        assert_no_is_demo(data, "get_unit")
        print(f"✓ Got unit: {unit_id} (no is_demo)")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/units/{unit_id}", headers=auth_headers)
    
    def test_update_unit(self, auth_headers, test_project):
        """PUT /api/units/{id} - update unit"""
        # Create unit
        create_resp = requests.post(f"{BASE_URL}/api/projects/{test_project}/units", headers=auth_headers, json={
            "unit_reference": "TEST_Update_Unit"
        })
        assert create_resp.status_code == 200
        unit_id = create_resp.json().get("unit_id")
        
        # Update
        update_payload = {"unit_reference": "TEST_Updated_Unit", "notes": "Updated notes"}
        response = requests.put(f"{BASE_URL}/api/units/{unit_id}", headers=auth_headers, json=update_payload)
        assert response.status_code == 200, f"Update unit failed: {response.text}"
        data = response.json()
        assert data.get("unit_reference") == "TEST_Updated_Unit"
        assert_no_is_demo(data, "updated_unit")
        print(f"✓ Updated unit: {unit_id} (no is_demo)")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/units/{unit_id}", headers=auth_headers)
    
    def test_delete_unit(self, auth_headers, test_project):
        """DELETE /api/units/{id} - delete unit"""
        # Create unit
        create_resp = requests.post(f"{BASE_URL}/api/projects/{test_project}/units", headers=auth_headers, json={
            "unit_reference": "TEST_Delete_Unit"
        })
        assert create_resp.status_code == 200
        unit_id = create_resp.json().get("unit_id")
        
        # Delete
        response = requests.delete(f"{BASE_URL}/api/units/{unit_id}", headers=auth_headers)
        assert response.status_code == 200, f"Delete unit failed: {response.text}"
        print(f"✓ Deleted unit: {unit_id}")


class TestTimelinesV2:
    """Timeline CRUD tests - timelines_v2.py"""
    
    @pytest.fixture
    def test_project(self, auth_headers):
        """Create a test project for timeline tests"""
        resp = requests.post(f"{BASE_URL}/api/projects", headers=auth_headers, json={
            "name": "TEST_Timeline_Project"
        })
        assert resp.status_code == 200
        project_id = resp.json().get("project_id")
        yield project_id
        # Cleanup - delete any timelines first
        timeline_resp = requests.get(f"{BASE_URL}/api/project-timeline?project_id={project_id}", headers=auth_headers)
        if timeline_resp.status_code == 200:
            timeline_data = timeline_resp.json()
            if timeline_data.get("timeline") and timeline_data["timeline"].get("timeline_id"):
                requests.delete(f"{BASE_URL}/api/timeline/{timeline_data['timeline']['timeline_id']}", headers=auth_headers)
        requests.delete(f"{BASE_URL}/api/projects/{project_id}", headers=auth_headers)
    
    def test_create_manual_timeline(self, auth_headers, test_project):
        """POST /api/timeline/create - create manual timeline with steps"""
        payload = {
            "project_id": test_project,
            "name": "TEST_Timeline",
            "steps": [
                {"title": "Step 1", "description": "First step"},
                {"title": "Step 2", "description": "Second step"}
            ]
        }
        response = requests.post(f"{BASE_URL}/api/timeline/create", headers=auth_headers, json=payload)
        assert response.status_code == 200, f"Create timeline failed: {response.text}"
        data = response.json()
        assert "timeline" in data or "timeline_id" in data.get("timeline", {})
        assert_no_is_demo(data, "created_timeline")
        print(f"✓ Created timeline with steps (no is_demo)")
    
    def test_get_project_timeline(self, auth_headers, test_project):
        """GET /api/project-timeline?project_id=xxx - get enriched timeline"""
        # First create a timeline
        requests.post(f"{BASE_URL}/api/timeline/create", headers=auth_headers, json={
            "project_id": test_project,
            "name": "TEST_Get_Timeline",
            "steps": [{"title": "Test Step"}]
        })
        
        # Get timeline
        response = requests.get(f"{BASE_URL}/api/project-timeline?project_id={test_project}", headers=auth_headers)
        assert response.status_code == 200, f"Get timeline failed: {response.text}"
        data = response.json()
        assert "timeline" in data
        assert "steps" in data
        assert_no_is_demo(data, "project_timeline")
        print(f"✓ Got project timeline (no is_demo)")
    
    def test_delete_timeline_cascade(self, auth_headers, test_project):
        """DELETE /api/timeline/{id} - cascade delete timeline"""
        # Create timeline
        create_resp = requests.post(f"{BASE_URL}/api/timeline/create", headers=auth_headers, json={
            "project_id": test_project,
            "name": "TEST_Delete_Timeline",
            "steps": [{"title": "Step to delete"}]
        })
        assert create_resp.status_code == 200
        timeline_id = create_resp.json().get("timeline", {}).get("timeline_id")
        if not timeline_id:
            timeline_id = create_resp.json().get("timeline_id")
        
        # Delete
        response = requests.delete(f"{BASE_URL}/api/timeline/{timeline_id}", headers=auth_headers)
        assert response.status_code == 200, f"Delete timeline failed: {response.text}"
        print(f"✓ Deleted timeline: {timeline_id}")


class TestTimelineStepsV2:
    """Timeline step management tests - timelines_v2.py and steps_v2.py"""
    
    @pytest.fixture
    def test_timeline(self, auth_headers):
        """Create a test project with timeline"""
        # Create project
        proj_resp = requests.post(f"{BASE_URL}/api/projects", headers=auth_headers, json={
            "name": "TEST_Steps_Project"
        })
        assert proj_resp.status_code == 200
        project_id = proj_resp.json().get("project_id")
        
        # Create timeline
        tl_resp = requests.post(f"{BASE_URL}/api/timeline/create", headers=auth_headers, json={
            "project_id": project_id,
            "name": "TEST_Steps_Timeline",
            "steps": [{"title": "Initial Step"}]
        })
        assert tl_resp.status_code == 200
        timeline_data = tl_resp.json()
        timeline_id = timeline_data.get("timeline", {}).get("timeline_id")
        step_id = timeline_data.get("steps", [{}])[0].get("step_id") if timeline_data.get("steps") else None
        
        yield {"project_id": project_id, "timeline_id": timeline_id, "step_id": step_id}
        
        # Cleanup
        if timeline_id:
            requests.delete(f"{BASE_URL}/api/timeline/{timeline_id}", headers=auth_headers)
        requests.delete(f"{BASE_URL}/api/projects/{project_id}", headers=auth_headers)
    
    def test_update_step_status(self, auth_headers, test_timeline):
        """PATCH /api/timeline/steps/{id} - update step status"""
        step_id = test_timeline.get("step_id")
        if not step_id:
            pytest.skip("No step_id available")
        
        payload = {"status": "in_progress", "progress_percent": 50}
        response = requests.patch(f"{BASE_URL}/api/timeline/steps/{step_id}", headers=auth_headers, json=payload)
        assert response.status_code == 200, f"Update step failed: {response.text}"
        data = response.json()
        assert data.get("status") == "in_progress"
        assert_no_is_demo(data, "updated_step")
        print(f"✓ Updated step status (no is_demo)")
    
    def test_add_step_to_timeline(self, auth_headers, test_timeline):
        """POST /api/timeline/{id}/steps - add step to timeline"""
        timeline_id = test_timeline.get("timeline_id")
        if not timeline_id:
            pytest.skip("No timeline_id available")
        
        payload = {"title": "New Added Step", "description": "Added via API"}
        response = requests.post(f"{BASE_URL}/api/timeline/{timeline_id}/steps", headers=auth_headers, json=payload)
        assert response.status_code == 200, f"Add step failed: {response.text}"
        data = response.json()
        assert data.get("title") == "New Added Step"
        assert data.get("step_id"), "No step_id in response"
        assert_no_is_demo(data, "added_step")
        print(f"✓ Added step to timeline (no is_demo)")
    
    def test_delete_step(self, auth_headers, test_timeline):
        """DELETE /api/timeline/steps/{id} - delete step"""
        timeline_id = test_timeline.get("timeline_id")
        if not timeline_id:
            pytest.skip("No timeline_id available")
        
        # Add a step to delete
        add_resp = requests.post(f"{BASE_URL}/api/timeline/{timeline_id}/steps", headers=auth_headers, json={
            "title": "Step to Delete"
        })
        assert add_resp.status_code == 200
        step_id = add_resp.json().get("step_id")
        
        # Delete
        response = requests.delete(f"{BASE_URL}/api/timeline/steps/{step_id}", headers=auth_headers)
        assert response.status_code == 200, f"Delete step failed: {response.text}"
        print(f"✓ Deleted step: {step_id}")
    
    def test_list_steps_via_steps_v2(self, auth_headers, test_timeline):
        """GET /api/projects/{id}/steps - list steps via steps_v2 route"""
        project_id = test_timeline.get("project_id")
        response = requests.get(f"{BASE_URL}/api/projects/{project_id}/steps", headers=auth_headers)
        assert response.status_code == 200, f"List steps failed: {response.text}"
        data = response.json()
        assert "steps" in data
        assert "total" in data
        assert_no_is_demo(data, "steps_list")
        print(f"✓ Listed {data.get('total')} steps via steps_v2 (no is_demo)")


class TestTimelineTemplates:
    """Timeline template tests - timelines_v2.py"""
    
    def test_list_templates(self, auth_headers):
        """GET /api/timeline/templates - list templates"""
        response = requests.get(f"{BASE_URL}/api/timeline/templates", headers=auth_headers)
        assert response.status_code == 200, f"List templates failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Expected list of templates"
        assert_no_is_demo(data, "templates_list")
        print(f"✓ Listed {len(data)} templates (no is_demo)")
    
    def test_create_template(self, auth_headers):
        """POST /api/timeline/templates - create template"""
        payload = {
            "name": "TEST_Template",
            "steps": [
                {"title": "Template Step 1", "order_index": 0},
                {"title": "Template Step 2", "order_index": 1}
            ]
        }
        response = requests.post(f"{BASE_URL}/api/timeline/templates", headers=auth_headers, json=payload)
        assert response.status_code == 200, f"Create template failed: {response.text}"
        data = response.json()
        assert data.get("name") == "TEST_Template"
        assert data.get("template_id"), "No template_id in response"
        assert_no_is_demo(data, "created_template")
        print(f"✓ Created template: {data.get('template_id')} (no is_demo)")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/timeline/templates/{data.get('template_id')}", headers=auth_headers)
    
    def test_delete_template(self, auth_headers):
        """DELETE /api/timeline/templates/{id} - delete template"""
        # Create template
        create_resp = requests.post(f"{BASE_URL}/api/timeline/templates", headers=auth_headers, json={
            "name": "TEST_Delete_Template",
            "steps": [{"title": "Step", "order_index": 0}]
        })
        assert create_resp.status_code == 200
        template_id = create_resp.json().get("template_id")
        
        # Delete
        response = requests.delete(f"{BASE_URL}/api/timeline/templates/{template_id}", headers=auth_headers)
        assert response.status_code == 200, f"Delete template failed: {response.text}"
        print(f"✓ Deleted template: {template_id}")
    
    def test_apply_template(self, auth_headers):
        """POST /api/timeline/templates/{id}/apply?project_id=xxx - apply template"""
        # Create template
        tmpl_resp = requests.post(f"{BASE_URL}/api/timeline/templates", headers=auth_headers, json={
            "name": "TEST_Apply_Template",
            "steps": [{"title": "Applied Step", "order_index": 0}]
        })
        assert tmpl_resp.status_code == 200
        template_id = tmpl_resp.json().get("template_id")
        
        # Create project
        proj_resp = requests.post(f"{BASE_URL}/api/projects", headers=auth_headers, json={
            "name": "TEST_Apply_Template_Project"
        })
        assert proj_resp.status_code == 200
        project_id = proj_resp.json().get("project_id")
        
        # Apply template
        response = requests.post(f"{BASE_URL}/api/timeline/templates/{template_id}/apply?project_id={project_id}", headers=auth_headers)
        assert response.status_code == 200, f"Apply template failed: {response.text}"
        data = response.json()
        assert "timeline_id" in data or "message" in data
        assert_no_is_demo(data, "applied_template")
        print(f"✓ Applied template to project (no is_demo)")
        
        # Cleanup
        if data.get("timeline_id"):
            requests.delete(f"{BASE_URL}/api/timeline/{data.get('timeline_id')}", headers=auth_headers)
        requests.delete(f"{BASE_URL}/api/timeline/templates/{template_id}", headers=auth_headers)
        requests.delete(f"{BASE_URL}/api/projects/{project_id}", headers=auth_headers)


class TestDashboardEndpoints:
    """Dashboard composite endpoints - dashboard.py"""
    
    def test_agent_dashboard(self, auth_headers):
        """GET /api/agent/dashboard - agent dashboard composite"""
        response = requests.get(f"{BASE_URL}/api/agent/dashboard", headers=auth_headers)
        assert response.status_code == 200, f"Agent dashboard failed: {response.text}"
        data = response.json()
        assert "projects" in data
        assert "recent_work" in data
        assert_no_is_demo(data, "agent_dashboard")
        print(f"✓ Got agent dashboard (no is_demo)")
    
    def test_project_context(self, auth_headers):
        """GET /api/projects/{id}/context - dashboard project context"""
        # Create project
        proj_resp = requests.post(f"{BASE_URL}/api/projects", headers=auth_headers, json={
            "name": "TEST_Context_Project"
        })
        assert proj_resp.status_code == 200
        project_id = proj_resp.json().get("project_id")
        
        # Get context
        response = requests.get(f"{BASE_URL}/api/projects/{project_id}/context", headers=auth_headers)
        assert response.status_code == 200, f"Project context failed: {response.text}"
        data = response.json()
        assert "project" in data
        assert "clients" in data
        assert "units" in data
        assert_no_is_demo(data, "project_context")
        print(f"✓ Got project context (no is_demo)")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/projects/{project_id}", headers=auth_headers)


class TestLegacyTeamEndpoints:
    """Team endpoints still use legacy routes - projects.py"""
    
    def test_team_endpoint_exists(self, auth_headers):
        """GET /api/projects/{id}/team - team members (legacy route still works)"""
        # Create project
        proj_resp = requests.post(f"{BASE_URL}/api/projects", headers=auth_headers, json={
            "name": "TEST_Team_Project"
        })
        assert proj_resp.status_code == 200
        project_id = proj_resp.json().get("project_id")
        
        # Get team - should work (legacy route)
        response = requests.get(f"{BASE_URL}/api/projects/{project_id}/team", headers=auth_headers)
        # Accept 200 or 404 (no team members) - just verify route exists
        assert response.status_code in [200, 404], f"Team endpoint failed: {response.status_code}"
        print(f"✓ Team endpoint accessible (legacy route)")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/projects/{project_id}", headers=auth_headers)


class TestRemovedEndpoints:
    """Verify AI extraction endpoints are REMOVED"""
    
    def test_timeline_extract_removed(self, auth_headers):
        """POST /api/timeline/extract - should NOT exist"""
        response = requests.post(f"{BASE_URL}/api/timeline/extract", headers=auth_headers, json={})
        # Should be 404 or 405 (not found or method not allowed)
        assert response.status_code in [404, 405, 422], f"Timeline extract should be removed, got {response.status_code}"
        print(f"✓ Timeline extract endpoint correctly removed (status: {response.status_code})")
    
    def test_timeline_extractions_removed(self, auth_headers):
        """GET /api/timeline/extractions - should NOT exist"""
        response = requests.get(f"{BASE_URL}/api/timeline/extractions", headers=auth_headers)
        assert response.status_code in [404, 405], f"Timeline extractions should be removed, got {response.status_code}"
        print(f"✓ Timeline extractions endpoint correctly removed (status: {response.status_code})")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
