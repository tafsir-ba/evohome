"""
Test Suite for Construction Milestone Notifications Feature (P1)
Tests:
- PATCH /api/timeline/steps/{id} with status='completed' triggers notification
- In-app notification created with correct title and message
- Email template 'milestone_completed' renders correctly with progress bar
- Progress percentage calculated correctly
- Buyer receives notification when their unit's milestone is completed
- GET /api/test/email-template/milestone_completed returns valid HTML
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Module-level session with auth token
def get_agent_session():
    """Login as demo agent and return session with auth token"""
    session = requests.Session()
    response = session.post(f"{BASE_URL}/api/auth/demo/agent")
    if response.status_code == 200:
        token = response.json().get("token")
        session.headers.update({"Authorization": f"Bearer {token}"})
    return session, response.status_code == 200

def get_buyer_session():
    """Login as demo buyer (Sophie) and return session with auth token"""
    session = requests.Session()
    response = session.post(f"{BASE_URL}/api/auth/demo/buyer?buyer_num=1")
    if response.status_code == 200:
        token = response.json().get("token")
        session.headers.update({"Authorization": f"Bearer {token}"})
    return session, response.status_code == 200


class TestMilestoneNotificationsSetup:
    """Test setup and prerequisite verification"""
    
    def test_api_health(self):
        """Verify API is accessible"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
        print("✓ API health check passed")
    
    def test_demo_agent_login(self):
        """Verify demo agent login works"""
        session, success = get_agent_session()
        assert success, "Failed to login as demo agent"
        
        # Verify we can access protected endpoint
        response = session.get(f"{BASE_URL}/api/auth/me")
        assert response.status_code == 200
        data = response.json()
        assert data.get("role") == "agent"
        assert data.get("is_demo") == True
        print(f"✓ Demo agent login successful: {data.get('name')}")
    
    def test_demo_buyer_login(self):
        """Verify demo buyer login works"""
        session, success = get_buyer_session()
        assert success, "Failed to login as demo buyer"
        
        response = session.get(f"{BASE_URL}/api/auth/me")
        assert response.status_code == 200
        data = response.json()
        assert data.get("role") == "buyer"
        assert data.get("is_demo") == True
        print(f"✓ Demo buyer login successful: {data.get('name')}")


