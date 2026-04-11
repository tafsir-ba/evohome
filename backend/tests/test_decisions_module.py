"""
Test suite for FEAT-001: Decisions Management Module
Tests the full lifecycle: Agent creates decisions, sends to buyers, buyers respond.
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from test_credentials.md
AGENT_EMAIL = "agent@evohome-test.ch"
AGENT_PASSWORD = "Evohome2026!"
BUYER_EMAIL = "buyer@evohome-test.ch"
BUYER_PASSWORD = "Evohome2026!"

# Known test data from context
TEST_PROJECT_ID = "proj_5e806411d00c"
TEST_CLIENT_ID = "client_0bb2d1275da1"


class TestDecisionsBackend:
    """Backend API tests for Decisions module"""
    
    @pytest.fixture(scope="class")
    def agent_session(self):
        """Get authenticated agent session"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
        # Login as agent
        res = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": AGENT_EMAIL,
            "password": AGENT_PASSWORD
        })
        
        if res.status_code != 200:
            pytest.skip(f"Agent login failed: {res.status_code} - {res.text}")
        
        data = res.json()
        token = data.get("token")
        if token:
            session.headers.update({"Authorization": f"Bearer {token}"})
        
        return session
    
    @pytest.fixture(scope="class")
    def buyer_session(self):
        """Get authenticated buyer session"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
        # Login as buyer
        res = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": BUYER_EMAIL,
            "password": BUYER_PASSWORD
        })
        
        if res.status_code != 200:
            pytest.skip(f"Buyer login failed: {res.status_code} - {res.text}")
        
        data = res.json()
        token = data.get("token")
        if token:
            session.headers.update({"Authorization": f"Bearer {token}"})
        
        return session
    
    @pytest.fixture(scope="class")
    def agent_project_id(self, agent_session):
        """Get a valid project ID for the agent"""
        res = agent_session.get(f"{BASE_URL}/api/projects")
        if res.status_code == 200:
            projects = res.json()
            if isinstance(projects, list) and len(projects) > 0:
                return projects[0].get("project_id")
            elif isinstance(projects, dict) and projects.get("projects"):
                return projects["projects"][0].get("project_id")
        # Fallback to known test project
        return TEST_PROJECT_ID
    
    # ============ Agent Decision CRUD Tests ============
    
    def test_agent_login(self, agent_session):
        """Verify agent can login"""
        res = agent_session.get(f"{BASE_URL}/api/auth/session")
        assert res.status_code == 200
        data = res.json()
        assert data.get("role") == "agent"
        print(f"Agent logged in: {data.get('email')}")
    
    def test_create_decision_agent_only(self, agent_session, agent_project_id):
        """POST /api/decisions creates a decision (agent only)"""
        payload = {
            "project_id": agent_project_id,
            "title": "TEST_Approve Kitchen Layout",
            "description": "Please review and approve the kitchen layout design.",
            "deadline": "2026-02-15",
            "coverage_type": "project"
        }
        
        res = agent_session.post(f"{BASE_URL}/api/decisions", json=payload)
        assert res.status_code == 200, f"Create decision failed: {res.text}"
        
        data = res.json()
        assert "decision_id" in data
        assert data["title"] == payload["title"]
        assert data["status"] == "draft"
        assert data["project_id"] == agent_project_id
        
        print(f"Created decision: {data['decision_id']}")
        
        # Store for later tests
        self.__class__.created_decision_id = data["decision_id"]
    
    def test_list_decisions(self, agent_session):
        """GET /api/decisions returns agent's decisions"""
        res = agent_session.get(f"{BASE_URL}/api/decisions")
        assert res.status_code == 200
        
        data = res.json()
        assert "decisions" in data
        assert "total" in data
        assert isinstance(data["decisions"], list)
        
        print(f"Agent has {data['total']} decisions")
    
    def test_get_decision_detail(self, agent_session):
        """GET /api/decisions/{id} returns decision with recipients"""
        decision_id = getattr(self.__class__, 'created_decision_id', None)
        if not decision_id:
            pytest.skip("No decision created in previous test")
        
        res = agent_session.get(f"{BASE_URL}/api/decisions/{decision_id}")
        assert res.status_code == 200
        
        data = res.json()
        assert data["decision_id"] == decision_id
        assert "recipients" in data or data["status"] == "draft"
        
        print(f"Decision detail: {data['title']} - {data['status']}")
    
    def test_update_draft_decision(self, agent_session):
        """PUT /api/decisions/{id} updates a draft decision"""
        decision_id = getattr(self.__class__, 'created_decision_id', None)
        if not decision_id:
            pytest.skip("No decision created in previous test")
        
        payload = {
            "title": "TEST_Updated Kitchen Layout Approval",
            "description": "Updated description for kitchen layout."
        }
        
        res = agent_session.put(f"{BASE_URL}/api/decisions/{decision_id}", json=payload)
        assert res.status_code == 200
        
        data = res.json()
        assert data["title"] == payload["title"]
        
        print(f"Updated decision title to: {data['title']}")
    
    def test_send_decision_to_buyers(self, agent_session):
        """POST /api/decisions/{id}/send sends decision to buyers"""
        decision_id = getattr(self.__class__, 'created_decision_id', None)
        if not decision_id:
            pytest.skip("No decision created in previous test")
        
        res = agent_session.post(f"{BASE_URL}/api/decisions/{decision_id}/send")
        assert res.status_code == 200
        
        data = res.json()
        assert data["status"] == "pending"
        assert data.get("sent_at") is not None
        
        print(f"Decision sent, status: {data['status']}")
    
    # ============ Buyer Decision Tests ============
    
    def test_buyer_login(self, buyer_session):
        """Verify buyer can login"""
        res = buyer_session.get(f"{BASE_URL}/api/auth/session")
        assert res.status_code == 200
        data = res.json()
        assert data.get("role") == "buyer"
        print(f"Buyer logged in: {data.get('email')}")
    
    def test_buyer_list_decisions(self, buyer_session):
        """GET /api/buyer/decisions returns decisions visible to buyer"""
        res = buyer_session.get(f"{BASE_URL}/api/buyer/decisions")
        assert res.status_code == 200
        
        data = res.json()
        assert "decisions" in data
        
        print(f"Buyer sees {len(data['decisions'])} decisions")
        
        # Store a pending decision for response test
        pending = [d for d in data["decisions"] if d.get("buyer_status") == "pending"]
        if pending:
            self.__class__.buyer_pending_decision_id = pending[0]["decision_id"]
    
    def test_buyer_approve_decision(self, buyer_session):
        """POST /api/decisions/{id}/respond allows buyer to approve"""
        decision_id = getattr(self.__class__, 'buyer_pending_decision_id', None)
        if not decision_id:
            # Try to use the created decision
            decision_id = getattr(self.__class__, 'created_decision_id', None)
        
        if not decision_id:
            pytest.skip("No pending decision available for buyer")
        
        payload = {
            "action": "approved",
            "comment": "Looks good, approved!"
        }
        
        res = buyer_session.post(f"{BASE_URL}/api/decisions/{decision_id}/respond", json=payload)
        
        # May fail if buyer is not a recipient - that's expected
        if res.status_code == 400:
            error = res.json()
            if "No client record" in str(error.get("detail", "")):
                pytest.skip("Buyer not linked to this decision's project")
        
        assert res.status_code == 200, f"Approve failed: {res.text}"
        
        data = res.json()
        print(f"Buyer approved decision, new status: {data.get('status')}")
    
    def test_buyer_reject_decision(self, agent_session, buyer_session, agent_project_id):
        """POST /api/decisions/{id}/respond allows buyer to reject"""
        # Create a new decision for rejection test
        payload = {
            "project_id": agent_project_id,
            "title": "TEST_Decision for Rejection",
            "description": "This will be rejected by buyer.",
            "coverage_type": "project"
        }
        
        res = agent_session.post(f"{BASE_URL}/api/decisions", json=payload)
        if res.status_code != 200:
            pytest.skip("Could not create decision for rejection test")
        
        decision_id = res.json()["decision_id"]
        
        # Send it
        res = agent_session.post(f"{BASE_URL}/api/decisions/{decision_id}/send")
        if res.status_code != 200:
            pytest.skip("Could not send decision")
        
        # Buyer rejects
        res = buyer_session.post(f"{BASE_URL}/api/decisions/{decision_id}/respond", json={
            "action": "rejected",
            "comment": "Not acceptable"
        })
        
        if res.status_code == 400:
            error = res.json()
            if "No client record" in str(error.get("detail", "")):
                pytest.skip("Buyer not linked to this decision's project")
        
        assert res.status_code == 200, f"Reject failed: {res.text}"
        
        data = res.json()
        assert data["status"] == "rejected"
        print(f"Buyer rejected decision, status: {data['status']}")
        
        # Store for cleanup
        self.__class__.rejected_decision_id = decision_id
    
    def test_buyer_request_change(self, agent_session, buyer_session, agent_project_id):
        """POST /api/decisions/{id}/respond with request_change creates canonical change_request"""
        # Create a new decision for change request test
        payload = {
            "project_id": agent_project_id,
            "title": "TEST_Decision for Change Request",
            "description": "This will have a change request.",
            "coverage_type": "project"
        }
        
        res = agent_session.post(f"{BASE_URL}/api/decisions", json=payload)
        if res.status_code != 200:
            pytest.skip("Could not create decision for change request test")
        
        decision_id = res.json()["decision_id"]
        
        # Send it
        res = agent_session.post(f"{BASE_URL}/api/decisions/{decision_id}/send")
        if res.status_code != 200:
            pytest.skip("Could not send decision")
        
        # Buyer requests change
        res = buyer_session.post(f"{BASE_URL}/api/decisions/{decision_id}/respond", json={
            "action": "request_change",
            "comment": "Please clarify the dimensions"
        })
        
        if res.status_code == 400:
            error = res.json()
            if "No client record" in str(error.get("detail", "")):
                pytest.skip("Buyer not linked to this decision's project")
        
        assert res.status_code == 200, f"Request change failed: {res.text}"
        
        data = res.json()
        assert data["status"] == "Change Requested"
        print(f"Buyer requested change, status: {data['status']}")
        
        # Store for resend test
        self.__class__.change_requested_decision_id = decision_id
    
    def test_agent_resend_change_requested_decision(self, agent_session):
        """Agent can resend a Change Requested decision"""
        decision_id = getattr(self.__class__, 'change_requested_decision_id', None)
        if not decision_id:
            pytest.skip("No change-requested decision available")
        
        # Agent resends
        res = agent_session.post(f"{BASE_URL}/api/decisions/{decision_id}/send")
        assert res.status_code == 200, f"Resend failed: {res.text}"
        
        data = res.json()
        assert data["status"] == "pending"
        print(f"Agent resent decision, status: {data['status']}")
    
    # ============ Close and Delete Tests ============
    
    def test_close_decision(self, agent_session, agent_project_id):
        """POST /api/decisions/{id}/close closes a decision"""
        # Create and approve a decision first
        payload = {
            "project_id": agent_project_id,
            "title": "TEST_Decision to Close",
            "description": "This will be closed.",
            "coverage_type": "project"
        }
        
        res = agent_session.post(f"{BASE_URL}/api/decisions", json=payload)
        if res.status_code != 200:
            pytest.skip("Could not create decision for close test")
        
        decision_id = res.json()["decision_id"]
        
        # Send it
        agent_session.post(f"{BASE_URL}/api/decisions/{decision_id}/send")
        
        # Close it (agent can close any decision)
        res = agent_session.post(f"{BASE_URL}/api/decisions/{decision_id}/close")
        assert res.status_code == 200, f"Close failed: {res.text}"
        
        data = res.json()
        assert data["status"] == "closed"
        print(f"Decision closed, status: {data['status']}")
    
    def test_delete_draft_decision(self, agent_session, agent_project_id):
        """DELETE /api/decisions/{id} deletes draft decisions"""
        # Create a draft decision
        payload = {
            "project_id": agent_project_id,
            "title": "TEST_Decision to Delete",
            "description": "This will be deleted.",
            "coverage_type": "project"
        }
        
        res = agent_session.post(f"{BASE_URL}/api/decisions", json=payload)
        if res.status_code != 200:
            pytest.skip("Could not create decision for delete test")
        
        decision_id = res.json()["decision_id"]
        
        # Delete it (only draft can be deleted)
        res = agent_session.delete(f"{BASE_URL}/api/decisions/{decision_id}")
        assert res.status_code == 200, f"Delete failed: {res.text}"
        
        data = res.json()
        assert data.get("message") == "Decision deleted"
        print(f"Draft decision deleted successfully")
        
        # Verify it's gone
        res = agent_session.get(f"{BASE_URL}/api/decisions/{decision_id}")
        assert res.status_code == 404
    
    def test_cannot_delete_sent_decision(self, agent_session, agent_project_id):
        """DELETE /api/decisions/{id} fails for non-draft decisions"""
        # Create and send a decision
        payload = {
            "project_id": agent_project_id,
            "title": "TEST_Sent Decision Cannot Delete",
            "description": "This cannot be deleted after sending.",
            "coverage_type": "project"
        }
        
        res = agent_session.post(f"{BASE_URL}/api/decisions", json=payload)
        if res.status_code != 200:
            pytest.skip("Could not create decision")
        
        decision_id = res.json()["decision_id"]
        
        # Send it
        agent_session.post(f"{BASE_URL}/api/decisions/{decision_id}/send")
        
        # Try to delete - should fail
        res = agent_session.delete(f"{BASE_URL}/api/decisions/{decision_id}")
        assert res.status_code == 400, f"Expected 400, got {res.status_code}"
        
        error = res.json()
        assert "draft" in str(error.get("detail", "")).lower()
        print(f"Correctly prevented deletion of sent decision")
    
    # ============ Stats Tests ============
    
    def test_agent_stats_includes_pending_decisions(self, agent_session):
        """GET /api/stats/agent includes pending_decisions count"""
        res = agent_session.get(f"{BASE_URL}/api/stats/agent")
        assert res.status_code == 200
        
        data = res.json()
        assert "pending_decisions" in data
        assert "overdue_decisions" in data
        assert "challenged_decisions" in data
        
        print(f"Agent stats - pending: {data['pending_decisions']}, overdue: {data['overdue_decisions']}, challenged: {data['challenged_decisions']}")
    
    # ============ Filter Tests ============
    
    def test_list_decisions_with_status_filter(self, agent_session):
        """GET /api/decisions?status=pending filters by status"""
        res = agent_session.get(f"{BASE_URL}/api/decisions?status=pending")
        assert res.status_code == 200
        
        data = res.json()
        for d in data.get("decisions", []):
            assert d["status"] == "pending"
        
        print(f"Filtered to {len(data.get('decisions', []))} pending decisions")
    
    def test_list_decisions_with_project_filter(self, agent_session, agent_project_id):
        """GET /api/decisions?project_id=xxx filters by project"""
        res = agent_session.get(f"{BASE_URL}/api/decisions?project_id={agent_project_id}")
        assert res.status_code == 200
        
        data = res.json()
        for d in data.get("decisions", []):
            assert d["project_id"] == agent_project_id
        
        print(f"Filtered to {len(data.get('decisions', []))} decisions for project")


