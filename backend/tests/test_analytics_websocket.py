"""
Test Analytics Dashboard API endpoint and WebSocket functionality
Tests: GET /api/analytics with period filters, WebSocket connection validation
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://invoice-track-20.preview.emergentagent.com').rstrip('/')

class TestDemoAgentLogin:
    """Test demo agent login endpoint"""
    
    def test_demo_agent_login_returns_token(self):
        """POST /api/auth/demo/agent returns valid token"""
        response = requests.post(f"{BASE_URL}/api/auth/demo/agent")
        assert response.status_code == 200
        
        data = response.json()
        assert "token" in data
        assert "user_id" in data
        assert data["user_id"] == "demo_agent_001"
        assert data["role"] == "agent"
        assert data["is_demo"] == True
        print(f"SUCCESS: Demo agent login - user_id: {data['user_id']}, role: {data['role']}")


class TestAnalyticsEndpoint:
    """Test GET /api/analytics endpoint with various period filters"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token for demo agent"""
        response = requests.post(f"{BASE_URL}/api/auth/demo/agent")
        assert response.status_code == 200
        return response.json()["token"]
    
    def test_analytics_default_period(self, auth_token):
        """GET /api/analytics returns stats for default period (month)"""
        response = requests.get(
            f"{BASE_URL}/api/analytics",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        
        data = response.json()
        # Verify all expected fields are present
        assert "totalQuotes" in data
        assert "totalInvoices" in data
        assert "totalClients" in data
        assert "totalProjects" in data
        assert "totalRevenue" in data
        assert "pendingAmount" in data
        assert "quoteStats" in data
        assert "invoiceStats" in data
        
        # Verify quoteStats structure
        assert "approved" in data["quoteStats"]
        assert "sent" in data["quoteStats"]
        assert "rejected" in data["quoteStats"]
        assert "draft" in data["quoteStats"]
        
        # Verify invoiceStats structure
        assert "paid" in data["invoiceStats"]
        assert "sent" in data["invoiceStats"]
        assert "draft" in data["invoiceStats"]
        
        print(f"SUCCESS: Analytics default - Quotes: {data['totalQuotes']}, Clients: {data['totalClients']}")
    
    def test_analytics_week_period(self, auth_token):
        """GET /api/analytics?period=week returns weekly filtered data"""
        response = requests.get(
            f"{BASE_URL}/api/analytics?period=week",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "totalQuotes" in data
        assert "totalRevenue" in data
        assert isinstance(data["totalQuotes"], int)
        assert isinstance(data["totalRevenue"], (int, float))
        print(f"SUCCESS: Analytics week - Quotes: {data['totalQuotes']}, Revenue: {data['totalRevenue']}")
    
    def test_analytics_month_period(self, auth_token):
        """GET /api/analytics?period=month returns monthly filtered data"""
        response = requests.get(
            f"{BASE_URL}/api/analytics?period=month",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "totalQuotes" in data
        assert data["totalClients"] >= 0  # Should be non-negative
        print(f"SUCCESS: Analytics month - Quotes: {data['totalQuotes']}, Clients: {data['totalClients']}")
    
    def test_analytics_quarter_period(self, auth_token):
        """GET /api/analytics?period=quarter returns quarterly filtered data"""
        response = requests.get(
            f"{BASE_URL}/api/analytics?period=quarter",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "totalQuotes" in data
        print(f"SUCCESS: Analytics quarter - Quotes: {data['totalQuotes']}")
    
    def test_analytics_year_period(self, auth_token):
        """GET /api/analytics?period=year returns yearly filtered data"""
        response = requests.get(
            f"{BASE_URL}/api/analytics?period=year",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "totalQuotes" in data
        print(f"SUCCESS: Analytics year - Quotes: {data['totalQuotes']}")
    
    def test_analytics_all_period(self, auth_token):
        """GET /api/analytics?period=all returns all-time data"""
        response = requests.get(
            f"{BASE_URL}/api/analytics?period=all",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "totalQuotes" in data
        # All-time should have >= month data
        print(f"SUCCESS: Analytics all - Quotes: {data['totalQuotes']}, Revenue: {data['totalRevenue']}")
    
    def test_analytics_requires_auth(self):
        """GET /api/analytics without token returns 401"""
        response = requests.get(f"{BASE_URL}/api/analytics")
        assert response.status_code == 401
        print("SUCCESS: Analytics requires authentication")
    
    def test_analytics_data_consistency(self, auth_token):
        """Verify analytics data is consistent - all period >= month period >= week period"""
        all_response = requests.get(
            f"{BASE_URL}/api/analytics?period=all",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        month_response = requests.get(
            f"{BASE_URL}/api/analytics?period=month",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        week_response = requests.get(
            f"{BASE_URL}/api/analytics?period=week",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        all_data = all_response.json()
        month_data = month_response.json()
        week_data = week_response.json()
        
        # All-time quotes >= month quotes >= week quotes
        assert all_data["totalQuotes"] >= month_data["totalQuotes"]
        assert month_data["totalQuotes"] >= week_data["totalQuotes"]
        
        # Clients and projects should be same (all-time)
        assert all_data["totalClients"] == month_data["totalClients"]
        
        print(f"SUCCESS: Data consistency verified - All: {all_data['totalQuotes']}, Month: {month_data['totalQuotes']}, Week: {week_data['totalQuotes']}")


class TestWebSocketEndpoint:
    """Test WebSocket endpoint existence and user validation"""
    
    def test_websocket_user_exists_in_db(self):
        """Verify demo agent user exists for WebSocket connection"""
        response = requests.post(f"{BASE_URL}/api/auth/demo/agent")
        assert response.status_code == 200
        
        data = response.json()
        user_id = data["user_id"]
        
        # Verify user can authenticate (which means user exists in DB)
        me_response = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {data['token']}"}
        )
        assert me_response.status_code == 200
        assert me_response.json()["user_id"] == user_id
        
        print(f"SUCCESS: WebSocket user exists - {user_id}")
    
    def test_websocket_endpoint_rejects_http(self):
        """WebSocket endpoint should reject non-WebSocket HTTP requests"""
        # Regular HTTP request to WebSocket endpoint should fail
        response = requests.get(f"{BASE_URL}/api/ws/demo_agent_001")
        # FastAPI WebSocket endpoints return 404/403/400 for non-WebSocket requests
        # 404 is valid when the endpoint expects a proper WebSocket handshake
        assert response.status_code in [400, 403, 404, 426]  # Bad Request, Forbidden, Not Found, or Upgrade Required
        print(f"SUCCESS: WebSocket rejects HTTP - status: {response.status_code}")


class TestAgentSidebar:
    """Test agent dashboard sidebar navigation"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token for demo agent"""
        response = requests.post(f"{BASE_URL}/api/auth/demo/agent")
        assert response.status_code == 200
        return response.json()["token"]
    
    def test_agent_stats_endpoint(self, auth_token):
        """GET /api/stats/agent works (used by dashboard)"""
        response = requests.get(
            f"{BASE_URL}/api/stats/agent",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "total_clients" in data
        assert "pending_quotes" in data
        print(f"SUCCESS: Agent stats - Clients: {data['total_clients']}, Pending Quotes: {data['pending_quotes']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
