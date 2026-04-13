"""
Test Batch 3E: Regional Settings, Logo Management, Buyer Branding
- Regional settings must be fully functional (language, currency)
- Logo management tied to plan permissions (Pro only)
- Settings persist correctly
- Buyer interface shows agent's branding
- Demo agent has Pro subscription
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

@pytest.fixture(scope="module")
def agent_token():
    """Get demo agent token (Pro plan)"""
    resp = requests.post(f"{BASE_URL}/api/demo/enter", json={"persona": "agent", "fresh": False})
    assert resp.status_code == 200, f"Failed to get agent token: {resp.text}"
    return resp.json()['token']

@pytest.fixture(scope="module")
def buyer_token():
    """Get demo buyer token"""
    resp = requests.post(f"{BASE_URL}/api/demo/enter", json={"persona": "buyer", "buyer_slot": 1, "fresh": False})
    assert resp.status_code == 200, f"Failed to get buyer token: {resp.text}"
    return resp.json()['token']

@pytest.fixture(scope="module")
def free_agent_token():
    """Get or create a free tier agent token"""
    # Try to login first
    login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "free.test.agent@test.com",
        "password": "testpass123"
    })
    if login_resp.status_code == 200:
        return login_resp.json()['token']
    
    # If not exists, register
    register_resp = requests.post(f"{BASE_URL}/api/auth/register", json={
        "email": "free.test.agent@test.com",
        "password": "testpass123",
        "name": "Free Test Agent"
    })
    if register_resp.status_code == 200:
        return register_resp.json()['token']
    pytest.skip("Could not create free agent for testing")


class TestAgentSettings:
    """Test agent settings endpoints"""
    
    def test_get_settings_returns_expected_fields(self, agent_token):
        """GET /api/settings returns language, currency, company_name, company_logo_url"""
        resp = requests.get(f"{BASE_URL}/api/settings", 
                           headers={"Authorization": f"Bearer {agent_token}"})
        assert resp.status_code == 200
        data = resp.json()
        
        # Verify expected fields exist
        assert "language" in data, "Settings should include language"
        assert "currency" in data, "Settings should include currency"
        assert "company_name" in data, "Settings should include company_name"
        assert "company_logo_url" in data, "Settings should include company_logo_url"
        
        # Verify valid values
        assert data["language"] in ["en", "de", "fr", "it"], f"Language {data['language']} not valid"
        assert data["currency"] in ["CHF", "EUR", "USD"], f"Currency {data['currency']} not valid"
    
    def test_update_language_setting(self, agent_token):
        """PUT /api/settings updates language, persists after refresh"""
        # First get current setting
        get_resp = requests.get(f"{BASE_URL}/api/settings",
                               headers={"Authorization": f"Bearer {agent_token}"})
        original_language = get_resp.json().get("language", "en")
        
        # Change to different language
        new_language = "fr" if original_language != "fr" else "de"
        
        update_resp = requests.put(f"{BASE_URL}/api/settings",
                                   headers={"Authorization": f"Bearer {agent_token}",
                                           "Content-Type": "application/json"},
                                   json={"language": new_language})
        assert update_resp.status_code == 200
        
        # Verify persistence
        verify_resp = requests.get(f"{BASE_URL}/api/settings",
                                   headers={"Authorization": f"Bearer {agent_token}"})
        assert verify_resp.status_code == 200
        assert verify_resp.json()["language"] == new_language
        
        # Restore original
        requests.put(f"{BASE_URL}/api/settings",
                    headers={"Authorization": f"Bearer {agent_token}",
                            "Content-Type": "application/json"},
                    json={"language": original_language})
    
    def test_update_currency_setting(self, agent_token):
        """PUT /api/settings updates currency, persists after refresh"""
        # First get current setting
        get_resp = requests.get(f"{BASE_URL}/api/settings",
                               headers={"Authorization": f"Bearer {agent_token}"})
        original_currency = get_resp.json().get("currency", "CHF")
        
        # Change to different currency
        new_currency = "EUR" if original_currency != "EUR" else "USD"
        
        update_resp = requests.put(f"{BASE_URL}/api/settings",
                                   headers={"Authorization": f"Bearer {agent_token}",
                                           "Content-Type": "application/json"},
                                   json={"currency": new_currency})
        assert update_resp.status_code == 200
        
        # Verify persistence
        verify_resp = requests.get(f"{BASE_URL}/api/settings",
                                   headers={"Authorization": f"Bearer {agent_token}"})
        assert verify_resp.status_code == 200
        assert verify_resp.json()["currency"] == new_currency
        
        # Restore original
        requests.put(f"{BASE_URL}/api/settings",
                    headers={"Authorization": f"Bearer {agent_token}",
                            "Content-Type": "application/json"},
                    json={"currency": original_currency})
    
    def test_invalid_language_rejected(self, agent_token):
        """PUT /api/settings rejects invalid language with 400"""
        resp = requests.put(f"{BASE_URL}/api/settings",
                           headers={"Authorization": f"Bearer {agent_token}",
                                   "Content-Type": "application/json"},
                           json={"language": "invalid_lang"})
        assert resp.status_code == 400
    
    def test_invalid_currency_rejected(self, agent_token):
        """PUT /api/settings rejects invalid currency with 400"""
        resp = requests.put(f"{BASE_URL}/api/settings",
                           headers={"Authorization": f"Bearer {agent_token}",
                                   "Content-Type": "application/json"},
                           json={"currency": "INVALID"})
        assert resp.status_code == 400


class TestBuyerBranding:
    """Test buyer view of agent branding"""
    
    def test_get_branding_returns_agent_info(self, buyer_token):
        """GET /api/branding returns agent's branding info for buyer"""
        resp = requests.get(f"{BASE_URL}/api/branding",
                           headers={"Authorization": f"Bearer {buyer_token}"})
        assert resp.status_code == 200
        data = resp.json()
        
        # Verify branding fields
        assert "company_name" in data, "Branding should include company_name"
        assert "company_logo_url" in data, "Branding should include company_logo_url"
        assert "language" in data, "Branding should include language"
        assert "currency" in data, "Branding should include currency"
    
    def test_branding_reflects_agent_settings(self, agent_token, buyer_token):
        """Buyer's branding endpoint reflects agent's current settings"""
        # Get agent's settings
        agent_settings = requests.get(f"{BASE_URL}/api/settings",
                                      headers={"Authorization": f"Bearer {agent_token}"}).json()
        
        # Get buyer's branding view
        buyer_branding = requests.get(f"{BASE_URL}/api/branding",
                                     headers={"Authorization": f"Bearer {buyer_token}"}).json()
        
        # They should match
        assert buyer_branding["company_name"] == agent_settings["company_name"]
        assert buyer_branding["language"] == agent_settings["language"]
        assert buyer_branding["currency"] == agent_settings["currency"]


