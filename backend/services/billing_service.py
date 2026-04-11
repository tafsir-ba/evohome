"""
Billing Service — Canonical Implementation

Subscription data and unit count for billing limit checks.
No is_demo.
"""
import logging
from typing import Dict, Any

from database import db
from helpers import SUBSCRIPTION_PLANS

logger = logging.getLogger(__name__)


async def get_agent_unit_count(agent_id: str) -> int:
    """Count total units owned by an agent."""
    return await db.units.count_documents({"agent_id": agent_id})


async def get_agent_subscription_data(user: Dict[str, Any]) -> Dict[str, Any]:
    """Get subscription data for billing limit checks."""
    agent_id = user['user_id']

    user_doc = await db.users.find_one({"user_id": agent_id}, {"_id": 0})
    plan_id = user_doc.get('subscription_plan', 'free') if user_doc else 'free'
    plan = SUBSCRIPTION_PLANS.get(plan_id, SUBSCRIPTION_PLANS['free'])

    unit_count = await get_agent_unit_count(agent_id)

    return {
        "plan_id": plan_id,
        "plan_name": plan['name'],
        "property_limit": plan['property_limit'],
        "current_unit_count": unit_count,
        "subscription_status": user_doc.get('subscription_status', 'active') if user_doc else 'active',
        "subscription_period_end": user_doc.get('subscription_period_end') if user_doc else None,
        # Compatibility fields for unrebuilt routes (removed after Phase 1)
        "unit_limit": plan['property_limit'],
        "unit_usage": unit_count,
        "can_create_unit": unit_count < plan['property_limit'],
    }
