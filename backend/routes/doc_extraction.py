"""Auto-extracted route module from server.py — Phase 3 modularization."""
import os
import re
import json
import uuid
import base64
import logging
import secrets
import tempfile
import openai
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Optional, Literal, Dict, Any
from io import BytesIO

from fastapi import APIRouter, HTTPException, Depends, Request, Response, UploadFile, File, Form, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel, Field, EmailStr

from database import db
from core.auth import get_current_user, get_current_agent, get_current_buyer, verify_token
from core.access_control import can_access_project, can_access_client, can_access_vault_doc, can_access_document, get_accessible_project_ids, get_accessible_client_ids, is_agent, is_buyer, get_is_demo
from core.rate_limit import rate_limit_check, check_rate_limit
from core.monitoring import capture_exception, capture_auth_failure, capture_payment_error, capture_email_error, capture_ai_error, capture_websocket_error, capture_document_error, ErrorContext
from core.responses import AuthSessionResponse, AuthLoginResponse, AuthRefreshResponse, AuthLogoutResponse, DocumentResponse, VaultDocumentResponse, NotificationResponse, ActivityResponse, ActivitiesListResponse, SuccessResponse

from helpers import get_demo_filter, build_query, secure_filename, VALID_TRANSITIONS, validate_transition, SUBSCRIPTION_PLANS, VAULT_CATEGORIES, VAULT_DOC_TYPES
from services.email_service import send_email_async, send_notification_email, create_notification, get_email_template
from services.realtime_service import ws_manager, notify_realtime, send_milestone_notification
from services.qr_service import generate_swiss_qr_code, generate_swiss_qr_code_base64, DEFAULT_IBAN, DEFAULT_COMPANY_NAME
from services.ai_service import extract_document_from_pdf, OPENAI_API_KEY

from models.schemas import *

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).parent.parent
UPLOAD_DIR = ROOT_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

router = APIRouter()

# ==================== DOCUMENT EXTRACTION ENDPOINTS ====================

# ==================== DOCUMENT EXTRACTION ENDPOINTS (Phase 3) ====================

from services.command_service import (
    classify_document,
    DocumentType,
    CommandIntent,
)


