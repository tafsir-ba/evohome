"""
Regression tests for multi-buyer notification fanout on document send.

Goal:
- When a document is sent for a unit with multiple buyer-linked clients,
  all buyer recipients should receive a document_sent notification.
"""
import os
import uuid
import time
from collections import defaultdict

import pytest
import requests


def _api_base_url():
    raw = (
        os.environ.get("TEST_API_URL")
        or os.environ.get("REACT_APP_BACKEND_URL")
        or "http://localhost:8001/api"
    ).rstrip("/")
    return raw if raw.endswith("/api") else f"{raw}/api"


BASE_URL = _api_base_url()


def _new_session():
    return requests.Session()


def _demo_login(session, persona, buyer_slot=None):
    payload = {"persona": persona, "fresh": False}
    if buyer_slot is not None:
        payload["buyer_slot"] = buyer_slot
    try:
        response = session.post(f"{BASE_URL}/demo/enter", json=payload, timeout=10)
    except requests.RequestException:
        pytest.skip("API is not reachable for integration tests")

    if response.status_code != 200:
        pytest.skip(f"Demo login failed for persona={persona}: {response.status_code}")

    data = response.json()
    token = data.get("token")
    if not token:
        pytest.skip(f"No token returned for persona={persona}")
    session.headers.update({"Authorization": f"Bearer {token}"})
    return data


@pytest.fixture(scope="module")
def agent_session():
    session = _new_session()
    _demo_login(session, "agent")
    return session


@pytest.fixture(scope="module")
def buyer_sessions_by_user_id():
    by_user_id = {}
    for slot in (1, 2, 3, 4):
        session = _new_session()
        data = _demo_login(session, "buyer", buyer_slot=slot)
        user_id = data.get("user_id")
        if user_id:
            by_user_id[user_id] = session
    return by_user_id


def _find_multi_buyer_unit(agent_session):
    response = agent_session.get(f"{BASE_URL}/clients", timeout=15)
    assert response.status_code == 200, f"Could not list clients: {response.text}"
    clients = response.json()

    by_unit = defaultdict(list)
    for client in clients:
        if client.get("unit_id") and client.get("buyer_id"):
            by_unit[client["unit_id"]].append(client)

    for unit_id, rows in by_unit.items():
        buyer_ids = {r.get("buyer_id") for r in rows if r.get("buyer_id")}
        if len(buyer_ids) >= 2:
            return unit_id, rows
    return None, []


def _has_doc_notification(session, document_id):
    response = session.get(f"{BASE_URL}/notifications", timeout=15)
    if response.status_code != 200:
        return False
    payload = response.json()
    notifications = payload.get("notifications", [])
    for n in notifications:
        if n.get("notification_type") != "document_sent":
            continue
        metadata = n.get("metadata") or {}
        if metadata.get("document_id") == document_id:
            return True
    return False


class TestMultiBuyerNotificationFanout:
    def test_send_document_notifies_all_unit_buyers(self, agent_session, buyer_sessions_by_user_id):
        unit_id, unit_clients = _find_multi_buyer_unit(agent_session)
        if not unit_id:
            pytest.skip("No unit with multiple buyer-linked clients found")

        buyer_ids = sorted({c.get("buyer_id") for c in unit_clients if c.get("buyer_id")})
        if not buyer_ids:
            pytest.skip("No buyer-linked clients found in selected multi-buyer unit")

        missing_sessions = [bid for bid in buyer_ids if bid not in buyer_sessions_by_user_id]
        if missing_sessions:
            pytest.skip(f"Missing buyer demo sessions for user_ids: {missing_sessions}")

        primary_client = unit_clients[0]

        create_payload = {
            "type": "quote",
            "title": f"TEST_MULTI_BUYER_NOTIF_{uuid.uuid4().hex[:8]}",
            "client_id": primary_client["client_id"],
            "items": [
                {"description": "Multi-buyer fanout test", "quantity": 1, "unit_price": 100.0, "total": 100.0}
            ],
            "amount": 100.0,
        }
        create_response = agent_session.post(f"{BASE_URL}/documents/create", json=create_payload, timeout=20)
        assert create_response.status_code in (200, 201), f"Document create failed: {create_response.text}"
        document_id = create_response.json()["document_id"]

        send_response = agent_session.post(f"{BASE_URL}/documents/{document_id}/send", timeout=20)
        assert send_response.status_code == 200, f"Document send failed: {send_response.text}"
        send_data = send_response.json()

        recipient_ids = send_data.get("recipient", {}).get("client_ids", [])
        assert len(recipient_ids) >= 2, f"Expected unit fanout recipients >=2, got {recipient_ids}"

        # Poll briefly to absorb async persistence timing.
        deadline = time.time() + 8
        pending = set(buyer_ids)
        while time.time() < deadline and pending:
            delivered = []
            for buyer_id in pending:
                session = buyer_sessions_by_user_id[buyer_id]
                if _has_doc_notification(session, document_id):
                    delivered.append(buyer_id)
            for buyer_id in delivered:
                pending.discard(buyer_id)
            if pending:
                time.sleep(0.8)

        assert not pending, f"Missing document_sent notification for buyers: {sorted(pending)}"
