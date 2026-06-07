"""
In-process integration tests for POST /api/demo/enter and demo seed.

Requires MongoDB reachable at MONGO_URL (default 127.0.0.1:27017 from conftest).
Skipped automatically when Mongo is down so `pytest` stays usable offline.
"""
import os
from unittest.mock import MagicMock, patch

import pytest

try:
    from pymongo import MongoClient
except ImportError:
    MongoClient = None  # type: ignore


def _mongo_available() -> bool:
    if MongoClient is None:
        return False
    url = (os.environ.get("MONGO_URL") or "").strip() or "mongodb://127.0.0.1:27017"
    try:
        MongoClient(url, serverSelectionTimeoutMS=2500).admin.command("ping")
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _mongo_available(),
    reason="MongoDB not reachable (start mongo or set MONGO_URL)",
)


@pytest.fixture(scope="module")
def client():
    """FastAPI app with real Motor + Mongo."""
    from starlette.testclient import TestClient
    from server import app

    with TestClient(app) as c:
        yield c


class TestDemoSeed:
    def test_post_demo_seed_returns_payload(self, client):
        r = client.post("/api/demo/seed")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "demo_credentials" in data
        assert data["demo_credentials"]["agent"]["email"]


class TestDemoEnter:
    def test_enter_agent_fresh_sets_cookie_and_token(self, client):
        r = client.post(
            "/api/demo/enter",
            json={"persona": "agent", "fresh": True},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["user_id"] == "demo_agent_001"
        assert body["role"] == "agent"
        assert body["token"]
        assert body["redirect"] == "/agent/home"
        assert r.cookies.get("session_token")

    def test_enter_buyer_slots(self, client):
        for slot, uid in [(1, "demo_buyer_001"), (2, "demo_buyer_002"), (3, "demo_buyer_003"), (4, "demo_buyer_004")]:
            r = client.post(
                "/api/demo/enter",
                json={"persona": "buyer", "buyer_slot": slot, "fresh": True},
            )
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["user_id"] == uid
            assert body["role"] == "buyer"
            assert body["redirect"] == "/buyer/dashboard"

    def test_enter_fresh_false_after_seed_works(self, client):
        client.post("/api/demo/seed")
        r = client.post(
            "/api/demo/enter",
            json={"persona": "agent", "fresh": False},
        )
        assert r.status_code == 200, r.text

    def test_enter_invalid_persona_422(self, client):
        client.post("/api/demo/seed")
        r = client.post(
            "/api/demo/enter",
            json={"persona": "hacker", "fresh": False},
        )
        assert r.status_code == 422

    def test_enter_buyer_slot_out_of_range_422(self, client):
        client.post("/api/demo/seed")
        r = client.post(
            "/api/demo/enter",
            json={"persona": "buyer", "buyer_slot": 99, "fresh": False},
        )
        assert r.status_code == 422

    def test_enter_public_demo_disabled_404(self, client):
        client.post("/api/demo/seed")
        with patch("routes.demo.get_config") as m:
            cfg = MagicMock()
            cfg.public_demo_allowed = False
            m.return_value = cfg
            r = client.post(
                "/api/demo/enter",
                json={"persona": "agent", "fresh": False},
            )
        assert r.status_code == 404


class TestAuthDemoRemoved:
    def test_auth_demo_agent_gone(self, client):
        r = client.post("/api/auth/demo/agent")
        assert r.status_code == 404

    def test_auth_demo_buyer_gone(self, client):
        r = client.post("/api/auth/demo/buyer")
        assert r.status_code == 404
