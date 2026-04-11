"""
Centralized test fixtures and credentials.

All test files should use these fixtures instead of hardcoding credentials.
Credentials are read from environment variables with fallback to test defaults.
"""
import os
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
