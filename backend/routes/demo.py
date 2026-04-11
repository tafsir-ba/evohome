"""
Demo Data Seeding — Canonical.

Seeds deterministic demo data using demo_* ID namespace.
Cleanup uses ID prefix matching — no is_demo flag anywhere.
"""
import logging
import bcrypt
from datetime import datetime, timezone, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends

from database import db
from core.auth import get_current_agent

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).parent.parent
UPLOAD_DIR = ROOT_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

router = APIRouter()


# ── Seed Namespace ──
# Every demo entity ID starts with a known prefix so cleanup is deterministic.
# Format: demo_{entity}_{seq}  (e.g. demo_agent_001, demo_proj_001)

DEMO_ID_PREFIXES = {
    "users":                       "user_id",
    "projects":                    "project_id",
    "clients":                     "client_id",
    "documents":                   "document_id",
    "activities":                  "activity_id",
    "activity_recipients":         "recipient_id",
    "activity_replies":            "reply_id",
    "team_members":                "member_id",
    "units":                       "unit_id",
    "timeline_templates":          "template_id",
    "timeline_template_steps":     "step_id",
    "timelines":                   "timeline_id",
    "timeline_steps":              "step_id",
    "timeline_step_documents":     "link_id",
    "timeline_step_internal_notes":"note_id",
    "notifications":               "notification_id",
}


async def _cleanup_demo_data():
    """Delete all demo-seeded data by deterministic ID prefix."""
    for collection_name, id_field in DEMO_ID_PREFIXES.items():
        collection = db[collection_name]
        await collection.delete_many({id_field: {"$regex": "^demo_"}})


# ── Endpoints ──

@router.get("/demo/seed")
async def seed_demo_data_get():
    """GET version for easy browser access"""
    return await seed_demo_data()


