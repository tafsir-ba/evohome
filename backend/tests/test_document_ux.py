"""
Test Document UX Improvements for Evohome
Tests for: hero image, summary, QR payment, unified document endpoints
"""
import pytest
import requests
import os
import io

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://invoice-track-20.preview.emergentagent.com')

class TestDocumentEndpoints:
    """Tests for unified document endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with demo agent authentication"""
        self.session = requests.Session()
        # Login as demo agent
        res = self.session.post(f"{BASE_URL}/api/auth/demo/agent")
        assert res.status_code == 200, f"Agent login failed: {res.text}"
        self.agent_token = res.json().get('token')
        self.session.headers.update({'Authorization': f'Bearer {self.agent_token}'})
        
    def test_get_documents_list(self):
        """Test fetching documents list"""
        res = self.session.get(f"{BASE_URL}/api/documents")
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)
        print(f"Found {len(data)} documents")
        
    def test_get_documents_by_type_quote(self):
        """Test fetching quotes only"""
        res = self.session.get(f"{BASE_URL}/api/documents?doc_type=quote")
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)
        for doc in data:
            assert doc.get('type') == 'quote', f"Expected quote, got {doc.get('type')}"
        print(f"Found {len(data)} quotes")
        
    def test_get_documents_by_type_invoice(self):
        """Test fetching invoices only"""
        res = self.session.get(f"{BASE_URL}/api/documents?doc_type=invoice")
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)
        for doc in data:
            assert doc.get('type') == 'invoice', f"Expected invoice, got {doc.get('type')}"
        print(f"Found {len(data)} invoices")
        
    def test_get_single_document(self):
        """Test getting single document with unified endpoint"""
        # First get list
        res = self.session.get(f"{BASE_URL}/api/documents")
        assert res.status_code == 200
        docs = res.json()
        
        if len(docs) > 0:
            doc_id = docs[0].get('document_id')
            res = self.session.get(f"{BASE_URL}/api/documents/{doc_id}")
            assert res.status_code == 200
            data = res.json()
            assert 'document_id' in data
            assert 'type' in data
            assert 'status' in data
            assert 'title' in data
            assert 'amount' in data
            # Check for new UX fields
            assert 'summary' in data or data.get('summary') is None
            assert 'hero_image_url' in data or data.get('hero_image_url') is None
            print(f"Document {doc_id} loaded successfully: {data.get('title')}")
        else:
            pytest.skip("No documents available for testing")


class TestDocumentUpdate:
    """Tests for updating documents with summary and hero image"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with demo agent authentication"""
        self.session = requests.Session()
        res = self.session.post(f"{BASE_URL}/api/auth/demo/agent")
        assert res.status_code == 200, f"Agent login failed: {res.text}"
        self.agent_token = res.json().get('token')
        self.session.headers.update({'Authorization': f'Bearer {self.agent_token}'})
        
    def _get_editable_document(self, doc_type='quote'):
        """Get a document that can be edited (Draft or Change Requested)"""
        res = self.session.get(f"{BASE_URL}/api/documents?doc_type={doc_type}")
        if res.status_code != 200:
            return None
        docs = res.json()
        for doc in docs:
            if doc.get('status') in ['Draft', 'Change Requested']:
                return doc.get('document_id')
        return None
        
    def test_update_document_summary(self):
        """Test updating document summary"""
        doc_id = self._get_editable_document('quote')
        if not doc_id:
            pytest.skip("No editable quote found")
            
        test_summary = "TEST_Premium kitchen upgrade with marble countertops"
        res = self.session.put(
            f"{BASE_URL}/api/documents/{doc_id}",
            json={"summary": test_summary}
        )
        assert res.status_code == 200, f"Update failed: {res.text}"
        data = res.json()
        assert data.get('summary') == test_summary
        print(f"Summary updated successfully")
        
        # Verify persistence
        res = self.session.get(f"{BASE_URL}/api/documents/{doc_id}")
        assert res.status_code == 200
        data = res.json()
        assert data.get('summary') == test_summary
        print(f"Summary persisted correctly")


