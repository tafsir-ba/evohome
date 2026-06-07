"""
Test Debug Console API Endpoints.

Tests for the Production Debugging & Verification Console at /api/internal/debug.
All API endpoints require DEBUG_SECRET bearer token authentication.

Modules tested:
- Auth gate (401 without token, 200 with valid token)
- Health endpoint (trace count)
- Traces endpoint (list, filter, errors_only)
- Entity inspector endpoint
- Verifications endpoint (list, update)
- Static asset serving (CSS, JS)
- Path traversal protection
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
DEBUG_SECRET = os.environ.get('DEBUG_SECRET', 'n5RSa0jpS6hLCU0Sbuw5cjWjr3NFoaat8Dn5RIO4jCU')

# Known test document IDs from the review request
KNOWN_DOC_IDS = ["doc_1057cdb1c89d", "doc_4ea1e9124d2b"]


class TestDebugAuth:
    """Test debug console authentication gate."""

    def test_health_without_auth_returns_401(self):
        """Health endpoint requires auth."""
        response = requests.get(f"{BASE_URL}/api/internal/debug/health")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        data = response.json()
        # Canonical error format: {error, message, request_id, source}
        assert data.get("error") == "unauthorized" or (data.get("detail", {}).get("error") == "unauthorized")

    def test_health_with_wrong_token_returns_401(self):
        """Health endpoint rejects wrong token."""
        headers = {"Authorization": "Bearer wrong_token_12345"}
        response = requests.get(f"{BASE_URL}/api/internal/debug/health", headers=headers)
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"

    def test_health_with_valid_token_returns_200(self):
        """Health endpoint accepts valid DEBUG_SECRET."""
        headers = {"Authorization": f"Bearer {DEBUG_SECRET}"}
        response = requests.get(f"{BASE_URL}/api/internal/debug/health", headers=headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["status"] == "ok"
        assert "trace_count" in data
        assert isinstance(data["trace_count"], int)

    def test_traces_without_auth_returns_401(self):
        """Traces endpoint requires auth."""
        response = requests.get(f"{BASE_URL}/api/internal/debug/traces")
        assert response.status_code == 401

    def test_verifications_without_auth_returns_401(self):
        """Verifications endpoint requires auth."""
        response = requests.get(f"{BASE_URL}/api/internal/debug/verifications")
        assert response.status_code == 401


class TestDebugHealth:
    """Test debug health endpoint."""

    @pytest.fixture
    def auth_headers(self):
        return {"Authorization": f"Bearer {DEBUG_SECRET}"}

    def test_health_returns_trace_count(self, auth_headers):
        """Health endpoint returns trace count."""
        response = requests.get(f"{BASE_URL}/api/internal/debug/health", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "trace_count" in data
        assert "status" in data
        assert data["status"] == "ok"

    def test_health_returns_collections(self, auth_headers):
        """Health endpoint returns collection names."""
        response = requests.get(f"{BASE_URL}/api/internal/debug/health", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "collections" in data
        assert isinstance(data["collections"], list)


class TestDebugTraces:
    """Test debug traces endpoint."""

    @pytest.fixture
    def auth_headers(self):
        return {"Authorization": f"Bearer {DEBUG_SECRET}"}

    def test_list_traces_returns_array(self, auth_headers):
        """Traces endpoint returns traces array."""
        response = requests.get(f"{BASE_URL}/api/internal/debug/traces", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "traces" in data
        assert isinstance(data["traces"], list)
        assert "total" in data
        assert "limit" in data
        assert "offset" in data

    def test_traces_with_limit(self, auth_headers):
        """Traces endpoint respects limit parameter."""
        response = requests.get(f"{BASE_URL}/api/internal/debug/traces?limit=5", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data["traces"]) <= 5

    def test_traces_errors_only_filter(self, auth_headers):
        """Traces endpoint filters errors only."""
        response = requests.get(f"{BASE_URL}/api/internal/debug/traces?errors_only=true", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        # All returned traces should have non-success outcome
        for trace in data["traces"]:
            assert trace.get("outcome") != "success", f"Found success trace in errors_only: {trace}"

    def test_traces_method_filter(self, auth_headers):
        """Traces endpoint filters by method."""
        response = requests.get(f"{BASE_URL}/api/internal/debug/traces?method=POST", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        for trace in data["traces"]:
            assert trace.get("method") == "POST", f"Found non-POST trace: {trace.get('method')}"

    def test_traces_outcome_filter(self, auth_headers):
        """Traces endpoint filters by outcome."""
        response = requests.get(f"{BASE_URL}/api/internal/debug/traces?outcome=success", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        for trace in data["traces"]:
            assert trace.get("outcome") == "success"

    def test_traces_action_filter(self, auth_headers):
        """Traces endpoint filters by action (regex search)."""
        response = requests.get(f"{BASE_URL}/api/internal/debug/traces?action=auth", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        # Action filter is case-insensitive regex
        for trace in data["traces"]:
            action = trace.get("action", "")
            endpoint = trace.get("endpoint", "")
            assert "auth" in action.lower() or "auth" in endpoint.lower()

    def test_trace_structure(self, auth_headers):
        """Verify trace object structure."""
        response = requests.get(f"{BASE_URL}/api/internal/debug/traces?limit=1", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        if data["traces"]:
            trace = data["traces"][0]
            # Required fields
            assert "trace_id" in trace
            assert "request_id" in trace
            assert "method" in trace
            assert "endpoint" in trace
            assert "outcome" in trace
            assert "duration_ms" in trace
            assert "created_at" in trace


class TestDebugEntityInspector:
    """Test debug entity inspector endpoint."""

    @pytest.fixture
    def auth_headers(self):
        return {"Authorization": f"Bearer {DEBUG_SECRET}"}

    def test_inspect_document_entity(self, auth_headers):
        """Inspect a document entity."""
        # Try known document IDs
        for doc_id in KNOWN_DOC_IDS:
            response = requests.get(
                f"{BASE_URL}/api/internal/debug/entity/document/{doc_id}",
                headers=auth_headers
            )
            assert response.status_code == 200, f"Failed for {doc_id}: {response.text}"
            data = response.json()
            assert data["entity_type"] == "document"
            assert data["entity_id"] == doc_id
            assert "exists" in data
            assert "current_state" in data
            assert "traces" in data
            assert "state_transitions" in data
            if data["exists"]:
                break  # Found a valid document
        else:
            # If no known docs exist, just verify the API structure works
            pass

    def test_inspect_invalid_entity_type(self, auth_headers):
        """Invalid entity type returns 400."""
        response = requests.get(
            f"{BASE_URL}/api/internal/debug/entity/invalid_type/some_id",
            headers=auth_headers
        )
        assert response.status_code == 400
        data = response.json()
        # Canonical error format or FastAPI detail format
        error = data.get("error") or data.get("detail", {}).get("error")
        assert error == "invalid_entity_type"

    def test_inspect_nonexistent_entity(self, auth_headers):
        """Nonexistent entity returns exists=false."""
        response = requests.get(
            f"{BASE_URL}/api/internal/debug/entity/document/doc_nonexistent123",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["exists"] == False
        assert data["current_state"] is None

    def test_inspect_client_entity(self, auth_headers):
        """Inspect a client entity type."""
        response = requests.get(
            f"{BASE_URL}/api/internal/debug/entity/client/client_test123",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["entity_type"] == "client"

    def test_inspect_change_request_entity(self, auth_headers):
        """Inspect a change_request entity type."""
        response = requests.get(
            f"{BASE_URL}/api/internal/debug/entity/change_request/cr_test123",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["entity_type"] == "change_request"


class TestDebugVerifications:
    """Test debug verifications endpoint."""

    @pytest.fixture
    def auth_headers(self):
        return {"Authorization": f"Bearer {DEBUG_SECRET}"}

    def test_list_verifications(self, auth_headers):
        """List verifications returns 36-item checklist."""
        response = requests.get(f"{BASE_URL}/api/internal/debug/verifications", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert isinstance(data["items"], list)
        # Should have 36 items as per the seed
        assert len(data["items"]) == 36, f"Expected 36 items, got {len(data['items'])}"

    def test_verification_item_structure(self, auth_headers):
        """Verify verification item structure."""
        response = requests.get(f"{BASE_URL}/api/internal/debug/verifications", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        if data["items"]:
            item = data["items"][0]
            assert "item_id" in item
            assert "category" in item
            assert "name" in item
            assert "description" in item
            assert "status" in item
            assert item["status"] in ("untested", "passed", "failed")

    def test_update_verification_status(self, auth_headers):
        """Update verification status via PUT."""
        # First get an item
        response = requests.get(f"{BASE_URL}/api/internal/debug/verifications", headers=auth_headers)
        assert response.status_code == 200
        items = response.json()["items"]
        assert len(items) > 0

        item_id = items[0]["item_id"]

        # Update status to passed
        update_response = requests.put(
            f"{BASE_URL}/api/internal/debug/verifications/{item_id}",
            headers={**auth_headers, "Content-Type": "application/json"},
            json={"status": "passed", "verified_by": "test_agent"}
        )
        assert update_response.status_code == 200, f"Update failed: {update_response.text}"
        updated = update_response.json()
        assert updated["status"] == "passed"
        assert updated["verified_by"] == "test_agent"
        assert "last_verified" in updated

    def test_update_verification_invalid_status(self, auth_headers):
        """Invalid status returns 400."""
        response = requests.get(f"{BASE_URL}/api/internal/debug/verifications", headers=auth_headers)
        items = response.json()["items"]
        item_id = items[0]["item_id"]

        update_response = requests.put(
            f"{BASE_URL}/api/internal/debug/verifications/{item_id}",
            headers={**auth_headers, "Content-Type": "application/json"},
            json={"status": "invalid_status"}
        )
        assert update_response.status_code == 400
        data = update_response.json()
        # Canonical error format or FastAPI detail format
        error = data.get("error") or data.get("detail", {}).get("error")
        assert error == "invalid_status"

    def test_update_nonexistent_verification(self, auth_headers):
        """Update nonexistent item returns 404."""
        update_response = requests.put(
            f"{BASE_URL}/api/internal/debug/verifications/BUG-999",
            headers={**auth_headers, "Content-Type": "application/json"},
            json={"status": "passed"}
        )
        assert update_response.status_code == 404


class TestDebugStaticAssets:
    """Test debug console static asset serving."""

    def test_debug_console_html_served(self):
        """Debug console HTML is served without auth."""
        response = requests.get(f"{BASE_URL}/api/internal/debug")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        assert "Evohome Debug Console" in response.text

    def test_css_served(self):
        """CSS file is served."""
        response = requests.get(f"{BASE_URL}/api/internal/debug/css/styles.css")
        assert response.status_code == 200
        assert "text/css" in response.headers.get("content-type", "")
        assert ":root" in response.text  # CSS variables

    def test_js_api_served(self):
        """JS api.js file is served."""
        response = requests.get(f"{BASE_URL}/api/internal/debug/js/api.js")
        assert response.status_code == 200
        assert "javascript" in response.headers.get("content-type", "")
        assert "apiFetch" in response.text

    def test_js_traces_served(self):
        """JS traces.js file is served."""
        response = requests.get(f"{BASE_URL}/api/internal/debug/js/traces.js")
        assert response.status_code == 200
        assert "loadTraces" in response.text

    def test_js_entity_inspector_served(self):
        """JS entity-inspector.js file is served."""
        response = requests.get(f"{BASE_URL}/api/internal/debug/js/entity-inspector.js")
        assert response.status_code == 200
        assert "inspectEntity" in response.text

    def test_js_verifications_served(self):
        """JS verifications.js file is served."""
        response = requests.get(f"{BASE_URL}/api/internal/debug/js/verifications.js")
        assert response.status_code == 200
        assert "loadVerifications" in response.text


class TestDebugPathTraversal:
    """Test path traversal protection."""

    def test_path_traversal_blocked_js(self):
        """Path traversal in JS route is blocked."""
        response = requests.get(f"{BASE_URL}/api/internal/debug/js/..%2F..%2Fserver.py")
        assert response.status_code == 404

    def test_path_traversal_blocked_css(self):
        """Path traversal in CSS route is blocked."""
        response = requests.get(f"{BASE_URL}/api/internal/debug/css/..%2F..%2Fserver.py")
        assert response.status_code == 404

    def test_path_traversal_with_backslash(self):
        """Path traversal with backslash is blocked."""
        response = requests.get(f"{BASE_URL}/api/internal/debug/js/..\\..\\server.py")
        assert response.status_code == 404

    def test_nonexistent_js_file(self):
        """Nonexistent JS file returns 404."""
        response = requests.get(f"{BASE_URL}/api/internal/debug/js/nonexistent.js")
        assert response.status_code == 404

    def test_nonexistent_css_file(self):
        """Nonexistent CSS file returns 404."""
        response = requests.get(f"{BASE_URL}/api/internal/debug/css/nonexistent.css")
        assert response.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
