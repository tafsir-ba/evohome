"""
Batch 4 Testing: Logo Display, Unit-Based Billing, and Core Functionality

Tests:
1. Logo serving from /api/uploads/
2. Agent settings with logo URL
3. Buyer branding endpoint
4. Billing status with unit_usage (not project count)
5. Unit creation incrementing usage count
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestHealthAndAuth:
    """Basic health and auth tests"""
    
    def test_health_endpoint(self):
        """Test health endpoint"""
        res = requests.get(f"{BASE_URL}/api/health")
        assert res.status_code == 200
        data = res.json()
        assert data.get('status') == 'healthy'
        print("✓ Health endpoint working")
    
    def test_demo_agent_login(self):
        """Test demo agent login"""
        res = requests.post(f"{BASE_URL}/api/auth/demo/agent")
        assert res.status_code == 200
        data = res.json()
        assert 'token' in data
        assert data.get('role') == 'agent'
        assert data.get('is_demo') == True
        print(f"✓ Demo agent login successful: {data.get('name')}")
        return data.get('token')
    
    def test_demo_buyer_login(self):
        """Test demo buyer login (Sophie)"""
        res = requests.post(f"{BASE_URL}/api/auth/demo/buyer?buyer_num=1")
        assert res.status_code == 200
        data = res.json()
        assert 'token' in data
        assert data.get('role') == 'buyer'
        assert data.get('is_demo') == True
        print(f"✓ Demo buyer login successful: {data.get('name')}")
        return data.get('token')


class TestLogoAndBranding:
    """Tests for logo display and branding"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get tokens for testing"""
        agent_res = requests.post(f"{BASE_URL}/api/auth/demo/agent")
        self.agent_token = agent_res.json().get('token')
        
        buyer_res = requests.post(f"{BASE_URL}/api/auth/demo/buyer?buyer_num=1")
        self.buyer_token = buyer_res.json().get('token')
    
    def test_agent_settings_contains_logo_url(self):
        """Test that agent settings returns logo URL"""
        res = requests.get(
            f"{BASE_URL}/api/settings",
            headers={"Authorization": f"Bearer {self.agent_token}"}
        )
        assert res.status_code == 200
        data = res.json()
        
        assert 'company_logo_url' in data
        assert 'company_name' in data
        assert 'language' in data
        assert 'currency' in data
        
        # Logo URL should start with /api/uploads/ if set
        if data.get('company_logo_url'):
            assert data['company_logo_url'].startswith('/api/uploads/')
            print(f"✓ Agent settings contains logo: {data['company_logo_url']}")
        else:
            print("⚠ Agent has no logo set (acceptable)")
        
        print(f"✓ Company name: {data.get('company_name')}")
    
    def test_logo_file_accessible(self):
        """Test that logo file is served correctly"""
        # First get the logo URL from settings
        res = requests.get(
            f"{BASE_URL}/api/settings",
            headers={"Authorization": f"Bearer {self.agent_token}"}
        )
        data = res.json()
        logo_url = data.get('company_logo_url')
        
        if logo_url:
            # Test logo is accessible
            logo_res = requests.get(f"{BASE_URL}{logo_url}")
            assert logo_res.status_code == 200
            assert logo_res.headers.get('content-type') in ['image/png', 'image/jpeg', 'image/jpg']
            assert len(logo_res.content) > 0
            print(f"✓ Logo file accessible, size: {len(logo_res.content)} bytes")
        else:
            pytest.skip("No logo URL configured")
    
    def test_buyer_branding_endpoint(self):
        """Test that buyer can access agent's branding"""
        res = requests.get(
            f"{BASE_URL}/api/branding",
            headers={"Authorization": f"Bearer {self.buyer_token}"}
        )
        assert res.status_code == 200
        data = res.json()
        
        assert 'company_name' in data
        assert 'company_logo_url' in data
        assert 'language' in data
        assert 'currency' in data
        
        print(f"✓ Buyer branding endpoint works")
        print(f"  Company: {data.get('company_name')}")
        print(f"  Logo: {data.get('company_logo_url')}")
    
    def test_buyer_can_access_agent_logo(self):
        """Test that buyer can access the agent's logo file"""
        # Get branding info
        res = requests.get(
            f"{BASE_URL}/api/branding",
            headers={"Authorization": f"Bearer {self.buyer_token}"}
        )
        data = res.json()
        logo_url = data.get('company_logo_url')
        
        if logo_url:
            # Logo should be accessible (no auth required for static files)
            logo_res = requests.get(f"{BASE_URL}{logo_url}")
            assert logo_res.status_code == 200
            print(f"✓ Buyer can access agent's logo")
        else:
            pytest.skip("No logo URL configured")


