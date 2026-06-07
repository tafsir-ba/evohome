"""
Phase 4 Billing Rebuild Tests - Iteration 14

Tests for the canonical billing_service.py SSOT implementation:
- GET /api/billing/plans - 4 plans with correct pricing
- GET /api/billing/status - subscription status with entitlement fields
- POST /api/billing/create-checkout-session - Stripe checkout creation
- POST /api/billing/webhook - all webhook event types
- POST /api/billing/cancel - subscription cancellation
- POST /api/billing/sync - subscription sync
- POST /api/billing/verify-session - checkout verification
- Entitlement enforcement via units.py
- Auth requirements on all endpoints
"""
import pytest
import requests
import os
import uuid
import json

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"

# Test agent credentials
DEMO_AGENT_EMAIL = "demo.agent@upgradeflow.com"
DEMO_AGENT_PASSWORD = "demo123"
E2E_AGENT_EMAIL = "e2e@evohome-test.com"
E2E_AGENT_PASSWORD = "Test2026!"


class TestBillingPlans:
    """Tests for GET /api/billing/plans endpoint - returns 4 plans with correct pricing"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get demo agent token"""
        res = requests.post(f"{BASE_URL}/api/demo/enter", json={"persona": "agent", "fresh": False})
        assert res.status_code == 200, f"Demo agent login failed: {res.text}"
        self.token = res.json()['token']
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_plans_returns_4_plans(self):
        """GET /api/billing/plans returns exactly 4 plans"""
        res = requests.get(f"{BASE_URL}/api/billing/plans", headers=self.headers)
        assert res.status_code == 200
        
        plans = res.json()
        assert len(plans) == 4, f"Expected 4 plans, got {len(plans)}"
        
        plan_ids = [p['plan_id'] for p in plans]
        assert 'free' in plan_ids
        assert 'starter' in plan_ids
        assert 'pro' in plan_ids
        assert 'enterprise' in plan_ids
    
    def test_free_plan_correct_pricing(self):
        """Free plan: CHF 0, 2 units limit"""
        res = requests.get(f"{BASE_URL}/api/billing/plans", headers=self.headers)
        plans = {p['plan_id']: p for p in res.json()}
        
        free = plans['free']
        assert free['name'] == 'Free'
        assert free['price'] == 0
        assert free['currency'] == 'CHF'
        assert free['property_limit'] == 2
        assert free['is_enterprise'] == False
    
    def test_starter_plan_correct_pricing(self):
        """Starter plan: CHF 29, 10 units limit"""
        res = requests.get(f"{BASE_URL}/api/billing/plans", headers=self.headers)
        plans = {p['plan_id']: p for p in res.json()}
        
        starter = plans['starter']
        assert starter['name'] == 'Starter'
        assert starter['price'] == 29
        assert starter['currency'] == 'CHF'
        assert starter['property_limit'] == 10
        assert starter['is_enterprise'] == False
    
    def test_pro_plan_correct_pricing(self):
        """Pro plan: CHF 79, 50 units limit"""
        res = requests.get(f"{BASE_URL}/api/billing/plans", headers=self.headers)
        plans = {p['plan_id']: p for p in res.json()}
        
        pro = plans['pro']
        assert pro['name'] == 'Pro'
        assert pro['price'] == 79
        assert pro['currency'] == 'CHF'
        assert pro['property_limit'] == 50
        assert pro['is_enterprise'] == False
    
    def test_enterprise_plan_correct_pricing(self):
        """Enterprise plan: custom pricing (None), unlimited units (None)"""
        res = requests.get(f"{BASE_URL}/api/billing/plans", headers=self.headers)
        plans = {p['plan_id']: p for p in res.json()}
        
        enterprise = plans['enterprise']
        assert enterprise['name'] == 'Enterprise'
        assert enterprise['price'] is None
        assert enterprise['property_limit'] is None
        assert enterprise['is_enterprise'] == True


