"""Auth routes — registration, login, OAuth, password reset, session management."""
import os
import uuid
import json
import secrets
import bcrypt
import jwt
import httpx
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, Depends, Request, Response
from pydantic import BaseModel, EmailStr
from typing import Optional
import logging

from database import db
from core.auth import (
    create_access_token, get_current_user,
    extract_token, invalidate_token, is_token_invalidated,
    JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRY_HOURS,
)
from core.rate_limit import rate_limit_check
from core.monitoring import capture_auth_failure
from services.email_service import send_notification_email, send_email_async
from core.config import get_config
from core.gantt_access import (
    GANTT_LOGIN_DENIED_MESSAGE,
    enforce_gantt_login_allowed,
    enforce_gantt_registration_closed,
    is_gantt_auth_request,
)
from core.gantt_site import GANTT_ORIGINS, gantt_welcome_email_data, is_gantt_request
from services.gantt_constants import GANTT_APP_NAME

logger = logging.getLogger("evohome.auth")


def _password_reset_frontend_url(req: Request) -> str:
    """Use request Origin when allowed (e.g. app.carib-recon.org), else FRONTEND_URL."""
    config = get_config()
    origin = (req.headers.get("origin") or "").strip().rstrip("/")
    allowed = {o.strip().rstrip("/") for o in config.CORS_ORIGINS if o and o != "*"}
    allowed.update(GANTT_ORIGINS)
    if config.FRONTEND_URL:
        allowed.add(config.FRONTEND_URL.strip().rstrip("/"))
    if origin in allowed:
        return origin
    if config.FRONTEND_URL:
        return config.FRONTEND_URL.strip().rstrip("/")
    return "https://app.evo-home.ch"

router = APIRouter()

# JWT config
JWT_EXPIRY_DAYS = 7

# Google OAuth
GOOGLE_CLIENT_ID = "1053944720664-ulkunc0n9qhvfq4cdntro2ks0lsru0p6.apps.googleusercontent.com"
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '')


# ---- helpers kept local (thin wrappers) ----

def verify_jwt_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


# ---- Pydantic request models ----

class AgentRegister(BaseModel):
    email: EmailStr
    password: str
    name: str

class AgentLogin(BaseModel):
    email: EmailStr
    password: str

class BuyerRegister(BaseModel):
    email: EmailStr
    password: str
    name: str
    invitation_code: Optional[str] = None

class BuyerLogin(BaseModel):
    email: EmailStr
    password: str

class ForgotPasswordRequest(BaseModel):
    email: str
    role: str

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

class SetPasswordRequest(BaseModel):
    email: str
    password: str
    role: str

class CheckEmailRequest(BaseModel):
    email: str
    role: str


# ---- response models (inline, tiny) ----

class AuthSessionResponse(BaseModel):
    authenticated: bool
    user: dict

class AuthLogoutResponse(BaseModel):
    success: bool
    message: str


# ======================= ENDPOINTS =======================

