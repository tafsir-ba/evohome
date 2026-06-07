"""Unit tests for Gantt authenticated-only auth."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from core.gantt_auth import get_gantt_actor


def _request(headers=None):
    req = MagicMock()
    req.cookies = {}
    req.headers = headers or {}
    return req


class TestGanttActor:
    def test_rejects_unauthenticated_requests(self):
        with pytest.raises(HTTPException) as exc:
            asyncio.run(get_gantt_actor(_request()))
        assert exc.value.status_code == 401
        assert "log in" in exc.value.detail.lower()

    def test_rejects_guest_session_even_with_header(self):
        with pytest.raises(HTTPException) as exc:
            asyncio.run(
                get_gantt_actor(
                    _request({"X-Gantt-Session": "11111111-1111-4111-8111-111111111111"})
                )
            )
        assert exc.value.status_code == 401

    def test_accepts_authenticated_user(self):
        user = {"user_id": "agent_abc123", "role": "agent"}

        with patch("core.gantt_auth.extract_token", return_value="token"), patch(
            "core.gantt_auth.get_current_user", AsyncMock(return_value=user)
        ):
            actor = asyncio.run(get_gantt_actor(_request()))
        assert actor["user_id"] == "agent_abc123"
        assert actor["role"] == "agent"

    def test_rejects_legacy_guest_user_id(self):
        user = {"user_id": "gantt_guest_abc", "role": "guest"}

        with patch("core.gantt_auth.extract_token", return_value="token"), patch(
            "core.gantt_auth.get_current_user", AsyncMock(return_value=user)
        ):
            with pytest.raises(HTTPException) as exc:
                asyncio.run(get_gantt_actor(_request()))
        assert exc.value.status_code == 401
