"""Auto-extracted route module from server.py — Phase 3 modularization."""
import os
import re
import json
import uuid
import base64
import logging
import secrets
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Optional, Literal, Dict, Any
from io import BytesIO

from fastapi import APIRouter, HTTPException, Depends, Request, Response, UploadFile, File, Form, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel, Field, EmailStr

from database import db
from core.auth import get_current_user, get_current_agent, get_current_buyer, verify_token
from core.access_control import can_access_project, can_access_client, can_access_vault_doc, can_access_document, get_accessible_project_ids, get_accessible_client_ids, is_agent, is_buyer, get_is_demo
from core.rate_limit import rate_limit_check, check_rate_limit
from core.monitoring import capture_exception, capture_auth_failure, capture_payment_error, capture_email_error, capture_ai_error, capture_websocket_error, capture_document_error, ErrorContext
from core.responses import AuthSessionResponse, AuthLoginResponse, AuthRefreshResponse, AuthLogoutResponse, DocumentResponse, VaultDocumentResponse, NotificationResponse, ActivityResponse, ActivitiesListResponse, SuccessResponse

from helpers import get_demo_filter, build_query, secure_filename, VALID_TRANSITIONS, validate_transition, SUBSCRIPTION_PLANS, VAULT_CATEGORIES, VAULT_DOC_TYPES
from services.email_service import send_email_async, send_notification_email, create_notification, get_email_template
from services.realtime_service import ws_manager, notify_realtime, send_milestone_notification
from services.qr_service import generate_swiss_qr_code, generate_swiss_qr_code_base64, DEFAULT_IBAN, DEFAULT_COMPANY_NAME
from services.ai_service import extract_document_from_pdf, OPENAI_API_KEY

from models.schemas import *

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).parent.parent
UPLOAD_DIR = ROOT_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

router = APIRouter()

# ==================== BILLING/SUBSCRIPTION ====================

# ==================== BILLING / SUBSCRIPTION ENDPOINTS ====================

STRIPE_API_KEY = os.environ.get('STRIPE_API_KEY', '')

from services.billing_service import get_agent_subscription_data, get_agent_unit_count

@router.get("/billing/plans")
async def get_available_plans(user: dict = Depends(get_current_agent)):
    """Get all available subscription plans"""
    plans = []
    for plan_id, plan_data in SUBSCRIPTION_PLANS.items():
        plans.append({
            "plan_id": plan_id,
            "name": plan_data['name'],
            "price": plan_data['price'],
            "currency": plan_data['currency'],
            "property_limit": plan_data['property_limit'],
            "features": plan_data['features'],
            "is_enterprise": plan_id == 'enterprise'
        })
    return plans

@router.get("/billing/status")
async def get_subscription_status(user: dict = Depends(get_current_agent)):
    """Get current subscription status for the agent"""
    return await get_agent_subscription_data(user)

@router.post("/billing/create-checkout-session")
async def create_checkout_session(data: CreateCheckoutRequest, user: dict = Depends(get_current_agent)):
    """Create a Stripe checkout session for subscribing to a plan"""
    if not STRIPE_API_KEY:
        raise HTTPException(status_code=500, detail="Stripe is not configured")
    
    plan_id = data.plan_id
    if plan_id not in SUBSCRIPTION_PLANS or plan_id in ['free', 'enterprise']:
        raise HTTPException(status_code=400, detail="Invalid plan selected")
    
    plan = SUBSCRIPTION_PLANS[plan_id]
    
    try:
        # Use Stripe SDK directly
        stripe.api_key = STRIPE_API_KEY
        
        # Amount in cents for Stripe
        amount_in_cents = int(plan['price'] * 100)
        
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'chf',
                    'unit_amount': amount_in_cents,
                    'product_data': {
                        'name': f"Evohome {plan['name']} Plan",
                        'description': f"Monthly subscription - {plan['property_limit']} units"
                    },
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=f"{data.origin_url}/agent/billing?session_id={{CHECKOUT_SESSION_ID}}&success=true",
            cancel_url=f"{data.origin_url}/agent/billing?canceled=true",
            metadata={
                "agent_id": user['user_id'],
                "plan_id": plan_id,
                "plan_name": plan['name']
            }
        )
        
        return {
            "checkout_url": session.url,
            "session_id": session.id
        }
        
    except Exception as e:
        # Capture Stripe errors for monitoring
        capture_payment_error(e, user_id=user['user_id'], operation="create_checkout")
        logger.error(f"Stripe checkout error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create checkout session. Please try again.")