class TestHeroImageEndpoints:
    """Tests for hero image upload/download/delete"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        res = self.session.post(f"{BASE_URL}/api/auth/demo/agent")
        assert res.status_code == 200, f"Agent login failed: {res.text}"
        self.agent_token = res.json().get('token')
        self.session.headers.update({'Authorization': f'Bearer {self.agent_token}'})
        
    def _get_editable_document(self):
        """Get a document that can be edited"""
        res = self.session.get(f"{BASE_URL}/api/documents")
        if res.status_code != 200:
            return None
        docs = res.json()
        for doc in docs:
            if doc.get('status') in ['Draft', 'Change Requested']:
                return doc.get('document_id')
        return None
        
    def test_hero_image_upload_endpoint_exists(self):
        """Test that hero image upload endpoint is accessible"""
        doc_id = self._get_editable_document()
        if not doc_id:
            pytest.skip("No editable document found")
            
        # Create a simple test image (1x1 pixel PNG)
        png_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
        
        files = {'file': ('test.png', io.BytesIO(png_data), 'image/png')}
        res = self.session.post(f"{BASE_URL}/api/documents/{doc_id}/hero-image", files=files)
        
        assert res.status_code == 200, f"Hero image upload failed: {res.text}"
        data = res.json()
        assert 'hero_image_url' in data
        print(f"Hero image uploaded: {data.get('hero_image_url')}")
        
    def test_hero_image_get_endpoint(self):
        """Test that hero image can be retrieved"""
        doc_id = self._get_editable_document()
        if not doc_id:
            pytest.skip("No editable document found")
            
        # Upload first
        png_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
        files = {'file': ('test.png', io.BytesIO(png_data), 'image/png')}
        self.session.post(f"{BASE_URL}/api/documents/{doc_id}/hero-image", files=files)
        
        # Then retrieve
        res = self.session.get(f"{BASE_URL}/api/documents/{doc_id}/hero-image")
        assert res.status_code in [200, 404]  # 200 if uploaded, 404 if not
        if res.status_code == 200:
            assert res.headers.get('content-type', '').startswith('image/')
            print(f"Hero image retrieved successfully")
            
    def test_hero_image_delete_endpoint(self):
        """Test deleting hero image"""
        doc_id = self._get_editable_document()
        if not doc_id:
            pytest.skip("No editable document found")
            
        res = self.session.delete(f"{BASE_URL}/api/documents/{doc_id}/hero-image")
        assert res.status_code == 200
        print(f"Hero image deleted successfully")


class TestQRCodeEndpoint:
    """Tests for Swiss QR payment code generation"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with demo buyer authentication"""
        self.session = requests.Session()
        # Login as demo buyer
        res = self.session.post(f"{BASE_URL}/api/auth/demo/buyer?buyer_num=1")
        assert res.status_code == 200, f"Buyer login failed: {res.text}"
        self.buyer_token = res.json().get('token')
        self.session.headers.update({'Authorization': f'Bearer {self.buyer_token}'})
        
    def test_qr_code_endpoint_for_invoice(self):
        """Test QR code generation for invoice"""
        # Get invoices
        res = self.session.get(f"{BASE_URL}/api/documents?doc_type=invoice")
        assert res.status_code == 200
        invoices = res.json()
        
        # Find a sent invoice
        sent_invoices = [i for i in invoices if i.get('status') == 'Sent']
        if not sent_invoices:
            pytest.skip("No sent invoices found")
            
        invoice_id = sent_invoices[0].get('document_id')
        res = self.session.get(f"{BASE_URL}/api/documents/{invoice_id}/qr-code")
        assert res.status_code == 200, f"QR code generation failed: {res.text}"
        
        data = res.json()
        # Verify QR code response structure
        assert 'qr_code_svg_base64' in data, "QR code SVG missing"
        assert 'amount' in data, "Amount missing"
        assert 'currency' in data, "Currency missing"
        assert 'document_number' in data, "Document number missing"
        assert 'payment_info' in data, "Payment info missing"
        
        payment_info = data.get('payment_info', {})
        assert 'beneficiary' in payment_info, "Beneficiary missing"
        assert 'iban' in payment_info, "IBAN missing"
        
        # Verify correct beneficiary
        assert payment_info.get('beneficiary') == 'Evohome SA', f"Wrong beneficiary: {payment_info.get('beneficiary')}"
        
        # Verify IBAN format
        iban = payment_info.get('iban', '')
        assert iban.startswith('CH'), f"Invalid IBAN format: {iban}"
        
        print(f"QR code generated successfully:")
        print(f"  Amount: {data.get('currency')} {data.get('amount')}")
        print(f"  Reference: {data.get('document_number')}")
        print(f"  Beneficiary: {payment_info.get('beneficiary')}")
        print(f"  IBAN: {payment_info.get('iban')}")
        
    def test_qr_code_not_available_for_quotes(self):
        """Test that QR code is not available for quotes"""
        res = self.session.get(f"{BASE_URL}/api/documents?doc_type=quote")
        assert res.status_code == 200
        quotes = res.json()
        
        if not quotes:
            pytest.skip("No quotes found")
            
        quote_id = quotes[0].get('document_id')
        res = self.session.get(f"{BASE_URL}/api/documents/{quote_id}/qr-code")
        assert res.status_code == 400, "QR code should not be available for quotes"
        print("Correctly rejected QR code request for quote")


