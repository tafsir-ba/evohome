"""
Email service - send emails via Resend and manage email templates.
Extracted from server.py during Phase 3 modularization.
"""
import os
import uuid
import asyncio
import logging
import resend
from datetime import datetime, timezone
from fastapi import Request

from database import db
from core.monitoring import capture_email_error

logger = logging.getLogger("evohome.email")

RESEND_API_KEY = os.environ.get('RESEND_API_KEY', '')
SENDER_EMAIL = os.environ.get('SENDER_EMAIL', '')
FRONTEND_URL = os.environ.get('FRONTEND_URL') or os.environ.get('APP_URL', '')

if RESEND_API_KEY:
    resend.api_key = RESEND_API_KEY


async def send_email_async(to_email: str, subject: str, html_content: str, request: Request = None) -> dict:
    """Send email asynchronously using Resend with error monitoring"""
    if not RESEND_API_KEY:
        logger.warning(f"RESEND_API_KEY not configured. Would send email to {to_email}: {subject}")
        return {"status": "skipped", "reason": "No API key configured"}

    if not SENDER_EMAIL:
        logger.warning(f"SENDER_EMAIL not configured. Cannot send email to {to_email}")
        return {"status": "skipped", "reason": "No sender email configured"}

    params = {
        "from": SENDER_EMAIL,
        "to": [to_email],
        "subject": subject,
        "html": html_content
    }

    try:
        result = await asyncio.to_thread(resend.Emails.send, params)
        logger.info(f"Email sent to {to_email}: {subject}")
        # Record side effect in trace
        try:
            from core.trace import trace_side_effect
            trace_side_effect("email", target=to_email, detail=f"sent: {subject[:50]}")
        except Exception:
            pass
        return {"status": "success", "email_id": result.get("id") if isinstance(result, dict) else str(result)}
    except Exception as e:
        capture_email_error(e, recipient=to_email, template=subject[:50], request=request)
        logger.error(f"Failed to send email to {to_email}: {str(e)}")
        try:
            from core.trace import trace_side_effect
            trace_side_effect("email", target=to_email, detail=f"failed: {subject[:50]}: {str(e)[:30]}")
        except Exception:
            pass
        return {"status": "error", "error": str(e)}


