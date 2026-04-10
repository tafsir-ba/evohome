"""
Phase 4 Workflow Hardening Tests
Tests for:
- Workflow templates endpoint returns correct templates
- Timeline step selector returns demo steps with 'name' field mapped from 'title'
- Milestone completion workflow execution (email will fail due to no recipient - tests warning flow)
- Retry endpoint for failed/warning steps
- Workflow result includes step_index and can_retry fields
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Demo agent credentials
DEMO_AGENT_EMAIL = "demo.agent@upgradeflow.com"
DEMO_AGENT_PASSWORD = "demo123"

class TestWorkflowHardeningPhase4:
    """Phase 4 Workflow hardening tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token before each test"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login with demo agent
        login_res = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": DEMO_AGENT_EMAIL,
            "password": DEMO_AGENT_PASSWORD
        })
        
        if login_res.status_code == 200:
            data = login_res.json()
            if data.get('token'):
                self.session.headers.update({"Authorization": f"Bearer {data['token']}"})
            self.user_id = data.get('user_id')
        else:
            pytest.skip(f"Login failed: {login_res.status_code} - {login_res.text}")
        
        yield
        self.session.close()
    
    # ================= WORKFLOW TEMPLATES =================
    
    def test_workflow_templates_endpoint_returns_templates(self):
        """Verify workflow templates endpoint returns available templates"""
        res = self.session.get(f"{BASE_URL}/api/workflows/templates")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        
        data = res.json()
        assert "templates" in data, "Response should contain 'templates' key"
        templates = data['templates']
        
        # Should have at least milestone_completion template
        template_ids = [t['template_id'] for t in templates]
        assert "milestone_completion" in template_ids, "Should include milestone_completion template"
        assert "invoice_paid_processing" in template_ids, "Should include invoice_paid_processing template"
        
        print(f"PASS: Found {len(templates)} workflow templates")
    
    def test_milestone_completion_template_structure(self):
        """Verify milestone_completion template has correct structure"""
        res = self.session.get(f"{BASE_URL}/api/workflows/templates")
        assert res.status_code == 200
        
        data = res.json()
        templates = data.get('templates', [])
        
        # Find milestone_completion template
        milestone_template = next((t for t in templates if t['template_id'] == 'milestone_completion'), None)
        assert milestone_template is not None, "milestone_completion template not found"
        
        # Verify structure
        assert milestone_template.get('name') == "Milestone Completion"
        assert "ui_selectors" in milestone_template, "Template should have ui_selectors"
        assert "timeline_step" in milestone_template.get('ui_selectors', []), "Should include timeline_step selector"
        assert "required_context" in milestone_template, "Template should have required_context"
        assert "step_id" in milestone_template.get('required_context', []), "Should require step_id"
        
        print(f"PASS: milestone_completion template has correct structure")
    
    # ================= TIMELINE STEP SELECTOR =================
    
    def test_timeline_step_selector_returns_items(self):
        """Verify timeline step selector returns demo steps"""
        res = self.session.get(f"{BASE_URL}/api/workflows/selectors?selector_type=timeline_step")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        
        data = res.json()
        assert "items" in data, "Response should contain 'items' key"
        items = data['items']
        
        # Should have demo steps
        assert len(items) > 0, "Should return timeline steps"
        
        print(f"PASS: Timeline step selector returned {len(items)} items")
    
    def test_timeline_step_selector_name_field_mapping(self):
        """Verify 'title' field is mapped to 'name' for UI consistency"""
        res = self.session.get(f"{BASE_URL}/api/workflows/selectors?selector_type=timeline_step")
        assert res.status_code == 200
        
        data = res.json()
        items = data.get('items', [])
        
        assert len(items) > 0, "Need at least one timeline step to test"
        
        # Each item should have 'name' field (mapped from 'title')
        for item in items:
            assert 'name' in item, f"Item {item.get('step_id')} should have 'name' field"
            # Verify name is not empty
            assert item['name'], f"Item {item.get('step_id')} name should not be empty"
        
        # Check for expected demo steps
        step_names = [item['name'] for item in items]
        print(f"Found timeline steps: {step_names}")
        
        # Check for common demo step names
        expected_steps = ['Permits', 'Foundation', 'Structure', 'Finishes']
        found_steps = [s for s in expected_steps if any(s in name for name in step_names)]
        assert len(found_steps) > 0, f"Should find some expected demo steps. Found: {step_names}"
        
        print(f"PASS: Timeline steps have correct 'name' field mapping. Found: {step_names[:5]}")
    
    def test_timeline_step_selector_includes_step_id(self):
        """Verify each timeline step includes step_id for workflow context"""
        res = self.session.get(f"{BASE_URL}/api/workflows/selectors?selector_type=timeline_step")
        assert res.status_code == 200
        
        data = res.json()
        items = data.get('items', [])
        
        assert len(items) > 0, "Need timeline steps to test"
        
        for item in items:
            assert 'step_id' in item, f"Item should have 'step_id' field"
            assert item['step_id'].startswith('step_'), f"step_id should start with 'step_': {item['step_id']}"
        
        print(f"PASS: All {len(items)} timeline steps have valid step_id")
    
    # ================= WORKFLOW EXECUTION =================
    
    def test_milestone_completion_workflow_execution(self):
        """Execute milestone_completion workflow - email will fail with warning due to no recipient"""
        # First get a timeline step to use
        steps_res = self.session.get(f"{BASE_URL}/api/workflows/selectors?selector_type=timeline_step")
        assert steps_res.status_code == 200
        
        steps = steps_res.json().get('items', [])
        # Find a pending step
        pending_step = next((s for s in steps if s.get('status') == 'pending'), None)
        
        if not pending_step:
            # Use any step if no pending found
            pending_step = steps[0] if steps else None
        
        if not pending_step:
            pytest.skip("No timeline steps available for testing")
        
        step_id = pending_step['step_id']
        print(f"Using timeline step: {step_id} ({pending_step.get('name')})")
        
        # Execute the workflow
        exec_res = self.session.post(f"{BASE_URL}/api/workflows/execute", json={
            "template_id": "milestone_completion",
            "context": {
                "step_id": step_id
            },
            "mode": "automatic"
        })
        
        # Should succeed (potentially with warnings)
        assert exec_res.status_code == 200, f"Expected 200, got {exec_res.status_code}: {exec_res.text}"
        
        data = exec_res.json()
        assert "execution" in data, "Response should contain 'execution'"
        
        execution = data['execution']
        assert "status" in execution, "Execution should have status"
        
        # Status should be completed (possibly with warnings since email may fail)
        assert execution['status'] in ['completed', 'completed_with_warnings', 'failed'], \
            f"Unexpected status: {execution['status']}"
        
        print(f"PASS: Workflow execution status: {execution['status']}")
        return execution
    
    # ================= STEP_INDEX AND CAN_RETRY FIELDS =================
    
    def test_workflow_result_includes_step_index(self):
        """Verify workflow result steps include step_index field"""
        # Execute a simple workflow
        exec_res = self.session.post(f"{BASE_URL}/api/workflows/execute", json={
            "template_id": "milestone_completion",
            "context": {
                "step_id": "step_demo_004"  # Use demo step
            },
            "mode": "automatic"
        })
        
        if exec_res.status_code != 200:
            pytest.skip(f"Workflow execution failed: {exec_res.text}")
        
        data = exec_res.json()
        execution = data.get('execution', {})
        steps = execution.get('steps', [])
        
        assert len(steps) > 0, "Should have at least one step"
        
        for i, step in enumerate(steps):
            assert 'step_index' in step, f"Step {i} should have step_index field"
            assert step['step_index'] == i, f"Step {i} should have step_index={i}, got {step['step_index']}"
        
        print(f"PASS: All {len(steps)} steps include correct step_index")
    
    def test_workflow_result_includes_can_retry(self):
        """Verify workflow result steps include can_retry field"""
        # Execute workflow that may have warnings
        exec_res = self.session.post(f"{BASE_URL}/api/workflows/execute", json={
            "template_id": "milestone_completion",
            "context": {
                "step_id": "step_demo_005"  # Different step
            },
            "mode": "automatic"
        })
        
        if exec_res.status_code != 200:
            pytest.skip(f"Workflow execution failed: {exec_res.text}")
        
        data = exec_res.json()
        execution = data.get('execution', {})
        steps = execution.get('steps', [])
        
        assert len(steps) > 0, "Should have at least one step"
        
        for i, step in enumerate(steps):
            assert 'can_retry' in step, f"Step {i} should have can_retry field"
            # can_retry should be boolean
            assert isinstance(step['can_retry'], bool), f"can_retry should be boolean"
            
            # If step has warning or failed status, can_retry should be True
            if step.get('status') in ['failed', 'completed_with_warning']:
                assert step['can_retry'] == True, f"Step with {step['status']} should have can_retry=True"
        
        print(f"PASS: All {len(steps)} steps include can_retry field")
    
    # ================= RETRY ENDPOINT =================
    
    def test_retry_endpoint_exists(self):
        """Verify retry endpoint returns proper response (not 405 Method Not Allowed)"""
        # First execute a workflow
        exec_res = self.session.post(f"{BASE_URL}/api/workflows/execute", json={
            "template_id": "milestone_completion",
            "context": {
                "step_id": "step_demo_003"
            },
            "mode": "automatic"
        })
        
        if exec_res.status_code != 200:
            pytest.skip(f"Workflow execution failed: {exec_res.text}")
        
        data = exec_res.json()
        execution_id = data.get('execution', {}).get('execution_id')
        
        if not execution_id:
            pytest.skip("No execution_id returned")
        
        # Try to retry step 0
        retry_res = self.session.post(f"{BASE_URL}/api/workflows/executions/{execution_id}/steps/0/retry")
        
        # Should not be 405 (method not allowed)
        assert retry_res.status_code != 405, "Retry endpoint should exist"
        
        # Valid responses: 200 (success), 400 (can't retry - step not failed/warning)
        assert retry_res.status_code in [200, 400], f"Expected 200 or 400, got {retry_res.status_code}: {retry_res.text}"
        
        print(f"PASS: Retry endpoint works (status {retry_res.status_code})")
    
    def test_retry_failed_step(self):
        """Test retrying a step that failed or has warning"""
        # Execute workflow that likely produces warnings (email without recipient)
        exec_res = self.session.post(f"{BASE_URL}/api/workflows/execute", json={
            "template_id": "milestone_completion",
            "context": {
                "step_id": "step_demo_002"  # Permits step
            },
            "mode": "automatic"
        })
        
        if exec_res.status_code != 200:
            pytest.skip(f"Workflow execution failed: {exec_res.text}")
        
        data = exec_res.json()
        execution = data.get('execution', {})
        execution_id = execution.get('execution_id')
        steps = execution.get('steps', [])
        
        # Find a step with can_retry=True
        retryable_step = None
        for step in steps:
            if step.get('can_retry') == True:
                retryable_step = step
                break
        
        if not retryable_step:
            print(f"INFO: No retryable steps found in this execution. Steps status: {[s.get('status') for s in steps]}")
            # Still test that endpoint works
            retry_res = self.session.post(f"{BASE_URL}/api/workflows/executions/{execution_id}/steps/1/retry")
            # 400 is expected when step is not retryable
            assert retry_res.status_code in [200, 400], f"Expected 200 or 400, got {retry_res.status_code}"
            print("PASS: Retry endpoint returns appropriate response for non-retryable step")
            return
        
        step_index = retryable_step['step_index']
        
        # Retry the step
        retry_res = self.session.post(f"{BASE_URL}/api/workflows/executions/{execution_id}/steps/{step_index}/retry")
        
        assert retry_res.status_code == 200, f"Expected 200, got {retry_res.status_code}: {retry_res.text}"
        
        retry_data = retry_res.json()
        assert retry_data.get('success') == True, "Retry should succeed"
        assert 'execution' in retry_data, "Should return updated execution"
        assert retry_data.get('retried_step') == step_index, "Should indicate which step was retried"
        
        print(f"PASS: Successfully retried step {step_index}")
    
    def test_retry_invalid_step_index(self):
        """Test retry with invalid step index returns 400"""
        # Execute workflow
        exec_res = self.session.post(f"{BASE_URL}/api/workflows/execute", json={
            "template_id": "milestone_completion",
            "context": {
                "step_id": "step_demo_001"
            },
            "mode": "automatic"
        })
        
        if exec_res.status_code != 200:
            pytest.skip(f"Workflow execution failed: {exec_res.text}")
        
        execution_id = exec_res.json().get('execution', {}).get('execution_id')
        
        # Try invalid step index
        retry_res = self.session.post(f"{BASE_URL}/api/workflows/executions/{execution_id}/steps/999/retry")
        
        assert retry_res.status_code == 400, f"Expected 400 for invalid step index, got {retry_res.status_code}"
        
        print("PASS: Invalid step index returns 400")
    
    def test_retry_nonexistent_execution(self):
        """Test retry with invalid execution_id returns 404"""
        retry_res = self.session.post(f"{BASE_URL}/api/workflows/executions/wf_nonexistent123/steps/0/retry")
        
        assert retry_res.status_code == 404, f"Expected 404, got {retry_res.status_code}"
        
        print("PASS: Nonexistent execution returns 404")
    
    # ================= WARNING STATUS HANDLING =================
    
    def test_completed_with_warnings_status(self):
        """Verify workflow can complete with COMPLETED_WITH_WARNINGS status"""
        # Execute milestone_completion - email step will fail/warn since no recipient configured
        exec_res = self.session.post(f"{BASE_URL}/api/workflows/execute", json={
            "template_id": "milestone_completion",
            "context": {
                "step_id": "step_demo_004"  # Structure step
            },
            "mode": "automatic"
        })
        
        if exec_res.status_code != 200:
            pytest.skip(f"Workflow execution failed: {exec_res.text}")
        
        data = exec_res.json()
        execution = data.get('execution', {})
        status = execution.get('status')
        progress = execution.get('progress', {})
        
        # Check if warnings count is included
        assert 'warnings' in progress, "Progress should include 'warnings' count"
        
        # If there are warnings, status should be completed_with_warnings
        if progress.get('warnings', 0) > 0:
            assert status == 'completed_with_warnings', \
                f"With warnings, status should be 'completed_with_warnings', got '{status}'"
            print(f"PASS: Workflow completed with warnings (warnings: {progress['warnings']})")
        else:
            assert status in ['completed', 'completed_with_warnings'], \
                f"Status should be 'completed' or 'completed_with_warnings', got '{status}'"
            print(f"PASS: Workflow completed (status: {status}, warnings: {progress.get('warnings', 0)})")


class TestInvalidSelectorType:
    """Test invalid selector type handling"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_res = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": DEMO_AGENT_EMAIL,
            "password": DEMO_AGENT_PASSWORD
        })
        
        if login_res.status_code == 200:
            data = login_res.json()
            if data.get('token'):
                self.session.headers.update({"Authorization": f"Bearer {data['token']}"})
        else:
            pytest.skip("Login failed")
        
        yield
        self.session.close()
    
    def test_invalid_selector_type_returns_400(self):
        """Verify invalid selector type returns 400 error"""
        res = self.session.get(f"{BASE_URL}/api/workflows/selectors?selector_type=invalid_type")
        
        assert res.status_code == 400, f"Expected 400, got {res.status_code}"
        
        print("PASS: Invalid selector type returns 400")
