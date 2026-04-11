"""
Authentication Module - Centralized auth logic
Extracted from server.py to provide:
- JWT token creation/verification
- Session management with refresh tokens
- Proper logout with token invalidation
- User retrieval scoped by ownership (agent_id / buyer_id)
"""

import os
import jwt
import secrets
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from fastapi import Request, HTTPException, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
ROOT_DIR = Path(__file__).parent.parent
load_dotenv(ROOT_DIR / '.env')

logger = logging.getLogger(__name__)

# JWT Configuration - MUST be set in environment for production
JWT_SECRET = os.environ.get('JWT_SECRET')
if not JWT_SECRET:
    logger.warning("JWT_SECRET not set in environment! Generating temporary secret.")
    JWT_SECRET = secrets.token_urlsafe(32)

JWT_ALGORITHM = 'HS256'
JWT_EXPIRY_HOURS = 24  # Shorter expiry, use refresh tokens for longer sessions
JWT_EXPIRY_DAYS = 7    # Cookie max-age for session persistence
REFRESH_TOKEN_EXPIRY_DAYS = 30

# Database reference - set by main app
_db: Optional[AsyncIOMotorDatabase] = None

def init_auth(db: AsyncIOMotorDatabase):
    """Initialize auth module with database reference"""
    global _db
    _db = db
    logger.info("Auth module initialized with database")

def get_db() -> AsyncIOMotorDatabase:
    """Get database reference"""
    if _db is None:
        raise RuntimeError("Auth module not initialized. Call init_auth(db) first.")
    return _db


# ==================== TOKEN MANAGEMENT ====================

def create_access_token(user_id: str, role: str) -> str:
    """Create a short-lived access token."""
    payload = {
        'user_id': user_id,
        'role': role,
        'type': 'access',
        'jti': secrets.token_urlsafe(16),  # Unique token ID for revocation
        'exp': datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRY_HOURS),
        'iat': datetime.now(timezone.utc)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    """
    Create a long-lived refresh token.
    Used to get new access tokens without re-login.
    """
    payload = {
        'user_id': user_id,
        'type': 'refresh',
        'exp': datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRY_DAYS),
        'iat': datetime.now(timezone.utc),
        'jti': secrets.token_urlsafe(16)  # Unique token ID for revocation
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_token(token: str, expected_type: str = 'access') -> Dict[str, Any]:
    """
    Verify and decode a JWT token.
    Returns payload if valid, raises HTTPException if invalid.
    
    NOTE: For backward compatibility, tokens without a 'type' field 
    are treated as 'access' tokens. This allows migration from old tokens.
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        
        # Backward compatibility: treat tokens without 'type' as 'access'
        token_type = payload.get('type', 'access')
        if token_type != expected_type:
            raise HTTPException(
                status_code=401, 
                detail=f"Invalid token type. Expected {expected_type}."
            )
        
        return payload
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired. Please login again.")
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid token: {e}")
        raise HTTPException(status_code=401, detail="Invalid token. Please login again.")


# ==================== TOKEN EXTRACTION ====================

def extract_token(request: Request) -> Optional[str]:
    """
    Extract token from request.
    Priority: Cookie > Authorization header
    """
    # Try cookie first (web clients)
    token = request.cookies.get('session_token')
    if token:
        return token
    
    # Try Authorization header (API clients, mobile)
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        return auth_header[7:]
    
    return None


# ==================== USER RETRIEVAL ====================

async def get_current_user(request: Request) -> Dict[str, Any]:
    """Get current authenticated user from DB by token."""
    token = extract_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated. Please login.")
    
    # Check if token has been invalidated (logged out)
    if is_token_invalidated(token):
        raise HTTPException(status_code=401, detail="Session has been invalidated. Please login again.")
    
    payload = verify_token(token, 'access')
    
    db = get_db()
    user = await db.users.find_one(
        {"user_id": payload['user_id']}, 
        {"_id": 0}
    )
    
    if not user:
        raise HTTPException(status_code=401, detail="User not found. Please login again.")
    
    return user


async def get_current_agent(request: Request) -> Dict[str, Any]:
    """Get current user and verify they are an agent"""
    user = await get_current_user(request)
    if user.get('role') != 'agent':
        raise HTTPException(status_code=403, detail="Agent access required")
    return user


async def get_current_buyer(request: Request) -> Dict[str, Any]:
    """Get current user and verify they are a buyer"""
    user = await get_current_user(request)
    if user.get('role') != 'buyer':
        raise HTTPException(status_code=403, detail="Buyer access required")
    return user


# ==================== SESSION INVALIDATION ====================

# In-memory blacklist for invalidated tokens (for MVP)
# In production, use Redis or database
_invalidated_tokens: set = set()

def invalidate_token(token: str):
    """Add token to blacklist"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM], options={"verify_exp": False})
        jti = payload.get('jti') or payload.get('user_id') + str(payload.get('iat', ''))
        _invalidated_tokens.add(jti)
        logger.info(f"Token invalidated: {jti[:20]}...")
    except Exception:
        pass  # Invalid token, no need to blacklist


def is_token_invalidated(token: str) -> bool:
    """Check if token has been invalidated"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM], options={"verify_exp": False})
        jti = payload.get('jti') or payload.get('user_id') + str(payload.get('iat', ''))
        return jti in _invalidated_tokens
    except Exception:
        return True  # Invalid token is effectively invalidated
