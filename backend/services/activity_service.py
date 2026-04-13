"""
Activity Service — Canonical Implementation.

No is_demo. Pure data operations + notification orchestration.
Activity is the master communication object. Replies are children.
Recipients are explicit. Attachments inherit ownership from activity.
"""
import os
import uuid
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from database import db
from services.notification_service import emit_notification, emit_email, emit_realtime

logger = logging.getLogger(__name__)

VALID_ACTIVITY_TYPES = {"message", "image", "pdf", "status"}


# ── Helpers ──

async def get_buyer_context(buyer_id: str) -> Optional[Dict[str, Any]]:
    """Get unit/project context for a buyer via client linkage."""
    client = await db.clients.find_one(
        {"buyer_id": buyer_id},
        {"_id": 0, "client_id": 1, "project_id": 1, "unit_reference": 1}
    )
    if not client:
        return None
    unit = await db.units.find_one(
        {"client_id": client['client_id']},
        {"_id": 0, "unit_id": 1, "unit_reference": 1, "project_id": 1}
    )
    return {
        "client_id": client['client_id'],
        "project_id": client.get('project_id') or (unit.get('project_id') if unit else None),
        "unit_id": unit.get('unit_id') if unit else None,
        "unit_reference": unit.get('unit_reference') if unit else client.get('unit_reference'),
    }


async def enrich_activity(activity: dict, include_replies: bool = False) -> dict:
    """Enrich a SINGLE activity. Used for detail views only.
    For list views, use batch_enrich_activities() instead."""

    author = await db.users.find_one({"user_id": activity['author_id']}, {"_id": 0, "name": 1})
    activity['author_name'] = author['name'] if author else 'Unknown'

    project = await db.projects.find_one({"project_id": activity['project_id']}, {"_id": 0, "name": 1})
    activity['project_name'] = project['name'] if project else None

    if activity.get('unit_id'):
        unit = await db.units.find_one({"unit_id": activity['unit_id']}, {"_id": 0, "unit_reference": 1})
        activity['unit_reference'] = unit['unit_reference'] if unit else None

    recipients = await db.activity_recipients.find(
        {"activity_id": activity['activity_id']}, {"_id": 0}
    ).to_list(100)
    for r in recipients:
        c = await db.clients.find_one({"client_id": r['client_id']}, {"_id": 0, "name": 1})
        r['client_name'] = c['name'] if c else 'Unknown'
    activity['recipients'] = recipients

    activity['reply_count'] = await db.activity_replies.count_documents(
        {"activity_id": activity['activity_id']}
    )

    if include_replies:
        replies = await db.activity_replies.find(
            {"activity_id": activity['activity_id']}, {"_id": 0}
        ).sort("created_at", 1).to_list(100)
        for reply in replies:
            a = await db.users.find_one({"user_id": reply['author_id']}, {"_id": 0, "name": 1})
            reply['author_name'] = a['name'] if a else 'Unknown'
        activity['replies'] = replies

    return activity


