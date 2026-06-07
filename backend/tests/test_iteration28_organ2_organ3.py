"""
Iteration 28: Organ 2 (Canonical Formatters) & Organ 3 (Change Request Frontend) Tests

Tests:
1. Agent authentication
2. Buyer authentication  
3. Dashboard stats with change_requests
4. Quote list with client context
5. Invoice list with client context
6. Quote detail with ChangeRequestPanel
7. Invoice detail with ChangeRequestPanel
8. Buyer timeline with ChangeRequestThread
9. Change request thread visibility for resolved CRs
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://evo-access.preview.emergentagent.com')

# Test credentials
AGENT_EMAIL = "agent@evohome-test.ch"
AGENT_PASSWORD = "Evohome2026!"
BUYER_EMAIL = "buyer@evohome-test.ch"
BUYER_PASSWORD = "Evohome2026!"


class TestOrgan2Organ3:
    """Tests for Organ 2 (canonical formatters) and Organ 3 (CR frontend)"""
    
    agent_token = None
    buyer_token = None
    agent_id = None
    buyer_id = None
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup tokens for all tests"""
        import time
        
        # Agent login (with retry for rate limiting)
        for attempt in range(3):
            res = requests.post(f"{BASE_URL}/api/auth/login", json={
                "email": AGENT_EMAIL,
                "password": AGENT_PASSWORD
            })
            if res.status_code == 200:
                data = res.json()
                TestOrgan2Organ3.agent_token = data.get("token")
                # user_id is at top level, not nested
                TestOrgan2Organ3.agent_id = data.get("user_id")
                break
            elif res.status_code == 429:
                time.sleep(5)  # Wait for rate limit
        
        # Buyer login (with retry for rate limiting)
        for attempt in range(3):
            res = requests.post(f"{BASE_URL}/api/auth/buyer/login", json={
                "email": BUYER_EMAIL,
                "password": BUYER_PASSWORD
            })
            if res.status_code == 200:
                data = res.json()
                TestOrgan2Organ3.buyer_token = data.get("token")
                # user_id is at top level, not nested
                TestOrgan2Organ3.buyer_id = data.get("user_id")
                break
            elif res.status_code == 429:
                time.sleep(5)  # Wait for rate limit
    
    def get_agent_headers(self):
        return {"Authorization": f"Bearer {self.agent_token}"} if self.agent_token else {}
    
    def get_buyer_headers(self):
        return {"Authorization": f"Bearer {self.buyer_token}"} if self.buyer_token else {}
    
    # ─── Authentication Tests ───
    
    def test_01_agent_auth_valid(self):
        """Agent authentication works"""
        assert self.agent_token is not None, "Agent token should be set"
        assert self.agent_id is not None, "Agent ID should be set"
        print(f"✓ Agent authenticated: {self.agent_id}")
    
    def test_02_buyer_auth_valid(self):
        """Buyer authentication works"""
        assert self.buyer_token is not None, "Buyer token should be set"
        assert self.buyer_id is not None, "Buyer ID should be set"
        print(f"✓ Buyer authenticated: {self.buyer_id}")
    
    # ─── Dashboard Tests (Organ 2 - formatDocContext) ───
    
    def test_03_dashboard_stats_returns_change_requests(self):
        """Dashboard stats endpoint returns change_requests array"""
        res = requests.get(f"{BASE_URL}/api/stats/agent", headers=self.get_agent_headers())
        assert res.status_code == 200, f"Expected 200, got {res.status_code}"
        
        data = res.json()
        assert "change_requests" in data, "Response should have change_requests field"
        assert isinstance(data["change_requests"], list), "change_requests should be a list"
        
        # If there are change requests, verify they have required fields for formatDocContext
        if len(data["change_requests"]) > 0:
            cr = data["change_requests"][0]
            assert "document_id" in cr, "CR should have document_id"
            assert "title" in cr, "CR should have title"
            assert "type" in cr, "CR should have type (quote/invoice)"
            print(f"✓ Dashboard has {len(data['change_requests'])} change requests")
        else:
            print("✓ Dashboard stats returned (no active CRs)")
    
    def test_04_dashboard_stats_has_client_name(self):
        """Dashboard change requests have client_name for formatDocContext"""
        res = requests.get(f"{BASE_URL}/api/stats/agent", headers=self.get_agent_headers())
        assert res.status_code == 200
        
        data = res.json()
        if len(data.get("change_requests", [])) > 0:
            cr = data["change_requests"][0]
            # client_name is used by formatDocContext
            assert "client_name" in cr or "unit_reference" in cr, "CR should have client context fields"
            print(f"✓ CR has client context: {cr.get('client_name', 'N/A')}")
        else:
            print("✓ No CRs to verify client_name (acceptable)")
    
    # ─── Quote List Tests (Organ 2 - formatDocContext) ───
    
    def test_05_quotes_list_has_context_fields(self):
        """Quotes list returns fields needed for formatDocContext"""
        res = requests.get(f"{BASE_URL}/api/documents?doc_type=quote", headers=self.get_agent_headers())
        assert res.status_code == 200, f"Expected 200, got {res.status_code}"
        
        quotes = res.json()
        assert isinstance(quotes, list), "Response should be a list"
        
        if len(quotes) > 0:
            quote = quotes[0]
            # formatDocContext uses: document_number, client_name, project_name, unit_reference
            assert "document_number" in quote, "Quote should have document_number"
            assert "client_name" in quote or "unit_reference" in quote, "Quote should have client context"
            print(f"✓ Quotes list has {len(quotes)} quotes with context fields")
        else:
            print("✓ No quotes to verify (acceptable)")
    
    # ─── Invoice List Tests (Organ 2 - formatDocContext) ───
    
    def test_06_invoices_list_has_context_fields(self):
        """Invoices list returns fields needed for formatDocContext"""
        res = requests.get(f"{BASE_URL}/api/documents?doc_type=invoice", headers=self.get_agent_headers())
        assert res.status_code == 200, f"Expected 200, got {res.status_code}"
        
        invoices = res.json()
        assert isinstance(invoices, list), "Response should be a list"
        
        if len(invoices) > 0:
            invoice = invoices[0]
            assert "document_number" in invoice, "Invoice should have document_number"
            print(f"✓ Invoices list has {len(invoices)} invoices with context fields")
        else:
            print("✓ No invoices to verify (acceptable)")
    
    # ─── Clients List Tests (Organ 2 - formatClientContext) ───
    
    def test_07_clients_list_has_context_fields(self):
        """Clients list returns fields needed for formatClientContext"""
        res = requests.get(f"{BASE_URL}/api/clients", headers=self.get_agent_headers())
        assert res.status_code == 200, f"Expected 200, got {res.status_code}"
        
        clients = res.json()
        assert isinstance(clients, list), "Response should be a list"
        
        if len(clients) > 0:
            client = clients[0]
            # formatClientContext uses: name, project_name, unit_reference
            assert "name" in client, "Client should have name"
            assert "client_id" in client, "Client should have client_id"
            print(f"✓ Clients list has {len(clients)} clients with context fields")
        else:
            print("✓ No clients to verify (acceptable)")
    
    # ─── Change Request API Tests (Organ 3) ───
    
    def test_08_change_request_entity_endpoint(self):
        """Change request entity endpoint works"""
        # First get a document to test with
        res = requests.get(f"{BASE_URL}/api/documents?doc_type=quote", headers=self.get_agent_headers())
        if res.status_code != 200 or len(res.json()) == 0:
            pytest.skip("No quotes available for CR testing")
        
        quote = res.json()[0]
        doc_id = quote["document_id"]
        
        # Test the CR entity endpoint
        res = requests.get(
            f"{BASE_URL}/api/change-requests/entity/quote/{doc_id}",
            headers=self.get_agent_headers()
        )
        assert res.status_code == 200, f"Expected 200, got {res.status_code}"
        
        data = res.json()
        assert "change_requests" in data, "Response should have change_requests field"
        print(f"✓ CR entity endpoint works, found {len(data['change_requests'])} CRs for quote {doc_id}")
    
    def test_09_buyer_timeline_endpoint(self):
        """Buyer timeline endpoint works"""
        res = requests.get(f"{BASE_URL}/api/timeline", headers=self.get_buyer_headers())
        assert res.status_code == 200, f"Expected 200, got {res.status_code}"
        
        data = res.json()
        assert "documents" in data, "Response should have documents field"
        print(f"✓ Buyer timeline has {len(data['documents'])} documents")
    
    def test_10_buyer_can_see_cr_thread(self):
        """Buyer can fetch CR thread for their documents"""
        # Get buyer's documents
        res = requests.get(f"{BASE_URL}/api/timeline", headers=self.get_buyer_headers())
        if res.status_code != 200:
            pytest.skip("Cannot fetch buyer timeline")
        
        docs = res.json().get("documents", [])
        if len(docs) == 0:
            pytest.skip("No documents for buyer")
        
        # Try to fetch CR for first document
        doc = docs[0]
        doc_type = doc.get("type", "quote")
        doc_id = doc.get("id")
        
        res = requests.get(
            f"{BASE_URL}/api/change-requests/entity/{doc_type}/{doc_id}",
            headers=self.get_buyer_headers()
        )
        assert res.status_code == 200, f"Expected 200, got {res.status_code}"
        print(f"✓ Buyer can fetch CR thread for {doc_type} {doc_id}")
    
    # ─── Document Detail Tests (Organ 3 - ChangeRequestPanel) ───
    
    def test_11_quote_detail_has_cr_fields(self):
        """Quote detail returns fields needed for ChangeRequestPanel"""
        res = requests.get(f"{BASE_URL}/api/documents?doc_type=quote", headers=self.get_agent_headers())
        if res.status_code != 200 or len(res.json()) == 0:
            pytest.skip("No quotes available")
        
        quote_id = res.json()[0]["document_id"]
        
        res = requests.get(f"{BASE_URL}/api/documents/{quote_id}", headers=self.get_agent_headers())
        assert res.status_code == 200, f"Expected 200, got {res.status_code}"
        
        quote = res.json()
        assert "document_id" in quote, "Quote detail should have document_id"
        assert "type" in quote or "doc_type" in quote, "Quote detail should have type"
        print(f"✓ Quote detail has required fields for ChangeRequestPanel")
    
    def test_12_invoice_detail_has_cr_fields(self):
        """Invoice detail returns fields needed for ChangeRequestPanel"""
        res = requests.get(f"{BASE_URL}/api/documents?doc_type=invoice", headers=self.get_agent_headers())
        if res.status_code != 200 or len(res.json()) == 0:
            pytest.skip("No invoices available")
        
        invoice_id = res.json()[0]["document_id"]
        
        res = requests.get(f"{BASE_URL}/api/documents/{invoice_id}", headers=self.get_agent_headers())
        assert res.status_code == 200, f"Expected 200, got {res.status_code}"
        
        invoice = res.json()
        assert "document_id" in invoice, "Invoice detail should have document_id"
        print(f"✓ Invoice detail has required fields for ChangeRequestPanel")
    
    # ─── Projects/Decisions Tests (Organ 2 - formatClientContext) ───
    
    def test_13_projects_list_works(self):
        """Projects list endpoint works"""
        res = requests.get(f"{BASE_URL}/api/projects", headers=self.get_agent_headers())
        assert res.status_code == 200, f"Expected 200, got {res.status_code}"
        
        projects = res.json()
        assert isinstance(projects, list), "Response should be a list"
        print(f"✓ Projects list has {len(projects)} projects")
    
    def test_14_decisions_list_works(self):
        """Decisions list endpoint works"""
        res = requests.get(f"{BASE_URL}/api/decisions", headers=self.get_agent_headers())
        assert res.status_code == 200, f"Expected 200, got {res.status_code}"
        
        data = res.json()
        assert "decisions" in data, "Response should have decisions field"
        print(f"✓ Decisions list has {len(data['decisions'])} decisions")
    
    # ─── Vault Tests (Organ 2 - formatContextSubtitle) ───
    
    def test_15_vault_documents_list_works(self):
        """Vault documents list endpoint works"""
        res = requests.get(f"{BASE_URL}/api/vault/documents", headers=self.get_agent_headers())
        assert res.status_code == 200, f"Expected 200, got {res.status_code}"
        
        docs = res.json()
        assert isinstance(docs, list), "Response should be a list"
        print(f"✓ Vault has {len(docs)} documents")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