def get_email_template(template_type: str, data: dict) -> tuple[str, str]:
    """Generate email subject and HTML content based on template type"""
    frontend_url = FRONTEND_URL.rstrip('/')

    agent_company = data.get('company_name') or data.get('agent_name') or 'Evohome'
    agent_name = data.get('agent_name') or 'Your Agent'
    agent_email = data.get('agent_email') or ''
    agent_phone = data.get('agent_phone') or ''

    signature_parts = [f"<strong>{agent_name}</strong>"]
    if agent_company and agent_company != agent_name:
        signature_parts.append(agent_company)
    if agent_email:
        signature_parts.append(f'<a href="mailto:{agent_email}" style="color: #2563EB;">{agent_email}</a>')
    if agent_phone:
        signature_parts.append(agent_phone)
    agent_signature = "<br>".join(signature_parts)

    cta_button_style = (
        "display: inline-block; "
        "background-color: #2563EB; "
        "color: #FFFFFF !important; "
        "padding: 14px 28px; "
        "text-decoration: none; "
        "border-radius: 6px; "
        "font-weight: bold; "
        "font-size: 16px; "
        "mso-padding-alt: 14px 28px; "
        "text-align: center;"
    )

    if template_type == "document_sent":
        doc_type = data.get('doc_type', 'document').capitalize()
        cta_text = f"View {doc_type}" if doc_type else "View in Platform"
        subject = f"New {doc_type} from {agent_company}: {data.get('title', 'Document')}"
        html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head><body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333333; margin: 0; padding: 0; background-color: #f5f5f5;"><div style="max-width: 600px; margin: 0 auto; padding: 20px;"><div style="background-color: #2563EB; color: #FFFFFF; padding: 24px; text-align: center; border-radius: 8px 8px 0 0;"><h1 style="margin: 0; color: #FFFFFF; font-size: 24px;">{doc_type} Received</h1></div><div style="background-color: #FFFFFF; padding: 32px; border: 1px solid #e5e7eb; border-top: none;"><p style="margin-top: 0;">Hi {data.get('buyer_name', 'there')},</p><p><strong>{agent_name}</strong> from <strong>{agent_company}</strong> has sent you a new {doc_type.lower()}.</p><div style="background-color: #f9fafb; padding: 20px; border-radius: 8px; margin: 24px 0; border: 1px solid #e5e7eb;"><h3 style="margin-top: 0; color: #1a1a1a;">{data.get('title', 'Document')}</h3><p style="color: #666666; margin-bottom: 12px;">{data.get('summary', '')}</p><p style="font-size: 28px; font-weight: bold; color: #2563EB; margin: 0;">{data.get('currency', 'CHF')} {data.get('amount', 0):,.2f}</p><p style="color: #666666; font-size: 14px; margin-top: 8px; margin-bottom: 0;">Project: {data.get('project_name', 'N/A')} - Unit: {data.get('unit_reference', 'N/A')}</p></div><p>Please review and take action:</p><table role="presentation" cellspacing="0" cellpadding="0" border="0" style="margin: 24px auto;"><tr><td style="border-radius: 6px; background-color: #2563EB;"><a href="{frontend_url}/buyer/dashboard" target="_blank" style="{cta_button_style}">{cta_text}</a></td></tr></table><hr style="border: none; border-top: 1px solid #e5e7eb; margin: 24px 0;"><p style="font-size: 14px; color: #666666; margin-bottom: 0;">{agent_signature}</p></div><div style="padding: 16px; text-align: center; color: #9ca3af; font-size: 12px;"><p style="margin: 0;">Powered by Evohome</p></div></div></body></html>"""

    elif template_type == "quote_approved":
        subject = f"Quote Approved: {data.get('title', 'Document')}"
        cta_text = "View Quote"
        html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head><body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333333; margin: 0; padding: 0; background-color: #f5f5f5;"><div style="max-width: 600px; margin: 0 auto; padding: 20px;"><div style="background-color: #16a34a; color: #FFFFFF; padding: 24px; text-align: center; border-radius: 8px 8px 0 0;"><h1 style="margin: 0; color: #FFFFFF; font-size: 24px;">Quote Approved</h1></div><div style="background-color: #FFFFFF; padding: 32px; border: 1px solid #e5e7eb; border-top: none;"><p style="margin-top: 0;">Great news!</p><p><strong>{data.get('buyer_name', 'Your client')}</strong> has approved the quote <strong>{data.get('document_number', '')}</strong>.</p><div style="background-color: #f9fafb; padding: 20px; border-radius: 8px; margin: 24px 0; border: 1px solid #e5e7eb;"><h3 style="margin-top: 0; color: #1a1a1a;">{data.get('title', 'Quote')}</h3><p style="font-size: 28px; font-weight: bold; color: #2563EB; margin: 8px 0;">{data.get('currency', 'CHF')} {data.get('amount', 0):,.2f}</p><span style="display: inline-block; padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; background-color: #dcfce7; color: #166534;">Approved</span></div><p>You can now convert this quote to an invoice.</p><table role="presentation" cellspacing="0" cellpadding="0" border="0" style="margin: 24px auto;"><tr><td style="border-radius: 6px; background-color: #2563EB;"><a href="{frontend_url}/agent/documents/{data.get('document_id', '')}" target="_blank" style="{cta_button_style}">{cta_text}</a></td></tr></table></div><div style="padding: 16px; text-align: center; color: #9ca3af; font-size: 12px;"><p style="margin: 0;">Evohome - Real Estate Management</p></div></div></body></html>"""

    elif template_type == "change_requested":
        subject = f"Changes Requested: {data.get('title', 'Document')}"
        cta_text = "View & Revise"
        html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head><body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333333; margin: 0; padding: 0; background-color: #f5f5f5;"><div style="max-width: 600px; margin: 0 auto; padding: 20px;"><div style="background-color: #f59e0b; color: #FFFFFF; padding: 24px; text-align: center; border-radius: 8px 8px 0 0;"><h1 style="margin: 0; color: #FFFFFF; font-size: 24px;">Changes Requested</h1></div><div style="background-color: #FFFFFF; padding: 32px; border: 1px solid #e5e7eb; border-top: none;"><p style="margin-top: 0;"><strong>{data.get('buyer_name', 'Your client')}</strong> has requested changes to <strong>{data.get('document_number', 'the document')}</strong>.</p><div style="background-color: #fef3c7; padding: 20px; border-radius: 8px; margin: 24px 0; border-left: 4px solid #f59e0b;"><h4 style="margin-top: 0; color: #92400e;">Client's Comment:</h4><p style="font-style: italic; color: #78350f; margin-bottom: 0;">"{data.get('comment', 'No comment provided')}"</p></div><p>Please review the feedback and upload a revised document.</p><table role="presentation" cellspacing="0" cellpadding="0" border="0" style="margin: 24px auto;"><tr><td style="border-radius: 6px; background-color: #2563EB;"><a href="{frontend_url}/agent/documents/{data.get('document_id', '')}" target="_blank" style="{cta_button_style}">{cta_text}</a></td></tr></table></div><div style="padding: 16px; text-align: center; color: #9ca3af; font-size: 12px;"><p style="margin: 0;">Evohome - Real Estate Management</p></div></div></body></html>"""

    elif template_type == "payment_confirmed":
        subject = f"Payment Confirmed: {data.get('title', 'Invoice')}"
        cta_text = "View Invoice"
        html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head><body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333333; margin: 0; padding: 0; background-color: #f5f5f5;"><div style="max-width: 600px; margin: 0 auto; padding: 20px;"><div style="background-color: #16a34a; color: #FFFFFF; padding: 24px; text-align: center; border-radius: 8px 8px 0 0;"><h1 style="margin: 0; color: #FFFFFF; font-size: 24px;">Payment Received</h1></div><div style="background-color: #FFFFFF; padding: 32px; border: 1px solid #e5e7eb; border-top: none;"><p style="margin-top: 0;">Payment has been confirmed for invoice <strong>{data.get('document_number', '')}</strong>.</p><div style="background-color: #f9fafb; padding: 20px; border-radius: 8px; margin: 24px 0; border: 1px solid #e5e7eb;"><h3 style="margin-top: 0; color: #1a1a1a;">{data.get('title', 'Invoice')}</h3><p style="font-size: 28px; font-weight: bold; color: #16a34a; margin: 8px 0;">{data.get('currency', 'CHF')} {data.get('amount', 0):,.2f}</p><span style="display: inline-block; padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; background-color: #dcfce7; color: #166534;">Paid</span></div><table role="presentation" cellspacing="0" cellpadding="0" border="0" style="margin: 24px auto;"><tr><td style="border-radius: 6px; background-color: #2563EB;"><a href="{frontend_url}/agent/documents/{data.get('document_id', '')}" target="_blank" style="{cta_button_style}">{cta_text}</a></td></tr></table></div><div style="padding: 16px; text-align: center; color: #9ca3af; font-size: 12px;"><p style="margin: 0;">Evohome - Real Estate Management</p></div></div></body></html>"""

    elif template_type == "new_message":
        subject = f"New Message from {data.get('sender_name', 'Your Agent')}"
        cta_text = "View Message"
        html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head><body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333333; margin: 0; padding: 0; background-color: #f5f5f5;"><div style="max-width: 600px; margin: 0 auto; padding: 20px;"><div style="background-color: #2563EB; color: #FFFFFF; padding: 24px; text-align: center; border-radius: 8px 8px 0 0;"><h1 style="margin: 0; color: #FFFFFF; font-size: 24px;">New Message</h1></div><div style="background-color: #FFFFFF; padding: 32px; border: 1px solid #e5e7eb; border-top: none;"><p style="margin-top: 0;"><strong>{data.get('sender_name', 'Someone')}</strong> sent you a message:</p><div style="background-color: #f9fafb; padding: 20px; border-radius: 8px; margin: 24px 0; border-left: 4px solid #2563EB;"><p style="margin: 0; color: #333333;">{data.get('message_preview', '')[:200]}...</p></div><table role="presentation" cellspacing="0" cellpadding="0" border="0" style="margin: 24px auto;"><tr><td style="border-radius: 6px; background-color: #2563EB;"><a href="{frontend_url}/{data.get('link', 'buyer/dashboard')}" target="_blank" style="{cta_button_style}">{cta_text}</a></td></tr></table></div><div style="padding: 16px; text-align: center; color: #9ca3af; font-size: 12px;"><p style="margin: 0;">Evohome - Real Estate Management</p></div></div></body></html>"""

    elif template_type == "feed_update":
        subject = f"New Update from {data.get('agent_name', 'Your Agent')} - {data.get('project_name', 'Your Project')}"
        cta_text = "View Update"
        html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head><body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333333; margin: 0; padding: 0; background-color: #f5f5f5;"><div style="max-width: 600px; margin: 0 auto; padding: 20px;"><div style="background-color: #2563EB; color: #FFFFFF; padding: 24px; text-align: center; border-radius: 8px 8px 0 0;"><h1 style="margin: 0; color: #FFFFFF; font-size: 24px;">New Update</h1></div><div style="background-color: #FFFFFF; padding: 32px; border: 1px solid #e5e7eb; border-top: none;"><p style="margin-top: 0;">Hi {data.get('buyer_name', 'there')},</p><p>Your agent has posted a new update for <strong>{data.get('project_name', 'your project')}</strong>.</p><div style="background-color: #f9fafb; padding: 20px; border-radius: 8px; margin: 24px 0; border-left: 4px solid #2563EB;"><p style="margin: 0; color: #333333;">{data.get('message_preview', 'View the full update in your dashboard.')}</p></div><table role="presentation" cellspacing="0" cellpadding="0" border="0" style="margin: 24px auto;"><tr><td style="border-radius: 6px; background-color: #2563EB;"><a href="{frontend_url}/{data.get('link', 'buyer/dashboard')}" target="_blank" style="{cta_button_style}">{cta_text}</a></td></tr></table><hr style="border: none; border-top: 1px solid #e5e7eb; margin: 24px 0;"><p style="font-size: 14px; color: #666666; margin-bottom: 0;">{agent_signature}</p></div><div style="padding: 16px; text-align: center; color: #9ca3af; font-size: 12px;"><p style="margin: 0;">Evohome - Real Estate Management</p></div></div></body></html>"""

    elif template_type == "milestone_completed":
        subject = f"Milestone Reached: {data.get('milestone_name', 'Construction Update')}"
        cta_text = "View Progress"
        progress_percent = data.get('progress_percent', 0)
        html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head><body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333333; margin: 0; padding: 0; background-color: #f5f5f5;"><div style="max-width: 600px; margin: 0 auto; padding: 20px;"><div style="background-color: #16a34a; color: #FFFFFF; padding: 24px; text-align: center; border-radius: 8px 8px 0 0;"><h1 style="margin: 0; color: #FFFFFF; font-size: 24px;">Milestone Completed</h1></div><div style="background-color: #FFFFFF; padding: 32px; border: 1px solid #e5e7eb; border-top: none;"><p style="margin-top: 0;">Hi {data.get('buyer_name', 'there')},</p><p>Great news! A construction milestone for your property has been completed.</p><div style="background-color: #f0fdf4; padding: 20px; border-radius: 8px; margin: 24px 0; border: 1px solid #bbf7d0;"><h3 style="margin-top: 0; color: #166534;">{data.get('milestone_name', 'Milestone')}</h3><p style="color: #666666; margin-bottom: 12px;">{data.get('milestone_description', '')}</p><p style="font-size: 14px; color: #166534; margin: 0;"><strong>Project:</strong> {data.get('project_name', 'N/A')} - <strong>Unit:</strong> {data.get('unit_reference', 'N/A')}</p></div><div style="margin: 24px 0;"><p style="margin-bottom: 8px; font-weight: 600;">Overall Progress: {progress_percent}%</p><div style="background-color: #e5e7eb; border-radius: 9999px; height: 12px; overflow: hidden;"><div style="background-color: #16a34a; height: 100%; width: {progress_percent}%; border-radius: 9999px;"></div></div></div><p>Log in to view the full construction timeline and details.</p><table role="presentation" cellspacing="0" cellpadding="0" border="0" style="margin: 24px auto;"><tr><td style="border-radius: 6px; background-color: #2563EB;"><a href="{frontend_url}/buyer/dashboard" target="_blank" style="{cta_button_style}">{cta_text}</a></td></tr></table><hr style="border: none; border-top: 1px solid #e5e7eb; margin: 24px 0;"><p style="font-size: 14px; color: #666666; margin-bottom: 0;">{agent_signature}</p></div><div style="padding: 16px; text-align: center; color: #9ca3af; font-size: 12px;"><p style="margin: 0;">Evohome - Real Estate Management</p></div></div></body></html>"""

    else:
        subject = "Notification from Evohome"
        cta_text = "View in Platform"
        html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head><body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333333; margin: 0; padding: 0; background-color: #f5f5f5;"><div style="max-width: 600px; margin: 0 auto; padding: 20px;"><div style="background-color: #2563EB; color: #FFFFFF; padding: 24px; text-align: center; border-radius: 8px 8px 0 0;"><h1 style="margin: 0; color: #FFFFFF; font-size: 24px;">Notification</h1></div><div style="background-color: #FFFFFF; padding: 32px; border: 1px solid #e5e7eb; border-top: none;"><p style="margin-top: 0;">{data.get('message', 'You have a new notification.')}</p><table role="presentation" cellspacing="0" cellpadding="0" border="0" style="margin: 24px auto;"><tr><td style="border-radius: 6px; background-color: #2563EB;"><a href="{frontend_url}" target="_blank" style="{cta_button_style}">{cta_text}</a></td></tr></table></div><div style="padding: 16px; text-align: center; color: #9ca3af; font-size: 12px;"><p style="margin: 0;">Evohome - Real Estate Management</p></div></div></body></html>"""

    return subject, html


async def send_notification_email(template_type: str, to_email: str, data: dict) -> dict:
    """Send a notification email using a template"""
    subject, html = get_email_template(template_type, data)
    return await send_email_async(to_email, subject, html)
