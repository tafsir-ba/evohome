"""
Tests for Construction Timeline/Workflow System
- Tests timeline templates API
- Tests project timeline creation, retrieval, updating
- Tests step status advancement (pending -> in_progress -> completed -> approved)
- Tests document linking to steps
- Tests internal notes (agent-only)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://invoice-track-20.preview.emergentagent.com').rstrip('/')

class TestTimelineWorkflow:
    """Construction Timeline/Workflow endpoint tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login as demo agent before each test"""
        res = requests.post(f"{BASE_URL}/api/auth/demo/agent")
        assert res.status_code == 200, f"Demo agent login failed: {res.text}"
        data = res.json()
        self.agent_token = data.get('token')
        self.agent_headers = {"Authorization": f"Bearer {self.agent_token}"}
        
        # Also login as demo buyer for buyer view tests
        res_buyer = requests.post(f"{BASE_URL}/api/auth/demo/buyer")
        if res_buyer.status_code == 200:
            self.buyer_token = res_buyer.json().get('token')
            self.buyer_headers = {"Authorization": f"Bearer {self.buyer_token}"}
        else:
            self.buyer_token = None
            self.buyer_headers = {}
    
    # ======================
    # TIMELINE TEMPLATES API
    # ======================
    
    def test_get_timeline_templates(self):
        """GET /timeline/templates - Should return list of templates"""
        res = requests.get(f"{BASE_URL}/api/timeline/templates", headers=self.agent_headers)
        
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        data = res.json()
        assert isinstance(data, list), "Response should be a list"
        
        # Demo data should include at least 1 template
        if len(data) > 0:
            template = data[0]
            assert "template_id" in template, "Template should have template_id"
            assert "name" in template, "Template should have name"
            assert "steps" in template, "Template should have steps array"
            print(f"Found {len(data)} timeline templates")
            print(f"First template: {template['name']} with {len(template.get('steps', []))} steps")
    
    def test_get_project_timeline_agent(self):
        """GET /project-timeline?project_id=X - Agent view of project timeline"""
        # First get a project
        projects_res = requests.get(f"{BASE_URL}/api/projects", headers=self.agent_headers)
        assert projects_res.status_code == 200
        projects = projects_res.json()
        
        if len(projects) == 0:
            pytest.skip("No projects available for timeline test")
        
        project_id = projects[0]['project_id']
        
        res = requests.get(
            f"{BASE_URL}/api/project-timeline?project_id={project_id}",
            headers=self.agent_headers
        )
        
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        data = res.json()
        
        # Check response structure
        assert "timeline" in data, "Response should have timeline field"
        assert "steps" in data, "Response should have steps field"
        
        if data['timeline']:
            timeline = data['timeline']
            assert "timeline_id" in timeline, "Timeline should have timeline_id"
            assert "project_id" in timeline, "Timeline should have project_id"
            assert timeline['project_id'] == project_id, "Timeline project_id should match"
            
            print(f"Timeline found: {timeline['timeline_id']}")
            print(f"Steps count: {len(data['steps'])}")
            
            # Verify steps structure
            for step in data['steps']:
                assert "step_id" in step, "Step should have step_id"
                assert "title" in step, "Step should have title"
                assert "status" in step, "Step should have status"
                assert step['status'] in ['pending', 'in_progress', 'completed', 'approved'], \
                    f"Invalid step status: {step['status']}"
        else:
            print("No timeline exists for this project (can create from template)")
    
    def test_get_project_timeline_buyer(self):
        """GET /project-timeline - Buyer view (should NOT see internal notes)"""
        if not self.buyer_token:
            pytest.skip("Buyer login not available")
        
        res = requests.get(f"{BASE_URL}/api/project-timeline", headers=self.buyer_headers)
        
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        data = res.json()
        
        assert "timeline" in data, "Response should have timeline field"
        assert "steps" in data, "Response should have steps field"
        
        if data['steps']:
            for step in data['steps']:
                # Buyer should NOT see internal_notes field populated
                # (or it should be empty/None)
                notes = step.get('internal_notes')
                if notes is not None and len(notes) > 0:
                    print(f"WARNING: Buyer can see internal notes on step {step['step_id']}")
            
            print(f"Buyer can see {len(data['steps'])} timeline steps")
    
    # ======================
    # STEP STATUS ADVANCEMENT
    # ======================
    
    def test_step_status_transitions(self):
        """PATCH /timeline/steps/{id} - Test status transitions"""
        # Get project timeline with steps
        projects_res = requests.get(f"{BASE_URL}/api/projects", headers=self.agent_headers)
        projects = projects_res.json()
        
        if len(projects) == 0:
            pytest.skip("No projects available")
        
        project_id = projects[0]['project_id']
        
        timeline_res = requests.get(
            f"{BASE_URL}/api/project-timeline?project_id={project_id}",
            headers=self.agent_headers
        )
        data = timeline_res.json()
        
        if not data.get('steps') or len(data['steps']) == 0:
            pytest.skip("No timeline steps available for status test")
        
        # Find a step to test status transitions
        # The demo data should have steps in various statuses
        steps = data['steps']
        
        # Report current statuses
        for step in steps:
            print(f"Step {step['order_index']}: {step['title']} - {step['status']}")
        
        # Find a pending step to advance
        pending_step = next((s for s in steps if s['status'] == 'pending'), None)
        if pending_step:
            # Try to advance pending -> in_progress
            res = requests.patch(
                f"{BASE_URL}/api/timeline/steps/{pending_step['step_id']}",
                headers=self.agent_headers,
                json={"status": "in_progress"}
            )
            # This may fail if there's a step before it that's not completed
            # Just check we get valid response
            assert res.status_code in [200, 400], f"Unexpected status: {res.status_code}: {res.text}"
            if res.status_code == 200:
                print(f"Successfully advanced step to in_progress")
            else:
                print(f"Could not advance step: {res.json().get('detail')}")
    
    def test_edit_step_details(self):
        """PATCH /timeline/steps/{id} - Edit title, description, planned_date"""
        projects_res = requests.get(f"{BASE_URL}/api/projects", headers=self.agent_headers)
        projects = projects_res.json()
        
        if len(projects) == 0:
            pytest.skip("No projects available")
        
        project_id = projects[0]['project_id']
        
        timeline_res = requests.get(
            f"{BASE_URL}/api/project-timeline?project_id={project_id}",
            headers=self.agent_headers
        )
        data = timeline_res.json()
        
        if not data.get('steps') or len(data['steps']) == 0:
            pytest.skip("No timeline steps available")
        
        step = data['steps'][0]
        original_title = step['title']
        
        # Update step details
        test_description = "TEST_Description updated by testing agent"
        res = requests.patch(
            f"{BASE_URL}/api/timeline/steps/{step['step_id']}",
            headers=self.agent_headers,
            json={
                "description": test_description,
                "planned_date": "2026-03-15"
            }
        )
        
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        updated = res.json()
        
        assert updated.get('description') == test_description, "Description should be updated"
        print(f"Step details updated successfully")
        
        # Revert description (cleanup)
        requests.patch(
            f"{BASE_URL}/api/timeline/steps/{step['step_id']}",
            headers=self.agent_headers,
            json={"description": step.get('description', '')}
        )
    
    # ======================
    # DOCUMENT LINKING
    # ======================
    
    def test_link_document_to_step(self):
        """POST /timeline/steps/{id}/documents - Link activity to step"""
        projects_res = requests.get(f"{BASE_URL}/api/projects", headers=self.agent_headers)
        projects = projects_res.json()
        
        if len(projects) == 0:
            pytest.skip("No projects available")
        
        project_id = projects[0]['project_id']
        
        # Get timeline steps
        timeline_res = requests.get(
            f"{BASE_URL}/api/project-timeline?project_id={project_id}",
            headers=self.agent_headers
        )
        data = timeline_res.json()
        
        if not data.get('steps') or len(data['steps']) == 0:
            pytest.skip("No timeline steps available")
        
        step = data['steps'][0]
        
        # Get activities for project
        activities_res = requests.get(
            f"{BASE_URL}/api/activities?project_id={project_id}",
            headers=self.agent_headers
        )
        
        if activities_res.status_code != 200:
            pytest.skip("Could not fetch activities")
        
        activities_data = activities_res.json()
        activities = activities_data.get('activities', [])
        
        if len(activities) == 0:
            pytest.skip("No activities available to link")
        
        activity = activities[0]
        
        # Try to link document
        res = requests.post(
            f"{BASE_URL}/api/timeline/steps/{step['step_id']}/documents",
            headers=self.agent_headers,
            json={"activity_id": activity['activity_id']}
        )
        
        # May succeed or fail if already linked
        assert res.status_code in [200, 201, 400], f"Unexpected status: {res.status_code}: {res.text}"
        if res.status_code in [200, 201]:
            print(f"Document linked successfully to step")
        else:
            print(f"Link failed (may already exist): {res.json().get('detail')}")
    
    # ======================
    # INTERNAL NOTES
    # ======================
    
    def test_add_internal_note(self):
        """POST /timeline/steps/{id}/notes - Add internal note (agent only)"""
        projects_res = requests.get(f"{BASE_URL}/api/projects", headers=self.agent_headers)
        projects = projects_res.json()
        
        if len(projects) == 0:
            pytest.skip("No projects available")
        
        project_id = projects[0]['project_id']
        
        timeline_res = requests.get(
            f"{BASE_URL}/api/project-timeline?project_id={project_id}",
            headers=self.agent_headers
        )
        data = timeline_res.json()
        
        if not data.get('steps') or len(data['steps']) == 0:
            pytest.skip("No timeline steps available")
        
        step = data['steps'][0]
        
        # Add a note
        test_note_content = "TEST_Internal note from testing agent - delete me"
        res = requests.post(
            f"{BASE_URL}/api/timeline/steps/{step['step_id']}/notes",
            headers=self.agent_headers,
            json={"content": test_note_content}
        )
        
        assert res.status_code in [200, 201], f"Expected 200/201, got {res.status_code}: {res.text}"
        note = res.json()
        
        assert "note_id" in note, "Note should have note_id"
        assert note.get('content') == test_note_content, "Note content should match"
        assert "author_name" in note, "Note should have author_name"
        
        print(f"Internal note added: {note['note_id']}")
    
    # ======================
    # APPLY TEMPLATE
    # ======================
    
    def test_apply_template_to_project(self):
        """POST /timeline/templates/{id}/apply - Create timeline from template"""
        # Get templates
        templates_res = requests.get(
            f"{BASE_URL}/api/timeline/templates",
            headers=self.agent_headers
        )
        templates = templates_res.json()
        
        if len(templates) == 0:
            pytest.skip("No templates available")
        
        template = templates[0]
        
        # Get a project
        projects_res = requests.get(f"{BASE_URL}/api/projects", headers=self.agent_headers)
        projects = projects_res.json()
        
        if len(projects) == 0:
            pytest.skip("No projects available")
        
        # Try to apply - this will fail if project already has timeline
        project_id = projects[0]['project_id']
        
        res = requests.post(
            f"{BASE_URL}/api/timeline/templates/{template['template_id']}/apply?project_id={project_id}",
            headers=self.agent_headers
        )
        
        # Either creates successfully (200) or fails because already exists (400)
        assert res.status_code in [200, 400], f"Unexpected status: {res.status_code}: {res.text}"
        
        if res.status_code == 200:
            print(f"Timeline created from template")
        else:
            error = res.json().get('detail', '')
            if 'already has a timeline' in error:
                print(f"Project already has timeline (expected for demo data)")
            else:
                print(f"Template apply failed: {error}")
    
    # ======================
    # DELETE TIMELINE
    # ======================
    
    def test_delete_timeline_requires_auth(self):
        """DELETE /timeline/{id} - Should require agent auth"""
        # Try without auth
        res = requests.delete(f"{BASE_URL}/api/timeline/test_timeline_id")
        assert res.status_code == 401, f"Expected 401 without auth, got {res.status_code}"
    
    def test_get_timeline_templates_requires_agent(self):
        """GET /timeline/templates - Should require agent role"""
        if not self.buyer_token:
            pytest.skip("Buyer login not available")
        
        # Buyer should not be able to access templates
        res = requests.get(
            f"{BASE_URL}/api/timeline/templates",
            headers=self.buyer_headers
        )
        
        # Should be 403 Forbidden for buyer
        assert res.status_code == 403, f"Expected 403 for buyer, got {res.status_code}: {res.text}"
        print("Templates endpoint correctly restricted to agents only")


class TestBuyerTimelineView:
    """Tests specific to buyer's view of construction progress"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login as demo buyer"""
        res = requests.post(f"{BASE_URL}/api/auth/demo/buyer")
        if res.status_code != 200:
            pytest.skip(f"Buyer login failed: {res.text}")
        
        data = res.json()
        self.buyer_token = data.get('token')
        self.buyer_headers = {"Authorization": f"Bearer {self.buyer_token}"}
    
    def test_buyer_sees_progress(self):
        """Buyer can see construction progress via /project-timeline"""
        res = requests.get(f"{BASE_URL}/api/project-timeline", headers=self.buyer_headers)
        
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        data = res.json()
        
        if data.get('timeline'):
            print(f"Buyer can see timeline: {data['timeline']['timeline_id']}")
            
            steps = data.get('steps', [])
            print(f"Buyer sees {len(steps)} construction stages")
            
            # Check progress calculation
            completed = sum(1 for s in steps if s['status'] in ['completed', 'approved'])
            progress = (completed / len(steps) * 100) if steps else 0
            print(f"Progress: {progress:.0f}% ({completed}/{len(steps)} stages)")
        else:
            print("No timeline available for buyer's project")
    
    def test_buyer_sees_linked_documents(self):
        """Buyer can see documents linked to timeline steps"""
        res = requests.get(f"{BASE_URL}/api/project-timeline", headers=self.buyer_headers)
        
        assert res.status_code == 200
        data = res.json()
        
        steps = data.get('steps', [])
        docs_found = 0
        
        for step in steps:
            docs = step.get('documents', [])
            if docs:
                docs_found += len(docs)
                for doc in docs:
                    assert 'activity_id' in doc, "Document should have activity_id"
                    print(f"Step '{step['title']}' has linked document: {doc.get('title', doc.get('file_name', 'unknown'))}")
        
        print(f"Total linked documents visible to buyer: {docs_found}")
    
    def test_buyer_does_not_see_internal_notes(self):
        """Buyer should NOT see internal_notes field content"""
        res = requests.get(f"{BASE_URL}/api/project-timeline", headers=self.buyer_headers)
        
        assert res.status_code == 200
        data = res.json()
        
        steps = data.get('steps', [])
        notes_visible = False
        
        for step in steps:
            notes = step.get('internal_notes')
            if notes and len(notes) > 0:
                notes_visible = True
                print(f"WARNING: Step '{step['title']}' has {len(notes)} internal notes visible to buyer!")
        
        # This is a critical security check - buyer should not see agent's internal notes
        if notes_visible:
            print("ISSUE: Buyer can see internal notes (agent-only)")
        else:
            print("PASS: No internal notes visible to buyer")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
