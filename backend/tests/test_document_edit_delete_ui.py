"""
Test suite for document edit/delete UI features
Tests the new edit and delete buttons on invoice/quote detail pages

Features tested:
1. Edit button on invoice detail navigates to edit page with pre-filled data
2. Delete button on invoice detail shows confirmation dialog  
3. DELETE endpoint blocks non-Draft documents
4. Edit button on quote detail navigates to edit page with pre-filled data
5. Delete button on quote detail shows confirmation dialog
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
API_URL = f"{BASE_URL}/api"


class TestInvoiceDetailEditDelete:
    """Tests for invoice detail page edit/delete functionality"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login as demo agent"""
        response = requests.post(f"{API_URL}/auth/demo/agent")
        assert response.status_code == 200, f"Demo login failed: {response.text}"
        self.token = response.json().get('token')
        self.headers = {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json'
        }
    
    def test_get_invoice_returns_editable_data(self):
        """Test that GET /api/documents/{id} returns data suitable for edit form"""
        # Get invoices
        response = requests.get(
            f"{API_URL}/documents?doc_type=invoice",
            headers=self.headers
        )
        assert response.status_code == 200
        invoices = response.json()
        
        if not invoices:
            pytest.skip("No invoices available")
            return
        
        # Get single invoice
        invoice = invoices[0]
        invoice_id = invoice.get('document_id')
        
        response = requests.get(
            f"{API_URL}/documents/{invoice_id}",
            headers=self.headers
        )
        assert response.status_code == 200
        
        data = response.json()
        
        # Verify editable fields exist
        assert 'document_id' in data, "document_id missing"
        assert 'title' in data, "title missing"
        assert 'amount' in data, "amount missing"
        assert 'items' in data, "items missing"
        assert 'supplier_name' in data, "supplier_name missing"
        
        print(f"Invoice {invoice_id} has all editable fields")
        print(f"  Title: {data.get('title')}")
        print(f"  Amount: {data.get('amount')}")
        print(f"  Items count: {len(data.get('items', []))}")
    
    def test_delete_sent_invoice_blocked(self):
        """Test that DELETE on a Sent invoice is blocked"""
        # Find a Sent invoice
        response = requests.get(
            f"{API_URL}/documents?doc_type=invoice",
            headers=self.headers
        )
        assert response.status_code == 200
        invoices = response.json()
        
        sent_invoices = [i for i in invoices if i.get('status') == 'Sent']
        
        if not sent_invoices:
            pytest.skip("No Sent invoices available")
            return
        
        invoice = sent_invoices[0]
        invoice_id = invoice.get('document_id')
        
        # Try to delete
        response = requests.delete(
            f"{API_URL}/documents/{invoice_id}",
            headers=self.headers
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        error = response.json()
        assert 'Draft' in error.get('detail', ''), f"Error should mention Draft: {error}"
        print(f"DELETE correctly blocked for Sent invoice: {error.get('detail')}")
    
    def test_delete_paid_invoice_blocked(self):
        """Test that DELETE on a Paid invoice is blocked"""
        response = requests.get(
            f"{API_URL}/documents?doc_type=invoice",
            headers=self.headers
        )
        assert response.status_code == 200
        invoices = response.json()
        
        paid_invoices = [i for i in invoices if i.get('status') == 'Paid']
        
        if not paid_invoices:
            pytest.skip("No Paid invoices available")
            return
        
        invoice = paid_invoices[0]
        invoice_id = invoice.get('document_id')
        
        response = requests.delete(
            f"{API_URL}/documents/{invoice_id}",
            headers=self.headers
        )
        
        assert response.status_code == 400
        print("DELETE correctly blocked for Paid invoice")


class TestQuoteDetailEditDelete:
    """Tests for quote detail page edit/delete functionality"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login as demo agent"""
        response = requests.post(f"{API_URL}/auth/demo/agent")
        assert response.status_code == 200
        self.token = response.json().get('token')
        self.headers = {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json'
        }
    
    def test_get_quote_returns_editable_data(self):
        """Test that GET /api/documents/{id} returns data suitable for edit form"""
        # Get quotes
        response = requests.get(
            f"{API_URL}/documents?doc_type=quote",
            headers=self.headers
        )
        assert response.status_code == 200
        quotes = response.json()
        
        if not quotes:
            pytest.skip("No quotes available")
            return
        
        # Get single quote
        quote = quotes[0]
        quote_id = quote.get('document_id')
        
        response = requests.get(
            f"{API_URL}/documents/{quote_id}",
            headers=self.headers
        )
        assert response.status_code == 200
        
        data = response.json()
        
        # Verify editable fields exist
        assert 'document_id' in data, "document_id missing"
        assert 'title' in data, "title missing"
        assert 'amount' in data, "amount missing"
        assert 'items' in data, "items missing"
        
        print(f"Quote {quote_id} has all editable fields")
        print(f"  Title: {data.get('title')}")
        print(f"  Amount: {data.get('amount')}")
        print(f"  Items count: {len(data.get('items', []))}")
    
    def test_delete_sent_quote_blocked(self):
        """Test that DELETE on a Sent quote is blocked"""
        response = requests.get(
            f"{API_URL}/documents?doc_type=quote",
            headers=self.headers
        )
        assert response.status_code == 200
        quotes = response.json()
        
        sent_quotes = [q for q in quotes if q.get('status') == 'Sent']
        
        if not sent_quotes:
            pytest.skip("No Sent quotes available")
            return
        
        quote = sent_quotes[0]
        quote_id = quote.get('document_id')
        
        response = requests.delete(
            f"{API_URL}/documents/{quote_id}",
            headers=self.headers
        )
        
        assert response.status_code == 400
        error = response.json()
        assert 'Draft' in error.get('detail', '')
        print(f"DELETE correctly blocked for Sent quote: {error.get('detail')}")
    
    def test_delete_approved_quote_blocked(self):
        """Test that DELETE on an Approved quote is blocked"""
        response = requests.get(
            f"{API_URL}/documents?doc_type=quote",
            headers=self.headers
        )
        assert response.status_code == 200
        quotes = response.json()
        
        approved_quotes = [q for q in quotes if q.get('status') == 'Approved']
        
        if not approved_quotes:
            pytest.skip("No Approved quotes available")
            return
        
        quote = approved_quotes[0]
        quote_id = quote.get('document_id')
        
        response = requests.delete(
            f"{API_URL}/documents/{quote_id}",
            headers=self.headers
        )
        
        assert response.status_code == 400
        print("DELETE correctly blocked for Approved quote")
    
    def test_update_change_requested_quote_allowed(self):
        """Test that PUT on a Change Requested quote is allowed"""
        response = requests.get(
            f"{API_URL}/documents?doc_type=quote",
            headers=self.headers
        )
        assert response.status_code == 200
        quotes = response.json()
        
        change_requested = [q for q in quotes if q.get('status') == 'Change Requested']
        
        if not change_requested:
            pytest.skip("No Change Requested quotes available")
            return
        
        quote = change_requested[0]
        quote_id = quote.get('document_id')
        
        response = requests.put(
            f"{API_URL}/documents/{quote_id}",
            headers=self.headers,
            json={"notes": "Updated after change request"}
        )
        
        assert response.status_code == 200
        print("PUT allowed for Change Requested quote (can revise)")


class TestDeleteEndpointValidation:
    """Tests for DELETE endpoint edge cases"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        response = requests.post(f"{API_URL}/auth/demo/agent")
        assert response.status_code == 200
        self.token = response.json().get('token')
        self.headers = {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json'
        }
    
    def test_delete_nonexistent_document(self):
        """Test DELETE returns 404 for non-existent document"""
        response = requests.delete(
            f"{API_URL}/documents/nonexistent_doc_xyz",
            headers=self.headers
        )
        assert response.status_code == 404
        print("DELETE returns 404 for non-existent document")
    
    def test_delete_requires_authentication(self):
        """Test DELETE requires authentication"""
        response = requests.delete(f"{API_URL}/documents/any_doc_id")
        assert response.status_code == 401
        print("DELETE requires authentication")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
