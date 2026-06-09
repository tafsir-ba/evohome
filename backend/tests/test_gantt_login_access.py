"""Gantt invite-only login allowlist."""
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from core.gantt_access import (
    GANTT_LOGIN_DENIED_MESSAGE,
    enforce_gantt_login_allowed,
    enforce_gantt_registration_closed,
    is_gantt_allowed_login_email,
    is_gantt_auth_request,
)


def _request(origin=None, host=None):
    req = MagicMock()
    headers = {}
    if origin:
        headers["origin"] = origin
    if host:
        headers["host"] = host
    req.headers = headers
    return req


class TestGanttLoginAllowlist:
    def test_allowed_emails(self):
        assert is_gantt_allowed_login_email("tafsir@evo-home.ch")
        assert is_gantt_allowed_login_email("Tafsir@Evo-Home.CH")
        assert is_gantt_allowed_login_email("patricia.r.francis@gmail.com")
        assert is_gantt_allowed_login_email("vanessa@evo-home.ch")

    def test_denied_email(self):
        assert not is_gantt_allowed_login_email("other@example.com")

    def test_gantt_auth_detected_from_redirect_uri(self):
        assert is_gantt_auth_request(
            None, redirect_uri="https://carib-recon.org/auth/google/callback"
        )

    def test_enforce_denies_non_allowlisted_gantt_login(self):
        with pytest.raises(HTTPException) as exc:
            enforce_gantt_login_allowed(
                _request("https://carib-recon.org"),
                "stranger@example.com",
            )
        assert exc.value.status_code == 403
        assert exc.value.detail == GANTT_LOGIN_DENIED_MESSAGE

    def test_enforce_allows_allowlisted_gantt_login(self):
        enforce_gantt_login_allowed(
            _request("https://carib-recon.org"),
            "tafsir@evo-home.ch",
        )

    def test_enforce_skips_non_gantt_requests(self):
        enforce_gantt_login_allowed(_request("https://app.evo-home.ch"), "stranger@example.com")

    def test_registration_closed_on_gantt_host(self):
        with pytest.raises(HTTPException) as exc:
            enforce_gantt_registration_closed(_request(host="carib-recon.org"))
        assert exc.value.status_code == 403
        assert "registration is not available" in exc.value.detail.lower()