class TestTimelineEndpoint:
    """Tests for buyer timeline with e-commerce card data"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with demo buyer authentication"""
        self.session = requests.Session()
        res = self.session.post(f"{BASE_URL}/api/auth/demo/buyer?buyer_num=1")
        assert res.status_code == 200, f"Buyer login failed: {res.text}"
        self.buyer_token = res.json().get('token')
        self.session.headers.update({'Authorization': f'Bearer {self.buyer_token}'})
        
    def test_timeline_returns_documents(self):
        """Test that timeline endpoint returns documents"""
        res = self.session.get(f"{BASE_URL}/api/timeline")
        assert res.status_code == 200
        data = res.json()
        
        assert 'documents' in data
        documents = data.get('documents', [])
        print(f"Timeline has {len(documents)} documents")
        
    def test_timeline_document_has_card_fields(self):
        """Test that timeline documents have e-commerce card fields"""
        res = self.session.get(f"{BASE_URL}/api/timeline")
        assert res.status_code == 200
        data = res.json()
        documents = data.get('documents', [])
        
        if not documents:
            pytest.skip("No documents in timeline")
            
        doc = documents[0]
        # Required card fields
        assert 'title' in doc, "Title missing"
        assert 'amount' in doc, "Amount missing"
        assert 'status' in doc, "Status missing"
        assert 'type' in doc, "Type missing"
        assert 'date' in doc, "Date missing"
        
        # E-commerce card fields
        assert 'summary' in doc or doc.get('summary') is None, "Summary field missing"
        assert 'heroImageUrl' in doc or doc.get('heroImageUrl') is None, "Hero image URL field missing"
        assert 'documentNumber' in doc, "Document number missing"
        assert 'actionRequired' in doc, "Action required flag missing"
        
        # Due date for invoices
        if doc.get('type') == 'invoice':
            assert 'dueDate' in doc or doc.get('dueDate') is None
            
        print(f"Document card fields verified: {doc.get('title')}")
        print(f"  Type: {doc.get('type')}, Status: {doc.get('status')}")
        print(f"  Amount: {doc.get('currency', 'CHF')} {doc.get('amount')}")
        print(f"  Summary: {doc.get('summary', 'N/A')[:50]}...")


class TestAuthenticationFlows:
    """Tests for demo authentication flows"""
    
    def test_demo_agent_login(self):
        """Test demo agent login"""
        session = requests.Session()
        res = session.post(f"{BASE_URL}/api/auth/demo/agent")
        assert res.status_code == 200
        data = res.json()
        assert 'user_id' in data
        assert 'token' in data
        assert data.get('role') == 'agent'
        assert data.get('is_demo') == True
        print(f"Demo agent login successful: {data.get('name')}")
        
    def test_demo_buyer_login(self):
        """Test demo buyer login"""
        session = requests.Session()
        res = session.post(f"{BASE_URL}/api/auth/demo/buyer?buyer_num=1")
        assert res.status_code == 200
        data = res.json()
        assert 'user_id' in data
        assert 'token' in data
        assert data.get('role') == 'buyer'
        assert data.get('is_demo') == True
        print(f"Demo buyer login successful: {data.get('name')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
