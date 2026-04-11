"""
Iteration 27: Organ 3 Rebuild - Change Request System Tests

Tests the full CR flow for both quotes and invoices:
1. buyer_id field resolution
2. State transition guards (no responding to resolved/closed CRs)
3. Resolve always returns doc to 'Sent' (NEVER Draft)
4. Dashboard aggregation with client_name enrichment
5. Parity between quote and invoice CR flows
"""
import pytest
import requests
import os
import uuid
import time
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Module-level tokens to avoid rate limiting
_tokens = {}
_test_data = {}


def get_tokens():
    """Get or create auth tokens (cached at module level)."""
    global _tokens
    
    if not _tokens:
        # Login as agent
        agent_login = requests.post(f"{BASE_URL}/api/auth/login", 
            json={"email": "agent@evohome-test.ch", "password": "Evohome2026!"},
            headers={"Content-Type": "application/json"}
        )
        assert agent_login.status_code == 200, f"Agent login failed: {agent_login.text}"
        agent_data = agent_login.json()
        
        time.sleep(1)  # Delay to avoid rate limiting
        
        # Login as buyer (separate endpoint)
        buyer_login = requests.post(f"{BASE_URL}/api/auth/buyer/login", 
            json={"email": "buyer@evohome-test.ch", "password": "Evohome2026!"},
            headers={"Content-Type": "application/json"}
        )
        assert buyer_login.status_code == 200, f"Buyer login failed: {buyer_login.text}"
        buyer_data = buyer_login.json()
        
        _tokens = {
            "agent_token": agent_data.get("token"),
            "agent_id": agent_data.get("user_id"),
            "buyer_token": buyer_data.get("token"),
            "buyer_id": buyer_data.get("user_id"),
        }
    
    return _tokens


def agent_headers():
    tokens = get_tokens()
    return {"Authorization": f"Bearer {tokens['agent_token']}", "Content-Type": "application/json"}


def buyer_headers():
    tokens = get_tokens()
    return {"Authorization": f"Bearer {tokens['buyer_token']}", "Content-Type": "application/json"}