@router.post("/billing/verify-session")
async def verify_checkout_session(data: CheckoutStatusRequest, user: dict = Depends(get_current_agent)):
    """Verify a checkout session and update subscription status"""
    if not STRIPE_API_KEY:
        raise HTTPException(status_code=500, detail="Stripe is not configured")
    
    try:
        # Use Stripe SDK directly
        stripe.api_key = STRIPE_API_KEY
        session = stripe.checkout.Session.retrieve(data.session_id)
        
        logger.info(f"Checkout status: {session.status}, payment: {session.payment_status}")
        
        if session.status == "complete" and session.payment_status == "paid":
            # Get plan_id from metadata (set during checkout creation)
            metadata = session.metadata or {}
            plan_id = metadata.get('plan_id', 'starter')
            
            # Fallback: determine plan from amount if metadata missing
            if not plan_id and session.amount_total:
                amount = session.amount_total / 100
                if amount >= 79:
                    plan_id = "pro"
                elif amount >= 29:
                    plan_id = "starter"
                else:
                    plan_id = "free"
            
            # Update user's subscription in database
            update_data = {
                "subscription_plan": plan_id,
                "subscription_status": "active",
                "subscription_updated_at": datetime.now(timezone.utc).isoformat()
            }
            
            # Store session ID for reference
            update_data["last_checkout_session"] = data.session_id
            
            await db.users.update_one(
                {"user_id": user['user_id']},
                {"$set": update_data}
            )
            
            logger.info(f"Subscription updated for {user['user_id']}: plan={plan_id}")
            
            return {
                "success": True,
                "plan_id": plan_id,
                "subscription_status": "active"
            }
        else:
            return {
                "success": False,
                "status": session.status,
                "payment_status": session.payment_status
            }
            
    except Exception as e:
        logger.error(f"Stripe session verification error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to verify session: {str(e)}")

