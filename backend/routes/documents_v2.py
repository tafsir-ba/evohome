"""
Document Routes — Canonical Implementation.

Thin route layer. File I/O delegated to file_service.
All data operations delegate to document_service.
"""
import logging
from io import BytesIO
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Request, UploadFile, File, Form
from fastapi.responses import StreamingResponse, FileResponse

from database import db
from core.auth import get_current_user, get_current_agent
from core.access_control import can_access_document, can_access_client
from core.access_scope import resolve_agent_access_scope
from services import document_service
from services import file_service
from services.ai_service import extract_document_from_pdf
from services.qr_service import generate_swiss_qr_code_base64, DEFAULT_IBAN, DEFAULT_COMPANY_NAME
from models.schemas import DocumentUpdate, DocumentAction

logger = logging.getLogger(__name__)

router = APIRouter()


def _effective_user_id(user: dict) -> str:
    """Agents operate on workspace scope; buyers use own id."""
    if user.get("role") == "agent":
        return user.get("workspace_owner_id") or user["user_id"]
    return user["user_id"]


async def _effective_project_scope(user: dict):
    if user.get("role") != "agent":
        return None
    return (await resolve_agent_access_scope(user)).accessible_project_ids


# ── Upload + preview (AI extraction is assistive only) ──

@router.post("/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    client_id: str = Form(...),
    doc_type: str = Form("quote"),
    user: dict = Depends(get_current_agent),
):
    """Upload PDF and run AI extraction preview. Does NOT create a document."""
    if doc_type not in ("quote", "invoice"):
        doc_type = "quote"

    scope = await resolve_agent_access_scope(user)
    client = await db.clients.find_one(
        {"client_id": client_id, "agent_id": scope.workspace_owner_id}, {"_id": 0}
    )
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    if not await can_access_client(user, client_id):
        raise HTTPException(status_code=403, detail="Access denied")

    result = await file_service.save_pdf(file)

    try:
        extraction = await extract_document_from_pdf(
            str(file_service.get_local_path(result["stored_filename"])),
            result["original_filename"],
        )
    except Exception as e:
        logger.warning(f"AI extraction failed (non-blocking): {e}")
        extraction = {}

    items_total = sum(i.get("total", 0) for i in extraction.get("items", []))
    amount = extraction.get("amount") or items_total or 0

    return {
        "preview_id": result["stored_filename"][:12],
        "type": doc_type,
        "client_id": client_id,
        "project_id": client.get("project_id", ""),
        "unit_reference": client.get("unit_reference", ""),
        "title": extraction.get("title", "Untitled Document"),
        "amount": amount,
        "items": extraction.get("items", []),
        "supplier_name": extraction.get("supplier_name"),
        "summary": extraction.get("description", ""),
        "pdf_filename": result["original_filename"],
        "pdf_stored_filename": result["stored_filename"],
        "ai_extraction_confidence": extraction.get("confidence", "low"),
        "extraction_warning": extraction.get("extraction_failed", False) or extraction.get("amount") is None,
        "is_preview": True,
    }


