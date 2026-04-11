"""
Billing Service — Canonical Single Source of Truth.

Owns ALL subscription state transitions, Stripe orchestration,
webhook event application, cancellation, sync, and entitlement checks.

Domain Model:
  Plan         — Static config from helpers.SUBSCRIPTION_PLANS. Immutable.
  Subscription — Local projection of Stripe state on users collection.
  Entitlement  — Computed from Plan + Subscription. Never stored.

Truth Hierarchy:
  Stripe webhook         = PRIMARY authority for subscription state
  verify-session / sync  = Recovery/reconciliation (calls same canonical updater)
  Local DB               = Projection of Stripe truth
"""
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

import stripe

from database import db
from core.config import validate_config
from helpers import SUBSCRIPTION_PLANS

logger = logging.getLogger(__name__)

_config = validate_config()

# Sentinel to distinguish "not provided" from "explicitly set to None"
_UNSET = object()


# ── Plan Lookup ──

def get_plan(plan_id: str) -> Dict[str, Any]:
    """Get plan definition by ID. Falls back to free."""
    return SUBSCRIPTION_PLANS.get(plan_id, SUBSCRIPTION_PLANS['free'])


def get_all_plans() -> list:
    """Get all available plans formatted for API response."""
    return [
        {
            "plan_id": pid,
            "name": p['name'],
            "price": p['price'],
            "currency": p['currency'],
            "property_limit": p['property_limit'],
            "features": p['features'],
            "is_enterprise": pid == 'enterprise',
        }
        for pid, p in SUBSCRIPTION_PLANS.items()
    ]


# ── Canonical Subscription Mutation ──
# This is the ONE path that writes subscription state.
# Webhook, verify-session, and sync all converge here.

async def apply_subscription_update(
    agent_id: str,
    *,
    plan_id=_UNSET,
    status=_UNSET,
    stripe_customer_id=_UNSET,
    stripe_subscription_id=_UNSET,
    period_end=_UNSET,
) -> Dict[str, Any]:
    """
    Single canonical mutation path for subscription state.

    Uses _UNSET sentinel to distinguish "not provided" from "explicitly set to None".
    Only sets fields that are explicitly provided (not _UNSET).
    """
    update: Dict[str, Any] = {
        "subscription_updated_at": datetime.now(timezone.utc).isoformat(),
    }

    if plan_id is not _UNSET:
        update["subscription_plan"] = plan_id
    if status is not _UNSET:
        update["subscription_status"] = status
    if stripe_customer_id is not _UNSET:
        update["stripe_customer_id"] = stripe_customer_id
    if stripe_subscription_id is not _UNSET:
        update["stripe_subscription_id"] = stripe_subscription_id
    if period_end is not _UNSET:
        update["subscription_period_end"] = period_end

    await db.users.update_one(
        {"user_id": agent_id},
        {"$set": update},
    )

    logger.info(f"Subscription updated for {agent_id}: {update}")
    return update


# ── Entitlement Checks ──

async def get_agent_unit_count(agent_id: str) -> int:
    """Count total units owned by an agent."""
    return await db.units.count_documents({"agent_id": agent_id})


async def get_subscription_status(agent_id: str) -> Dict[str, Any]:
    """Get full subscription status for an agent."""
    user_doc = await db.users.find_one({"user_id": agent_id}, {"_id": 0})
    plan_id = user_doc.get('subscription_plan', 'free') if user_doc else 'free'
    plan = get_plan(plan_id)
    unit_count = await get_agent_unit_count(agent_id)
    prop_limit = plan['property_limit']

    return {
        "plan_id": plan_id,
        "plan_name": plan['name'],
        "property_limit": prop_limit,
        "unit_usage": unit_count,
        "can_create_unit": (prop_limit is None) or (unit_count < prop_limit),
        "subscription_status": user_doc.get('subscription_status', 'active') if user_doc else 'active',
        "current_period_end": user_doc.get('subscription_period_end') if user_doc else None,
        "stripe_subscription_id": user_doc.get('stripe_subscription_id') if user_doc else None,
        "stripe_customer_id": user_doc.get('stripe_customer_id') if user_doc else None,
    }


async def can_create_unit(agent_id: str) -> bool:
    """Check if agent can create another unit under their plan."""
    status = await get_subscription_status(agent_id)
    return status['can_create_unit']


async def get_unit_limit(agent_id: str) -> Optional[int]:
    """Get the unit limit for an agent's current plan. None = unlimited."""
    status = await get_subscription_status(agent_id)
    return status['property_limit']


# ── Stripe Orchestration ──

def _ensure_stripe():
    """Configure Stripe SDK. Raises if not configured."""
    if not _config.billing_enabled:
        raise BillingNotConfiguredError()
    stripe.api_key = _config.STRIPE_API_KEY


class BillingNotConfiguredError(Exception):
    pass