@router.post("/demo/seed")
async def seed_demo_data():
    """
    Seed comprehensive demo data using canonical schema.
    All entities use demo_* ID prefixes. No is_demo field written anywhere.
    Idempotent: cleans existing demo data before re-seeding.
    """
    await _cleanup_demo_data()

    now = datetime.now(timezone.utc)

    # ── Agent ──
    demo_agent_id = "demo_agent_001"
    demo_agent = {
        "user_id": demo_agent_id,
        "email": "demo.agent@upgradeflow.com",
        "name": "Marc Dubois",
        "password_hash": bcrypt.hashpw("demo123".encode('utf-8'), bcrypt.gensalt()).decode('utf-8'),
        "role": "agent",
        "picture": None,
        "created_at": now.isoformat(),
        "subscription_plan": "pro",
        "subscription_status": "active",
        "settings": {
            "language": "en",
            "currency": "CHF",
            "company_name": "Dubois Immobilier",
        },
    }
    await db.users.insert_one(demo_agent)

    # Generate demo logo
    try:
        from PIL import Image, ImageDraw
        logo_filename = f"logo_{demo_agent_id}_demo.png"
        logo_path = UPLOAD_DIR / logo_filename
        img = Image.new('RGBA', (200, 200), (255, 255, 255, 0))
        draw = ImageDraw.Draw(img)
        primary = (37, 99, 235, 255)
        white = (255, 255, 255, 255)

        def rounded_rectangle(d, xy, radius, fill):
            x1, y1, x2, y2 = xy
            d.rectangle([x1 + radius, y1, x2 - radius, y2], fill=fill)
            d.rectangle([x1, y1 + radius, x2, y2 - radius], fill=fill)
            d.ellipse([x1, y1, x1 + radius * 2, y1 + radius * 2], fill=fill)
            d.ellipse([x2 - radius * 2, y1, x2, y1 + radius * 2], fill=fill)
            d.ellipse([x1, y2 - radius * 2, x1 + radius * 2, y2], fill=fill)
            d.ellipse([x2 - radius * 2, y2 - radius * 2, x2, y2], fill=fill)

        rounded_rectangle(draw, [10, 10, 190, 190], 24, primary)
        draw.rectangle([55, 100, 145, 165], fill=white)
        draw.polygon([(45, 100), (100, 50), (155, 100)], fill=white)
        draw.rectangle([85, 125, 115, 165], fill=primary)
        draw.rectangle([62, 110, 78, 125], fill=primary)
        draw.rectangle([122, 110, 138, 125], fill=primary)
        img.save(str(logo_path), 'PNG')
        await db.users.update_one(
            {"user_id": demo_agent_id},
            {"$set": {"company_logo_url": f"/api/uploads/{logo_filename}"}},
        )
    except Exception as e:
        logger.warning(f"Could not create demo logo: {e}")

    # ── Buyers ──
    demo_buyer1_id = "demo_buyer_001"
    demo_buyer2_id = "demo_buyer_002"

    await db.users.insert_many([
        {
            "user_id": demo_buyer1_id,
            "email": "sophie.mueller@example.com",
            "name": "Sophie Müller",
            "role": "buyer",
            "picture": None,
            "created_at": now.isoformat(),
        },
        {
            "user_id": demo_buyer2_id,
            "email": "thomas.weber@example.com",
            "name": "Thomas Weber",
            "role": "buyer",
            "picture": None,
            "created_at": now.isoformat(),
        },
    ])

    # ── Project ──
    demo_project_id = "demo_proj_001"
    await db.projects.insert_one({
        "project_id": demo_project_id,
        "agent_id": demo_agent_id,
        "name": "Residenza Lago Vista",
        "address": "Via del Sole 15, 6900 Lugano, Switzerland",
        "description": "Luxury lakefront apartments with panoramic views of Lake Lugano.",
        "created_at": (now - timedelta(days=90)).isoformat(),
    })

    # ── Clients ──
    demo_client1_id = "demo_client_001"
    demo_client2_id = "demo_client_002"

    await db.clients.insert_many([
        {
            "client_id": demo_client1_id,
            "agent_id": demo_agent_id,
            "buyer_id": demo_buyer1_id,
            "name": "Sophie Müller",
            "email": "sophie.mueller@example.com",
            "phone": "+41 79 123 45 67",
            "project_id": demo_project_id,
            "unit_id": "demo_unit_001",
            "unit_reference": "Unit A-301",
            "created_at": (now - timedelta(days=60)).isoformat(),
        },
        {
            "client_id": demo_client2_id,
            "agent_id": demo_agent_id,
            "buyer_id": demo_buyer2_id,
            "name": "Thomas Weber",
            "email": "thomas.weber@example.com",
            "phone": "+41 78 987 65 43",
            "project_id": demo_project_id,
            "unit_id": "demo_unit_002",
            "unit_reference": "Unit B-502",
            "created_at": (now - timedelta(days=45)).isoformat(),
        },
    ])

    # ── Units ──
    demo_unit1_id = "demo_unit_001"
    demo_unit2_id = "demo_unit_002"

    await db.units.insert_many([
        {
            "unit_id": demo_unit1_id,
            "project_id": demo_project_id,
            "unit_reference": "A-301",
            "client_id": demo_client1_id,
            "created_at": now.isoformat(),
        },
        {
            "unit_id": demo_unit2_id,
            "project_id": demo_project_id,
            "unit_reference": "B-502",
            "client_id": demo_client2_id,
            "created_at": now.isoformat(),
        },
    ])

    # ── Documents ──
    demo_documents = [
        {
            "document_id": "demo_doc_001",
            "document_number": "QT-2024-0001",
            "type": "quote",
            "status": "Approved",
            "agent_id": demo_agent_id,
            "client_id": demo_client1_id,
            "buyer_id": demo_buyer1_id,
            "project_id": demo_project_id,
            "unit_reference": "Unit A-301",
            "title": "Premium Kitchen Upgrade Package",
            "summary": "Transform your kitchen with Gaggenau appliances, custom oak cabinetry, and premium Silestone countertops.",
            "hero_image_url": None,
            "hero_image_path": None,
            "amount": 43500.00,
            "items": [
                {"description": "Gaggenau Oven Set", "quantity": 1, "unit_price": 12500.00, "total": 12500.00},
                {"description": "Custom Oak Cabinetry", "quantity": 1, "unit_price": 18000.00, "total": 18000.00},
                {"description": "Silestone Countertops", "quantity": 1, "unit_price": 8500.00, "total": 8500.00},
                {"description": "Installation & Labor", "quantity": 1, "unit_price": 4500.00, "total": 4500.00},
            ],
            "currency": "CHF",
            "supplier_name": "Kitchen Solutions AG",
            "notes": "Premium package includes 5-year warranty.",
            "change_request_comment": None,
            "pdf_filename": None,
            "pdf_path": None,
            "ai_extraction_confidence": None,
            "parent_document_id": None,
            "due_date": None,
            "paid_date": None,
            "created_at": (now - timedelta(days=50)).isoformat(),
            "updated_at": (now - timedelta(days=20)).isoformat(),
        },
        {
            "document_id": "demo_doc_002",
            "document_number": "QT-2024-0002",
            "type": "quote",
            "status": "Sent",
            "agent_id": demo_agent_id,
            "client_id": demo_client1_id,
            "buyer_id": demo_buyer1_id,
            "project_id": demo_project_id,
            "unit_reference": "Unit A-301",
            "title": "Smart Home Automation System",
            "summary": "Complete home automation with KNX controller, smart lighting, climate control, and integrated security.",
            "hero_image_url": None,
            "hero_image_path": None,
            "amount": 22800.00,
            "items": [
                {"description": "KNX Controller Hub", "quantity": 1, "unit_price": 3500.00, "total": 3500.00},
                {"description": "Smart Lighting System (12 zones)", "quantity": 1, "unit_price": 6800.00, "total": 6800.00},
                {"description": "Climate Control Integration", "quantity": 1, "unit_price": 4200.00, "total": 4200.00},
                {"description": "Security System Integration", "quantity": 1, "unit_price": 5500.00, "total": 5500.00},
                {"description": "Programming & Configuration", "quantity": 1, "unit_price": 2800.00, "total": 2800.00},
            ],
            "currency": "CHF",
            "supplier_name": "Smart Living GmbH",
            "notes": "System demonstration included upon completion.",
            "change_request_comment": None,
            "pdf_filename": None,
            "pdf_path": None,
            "ai_extraction_confidence": None,
            "parent_document_id": None,
            "due_date": None,
            "paid_date": None,
            "created_at": (now - timedelta(days=5)).isoformat(),
            "updated_at": (now - timedelta(days=4)).isoformat(),
        },
        {
            "document_id": "demo_doc_003",
            "document_number": "QT-2024-0003",
            "type": "quote",
            "status": "Sent",
            "agent_id": demo_agent_id,
            "client_id": demo_client2_id,
            "buyer_id": demo_buyer2_id,
            "project_id": demo_project_id,
            "unit_reference": "Unit B-502",
            "title": "Bathroom Wellness Upgrade",
            "summary": "Luxury spa experience with Hansgrohe rain shower, heated floors, and natural stone finishes.",
            "hero_image_url": None,
            "hero_image_path": None,
            "amount": 27800.00,
            "items": [
                {"description": "Hansgrohe Rain Shower System", "quantity": 1, "unit_price": 4800.00, "total": 4800.00},
                {"description": "Heated Floor System", "quantity": 1, "unit_price": 3200.00, "total": 3200.00},
                {"description": "Premium Duravit Fixtures", "quantity": 1, "unit_price": 6500.00, "total": 6500.00},
                {"description": "Natural Stone Tiles", "quantity": 1, "unit_price": 7800.00, "total": 7800.00},
                {"description": "Installation", "quantity": 1, "unit_price": 5500.00, "total": 5500.00},
            ],
            "currency": "CHF",
            "supplier_name": "Bathroom Design Studio",
            "notes": "Estimated completion: 3 weeks from approval.",
            "change_request_comment": None,
            "pdf_filename": None,
            "pdf_path": None,
            "ai_extraction_confidence": None,
            "parent_document_id": None,
            "due_date": None,
            "paid_date": None,
            "created_at": (now - timedelta(days=3)).isoformat(),
            "updated_at": (now - timedelta(days=2)).isoformat(),
        },
        {
            "document_id": "demo_doc_004",
            "document_number": "QT-2024-0004",
            "type": "quote",
            "status": "Change Requested",
            "agent_id": demo_agent_id,
            "client_id": demo_client2_id,
            "buyer_id": demo_buyer2_id,
            "project_id": demo_project_id,
            "unit_reference": "Unit B-502",
            "title": "Terrace Extension & Landscaping",
            "summary": "Expand your outdoor living with a 25 sqm terrace extension, outdoor kitchen, and professional landscaping.",
            "hero_image_url": None,
            "hero_image_path": None,
            "amount": 30000.00,
            "items": [
                {"description": "Terrace Extension (25 sqm)", "quantity": 1, "unit_price": 15000.00, "total": 15000.00},
                {"description": "Outdoor Kitchen Station", "quantity": 1, "unit_price": 8500.00, "total": 8500.00},
                {"description": "Professional Landscaping", "quantity": 1, "unit_price": 6500.00, "total": 6500.00},
            ],
            "currency": "CHF",
            "supplier_name": "Outdoor Living AG",
            "notes": None,
            "change_request_comment": "I'd like to explore composite decking instead of natural wood for the terrace flooring - easier maintenance. Can you provide an updated quote with this alternative? Also, could we add a pergola (~3x4m) to the outdoor kitchen area?",
            "pdf_filename": None,
            "pdf_path": None,
            "ai_extraction_confidence": None,
            "parent_document_id": None,
            "due_date": None,
            "paid_date": None,
            "created_at": (now - timedelta(days=8)).isoformat(),
            "updated_at": (now - timedelta(days=2)).isoformat(),
        },
        {
            "document_id": "demo_doc_005",
            "document_number": "INV-2024-0001",
            "type": "invoice",
            "status": "Sent",
            "agent_id": demo_agent_id,
            "client_id": demo_client1_id,
            "buyer_id": demo_buyer1_id,
            "project_id": demo_project_id,
            "unit_reference": "Unit A-301",
            "title": "Walk-in Closet Installation",
            "summary": "Custom wardrobe system with integrated LED lighting and jewelry drawers.",
            "hero_image_url": None,
            "hero_image_path": None,
            "amount": 20000.00,
            "items": [
                {"description": "Custom Wardrobe System", "quantity": 1, "unit_price": 12000.00, "total": 12000.00},
                {"description": "Integrated LED Lighting", "quantity": 1, "unit_price": 2500.00, "total": 2500.00},
                {"description": "Jewelry & Accessory Drawers", "quantity": 1, "unit_price": 3500.00, "total": 3500.00},
                {"description": "Installation & Assembly", "quantity": 1, "unit_price": 2000.00, "total": 2000.00},
            ],
            "currency": "CHF",
            "supplier_name": "Closet Masters",
            "notes": None,
            "change_request_comment": None,
            "pdf_filename": None,
            "pdf_path": None,
            "ai_extraction_confidence": None,
            "parent_document_id": "demo_doc_006",
            "due_date": (now + timedelta(days=20)).isoformat(),
            "paid_date": None,
            "created_at": (now - timedelta(days=7)).isoformat(),
            "updated_at": (now - timedelta(days=7)).isoformat(),
        },
        {
            "document_id": "demo_doc_007",
            "document_number": "INV-2024-0002",
            "type": "invoice",
            "status": "Paid",
            "agent_id": demo_agent_id,
            "client_id": demo_client1_id,
            "buyer_id": demo_buyer1_id,
            "project_id": demo_project_id,
            "unit_reference": "Unit A-301",
            "title": "Wine Cellar Installation",
            "summary": "Climate-controlled wine cellar with custom racking and ambient lighting.",
            "hero_image_url": None,
            "hero_image_path": None,
            "amount": 16200.00,
            "items": [
                {"description": "Climate Control Unit", "quantity": 1, "unit_price": 4500.00, "total": 4500.00},
                {"description": "Custom Wine Racking", "quantity": 1, "unit_price": 8000.00, "total": 8000.00},
                {"description": "LED Lighting System", "quantity": 1, "unit_price": 1200.00, "total": 1200.00},
                {"description": "Installation", "quantity": 1, "unit_price": 2500.00, "total": 2500.00},
            ],
            "currency": "CHF",
            "supplier_name": "Wine Cellar Design",
            "notes": None,
            "change_request_comment": None,
            "pdf_filename": None,
            "pdf_path": None,
            "ai_extraction_confidence": None,
            "parent_document_id": None,
            "due_date": (now - timedelta(days=10)).isoformat(),
            "paid_date": (now - timedelta(days=15)).isoformat(),
            "created_at": (now - timedelta(days=40)).isoformat(),
            "updated_at": (now - timedelta(days=15)).isoformat(),
        },
    ]

    for doc in demo_documents:
        await db.documents.insert_one(doc)

    # ── Activities ──
    demo_activities = [
        {
            "activity_id": "demo_act_001",
            "type": "image",
            "title": "Foundation Complete",
            "content": "Great news! The foundation work for your unit has been completed successfully. The concrete curing process is underway and structural work will begin next week.",
            "file_url": "/api/activities/files/demo/foundation_complete.jpg",
            "file_name": "foundation_complete.jpg",
            "file_size": 19735,
            "file_type": "image",
            "author_id": demo_agent_id,
            "author_role": "agent",
            "project_id": demo_project_id,
            "unit_id": None,
            "created_at": (now - timedelta(days=30)).isoformat(),
            "updated_at": (now - timedelta(days=30)).isoformat(),
        },
        {
            "activity_id": "demo_act_002",
            "type": "file",
            "title": "Updated Floor Plan - Unit A-301",
            "content": "Please find attached the updated floor plan reflecting your requested modifications to the living room layout. The changes include an expanded balcony access and repositioned kitchen island.",
            "file_url": "/api/activities/files/demo/floor_plan_a301.pdf",
            "file_name": "floor_plan_a301.pdf",
            "file_size": 2077,
            "file_type": "pdf",
            "author_id": demo_agent_id,
            "author_role": "agent",
            "project_id": demo_project_id,
            "unit_id": demo_unit1_id,
            "created_at": (now - timedelta(days=20)).isoformat(),
            "updated_at": (now - timedelta(days=20)).isoformat(),
        },
        {
            "activity_id": "demo_act_003",
            "type": "file",
            "title": "Premium Kitchen Upgrade Contract",
            "content": "Attached is the contract for your premium kitchen upgrade package. Please review the terms and let me know if you have any questions before signing.",
            "file_url": "/api/activities/files/demo/contract_upgrade_package.pdf",
            "file_name": "contract_upgrade_package.pdf",
            "file_size": 2152,
            "file_type": "pdf",
            "author_id": demo_agent_id,
            "author_role": "agent",
            "project_id": demo_project_id,
            "unit_id": demo_unit1_id,
            "created_at": (now - timedelta(days=15)).isoformat(),
            "updated_at": (now - timedelta(days=15)).isoformat(),
        },
        {
            "activity_id": "demo_act_004",
            "type": "status",
            "title": "Electrical Rough-In Scheduled",
            "content": "The electrical rough-in for your unit is scheduled for next week. Our technician will begin installing wiring for the smart home system you selected.",
            "file_url": None,
            "file_name": None,
            "file_size": None,
            "file_type": None,
            "author_id": demo_agent_id,
            "author_role": "agent",
            "project_id": demo_project_id,
            "unit_id": demo_unit2_id,
            "created_at": (now - timedelta(days=10)).isoformat(),
            "updated_at": (now - timedelta(days=10)).isoformat(),
        },
        {
            "activity_id": "demo_act_005",
            "type": "message",
            "title": "Action Required: Tile Selection Deadline",
            "content": "Please confirm your bathroom tile selection by Friday. The options we discussed are:\n\n1. Carrara Marble Look (Premium)\n2. Terrazzo Effect (Modern)\n3. Large Format Porcelain (Contemporary)\n\nLet me know your preference and we'll proceed with the order.",
            "file_url": None,
            "file_name": None,
            "file_size": None,
            "file_type": None,
            "author_id": demo_agent_id,
            "author_role": "agent",
            "project_id": demo_project_id,
            "unit_id": demo_unit1_id,
            "created_at": (now - timedelta(days=5)).isoformat(),
            "updated_at": (now - timedelta(days=4)).isoformat(),
        },
        {
            "activity_id": "demo_act_006",
            "type": "file",
            "title": "March Progress Report",
            "content": "Here's your monthly construction progress report. All milestones are on track and we remain on schedule for the planned completion date.",
            "file_url": "/api/activities/files/demo/progress_report_march.pdf",
            "file_name": "progress_report_march.pdf",
            "file_size": 2088,
            "file_type": "pdf",
            "author_id": demo_agent_id,
            "author_role": "agent",
            "project_id": demo_project_id,
            "unit_id": None,
            "created_at": (now - timedelta(days=2)).isoformat(),
            "updated_at": (now - timedelta(days=2)).isoformat(),
        },
    ]

    for activity in demo_activities:
        await db.activities.insert_one(activity)

    # ── Activity Recipients ──
    demo_recipients = [
        {"recipient_id": "demo_rcpt_001", "activity_id": "demo_act_001", "client_id": demo_client1_id, "created_at": (now - timedelta(days=30)).isoformat()},
        {"recipient_id": "demo_rcpt_002", "activity_id": "demo_act_001", "client_id": demo_client2_id, "created_at": (now - timedelta(days=30)).isoformat()},
        {"recipient_id": "demo_rcpt_003", "activity_id": "demo_act_002", "client_id": demo_client1_id, "created_at": (now - timedelta(days=20)).isoformat()},
        {"recipient_id": "demo_rcpt_004", "activity_id": "demo_act_003", "client_id": demo_client1_id, "created_at": (now - timedelta(days=15)).isoformat()},
        {"recipient_id": "demo_rcpt_005", "activity_id": "demo_act_004", "client_id": demo_client2_id, "created_at": (now - timedelta(days=10)).isoformat()},
        {"recipient_id": "demo_rcpt_006", "activity_id": "demo_act_005", "client_id": demo_client1_id, "created_at": (now - timedelta(days=5)).isoformat()},
        {"recipient_id": "demo_rcpt_007", "activity_id": "demo_act_006", "client_id": demo_client1_id, "created_at": (now - timedelta(days=2)).isoformat()},
        {"recipient_id": "demo_rcpt_008", "activity_id": "demo_act_006", "client_id": demo_client2_id, "created_at": (now - timedelta(days=2)).isoformat()},
    ]

    for recipient in demo_recipients:
        await db.activity_recipients.insert_one(recipient)

    # ── Activity Reply ──
    await db.activity_replies.insert_one({
        "reply_id": "demo_reply_001",
        "activity_id": "demo_act_005",
        "author_id": demo_buyer1_id,
        "author_role": "buyer",
        "content": "Thank you for the reminder. I'd like to go with option 1 - the Carrara Marble Look. It matches the kitchen design perfectly.",
        "created_at": (now - timedelta(days=4)).isoformat(),
    })

    # ── Team Members ──
    demo_team = [
        {
            "member_id": "demo_member_001",
            "project_id": demo_project_id,
            "agent_id": demo_agent_id,
            "company_name": "SaniTech SA",
            "contact_name": "Pierre Dupont",
            "role": "Plumber",
            "email": "pierre.dupont@sanitech.ch",
            "phone": "+41 76 555 0101",
            "website": "https://sanitech.ch",
            "notes": "Main plumbing contractor for bathrooms and kitchens",
            "created_at": now.isoformat(),
        },
        {
            "member_id": "demo_member_002",
            "project_id": demo_project_id,
            "agent_id": demo_agent_id,
            "company_name": "ElecPro Sàrl",
            "contact_name": "Marie Fontaine",
            "role": "Electrician",
            "email": "m.fontaine@elecpro.ch",
            "phone": "+41 76 555 0202",
            "website": "https://elecpro.ch",
            "notes": "Smart home specialist, handles all electrical installations",
            "created_at": now.isoformat(),
        },
        {
            "member_id": "demo_member_003",
            "project_id": demo_project_id,
            "agent_id": demo_agent_id,
            "company_name": "Meier Architekten AG",
            "contact_name": "Hans Meier",
            "role": "Architect",
            "email": "hans@meier-architekten.ch",
            "phone": "+41 76 555 0303",
            "website": "https://meier-architekten.ch",
            "notes": "Lead architect for the project",
            "created_at": now.isoformat(),
        },
        {
            "member_id": "demo_member_004",
            "project_id": demo_project_id,
            "agent_id": demo_agent_id,
            "company_name": "Kell Design Studio",
            "contact_name": "Anna Keller",
            "role": "Interior Designer",
            "email": "anna@kelldesign.ch",
            "phone": "+41 76 555 0404",
            "website": None,
            "notes": "Custom interior solutions and material selection",
            "created_at": now.isoformat(),
        },
    ]

    for member in demo_team:
        await db.team_members.insert_one(member)

    # ── Timeline Template ──
    demo_template_id = "demo_tmpl_001"
    await db.timeline_templates.insert_one({
        "template_id": demo_template_id,
        "agent_id": demo_agent_id,
        "name": "Standard Construction",
        "created_at": now.isoformat(),
    })

    template_steps = [
        {"step_id": "demo_tmpl_step_001", "template_id": demo_template_id, "title": "Site Preparation", "description": "Clear and prepare construction site", "order_index": 1},
        {"step_id": "demo_tmpl_step_002", "template_id": demo_template_id, "title": "Excavation", "description": "Excavate foundation area", "order_index": 2},
        {"step_id": "demo_tmpl_step_003", "template_id": demo_template_id, "title": "Foundation", "description": "Pour and cure foundation concrete", "order_index": 3},
        {"step_id": "demo_tmpl_step_004", "template_id": demo_template_id, "title": "Structure", "description": "Build structural framework and walls", "order_index": 4},
        {"step_id": "demo_tmpl_step_005", "template_id": demo_template_id, "title": "Finishes", "description": "Interior and exterior finishing work", "order_index": 5},
    ]
    for step in template_steps:
        await db.timeline_template_steps.insert_one(step)

    # ── Timeline Instance ──
    demo_timeline_id = "demo_timeline_001"
    await db.timelines.insert_one({
        "timeline_id": demo_timeline_id,
        "project_id": demo_project_id,
        "template_id": demo_template_id,
        "created_at": (now - timedelta(days=60)).isoformat(),
    })

    timeline_steps = [
        {
            "step_id": "demo_step_001",
            "timeline_id": demo_timeline_id,
            "title": "Site Preparation",
            "description": "Clear vegetation, mark boundaries, set up site office and safety perimeter",
            "status": "completed",
            "order_index": 1,
            "planned_date": (now - timedelta(days=45)).strftime("%Y-%m-%d"),
            "completed_at": (now - timedelta(days=42)).isoformat(),
            "created_at": (now - timedelta(days=60)).isoformat(),
            "updated_at": (now - timedelta(days=42)).isoformat(),
        },
        {
            "step_id": "demo_step_002",
            "timeline_id": demo_timeline_id,
            "title": "Excavation",
            "description": "Excavate foundation trenches, install drainage, prepare for concrete",
            "status": "completed",
            "order_index": 2,
            "planned_date": (now - timedelta(days=35)).strftime("%Y-%m-%d"),
            "completed_at": (now - timedelta(days=30)).isoformat(),
            "created_at": (now - timedelta(days=60)).isoformat(),
            "updated_at": (now - timedelta(days=30)).isoformat(),
        },
        {
            "step_id": "demo_step_003",
            "timeline_id": demo_timeline_id,
            "title": "Foundation",
            "description": "Reinforcement installation, concrete pour, waterproofing membrane",
            "status": "in_progress",
            "order_index": 3,
            "planned_date": (now - timedelta(days=15)).strftime("%Y-%m-%d"),
            "completed_at": None,
            "created_at": (now - timedelta(days=60)).isoformat(),
            "updated_at": (now - timedelta(days=5)).isoformat(),
        },
        {
            "step_id": "demo_step_004",
            "timeline_id": demo_timeline_id,
            "title": "Structure",
            "description": "Steel framework, load-bearing walls, floor slabs for each level",
            "status": "pending",
            "order_index": 4,
            "planned_date": (now + timedelta(days=15)).strftime("%Y-%m-%d"),
            "completed_at": None,
            "created_at": (now - timedelta(days=60)).isoformat(),
            "updated_at": (now - timedelta(days=60)).isoformat(),
        },
        {
            "step_id": "demo_step_005",
            "timeline_id": demo_timeline_id,
            "title": "Finishes",
            "description": "Plastering, painting, flooring, fixtures, final inspections",
            "status": "pending",
            "order_index": 5,
            "planned_date": (now + timedelta(days=60)).strftime("%Y-%m-%d"),
            "completed_at": None,
            "created_at": (now - timedelta(days=60)).isoformat(),
            "updated_at": (now - timedelta(days=60)).isoformat(),
        },
    ]

    for step in timeline_steps:
        await db.timeline_steps.insert_one(step)

    # Link foundation activity to Foundation step
    await db.timeline_step_documents.insert_one({
        "link_id": "demo_link_001",
        "timeline_step_id": "demo_step_003",
        "activity_id": "demo_act_001",
        "created_at": (now - timedelta(days=5)).isoformat(),
    })

    # Internal note on Foundation step
    await db.timeline_step_internal_notes.insert_one({
        "note_id": "demo_note_001",
        "timeline_step_id": "demo_step_003",
        "author_id": demo_agent_id,
        "content": "Waiting for concrete test results. Expected by end of week.",
        "created_at": (now - timedelta(days=3)).isoformat(),
    })

    return {
        "message": "Demo data seeded successfully",
        "demo_credentials": {
            "agent": {"email": "demo.agent@upgradeflow.com", "password": "demo123"},
            "buyer1": {"name": "Sophie Müller"},
            "buyer2": {"name": "Thomas Weber"},
        },
    }


@router.post("/demo/reset")
async def reset_demo_data():
    """Reset demo data to fresh state"""
    return await seed_demo_data()


# ── Admin Utilities (not demo-specific, kept for operational use) ──

@router.post("/admin/migrate-clients")
async def migrate_client_data(user: dict = Depends(get_current_agent)):
    """
    Migration endpoint to fix clients with missing fields.
    Adds default values for unit_reference and status.
    """
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
    """
    Check data integrity across collections.
    Returns counts of records with missing required fields.
    """
    clients_missing_unit_ref = await db.clients.count_documents({"unit_reference": {"$exists": False}})
    clients_missing_status = await db.clients.count_documents({"status": {"$exists": False}})
    docs_missing_client = await db.documents.count_documents({"client_id": {"$exists": False}})
    docs_missing_project = await db.documents.count_documents({"project_id": {"$exists": False}})

    all_buyers = await db.users.find({"role": "buyer"}, {"_id": 0, "user_id": 1}).to_list(1000)
    buyer_ids = [b['user_id'] for b in all_buyers]
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