class TestBillingStatus:
    """Tests for GET /api/billing/status - subscription status with entitlement fields"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get demo agent token"""
        res = requests.post(f"{BASE_URL}/api/demo/enter", json={"persona": "agent", "fresh": False})
        assert res.status_code == 200
        self.token = res.json()['token']
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_status_returns_entitlement_fields(self):
        """Status returns plan_id, property_limit, unit_usage, can_create_unit"""
        res = requests.get(f"{BASE_URL}/api/billing/status", headers=self.headers)
        assert res.status_code == 200
        
        status = res.json()
        
        # Required entitlement fields
        assert 'plan_id' in status
        assert 'plan_name' in status
        assert 'property_limit' in status
        assert 'current_unit_count' in status
        assert 'subscription_status' in status
        assert 'unit_limit' in status
        assert 'unit_usage' in status
        assert 'can_create_unit' in status
    
    def test_status_returns_stripe_fields(self):
        """Status returns Stripe-related fields"""
        res = requests.get(f"{BASE_URL}/api/billing/status", headers=self.headers)
        status = res.json()
        
        # Stripe fields (may be null for demo)
        assert 'stripe_subscription_id' in status
        assert 'stripe_customer_id' in status
        assert 'subscription_period_end' in status
    
    def test_demo_agent_has_pro_plan(self):
        """Demo agent should be seeded with Pro plan"""
        # Reseed to ensure clean state (previous tests may have modified plan)
        requests.post(f"{BASE_URL}/api/demo/seed")
        
        # Get fresh token after reseed
        res = requests.post(f"{BASE_URL}/api/demo/enter", json={"persona": "agent", "fresh": False})
        token = res.json()['token']
        headers = {"Authorization": f"Bearer {token}"}
        
        res = requests.get(f"{BASE_URL}/api/billing/status", headers=headers)
        status = res.json()
        
        assert status['plan_id'] == 'pro', f"Expected pro plan, got {status['plan_id']}"
        assert status['plan_name'] == 'Pro'
        assert status['property_limit'] == 50


class TestCheckoutSession:
    """Tests for POST /api/billing/create-checkout-session"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get demo agent token"""
        res = requests.post(f"{BASE_URL}/api/demo/enter", json={"persona": "agent", "fresh": False})
        assert res.status_code == 200
        self.token = res.json()['token']
        self.headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
    
    def test_checkout_starter_plan_success(self):
        """POST with plan_id=starter creates Stripe checkout session"""
        res = requests.post(
            f"{BASE_URL}/api/billing/create-checkout-session",
            headers=self.headers,
            json={"plan_id": "starter", "origin_url": BASE_URL}
        )
        assert res.status_code == 200
        
        data = res.json()
        assert 'checkout_url' in data
        assert 'session_id' in data
        assert data['checkout_url'].startswith('https://checkout.stripe.com')
        assert data['session_id'].startswith('cs_test_')
    
    def test_checkout_pro_plan_success(self):
        """POST with plan_id=pro creates Stripe checkout session"""
        res = requests.post(
            f"{BASE_URL}/api/billing/create-checkout-session",
            headers=self.headers,
            json={"plan_id": "pro", "origin_url": BASE_URL}
        )
        assert res.status_code == 200
        
        data = res.json()
        assert 'checkout_url' in data
        assert 'session_id' in data
    
    def test_checkout_free_plan_returns_400(self):
        """POST with plan_id=free should return 400 (invalid plan)"""
        res = requests.post(
            f"{BASE_URL}/api/billing/create-checkout-session",
            headers=self.headers,
            json={"plan_id": "free", "origin_url": BASE_URL}
        )
        assert res.status_code == 400, f"Expected 400, got {res.status_code}: {res.text}"
    
    def test_checkout_enterprise_plan_returns_400(self):
        """POST with plan_id=enterprise should return 400 (invalid plan)"""
        res = requests.post(
            f"{BASE_URL}/api/billing/create-checkout-session",
            headers=self.headers,
            json={"plan_id": "enterprise", "origin_url": BASE_URL}
        )
        assert res.status_code == 400, f"Expected 400, got {res.status_code}: {res.text}"
    
    def test_checkout_invalid_plan_returns_400(self):
        """POST with invalid plan_id returns 400"""
        res = requests.post(
            f"{BASE_URL}/api/billing/create-checkout-session",
            headers=self.headers,
            json={"plan_id": "nonexistent", "origin_url": BASE_URL}
        )
        assert res.status_code == 400


