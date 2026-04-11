"""
Billing Routes — Thin layer over billing_service.

Routes only: validate, auth, delegate to service, return response.
No business logic. No direct DB writes. No Stripe SDK calls.
"""
import json
import logging

import stripe
from fastapi import APIRouter, HTTPException, Depends, Request

from core.auth import get_current_agent
from core.config import validate_config
from core.monitoring import capture_payment_error
from models.schemas import CreateCheckoutRequest, CheckoutStatusRequest
from services.billing_service import (
    BillingNotConfiguredError,
    get_all_plans,
    get_subscription_status,
    create_checkout_session,
    verify_checkout,
    handle_webhook_event,
    cancel_subscription,
    sync_subscription,
    create_billing_portal,
)

logger = logging.getLogger(__name__)

_config = validate_config()

router = APIRouter()


# ── Plans ──

@router.get("/billing/plans")
async def list_plans(user: dict = Depends(get_current_agent)):
    """Get all available subscription plans."""
    return get_all_plans()


# ── Subscription Status ──

@router.get("/billing/status")
async def billing_status(user: dict = Depends(get_current_agent)):
    """Get current subscription status for the agent."""
    return await get_subscription_status(user['user_id'])


# ── Checkout ──

@router.post("/billing/create-checkout-session")
async def checkout(data: CreateCheckoutRequest, user: dict = Depends(get_current_agent)):
    """Create a Stripe checkout session for a plan subscription."""
    try:
        return await create_checkout_session(user['user_id'], data.plan_id, data.origin_url)
    except BillingNotConfiguredError:
        raise HTTPException(status_code=500, detail="Stripe is not configured")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        capture_payment_error(e, user_id=user['user_id'], operation="create_checkout")
        logger.error(f"Checkout error: {e}")
        raise HTTPException(status_code=500, detail="Failed to create checkout session")


@router.post("/billing/verify-session")
async def verify_session(data: CheckoutStatusRequest, user: dict = Depends(get_current_agent)):
    """Verify a checkout session. Reconciliation path."""
    try:
        return await verify_checkout(user['user_id'], data.session_id)
    except BillingNotConfiguredError:
        raise HTTPException(status_code=500, detail="Stripe is not configured")
    except Exception as e:
        logger.error(f"Session verify error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to verify session: {e}")


# ── Webhook ──

@router.post("/billing/webhook")
async def webhook(request: Request):
    """
    Handle Stripe webhook events. PRIMARY truth authority.
    Verifies signature when STRIPE_WEBHOOK_SECRET is configured.
    """
    payload = await request.body()

    # Signature verification (mandatory when secret is configured)
    if _config.STRIPE_WEBHOOK_SECRET:
        sig_header = request.headers.get('stripe-signature', '')
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, _config.STRIPE_WEBHOOK_SECRET,
            )
            event_type = event['type']
            event_data = event
        except stripe.error.SignatureVerificationError:
            logger.warning("Webhook signature verification failed")
            raise HTTPException(status_code=400, detail="Invalid signature")
        except Exception as e:
            logger.error(f"Webhook construction error: {e}")
            raise HTTPException(status_code=400, detail="Invalid payload")
    else:
        # No secret configured — parse raw (development/testing only)
        try:
            event_data = json.loads(payload)
            event_type = event_data.get('type', '')
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON")

    logger.info(f"Webhook received: {event_type}")

    try:
        result = await handle_webhook_event(event_type, event_data)
        return {"received": True, **result}
    except Exception as e:
        capture_payment_error(e, operation="webhook_processing")
        logger.error(f"Webhook processing error: {e}")
        raise HTTPException(status_code=400, detail="Webhook processing failed")


# ── Cancel ──

@router.post("/billing/cancel")
async def cancel(user: dict = Depends(get_current_agent)):
    """Cancel subscription at period end."""
    try:
        return await cancel_subscription(user['user_id'])
    except BillingNotConfiguredError:
        raise HTTPException(status_code=500, detail="Stripe is not configured")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        capture_payment_error(e, user_id=user['user_id'], operation="cancel")
        logger.error(f"Cancel error: {e}")
        raise HTTPException(status_code=500, detail="Failed to cancel subscription")


# ── Sync ──

@router.post("/billing/sync")
async def sync(user: dict = Depends(get_current_agent)):
    """Sync local subscription state from Stripe. Recovery path."""
    try:
        return await sync_subscription(user['user_id'])
    except BillingNotConfiguredError:
        raise HTTPException(status_code=500, detail="Stripe is not configured")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Sync error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to sync: {e}")


# ── Billing Portal ──

@router.post("/billing/portal")
async def portal(request: Request, user: dict = Depends(get_current_agent)):
    """Create a Stripe billing portal session for subscription management."""
    try:
        body = await request.json()
        return_url = body.get('return_url', '')
    except Exception:
        return_url = ''

    try:
        return await create_billing_portal(user['user_id'], return_url)
    except BillingNotConfiguredError:
        raise HTTPException(status_code=500, detail="Stripe is not configured")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Portal error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create billing portal: {e}")
