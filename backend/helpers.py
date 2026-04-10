"""
Shared helper functions and constants for the Evohome API.
Extracted from server.py during Phase 3 modularization.
"""
import re
from core.config import validate_config

app_config = validate_config()


# ==================== FILE HELPERS ====================

def secure_filename(filename: str) -> str:
    """Sanitize filename to prevent path traversal attacks"""
    safe_chars = re.sub(r'[^\w\s\-\.]', '', filename)
    safe_chars = safe_chars.replace(' ', '_')
    return safe_chars[:100] if safe_chars else 'unnamed_file'


# ==================== DEMO FILTER HELPERS ====================

def get_demo_filter(user: dict) -> dict:
    """
    Get is_demo filter for queries during migration period.
    Production: filter by user's is_demo flag.
    Demo deployment (DEMO_MODE=true): no filter needed.
    """
    if app_config.DEMO_MODE:
        return {}
    else:
        return {"is_demo": user.get('is_demo', False)}


def build_query(user: dict, **filters) -> dict:
    """Build a query with proper ownership and demo isolation."""
    query = {**filters}
    if user.get('role') == 'agent' and 'agent_id' not in query:
        query['agent_id'] = user['user_id']
    query.update(get_demo_filter(user))
    return query


# ==================== DOCUMENT STATE MACHINE ====================

VALID_TRANSITIONS = {
    "quote": {
        "Draft": ["Sent"],
        "Sent": ["Approved", "Rejected", "Change Requested"],
        "Change Requested": ["Sent"],
        "Approved": [],
        "Rejected": [],
    },
    "invoice": {
        "Draft": ["Sent"],
        "Sent": ["Paid", "Change Requested"],
        "Change Requested": ["Sent"],
        "Paid": [],
    }
}

def validate_transition(doc_type: str, current_status: str, new_status: str) -> bool:
    """Validate if a status transition is allowed"""
    allowed = VALID_TRANSITIONS.get(doc_type, {}).get(current_status, [])
    return new_status in allowed


# ==================== SUBSCRIPTION PLANS ====================

SUBSCRIPTION_PLANS = {
    "free": {
        "name": "Free",
        "price": 0.0,
        "currency": "CHF",
        "property_limit": 2,
        "features": [
            "Up to 2 units",
            "Client communication",
            "Document management",
            "Basic timeline tracking"
        ]
    },
    "starter": {
        "name": "Starter",
        "price": 29.0,
        "currency": "CHF",
        "property_limit": 10,
        "features": [
            "Manage up to 10 units",
            "Full client tracking & communication",
            "Quote & invoice management",
            "Email support"
        ]
    },
    "pro": {
        "name": "Pro",
        "price": 79.0,
        "currency": "CHF",
        "property_limit": 50,
        "features": [
            "Scale to 50 units",
            "Priority support",
            "Advanced workflow templates",
            "Team collaboration",
            "Custom branding & logo"
        ]
    },
    "enterprise": {
        "name": "Enterprise",
        "price": None,
        "currency": "CHF",
        "property_limit": None,
        "features": [
            "Unlimited units",
            "Custom workflows",
            "Dedicated account manager",
            "API access & integrations"
        ]
    }
}


# ==================== VAULT CONSTANTS ====================

VAULT_CATEGORIES = ["Contracts", "Plans", "Permits", "Reports", "Other"]
VAULT_DOC_TYPES = ["general", "action_required"]
