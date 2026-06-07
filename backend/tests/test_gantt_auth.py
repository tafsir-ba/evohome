"""Unit tests for Gantt anonymous session auth."""
import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from core.gantt_auth import GANTT_SESSION_HEADER, get_gantt_actor


def _request(headers=None):
    req = MagicMock()
    req.cookies = {}
    req.headers = headers or {}
    return req


class TestGanttActor:
    def test_rejects_unauthenticated_without_session(self):
        with pytest.raises(HTTPException) as exc:
            asyncio.run(get_gantt_actor(_request()))
        assert exc.value.status_code == 401

    def test_accepts_valid_guest_session(self):
        session_id = str(uuid.uuid4())
        actor = asyncio.run(
            get_gantt_actor(_request({GANTT_SESSION_HEADER: session_id}))
        )
        assert actor["user_id"] == f"gantt_guest_{session_id}"
        assert actor["is_guest"] is True

    def test_rejects_invalid_session_format(self):
        with pytest.raises(HTTPException) as exc:
            asyncio.run(
                get_gantt_actor(_request({GANTT_SESSION_HEADER: "not-a-uuid"}))
            )
        assert exc.value.status_code == 401

    def test_prefers_login_token_over_guest_session(self):
        session_id = str(uuid.uuid4())
        user = {"user_id": "u_real", "role": "agent"}

        with patch("core.gantt_auth.extract_token", return_value="token"), patch(
            "core.gantt_auth.get_current_user", AsyncMock(return_value=user)
        ):
            actor = asyncio.run(
                get_gantt_actor(_request({GANTT_SESSION_HEADER: session_id}))
            )
        assert actor["user_id"] == "u_real"