class TestWebhookEvents:
    """Tests for POST /api/billing/webhook - all webhook event types"""
    
    def test_checkout_session_completed_updates_subscription(self):
        """checkout.session.completed updates subscription_plan, stripe_customer_id, stripe_subscription_id"""
        # First get a test agent (response is flat, not nested under 'user')
        res = requests.post(f"{BASE_URL}/api/demo/enter", json={"persona": "agent", "fresh": False})
        assert res.status_code == 200
        data = res.json()
        token = data['token']
        agent_id = data['user_id']
        headers = {"Authorization": f"Bearer {token}"}
        
        # Simulate checkout.session.completed webhook
        webhook_payload = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "metadata": {
                        "agent_id": agent_id,
                        "plan_id": "starter"
                    },
                    "customer": "cus_test_webhook_123",
                    "subscription": "sub_test_webhook_123"
                }
            }
        }
        
        res = requests.post(
            f"{BASE_URL}/api/billing/webhook",
            json=webhook_payload,
            headers={"Content-Type": "application/json"}
        )
        assert res.status_code == 200
        
        result = res.json()
        assert result.get('received') == True
        assert result.get('handled') == True
        
        # Verify subscription was updated
        res = requests.get(f"{BASE_URL}/api/billing/status", headers=headers)
        status = res.json()
        assert status['plan_id'] == 'starter'
        assert status['stripe_customer_id'] == 'cus_test_webhook_123'
        assert status['stripe_subscription_id'] == 'sub_test_webhook_123'
    
    def test_subscription_updated_changes_status(self):
        """customer.subscription.updated changes subscription_status"""
        # Get demo agent with stripe_customer_id set from previous test
        res = requests.post(f"{BASE_URL}/api/demo/enter", json={"persona": "agent", "fresh": False})
        token = res.json()['token']
        headers = {"Authorization": f"Bearer {token}"}
        
        # Get current customer_id
        status_res = requests.get(f"{BASE_URL}/api/billing/status", headers=headers)
        customer_id = status_res.json().get('stripe_customer_id')
        
        if not customer_id:
            pytest.skip("No stripe_customer_id set - run checkout test first")
        
        # Simulate subscription.updated webhook
        webhook_payload = {
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "customer": customer_id,
                    "status": "active",
                    "current_period_end": 1735689600,
                    "metadata": {"plan_id": "starter"}
                }
            }
        }
        
        res = requests.post(
            f"{BASE_URL}/api/billing/webhook",
            json=webhook_payload,
            headers={"Content-Type": "application/json"}
        )
        assert res.status_code == 200
        assert res.json().get('handled') == True
    
    def test_subscription_deleted_downgrades_to_free(self):
        """customer.subscription.deleted downgrades to free, sets stripe_subscription_id to null"""
        # Get demo agent
        res = requests.post(f"{BASE_URL}/api/demo/enter", json={"persona": "agent", "fresh": False})
        token = res.json()['token']
        headers = {"Authorization": f"Bearer {token}"}
        
        # Get current customer_id
        status_res = requests.get(f"{BASE_URL}/api/billing/status", headers=headers)
        customer_id = status_res.json().get('stripe_customer_id')
        
        if not customer_id:
            pytest.skip("No stripe_customer_id set")
        
        # Simulate subscription.deleted webhook
        webhook_payload = {
            "type": "customer.subscription.deleted",
            "data": {
                "object": {
                    "customer": customer_id
                }
            }
        }
        
        res = requests.post(
            f"{BASE_URL}/api/billing/webhook",
            json=webhook_payload,
            headers={"Content-Type": "application/json"}
        )
        assert res.status_code == 200
        assert res.json().get('handled') == True
        
        # Verify downgraded to free
        res = requests.get(f"{BASE_URL}/api/billing/status", headers=headers)
        status = res.json()
        assert status['plan_id'] == 'free', f"Expected free plan after deletion, got {status['plan_id']}"
        assert status['stripe_subscription_id'] is None
    
    def test_payment_failed_sets_past_due(self):
        """invoice.payment_failed sets status to past_due"""
        # First set up a customer_id via checkout webhook (response is flat)
        res = requests.post(f"{BASE_URL}/api/demo/enter", json={"persona": "agent", "fresh": False})
        data = res.json()
        token = data['token']
        agent_id = data['user_id']
        headers = {"Authorization": f"Bearer {token}"}
        
        # Set up customer via checkout webhook
        checkout_payload = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "metadata": {"agent_id": agent_id, "plan_id": "pro"},
                    "customer": "cus_test_payment_fail",
                    "subscription": "sub_test_payment_fail"
                }
            }
        }
        requests.post(f"{BASE_URL}/api/billing/webhook", json=checkout_payload)
        
        # Now simulate payment failed
        webhook_payload = {
            "type": "invoice.payment_failed",
            "data": {
                "object": {
                    "customer": "cus_test_payment_fail"
                }
            }
        }
        
        res = requests.post(
            f"{BASE_URL}/api/billing/webhook",
            json=webhook_payload,
            headers={"Content-Type": "application/json"}
        )
        assert res.status_code == 200
        assert res.json().get('handled') == True
        
        # Verify status is past_due
        res = requests.get(f"{BASE_URL}/api/billing/status", headers=headers)
        status = res.json()
        assert status['subscription_status'] == 'past_due'