@router.post("/auth/register")
async def register_agent(data: AgentRegister, response: Response, request: Request):
    await rate_limit_check(request, "auth_register")
    enforce_gantt_registration_closed(request)
    existing = await db.users.find_one({"email": data.email, "role": "agent"}, {"_id": 0})

    if existing:
        if not existing.get('password_hash'):
            hashed_password = bcrypt.hashpw(data.password.encode('utf-8'), bcrypt.gensalt())
            await db.users.update_one(
                {"user_id": existing['user_id']},
                {"$set": {
                    "password_hash": hashed_password.decode('utf-8'),
                    "name": data.name if data.name else existing['name']
                }}
            )
            token = create_access_token(existing['user_id'], "agent")
            _set_session_cookie(response, token)
            return {
                "user_id": existing['user_id'], "email": data.email,
                "name": data.name if data.name else existing['name'],
                "role": "agent",
                "token": token, "account_linked": True,
                "message": "Password successfully added to your Google account. You can now login with email/password."
            }
        else:
            raise HTTPException(status_code=400, detail="An account with this email already exists. Please login instead, or use 'Forgot Password' to reset.")

    hashed_password = bcrypt.hashpw(data.password.encode('utf-8'), bcrypt.gensalt())
    user_id = f"agent_{uuid.uuid4().hex[:12]}"
    user_doc = {
        "user_id": user_id, "email": data.email, "name": data.name,
        "password_hash": hashed_password.decode('utf-8'),
        "role": "agent", "picture": None,
        "subscription_plan": "free", "subscription_status": "active",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.users.insert_one(user_doc)
    welcome_data = {
        "name": data.name,
        "role": "agent",
        "project_name": "your workspace",
    }
    welcome_data.update(gantt_welcome_email_data(request, data.name))
    await send_notification_email(
        "welcome_onboarding", data.email, welcome_data, request=request
    )
    token = create_access_token(user_id, "agent")
    _set_session_cookie(response, token)
    return {"user_id": user_id, "email": data.email, "name": data.name, "role": "agent", "token": token}


@router.post("/auth/login")
async def login_agent(data: AgentLogin, response: Response, request: Request):
    await rate_limit_check(request, "auth_login")
    enforce_gantt_login_allowed(request, data.email)
    user = await db.users.find_one({"email": data.email, "role": "agent"}, {"_id": 0})
    if not user:
        capture_auth_failure("invalid_credentials", email=data.email, request=request)
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if user.get("is_active", True) is False:
        raise HTTPException(status_code=403, detail="Account is deactivated. Contact your administrator.")
    if not user.get('password_hash'):
        capture_auth_failure("oauth_only_account", email=data.email, request=request)
        raise HTTPException(status_code=401, detail="This account was created with Google. Please login with Google, or create a password by clicking 'Create Account' with the same email.")
    if not bcrypt.checkpw(data.password.encode('utf-8'), user['password_hash'].encode('utf-8')):
        capture_auth_failure("wrong_password", email=data.email, request=request)
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token(user['user_id'], "agent")
    _set_session_cookie(response, token)
    return {"user_id": user['user_id'], "email": user['email'], "name": user['name'], "role": "agent", "token": token}


@router.post("/auth/buyer/register")
async def register_buyer(data: BuyerRegister, response: Response):
    existing = await db.users.find_one({"email": data.email, "role": "buyer"}, {"_id": 0})
    if existing:
        if not existing.get('password_hash'):
            hashed_password = bcrypt.hashpw(data.password.encode('utf-8'), bcrypt.gensalt())
            await db.users.update_one({"user_id": existing['user_id']}, {"$set": {"password_hash": hashed_password.decode('utf-8'), "name": data.name if data.name else existing['name']}})
            token = create_access_token(existing['user_id'], "buyer")
            _set_session_cookie(response, token)
            return {"user_id": existing['user_id'], "email": data.email, "name": data.name if data.name else existing['name'], "role": "buyer", "token": token, "account_linked": True, "message": "Password successfully added to your Google account. You can now login with email/password."}
        else:
            raise HTTPException(status_code=400, detail="An account with this email already exists. Please login instead, or use 'Forgot Password' to reset.")

    hashed_password = bcrypt.hashpw(data.password.encode('utf-8'), bcrypt.gensalt())
    user_id = f"buyer_{uuid.uuid4().hex[:12]}"
    user_doc = {"user_id": user_id, "email": data.email, "name": data.name, "password_hash": hashed_password.decode('utf-8'), "role": "buyer", "picture": None, "created_at": datetime.now(timezone.utc).isoformat()}
    await db.users.insert_one(user_doc)
    await db.clients.update_many({"email": data.email, "buyer_id": None}, {"$set": {"buyer_id": user_id}})
    await db.clients.update_many({"email": data.email, "buyer_id": {"$exists": False}}, {"$set": {"buyer_id": user_id}})
    if data.invitation_code:
        client = await db.clients.find_one({"invitation_code": data.invitation_code}, {"_id": 0})
        if client and not client.get('buyer_id'):
            await db.clients.update_one({"client_id": client['client_id']}, {"$set": {"buyer_id": user_id}})
    await send_notification_email("welcome_onboarding", data.email, {
        "name": data.name,
        "role": "buyer",
        "project_name": "your buyer dashboard",
    })
    logger.info(f"Buyer registered: {data.email} (user_id: {user_id})")
    token = create_access_token(user_id, "buyer")
    _set_session_cookie(response, token)
    return {"user_id": user_id, "email": data.email, "name": data.name, "role": "buyer", "token": token}


@router.post("/auth/buyer/login")
async def login_buyer(data: BuyerLogin, response: Response, request: Request):
    await rate_limit_check(request, "auth_login")
    user = await db.users.find_one({"email": data.email, "role": "buyer"}, {"_id": 0})
    if not user:
        capture_auth_failure("invalid_credentials", email=data.email, request=request)
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if user.get("is_active", True) is False:
        raise HTTPException(status_code=403, detail="Account is deactivated. Contact your administrator.")
    if not user.get('password_hash'):
        capture_auth_failure("oauth_only_account", email=data.email, request=request)
        raise HTTPException(status_code=401, detail="This account was created with Google. Please login with Google, or create a password by clicking 'Create Account' with the same email.")
    if not bcrypt.checkpw(data.password.encode('utf-8'), user['password_hash'].encode('utf-8')):
        capture_auth_failure("wrong_password", email=data.email, request=request)
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token(user['user_id'], "buyer")
    _set_session_cookie(response, token)
    return {"user_id": user['user_id'], "email": user['email'], "name": user['name'], "role": "buyer", "token": token}


@router.post("/auth/session")
async def exchange_session(request: Request, response: Response):
    body = await request.json()
    session_id = body.get('session_id')
    intended_role = body.get('intended_role')
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id required")

    OAUTH_BACKEND_URL = os.environ.get('OAUTH_BACKEND_URL', 'https://demobackend.emergentagent.com')
    async with httpx.AsyncClient() as client_http:
        try:
            resp = await client_http.get(f"{OAUTH_BACKEND_URL}/auth/v1/env/oauth/session-data", headers={"X-Session-ID": session_id})
            if resp.status_code != 200:
                raise HTTPException(status_code=401, detail="Invalid session")
            oauth_data = resp.json()
        except Exception as e:
            logger.error(f"OAuth exchange failed: {e}")
            raise HTTPException(status_code=401, detail="Authentication failed")

    email = oauth_data.get('email')
    existing_agent = await db.users.find_one({"email": email, "role": "agent"}, {"_id": 0})
    existing_buyer = await db.users.find_one({"email": email, "role": "buyer"}, {"_id": 0})
    client_link = await db.clients.find_one({"email": email}, {"_id": 0})

    user_id, role = await _resolve_oauth_role(intended_role, email, oauth_data, existing_agent, existing_buyer, client_link)

    token = create_access_token(user_id, role)
    _set_session_cookie(response, token)
    user = await db.users.find_one({"user_id": user_id}, {"_id": 0, "password_hash": 0})
    return {**user, "token": token}


@router.post("/auth/google/callback")
async def google_oauth_callback(request: Request, response: Response):
    body = await request.json()
    code = body.get('code')
    state = body.get('state', '{}')
    redirect_uri = body.get('redirect_uri')
    if not code:
        raise HTTPException(status_code=400, detail="Authorization code required")
    if not GOOGLE_CLIENT_SECRET:
        raise HTTPException(status_code=500, detail="Google OAuth not configured - missing client secret")

    try:
        state_data = json.loads(state)
        intended_role = state_data.get('role', 'buyer')
    except (json.JSONDecodeError, ValueError):
        intended_role = 'buyer'

    async with httpx.AsyncClient() as client_http:
        try:
            token_response = await client_http.post("https://oauth2.googleapis.com/token", data={"code": code, "client_id": GOOGLE_CLIENT_ID, "client_secret": GOOGLE_CLIENT_SECRET, "redirect_uri": redirect_uri, "grant_type": "authorization_code"})
            if token_response.status_code != 200:
                raise HTTPException(status_code=401, detail="Failed to exchange authorization code")
            tokens = token_response.json()
            userinfo_response = await client_http.get("https://www.googleapis.com/oauth2/v2/userinfo", headers={"Authorization": f"Bearer {tokens.get('access_token')}"})
            if userinfo_response.status_code != 200:
                raise HTTPException(status_code=401, detail="Failed to get user info from Google")
            google_user = userinfo_response.json()
        except httpx.RequestError as e:
            logger.error(f"Google OAuth request failed: {e}")
            raise HTTPException(status_code=401, detail="Authentication failed")

    email = google_user.get('email')
    name = google_user.get('name', 'User')
    picture = google_user.get('picture')
    if not email:
        raise HTTPException(status_code=400, detail="Email not provided by Google")

    if is_gantt_auth_request(request, redirect_uri):
        enforce_gantt_login_allowed(request, email, redirect_uri=redirect_uri)
        existing_for_gate = await db.users.find_one({"email": email, "role": "agent"}, {"_id": 0})
        if not existing_for_gate:
            raise HTTPException(status_code=403, detail=GANTT_LOGIN_DENIED_MESSAGE)

    existing_agent = await db.users.find_one({"email": email, "role": "agent"}, {"_id": 0})
    existing_buyer = await db.users.find_one({"email": email, "role": "buyer"}, {"_id": 0})
    client_link = await db.clients.find_one({"email": email}, {"_id": 0})
    is_new_agent = (
        intended_role == "agent" and not existing_agent and not existing_buyer
    )

    user_id, role = await _resolve_google_role(intended_role, email, name, picture, existing_agent, existing_buyer, client_link)

    if is_new_agent:
        welcome_data = {
            "name": name,
            "role": "agent",
            "project_name": "your Gantt projects",
        }
        welcome_data.update(gantt_welcome_email_data(request, name))
        await send_notification_email(
            "welcome_onboarding", email, welcome_data, request=request
        )

    token = create_access_token(user_id, role)
    _set_session_cookie(response, token)
    user = await db.users.find_one({"user_id": user_id}, {"_id": 0, "password_hash": 0})
    return {**user, "token": token}


@router.get("/auth/me")
async def get_me(user: dict = Depends(get_current_user)):
    return {k: v for k, v in user.items() if k != 'password_hash'}


@router.post("/auth/check-email")
async def check_email_status(request: CheckEmailRequest):
    email = request.email.lower().strip()
    role = request.role
    if role not in ['agent', 'buyer']:
        raise HTTPException(status_code=400, detail="Invalid role")
    user = await db.users.find_one({"email": email, "role": role}, {"_id": 0})
    if not user:
        return {"exists": False, "has_password": False, "has_google": False, "message": "No account found. You can create a new account."}
    has_password = bool(user.get('password_hash'))
    has_google = user.get('picture') is not None
    if has_password and has_google:
        return {"exists": True, "has_password": True, "has_google": True, "message": "You can login with email/password or Google."}
    elif has_password:
        return {"exists": True, "has_password": True, "has_google": False, "message": "Login with your email and password."}
    else:
        return {"exists": True, "has_password": False, "has_google": True, "message": "This account was created with Google. Login with Google, or set a password to enable email login."}


@router.post("/auth/set-password")
async def set_password_for_oauth_user(request: SetPasswordRequest, response: Response):
    email = request.email.lower().strip()
    role = request.role
    if role not in ['agent', 'buyer']:
        raise HTTPException(status_code=400, detail="Invalid role")
    if len(request.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    user = await db.users.find_one({"email": email, "role": role}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="No account found with this email")
    if user.get('password_hash'):
        raise HTTPException(status_code=400, detail="This account already has a password. Use 'Forgot Password' to reset it.")
    password_hash = bcrypt.hashpw(request.password.encode(), bcrypt.gensalt()).decode()
    await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"password_hash": password_hash}})
    logger.info(f"Password set for OAuth user: {user['user_id']}")
    token = create_access_token(user['user_id'], role)
    _set_session_cookie(response, token)
    return {"message": "Password set successfully. You can now login with email/password.", "user_id": user['user_id'], "email": email, "name": user['name'], "role": role, "token": token}