@router.post("/billing/webhook")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events for subscription updates"""
    if not STRIPE_API_KEY:
        raise HTTPException(status_code=500, detail="Stripe is not configured")
    
    try:
        payload = await request.body()
        event_data = json.loads(payload)
        event_type = event_data.get('type', '')
        
        logger.info(f"Received Stripe webhook: {event_type}")
        
        if event_type == 'checkout.session.completed':
            session = event_data.get('data', {}).get('object', {})
            metadata = session.get('metadata', {})
            agent_id = metadata.get('agent_id')
            plan_id = metadata.get('plan_id', 'starter')
            
            if agent_id:
                await db.users.update_one(
                    {"user_id": agent_id},
                    {"$set": {
                        "stripe_customer_id": session.get('customer'),
                        "stripe_subscription_id": session.get('subscription'),
                        "subscription_plan": plan_id,
                        "subscription_status": "active"
                    }}
                )
                logger.info(f"Updated subscription for agent {agent_id} to plan {plan_id}")
        
        elif event_type == 'customer.subscription.updated':
            subscription = event_data.get('data', {}).get('object', {})
            customer_id = subscription.get('customer')
            status = subscription.get('status')
            
            # Find user by customer ID and update status
            await db.users.update_many(
                {"stripe_customer_id": customer_id},
                {"$set": {
                    "subscription_status": status,
                    "subscription_period_end": subscription.get('current_period_end')
                }}
            )
            logger.info(f"Updated subscription status to {status} for customer {customer_id}")
        
        elif event_type == 'customer.subscription.deleted':
            subscription = event_data.get('data', {}).get('object', {})
            customer_id = subscription.get('customer')
            
            # Downgrade to free plan
            await db.users.update_many(
                {"stripe_customer_id": customer_id},
                {"$set": {
                    "subscription_plan": "free",
                    "subscription_status": "canceled",
                    "stripe_subscription_id": None
                }}
            )
            logger.info(f"Subscription canceled for customer {customer_id}, downgraded to free")
        
        elif event_type == 'invoice.payment_failed':
            invoice = event_data.get('data', {}).get('object', {})
            customer_id = invoice.get('customer')
            
            await db.users.update_many(
                {"stripe_customer_id": customer_id},
                {"$set": {"subscription_status": "past_due"}}
            )
            logger.info(f"Payment failed for customer {customer_id}")
        
        return {"received": True}
        
    except Exception as e:
        # Capture webhook errors for monitoring
        capture_payment_error(e, operation="webhook_processing")
        logger.error(f"Webhook processing error: {str(e)}")
        raise HTTPException(status_code=400, detail="Webhook processing failed")

@router.post("/billing/cancel")
async def cancel_subscription(user: dict = Depends(get_current_agent)):
    """Cancel the current subscription (keeps active until period end)"""
    user_doc = await db.users.find_one({"user_id": user['user_id']}, {"_id": 0})
    
    if not user_doc or not user_doc.get('stripe_subscription_id'):
        raise HTTPException(status_code=400, detail="No active subscription found")
    
    # Note: In production, you would call Stripe API to cancel
    # For now, we'll mark it as canceled locally
    await db.users.update_one(
        {"user_id": user['user_id']},
        {"$set": {"subscription_status": "canceling"}}
    )
    
    return {"message": "Subscription will be canceled at period end"}

@router.post("/billing/sync")
async def sync_subscription_from_stripe(user: dict = Depends(get_current_agent)):
    """Sync subscription status - re-verify the last checkout session"""
    if not STRIPE_API_KEY:
        raise HTTPException(status_code=500, detail="Stripe is not configured")
    
    user_doc = await db.users.find_one({"user_id": user['user_id']}, {"_id": 0})
    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found")
    
    last_session = user_doc.get('last_checkout_session')
    
    if not last_session:
        # No checkout session found - check if they have a plan already
        current_plan = user_doc.get('subscription_plan', 'free')
        return {
            "message": "No checkout session to sync",
            "synced": False,
            "current_plan": current_plan
        }
    
    try:
        # Use Stripe SDK directly
        stripe.api_key = STRIPE_API_KEY
        session = stripe.checkout.Session.retrieve(last_session)
        
        logger.info(f"Sync - Checkout status for {user['user_id']}: {session.status}, payment: {session.payment_status}")
        
        if session.status == "complete" and session.payment_status == "paid":
            # Get plan_id from metadata
            metadata = session.metadata or {}
            plan_id = metadata.get('plan_id')
            
            # Fallback: determine plan from amount
            if not plan_id and session.amount_total:
                amount = session.amount_total / 100
                if amount >= 79:
                    plan_id = "pro"
                elif amount >= 29:
                    plan_id = "starter"
                else:
                    plan_id = "free"
            
            if not plan_id:
                plan_id = "starter"  # Default
            
            # Update subscription
            update_data = {
                "subscription_plan": plan_id,
                "subscription_status": "active",
                "subscription_updated_at": datetime.now(timezone.utc).isoformat()
            }
            
            await db.users.update_one(
                {"user_id": user['user_id']},
                {"$set": update_data}
            )
            
            logger.info(f"Synced subscription for {user['user_id']}: plan={plan_id}")
            
            return {
                "message": "Subscription synced successfully",
                "synced": True,
                "plan_id": plan_id,
                "status": "active"
            }
        else:
            return {
                "message": f"Checkout session not complete (status: {session.status}, payment: {session.payment_status})",
                "synced": False,
                "current_plan": user_doc.get('subscription_plan', 'free')
            }
            
    except Exception as e:
        logger.error(f"Failed to sync subscription: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to sync: {str(e)}")

@router.post("/billing/portal")
async def create_billing_portal(request: Request, user: dict = Depends(get_current_agent)):
    """Create a Stripe billing portal session for subscription management"""
    if not STRIPE_API_KEY:
        raise HTTPException(status_code=500, detail="Stripe is not configured")
    
    user_doc = await db.users.find_one({"user_id": user['user_id']}, {"_id": 0})
    
    if not user_doc or not user_doc.get('stripe_customer_id'):
        raise HTTPException(status_code=400, detail="No Stripe customer found. Please subscribe first.")
    
    try:
        # Get the return URL from request body
        body = await request.json()
        return_url = body.get('return_url', '')
        
        # Use Stripe API directly for billing portal (emergentintegrations may not have this)
        import stripe
        stripe.api_key = STRIPE_API_KEY
        
        portal_session = stripe.billing_portal.Session.create(
            customer=user_doc['stripe_customer_id'],
            return_url=return_url or f"{os.environ.get('FRONTEND_URL', '')}/agent/billing"
        )
        
        return {
            "portal_url": portal_session.url
        }
        
    except Exception as e:
        logger.error(f"Billing portal error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create billing portal: {str(e)}")