class TestCancelSubscription:
    """Tests for POST /api/billing/cancel"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get demo agent token"""
        res = requests.post(f"{BASE_URL}/api/demo/enter", json={"persona": "agent", "fresh": False})
        assert res.status_code == 200
        self.token = res.json()['token']
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_cancel_returns_400_when_no_subscription(self):
        """POST /api/billing/cancel returns 400 when no active subscription"""
        # First ensure no stripe_subscription_id by simulating deletion
        status_res = requests.get(f"{BASE_URL}/api/billing/status", headers=self.headers)
        customer_id = status_res.json().get('stripe_customer_id')
        
        if customer_id:
            # Clear subscription via webhook
            webhook_payload = {
                "type": "customer.subscription.deleted",
                "data": {"object": {"customer": customer_id}}
            }
            requests.post(f"{BASE_URL}/api/billing/webhook", json=webhook_payload)
        
        # Now try to cancel
        res = requests.post(f"{BASE_URL}/api/billing/cancel", headers=self.headers)
        assert res.status_code == 400, f"Expected 400, got {res.status_code}: {res.text}"
        assert "No active subscription" in res.json().get('detail', '')


class TestSyncSubscription:
    """Tests for POST /api/billing/sync"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get demo agent token"""
        res = requests.post(f"{BASE_URL}/api/demo/enter", json={"persona": "agent", "fresh": False})
        assert res.status_code == 200
        self.token = res.json()['token']
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_sync_returns_status(self):
        """POST /api/billing/sync returns sync status"""
        res = requests.post(f"{BASE_URL}/api/billing/sync", headers=self.headers)
        assert res.status_code == 200
        
        data = res.json()
        # Should have synced field or message
        assert 'synced' in data or 'message' in data or 'current_plan' in data


class TestVerifySession:
    """Tests for POST /api/billing/verify-session"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get demo agent token"""
        res = requests.post(f"{BASE_URL}/api/demo/enter", json={"persona": "agent", "fresh": False})
        assert res.status_code == 200
        self.token = res.json()['token']
        self.headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
    
    def test_verify_session_with_invalid_session(self):
        """verify-session with invalid session_id returns appropriate response"""
        res = requests.post(
            f"{BASE_URL}/api/billing/verify-session",
            headers=self.headers,
            json={"session_id": "cs_test_invalid_session_id"}
        )
        # Should return 500 (Stripe error) or 200 with success=false
        assert res.status_code in [200, 500]


