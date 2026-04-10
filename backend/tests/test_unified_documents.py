"""
Comprehensive tests for UpgradeFlow Unified Document Model
Tests the complete flow: Quotes & Invoices via db.documents collection
State machine transitions and convert quote to invoice flow
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Demo credentials
AGENT_EMAIL = "demo.agent@upgradeflow.com"
AGENT_PASSWORD = "demo123"


class TestSetup:
    """Initial setup and demo data seeding"""
    
    def test_seed_demo_data(self):
        """Seed demo data before running tests"""
        res = requests.post(f"{BASE_URL}/api/demo/seed")
        assert res.status_code == 200
        data = res.json()
        assert "message" in data
        assert "Demo data seeded" in data["message"]


class TestAuthAndDocumentsEndpoint:
    """Test authentication and documents endpoints return both quotes and invoices"""
    
    @pytest.fixture(scope="class")
    def agent_token(self):
        """Get agent token"""
        res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": AGENT_EMAIL,
            "password": AGENT_PASSWORD
        })
        assert res.status_code == 200
        return res.json()["token"]
    
    @pytest.fixture(scope="class")
    def buyer_token(self):
        """Get buyer (Sophie) token via demo login"""
        res = requests.post(f"{BASE_URL}/api/auth/demo/buyer?buyer_num=1")
        assert res.status_code == 200
        return res.json()["token"]
    
    def test_agent_login(self, agent_token):
        """Test agent can login with demo credentials"""
        assert agent_token is not None
        assert len(agent_token) > 0
    
    def test_buyer_demo_login(self, buyer_token):
        """Test buyer can login via demo endpoint"""
        assert buyer_token is not None
        assert len(buyer_token) > 0
    
    def test_documents_endpoint_returns_quotes_and_invoices(self, agent_token):
        """Test /api/documents returns BOTH quotes and invoices from unified collection"""
        res = requests.get(
            f"{BASE_URL}/api/documents",
            headers={"Authorization": f"Bearer {agent_token}"}
        )
        assert res.status_code == 200
        docs = res.json()
        
        # Should have both quotes and invoices
        types = set(doc["type"] for doc in docs)
        assert "quote" in types, "Documents should include quotes"
        assert "invoice" in types, "Documents should include invoices"
        
        # Verify document structure
        for doc in docs:
            assert "document_id" in doc
            assert "type" in doc
            assert "status" in doc
            assert "amount" in doc
            assert doc["type"] in ["quote", "invoice"]
    
    def test_filter_documents_by_type(self, agent_token):
        """Test filtering documents by type"""
        # Filter quotes only
        res = requests.get(
            f"{BASE_URL}/api/documents?doc_type=quote",
            headers={"Authorization": f"Bearer {agent_token}"}
        )
        assert res.status_code == 200
        quotes = res.json()
        for doc in quotes:
            assert doc["type"] == "quote"
        
        # Filter invoices only
        res = requests.get(
            f"{BASE_URL}/api/documents?doc_type=invoice",
            headers={"Authorization": f"Bearer {agent_token}"}
        )
        assert res.status_code == 200
        invoices = res.json()
        for doc in invoices:
            assert doc["type"] == "invoice"


class TestBuyerTimeline:
    """Test buyer timeline shows all documents"""
    
    @pytest.fixture(scope="class")
    def buyer_token(self):
        """Get buyer token"""
        res = requests.post(f"{BASE_URL}/api/auth/demo/buyer?buyer_num=1")
        assert res.status_code == 200
        return res.json()["token"]
    
    def test_buyer_timeline_shows_all_documents(self, buyer_token):
        """Test /api/timeline returns quotes and invoices for buyer"""
        res = requests.get(
            f"{BASE_URL}/api/timeline",
            headers={"Authorization": f"Bearer {buyer_token}"}
        )
        assert res.status_code == 200
        data = res.json()
        
        assert "documents" in data
        assert "project_info" in data
        
        # Check document types
        docs = data["documents"]
        types = set(doc["type"] for doc in docs)
        assert "quote" in types or "invoice" in types, "Timeline should have documents"
        
        # Verify timeline format
        for doc in docs:
            assert "id" in doc
            assert "type" in doc
            assert "title" in doc
            assert "status" in doc
            assert "actionRequired" in doc
    
    def test_buyer_timeline_excludes_drafts(self, buyer_token):
        """Test buyer timeline excludes Draft status documents"""
        res = requests.get(
            f"{BASE_URL}/api/timeline",
            headers={"Authorization": f"Bearer {buyer_token}"}
        )
        assert res.status_code == 200
        docs = res.json()["documents"]
        
        # Buyers should NOT see Draft documents
        for doc in docs:
            assert doc["status"] != "Draft", "Buyer should not see Draft documents"
    
    def test_buyer_timeline_has_project_info(self, buyer_token):
        """Test timeline includes project information"""
        res = requests.get(
            f"{BASE_URL}/api/timeline",
            headers={"Authorization": f"Bearer {buyer_token}"}
        )
        assert res.status_code == 200
        data = res.json()
        
        project = data["project_info"]
        if project:
            assert "project_id" in project
            assert "name" in project
            assert "unit_reference" in project


class TestQuoteApprovalFlow:
    """Test buyer approving a quote"""
    
    @pytest.fixture(scope="class")
    def buyer_token(self):
        """Get buyer token"""
        res = requests.post(f"{BASE_URL}/api/auth/demo/buyer?buyer_num=1")
        assert res.status_code == 200
        return res.json()["token"]
    
    @pytest.fixture(scope="class")
    def agent_token(self):
        """Get agent token"""
        res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": AGENT_EMAIL,
            "password": AGENT_PASSWORD
        })
        assert res.status_code == 200
        return res.json()["token"]
    
    def test_buyer_approves_quote(self, buyer_token, agent_token):
        """Test buyer can approve a Sent quote"""
        # First, find a Sent quote for this buyer
        timeline_res = requests.get(
            f"{BASE_URL}/api/timeline",
            headers={"Authorization": f"Bearer {buyer_token}"}
        )
        assert timeline_res.status_code == 200
        
        docs = timeline_res.json()["documents"]
        sent_quote = None
        for doc in docs:
            if doc["type"] == "quote" and doc["status"] == "Sent":
                sent_quote = doc
                break
        
        if not sent_quote:
            pytest.skip("No Sent quote available for testing approval")
        
        # Approve the quote
        res = requests.post(
            f"{BASE_URL}/api/documents/{sent_quote['id']}/action",
            headers={"Authorization": f"Bearer {buyer_token}"},
            json={"action": "approve"}
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "Approved"
        
        # Verify the quote is now Approved
        verify_res = requests.get(
            f"{BASE_URL}/api/documents/{sent_quote['id']}",
            headers={"Authorization": f"Bearer {buyer_token}"}
        )
        assert verify_res.status_code == 200
        assert verify_res.json()["status"] == "Approved"


class TestConvertToInvoiceFlow:
    """Test agent converting approved quote to invoice"""
    
    @pytest.fixture(scope="class")
    def agent_token(self):
        """Get agent token"""
        res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": AGENT_EMAIL,
            "password": AGENT_PASSWORD
        })
        assert res.status_code == 200
        return res.json()["token"]
    
    def test_convert_approved_quote_to_invoice(self, agent_token):
        """Test agent can convert an Approved quote to invoice"""
        # Find an Approved quote
        docs_res = requests.get(
            f"{BASE_URL}/api/documents?doc_type=quote&status=Approved",
            headers={"Authorization": f"Bearer {agent_token}"}
        )
        assert docs_res.status_code == 200
        
        quotes = docs_res.json()
        approved_quote = None
        for q in quotes:
            if q["status"] == "Approved":
                approved_quote = q
                break
        
        if not approved_quote:
            pytest.skip("No Approved quote available for conversion test")
        
        # Convert to invoice
        res = requests.post(
            f"{BASE_URL}/api/documents/{approved_quote['document_id']}/action",
            headers={"Authorization": f"Bearer {agent_token}"},
            json={"action": "convert_to_invoice"}
        )
        assert res.status_code == 200
        data = res.json()
        assert "invoice_id" in data
        assert "invoice_number" in data
        
        # Verify invoice was created with parent_document_id linking
        invoice_res = requests.get(
            f"{BASE_URL}/api/documents/{data['invoice_id']}",
            headers={"Authorization": f"Bearer {agent_token}"}
        )
        assert invoice_res.status_code == 200
        invoice = invoice_res.json()
        
        assert invoice["type"] == "invoice"
        assert invoice["status"] == "Draft"
        assert invoice["parent_document_id"] == approved_quote["document_id"]
        assert invoice["amount"] == approved_quote["amount"]


class TestSendInvoiceFlow:
    """Test agent sending invoice to buyer"""
    
    @pytest.fixture(scope="class")
    def agent_token(self):
        """Get agent token"""
        res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": AGENT_EMAIL,
            "password": AGENT_PASSWORD
        })
        assert res.status_code == 200
        return res.json()["token"]
    
    def test_send_invoice_to_buyer(self, agent_token):
        """Test agent can send a Draft invoice"""
        # Find a Draft invoice
        docs_res = requests.get(
            f"{BASE_URL}/api/documents?doc_type=invoice",
            headers={"Authorization": f"Bearer {agent_token}"}
        )
        assert docs_res.status_code == 200
        
        invoices = docs_res.json()
        draft_invoice = None
        for inv in invoices:
            if inv["status"] == "Draft":
                draft_invoice = inv
                break
        
        if not draft_invoice:
            pytest.skip("No Draft invoice available for sending")
        
        # Send the invoice
        res = requests.post(
            f"{BASE_URL}/api/documents/{draft_invoice['document_id']}/send",
            headers={"Authorization": f"Bearer {agent_token}"}
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "Sent"
        
        # Verify status change
        verify_res = requests.get(
            f"{BASE_URL}/api/documents/{draft_invoice['document_id']}",
            headers={"Authorization": f"Bearer {agent_token}"}
        )
        assert verify_res.status_code == 200
        assert verify_res.json()["status"] == "Sent"


class TestPaymentConfirmation:
    """Test buyer confirming payment"""
    
    @pytest.fixture(scope="class")
    def buyer_token(self):
        """Get buyer token"""
        res = requests.post(f"{BASE_URL}/api/auth/demo/buyer?buyer_num=1")
        assert res.status_code == 200
        return res.json()["token"]
    
    def test_buyer_confirms_payment(self, buyer_token):
        """Test buyer can confirm payment for a Sent invoice"""
        # Find a Sent invoice
        timeline_res = requests.get(
            f"{BASE_URL}/api/timeline",
            headers={"Authorization": f"Bearer {buyer_token}"}
        )
        assert timeline_res.status_code == 200
        
        docs = timeline_res.json()["documents"]
        sent_invoice = None
        for doc in docs:
            if doc["type"] == "invoice" and doc["status"] == "Sent":
                sent_invoice = doc
                break
        
        if not sent_invoice:
            pytest.skip("No Sent invoice available for payment confirmation")
        
        # Confirm payment
        res = requests.post(
            f"{BASE_URL}/api/documents/{sent_invoice['id']}/action",
            headers={"Authorization": f"Bearer {buyer_token}"},
            json={"action": "confirm_payment"}
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "Paid"


class TestStateMachineEnforcement:
    """Test that invalid state transitions are blocked"""
    
    @pytest.fixture(scope="class")
    def agent_token(self):
        """Get agent token"""
        res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": AGENT_EMAIL,
            "password": AGENT_PASSWORD
        })
        assert res.status_code == 200
        return res.json()["token"]
    
    @pytest.fixture(scope="class")
    def buyer_token(self):
        """Get buyer token"""
        res = requests.post(f"{BASE_URL}/api/auth/demo/buyer?buyer_num=1")
        assert res.status_code == 200
        return res.json()["token"]
    
    def test_cannot_approve_non_sent_quote(self, buyer_token):
        """Test buyer cannot approve a quote that's not in Sent status"""
        # Find an Approved or Rejected quote
        timeline_res = requests.get(
            f"{BASE_URL}/api/timeline",
            headers={"Authorization": f"Bearer {buyer_token}"}
        )
        docs = timeline_res.json()["documents"]
        
        non_sent_quote = None
        for doc in docs:
            if doc["type"] == "quote" and doc["status"] not in ["Sent"]:
                non_sent_quote = doc
                break
        
        if not non_sent_quote:
            pytest.skip("No non-Sent quote available for testing")
        
        # Try to approve - should fail
        res = requests.post(
            f"{BASE_URL}/api/documents/{non_sent_quote['id']}/action",
            headers={"Authorization": f"Bearer {buyer_token}"},
            json={"action": "approve"}
        )
        assert res.status_code == 400
    
    def test_cannot_convert_non_approved_quote(self, agent_token):
        """Test agent cannot convert a quote that's not Approved"""
        # Find a Sent quote
        docs_res = requests.get(
            f"{BASE_URL}/api/documents?doc_type=quote",
            headers={"Authorization": f"Bearer {agent_token}"}
        )
        quotes = docs_res.json()
        
        non_approved = None
        for q in quotes:
            if q["status"] != "Approved":
                non_approved = q
                break
        
        if not non_approved:
            pytest.skip("No non-Approved quote available for testing")
        
        # Try to convert - should fail
        res = requests.post(
            f"{BASE_URL}/api/documents/{non_approved['document_id']}/action",
            headers={"Authorization": f"Bearer {agent_token}"},
            json={"action": "convert_to_invoice"}
        )
        assert res.status_code == 400
    
    def test_cannot_send_already_sent_document(self, agent_token):
        """Test agent cannot send a document that's already Sent"""
        # Find a Sent document
        docs_res = requests.get(
            f"{BASE_URL}/api/documents",
            headers={"Authorization": f"Bearer {agent_token}"}
        )
        docs = docs_res.json()
        
        sent_doc = None
        for d in docs:
            if d["status"] == "Sent":
                sent_doc = d
                break
        
        if not sent_doc:
            pytest.skip("No Sent document available")
        
        # Try to send again - should fail
        res = requests.post(
            f"{BASE_URL}/api/documents/{sent_doc['document_id']}/send",
            headers={"Authorization": f"Bearer {agent_token}"}
        )
        assert res.status_code == 400
    
    def test_cannot_pay_non_sent_invoice(self, buyer_token):
        """Test buyer cannot confirm payment for non-Sent invoice"""
        # Find a Paid invoice
        timeline_res = requests.get(
            f"{BASE_URL}/api/timeline",
            headers={"Authorization": f"Bearer {buyer_token}"}
        )
        docs = timeline_res.json()["documents"]
        
        paid_invoice = None
        for doc in docs:
            if doc["type"] == "invoice" and doc["status"] == "Paid":
                paid_invoice = doc
                break
        
        if not paid_invoice:
            pytest.skip("No Paid invoice available for testing")
        
        # Try to pay again - should fail
        res = requests.post(
            f"{BASE_URL}/api/documents/{paid_invoice['id']}/action",
            headers={"Authorization": f"Bearer {buyer_token}"},
            json={"action": "confirm_payment"}
        )
        assert res.status_code == 400


