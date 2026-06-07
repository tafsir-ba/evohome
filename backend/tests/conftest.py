"""
Centralized test fixtures and credentials.

All test files should use these fixtures instead of hardcoding credentials.
Credentials are read from environment variables with fallback to test defaults.
"""
import os

# Minimal env so importing `database` / `server` during pytest never fails on empty env.
# Override with real values in CI or local `.env`; set EVOHOME_SKIP_TEST_ENV=1 to disable.
if not os.environ.get("EVOHOME_SKIP_TEST_ENV"):
    if not (os.environ.get("MONGO_URL") or "").strip():
        os.environ["MONGO_URL"] = "mongodb://127.0.0.1:27017"
    if not (os.environ.get("DB_NAME") or "").strip():
        os.environ["DB_NAME"] = "evohome_pytest"
    _jwt = (os.environ.get("JWT_SECRET") or "").strip()
    if len(_jwt) < 32:
        os.environ["JWT_SECRET"] = "pytest_jwt_secret_value_32_chars_min__"
    if not (os.environ.get("CORS_ORIGINS") or "").strip():
        os.environ["CORS_ORIGINS"] = "http://localhost:3000"

import pytest


# ── Test Credentials ──

DEMO_AGENT_EMAIL = os.environ.get("TEST_DEMO_AGENT_EMAIL", "demo.agent@upgradeflow.com")
DEMO_AGENT_PASSWORD = os.environ.get("TEST_DEMO_AGENT_PASSWORD", "demo123")

E2E_AGENT_EMAIL = os.environ.get("TEST_E2E_AGENT_EMAIL", "e2e@evohome-test.com")
E2E_AGENT_PASSWORD = os.environ.get("TEST_E2E_AGENT_PASSWORD", "Test2026!")

DEMO_BUYER_EMAIL = os.environ.get("TEST_DEMO_BUYER_EMAIL", "sophie.mueller@email.com")


@pytest.fixture
def demo_agent_credentials():
    """Demo agent login credentials."""
    return {"email": DEMO_AGENT_EMAIL, "password": DEMO_AGENT_PASSWORD}


@pytest.fixture
def e2e_agent_credentials():
    """E2E test agent login credentials."""
    return {"email": E2E_AGENT_EMAIL, "password": E2E_AGENT_PASSWORD}


@pytest.fixture
def api_base_url():
    """Base URL for API testing."""
    return os.environ.get("TEST_API_URL", "http://localhost:8001/api")