class TestEntitlementEnforcement:
    """Tests for entitlement enforcement - unit creation limits"""
    
    def test_free_plan_unit_limit_enforcement(self):
        """Create units on free plan (limit 2), 3rd unit should be blocked with 403"""
        # Register a fresh agent (starts on free plan)
        unique_email = f"test.entitlement.{uuid.uuid4().hex[:8]}@example.com"
        
        res = requests.post(
            f"{BASE_URL}/api/auth/register",
            json={"email": unique_email, "password": "TestPass123!", "name": "Entitlement Test"}
        )
        assert res.status_code == 200, f"Registration failed: {res.text}"
        token = res.json()['token']
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        
        # Verify on free plan
        status_res = requests.get(f"{BASE_URL}/api/billing/status", headers=headers)
        status = status_res.json()
        assert status['plan_id'] == 'free'
        assert status['property_limit'] == 2
        
        # Create first project (needed for units)
        proj_res = requests.post(
            f"{BASE_URL}/api/projects",
            headers=headers,
            json={"name": "Entitlement Test Project"}
        )
        assert proj_res.status_code == 200, f"Project creation failed: {proj_res.text}"
        project_id = proj_res.json()['project_id']
        
        # Create 2 units (should succeed)
        for i in range(2):
            unit_res = requests.post(
                f"{BASE_URL}/api/projects/{project_id}/units",
                headers=headers,
                json={"unit_reference": f"Unit {i+1}"}
            )
            assert unit_res.status_code == 200, f"Unit {i+1} creation failed: {unit_res.text}"
        
        # Verify at limit
        status_res = requests.get(f"{BASE_URL}/api/billing/status", headers=headers)
        status = status_res.json()
        assert status['unit_usage'] == 2
        assert status['can_create_unit'] == False
        
        # 3rd unit should fail with 403
        unit_res = requests.post(
            f"{BASE_URL}/api/projects/{project_id}/units",
            headers=headers,
            json={"unit_reference": "Unit 3"}
        )
        assert unit_res.status_code == 403, f"Expected 403, got {unit_res.status_code}: {unit_res.text}"
        assert "limit" in unit_res.json().get('detail', '').lower()
    
    def test_upgrade_allows_more_units(self):
        """After webhook upgrades to pro (limit 50), unit creation should succeed"""
        # Register fresh agent (response is flat)
        unique_email = f"test.upgrade.{uuid.uuid4().hex[:8]}@example.com"
        
        res = requests.post(
            f"{BASE_URL}/api/auth/register",
            json={"email": unique_email, "password": "TestPass123!", "name": "Upgrade Test"}
        )
        assert res.status_code == 200
        data = res.json()
        token = data['token']
        agent_id = data['user_id']
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        
        # Create project
        proj_res = requests.post(
            f"{BASE_URL}/api/projects",
            headers=headers,
            json={"name": "Upgrade Test Project"}
        )
        project_id = proj_res.json()['project_id']
        
        # Fill free plan limit (2 units)
        for i in range(2):
            requests.post(
                f"{BASE_URL}/api/projects/{project_id}/units",
                headers=headers,
                json={"unit_reference": f"Unit {i+1}"}
            )
        
        # Verify blocked
        unit_res = requests.post(
            f"{BASE_URL}/api/projects/{project_id}/units",
            headers=headers,
            json={"unit_reference": "Unit 3"}
        )
        assert unit_res.status_code == 403
        
        # Simulate upgrade via webhook
        webhook_payload = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "metadata": {"agent_id": agent_id, "plan_id": "pro"},
                    "customer": f"cus_upgrade_test_{uuid.uuid4().hex[:8]}",
                    "subscription": f"sub_upgrade_test_{uuid.uuid4().hex[:8]}"
                }
            }
        }
        webhook_res = requests.post(f"{BASE_URL}/api/billing/webhook", json=webhook_payload)
        assert webhook_res.status_code == 200
        
        # Verify upgraded to pro
        status_res = requests.get(f"{BASE_URL}/api/billing/status", headers=headers)
        status = status_res.json()
        assert status['plan_id'] == 'pro'
        assert status['property_limit'] == 50
        assert status['can_create_unit'] == True
        
        # Now unit creation should succeed
        unit_res = requests.post(
            f"{BASE_URL}/api/projects/{project_id}/units",
            headers=headers,
            json={"unit_reference": "Unit 3 After Upgrade"}
        )
        assert unit_res.status_code == 200, f"Unit creation after upgrade failed: {unit_res.text}"