class TestLogoManagement:
    """Test logo upload permissions based on plan"""
    
    def test_logo_upload_works_for_pro_agent(self, agent_token):
        """POST /api/settings/logo works for Pro agents (200)"""
        # Create a minimal valid PNG (1x1 pixel)
        import base64
        png_data = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")
        
        # First backup current logo if any
        current = requests.get(f"{BASE_URL}/api/settings",
                              headers={"Authorization": f"Bearer {agent_token}"}).json()
        had_logo = current.get("company_logo_url") is not None
        
        # Upload new logo
        files = {"file": ("test.png", png_data, "image/png")}
        resp = requests.post(f"{BASE_URL}/api/settings/logo",
                            headers={"Authorization": f"Bearer {agent_token}"},
                            files=files)
        assert resp.status_code == 200, f"Pro agent should be able to upload logo: {resp.text}"
        data = resp.json()
        assert "logo_url" in data
        
        # Verify it's reflected in settings
        settings = requests.get(f"{BASE_URL}/api/settings",
                               headers={"Authorization": f"Bearer {agent_token}"}).json()
        assert settings["company_logo_url"] is not None
    
    def test_logo_upload_returns_403_for_free_agent(self, free_agent_token):
        """POST /api/settings/logo returns 403 for Free/Starter agents"""
        import base64
        png_data = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")
        
        files = {"file": ("test.png", png_data, "image/png")}
        resp = requests.post(f"{BASE_URL}/api/settings/logo",
                            headers={"Authorization": f"Bearer {free_agent_token}"},
                            files=files)
        assert resp.status_code == 403, f"Free agent should get 403 for logo upload, got {resp.status_code}"
        assert "Pro" in resp.json().get("detail", "")


class TestDemoAgentPlan:
    """Test demo agent has Pro subscription"""
    
    def test_demo_agent_has_pro_plan(self, agent_token):
        """Demo agent has Pro subscription (plan_id: 'pro')"""
        resp = requests.get(f"{BASE_URL}/api/billing/status",
                           headers={"Authorization": f"Bearer {agent_token}"})
        assert resp.status_code == 200
        data = resp.json()
        
        assert data["plan_id"] == "pro", f"Demo agent should have Pro plan, got {data['plan_id']}"
        assert data["plan_name"] == "Pro"
        assert data["property_limit"] == 50, "Pro plan should have 50 property limit"
    
    def test_demo_agent_can_upload_logo(self, agent_token):
        """Demo agent with Pro plan can upload logo"""
        # First check plan
        billing = requests.get(f"{BASE_URL}/api/billing/status",
                              headers={"Authorization": f"Bearer {agent_token}"}).json()
        assert billing["plan_id"] in ["pro", "enterprise"], "Must have Pro+ plan"
        
        # Then verify logo upload works
        import base64
        png_data = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")
        
        files = {"file": ("test.png", png_data, "image/png")}
        resp = requests.post(f"{BASE_URL}/api/settings/logo",
                            headers={"Authorization": f"Bearer {agent_token}"},
                            files=files)
        assert resp.status_code == 200, f"Pro agent logo upload failed: {resp.text}"


class TestSettingsPersistence:
    """Test that settings properly persist"""
    
    def test_multiple_settings_update_and_persist(self, agent_token):
        """Update multiple settings at once and verify persistence"""
        # Get original settings
        original = requests.get(f"{BASE_URL}/api/settings",
                               headers={"Authorization": f"Bearer {agent_token}"}).json()
        
        # Update language and currency together
        test_lang = "it" if original.get("language") != "it" else "de"
        test_curr = "USD" if original.get("currency") != "USD" else "EUR"
        
        update_resp = requests.put(f"{BASE_URL}/api/settings",
                                   headers={"Authorization": f"Bearer {agent_token}",
                                           "Content-Type": "application/json"},
                                   json={"language": test_lang, "currency": test_curr})
        assert update_resp.status_code == 200
        
        # Verify both persisted
        verify = requests.get(f"{BASE_URL}/api/settings",
                             headers={"Authorization": f"Bearer {agent_token}"}).json()
        assert verify["language"] == test_lang
        assert verify["currency"] == test_curr
        
        # Restore original
        requests.put(f"{BASE_URL}/api/settings",
                    headers={"Authorization": f"Bearer {agent_token}",
                            "Content-Type": "application/json"},
                    json={"language": original.get("language", "en"), 
                          "currency": original.get("currency", "CHF")})
