"""Demo environment HTTP API — seed, reset, and session entry (no auth under /auth)."""
import importlib.util
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from database import db
from core.auth import create_access_token, get_current_agent
from core.config import get_config

# Load seed module by path so importing this router does not execute services/__init__.py
# (that package eagerly imports optional deps like resend).
_seed_path = Path(__file__).resolve().parent.parent / "services" / "demo_environment.py"
_seed_spec = importlib.util.spec_from_file_location("evohome_demo_environment", _seed_path)
_demo_environment = importlib.util.module_from_spec(_seed_spec)
assert _seed_spec.loader is not None
_seed_spec.loader.exec_module(_demo_environment)
seed_demo_environment = _demo_environment.seed_demo_environment

router = APIRouter()

SESSION_COOKIE_MAX_AGE = 7 * 24 * 60 * 60


def _require_public_demo():
    if not get_config().public_demo_allowed:
        raise HTTPException(status_code=404, detail="Not found")


def _require_demo_seed_routes():
    """Destructive seed/reset: allowed on demo deployments or when public demo is on."""
    cfg = get_config()
    if not (cfg.is_demo_deployment or cfg.public_demo_allowed):
        raise HTTPException(status_code=404, detail="Not found")


def _set_session_cookie(response: Response, token: str):
    response.set_cookie(
        key="session_token",
        value=token,
        httponly=True,
        secure=True,
        samesite="none",
        path="/",
        max_age=SESSION_COOKIE_MAX_AGE,
    )


class DemoEnterBody(BaseModel):
    """Start a demo session. When fresh=true, demo_* data is purged and re-seeded first."""

    persona: Literal["agent", "buyer"]
    buyer_slot: int = Field(1, ge=1, le=4, description="Which demo buyer (1–4) when persona=buyer")
    fresh: bool = Field(
        default=False,
        description="If true, purge and re-seed the demo world before issuing the session.",
    )


@router.post("/demo/enter")
async def demo_enter(body: DemoEnterBody, response: Response):
    """
    Canonical Try Demo entry: optional full re-seed, then JWT + session cookie like email login.
    """
    _require_public_demo()
    if body.fresh:
        await seed_demo_environment()

    if body.persona == "agent":
        user_id = "demo_agent_001"
    else:
        user_id = f"demo_buyer_00{body.buyer_slot}"

    user = await db.users.find_one({"user_id": user_id}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(
            status_code=404,
            detail="Demo is not initialized. Call with fresh=true or POST /api/demo/seed (demo deployments).",
        )

    role = user["role"]
    token = create_access_token(user_id, role)
    _set_session_cookie(response, token)
    redirect = "/agent/home" if role == "agent" else "/buyer/dashboard"
    return {
        "user_id": user["user_id"],
        "email": user["email"],
        "name": user["name"],
        "role": role,
        "token": token,
        "redirect": redirect,
    }


@router.get("/demo/seed")
async def seed_demo_data_get():
    _require_demo_seed_routes()
    return await seed_demo_data_post()


@router.post("/demo/seed")
async def seed_demo_data_post():
    """Purge all demo_* rows and insert the full demo dataset."""
    _require_demo_seed_routes()
    return await seed_demo_environment()


@router.post("/demo/reset")
async def reset_demo_data():
    """Alias for POST /demo/seed (fresh demo world)."""
    _require_demo_seed_routes()
    return await seed_demo_environment()


# ── Admin utilities (operational; not demo-specific) ──


@router.post("/admin/migrate-clients")
async def migrate_client_data(user: dict = Depends(get_current_agent)):
    clients_without_unit_ref = await db.clients.find(
        {"unit_reference": {"$exists": False}},
        {"_id": 0, "client_id": 1},
    ).to_list(1000)

    clients_without_status = await db.clients.find(
        {"status": {"$exists": False}},
        {"_id": 0, "client_id": 1},
    ).to_list(1000)

    if clients_without_unit_ref:
        await db.clients.update_many(
            {"unit_reference": {"$exists": False}},
            {"$set": {"unit_reference": "General"}},
        )

    if clients_without_status:
        await db.clients.update_many(
            {"status": {"$exists": False}},
            {"$set": {"status": "active"}},
        )

    return {
        "migrated": True,
        "clients_fixed_unit_reference": len(clients_without_unit_ref),
        "clients_fixed_status": len(clients_without_status),
    }


@router.get("/admin/data-health")
async def check_data_health(user: dict = Depends(get_current_agent)):
    clients_missing_unit_ref = await db.clients.count_documents({"unit_reference": {"$exists": False}})
    clients_missing_status = await db.clients.count_documents({"status": {"$exists": False}})
    docs_missing_client = await db.documents.count_documents({"client_id": {"$exists": False}})
    docs_missing_project = await db.documents.count_documents({"project_id": {"$exists": False}})

    all_buyers = await db.users.find({"role": "buyer"}, {"_id": 0, "user_id": 1}).to_list(1000)
    buyer_ids = [b["user_id"] for b in all_buyers]
    linked_buyers = await db.clients.distinct("buyer_id", {"buyer_id": {"$in": buyer_ids}})
    orphan_buyers = len(buyer_ids) - len(linked_buyers)

    issues = []
    if clients_missing_unit_ref > 0:
        issues.append(f"{clients_missing_unit_ref} clients missing unit_reference")
    if clients_missing_status > 0:
        issues.append(f"{clients_missing_status} clients missing status")
    if docs_missing_client > 0:
        issues.append(f"{docs_missing_client} documents missing client_id")
    if docs_missing_project > 0:
        issues.append(f"{docs_missing_project} documents missing project_id")
    if orphan_buyers > 0:
        issues.append(f"{orphan_buyers} buyers without client linkage")

    return {
        "healthy": len(issues) == 0,
        "issues": issues,
        "details": {
            "clients_missing_unit_reference": clients_missing_unit_ref,
            "clients_missing_status": clients_missing_status,
            "documents_missing_client_id": docs_missing_client,
            "documents_missing_project_id": docs_missing_project,
            "buyers_without_client_linkage": orphan_buyers,
        },
    }
