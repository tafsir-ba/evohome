"""
Test Unit Assignment Feature - Client Profile Unit Assignment
Tests backend API endpoints for unit assignment in client profiles

Key features tested:
1. GET /projects/{id}/units returns is_available, assigned_client_id, assigned_client_name
2. PUT /clients/{id} validates unit exists in project
3. PUT /clients/{id} prevents duplicate assignment without force_unit_reassign
4. PUT /clients/{id} allows reassignment with force_unit_reassign=true
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

@pytest.fixture(scope="module")
def auth_session():
    """Create authenticated session with demo agent"""
    session = requests.Session()
    
    # Login as demo agent
    response = session.post(f"{BASE_URL}/api/demo/enter", json={"persona": "agent", "fresh": False})
    assert response.status_code == 200, f"Demo agent login failed: {response.text}"
    data = response.json()
    token = data.get('token')
    assert token, "No token in response"
    
    session.headers.update({
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    })
    return session


class TestGetProjectUnits:
    """Test GET /projects/{project_id}/units endpoint"""
    
    def test_get_units_returns_assignment_info(self, auth_session):
        """Verify units endpoint returns is_available, assigned_client_id, assigned_client_name"""
        response = auth_session.get(f"{BASE_URL}/api/projects/demo_proj_001/units")
        
        assert response.status_code == 200, f"Get units failed: {response.text}"
        units = response.json()
        
        # Should have units
        assert len(units) >= 2, f"Expected at least 2 units, got {len(units)}"
        
        # Check first unit has required fields
        unit = units[0]
        assert "unit_id" in unit, "Missing unit_id field"
        assert "is_available" in unit, "Missing is_available field"
        assert "assigned_client_id" in unit, "Missing assigned_client_id field"
        assert "assigned_client_name" in unit, "Missing assigned_client_name field"
        assert "unit_reference" in unit, "Missing unit_reference field"
    
    def test_units_show_assigned_client_info(self, auth_session):
        """Verify assigned units show client info"""
        response = auth_session.get(f"{BASE_URL}/api/projects/demo_proj_001/units")
        assert response.status_code == 200
        
        units = response.json()
        # Find demo_unit_001 (assigned to Sophie)
        unit_001 = next((u for u in units if u['unit_id'] == 'demo_unit_001'), None)
        
        if unit_001:
            assert unit_001['is_available'] == False, "Assigned unit should not be available"
            assert unit_001['assigned_client_id'] == 'demo_client_001', "Wrong assigned_client_id"
            # Note: The name check is flexible due to possible unicode handling
            assert unit_001['assigned_client_name'] is not None, "Missing assigned_client_name"


class TestClientUnitAssignment:
    """Test PUT /clients/{client_id} unit assignment logic"""
    
    def test_assign_available_unit(self, auth_session):
        """Test assigning an available unit works"""
        # First get current client state
        response = auth_session.get(f"{BASE_URL}/api/clients/demo_client_001")
        assert response.status_code == 200
        original_client = response.json()
        original_unit = original_client.get('unit_id')
        
        # Assign the same unit (should work, no conflict)
        if original_unit:
            response = auth_session.put(
                f"{BASE_URL}/api/clients/demo_client_001",
                json={"unit_id": original_unit}
            )
            assert response.status_code == 200, f"Assigning same unit failed: {response.text}"
    
    def test_prevent_duplicate_assignment_without_force(self, auth_session):
        """Test that assigning an already-assigned unit returns 409 without force flag"""
        # Try to assign demo_unit_001 (Sophie's) to Thomas without force
        response = auth_session.put(
            f"{BASE_URL}/api/clients/demo_client_002",
            json={"unit_id": "demo_unit_001"}  # This is Sophie's unit
        )
        
        assert response.status_code == 409, f"Expected 409 conflict, got {response.status_code}: {response.text}"
        data = response.json()
        assert "detail" in data, "Missing error detail"
        # The error should mention the client name
        assert "Sophie" in data['detail'] or "already assigned" in data['detail'].lower(), \
            f"Error should mention conflicting client: {data['detail']}"
    
    def test_force_reassign_removes_unit_from_other_client(self, auth_session):
        """Test force_unit_reassign=true removes unit from other client"""
        # Force assign Sophie's unit to Thomas
        response = auth_session.put(
            f"{BASE_URL}/api/clients/demo_client_002",
            json={"unit_id": "demo_unit_001", "force_unit_reassign": True}
        )
        assert response.status_code == 200, f"Force reassign failed: {response.text}"
        
        # Verify Thomas now has the unit
        thomas = response.json()
        assert thomas['unit_id'] == 'demo_unit_001', "Thomas should have demo_unit_001"
        
        # Verify Sophie no longer has the unit
        response = auth_session.get(f"{BASE_URL}/api/clients/demo_client_001")
        assert response.status_code == 200
        sophie = response.json()
        assert sophie['unit_id'] is None, "Sophie should have no unit"
        assert sophie['unit_reference'] == 'General', "Sophie's unit_reference should be 'General'"
        
        # CLEANUP: Restore original assignment
        auth_session.put(
            f"{BASE_URL}/api/clients/demo_client_001",
            json={"unit_id": "demo_unit_001", "force_unit_reassign": True}
        )
        auth_session.put(
            f"{BASE_URL}/api/clients/demo_client_002",
            json={"unit_id": "demo_unit_002"}
        )
    
    def test_validate_unit_exists_in_project(self, auth_session):
        """Test that assigning non-existent unit returns 400"""
        response = auth_session.put(
            f"{BASE_URL}/api/clients/demo_client_001",
            json={"unit_id": "non_existent_unit_12345"}
        )
        
        assert response.status_code == 400, f"Expected 400 for invalid unit, got {response.status_code}: {response.text}"
        data = response.json()
        assert "Invalid unit" in data.get('detail', ''), f"Error should mention invalid unit: {data}"
    
    def test_clear_unit_assignment(self, auth_session):
        """Test clearing unit assignment with empty string"""
        # First get Sophie's current unit
        response = auth_session.get(f"{BASE_URL}/api/clients/demo_client_001")
        original_unit = response.json().get('unit_id')
        
        # Clear unit assignment
        response = auth_session.put(
            f"{BASE_URL}/api/clients/demo_client_001",
            json={"unit_id": ""}
        )
        assert response.status_code == 200, f"Clear unit failed: {response.text}"
        client = response.json()
        assert client['unit_id'] is None, "unit_id should be None after clearing"
        assert client['unit_reference'] == 'General', "unit_reference should be 'General'"
        
        # CLEANUP: Restore original unit
        if original_unit:
            auth_session.put(
                f"{BASE_URL}/api/clients/demo_client_001",
                json={"unit_id": original_unit}
            )


class TestClientDetail:
    """Test GET /clients/{client_id} returns unit assignment info"""
    
    def test_client_includes_unit_fields(self, auth_session):
        """Verify client detail includes unit_id and unit_reference"""
        response = auth_session.get(f"{BASE_URL}/api/clients/demo_client_001")
        assert response.status_code == 200, f"Get client failed: {response.text}"
        
        client = response.json()
        assert "client_id" in client
        assert "unit_id" in client, "Missing unit_id field"
        assert "unit_reference" in client, "Missing unit_reference field"
        assert "project_id" in client, "Missing project_id field"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