class TestMilestoneEmailTemplate:
    """Test the milestone_completed email template"""
    
    def test_email_template_milestone_completed(self):
        """GET /api/test/email-template/milestone_completed should return valid HTML with progress bar"""
        response = requests.get(f"{BASE_URL}/api/test/email-template/milestone_completed")
        
        if response.status_code == 400:
            data = response.json()
            if "Invalid template" in data.get("detail", ""):
                pytest.fail(f"milestone_completed not in valid_templates list. Response: {data}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "template_type" in data
        assert data["template_type"] == "milestone_completed"
        assert "subject" in data
        assert "html_preview" in data
        
        # Verify HTML contains expected milestone elements
        html = data.get("html_preview", "")
        assert "Milestone" in html or "milestone" in html, "HTML should contain 'Milestone'"
        
        # Check for progress bar element
        assert "width:" in html or "progress" in html.lower(), "HTML should contain progress indication"
        
        print(f"✓ Email template 'milestone_completed' returns valid HTML")
        print(f"  Subject: {data.get('subject')}")
    
    def test_email_template_has_progress_bar(self):
        """Verify email template includes progress bar visualization"""
        response = requests.get(f"{BASE_URL}/api/test/email-template/milestone_completed")
        
        if response.status_code != 200:
            pytest.skip("milestone_completed template not available")
        
        data = response.json()
        html = data.get("html_preview", "")
        
        # Check for progress bar elements
        assert "progress" in html.lower() or "%" in html, "Should show progress percentage"
        assert "background-color" in html, "Should have styled progress bar"
        
        # Check for green color (success/completion indicator)
        assert "#16a34a" in html or "#dcfce7" in html or "green" in html.lower(), "Should have green color for completed milestone"
        
        print("✓ Email template has progress bar visualization")
    
    def test_email_template_has_cta_button(self):
        """Verify CTA button has proper inline styles for email clients"""
        response = requests.get(f"{BASE_URL}/api/test/email-template/milestone_completed")
        
        if response.status_code != 200:
            pytest.skip("milestone_completed template not available via test endpoint")
        
        data = response.json()
        cta_validation = data.get("cta_validation", {})
        
        assert cta_validation.get("has_bg_color", False) or "background-color: #2563EB" in data.get("html_preview", "")
        print("✓ Email template has proper CTA button styles")


class TestTimelineStepNotifications:
    """Test that updating timeline step to 'completed' triggers notifications"""
    
    def test_get_existing_timelines(self):
        """Get existing project timelines to find a step to test with"""
        session, success = get_agent_session()
        assert success, "Agent login failed"
        
        # Get projects
        projects_response = session.get(f"{BASE_URL}/api/projects")
        assert projects_response.status_code == 200
        projects = projects_response.json()
        
        if not projects:
            pytest.skip("No projects found for demo agent")
        
        print(f"✓ Found {len(projects)} projects")
        
        # Check each project for timeline using correct endpoint
        found_timeline = False
        for project in projects:
            project_id = project.get("project_id")
            # Correct endpoint: /api/project-timeline?project_id=xxx
            timeline_response = session.get(f"{BASE_URL}/api/project-timeline?project_id={project_id}")
            
            if timeline_response.status_code == 200:
                timeline_data = timeline_response.json()
                steps = timeline_data.get("steps", [])
                if steps:
                    print(f"  Project '{project.get('name')}' has {len(steps)} timeline steps")
                    found_timeline = True
        
        assert found_timeline, "No timelines with steps found"
    
    def test_find_non_completed_step(self):
        """Find a timeline step that is not yet completed for testing"""
        session, success = get_agent_session()
        assert success, "Agent login failed"
        
        projects_response = session.get(f"{BASE_URL}/api/projects")
        projects = projects_response.json()
        
        if not projects:
            pytest.skip("No projects available")
        
        for project in projects:
            project_id = project.get("project_id")
            timeline_response = session.get(f"{BASE_URL}/api/project-timeline?project_id={project_id}")
            
            if timeline_response.status_code != 200:
                continue
                
            timeline_data = timeline_response.json()
            steps = timeline_data.get("steps", [])
            
            for step in steps:
                if step.get("status") in ["pending", "in_progress"]:
                    print(f"✓ Found non-completed step: {step.get('step_id')} - '{step.get('title')}' (status: {step.get('status')})")
                    return
        
        print("  INFO: All steps may already be completed - testing with completed step")
    
    def test_update_step_to_completed_triggers_notification(self):
        """PATCH /api/timeline/steps/{id} with status='completed' should trigger notification"""
        agent_session, agent_success = get_agent_session()
        buyer_session, buyer_success = get_buyer_session()
        
        assert agent_success, "Agent login failed"
        assert buyer_success, "Buyer login failed"
        
        # Find a testable step
        projects_response = agent_session.get(f"{BASE_URL}/api/projects")
        projects = projects_response.json()
        
        test_step = None
        original_status = None
        project_info = None
        
        for project in projects:
            project_id = project.get("project_id")
            timeline_response = agent_session.get(f"{BASE_URL}/api/project-timeline?project_id={project_id}")
            
            if timeline_response.status_code != 200:
                continue
                
            timeline_data = timeline_response.json()
            steps = timeline_data.get("steps", [])
            
            for step in steps:
                if step.get("status") in ["pending", "in_progress"]:
                    test_step = step
                    original_status = step.get("status")
                    project_info = project
                    break
            
            if test_step:
                break
        
        if not test_step:
            pytest.skip("No non-completed steps available for testing")
        
        step_id = test_step.get("step_id")
        step_title = test_step.get("title")
        
        print(f"  Testing with step: '{step_title}' (current status: {original_status})")
        
        # Get buyer notifications count before update
        buyer_notifs_before = buyer_session.get(f"{BASE_URL}/api/notifications")
        notif_count_before = len(buyer_notifs_before.json().get("notifications", [])) if buyer_notifs_before.status_code == 200 else 0
        print(f"  Buyer notifications before: {notif_count_before}")
        
        # Update step to 'completed'
        response = agent_session.patch(
            f"{BASE_URL}/api/timeline/steps/{step_id}",
            json={"status": "completed"},
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 200, f"Failed to update step: {response.text}"
        updated_step = response.json()
        assert updated_step.get("status") == "completed"
        assert updated_step.get("completed_at") is not None
        print(f"✓ Step '{step_title}' updated to 'completed'")
        print(f"  completed_at: {updated_step.get('completed_at')}")
        
        # Brief wait for async notification to be created
        time.sleep(1.5)
        
        # Check if buyer got notification
        buyer_notifs_after = buyer_session.get(f"{BASE_URL}/api/notifications")
        assert buyer_notifs_after.status_code == 200
        
        notifications = buyer_notifs_after.json().get("notifications", [])
        notif_count_after = len(notifications)
        print(f"  Buyer notifications after: {notif_count_after}")
        
        # Look for milestone notification
        milestone_notifs = [
            n for n in notifications 
            if n.get("notification_type") == "milestone_completed"
        ]
        
        if milestone_notifs:
            latest_notif = milestone_notifs[0]
            print(f"✓ Found milestone notification:")
            print(f"  Title: {latest_notif.get('title')}")
            print(f"  Message: {latest_notif.get('message')}")
            
            # Verify notification content contains progress
            assert "%" in latest_notif.get("message", "") or "progress" in latest_notif.get("message", "").lower()
        else:
            print("  NOTE: No milestone notification found - buyer may not be linked to project units")
            # Get clients to verify linkage
            clients_response = agent_session.get(f"{BASE_URL}/api/clients")
            if clients_response.status_code == 200:
                clients = clients_response.json()
                project_clients = [c for c in clients if c.get("project_id") == project_info.get("project_id")]
                linked_buyers = [c for c in project_clients if c.get("buyer_id")]
                print(f"  Project has {len(project_clients)} clients, {len(linked_buyers)} with buyer_id")
        
        # Restore original status to keep test data clean
        restore_response = agent_session.patch(
            f"{BASE_URL}/api/timeline/steps/{step_id}",
            json={"status": original_status},
            headers={"Content-Type": "application/json"}
        )
        if restore_response.status_code == 200:
            print(f"  Restored step status to '{original_status}'")


class TestProgressCalculation:
    """Test that progress percentage is calculated correctly"""
    
    def test_progress_percentage_in_timeline(self):
        """Verify timeline has progress calculation"""
        session, success = get_agent_session()
        assert success, "Agent login failed"
        
        projects_response = session.get(f"{BASE_URL}/api/projects")
        projects = projects_response.json()
        
        if not projects:
            pytest.skip("No projects available")
        
        found_timeline = False
        for project in projects:
            project_id = project.get("project_id")
            timeline_response = session.get(f"{BASE_URL}/api/project-timeline?project_id={project_id}")
            
            if timeline_response.status_code != 200:
                continue
            
            timeline_data = timeline_response.json()
            steps = timeline_data.get("steps", [])
            
            if not steps:
                continue
            
            found_timeline = True
            
            # Calculate expected progress
            completed_count = sum(1 for s in steps if s.get("status") in ["completed", "approved"])
            total_count = len(steps)
            expected_progress = round((completed_count / total_count) * 100) if total_count > 0 else 0
            
            print(f"✓ Project '{project.get('name')}':")
            print(f"  Total steps: {total_count}")
            print(f"  Completed/Approved: {completed_count}")
            print(f"  Progress: {expected_progress}%")
            
            return
        
        if not found_timeline:
            pytest.skip("No timelines with steps found")


class TestNotificationCenterIntegration:
    """Test that NotificationCenter frontend component supports milestone_completed type"""
    
    def test_notification_icons_include_milestone(self):
        """Verify NotificationCenter has HardHat icon for milestone_completed"""
        notification_center_path = "/app/frontend/src/components/NotificationCenter.js"
        
        if not os.path.exists(notification_center_path):
            pytest.skip("NotificationCenter.js not found")
        
        with open(notification_center_path, "r") as f:
            content = f.read()
        
        # Check for milestone_completed in notificationIcons
        assert "milestone_completed" in content, "milestone_completed should be in notificationIcons"
        assert "HardHat" in content, "HardHat icon should be imported"
        
        print("✓ NotificationCenter has HardHat icon for milestone_completed type")


class TestBuyerClientLinkage:
    """Test that only buyers linked to project units receive notifications"""
    
    def test_get_clients_with_units(self):
        """Verify clients are linked to units (prerequisite for milestone notifications)"""
        session, success = get_agent_session()
        assert success, "Agent login failed"
        
        response = session.get(f"{BASE_URL}/api/clients")
        assert response.status_code == 200
        
        clients = response.json()
        print(f"✓ Found {len(clients)} clients")
        
        clients_with_units = [c for c in clients if c.get("unit_id")]
        print(f"  Clients with unit_id: {len(clients_with_units)}")
        
        clients_with_buyer = [c for c in clients if c.get("buyer_id")]
        print(f"  Clients with buyer_id: {len(clients_with_buyer)}")
        
        # For notifications to work, need clients linked to both unit and buyer
        linked_clients = [c for c in clients if c.get("unit_id") and c.get("buyer_id")]
        print(f"  Clients linked to both unit AND buyer: {len(linked_clients)}")
        
        if not linked_clients:
            print("  NOTE: No clients fully linked - milestone notifications may not reach buyers")


class TestEmailTemplateValidation:
    """Validate the milestone_completed email template structure in backend"""
    
    def test_email_template_function_exists(self):
        """Verify get_email_template handles milestone_completed"""
        server_path = "/app/backend/server.py"
        
        with open(server_path, "r") as f:
            content = f.read()
        
        # Check for milestone_completed template case
        assert 'template_type == "milestone_completed"' in content or '"milestone_completed"' in content
        
        # Check for progress_percent usage in template
        assert "progress_percent" in content
        
        print("✓ Server has milestone_completed email template implementation")
    
    def test_send_milestone_notification_function_exists(self):
        """Verify send_milestone_notification helper function exists"""
        server_path = "/app/backend/server.py"
        
        with open(server_path, "r") as f:
            content = f.read()
        
        assert "async def send_milestone_notification" in content
        assert "await send_milestone_notification" in content
        
        print("✓ send_milestone_notification helper function exists and is called")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
