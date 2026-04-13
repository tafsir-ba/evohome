"""
Test Suite for Amount Parsing Bug Fix
Tests the fix for comma separator handling in amount parsing.
Bug: 'CHF 10,000' was being parsed as 10.00 instead of 10000.0
Fix: Updated regex patterns to correctly distinguish thousands separators from decimal separators
"""

import pytest
import requests
import os

# Base URL from environment - must include /api prefix for proper routing
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAmountParsing:
    """Tests for amount extraction from command text"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: Login as demo agent and get session"""
        self.session = requests.Session()
        # Login as demo agent
        login_res = self.session.post(f"{BASE_URL}/api/demo/enter", json={"persona": "agent", "fresh": False})
        assert login_res.status_code == 200, f"Failed to login: {login_res.text}"
        self.user_data = login_res.json()
        print(f"Logged in as: {self.user_data.get('name')}")
        yield
        # Cleanup if needed
    
    def test_thousands_separator_comma(self):
        """Test: 'CHF 10,000' should extract 10000.0 (comma as thousands separator)"""
        response = self.session.post(
            f"{BASE_URL}/api/command/interpret",
            data={
                "command": "create invoice CHF 10,000",
                "context": '{"project_id":"test","client_id":"test"}'
            }
        )
        assert response.status_code == 200, f"API failed: {response.text}"
        
        data = response.json()
        assert data["intent"] == "create_invoice", f"Wrong intent: {data['intent']}"
        
        # Find amount field
        amount_field = next((f for f in data["fields"] if f["name"] == "amount"), None)
        assert amount_field is not None, "Amount field not extracted"
        assert amount_field["value"] == 10000, f"Amount incorrectly parsed as {amount_field['value']}, expected 10000"
        print(f"PASS: 'CHF 10,000' correctly parsed as {amount_field['value']}")
    
    def test_multiple_thousands_separators(self):
        """Test: 'CHF 1,000,000' should extract 1000000.0 (multiple comma separators)"""
        response = self.session.post(
            f"{BASE_URL}/api/command/interpret",
            data={
                "command": "create invoice CHF 1,000,000",
                "context": '{"project_id":"test","client_id":"test"}'
            }
        )
        assert response.status_code == 200, f"API failed: {response.text}"
        
        data = response.json()
        amount_field = next((f for f in data["fields"] if f["name"] == "amount"), None)
        assert amount_field is not None, "Amount field not extracted"
        assert amount_field["value"] == 1000000, f"Amount incorrectly parsed as {amount_field['value']}, expected 1000000"
        print(f"PASS: 'CHF 1,000,000' correctly parsed as {amount_field['value']}")
    
    def test_thousands_with_decimal(self):
        """Test: 'CHF 25,309.50' should extract 25309.5 (thousands separator + decimal)"""
        response = self.session.post(
            f"{BASE_URL}/api/command/interpret",
            data={
                "command": "create invoice CHF 25,309.50",
                "context": '{"project_id":"test","client_id":"test"}'
            }
        )
        assert response.status_code == 200, f"API failed: {response.text}"
        
        data = response.json()
        amount_field = next((f for f in data["fields"] if f["name"] == "amount"), None)
        assert amount_field is not None, "Amount field not extracted"
        assert amount_field["value"] == 25309.5, f"Amount incorrectly parsed as {amount_field['value']}, expected 25309.5"
        print(f"PASS: 'CHF 25,309.50' correctly parsed as {amount_field['value']}")
    
    def test_european_decimal_comma(self):
        """Test: '10,50 eur' should extract 10.5 (European comma as decimal)"""
        response = self.session.post(
            f"{BASE_URL}/api/command/interpret",
            data={
                "command": "invoice 10,50 eur",
                "context": '{"project_id":"test","client_id":"test"}'
            }
        )
        assert response.status_code == 200, f"API failed: {response.text}"
        
        data = response.json()
        amount_field = next((f for f in data["fields"] if f["name"] == "amount"), None)
        assert amount_field is not None, "Amount field not extracted"
        assert amount_field["value"] == 10.5, f"Amount incorrectly parsed as {amount_field['value']}, expected 10.5"
        print(f"PASS: '10,50 eur' correctly parsed as {amount_field['value']}")
    
    def test_whole_number(self):
        """Test: '100 usd' should extract 100.0 (whole number)"""
        response = self.session.post(
            f"{BASE_URL}/api/command/interpret",
            data={
                "command": "create invoice 100 usd",
                "context": '{"project_id":"test","client_id":"test"}'
            }
        )
        assert response.status_code == 200, f"API failed: {response.text}"
        
        data = response.json()
        amount_field = next((f for f in data["fields"] if f["name"] == "amount"), None)
        assert amount_field is not None, "Amount field not extracted"
        assert amount_field["value"] == 100, f"Amount incorrectly parsed as {amount_field['value']}, expected 100"
        print(f"PASS: '100 usd' correctly parsed as {amount_field['value']}")
    
    def test_exact_user_scenario(self):
        """Test: 'create invoice for Vanessa CHF 10,000' (exact bug scenario)"""
        response = self.session.post(
            f"{BASE_URL}/api/command/interpret",
            data={
                "command": "create invoice for Vanessa CHF 10,000",
                "context": '{"project_id":"test","client_id":"test"}'
            }
        )
        assert response.status_code == 200, f"API failed: {response.text}"
        
        data = response.json()
        assert data["intent"] == "create_invoice", f"Wrong intent: {data['intent']}"
        
        amount_field = next((f for f in data["fields"] if f["name"] == "amount"), None)
        assert amount_field is not None, "Amount field not extracted"
        
        # This is the critical bug fix test: 10,000 should be 10000, NOT 10.00
        assert amount_field["value"] == 10000, f"BUG NOT FIXED: Amount parsed as {amount_field['value']}, expected 10000 (not 10.00)"
        print(f"PASS: 'create invoice for Vanessa CHF 10,000' correctly parsed as {amount_field['value']}")
    
    def test_swiss_apostrophe_format(self):
        """Test: 'CHF 10'000' should extract 10000.0 (Swiss apostrophe separator)"""
        response = self.session.post(
            f"{BASE_URL}/api/command/interpret",
            data={
                "command": "create invoice CHF 10'000",
                "context": '{"project_id":"test","client_id":"test"}'
            }
        )
        assert response.status_code == 200, f"API failed: {response.text}"
        
        data = response.json()
        amount_field = next((f for f in data["fields"] if f["name"] == "amount"), None)
        assert amount_field is not None, "Amount field not extracted"
        assert amount_field["value"] == 10000, f"Amount incorrectly parsed as {amount_field['value']}, expected 10000"
        print(f"PASS: 'CHF 10'000' correctly parsed as {amount_field['value']}")
    
    def test_standard_decimal(self):
        """Test: 'CHF 10.50' should extract 10.5 (standard decimal)"""
        response = self.session.post(
            f"{BASE_URL}/api/command/interpret",
            data={
                "command": "create invoice CHF 10.50",
                "context": '{"project_id":"test","client_id":"test"}'
            }
        )
        assert response.status_code == 200, f"API failed: {response.text}"
        
        data = response.json()
        amount_field = next((f for f in data["fields"] if f["name"] == "amount"), None)
        assert amount_field is not None, "Amount field not extracted"
        assert amount_field["value"] == 10.5, f"Amount incorrectly parsed as {amount_field['value']}, expected 10.5"
        print(f"PASS: 'CHF 10.50' correctly parsed as {amount_field['value']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