@router.post("/documents/create")
async def create_document_from_preview(request: Request, user: dict = Depends(get_current_agent)):
    """Create a document from previewed extraction data."""
    body = await request.json()

    client_id = body.get("client_id")
    if not client_id:
        raise HTTPException(status_code=400, detail="client_id is required")
    if not await can_access_client(user, client_id):
        raise HTTPException(status_code=403, detail="Access denied")

    doc_type = body.get("type", "quote")
    if doc_type not in ("quote", "invoice"):
        doc_type = "quote"

    try:
        result = await document_service.create_document(
            agent_id=(await resolve_agent_access_scope(user)).workspace_owner_id,
            doc_type=doc_type,
            client_id=client_id,
            title=body.get("title", "Untitled Document"),
            amount=float(body.get("amount", 0)),
            items=body.get("items", []),
            supplier_name=body.get("supplier_name"),
            notes=body.get("notes"),
            summary=body.get("summary", ""),
            due_date=body.get("due_date"),
            pdf_filename=body.get("pdf_filename"),
            pdf_stored_filename=body.get("pdf_stored_filename"),
            ai_extraction_confidence=body.get("ai_extraction_confidence", "low"),
            approver_client_ids=body.get("approver_client_ids"),
            approval_required_count=body.get("approval_required_count"),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return result


@router.post("/documents/{document_id}/reupload")
async def reupload_document_pdf(
    document_id: str, file: UploadFile = File(...), user: dict = Depends(get_current_agent),
):
    """Upload a revised PDF with version tracking."""
    if not await can_access_document(user, document_id):
        raise HTTPException(status_code=403, detail="Access denied")
    scope = await resolve_agent_access_scope(user)
    query = {"document_id": document_id, "agent_id": scope.workspace_owner_id}
    doc = await db.documents.find_one(query, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc["status"] not in ("Draft", "Sent", "Change Requested"):
        raise HTTPException(status_code=400, detail="Cannot revise document in current status")

    result = await file_service.save_pdf(file)

    try:
        extraction = await extract_document_from_pdf(
            str(file_service.get_local_path(result["stored_filename"])),
            result["original_filename"],
        )
    except Exception as e:
        logger.warning(f"AI extraction failed (non-blocking): {e}")
        extraction = {}

    return await document_service.reupload_document(
        document_id,
        scope.workspace_owner_id,
        result["stored_filename"],
        result["original_filename"],
        extraction,
        doc,
    )


@router.put("/documents/{document_id}")
async def update_document(document_id: str, data: DocumentUpdate, user: dict = Depends(get_current_agent)):
    if not await can_access_document(user, document_id):
        raise HTTPException(status_code=403, detail="Access denied")
    try:
        updates = data.model_dump(exclude_none=False)
        result = await document_service.update_document(
            document_id,
            (await resolve_agent_access_scope(user)).workspace_owner_id,
            updates,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not result:
        raise HTTPException(status_code=404, detail="Document not found")
    return result


@router.delete("/documents/{document_id}")
async def delete_document(document_id: str, force: bool = False, user: dict = Depends(get_current_agent)):
    if not await can_access_document(user, document_id):
        raise HTTPException(status_code=403, detail="Access denied")
    try:
        deleted = await document_service.delete_document(
            document_id,
            (await resolve_agent_access_scope(user)).workspace_owner_id,
            force,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"message": "Document deleted successfully"}


@router.post("/documents/{document_id}/revert-to-draft")
async def revert_document_to_draft(document_id: str, user: dict = Depends(get_current_agent)):
    if not await can_access_document(user, document_id):
        raise HTTPException(status_code=403, detail="Access denied")
    try:
        status = await document_service.revert_to_draft(
            document_id,
            (await resolve_agent_access_scope(user)).workspace_owner_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if status is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"message": f"Document {'is already in' if status == 'Draft' else 'reverted to'} Draft", "status": status}


@router.get("/documents")
async def get_documents(
    doc_type: Optional[str] = None, status: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    return await document_service.list_documents(
        _effective_user_id(user),
        user["role"],
        doc_type,
        status,
        await _effective_project_scope(user),
    )


@router.get("/documents/{document_id}")
async def get_document(document_id: str, user: dict = Depends(get_current_user)):
    if user.get("role") == "agent" and not await can_access_document(user, document_id):
        raise HTTPException(status_code=403, detail="Access denied")
    doc = await document_service.get_document(document_id, _effective_user_id(user), user["role"])
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.get("/documents/{document_id}/source-pdf")
async def get_document_source_pdf(document_id: str, user: dict = Depends(get_current_user)):
    if user.get("role") == "agent" and not await can_access_document(user, document_id):
        raise HTTPException(status_code=403, detail="Access denied")
    doc = await document_service.get_document(document_id, _effective_user_id(user), user["role"])
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    stored = doc.get("pdf_stored_filename")
    # Backward compatibility: old documents have pdf_path (absolute path)
    legacy_path = doc.get("pdf_path")
    if not stored and legacy_path:
        import os
        if os.path.exists(legacy_path):
            return FileResponse(legacy_path, media_type="application/pdf", filename=doc.get("pdf_filename", "document.pdf"))
    if not stored:
        raise HTTPException(status_code=404, detail="Source PDF not found")

    if file_service.USE_SPACES:
        from fastapi.responses import RedirectResponse
        url = file_service.get_file_url(stored)
        return RedirectResponse(url=url)

    path = file_service.resolve_path(stored)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Source PDF not found on disk")

    return FileResponse(str(path), media_type="application/pdf", filename=doc.get("pdf_filename", "document.pdf"))


@router.post("/documents/{document_id}/hero-image")
async def upload_hero_image(document_id: str, file: UploadFile = File(...), user: dict = Depends(get_current_agent)):
    """Upload a hero/banner image for a document."""
    if not await can_access_document(user, document_id):
        raise HTTPException(status_code=403, detail="Access denied")
    from core.trace import set_trace_action, set_trace_entity, trace_db_mutation, trace_service, set_trace_response_summary
    set_trace_action("hero_image_upload")
    set_trace_entity("document", document_id)
    trace_service("routes.documents_v2.upload_hero_image")
    query = {
        "document_id": document_id,
        "agent_id": (await resolve_agent_access_scope(user)).workspace_owner_id,
    }
    doc = await db.documents.find_one(query, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Delete old hero image
    old_stored = doc.get("hero_image_stored_filename")
    if old_stored:
        file_service.delete_file(old_stored)

    result = await file_service.save_hero_image(file, document_id)
    trace_service("services.file_service.save_hero_image")

    from datetime import timezone
    await db.documents.update_one(query, {"$set": {
        "hero_image_url": result["url"],
        "hero_image_stored_filename": result["stored_filename"],
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }})
    trace_db_mutation("documents", "update_one", document_id)
    set_trace_response_summary({"hero_image_url": result["url"], "file_size": result["file_size"]})

    return {"url": result["url"], "filename": result["original_filename"], "size": result["file_size"]}


@router.get("/documents/{document_id}/hero-image")
async def get_hero_image(document_id: str, user: dict = Depends(get_current_user)):
    if user.get("role") == "agent" and not await can_access_document(user, document_id):
        raise HTTPException(status_code=403, detail="Access denied")
    doc = await document_service.get_document(document_id, _effective_user_id(user), user["role"])
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    stored = doc.get("hero_image_stored_filename")
    # Backward compatibility: old documents have hero_image_path (absolute path)
    legacy_path = doc.get("hero_image_path")
    if not stored and legacy_path:
        import os
        if os.path.exists(legacy_path):
            ext = legacy_path.split(".")[-1].lower()
            media = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}.get(ext, "image/jpeg")
            return FileResponse(legacy_path, media_type=media)
    if not stored:
        raise HTTPException(status_code=404, detail="Hero image not found")

    if file_service.USE_SPACES:
        from fastapi.responses import RedirectResponse
        url = file_service.get_file_url(stored)
        return RedirectResponse(url=url)

    path = file_service.resolve_path(stored)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Hero image not found on disk")

    ct = doc.get("content_type", "image/jpeg")
    ext = stored.split(".")[-1].lower()
    media = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}.get(ext, ct)
    return FileResponse(str(path), media_type=media)


@router.delete("/documents/{document_id}/hero-image")
async def delete_hero_image(document_id: str, user: dict = Depends(get_current_agent)):
    if not await can_access_document(user, document_id):
        raise HTTPException(status_code=403, detail="Access denied")
    query = {
        "document_id": document_id,
        "agent_id": (await resolve_agent_access_scope(user)).workspace_owner_id,
    }
    doc = await db.documents.find_one(query, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    stored = doc.get("hero_image_stored_filename")
    if stored:
        file_service.delete_file(stored)
    # Backward compatibility: clean up legacy absolute path
    legacy_path = doc.get("hero_image_path")
    if legacy_path:
        import os
        if os.path.exists(legacy_path):
            try:
                os.remove(legacy_path)
            except OSError:
                pass

    from datetime import timezone
    await db.documents.update_one(query, {"$set": {
        "hero_image_url": None,
        "hero_image_stored_filename": None,
        "hero_image_path": None,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }})
    return {"message": "Hero image deleted"}


@router.get("/documents/{document_id}/qr-code")
async def get_document_qr_code(document_id: str, user: dict = Depends(get_current_user)):
    if user.get("role") == "agent" and not await can_access_document(user, document_id):
        raise HTTPException(status_code=403, detail="Access denied")
    doc = await document_service.get_document(document_id, _effective_user_id(user), user["role"])
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc["type"] != "invoice":
        raise HTTPException(status_code=400, detail="QR code only available for invoices")

    client = await db.clients.find_one({"client_id": doc["client_id"]}, {"_id": 0})
    buyer_name = client.get("name", "Client") if client else "Client"

    agent = await db.users.find_one({"user_id": doc["agent_id"]}, {"_id": 0})
    agent_settings = agent.get("settings", {}) if agent else {}
    billing_info = agent_settings.get("billing", {})

    qr_base64 = generate_swiss_qr_code_base64(
        amount=doc["amount"], reference=doc["document_number"], buyer_name=buyer_name,
        iban=billing_info.get("iban"),
        creditor_name=billing_info.get("company_name") or agent_settings.get("company_name"),
        creditor_address=billing_info.get("address"),
        creditor_pcode=billing_info.get("postal_code"),
        creditor_city=billing_info.get("city"),
    )
    if not qr_base64:
        raise HTTPException(status_code=500, detail="Failed to generate QR code")

    return {
        "qr_code_svg_base64": qr_base64,
        "amount": doc["amount"], "currency": doc.get("currency", "CHF"),
        "document_number": doc["document_number"],
        "payment_info": {
            "beneficiary": billing_info.get("company_name") or agent_settings.get("company_name") or DEFAULT_COMPANY_NAME,
            "iban": billing_info.get("iban") or DEFAULT_IBAN,
            "reference": doc["document_number"],
        },
    }


@router.post("/documents/{document_id}/send")
async def send_document(document_id: str, request: Request, user: dict = Depends(get_current_agent)):
    if not await can_access_document(user, document_id):
        raise HTTPException(status_code=403, detail="Access denied")
    try:
        send_config = {}
        try:
            if request.headers.get("content-type", "").startswith("application/json"):
                send_config = await request.json()
        except Exception:
            send_config = {}
        return await document_service.send_document(
            document_id,
            (await resolve_agent_access_scope(user)).workspace_owner_id,
            user,
            approver_client_ids=send_config.get("approver_client_ids"),
            approval_required_count=send_config.get("approval_required_count"),
            approval_mode=send_config.get("approval_mode"),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/documents/{document_id}/action")
async def perform_document_action(document_id: str, action_data: DocumentAction, user: dict = Depends(get_current_user)):
    if user.get("role") == "agent" and not await can_access_document(user, document_id):
        raise HTTPException(status_code=403, detail="Access denied")
    try:
        return await document_service.document_action(
            document_id, action_data.action, _effective_user_id(user), user["role"],
            user.get("name", ""), action_data.comment,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/timeline")
async def get_document_timeline(user: dict = Depends(get_current_user)):
    return await document_service.get_document_timeline(
        _effective_user_id(user),
        user["role"],
        await _effective_project_scope(user),
    )


# ── PDF generation ──

@router.get("/documents/{document_id}/pdf")
async def get_document_pdf(document_id: str, user: dict = Depends(get_current_user)):
    if user.get("role") == "agent" and not await can_access_document(user, document_id):
        raise HTTPException(status_code=403, detail="Access denied")
    doc = await document_service.get_document(document_id, _effective_user_id(user), user["role"])
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    client = doc.get("client")
    project = doc.get("project")

    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    except ImportError:
        raise HTTPException(status_code=500, detail="PDF generation not available")

    buffer = BytesIO()
    pdf_doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=20*mm, leftMargin=20*mm, topMargin=20*mm, bottomMargin=20*mm)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="CompanyName", fontSize=18, fontName="Helvetica-Bold", spaceAfter=6))
    styles.add(ParagraphStyle(name="DocTitle", fontSize=24, fontName="Helvetica-Bold", spaceAfter=20))
    styles.add(ParagraphStyle(name="SectionTitle", fontSize=12, fontName="Helvetica-Bold", spaceBefore=16, spaceAfter=8))
    styles.add(ParagraphStyle(name="Normal12", fontSize=10, fontName="Helvetica", spaceAfter=4))

    elements = []
    elements.append(Paragraph("UpgradeFlow", styles["CompanyName"]))
    elements.append(Paragraph("Real Estate Post-Sale Management", styles["Normal12"]))
    elements.append(Spacer(1, 10*mm))

    doc_type_label = "INVOICE" if doc["type"] == "invoice" else "QUOTE"
    elements.append(Paragraph(doc_type_label, styles["DocTitle"]))

    created_date = doc["created_at"]
    if isinstance(created_date, str):
        created_date = datetime.fromisoformat(created_date.replace("Z", "+00:00"))

    info_data = [
        [f"{doc_type_label[0]}# :", doc["document_number"]],
        ["Date:", created_date.strftime("%d %B %Y")],
        ["Status:", doc["status"]],
        ["Project:", project["name"] if project else "N/A"],
        ["Unit:", doc.get("unit_reference", "N/A")],
    ]
    if doc["type"] == "invoice" and doc.get("due_date"):
        dd = doc["due_date"]
        if isinstance(dd, str):
            try:
                dd = datetime.fromisoformat(dd.replace("Z", "+00:00"))
            except Exception:
                pass
        info_data.append(["Due Date:", dd.strftime("%d %B %Y") if isinstance(dd, datetime) else dd])

    info_table = Table(info_data, colWidths=[35*mm, 100*mm])
    info_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 10*mm))

    elements.append(Paragraph("Bill To:", styles["SectionTitle"]))
    if client:
        elements.append(Paragraph(client.get("name", ""), styles["Normal12"]))
        elements.append(Paragraph(client.get("email", ""), styles["Normal12"]))
    elements.append(Spacer(1, 8*mm))

    elements.append(Paragraph(doc["title"], styles["SectionTitle"]))
    elements.append(Spacer(1, 6*mm))

    if doc.get("items") and len(doc["items"]) > 0:
        table_data = [["Description", "Qty", "Unit Price", "Total"]]
        for item in doc["items"]:
            table_data.append([
                item.get("description", ""), str(item.get("quantity", "")),
                f"CHF {item.get('unit_price', 0):,.2f}", f"CHF {item.get('total', 0):,.2f}",
            ])
        table_data.append(["", "", "Total:", f"CHF {doc['amount']:,.2f}"])
        items_table = Table(table_data, colWidths=[85*mm, 15*mm, 35*mm, 35*mm])
        items_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3f4f6")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -2), 0.5, colors.HexColor("#e5e7eb")),
            ("FONTNAME", (-2, -1), (-1, -1), "Helvetica-Bold"),
            ("LINEABOVE", (0, -1), (-1, -1), 1, colors.black),
        ]))
        elements.append(items_table)
    else:
        elements.append(Paragraph(f"Total: CHF {doc['amount']:,.2f}", styles["SectionTitle"]))

    elements.append(Spacer(1, 10*mm))
    if doc.get("notes"):
        elements.append(Paragraph("Notes:", styles["SectionTitle"]))
        elements.append(Paragraph(doc["notes"], styles["Normal12"]))

    elements.append(Spacer(1, 20*mm))
    footer_style = ParagraphStyle(name="Footer", fontSize=8, textColor=colors.grey)
    elements.append(Paragraph("UpgradeFlow SA - Rue du Rhone 1, 1204 Geneve - Switzerland", footer_style))

    pdf_doc.build(elements)
    buffer.seek(0)

    filename = f"{doc['type']}_{doc['document_number']}.pdf"
    return StreamingResponse(buffer, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename={filename}"})