async def create_checkout_session(
    agent_id: str,
    plan_id: str,
    origin_url: str,
) -> Dict[str, str]:
    """Create a Stripe Checkout session for a plan subscription."""
    _ensure_stripe()

    if plan_id not in SUBSCRIPTION_PLANS or plan_id in ('free', 'enterprise'):
        raise ValueError(f"Invalid plan: {plan_id}")

    plan = SUBSCRIPTION_PLANS[plan_id]
    amount_cents = int(plan['price'] * 100)

    session = stripe.checkout.Session.create(
        payment_method_types=['card'],
        line_items=[{
            'price_data': {
                'currency': 'chf',
                'unit_amount': amount_cents,
                'recurring': {'interval': 'month'},
                'product_data': {
                    'name': f"Evohome {plan['name']} Plan",
                    'description': f"Monthly subscription - {plan['property_limit']} units",
                },
            },
            'quantity': 1,
        }],
        mode='subscription',
        success_url=f"{origin_url}/agent/billing?session_id={{CHECKOUT_SESSION_ID}}&success=true",
        cancel_url=f"{origin_url}/agent/billing?canceled=true",
        metadata={"agent_id": agent_id, "plan_id": plan_id},
        subscription_data={"metadata": {"agent_id": agent_id, "plan_id": plan_id}},
    )

    # Store session reference for sync/recovery
    await db.users.update_one(
        {"user_id": agent_id},
        {"$set": {"last_checkout_session": session.id}},
    )

    return {"checkout_url": session.url, "session_id": session.id}


async def verify_checkout(agent_id: str, session_id: str) -> Dict[str, Any]:
    """
    Verify a checkout session. Recovery/reconciliation path.
    Calls the same canonical updater as webhook.
    """
    _ensure_stripe()

    session = stripe.checkout.Session.retrieve(session_id)
    logger.info(f"Verify checkout for {agent_id}: status={session.status}, payment={session.payment_status}")

    if session.status != "complete" or session.payment_status != "paid":
        return {
            "success": False,
            "status": session.status,
            "payment_status": session.payment_status,
        }

    plan_id = _resolve_plan_from_session(session)

    await apply_subscription_update(
        agent_id,
        plan_id=plan_id,
        status="active",
        stripe_customer_id=session.customer if session.customer else None,
        stripe_subscription_id=session.subscription if session.subscription else None,
    )

    return {"success": True, "plan_id": plan_id, "subscription_status": "active"}


async def handle_webhook_event(event_type: str, event_data: dict) -> Dict[str, Any]:
    """
    Process a Stripe webhook event. PRIMARY truth authority.
    Dispatches to the canonical updater.
    """
    obj = event_data.get('data', {}).get('object', {})

    if event_type == 'checkout.session.completed':
        return await _handle_checkout_completed(obj)
    elif event_type == 'customer.subscription.updated':
        return await _handle_subscription_updated(obj)
    elif event_type == 'customer.subscription.deleted':
        return await _handle_subscription_deleted(obj)
    elif event_type == 'invoice.payment_failed':
        return await _handle_payment_failed(obj)
    else:
        logger.info(f"Unhandled webhook event: {event_type}")
        return {"handled": False, "event_type": event_type}


async def cancel_subscription(agent_id: str) -> Dict[str, Any]:
    """
    Cancel subscription at period end via Stripe API.
    Actual downgrade happens when webhook fires customer.subscription.deleted.
    """
    _ensure_stripe()

    user_doc = await db.users.find_one({"user_id": agent_id}, {"_id": 0})
    sub_id = user_doc.get('stripe_subscription_id') if user_doc else None

    if not sub_id:
        raise ValueError("No active subscription found")

    # Tell Stripe to cancel at period end (not immediately)
    subscription = stripe.Subscription.modify(
        sub_id,
        cancel_at_period_end=True,
    )

    await apply_subscription_update(
        agent_id,
        status="canceling",
        period_end=subscription.current_period_end,
    )

    return {"message": "Subscription will be canceled at period end"}


async def sync_subscription(agent_id: str) -> Dict[str, Any]:
    """
    Sync local state from Stripe. Recovery/reconciliation path.
    Tries subscription first, falls back to last checkout session.
    """
    _ensure_stripe()

    user_doc = await db.users.find_one({"user_id": agent_id}, {"_id": 0})
    if not user_doc:
        raise ValueError("User not found")

    # Try subscription ID first (most authoritative)
    sub_id = user_doc.get('stripe_subscription_id')
    if sub_id:
        try:
            subscription = stripe.Subscription.retrieve(sub_id)
            plan_id = subscription.metadata.get('plan_id')
            if not plan_id:
                plan_id = _resolve_plan_from_amount(subscription.plan.amount / 100 if subscription.plan else 0)

            await apply_subscription_update(
                agent_id,
                plan_id=plan_id,
                status=subscription.status,
                period_end=subscription.current_period_end,
            )

            return {"synced": True, "source": "subscription", "plan_id": plan_id, "status": subscription.status}
        except stripe.error.InvalidRequestError:
            logger.warning(f"Subscription {sub_id} not found in Stripe for {agent_id}")

    # Fallback: last checkout session
    last_session = user_doc.get('last_checkout_session')
    if not last_session:
        return {
            "synced": False,
            "message": "No Stripe reference to sync from",
            "current_plan": user_doc.get('subscription_plan', 'free'),
        }

    session = stripe.checkout.Session.retrieve(last_session)
    if session.status == "complete" and session.payment_status == "paid":
        plan_id = _resolve_plan_from_session(session)
        await apply_subscription_update(agent_id, plan_id=plan_id, status="active")
        return {"synced": True, "source": "checkout_session", "plan_id": plan_id, "status": "active"}

    return {
        "synced": False,
        "message": f"Session not complete (status: {session.status})",
        "current_plan": user_doc.get('subscription_plan', 'free'),
    }