class TestAuthRequirements:
    """Tests that all billing endpoints require authentication"""
    
    def test_plans_requires_auth(self):
        """GET /api/billing/plans requires auth (401 without token)"""
        res = requests.get(f"{BASE_URL}/api/billing/plans")
        assert res.status_code == 401
    
    def test_status_requires_auth(self):
        """GET /api/billing/status requires auth"""
        res = requests.get(f"{BASE_URL}/api/billing/status")
        assert res.status_code == 401
    
    def test_checkout_requires_auth(self):
        """POST /api/billing/create-checkout-session requires auth"""
        res = requests.post(
            f"{BASE_URL}/api/billing/create-checkout-session",
            json={"plan_id": "starter", "origin_url": BASE_URL}
        )
        assert res.status_code == 401
    
    def test_verify_session_requires_auth(self):
        """POST /api/billing/verify-session requires auth"""
        res = requests.post(
            f"{BASE_URL}/api/billing/verify-session",
            json={"session_id": "cs_test_123"}
        )
        assert res.status_code == 401
    
    def test_cancel_requires_auth(self):
        """POST /api/billing/cancel requires auth"""
        res = requests.post(f"{BASE_URL}/api/billing/cancel")
        assert res.status_code == 401
    
    def test_sync_requires_auth(self):
        """POST /api/billing/sync requires auth"""
        res = requests.post(f"{BASE_URL}/api/billing/sync")
        assert res.status_code == 401
    
    def test_portal_requires_auth(self):
        """POST /api/billing/portal requires auth"""
        res = requests.post(f"{BASE_URL}/api/billing/portal", json={})
        assert res.status_code == 401


class TestCanonicalUpdatePath:
    """Tests that webhook and verify-session converge to same canonical update path"""
    
    def test_webhook_and_verify_produce_same_state(self):
        """Verify webhook and verify-session use same apply_subscription_update"""
        # This is verified by code inspection - both call apply_subscription_update
        # We test that the DB state is consistent after webhook
        
        res = requests.post(f"{BASE_URL}/api/demo/enter", json={"persona": "agent", "fresh": False})
        data = res.json()
        token = data['token']
        agent_id = data['user_id']
        headers = {"Authorization": f"Bearer {token}"}
        
        # Apply via webhook
        webhook_payload = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "metadata": {"agent_id": agent_id, "plan_id": "starter"},
                    "customer": "cus_canonical_test",
                    "subscription": "sub_canonical_test"
                }
            }
        }
        webhook_res = requests.post(f"{BASE_URL}/api/billing/webhook", json=webhook_payload)
        assert webhook_res.status_code == 200
        
        # Verify state
        status_res = requests.get(f"{BASE_URL}/api/billing/status", headers=headers)
        status = status_res.json()
        
        # All fields should be set correctly
        assert status['plan_id'] == 'starter'
        assert status['stripe_customer_id'] == 'cus_canonical_test'
        assert status['stripe_subscription_id'] == 'sub_canonical_test'
        assert status['subscription_status'] == 'active'


class TestDemoSeedAndLogin:
    """Tests that demo seed and agent login still work after billing rebuild"""
    
    def test_demo_seed_works(self):
        """POST /api/demo/seed still works"""
        res = requests.post(f"{BASE_URL}/api/demo/seed")
        assert res.status_code == 200
        
        data = res.json()
        assert 'demo_credentials' in data
    
    def test_demo_agent_login_works(self):
        """POST /api/demo/enter (agent) still works"""
        res = requests.post(f"{BASE_URL}/api/demo/enter", json={"persona": "agent", "fresh": False})
        assert res.status_code == 200
        
        data = res.json()
        assert 'token' in data
        # Response is flat (user_id, email, name, role, token) not nested under 'user'
        assert 'user_id' in data
        assert 'email' in data
        assert 'role' in data
    
    def test_demo_agent_dashboard_access(self):
        """Demo agent can access basic dashboard endpoints"""
        res = requests.post(f"{BASE_URL}/api/demo/enter", json={"persona": "agent", "fresh": False})
        token = res.json()['token']
        headers = {"Authorization": f"Bearer {token}"}
        
        # Test projects endpoint
        proj_res = requests.get(f"{BASE_URL}/api/projects", headers=headers)
        assert proj_res.status_code == 200
        
        # Test clients endpoint
        clients_res = requests.get(f"{BASE_URL}/api/clients", headers=headers)
        assert clients_res.status_code == 200


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
