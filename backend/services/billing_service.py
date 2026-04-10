"""
Subscription/billing service - shared functions for subscription checks.
Extracted from billing routes for cross-module access.
"""
from database import db
from helpers import SUBSCRIPTION_PLANS


async def get_agent_unit_count(agent_id: str, is_demo: bool = False) -> int:
    """Count total units across all projects owned by an agent"""
    projects = await db.projects.find({
        "agent_id": agent_id,
        "is_demo": is_demo
    }, {"project_id": 1}).to_list(None)
    
    if not projects:
        return 0
    
    project_ids = [p['project_id'] for p in projects]
    
    total_units = await db.units.count_documents({
        "project_id": {"$in": project_ids},
        "is_demo": is_demo
    })
    
    if total_units == 0:
        total_units = len(projects)
    
    return total_units


async def get_agent_subscription_data(user: dict) -> dict:
    """Get subscription data for an agent from database"""
    agent_id = user['user_id']
    is_demo = user.get('is_demo', False)
    
    user_doc = await db.users.find_one({"user_id": agent_id}, {"_id": 0})
    
    plan_id = user_doc.get('subscription_plan', 'free') if user_doc else 'free'
    subscription_status = user_doc.get('subscription_status', 'active')
    
    plan = SUBSCRIPTION_PLANS.get(plan_id, SUBSCRIPTION_PLANS['free'])
    
    unit_count = await get_agent_unit_count(agent_id, is_demo)
    
    unit_limit = plan.get('property_limit')
    can_create = unit_limit is None or unit_count < unit_limit
    
    usage_percent = 0
    near_limit = False
    if unit_limit and unit_limit > 0:
        usage_percent = (unit_count / unit_limit) * 100
        near_limit = usage_percent >= 80 and can_create
    
    return {
        "plan_id": plan_id,
        "plan_name": plan['name'],
        "unit_limit": unit_limit,
        "unit_usage": unit_count,
        "property_limit": unit_limit,
        "property_usage": unit_count,
        "usage_percent": usage_percent,
        "near_limit": near_limit,
        "can_create_property": can_create and subscription_status == 'active',
        "can_create_unit": can_create and subscription_status == 'active',
        "stripe_subscription_id": user_doc.get('stripe_subscription_id') if user_doc else None,
        "stripe_customer_id": user_doc.get('stripe_customer_id') if user_doc else None,
        "subscription_status": subscription_status,
        "current_period_end": user_doc.get('subscription_period_end') if user_doc else None
    }