async def create_billing_portal(agent_id: str, return_url: str) -> Dict[str, str]:
    """Create a Stripe Billing Portal session."""
    _ensure_stripe()

    user_doc = await db.users.find_one({"user_id": agent_id}, {"_id": 0})
    customer_id = user_doc.get('stripe_customer_id') if user_doc else None

    if not customer_id:
        raise ValueError("No Stripe customer found. Subscribe first.")

    portal = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=return_url or f"{_config.FRONTEND_URL}/agent/billing",
    )

    return {"portal_url": portal.url}


# ── Internal Helpers ──

def _resolve_plan_from_session(session) -> str:
    """Extract plan_id from Stripe session metadata, with amount fallback."""
    metadata = session.metadata or {}
    plan_id = metadata.get('plan_id')
    if plan_id and plan_id in SUBSCRIPTION_PLANS:
        return plan_id

    # Fallback: derive from amount
    if session.amount_total:
        return _resolve_plan_from_amount(session.amount_total / 100)

    return 'starter'


def _resolve_plan_from_amount(amount: float) -> str:
    """Derive plan from CHF amount. Last resort fallback."""
    if amount >= 79:
        return 'pro'
    elif amount >= 29:
        return 'starter'
    return 'free'


async def _handle_checkout_completed(session: dict) -> Dict[str, Any]:
    """Handle checkout.session.completed webhook."""
    metadata = session.get('metadata', {})
    agent_id = metadata.get('agent_id')
    if not agent_id:
        logger.warning("checkout.session.completed without agent_id in metadata")
        return {"handled": False, "reason": "missing agent_id"}

    plan_id = metadata.get('plan_id', 'starter')

    await apply_subscription_update(
        agent_id,
        plan_id=plan_id,
        status="active",
        stripe_customer_id=session.get('customer'),
        stripe_subscription_id=session.get('subscription'),
    )

    return {"handled": True, "agent_id": agent_id, "plan_id": plan_id}


async def _handle_subscription_updated(subscription: dict) -> Dict[str, Any]:
    """Handle customer.subscription.updated webhook."""
    customer_id = subscription.get('customer')
    status = subscription.get('status')

    if not customer_id:
        return {"handled": False, "reason": "missing customer_id"}

    update_kwargs = {"status": status}
    period_end = subscription.get('current_period_end')
    if period_end is not None:
        update_kwargs["period_end"] = period_end

    # Resolve plan from metadata if available
    metadata = subscription.get('metadata', {})
    plan_id = metadata.get('plan_id')
    if plan_id:
        update_kwargs["plan_id"] = plan_id

    # Find agent by customer_id and apply
    user = await db.users.find_one({"stripe_customer_id": customer_id}, {"_id": 0, "user_id": 1})
    if user:
        await apply_subscription_update(user['user_id'], **update_kwargs)
        return {"handled": True, "customer_id": customer_id, "status": status}

    logger.warning(f"No user found for stripe_customer_id={customer_id}")
    return {"handled": False, "reason": "customer_not_found"}


async def _handle_subscription_deleted(subscription: dict) -> Dict[str, Any]:
    """
    Handle customer.subscription.deleted webhook.
    This fires on: cancellation, expiration, incomplete lifecycle end.
    Always downgrades to free.
    """
    customer_id = subscription.get('customer')
    if not customer_id:
        return {"handled": False, "reason": "missing customer_id"}

    user = await db.users.find_one({"stripe_customer_id": customer_id}, {"_id": 0, "user_id": 1})
    if user:
        await apply_subscription_update(
            user['user_id'],
            plan_id="free",
            status="canceled",
            stripe_subscription_id=None,
        )
        return {"handled": True, "customer_id": customer_id, "action": "downgraded_to_free"}

    logger.warning(f"No user found for stripe_customer_id={customer_id}")
    return {"handled": False, "reason": "customer_not_found"}


async def _handle_payment_failed(invoice: dict) -> Dict[str, Any]:
    """Handle invoice.payment_failed webhook."""
    customer_id = invoice.get('customer')
    if not customer_id:
        return {"handled": False, "reason": "missing customer_id"}

    user = await db.users.find_one({"stripe_customer_id": customer_id}, {"_id": 0, "user_id": 1})
    if user:
        await apply_subscription_update(user['user_id'], status="past_due")
        return {"handled": True, "customer_id": customer_id, "status": "past_due"}

    logger.warning(f"No user found for stripe_customer_id={customer_id}")
    return {"handled": False, "reason": "customer_not_found"}