class TestDocumentHistory:
    """Test timeline shows full document history with parent linking"""
    
    @pytest.fixture(scope="class")
    def buyer_token(self):
        """Get buyer token"""
        res = requests.post(f"{BASE_URL}/api/auth/demo/buyer?buyer_num=1")
        assert res.status_code == 200
        return res.json()["token"]
    
    def test_invoice_shows_parent_document_link(self, buyer_token):
        """Test invoices created from quotes have parent_document_id"""
        timeline_res = requests.get(
            f"{BASE_URL}/api/timeline",
            headers={"Authorization": f"Bearer {buyer_token}"}
        )
        assert timeline_res.status_code == 200
        
        docs = timeline_res.json()["documents"]
        
        # Check if any invoice has parent_document_id
        linked_invoices = [d for d in docs if d["type"] == "invoice" and d.get("parentDocumentId")]
        
        # If we have linked invoices, verify the link is valid
        if linked_invoices:
            for inv in linked_invoices:
                assert inv["parentDocumentId"] is not None


class TestQuoteChangeRequest:
    """Test buyer requesting changes on a quote"""
    
    @pytest.fixture(scope="class")
    def buyer_token(self):
        """Get buyer 2 token (Thomas Weber) who has Sent quotes"""
        res = requests.post(f"{BASE_URL}/api/auth/demo/buyer?buyer_num=2")
        assert res.status_code == 200
        return res.json()["token"]
    
    def test_buyer_requests_change(self, buyer_token):
        """Test buyer can request changes on a Sent quote"""
        # Find a Sent quote for buyer 2
        timeline_res = requests.get(
            f"{BASE_URL}/api/timeline",
            headers={"Authorization": f"Bearer {buyer_token}"}
        )
        assert timeline_res.status_code == 200
        
        docs = timeline_res.json()["documents"]
        sent_quote = None
        for doc in docs:
            if doc["type"] == "quote" and doc["status"] == "Sent":
                sent_quote = doc
                break
        
        if not sent_quote:
            pytest.skip("No Sent quote available for change request test")
        
        # Request change
        res = requests.post(
            f"{BASE_URL}/api/documents/{sent_quote['id']}/action",
            headers={"Authorization": f"Bearer {buyer_token}"},
            json={"action": "request_change", "comment": "Can we use different flooring material?"}
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "Change Requested"
    
    def test_change_request_requires_comment(self, buyer_token):
        """Test change request fails without comment"""
        # Find a Sent quote
        timeline_res = requests.get(
            f"{BASE_URL}/api/timeline",
            headers={"Authorization": f"Bearer {buyer_token}"}
        )
        docs = timeline_res.json()["documents"]
        
        sent_quote = None
        for doc in docs:
            if doc["type"] == "quote" and doc["status"] == "Sent":
                sent_quote = doc
                break
        
        if not sent_quote:
            pytest.skip("No Sent quote available")
        
        # Try without comment - should fail
        res = requests.post(
            f"{BASE_URL}/api/documents/{sent_quote['id']}/action",
            headers={"Authorization": f"Bearer {buyer_token}"},
            json={"action": "request_change"}
        )
        assert res.status_code == 400


class TestAgentStats:
    """Test agent dashboard statistics"""
    
    @pytest.fixture(scope="class")
    def agent_token(self):
        """Get agent token"""
        res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": AGENT_EMAIL,
            "password": AGENT_PASSWORD
        })
        assert res.status_code == 200
        return res.json()["token"]
    
    def test_agent_stats_endpoint(self, agent_token):
        """Test /api/stats/agent returns proper statistics"""
        res = requests.get(
            f"{BASE_URL}/api/stats/agent",
            headers={"Authorization": f"Bearer {agent_token}"}
        )
        assert res.status_code == 200
        data = res.json()
        
        assert "total_clients" in data
        assert "pending_quotes" in data
        assert "pending_invoices" in data
        assert "total_revenue" in data
        assert "recent_documents" in data
        assert "approved_quotes" in data


class TestBuyerStats:
    """Test buyer dashboard statistics"""
    
    @pytest.fixture(scope="class")
    def buyer_token(self):
        """Get buyer token"""
        res = requests.post(f"{BASE_URL}/api/auth/demo/buyer?buyer_num=1")
        assert res.status_code == 200
        return res.json()["token"]
    
    def test_buyer_stats_endpoint(self, buyer_token):
        """Test /api/stats/buyer returns proper statistics"""
        res = requests.get(
            f"{BASE_URL}/api/stats/buyer",
            headers={"Authorization": f"Bearer {buyer_token}"}
        )
        assert res.status_code == 200
        data = res.json()
        
        assert "pending_quotes" in data
        assert "pending_invoices" in data
        assert "total_paid" in data
        assert "projects" in data