@router.post("/command/classify-document")
async def classify_uploaded_document(
    file: UploadFile = File(...),
    user: dict = Depends(get_current_agent)
):
    """
    Classify an uploaded document type.
    Returns document type with confidence score.
    Agent can override the classification.
    
    Supports: PDF files and images (jpg, jpeg, png, webp)
    """
    try:
        # Validate file type - PDFs and images supported
        file_ext = os.path.splitext(file.filename)[1].lower()
        supported_extensions = [".pdf", ".jpg", ".jpeg", ".png", ".webp"]
        
        if file_ext not in supported_extensions:
            raise HTTPException(
                status_code=400, 
                detail="Unsupported file type. Supported formats: PDF, JPG, PNG, WEBP"
            )
        
        # Save file temporarily
        file_id = f"temp_{uuid.uuid4().hex[:12]}"
        file_path = f"/tmp/{file_id}{file_ext}"
        
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # Extract text for classification
        text_content = ""
        extraction_method = "none"
        
        if file_ext == ".pdf":
            try:
                doc = fitz.open(file_path)
                for page_num in range(min(3, len(doc))):  # First 3 pages
                    text_content += doc[page_num].get_text()
                doc.close()
                extraction_method = "pdf_text"
            except Exception as e:
                logger.warning(f"PDF text extraction failed: {e}")
                if os.path.exists(file_path):
                    os.remove(file_path)
                raise HTTPException(
                    status_code=400,
                    detail="Could not read PDF file. The file may be corrupted or password-protected."
                )
        else:
            # Image file - use OCR via OpenAI Vision
            if OPENAI_API_KEY:
                try:
                    import base64
                    with open(file_path, "rb") as img_file:
                        image_data = base64.b64encode(img_file.read()).decode('utf-8')
                    
                    # Determine mime type
                    mime_types = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
                    mime_type = mime_types.get(file_ext, "image/jpeg")
                    
                    client = openai.OpenAI(api_key=OPENAI_API_KEY)
                    response = client.chat.completions.create(
                        model="gpt-4o",
                        messages=[{
                            "role": "user",
                            "content": [
                                {"type": "text", "text": "Extract all text from this document image. Include numbers, dates, and any structured data. Return only the extracted text, no commentary."},
                                {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{image_data}", "detail": "high"}}
                            ]
                        }],
                        max_tokens=2000
                    )
                    text_content = response.choices[0].message.content
                    extraction_method = "ocr_vision"
                except Exception as e:
                    logger.warning(f"OCR extraction failed: {e}")
                    extraction_method = "ocr_failed"
            else:
                extraction_method = "no_api_key"
        
        # Classify document
        doc_type, confidence = classify_document(text_content, file.filename)
        
        # Adjust confidence based on extraction method
        if extraction_method in ["ocr_failed", "no_api_key", "none"]:
            confidence = min(confidence, 0.3)  # Lower confidence if we couldn't extract text
        
        return {
            "file_id": file_id,
            "file_path": file_path,
            "filename": file.filename,
            "document_type": doc_type.value,
            "confidence": round(confidence, 2),
            "extraction_method": extraction_method,
            "can_override": True,
            "available_types": [t.value for t in DocumentType if t != DocumentType.UNKNOWN]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document classification failed: {e}")
        raise HTTPException(status_code=500, detail="Document classification failed. Please try again.")


async def _extract_document_from_image(file_path: str, doc_type_value: str) -> dict:
    """Extract structured data from an image file using OpenAI Vision API."""
    if not OPENAI_API_KEY:
        return {
            "title": os.path.basename(file_path),
            "amount": None,
            "items": [],
            "supplier_name": None,
            "description": "AI extraction unavailable - please enter details manually",
            "confidence": "low",
            "extraction_failed": True
        }

    try:
        with open(file_path, "rb") as img_file:
            image_data = base64.b64encode(img_file.read()).decode('utf-8')

        ext = os.path.splitext(file_path)[1].lower()
        mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
        mime_type = mime_map.get(ext, "image/jpeg")

        client = openai.OpenAI(api_key=OPENAI_API_KEY)

        system_prompt = f"""You are a Swiss real estate document extraction assistant specializing in construction quotes, invoices, and renovation documents. Extract structured data from this {doc_type_value} image.

IMPORTANT: Look carefully for:
- Company/supplier name and address
- Document reference numbers
- Individual line items with descriptions, quantities, and prices
- Tax amounts (TVA/MwSt)
- Total amounts (HT and TTC)
- Currency (default CHF if not specified)
- Dates

Return ONLY a valid JSON object with this exact structure:
{{
  "title": "descriptive title based on document content",
  "amount": total_amount_as_number_or_null,
  "items": [{{"description": "line item text", "quantity": 1, "unit_price": 0, "total": 0}}],
  "supplier_name": "company name from the document",
  "description": "one paragraph summary of the document content",
  "reference": "document reference/number if visible",
  "confidence": "high/medium/low"
}}

If the image is not a clear document (e.g., a photo, screenshot, or unclear scan), still try your best to extract any visible text and structure it. Set confidence to "low" if the content is unclear."""

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": [
                    {"type": "text", "text": f"Extract document information from this {doc_type_value} image. Return only valid JSON."},
                    {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{image_data}", "detail": "high"}}
                ]}
            ],
            max_tokens=4000
        )

        response_text = response.choices[0].message.content or ""
        json_match = re.search(r'\{[\s\S]*\}', response_text) if response_text else None
        if json_match:
            extracted = json.loads(json_match.group())
        else:
            raise ValueError("No JSON found in AI response")

        return {
            "title": extracted.get("title", os.path.basename(file_path)),
            "amount": extracted.get("amount"),
            "items": extracted.get("items", []),
            "supplier_name": extracted.get("supplier_name"),
            "description": extracted.get("description", ""),
            "confidence": extracted.get("confidence", "medium"),
            "extraction_failed": False
        }

    except Exception as e:
        logger.error(f"Image extraction failed: {e}")
        return {
            "title": os.path.basename(file_path),
            "amount": None,
            "items": [],
            "supplier_name": None,
            "description": f"Extraction failed: {str(e)[:80]}",
            "confidence": "low",
            "extraction_failed": True
        }