async def batch_enrich_activities(activities: List[dict]) -> List[dict]:
    """Batch-enrich a list of activities using O(1) queries instead of O(N*M).
    
    Replaces serial enrich_activity() calls for list views.
    Uses $in batch lookups and in-memory joins.
    """
    if not activities:
        return []

    # Collect unique IDs
    activity_ids = [a['activity_id'] for a in activities]
    author_ids = list({a['author_id'] for a in activities})
    project_ids = list({a['project_id'] for a in activities if a.get('project_id')})
    unit_ids = list({a['unit_id'] for a in activities if a.get('unit_id')})

    # Batch fetch: 6 queries total (regardless of page size)
    authors_list = await db.users.find(
        {"user_id": {"$in": author_ids}}, {"_id": 0, "user_id": 1, "name": 1}
    ).to_list(len(author_ids))
    author_map = {u['user_id']: u['name'] for u in authors_list}

    projects_list = await db.projects.find(
        {"project_id": {"$in": project_ids}}, {"_id": 0, "project_id": 1, "name": 1}
    ).to_list(len(project_ids)) if project_ids else []
    project_map = {p['project_id']: p['name'] for p in projects_list}

    units_list = await db.units.find(
        {"unit_id": {"$in": unit_ids}}, {"_id": 0, "unit_id": 1, "unit_reference": 1}
    ).to_list(len(unit_ids)) if unit_ids else []
    unit_map = {u['unit_id']: u.get('unit_reference') for u in units_list}

    # Batch fetch recipients for all activities at once
    all_recipients = await db.activity_recipients.find(
        {"activity_id": {"$in": activity_ids}}, {"_id": 0}
    ).to_list(1000)

    # Batch fetch client names for all recipients
    recipient_client_ids = list({r['client_id'] for r in all_recipients})
    clients_list = await db.clients.find(
        {"client_id": {"$in": recipient_client_ids}}, {"_id": 0, "client_id": 1, "name": 1}
    ).to_list(len(recipient_client_ids)) if recipient_client_ids else []
    client_map = {c['client_id']: c['name'] for c in clients_list}

    # Group recipients by activity_id
    recipients_by_activity = {}
    for r in all_recipients:
        r['client_name'] = client_map.get(r['client_id'], 'Unknown')
        recipients_by_activity.setdefault(r['activity_id'], []).append(r)

    # Batch count replies using aggregation
    reply_counts_pipeline = [
        {"$match": {"activity_id": {"$in": activity_ids}}},
        {"$group": {"_id": "$activity_id", "count": {"$sum": 1}}}
    ]
    reply_counts = await db.activity_replies.aggregate(reply_counts_pipeline).to_list(len(activity_ids))
    reply_count_map = {r['_id']: r['count'] for r in reply_counts}

    # Enrich in-memory
    for a in activities:
        a['author_name'] = author_map.get(a['author_id'], 'Unknown')
        a['project_name'] = project_map.get(a.get('project_id'))
        if a.get('unit_id'):
            a['unit_reference'] = unit_map.get(a['unit_id'])
        a['recipients'] = recipients_by_activity.get(a['activity_id'], [])
        a['reply_count'] = reply_count_map.get(a['activity_id'], 0)

    return activities


# ── Core CRUD ──

async def create_and_distribute_activity(
    author_id: str,
    activity_type: str,
    project_id: str,
    recipient_client_ids: List[str],
    title: Optional[str],
    content: Optional[str],
    file_url: Optional[str],
    file_name: Optional[str],
    file_size: Optional[int],
    unit_id: Optional[str],
    agent_user: dict,
    stored_filename: Optional[str] = None,
) -> Dict[str, Any]:
    """Create activity, link recipients, send notifications. Full canonical flow."""
    now = datetime.now(timezone.utc).isoformat()
    activity_id = f"act_{uuid.uuid4().hex[:12]}"

    doc = {
        "activity_id": activity_id,
        "type": activity_type,
        "title": title,
        "content": content,
        "file_url": file_url,
        "file_name": file_name,
        "file_size": file_size,
        "author_id": author_id,
        "author_role": "agent",
        "project_id": project_id,
        "unit_id": unit_id,
        "created_at": now,
        "updated_at": now,
    }
    if stored_filename:
        doc["stored_filename"] = stored_filename
    await db.activities.insert_one(doc)

    project = await db.projects.find_one({"project_id": project_id}, {"_id": 0, "name": 1})

    for client_id in recipient_client_ids:
        await db.activity_recipients.insert_one({
            "recipient_id": f"rcpt_{uuid.uuid4().hex[:8]}",
            "activity_id": activity_id,
            "client_id": client_id,
            "created_at": now,
        })
        await _notify_recipient(client_id, activity_id, activity_type, content, project, agent_user)

    result = await db.activities.find_one({"activity_id": activity_id}, {"_id": 0})
    return await enrich_activity(result)


