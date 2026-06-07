"""
Regression tests for buyer activity parity across portal/feed paths.

Focus:
1) Activities sent to a buyer-linked client appear in `/api/buyer/portal`.
2) Image activities appear with file metadata/url in portal.
3) Activities sent to a unit peer client are still visible to buyer scope.
"""
import os
import uuid

import pytest
import requests


def _api_base_url() -> str:
    raw = (
        os.environ.get("TEST_API_URL")
        or os.environ.get("REACT_APP_BACKEND_URL")
        or "http://localhost:8001/api"
    ).rstrip("/")
    return raw if raw.endswith("/api") else f"{raw}/api"


BASE_URL = _api_base_url()


@pytest.fixture(scope="module")
def agent_session():
    session = requests.Session()
    response = session.post(f"{BASE_URL}/demo/enter", json={"persona": "agent", "fresh": False})
    assert response.status_code == 200, f"Demo agent login failed: {response.text}"
    token = response.json().get("token")
    assert token, f"No token in agent login response: {response.text}"
    session.headers.update({"Authorization": f"Bearer {token}"})
    return session


@pytest.fixture(scope="module")
def buyer_session_and_id():
    session = requests.Session()
    response = session.post(f"{BASE_URL}/demo/enter", json={"persona": "buyer", "buyer_slot": 1, "fresh": False})
    assert response.status_code == 200, f"Demo buyer login failed: {response.text}"
    payload = response.json()
    token = payload.get("token")
    buyer_id = payload.get("user_id")
    assert token, f"No token in buyer login response: {response.text}"
    assert buyer_id, f"No user_id in buyer login response: {response.text}"
    session.headers.update({"Authorization": f"Bearer {token}"})
    return session, buyer_id


def _select_buyer_client(agent_session: requests.Session, buyer_id: str) -> dict:
    clients_res = agent_session.get(f"{BASE_URL}/clients")
    assert clients_res.status_code == 200, f"Could not list clients: {clients_res.text}"
    clients = clients_res.json()
    buyer_clients = [c for c in clients if c.get("buyer_id") == buyer_id]
    assert buyer_clients, f"No clients linked to buyer {buyer_id}"
    client = buyer_clients[0]
    assert client.get("project_id"), f"Buyer client missing project_id: {client}"
    assert client.get("client_id"), f"Buyer client missing client_id: {client}"
    return client


def _create_activity(
    agent_session: requests.Session,
    *,
    activity_type: str,
    project_id: str,
    client_ids: list[str],
    title: str,
    content: str | None = None,
    files=None,
):
    form_data = {
        "type": activity_type,
        "project_id": project_id,
        "client_ids": ",".join(client_ids),
        "title": title,
    }
    if content is not None:
        form_data["content"] = content

    response = agent_session.post(
        f"{BASE_URL}/activities",
        data=form_data,
        files=files,
    )
    assert response.status_code == 200, f"Create activity failed: {response.text}"
    payload = response.json()
    assert payload.get("activity_id"), f"No activity_id returned: {payload}"
    return payload


class TestBuyerPortalActivityParity:
    def test_message_activity_visible_in_buyer_portal(self, agent_session, buyer_session_and_id):
        buyer_session, buyer_id = buyer_session_and_id
        buyer_client = _select_buyer_client(agent_session, buyer_id)

        created = _create_activity(
            agent_session,
            activity_type="message",
            project_id=buyer_client["project_id"],
            client_ids=[buyer_client["client_id"]],
            title=f"TEST_PORTAL_MSG_{uuid.uuid4().hex[:8]}",
            content="Portal parity regression test message",
        )

        portal_res = buyer_session.get(f"{BASE_URL}/buyer/portal")
        assert portal_res.status_code == 200, f"Buyer portal failed: {portal_res.text}"
        portal = portal_res.json()
        activities = portal.get("activities", [])
        assert isinstance(activities, list), f"Expected list for activities, got: {type(activities)}"
        assert any(a.get("activity_id") == created["activity_id"] for a in activities), (
            "New activity not found in buyer portal activities list"
        )

    def test_image_activity_visible_in_portal_with_file_url(self, agent_session, buyer_session_and_id):
        buyer_session, buyer_id = buyer_session_and_id
        buyer_client = _select_buyer_client(agent_session, buyer_id)

        png_bytes = b"\x89PNG\r\n\x1a\n" + (b"\x00" * 64)
        created = _create_activity(
            agent_session,
            activity_type="image",
            project_id=buyer_client["project_id"],
            client_ids=[buyer_client["client_id"]],
            title=f"TEST_PORTAL_IMG_{uuid.uuid4().hex[:8]}",
            files={"file": ("test.png", png_bytes, "image/png")},
        )

        portal_res = buyer_session.get(f"{BASE_URL}/buyer/portal")
        assert portal_res.status_code == 200, f"Buyer portal failed: {portal_res.text}"
        portal = portal_res.json()
        activities = portal.get("activities", [])
        match = next((a for a in activities if a.get("activity_id") == created["activity_id"]), None)
        assert match is not None, "Image activity missing from buyer portal"
        assert match.get("file_url"), f"Image activity should expose file_url: {match}"

    def test_unit_peer_targeted_activity_visible_via_buyer_scope(self, agent_session, buyer_session_and_id):
        buyer_session, buyer_id = buyer_session_and_id

        clients_res = agent_session.get(f"{BASE_URL}/clients")
        assert clients_res.status_code == 200, f"Could not list clients: {clients_res.text}"
        clients = clients_res.json()

        direct_clients = [c for c in clients if c.get("buyer_id") == buyer_id and c.get("unit_id")]
        if not direct_clients:
            pytest.skip("No buyer-linked client with unit_id found for unit-peer scope test")

        direct = direct_clients[0]
        peer = next(
            (
                c for c in clients
                if c.get("unit_id") == direct.get("unit_id")
                and c.get("client_id") != direct.get("client_id")
                and c.get("project_id") == direct.get("project_id")
            ),
            None,
        )
        if not peer or not peer.get("client_id"):
            pytest.skip("No same-unit peer client available for this environment")

        created = _create_activity(
            agent_session,
            activity_type="message",
            project_id=direct["project_id"],
            client_ids=[peer["client_id"]],
            title=f"TEST_PORTAL_PEER_{uuid.uuid4().hex[:8]}",
            content="Should be visible through unit peer expansion",
        )

        portal_res = buyer_session.get(f"{BASE_URL}/buyer/portal")
        assert portal_res.status_code == 200, f"Buyer portal failed: {portal_res.text}"
        activities = portal_res.json().get("activities", [])
        assert any(a.get("activity_id") == created["activity_id"] for a in activities), (
            "Peer-targeted activity not visible via buyer scope expansion"
        )