@router.post("/auth/forgot-password")
async def forgot_password(request: ForgotPasswordRequest, req: Request):
    await rate_limit_check(req, "auth_password_reset")
    email = request.email.lower().strip()
    role = request.role
    if role not in ['agent', 'buyer']:
        raise HTTPException(status_code=400, detail="Invalid role")
    enforce_gantt_login_allowed(req, email)
    user = await db.users.find_one({"email": email, "role": role, "password_hash": {"$exists": True}})
    if not user:
        return {"message": "If an account exists with this email, you will receive a reset link."}
    reset_token = secrets.token_urlsafe(32)
    reset_expiry = datetime.now(timezone.utc) + timedelta(hours=1)
    await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"password_reset_token": reset_token, "password_reset_expires": reset_expiry.isoformat()}})
    frontend_url = _password_reset_frontend_url(req)
    reset_link = f"{frontend_url}/reset-password?token={reset_token}"
    if is_gantt_request(req):
        subject = f"Reset your {GANTT_APP_NAME} password"
        brand_color = "#0e7490"
        brand_label = GANTT_APP_NAME
    else:
        subject = "Reset your Evohome password"
        brand_color = "#2563EB"
        brand_label = "Evohome"
    html_content = (
        f'<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto">'
        f'<h2 style="color:{brand_color}">Reset Your Password</h2>'
        f'<p>Hi {user.get("name", "there")},</p>'
        f'<p>Click below to create a new password for your {brand_label} account:</p>'
        f'<p style="text-align:center;margin:30px 0">'
        f'<a href="{reset_link}" style="background:{brand_color};color:#fff;padding:12px 24px;'
        f'text-decoration:none;border-radius:6px;display:inline-block">Reset Password</a></p>'
        f'<p style="color:#666;font-size:14px">This link expires in 1 hour.</p>'
        f'<p style="color:#999;font-size:12px">{brand_label}</p></div>'
    )
    await send_email_async(email, subject, html_content, request=req)
    return {"message": "If an account exists with this email, you will receive a reset link."}