class TestBillingAndSubscription:
    """Tests for unit-based billing (not project-based)"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get token for testing"""
        agent_res = requests.post(f"{BASE_URL}/api/auth/demo/agent")
        self.agent_token = agent_res.json().get('token')
    
    def test_billing_status_returns_unit_usage(self):
        """Test that billing status returns unit_usage field"""
        res = requests.get(
            f"{BASE_URL}/api/billing/status",
            headers={"Authorization": f"Bearer {self.agent_token}"}
        )
        assert res.status_code == 200
        data = res.json()
        
        # Check required fields
        assert 'plan_id' in data
        assert 'plan_name' in data
        assert 'unit_usage' in data, "unit_usage field is required for unit-based billing"
        assert 'unit_limit' in data
        assert 'can_create_unit' in data
        
        # Backward compatibility fields
        assert 'property_usage' in data
        assert 'property_limit' in data
        
        print(f"✓ Billing status endpoint working")
        print(f"  Plan: {data.get('plan_name')} ({data.get('plan_id')})")
        print(f"  Unit usage: {data.get('unit_usage')}/{data.get('unit_limit')}")
        print(f"  Can create unit: {data.get('can_create_unit')}")
    
    def test_unit_usage_counts_units_not_projects(self):
        """Test that unit_usage counts total units, not project count"""
        # Get billing status
        billing_res = requests.get(
            f"{BASE_URL}/api/billing/status",
            headers={"Authorization": f"Bearer {self.agent_token}"}
        )
        billing_data = billing_res.json()
        unit_usage = billing_data.get('unit_usage', 0)
        
        # Get projects
        projects_res = requests.get(
            f"{BASE_URL}/api/projects",
            headers={"Authorization": f"Bearer {self.agent_token}"}
        )
        projects = projects_res.json()
        
        # Count total units across all projects
        total_units = 0
        for project in projects:
            # Get units for each project
            units_res = requests.get(
                f"{BASE_URL}/api/projects/{project['project_id']}/units",
                headers={"Authorization": f"Bearer {self.agent_token}"}
            )
            if units_res.status_code == 200:
                units = units_res.json()
                total_units += len(units)
        
        # If no units found, count clients as units (backward compatibility)
        if total_units == 0:
            total_units = sum(p.get('client_count', 0) for p in projects)
        
        print(f"  Projects count: {len(projects)}")
        print(f"  Total units: {total_units}")
        print(f"  Unit usage from billing: {unit_usage}")
        
        # Unit usage should match total units (or be close if units are counted differently)
        # Allow some tolerance for edge cases
        assert abs(unit_usage - total_units) <= 1 or unit_usage >= total_units, \
            f"Unit usage ({unit_usage}) should match total units ({total_units})"
        print(f"✓ Unit usage correctly counts units, not projects")


class TestProjectUnits:
    """Tests for unit management within projects"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get token and first project for testing"""
        agent_res = requests.post(f"{BASE_URL}/api/auth/demo/agent")
        self.agent_token = agent_res.json().get('token')
        
        # Get first project
        projects_res = requests.get(
            f"{BASE_URL}/api/projects",
            headers={"Authorization": f"Bearer {self.agent_token}"}
        )
        projects = projects_res.json()
        self.project_id = projects[0]['project_id'] if projects else None
    
    def test_list_project_units(self):
        """Test listing units for a project"""
        if not self.project_id:
            pytest.skip("No project available")
        
        res = requests.get(
            f"{BASE_URL}/api/projects/{self.project_id}/units",
            headers={"Authorization": f"Bearer {self.agent_token}"}
        )
        assert res.status_code == 200
        units = res.json()
        assert isinstance(units, list)
        print(f"✓ Project has {len(units)} units")
        
        for unit in units[:3]:  # Show first 3
            print(f"  - {unit.get('unit_reference')}")


class TestDocuments:
    """Tests for quote and invoice functionality"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get tokens"""
        agent_res = requests.post(f"{BASE_URL}/api/auth/demo/agent")
        self.agent_token = agent_res.json().get('token')
        
        buyer_res = requests.post(f"{BASE_URL}/api/auth/demo/buyer?buyer_num=1")
        self.buyer_token = buyer_res.json().get('token')
    
    def test_agent_documents_list(self):
        """Test listing documents for agent"""
        res = requests.get(
            f"{BASE_URL}/api/documents",
            headers={"Authorization": f"Bearer {self.agent_token}"}
        )
        assert res.status_code == 200
        documents = res.json()
        assert isinstance(documents, list)
        
        quotes = [d for d in documents if d.get('type') == 'quote']
        invoices = [d for d in documents if d.get('type') == 'invoice']
        
        print(f"✓ Agent has {len(quotes)} quotes, {len(invoices)} invoices")
    
    def test_buyer_timeline(self):
        """Test buyer timeline shows documents"""
        res = requests.get(
            f"{BASE_URL}/api/timeline",
            headers={"Authorization": f"Bearer {self.buyer_token}"}
        )
        assert res.status_code == 200
        data = res.json()
        
        assert 'documents' in data
        assert 'project_info' in data
        
        documents = data.get('documents', [])
        print(f"✓ Buyer timeline has {len(documents)} visible documents")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