async def _notify_recipient(client_id, activity_id, activity_type, content, project, agent_user):
    """Send notification + email to a single recipient."""
    client = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
    if not client or not client.get('buyer_id'):
        return

    buyer = await db.users.find_one(
        {"user_id": client['buyer_id']}, {"_id": 0, "email": 1, "name": 1}
    )
    if not buyer:
        return

    from core.notification_routing import buyer_query

    pid = project.get('project_id') if project else None
    await emit_notification(
        user_id=client['buyer_id'],
        title="New Update from Your Agent",
        message=content[:100] if content else f"New {activity_type} posted",
        notification_type="feed_update",
        link=buyer_query("updates", activity_id=activity_id, project_id=pid or ""),
        metadata={"activity_id": activity_id, "project_id": pid},
    )

    await emit_realtime(
        [client['buyer_id']], "new_activity",
        {"activity_id": activity_id, "type": activity_type}
    )

    if buyer.get('email'):
        agent = await db.users.find_one(
            {"user_id": agent_user['user_id']},
            {"_id": 0, "name": 1, "contact_email": 1, "phone": 1, "company_name": 1}
        )
        await emit_email("feed_update", buyer['email'], {
            "buyer_name": buyer.get('name', client.get('name', 'there')),
            "agent_name": agent.get('name', 'Your Agent') if agent else 'Your Agent',
            "agent_email": agent.get('contact_email', '') if agent else '',
            "agent_phone": agent.get('phone', '') if agent else '',
            "company_name": agent.get('company_name', '') if agent else '',
            "project_name": project.get('name', 'Your Project') if project else 'Your Project',
            "message_preview": content[:200] if content else f"New {activity_type} update",
            "link": "buyer/dashboard",
        })


async def list_activities(
    user_id: str,
    role: str,
    agent_scope_id: Optional[str] = None,
    project_id: Optional[str] = None,
    client_id: Optional[str] = None,
    unit_id: Optional[str] = None,
    activity_type: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
) -> Dict[str, Any]:
    """List activities scoped by role."""
    if role == 'buyer':
        return await _list_buyer_activities(user_id, activity_type, limit, offset)
    return await _list_agent_activities(
        user_id, agent_scope_id, project_id, client_id, unit_id, activity_type, limit, offset
    )


async def _list_agent_activities(
    user_id, agent_scope_id, project_id, client_id, unit_id, activity_type, limit, offset
):
    query = {}
    if project_id:
        query["project_id"] = project_id
    if client_id:
        recs = await db.activity_recipients.find(
            {"client_id": client_id}, {"_id": 0, "activity_id": 1}
        ).to_list(1000)
        query["activity_id"] = {"$in": [r['activity_id'] for r in recs]} if recs else {"$in": []}
    if unit_id:
        query["unit_id"] = unit_id
    if not project_id and not client_id and not unit_id:
        if agent_scope_id:
            projects = await db.projects.find(
                {"agent_id": agent_scope_id}, {"_id": 0, "project_id": 1}
            ).to_list(2000)
            project_ids = [p["project_id"] for p in projects]
            query["project_id"] = {"$in": project_ids}
        else:
            query["author_id"] = user_id
    if activity_type:
        query["type"] = activity_type

    total = await db.activities.count_documents(query)
    activities = await db.activities.find(
        query, {"_id": 0}
    ).sort("created_at", -1).skip(offset).limit(limit).to_list(limit)
    enriched = await batch_enrich_activities(activities)
    return {"activities": enriched, "total": total, "limit": limit, "offset": offset}


async def _list_buyer_activities(buyer_id, activity_type, limit, offset):
    ctx = await get_buyer_context(buyer_id)
    if not ctx:
        return {"activities": [], "total": 0, "limit": limit, "offset": offset}

    recs = await db.activity_recipients.find(
        {"client_id": ctx['client_id']}, {"_id": 0, "activity_id": 1}
    ).to_list(1000)
    ids = [r['activity_id'] for r in recs]
    if not ids:
        return {"activities": [], "total": 0, "limit": limit, "offset": offset}

    query = {"activity_id": {"$in": ids}}
    if activity_type:
        query["type"] = activity_type

    total = await db.activities.count_documents(query)
    activities = await db.activities.find(
        query, {"_id": 0}
    ).sort("created_at", -1).skip(offset).limit(limit).to_list(limit)
    enriched = await batch_enrich_activities(activities)
    return {"activities": enriched, "total": total, "limit": limit, "offset": offset}