@router.post("/auth/reset-password")
async def reset_password(request: ResetPasswordRequest):
    user = await db.users.find_one({"password_reset_token": request.token})
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    expiry = user.get("password_reset_expires")
    if expiry:
        expiry_dt = datetime.fromisoformat(expiry.replace('Z', '+00:00'))
        if datetime.now(timezone.utc) > expiry_dt:
            raise HTTPException(status_code=400, detail="Reset token has expired")
    if len(request.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    password_hash = bcrypt.hashpw(request.new_password.encode(), bcrypt.gensalt()).decode()
    await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"password_hash": password_hash}, "$unset": {"password_reset_token": "", "password_reset_expires": ""}})
    logger.info(f"Password reset successful for user: {user['user_id']}")
    return {"message": "Password reset successful. You can now log in with your new password."}


@router.post("/auth/refresh")
async def refresh_token(request: Request, response: Response):
    token = extract_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="No token provided")
    if is_token_invalidated(token):
        raise HTTPException(status_code=401, detail="Session has been invalidated. Please login again.")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM], options={"verify_exp": False})
        exp = datetime.fromtimestamp(payload['exp'], tz=timezone.utc)
        if datetime.now(timezone.utc) > exp + timedelta(hours=24):
            raise HTTPException(status_code=401, detail="Token too old to refresh. Please login again.")
        user_id = payload['user_id']
        user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        new_token = create_access_token(user_id, user['role'])
        response.set_cookie(key="session_token", value=new_token, httponly=True, secure=True, samesite="none", path="/", max_age=JWT_EXPIRY_HOURS * 3600)
        return {"success": True, "token": new_token, "expires_in": JWT_EXPIRY_HOURS * 3600}
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


