"""
Team Routes — Canonical Implementation.

Thin route layer for team member CRUD and directory.
No is_demo. No business logic in routes.
"""
import os
import uuid
import base64
import logging
from typing import Optional, List
from pathlib import Path

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Query
from pydantic import BaseModel

from core.auth import get_current_user, get_current_agent
from core.access_control import get_workspace_owner_id
from services import team_service
from services.ai_service import OPENAI_API_KEY

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Schemas ──

class TeamMemberCreateBody(BaseModel):
    company_name: str = ""
    contact_name: str = ""
    role: str = ""
    email: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None


class TeamMemberUpdateBody(BaseModel):
    company_name: Optional[str] = None
    contact_name: Optional[str] = None
    role: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None


class BulkContactsBody(BaseModel):
    contacts: List[dict]


# ── Project-scoped team CRUD ──

@router.get("/projects/{project_id}/team")
async def get_team_members(project_id: str, user: dict = Depends(get_current_user)):
    """Get team members for a project."""
    members = await team_service.list_team_members(project_id, user)
    if members is None:
        status = 404 if user["role"] == "agent" else 403
        raise HTTPException(status_code=status, detail="Project not found or not authorized")
    return members


@router.post("/projects/{project_id}/team")
async def create_team_member(project_id: str, data: TeamMemberCreateBody, user: dict = Depends(get_current_agent)):
    """Add a team member to a project."""
    from database import db
    scope_agent_id = get_workspace_owner_id(user)
    project = await db.projects.find_one(
        {"project_id": project_id, "agent_id": scope_agent_id}, {"_id": 0}
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return await team_service.create_team_member(
        project_id=project_id,
        agent_id=scope_agent_id,
        company_name=data.company_name,
        contact_name=data.contact_name,
        role=data.role,
        email=data.email,
        phone=data.phone,
        website=data.website,
        address=data.address,
        notes=data.notes,
    )


@router.put("/projects/{project_id}/team/{member_id}")
async def update_team_member(project_id: str, member_id: str, data: TeamMemberUpdateBody, user: dict = Depends(get_current_agent)):
    """Update a team member."""
    result = await team_service.update_team_member(
        member_id=member_id,
        project_id=project_id,
        agent_id=get_workspace_owner_id(user),
        update_data=data.model_dump(),
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Team member not found")
    return result


@router.delete("/projects/{project_id}/team/{member_id}")
async def delete_team_member(project_id: str, member_id: str, user: dict = Depends(get_current_agent)):
    """Delete a team member."""
    if not await team_service.delete_team_member(member_id, project_id, get_workspace_owner_id(user)):
        raise HTTPException(status_code=404, detail="Team member not found")
    return {"message": "Team member deleted"}


@router.post("/projects/{project_id}/team/bulk")
async def create_team_members_bulk(project_id: str, request: BulkContactsBody, user: dict = Depends(get_current_agent)):
    """Bulk import team members after AI extraction review."""
    from database import db
    scope_agent_id = get_workspace_owner_id(user)
    project = await db.projects.find_one(
        {"project_id": project_id, "agent_id": scope_agent_id}, {"_id": 0}
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return await team_service.bulk_create_team_members(
        project_id=project_id,
        agent_id=scope_agent_id,
        contacts=request.contacts,
    )


# ── Directory + AI extraction ──

@router.get("/team/directory")
async def get_team_directory(
    search: Optional[str] = None,
    project_id: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    user: dict = Depends(get_current_agent),
):
    """Global supplier/contact directory for an agent."""
    return await team_service.get_directory(
        agent_id=get_workspace_owner_id(user), search=search, project_id=project_id, limit=limit
    )


@router.post("/team/extract-contacts")
async def extract_contacts_from_document(
    file: UploadFile = File(...),
    user: dict = Depends(get_current_agent),
):
    """Extract contact information from uploaded document using AI."""
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=503, detail="AI extraction not available - OpenAI API key not configured")

    allowed_extensions = [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".png", ".jpg", ".jpeg", ".webp"]
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail=f"Unsupported file type. Allowed: {', '.join(allowed_extensions)}")

    temp_dir = "/tmp/contact_extraction"
    os.makedirs(temp_dir, exist_ok=True)
    temp_path = os.path.join(temp_dir, f"{uuid.uuid4().hex}_{file.filename}")

    try:
        content = await file.read()
        with open(temp_path, "wb") as f:
            f.write(content)

        extracted_text = ""
        images_base64 = []

        if file_ext == ".pdf":
            try:
                import fitz
                doc = fitz.open(temp_path)
                for page_num in range(min(doc.page_count, 5)):
                    page = doc[page_num]
                    mat = fitz.Matrix(2, 2)
                    pix = page.get_pixmap(matrix=mat)
                    images_base64.append(base64.b64encode(pix.tobytes("png")).decode("utf-8"))
                doc.close()
            except Exception as e:
                logger.error(f"PDF processing error: {e}")
                raise HTTPException(status_code=500, detail="Failed to process PDF")
        elif file_ext in [".png", ".jpg", ".jpeg", ".webp"]:
            with open(temp_path, "rb") as f:
                images_base64.append(base64.b64encode(f.read()).decode("utf-8"))
        elif file_ext in [".doc", ".docx", ".xls", ".xlsx"]:
            try:
                if file_ext == ".docx":
                    from docx import Document
                    doc = Document(temp_path)
                    extracted_text = "\n".join([p.text for p in doc.paragraphs])
                elif file_ext in [".xlsx", ".xls"]:
                    import openpyxl
                    wb = openpyxl.load_workbook(temp_path, data_only=True)
                    texts = []
                    for sheet in wb.worksheets[:3]:
                        for row in sheet.iter_rows(max_row=100, values_only=True):
                            row_text = " | ".join([str(c) for c in row if c])
                            if row_text.strip():
                                texts.append(row_text)
                    extracted_text = "\n".join(texts)
            except ImportError:
                raise HTTPException(status_code=400, detail="Office document processing not available")

        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)

        extraction_prompt = """Analyze this document and extract all contact information for companies, suppliers, or individuals.

For each contact found, extract:
- company_name, contact_name, role, email, phone, website, address

Rules:
1. Only extract real contacts (suppliers, contractors, business partners)
2. Deduplicate contacts
3. Accept partial data
4. For role, infer from context if not explicit

Return a JSON array of contacts. If no contacts found, return []"""

        messages = [{"role": "system", "content": extraction_prompt}]
        if images_base64:
            content_parts = [{"type": "text", "text": "Extract all contact information from this document:"}]
            for img_b64 in images_base64[:5]:
                content_parts.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}", "detail": "high"}})
            messages.append({"role": "user", "content": content_parts})
        else:
            messages.append({"role": "user", "content": f"Extract all contact information from this document:\n\n{extracted_text[:10000]}"})

        response = client.chat.completions.create(model="gpt-4o", messages=messages, max_tokens=4000, temperature=0.1)
        response_text = response.choices[0].message.content.strip()

        import json
        try:
            if "```json" in response_text:
                json_str = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                json_str = response_text.split("```")[1].split("```")[0].strip()
            else:
                json_str = response_text

            contacts = json.loads(json_str)
            if not isinstance(contacts, list):
                contacts = [contacts] if contacts else []

            valid_contacts = []
            for c in contacts:
                if isinstance(c, dict) and (c.get("company_name") or c.get("contact_name")):
                    valid_contacts.append({
                        "company_name": c.get("company_name", ""),
                        "contact_name": c.get("contact_name", ""),
                        "role": c.get("role", ""),
                        "email": c.get("email", ""),
                        "phone": c.get("phone", ""),
                        "website": c.get("website", ""),
                        "address": c.get("address", ""),
                        "confidence": 0.85,
                    })

            return {"contacts": valid_contacts, "source_filename": file.filename, "extraction_count": len(valid_contacts)}
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response: {e}")
            return {"contacts": [], "source_filename": file.filename, "extraction_count": 0, "error": "Could not extract contacts"}
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