@router.post("/command/extract-document")
async def extract_document_data(
    file_path: str = Form(...),
    document_type: str = Form(...),
    context: str = Form("{}"),
    idempotency_key: str = Form(None),
    user: dict = Depends(get_current_agent)
):
    """
    Extract structured data from a classified document.
    Returns extracted fields that populate the draft form.
    
    Supports: PDF and image files (jpg, jpeg, png, webp)
    
    Features:
    - Idempotency key to prevent duplicate extractions
    - Validation of extracted amounts (must be positive, reasonable range)
    - Retry-safe: same idempotency_key returns cached result
    """
    try:
        ctx_dict = json.loads(context) if context else {}
        is_demo = user.get('is_demo', False)
        
        # Check idempotency - return cached result if exists
        if idempotency_key:
            cached = await db.extraction_cache.find_one({
                "idempotency_key": idempotency_key,
                "user_id": user['user_id']
            }, {"_id": 0})
            if cached and cached.get("result"):
                logger.info(f"Returning cached extraction for key: {idempotency_key}")
                return cached["result"]
        
        # Validate file exists
        if not os.path.exists(file_path):
            raise HTTPException(
                status_code=400, 
                detail="Document file not found. Please re-upload the document."
            )
        
        # Validate file type - PDFs and images supported
        file_ext = os.path.splitext(file_path)[1].lower()
        supported_extensions = [".pdf", ".jpg", ".jpeg", ".png", ".webp"]
        if file_ext not in supported_extensions:
            raise HTTPException(
                status_code=400,
                detail="Unsupported file type. Supported: PDF, JPG, PNG, WEBP"
            )
        
        # Validate document type
        try:
            doc_type = DocumentType(document_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid document type: {document_type}")
        
        # Map document type to extraction intent
        intent_map = {
            DocumentType.QUOTE: CommandIntent.EXTRACT_QUOTE,
            DocumentType.INVOICE: CommandIntent.EXTRACT_INVOICE,
            DocumentType.TIMELINE: CommandIntent.EXTRACT_TIMELINE,
            DocumentType.CONTACTS: CommandIntent.EXTRACT_CONTACTS,
        }
        
        intent = intent_map.get(doc_type)
        if not intent:
            # For UNKNOWN type, default to quote extraction (most common)
            if doc_type == DocumentType.UNKNOWN:
                intent = CommandIntent.EXTRACT_QUOTE
                doc_type = DocumentType.QUOTE
            else:
                raise HTTPException(status_code=400, detail=f"Cannot extract from document type: {document_type}")
        
        # Extract data using appropriate method based on file type
        extracted_data = {}
        extraction_confidence = 0.5
        extraction_warnings = []
        
        if doc_type in [DocumentType.QUOTE, DocumentType.INVOICE]:
            # Use existing PDF extraction for PDFs, or image extraction for images
            if file_ext == ".pdf":
                extraction_result = await extract_document_from_pdf(file_path, os.path.basename(file_path))
            else:
                # Image extraction using Vision API
                extraction_result = await _extract_document_from_image(file_path, doc_type.value)
            
            extracted_data = {
                "supplier_name": extraction_result.get("supplier_name"),
                "amount": extraction_result.get("amount"),
                "currency": "CHF",
                "description": extraction_result.get("description"),
                "title": extraction_result.get("title"),
                "line_items": extraction_result.get("items", []),
                "reference_number": extraction_result.get("reference"),
            }
            
            # Validate extracted amount
            amount = extracted_data.get("amount")
            if amount is not None:
                try:
                    amount = float(amount)
                    if amount < 0:
                        extraction_warnings.append("Negative amount detected - please verify")
                        extracted_data["_amount_warning"] = "negative"
                    elif amount > 10000000:  # 10M threshold
                        extraction_warnings.append("Unusually large amount - please verify")
                        extracted_data["_amount_warning"] = "large"
                    elif amount == 0:
                        extraction_warnings.append("Zero amount detected - please verify")
                        extracted_data["_amount_warning"] = "zero"
                except (ValueError, TypeError):
                    extraction_warnings.append("Could not parse amount - manual entry required")
                    extracted_data["amount"] = None
            
            confidence_map = {"high": 0.9, "medium": 0.7, "low": 0.4}
            extraction_confidence = confidence_map.get(extraction_result.get("confidence", "low"), 0.4)
            
            if extraction_result.get("extraction_failed"):
                extraction_confidence = 0.1
        
        elif doc_type == DocumentType.TIMELINE:
            # Check if project already has a timeline
            project_id = ctx_dict.get("project_id")
            if project_id:
                existing_timeline = await db.timelines.find_one({
                    "project_id": project_id,
                    "agent_id": user['user_id'],
                    "is_demo": user.get('is_demo', False)
                }, {"_id": 0})
                
                if existing_timeline:
                    # Timeline already exists - return info about existing timeline
                    return {
                        "plan_id": f"plan_{uuid.uuid4().hex[:12]}",
                        "intent": "view_timeline",  # Change intent to view instead of create
                        "document_type": "timeline",
                        "can_execute": False,
                        "timeline_exists": True,
                        "existing_timeline": {
                            "timeline_id": existing_timeline['timeline_id'],
                            "name": existing_timeline.get('name', 'Project Timeline'),
                            "created_at": existing_timeline.get('created_at')
                        },
                        "fields": [
                            {"name": "existing_timeline_id", "value": existing_timeline['timeline_id'], "confidence": 1.0, "source": "database"},
                            {"name": "timeline_name", "value": existing_timeline.get('name', 'Project Timeline'), "confidence": 1.0, "source": "database"},
                            {"name": "project_id", "value": project_id, "confidence": 1.0, "source": "context"}
                        ],
                        "missing_fields": [],
                        "message": f"This project already has a timeline: '{existing_timeline.get('name', 'Project Timeline')}'. Would you like to view or update it?",
                        "available_actions": [
                            {"action": "view", "label": "View Existing Timeline", "path": f"/agent/timeline?project={project_id}"},
                            {"action": "replace", "label": "Replace Timeline", "warning": "This will delete the existing timeline"}
                        ],
                        "source_file": file_path,
                        "created_at": datetime.now(timezone.utc).isoformat()
                    }
            
            # No existing timeline - proceed with extraction
            extracted_data = await _extract_timeline_stages(file_path)
            extraction_confidence = extracted_data.get("confidence", 0.5)
        
        elif doc_type == DocumentType.CONTACTS:
            # Extract contacts
            extracted_data = await _extract_contacts_list(file_path)
            extraction_confidence = extracted_data.get("confidence", 0.5)
        
        # Build the command plan
        fields = []
        for key, value in extracted_data.items():
            if value is not None and key != "confidence":
                conf = 0.9 if value else 0.3
                fields.append({
                    "name": key,
                    "value": value,
                    "confidence": conf,
                    "source": "ai_extraction"
                })
        
        # Add context fields
        if ctx_dict.get("project_id"):
            fields.append({
                "name": "project_id",
                "value": ctx_dict["project_id"],
                "confidence": 1.0,
                "source": "context"
            })
        
        if ctx_dict.get("client_id"):
            fields.append({
                "name": "client_id",
                "value": ctx_dict["client_id"],
                "confidence": 1.0,
                "source": "context"
            })
        
        # Determine missing required fields
        missing_fields = []
        if not ctx_dict.get("project_id"):
            missing_fields.append({
                "name": "project_id",
                "description": "Select a project",
                "required": True
            })
        
        if doc_type in [DocumentType.QUOTE, DocumentType.INVOICE] and not ctx_dict.get("client_id"):
            missing_fields.append({
                "name": "client_id",
                "description": "Select a client",
                "required": False  # Can be added later
            })
        
        # Check if we can execute
        can_execute = len([m for m in missing_fields if m.get("required")]) == 0
        
        # Build result
        result = {
            "plan_id": f"plan_{uuid.uuid4().hex[:12]}",
            "intent": intent.value,
            "intent_confidence": extraction_confidence,
            "document_type": doc_type.value,
            "entities": {
                "project_id": ctx_dict.get("project_id"),
                "client_id": ctx_dict.get("client_id"),
            },
            "fields": fields,
            "extracted_data": extracted_data,
            "missing_fields": missing_fields,
            "is_valid": can_execute,
            "validation_errors": [],
            "extraction_warnings": extraction_warnings if 'extraction_warnings' in dir() else [],
            "requires_confirmation": True,
            "can_execute": can_execute,
            "source_file": file_path,
            "interpretation_log": [
                f"Document type: {doc_type.value}",
                f"Extraction confidence: {extraction_confidence:.0%}",
                f"Fields extracted: {len(fields)}",
            ]
        }
        
        # Cache the result for idempotency
        if idempotency_key:
            await db.extraction_cache.update_one(
                {"idempotency_key": idempotency_key, "user_id": user['user_id']},
                {"$set": {
                    "result": result,
                    "created_at": datetime.now(timezone.utc)
                }},
                upsert=True
            )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document extraction failed: {e}")
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")


