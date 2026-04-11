# Evohome Backend Services
from .email_service import send_email_async, send_notification_email, get_email_template
from .notification_service import create_notification, emit_notification, emit_email, emit_realtime, list_notifications_with_count
from .realtime_service import ws_manager, notify_realtime, send_milestone_notification, ConnectionManager
from .qr_service import generate_swiss_qr_code, generate_swiss_qr_code_base64
from .ai_service import extract_document_from_pdf, OPENAI_API_KEY