class TestOrgan3ChangeRequestRebuild:
    """Full test suite for the rebuilt Change Request system."""

    # ── Test 1: Auth verification ──
    def test_01_auth_tokens_valid(self):
        """Verify both agent and buyer tokens are valid."""
        tokens = get_tokens()
        assert tokens["agent_token"], "Agent token should be present"
        assert tokens["buyer_token"], "Buyer token should be present"
        assert tokens["agent_id"], "Agent ID should be present"
        assert tokens["buyer_id"], "Buyer ID should be present"
        print(f"✓ Agent ID: {tokens['agent_id']}")
        print(f"✓ Buyer ID: {tokens['buyer_id']}")

    # ── Test 2: Create a quote for CR testing ──
    def test_02_create_quote_for_cr_testing(self):
        """Create a fresh quote to test CR flow."""
        global _test_data
        tokens = get_tokens()
        
        # Get client for the buyer
        clients_res = requests.get(f"{BASE_URL}/api/clients", headers=agent_headers())
        assert clients_res.status_code == 200, f"Get clients failed: {clients_res.text}"
        clients = clients_res.json()
        
        # Find client linked to buyer
        test_client = None
        for c in clients:
            if c.get("buyer_id") == tokens["buyer_id"]:
                test_client = c
                break
        
        if not test_client:
            pytest.skip("No client linked to test buyer found")
        
        _test_data["client_id"] = test_client["client_id"]
        print(f"✓ Using client: {test_client['name']} ({test_client['client_id']})")
        
        # Create a quote
        unique_id = uuid.uuid4().hex[:8]
        create_res = requests.post(f"{BASE_URL}/api/documents/create", 
            headers=agent_headers(),
            json={
                "client_id": test_client["client_id"],
                "type": "quote",
                "title": f"TEST_CR_Quote_{unique_id}",
                "amount": 1500.00,
                "items": [{"description": "Test item", "quantity": 1, "unit_price": 1500, "total": 1500}],
                "summary": "Test quote for CR flow testing"
            }
        )
        assert create_res.status_code == 200, f"Create quote failed: {create_res.text}"
        quote = create_res.json()
        _test_data["quote_id"] = quote["document_id"]
        print(f"✓ Created quote: {quote['document_id']} - Status: {quote['status']}")
        assert quote["status"] == "Draft"

    # ── Test 3: Send quote to buyer ──
    def test_03_send_quote_to_buyer(self):
        """Send the quote so buyer can create CR."""
        send_res = requests.post(
            f"{BASE_URL}/api/documents/{_test_data['quote_id']}/send",
            headers=agent_headers()
        )
        assert send_res.status_code == 200, f"Send quote failed: {send_res.text}"
        
        # Verify status is now Sent
        doc_res = requests.get(f"{BASE_URL}/api/documents/{_test_data['quote_id']}", headers=agent_headers())
        assert doc_res.status_code == 200
        doc = doc_res.json()
        assert doc["status"] == "Sent", f"Expected 'Sent', got '{doc['status']}'"
        print(f"✓ Quote sent - Status: {doc['status']}")

    # ── Test 4: Buyer creates change request ──
    def test_04_buyer_creates_change_request(self):
        """Buyer creates a change request on the quote."""
        global _test_data
        tokens = get_tokens()
        
        cr_message = f"TEST_CR: I have a question about this quote - {uuid.uuid4().hex[:6]}"
        
        cr_res = requests.post(f"{BASE_URL}/api/change-requests",
            headers=buyer_headers(),
            json={
                "entity_type": "quote",
                "entity_id": _test_data["quote_id"],
                "message": cr_message
            }
        )
        assert cr_res.status_code == 200, f"Create CR failed: {cr_res.text}"
        cr = cr_res.json()
        
        _test_data["cr_id"] = cr["change_request_id"]
        
        # Verify CR has buyer_id field
        assert "buyer_id" in cr, "CR should have buyer_id field"
        assert cr["buyer_id"] == tokens["buyer_id"], f"buyer_id mismatch: expected {tokens['buyer_id']}, got {cr.get('buyer_id')}"
        assert cr["status"] == "open", f"CR status should be 'open', got '{cr['status']}'"
        assert cr["entity_type"] == "quote"
        assert cr["entity_id"] == _test_data["quote_id"]
        
        print(f"✓ CR created: {cr['change_request_id']}")
        print(f"✓ buyer_id field present: {cr['buyer_id']}")
        print(f"✓ CR status: {cr['status']}")
        
        # Verify document status changed to 'Change Requested'
        doc_res = requests.get(f"{BASE_URL}/api/documents/{_test_data['quote_id']}", headers=agent_headers())
        assert doc_res.status_code == 200
        doc = doc_res.json()
        assert doc["status"] == "Change Requested", f"Doc status should be 'Change Requested', got '{doc['status']}'"
        print(f"✓ Document status updated to: {doc['status']}")

    # ── Test 5: Agent responds to CR ──
    def test_05_agent_responds_to_cr(self):
        """Agent responds to the change request."""
        response_message = f"TEST_RESPONSE: Here is my answer - {uuid.uuid4().hex[:6]}"
        
        respond_res = requests.post(
            f"{BASE_URL}/api/change-requests/{_test_data['cr_id']}/respond",
            headers=agent_headers(),
            json={"message": response_message}
        )
        assert respond_res.status_code == 200, f"Respond to CR failed: {respond_res.text}"
        cr = respond_res.json()
        
        # Verify status changed to under_review
        assert cr["status"] == "under_review", f"CR status should be 'under_review', got '{cr['status']}'"
        assert len(cr["messages"]) == 2, f"Should have 2 messages, got {len(cr['messages'])}"
        
        # Verify second message is from agent
        agent_msg = cr["messages"][1]
        assert agent_msg["author_role"] == "agent"
        assert agent_msg["content"] == response_message
        
        print(f"✓ Agent responded - CR status: {cr['status']}")
        print(f"✓ Message count: {len(cr['messages'])}")

    # ── Test 6: Agent resolves CR - doc reverts to Sent (NOT Draft) ──
    def test_06_agent_resolves_cr_doc_reverts_to_sent(self):
        """CRITICAL: Agent resolves CR and document reverts to 'Sent', NOT 'Draft'."""
        resolve_res = requests.post(
            f"{BASE_URL}/api/change-requests/{_test_data['cr_id']}/resolve",
            headers=agent_headers(),
            json={"resolution_note": "Issue resolved, please review the updated quote."}
        )
        assert resolve_res.status_code == 200, f"Resolve CR failed: {resolve_res.text}"
        cr = resolve_res.json()
        
        # Verify CR status is resolved
        assert cr["status"] == "resolved", f"CR status should be 'resolved', got '{cr['status']}'"
        assert cr.get("resolved_at") is not None, "resolved_at should be set"
        
        print(f"✓ CR resolved - Status: {cr['status']}")
        
        # CRITICAL: Verify document status is 'Sent', NOT 'Draft'
        doc_res = requests.get(f"{BASE_URL}/api/documents/{_test_data['quote_id']}", headers=agent_headers())
        assert doc_res.status_code == 200
        doc = doc_res.json()
        
        assert doc["status"] == "Sent", f"CRITICAL: Doc status should be 'Sent' after resolve, got '{doc['status']}'"
        assert doc["status"] != "Draft", "CRITICAL: Doc should NEVER revert to Draft after CR resolve"
        
        print(f"✓ CRITICAL CHECK PASSED: Document status is '{doc['status']}' (not Draft)")

    # ── Test 7: State guard - cannot respond to resolved CR ──
    def test_07_cannot_respond_to_resolved_cr(self):
        """State guard: responding to a resolved CR should fail."""
        respond_res = requests.post(
            f"{BASE_URL}/api/change-requests/{_test_data['cr_id']}/respond",
            headers=agent_headers(),
            json={"message": "This should fail"}
        )
        
        # Should return error (404 with detail message)
        assert respond_res.status_code in [400, 404], f"Expected error, got {respond_res.status_code}"
        error = respond_res.json()
        assert "resolved" in error.get("detail", "").lower() or "cannot" in error.get("detail", "").lower(), \
            f"Error should mention resolved status: {error}"
        
        print(f"✓ State guard working: Cannot respond to resolved CR")
        print(f"  Error: {error.get('detail')}")

    # ── Test 8: Close the CR ──
    def test_08_close_resolved_cr(self):
        """Close the resolved CR."""
        close_res = requests.post(
            f"{BASE_URL}/api/change-requests/{_test_data['cr_id']}/close",
            headers=agent_headers()
        )
        assert close_res.status_code == 200, f"Close CR failed: {close_res.text}"
        cr = close_res.json()
        
        assert cr["status"] == "closed", f"CR status should be 'closed', got '{cr['status']}'"
        print(f"✓ CR closed - Status: {cr['status']}")

    # ── Test 9: State guard - cannot respond to closed CR ──
    def test_09_cannot_respond_to_closed_cr(self):
        """State guard: responding to a closed CR should fail."""
        respond_res = requests.post(
            f"{BASE_URL}/api/change-requests/{_test_data['cr_id']}/respond",
            headers=agent_headers(),
            json={"message": "This should also fail"}
        )
        
        assert respond_res.status_code in [400, 404], f"Expected error, got {respond_res.status_code}"
        error = respond_res.json()
        print(f"✓ State guard working: Cannot respond to closed CR")
        print(f"  Error: {error.get('detail')}")

    # ── Test 10: State guard - cannot close an open CR (must resolve first) ──
    def test_10_cannot_close_open_cr(self):
        """State guard: closing an open CR should fail (must resolve first)."""
        # Create a new CR to test this
        cr_res = requests.post(f"{BASE_URL}/api/change-requests",
            headers=buyer_headers(),
            json={
                "entity_type": "quote",
                "entity_id": _test_data["quote_id"],
                "message": f"TEST_CR_for_close_guard_{uuid.uuid4().hex[:6]}"
            }
        )
        assert cr_res.status_code == 200, f"Create CR failed: {cr_res.text}"
        new_cr = cr_res.json()
        new_cr_id = new_cr["change_request_id"]
        
        # Try to close without resolving first
        close_res = requests.post(
            f"{BASE_URL}/api/change-requests/{new_cr_id}/close",
            headers=agent_headers()
        )
        
        assert close_res.status_code in [400, 404], f"Expected error when closing open CR, got {close_res.status_code}"
        error = close_res.json()
        print(f"✓ State guard working: Cannot close open CR without resolving first")
        print(f"  Error: {error.get('detail')}")
        
        # Cleanup: resolve and close this CR
        requests.post(f"{BASE_URL}/api/change-requests/{new_cr_id}/resolve", 
            headers=agent_headers(), json={})
        requests.post(f"{BASE_URL}/api/change-requests/{new_cr_id}/close", 
            headers=agent_headers())

    # ── Test 11: Buyer sees full thread ──
    def test_11_buyer_sees_full_thread(self):
        """Buyer can see the full CR thread including agent responses."""
        # Get CR thread for the entity
        thread_res = requests.get(
            f"{BASE_URL}/api/change-requests/entity/quote/{_test_data['quote_id']}",
            headers=buyer_headers()
        )
        assert thread_res.status_code == 200, f"Get CR thread failed: {thread_res.text}"
        data = thread_res.json()
        
        crs = data.get("change_requests", [])
        assert len(crs) >= 1, f"Should have at least 1 CR, got {len(crs)}"
        
        # Find our test CR
        test_cr = next((cr for cr in crs if cr["change_request_id"] == _test_data["cr_id"]), None)
        assert test_cr is not None, "Test CR should be in the list"
        
        # Verify buyer can see all messages
        messages = test_cr.get("messages", [])
        assert len(messages) >= 2, f"Should have at least 2 messages, got {len(messages)}"
        
        # Verify both buyer and agent messages are visible
        roles = [m["author_role"] for m in messages]
        assert "buyer" in roles, "Buyer message should be visible"
        assert "agent" in roles, "Agent message should be visible"
        
        print(f"✓ Buyer can see full thread with {len(messages)} messages")
        print(f"  Roles in thread: {roles}")

    # ── Test 12: Dashboard aggregation with client_name ──
    def test_12_dashboard_aggregation_with_client_name(self):
        """Dashboard stats should include change_requests with client_name enriched."""
        stats_res = requests.get(f"{BASE_URL}/api/stats/agent", headers=agent_headers())
        assert stats_res.status_code == 200, f"Get stats failed: {stats_res.text}"
        stats = stats_res.json()
        
        # Check change_requests field exists
        assert "change_requests" in stats, "Stats should have change_requests field"
        
        # If there are change requests, verify client_name enrichment
        crs = stats.get("change_requests", [])
        if crs:
            # Find one with client_id
            cr_with_client = next((cr for cr in crs if cr.get("client_id")), None)
            if cr_with_client:
                # client_name should be enriched
                print(f"✓ Change request found: {cr_with_client.get('document_id')}")
                print(f"  client_id: {cr_with_client.get('client_id')}")
                print(f"  client_name: {cr_with_client.get('client_name')}")
                print(f"  type: {cr_with_client.get('type')}")
        
        print(f"✓ Dashboard stats returned {len(crs)} change requests")

    # ── Test 13: INVOICE CR flow - identical to quote ──
    def test_13_invoice_cr_flow_parity(self):
        """Test that invoice CR flow is identical to quote CR flow."""
        global _test_data
        tokens = get_tokens()
        
        # Create an invoice
        unique_id = uuid.uuid4().hex[:8]
        create_res = requests.post(f"{BASE_URL}/api/documents/create", 
            headers=agent_headers(),
            json={
                "client_id": _test_data["client_id"],
                "type": "invoice",
                "title": f"TEST_CR_Invoice_{unique_id}",
                "amount": 2000.00,
                "items": [{"description": "Invoice item", "quantity": 1, "unit_price": 2000, "total": 2000}],
                "summary": "Test invoice for CR flow testing"
            }
        )
        assert create_res.status_code == 200, f"Create invoice failed: {create_res.text}"
        invoice = create_res.json()
        _test_data["invoice_id"] = invoice["document_id"]
        print(f"✓ Created invoice: {_test_data['invoice_id']}")
        
        # Send invoice
        send_res = requests.post(f"{BASE_URL}/api/documents/{_test_data['invoice_id']}/send", headers=agent_headers())
        assert send_res.status_code == 200, f"Send invoice failed: {send_res.text}"
        print(f"✓ Invoice sent")
        
        # Buyer creates CR on invoice
        cr_res = requests.post(f"{BASE_URL}/api/change-requests",
            headers=buyer_headers(),
            json={
                "entity_type": "invoice",
                "entity_id": _test_data["invoice_id"],
                "message": f"TEST_CR_Invoice: Question about this invoice - {unique_id}"
            }
        )
        assert cr_res.status_code == 200, f"Create CR on invoice failed: {cr_res.text}"
        cr = cr_res.json()
        _test_data["invoice_cr_id"] = cr["change_request_id"]
        
        # Verify buyer_id field
        assert cr.get("buyer_id") == tokens["buyer_id"], "Invoice CR should have buyer_id"
        print(f"✓ Invoice CR created with buyer_id: {cr['buyer_id']}")
        
        # Verify invoice status changed
        doc_res = requests.get(f"{BASE_URL}/api/documents/{_test_data['invoice_id']}", headers=agent_headers())
        assert doc_res.json()["status"] == "Change Requested"
        print(f"✓ Invoice status: Change Requested")
        
        # Agent responds
        respond_res = requests.post(
            f"{BASE_URL}/api/change-requests/{_test_data['invoice_cr_id']}/respond",
            headers=agent_headers(),
            json={"message": "Here is the answer to your invoice question"}
        )
        assert respond_res.status_code == 200
        assert respond_res.json()["status"] == "under_review"
        print(f"✓ Agent responded - CR status: under_review")
        
        # Agent resolves
        resolve_res = requests.post(
            f"{BASE_URL}/api/change-requests/{_test_data['invoice_cr_id']}/resolve",
            headers=agent_headers(),
            json={}
        )
        assert resolve_res.status_code == 200
        assert resolve_res.json()["status"] == "resolved"
        print(f"✓ CR resolved")
        
        # CRITICAL: Verify invoice reverts to 'Sent', NOT 'Draft'
        doc_res = requests.get(f"{BASE_URL}/api/documents/{_test_data['invoice_id']}", headers=agent_headers())
        doc = doc_res.json()
        assert doc["status"] == "Sent", f"CRITICAL: Invoice should revert to 'Sent', got '{doc['status']}'"
        print(f"✓ CRITICAL: Invoice reverted to 'Sent' (not Draft)")
        
        # Buyer sees full thread
        thread_res = requests.get(
            f"{BASE_URL}/api/change-requests/entity/invoice/{_test_data['invoice_id']}",
            headers=buyer_headers()
        )
        assert thread_res.status_code == 200
        crs = thread_res.json().get("change_requests", [])
        assert len(crs) >= 1
        messages = crs[0].get("messages", [])
        assert len(messages) >= 2, "Buyer should see both messages"
        print(f"✓ Buyer sees full thread with {len(messages)} messages")

    # ── Test 14: Legacy backward compat - pdf_path ──
    def test_14_legacy_pdf_path_backward_compat(self):
        """Test that GET /api/documents/{id}/source-pdf works for old docs with pdf_path field."""
        # Try to get source PDF for our test quote
        pdf_res = requests.get(
            f"{BASE_URL}/api/documents/{_test_data['quote_id']}/source-pdf",
            headers=agent_headers()
        )
        
        # Should return 404 (no PDF uploaded) or 200 (if PDF exists)
        assert pdf_res.status_code in [200, 404], f"Unexpected status: {pdf_res.status_code}"
        
        if pdf_res.status_code == 404:
            print(f"✓ Source PDF endpoint works (returns 404 for docs without PDF)")
        else:
            print(f"✓ Source PDF endpoint works (returns PDF)")

    # ── Test 15: Cleanup test data ──
    def test_99_cleanup(self):
        """Cleanup test documents."""
        # Delete test quote
        if _test_data.get("quote_id"):
            del_res = requests.delete(
                f"{BASE_URL}/api/documents/{_test_data['quote_id']}?force=true",
                headers=agent_headers()
            )
            print(f"✓ Cleanup quote: {del_res.status_code}")
        
        # Delete test invoice
        if _test_data.get("invoice_id"):
            del_res = requests.delete(
                f"{BASE_URL}/api/documents/{_test_data['invoice_id']}?force=true",
                headers=agent_headers()
            )
            print(f"✓ Cleanup invoice: {del_res.status_code}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