async def get_activity_detail(activity_id: str) -> Optional[Dict[str, Any]]:
    """Get a single activity with full enrichment and replies."""
    activity = await db.activities.find_one(
        {"activity_id": activity_id}, {"_id": 0}
    )
    if not activity:
        return None
    return await enrich_activity(activity, include_replies=True)


async def can_buyer_access_activity(buyer_id: str, activity_id: str) -> bool:
    """Check buyer has access via recipient linkage."""
    ctx = await get_buyer_context(buyer_id)
    if not ctx:
        return False
    return bool(await db.activity_recipients.find_one({
        "activity_id": activity_id, "client_id": ctx['client_id'],
    }))


async def update_activity(
    activity_id: str, author_id: str, title: Optional[str], content: Optional[str]
) -> Optional[Dict[str, Any]]:
    """Update activity title/content. Author only."""
    activity = await db.activities.find_one(
        {"activity_id": activity_id, "author_id": author_id}, {"_id": 0}
    )
    if not activity:
        return None

    updates = {"updated_at": datetime.now(timezone.utc).isoformat()}
    if title is not None:
        updates['title'] = title
    if content is not None:
        updates['content'] = content

    await db.activities.update_one({"activity_id": activity_id}, {"$set": updates})
    result = await db.activities.find_one({"activity_id": activity_id}, {"_id": 0})
    return result


async def delete_activity(activity_id: str, author_id: str) -> bool:
    """Delete activity and cascade (recipients, replies, files)."""
    activity = await db.activities.find_one(
        {"activity_id": activity_id, "author_id": author_id}, {"_id": 0}
    )
    if not activity:
        return False

    from services import file_service

    sf = activity.get("stored_filename")
    if not sf and activity.get("file_url"):
        sf = file_service.stored_filename_from_public_url(activity["file_url"])
    if sf:
        try:
            file_service.delete_file(sf)
        except Exception as e:
            logger.warning("delete activity file storage failed activity_id=%s: %s", activity_id, e)

    if activity.get('file_path') and os.path.exists(activity['file_path']):
        try:
            os.remove(activity['file_path'])
        except Exception:
            pass

    # Legacy: files written only under backend/uploads/activities/ (not file_service)
    fu = activity.get("file_url") or ""
    if "/activities/files/" in fu:
        rel = fu.split("/activities/files/", 1)[-1].split("?")[0]
        legacy_dir = Path(__file__).resolve().parent.parent / "uploads" / "activities"
        parts = [p for p in rel.replace("\\", "/").split("/") if p and p != "."]
        if parts and ".." not in parts:
            try:
                target = legacy_dir.joinpath(*parts).resolve()
                target.relative_to(legacy_dir.resolve())
                if target.is_file():
                    target.unlink()
            except (OSError, ValueError):
                pass

    await db.activity_replies.delete_many({"activity_id": activity_id})
    await db.activity_recipients.delete_many({"activity_id": activity_id})
    await db.activities.delete_one({"activity_id": activity_id})
    return True


async def create_reply(
    activity_id: str, author_id: str, author_role: str, content: str
) -> Dict[str, Any]:
    """Create a reply to an activity."""
    now = datetime.now(timezone.utc).isoformat()
    reply_id = f"reply_{uuid.uuid4().hex[:12]}"
    doc = {
        "reply_id": reply_id,
        "activity_id": activity_id,
        "author_id": author_id,
        "author_role": author_role,
        "content": content,
        "created_at": now,
    }
    await db.activity_replies.insert_one(doc)
    await db.activities.update_one({"activity_id": activity_id}, {"$set": {"updated_at": now}})

    doc.pop('_id', None)
    author = await db.users.find_one({"user_id": author_id}, {"_id": 0, "name": 1})
    doc['author_name'] = author['name'] if author else 'Unknown'
    return doc