@router.get("/auth/session", response_model=AuthSessionResponse)
async def check_session(request: Request):
    token = extract_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if is_token_invalidated(token):
        raise HTTPException(status_code=401, detail="Session invalidated")
    try:
        payload = verify_jwt_token(token)
        user = await db.users.find_one({"user_id": payload['user_id']}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return {"authenticated": True, "user": {"user_id": user['user_id'], "email": user['email'], "name": user['name'], "role": user['role']}}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid session")


@router.post("/auth/logout", response_model=AuthLogoutResponse)
async def logout(request: Request, response: Response):
    token = extract_token(request)
    if token:
        invalidate_token(token)
    response.delete_cookie(key="session_token", path="/", secure=True, httponly=True, samesite="none")
    return {"success": True, "message": "Logged out successfully"}


# ======================= PRIVATE HELPERS =======================

def _set_session_cookie(response: Response, token: str):
    response.set_cookie(key="session_token", value=token, httponly=True, secure=True, samesite="none", path="/", max_age=JWT_EXPIRY_DAYS * 24 * 60 * 60)


async def _resolve_oauth_role(intended_role, email, oauth_data, existing_agent, existing_buyer, client_link):
    """Resolve user_id and role for Emergent OAuth session exchange."""
    name = oauth_data.get('name', 'User')
    picture = oauth_data.get('picture')

    if intended_role == 'agent':
        if existing_agent:
            await db.users.update_one({"user_id": existing_agent['user_id']}, {"$set": {"name": name, "picture": picture}})
            return existing_agent['user_id'], "agent"
        elif existing_buyer:
            raise HTTPException(status_code=403, detail="This account is registered as a buyer. Please use 'Login as Buyer' instead.")
        else:
            raise HTTPException(status_code=403, detail="This email is not authorized as an agent. Contact your administrator to register.")

    elif intended_role == 'buyer':
        if existing_buyer:
            await db.users.update_one({"user_id": existing_buyer['user_id']}, {"$set": {"name": name, "picture": picture}})
            return existing_buyer['user_id'], "buyer"
        elif existing_agent:
            raise HTTPException(status_code=403, detail="This account is registered as an agent. Please use 'Login as Agent' instead.")
        else:
            return await _create_buyer(email, name, picture, client_link)

    else:
        if existing_agent:
            await db.users.update_one({"user_id": existing_agent['user_id']}, {"$set": {"name": name, "picture": picture}})
            return existing_agent['user_id'], "agent"
        elif existing_buyer:
            await db.users.update_one({"user_id": existing_buyer['user_id']}, {"$set": {"name": name, "picture": picture}})
            return existing_buyer['user_id'], "buyer"
        else:
            return await _create_buyer(email, name, picture, client_link)


async def _resolve_google_role(intended_role, email, name, picture, existing_agent, existing_buyer, client_link):
    """Resolve user_id and role for Google OAuth callback."""
    if intended_role == 'agent':
        if existing_agent:
            await db.users.update_one({"user_id": existing_agent['user_id']}, {"$set": {"name": name, "picture": picture}})
            return existing_agent['user_id'], "agent"
        elif existing_buyer:
            raise HTTPException(status_code=403, detail="This account is registered as a buyer. Please use 'Login as Buyer' instead.")
        else:
            user_id = f"agent_{uuid.uuid4().hex[:12]}"
            await db.users.insert_one({"user_id": user_id, "email": email, "name": name, "picture": picture, "role": "agent", "subscription_plan": "free", "subscription_status": "active", "created_at": datetime.now(timezone.utc).isoformat()})
            logger.info(f"New agent registered via Google OAuth: {email}")
            return user_id, "agent"
    else:
        if existing_buyer:
            await db.users.update_one({"user_id": existing_buyer['user_id']}, {"$set": {"name": name, "picture": picture}})
            return existing_buyer['user_id'], "buyer"
        elif existing_agent:
            raise HTTPException(status_code=403, detail="This account is registered as an agent. Please use 'Login as Agent' instead.")
        else:
            return await _create_buyer(email, name, picture, client_link)


async def _create_buyer(email, name, picture, client_link):
    user_id = f"buyer_{uuid.uuid4().hex[:12]}"
    user_doc = {"user_id": user_id, "email": email, "name": name, "picture": picture, "role": "buyer", "created_at": datetime.now(timezone.utc).isoformat()}
    await db.users.insert_one(user_doc)
    if client_link:
        await db.clients.update_one({"client_id": client_link['client_id']}, {"$set": {"buyer_id": user_id}})
    return user_id, "buyer"
