"""
WebSocket real-time service - manages connections and broadcasts.
Extracted from server.py during Phase 3 modularization.
"""
import logging
from datetime import datetime, timezone
from fastapi import WebSocket

from database import db
from services.email_service import send_notification_email, create_notification

logger = logging.getLogger("evohome.realtime")


class ConnectionManager:
    """Manages WebSocket connections for real-time updates"""

    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)
        logger.info(f"WebSocket connected for user: {user_id}")

    def disconnect(self, websocket: WebSocket, user_id: str):
        if user_id in self.active_connections:
            if websocket in self.active_connections[user_id]:
                self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
        logger.info(f"WebSocket disconnected for user: {user_id}")

    async def send_to_user(self, user_id: str, message: dict):
        if user_id in self.active_connections:
            disconnected = []
            for connection in self.active_connections[user_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"Failed to send WebSocket message: {e}")
                    disconnected.append(connection)
            for conn in disconnected:
                self.active_connections[user_id].remove(conn)

    async def broadcast_to_users(self, user_ids: list[str], message: dict):
        for user_id in user_ids:
            await self.send_to_user(user_id, message)


ws_manager = ConnectionManager()


async def notify_realtime(user_ids: list[str], event_type: str, data: dict):
    """Helper to send real-time notifications via WebSocket"""
    message = {
        "type": event_type,
        "data": data,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    await ws_manager.broadcast_to_users(user_ids, message)


async def send_milestone_notification(step: dict, project: dict, timeline: dict, user: dict, is_demo: bool):
    """Send notifications when a construction milestone is completed"""
    try:
        units = await db.units.find(
            {"project_id": project['project_id']},
            {"_id": 0, "unit_id": 1, "reference": 1}
        ).to_list(100)

        unit_ids = [u['unit_id'] for u in units]
        unit_refs = {u['unit_id']: u.get('reference', 'Unit') for u in units}

        clients = await db.clients.find(
            {"unit_id": {"$in": unit_ids}},
            {"_id": 0, "client_id": 1, "buyer_id": 1, "name": 1, "email": 1, "unit_id": 1}
        ).to_list(100)

        if not clients:
            logger.info(f"No clients to notify for milestone completion: {step.get('title')}")
            return

        agent_settings = await db.agent_settings.find_one(
            {"agent_id": user['user_id']},
            {"_id": 0}
        ) or {}

        tl_ref = step.get('timeline_id', '')
        all_steps = await db.timeline_steps.find(
            {"timeline_id": tl_ref},
            {"_id": 0, "status": 1}
        ).to_list(100)

        completed_count = sum(1 for s in all_steps if s['status'] in ['completed', 'approved'])
        total_count = len(all_steps)
        progress_percent = round((completed_count / total_count) * 100) if total_count > 0 else 0

        for client in clients:
            buyer_id = client.get('buyer_id')
            if not buyer_id:
                continue

            unit_ref = unit_refs.get(client.get('unit_id'), 'Your Unit')

            await create_notification(
                user_id=buyer_id,
                title=f"Milestone Reached: {step.get('title', 'Construction Update')}",
                message=f"The '{step.get('title')}' phase has been completed for {unit_ref}. Overall progress: {progress_percent}%",
                notification_type="milestone_completed",
                link="/buyer/dashboard",
                is_demo=is_demo,
                metadata={
                    "step_id": step.get('step_id'),
                    "project_id": project.get('project_id'),
                    "progress_percent": progress_percent
                }
            )

            if client.get('email'):
                email_data = {
                    "buyer_name": client.get('name', 'there'),
                    "milestone_name": step.get('title', 'Construction Phase'),
                    "milestone_description": step.get('description', ''),
                    "project_name": project.get('name', 'Your Project'),
                    "unit_reference": unit_ref,
                    "progress_percent": progress_percent,
                    "agent_name": agent_settings.get('profile', {}).get('display_name') or user.get('name', 'Your Agent'),
                    "company_name": agent_settings.get('company_name', ''),
                    "agent_email": agent_settings.get('profile', {}).get('contact_email', ''),
                    "agent_phone": agent_settings.get('profile', {}).get('contact_phone', '')
                }
                try:
                    await send_notification_email("milestone_completed", client['email'], email_data)
                    logger.info(f"Sent milestone email to {client['email']} for step {step.get('step_id')}")
                except Exception as e:
                    logger.error(f"Failed to send milestone email to {client['email']}: {e}")

            await notify_realtime(
                [buyer_id],
                "milestone_completed",
                {
                    "step_id": step.get('step_id'),
                    "step_title": step.get('title'),
                    "progress_percent": progress_percent
                }
            )

        logger.info(f"Sent milestone notifications to {len(clients)} clients for step: {step.get('title')}")

    except Exception as e:
        logger.error(f"Failed to send milestone notifications: {e}")