async def create_draft_activity(
    author_id: str,
    project_id: str,
    title: Optional[str],
    content: Optional[str],
    recipient_client_ids: List[str],
) -> Dict[str, Any]:
    """Create a draft activity. No distribution, no notifications.
    Returns the created activity dict. Canonical — no is_demo."""
    now = datetime.now(timezone.utc).isoformat()
    activity_id = f"act_{uuid.uuid4().hex[:12]}"

    doc = {
        "activity_id": activity_id,
        "type": "message",
        "title": title or "",
        "content": content or "",
        "file_url": None,
        "file_name": None,
        "file_size": None,
        "author_id": author_id,
        "author_role": "agent",
        "project_id": project_id,
        "unit_id": None,
        "is_draft": True,
        "draft_recipients": recipient_client_ids,
        "created_at": now,
        "updated_at": now,
    }
    await db.activities.insert_one(doc)
    result = await db.activities.find_one({"activity_id": activity_id}, {"_id": 0})
    return result



async def send_draft_activity(activity_id: str, author_id: str, agent_user: dict) -> Optional[Dict[str, Any]]:
    """Convert a draft to sent, create recipients, notify."""
    activity = await db.activities.find_one(
        {"activity_id": activity_id, "author_id": author_id}, {"_id": 0}
    )
    if not activity or not activity.get('is_draft'):
        return None

    recipients = activity.get('draft_recipients', [])
    if not recipients:
        return None

    now = datetime.now(timezone.utc).isoformat()
    await db.activities.update_one(
        {"activity_id": activity_id},
        {"$set": {"is_draft": False, "updated_at": now}, "$unset": {"draft_recipients": ""}}
    )

    project = await db.projects.find_one(
        {"project_id": activity['project_id']}, {"_id": 0, "name": 1}
    )
    for client_id in recipients:
        await db.activity_recipients.insert_one({
            "recipient_id": f"rcpt_{uuid.uuid4().hex[:8]}",
            "activity_id": activity_id,
            "client_id": client_id,
            "created_at": now,
        })
        await _notify_recipient(
            client_id, activity_id, activity.get('type', 'message'),
            activity.get('content'), project, agent_user
        )

    updated = await db.activities.find_one({"activity_id": activity_id}, {"_id": 0})
    return await enrich_activity(updated)


async def request_change(activity_id: str) -> bool:
    """Mark a file-type activity as change_requested."""
    activity = await db.activities.find_one({"activity_id": activity_id}, {"_id": 0})
    if not activity or activity['type'] != 'file':
        return False
    await db.activities.update_one(
        {"activity_id": activity_id},
        {"$set": {"status": "change_requested", "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    return True


async def mark_seen(user_id: str) -> str:
    """Update last_seen_at tracking. Returns timestamp."""
    now = datetime.now(timezone.utc).isoformat()
    await db.user_activity_tracking.update_one(
        {"user_id": user_id},
        {"$set": {"last_seen_at": now}},
        upsert=True,
    )
    return now


async def get_unread_count(user_id: str, role: str, agent_scope_id: Optional[str] = None) -> Dict[str, Any]:
    """Count activities newer than last_seen_at."""
    tracking = await db.user_activity_tracking.find_one(
        {"user_id": user_id}, {"_id": 0}
    )
    last_seen = tracking.get('last_seen_at') if tracking else None

    if role == 'buyer':
        ctx = await get_buyer_context(user_id)
        if not ctx:
            return {"unread_count": 0, "last_seen_at": last_seen}
        recs = await db.activity_recipients.find(
            {"client_id": ctx['client_id']}, {"_id": 0, "activity_id": 1}
        ).to_list(1000)
        ids = [r['activity_id'] for r in recs]
        if not ids:
            return {"unread_count": 0, "last_seen_at": last_seen}
        query = {"activity_id": {"$in": ids}}
    else:
        if agent_scope_id:
            projects = await db.projects.find(
                {"agent_id": agent_scope_id}, {"_id": 0, "project_id": 1}
            ).to_list(2000)
            project_ids = [p["project_id"] for p in projects]
            query = {"project_id": {"$in": project_ids}}
        else:
            query = {"author_id": user_id}

    if last_seen:
        query["created_at"] = {"$gt": last_seen}

    count = await db.activities.count_documents(query)
    return {"unread_count": count, "last_seen_at": last_seen}