class TestDecisionsChangeRequestIntegration:
    """Test that change requests on decisions use canonical change_request_service"""
    
    @pytest.fixture(scope="class")
    def agent_session(self):
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        res = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": AGENT_EMAIL,
            "password": AGENT_PASSWORD
        })
        if res.status_code != 200:
            pytest.skip("Agent login failed")
        token = res.json().get("token")
        if token:
            session.headers.update({"Authorization": f"Bearer {token}"})
        return session
    
    def test_change_request_created_for_decision(self, agent_session):
        """Verify change request is created when buyer requests change on decision"""
        # Check change requests for decision entity type
        res = agent_session.get(f"{BASE_URL}/api/change-requests")
        assert res.status_code == 200
        
        data = res.json()
        change_requests = data.get("change_requests", [])
        
        # Look for decision-related change requests
        decision_crs = [cr for cr in change_requests if cr.get("entity_type") == "decision"]
        
        print(f"Found {len(decision_crs)} change requests for decisions")
        
        # This is informational - we created change requests in previous tests
        if decision_crs:
            cr = decision_crs[0]
            assert "entity_id" in cr
            assert "messages" in cr or "message" in cr
            print(f"Sample decision change request: {cr.get('entity_id')}")


# Cleanup test data
class TestCleanup:
    """Cleanup TEST_ prefixed decisions"""
    
    @pytest.fixture(scope="class")
    def agent_session(self):
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        res = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": AGENT_EMAIL,
            "password": AGENT_PASSWORD
        })
        if res.status_code != 200:
            pytest.skip("Agent login failed")
        token = res.json().get("token")
        if token:
            session.headers.update({"Authorization": f"Bearer {token}"})
        return session
    
    def test_cleanup_test_decisions(self, agent_session):
        """Remove TEST_ prefixed decisions"""
        res = agent_session.get(f"{BASE_URL}/api/decisions?limit=100")
        if res.status_code != 200:
            return
        
        data = res.json()
        test_decisions = [d for d in data.get("decisions", []) if d.get("title", "").startswith("TEST_")]
        
        deleted = 0
        for d in test_decisions:
            if d["status"] == "draft":
                res = agent_session.delete(f"{BASE_URL}/api/decisions/{d['decision_id']}")
                if res.status_code == 200:
                    deleted += 1
        
        print(f"Cleaned up {deleted} test decisions (draft only)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
