"""
Agent Command Service - Phase 2 Implementation

Architecture:
- Tool Registry: Explicit definitions for each command type
- Interpret: Input → Structured Plan (no side effects)
- Execute: Validated Plan → Draft Object → Confirmation → Live Object

Rules:
- AI never writes to DB directly
- All execution goes through existing services
- Every execution is logged
- Every external action requires confirmation
- No silent failures
"""

import re
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field


# =============================================================================
# ENUMS & CONSTANTS
# =============================================================================

class CommandIntent(str, Enum):
    CREATE_QUOTE = "create_quote"
    CREATE_INVOICE = "create_invoice"
    CREATE_MESSAGE = "create_message"
    # Phase 3: Document extraction intents
    EXTRACT_QUOTE = "extract_quote"
    EXTRACT_INVOICE = "extract_invoice"
    EXTRACT_TIMELINE = "extract_timeline"
    EXTRACT_CONTACTS = "extract_contacts"
    UNKNOWN = "unknown"


class DocumentType(str, Enum):
    """Document types for classification"""
    QUOTE = "quote"
    INVOICE = "invoice"
    TIMELINE = "timeline"
    CONTACTS = "contacts"
    UNKNOWN = "unknown"


class DraftStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    EXECUTED = "executed"
    CANCELLED = "cancelled"
    FAILED = "failed"


# =============================================================================
# PYDANTIC MODELS - Strict Schema
# =============================================================================

class CommandContext(BaseModel):
    """Context provided with a command"""
    project_id: Optional[str] = None
    client_id: Optional[str] = None
    unit_id: Optional[str] = None


class ExtractedField(BaseModel):
    """A field extracted from user input"""
    name: str
    value: Any
    confidence: float = 1.0  # 1.0 = explicit, <1.0 = inferred
    source: str = "user_input"  # user_input, context, default


class MissingField(BaseModel):
    """A required field that was not provided"""
    name: str
    description: str
    required: bool = True
    suggestions: List[str] = []


class CommandPlan(BaseModel):
    """The structured output of command interpretation"""
    plan_id: str = Field(default_factory=lambda: f"plan_{uuid.uuid4().hex[:12]}")
    intent: CommandIntent
    intent_confidence: float = 1.0
    
    # Extracted data
    entities: Dict[str, Any] = {}  # project_name, client_name, etc.
    fields: List[ExtractedField] = []
    missing_fields: List[MissingField] = []
    
    # Validation
    is_valid: bool = False
    validation_errors: List[str] = []
    
    # Execution control
    requires_confirmation: bool = True
    can_execute: bool = False
    
    # Debug info
    raw_command: str = ""
    interpretation_log: List[str] = []
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CommandDraft(BaseModel):
    """A draft object created before execution"""
    draft_id: str = Field(default_factory=lambda: f"draft_{uuid.uuid4().hex[:12]}")
    plan_id: str
    intent: CommandIntent
    status: DraftStatus = DraftStatus.PENDING
    
    # The data to be created
    draft_data: Dict[str, Any] = {}
    
    # Execution tracking
    created_by: str  # user_id
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    confirmed_at: Optional[datetime] = None
    executed_at: Optional[datetime] = None
    
    # Result
    result_id: Optional[str] = None  # ID of created object
    result_type: Optional[str] = None  # quote, invoice, message
    error: Optional[str] = None


class ExecutionLog(BaseModel):
    """Log entry for command execution"""
    log_id: str = Field(default_factory=lambda: f"log_{uuid.uuid4().hex[:12]}")
    draft_id: str
    user_id: str
    action: str  # interpret, confirm, execute, cancel
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    details: Dict[str, Any] = {}
    success: bool = True
    error: Optional[str] = None


# =============================================================================
# TOOL DEFINITIONS - Explicit Registry
# =============================================================================

class ToolDefinition:
    """Base class for tool definitions"""
    
    intent: CommandIntent
    name: str
    description: str
    required_fields: List[Dict[str, Any]]
    optional_fields: List[Dict[str, Any]]
    
    def validate(self, fields: Dict[str, Any], context: CommandContext) -> tuple[bool, List[str]]:
        """Validate extracted fields. Returns (is_valid, error_messages)"""
        raise NotImplementedError
    
    def get_missing_fields(self, fields: Dict[str, Any], context: CommandContext) -> List[MissingField]:
        """Return list of missing required fields"""
        raise NotImplementedError
    
    def build_draft_data(self, fields: Dict[str, Any], context: CommandContext, entities: Dict[str, Any]) -> Dict[str, Any]:
        """Build the draft data structure for this tool"""
        raise NotImplementedError


class CreateQuoteTool(ToolDefinition):
    intent = CommandIntent.CREATE_QUOTE
    name = "create_quote"
    description = "Create a quote/estimate for a client"
    
    required_fields = [
        {"name": "client_id", "type": "string", "description": "Client to create quote for"},
        {"name": "project_id", "type": "string", "description": "Project context"},
    ]
    
    optional_fields = [
        {"name": "title", "type": "string", "description": "Quote title/description"},
        {"name": "amount", "type": "number", "description": "Total amount"},
        {"name": "items", "type": "array", "description": "Line items"},
        {"name": "notes", "type": "string", "description": "Additional notes"},
        {"name": "valid_until", "type": "date", "description": "Quote validity date"},
    ]
    
    def validate(self, fields: Dict[str, Any], context: CommandContext) -> tuple[bool, List[str]]:
        errors = []
        
        # Check required fields
        client_id = fields.get("client_id") or context.client_id
        project_id = fields.get("project_id") or context.project_id
        
        if not client_id:
            errors.append("client_id is required")
        if not project_id:
            errors.append("project_id is required")
        
        # Validate amount if provided
        amount = fields.get("amount")
        if amount is not None:
            try:
                float(amount)
            except (ValueError, TypeError):
                errors.append("amount must be a valid number")
        
        return len(errors) == 0, errors
    
    def get_missing_fields(self, fields: Dict[str, Any], context: CommandContext) -> List[MissingField]:
        missing = []
        
        client_id = fields.get("client_id") or context.client_id
        project_id = fields.get("project_id") or context.project_id
        
        if not client_id:
            missing.append(MissingField(
                name="client_id",
                description="Select a client for this quote",
                required=True
            ))
        
        if not project_id:
            missing.append(MissingField(
                name="project_id",
                description="Select a project context",
                required=True
            ))
        
        # Optional but recommended
        if not fields.get("title"):
            missing.append(MissingField(
                name="title",
                description="Add a title/description for the quote",
                required=False
            ))
        
        if not fields.get("amount") and not fields.get("items"):
            missing.append(MissingField(
                name="amount",
                description="Specify the total amount or add line items",
                required=False
            ))
        
        return missing
    
    def build_draft_data(self, fields: Dict[str, Any], context: CommandContext, entities: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "document_type": "quote",
            "project_id": fields.get("project_id") or context.project_id,
            "client_id": fields.get("client_id") or context.client_id,
            "client_name": entities.get("client_name", ""),
            "project_name": entities.get("project_name", ""),
            "title": fields.get("title", ""),
            "total_amount": fields.get("amount"),
            "items": fields.get("items", []),
            "notes": fields.get("notes", ""),
            "valid_until": fields.get("valid_until"),
            "status": "Draft",
        }


class CreateInvoiceTool(ToolDefinition):
    intent = CommandIntent.CREATE_INVOICE
    name = "create_invoice"
    description = "Create an invoice for a client"
    
    required_fields = [
        {"name": "client_id", "type": "string", "description": "Client to invoice"},
        {"name": "project_id", "type": "string", "description": "Project context"},
    ]
    
    optional_fields = [
        {"name": "title", "type": "string", "description": "Invoice title/description"},
        {"name": "amount", "type": "number", "description": "Total amount"},
        {"name": "items", "type": "array", "description": "Line items"},
        {"name": "due_date", "type": "date", "description": "Payment due date"},
        {"name": "notes", "type": "string", "description": "Additional notes"},
    ]
    
    def validate(self, fields: Dict[str, Any], context: CommandContext) -> tuple[bool, List[str]]:
        errors = []
        
        client_id = fields.get("client_id") or context.client_id
        project_id = fields.get("project_id") or context.project_id
        
        if not client_id:
            errors.append("client_id is required")
        if not project_id:
            errors.append("project_id is required")
        
        amount = fields.get("amount")
        if amount is not None:
            try:
                float(amount)
            except (ValueError, TypeError):
                errors.append("amount must be a valid number")
        
        return len(errors) == 0, errors
    
    def get_missing_fields(self, fields: Dict[str, Any], context: CommandContext) -> List[MissingField]:
        missing = []
        
        client_id = fields.get("client_id") or context.client_id
        project_id = fields.get("project_id") or context.project_id
        
        if not client_id:
            missing.append(MissingField(
                name="client_id",
                description="Select a client for this invoice",
                required=True
            ))
        
        if not project_id:
            missing.append(MissingField(
                name="project_id",
                description="Select a project context",
                required=True
            ))
        
        if not fields.get("title"):
            missing.append(MissingField(
                name="title",
                description="Add a title/description for the invoice",
                required=False
            ))
        
        if not fields.get("amount") and not fields.get("items"):
            missing.append(MissingField(
                name="amount",
                description="Specify the total amount or add line items",
                required=False
            ))
        
        return missing
    
    def build_draft_data(self, fields: Dict[str, Any], context: CommandContext, entities: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "document_type": "invoice",
            "project_id": fields.get("project_id") or context.project_id,
            "client_id": fields.get("client_id") or context.client_id,
            "client_name": entities.get("client_name", ""),
            "project_name": entities.get("project_name", ""),
            "title": fields.get("title", ""),
            "total_amount": fields.get("amount"),
            "items": fields.get("items", []),
            "due_date": fields.get("due_date"),
            "notes": fields.get("notes", ""),
            "status": "Draft",
        }


class CreateMessageTool(ToolDefinition):
    intent = CommandIntent.CREATE_MESSAGE
    name = "create_message"
    description = "Send a message/update to clients via the feed"
    
    required_fields = [
        {"name": "content", "type": "string", "description": "Message content"},
        {"name": "project_id", "type": "string", "description": "Project context"},
    ]
    
    optional_fields = [
        {"name": "client_id", "type": "string", "description": "Specific client (or broadcast to all)"},
        {"name": "title", "type": "string", "description": "Message title"},
        {"name": "activity_type", "type": "string", "description": "Type: update, milestone, announcement"},
    ]
    
    def validate(self, fields: Dict[str, Any], context: CommandContext) -> tuple[bool, List[str]]:
        errors = []
        
        content = fields.get("content")
        project_id = fields.get("project_id") or context.project_id
        
        if not content or len(str(content).strip()) == 0:
            errors.append("Message content is required")
        
        if not project_id:
            errors.append("project_id is required")
        
        return len(errors) == 0, errors
    
    def get_missing_fields(self, fields: Dict[str, Any], context: CommandContext) -> List[MissingField]:
        missing = []
        
        project_id = fields.get("project_id") or context.project_id
        
        if not fields.get("content"):
            missing.append(MissingField(
                name="content",
                description="Enter the message content",
                required=True
            ))
        
        if not project_id:
            missing.append(MissingField(
                name="project_id",
                description="Select a project to post to",
                required=True
            ))
        
        return missing
    
    def build_draft_data(self, fields: Dict[str, Any], context: CommandContext, entities: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "activity_type": fields.get("activity_type", "update"),
            "project_id": fields.get("project_id") or context.project_id,
            "client_id": fields.get("client_id") or context.client_id,
            "title": fields.get("title", ""),
            "content": fields.get("content", ""),
            "project_name": entities.get("project_name", ""),
        }


# =============================================================================
# DOCUMENT EXTRACTION TOOLS - Phase 3
# =============================================================================

class ExtractQuoteTool(ToolDefinition):
    """Extract quote data from uploaded document"""
    intent = CommandIntent.EXTRACT_QUOTE
    name = "extract_quote"
    description = "Extract quote/estimate data from an uploaded document"
    
    required_fields = [
        {"name": "file_path", "type": "string", "description": "Path to uploaded document"},
        {"name": "project_id", "type": "string", "description": "Project context"},
    ]
    
    optional_fields = [
        {"name": "client_id", "type": "string", "description": "Client to associate quote with"},
    ]
    
    def validate(self, fields: Dict[str, Any], context: CommandContext) -> tuple[bool, List[str]]:
        errors = []
        if not fields.get("file_path"):
            errors.append("No document uploaded")
        project_id = fields.get("project_id") or context.project_id
        if not project_id:
            errors.append("project_id is required")
        return len(errors) == 0, errors
    
    def get_missing_fields(self, fields: Dict[str, Any], context: CommandContext) -> List[MissingField]:
        missing = []
        if not fields.get("file_path"):
            missing.append(MissingField(name="file_path", description="Upload a document", required=True))
        if not (fields.get("project_id") or context.project_id):
            missing.append(MissingField(name="project_id", description="Select a project", required=True))
        return missing
    
    def build_draft_data(self, fields: Dict[str, Any], context: CommandContext, entities: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "document_type": "quote",
            "project_id": fields.get("project_id") or context.project_id,
            "client_id": fields.get("client_id") or context.client_id,
            "extracted_data": fields.get("extracted_data", {}),
            "source_file": fields.get("file_path"),
        }


class ExtractInvoiceTool(ToolDefinition):
    """Extract invoice data from uploaded document"""
    intent = CommandIntent.EXTRACT_INVOICE
    name = "extract_invoice"
    description = "Extract invoice data from an uploaded document"
    
    required_fields = [
        {"name": "file_path", "type": "string", "description": "Path to uploaded document"},
        {"name": "project_id", "type": "string", "description": "Project context"},
    ]
    
    optional_fields = [
        {"name": "client_id", "type": "string", "description": "Client to associate invoice with"},
    ]
    
    def validate(self, fields: Dict[str, Any], context: CommandContext) -> tuple[bool, List[str]]:
        errors = []
        if not fields.get("file_path"):
            errors.append("No document uploaded")
        project_id = fields.get("project_id") or context.project_id
        if not project_id:
            errors.append("project_id is required")
        return len(errors) == 0, errors
    
    def get_missing_fields(self, fields: Dict[str, Any], context: CommandContext) -> List[MissingField]:
        missing = []
        if not fields.get("file_path"):
            missing.append(MissingField(name="file_path", description="Upload a document", required=True))
        if not (fields.get("project_id") or context.project_id):
            missing.append(MissingField(name="project_id", description="Select a project", required=True))
        return missing
    
    def build_draft_data(self, fields: Dict[str, Any], context: CommandContext, entities: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "document_type": "invoice",
            "project_id": fields.get("project_id") or context.project_id,
            "client_id": fields.get("client_id") or context.client_id,
            "extracted_data": fields.get("extracted_data", {}),
            "source_file": fields.get("file_path"),
        }


class ExtractTimelineTool(ToolDefinition):
    """Extract timeline/schedule from uploaded document"""
    intent = CommandIntent.EXTRACT_TIMELINE
    name = "extract_timeline"
    description = "Extract project timeline/schedule from an uploaded document"
    
    required_fields = [
        {"name": "file_path", "type": "string", "description": "Path to uploaded document"},
        {"name": "project_id", "type": "string", "description": "Project to add timeline to"},
    ]
    
    optional_fields = []
    
    def validate(self, fields: Dict[str, Any], context: CommandContext) -> tuple[bool, List[str]]:
        errors = []
        if not fields.get("file_path"):
            errors.append("No document uploaded")
        project_id = fields.get("project_id") or context.project_id
        if not project_id:
            errors.append("project_id is required")
        return len(errors) == 0, errors
    
    def get_missing_fields(self, fields: Dict[str, Any], context: CommandContext) -> List[MissingField]:
        missing = []
        if not fields.get("file_path"):
            missing.append(MissingField(name="file_path", description="Upload a document", required=True))
        if not (fields.get("project_id") or context.project_id):
            missing.append(MissingField(name="project_id", description="Select a project", required=True))
        return missing
    
    def build_draft_data(self, fields: Dict[str, Any], context: CommandContext, entities: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "document_type": "timeline",
            "project_id": fields.get("project_id") or context.project_id,
            "extracted_data": fields.get("extracted_data", {}),
            "source_file": fields.get("file_path"),
        }


class ExtractContactsTool(ToolDefinition):
    """Extract contacts from uploaded document"""
    intent = CommandIntent.EXTRACT_CONTACTS
    name = "extract_contacts"
    description = "Extract contact list from an uploaded document"
    
    required_fields = [
        {"name": "file_path", "type": "string", "description": "Path to uploaded document"},
    ]
    
    optional_fields = [
        {"name": "project_id", "type": "string", "description": "Project to associate contacts with"},
    ]
    
    def validate(self, fields: Dict[str, Any], context: CommandContext) -> tuple[bool, List[str]]:
        errors = []
        if not fields.get("file_path"):
            errors.append("No document uploaded")
        return len(errors) == 0, errors
    
    def get_missing_fields(self, fields: Dict[str, Any], context: CommandContext) -> List[MissingField]:
        missing = []
        if not fields.get("file_path"):
            missing.append(MissingField(name="file_path", description="Upload a document", required=True))
        return missing
    
    def build_draft_data(self, fields: Dict[str, Any], context: CommandContext, entities: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "document_type": "contacts",
            "project_id": fields.get("project_id") or context.project_id,
            "extracted_data": fields.get("extracted_data", {}),
            "source_file": fields.get("file_path"),
        }


# =============================================================================
# TOOL REGISTRY
# =============================================================================

TOOL_REGISTRY: Dict[CommandIntent, ToolDefinition] = {
    CommandIntent.CREATE_QUOTE: CreateQuoteTool(),
    CommandIntent.CREATE_INVOICE: CreateInvoiceTool(),
    CommandIntent.CREATE_MESSAGE: CreateMessageTool(),
    # Phase 3: Document extraction tools
    CommandIntent.EXTRACT_QUOTE: ExtractQuoteTool(),
    CommandIntent.EXTRACT_INVOICE: ExtractInvoiceTool(),
    CommandIntent.EXTRACT_TIMELINE: ExtractTimelineTool(),
    CommandIntent.EXTRACT_CONTACTS: ExtractContactsTool(),
}


def get_tool(intent: CommandIntent) -> Optional[ToolDefinition]:
    """Get tool definition by intent"""
    return TOOL_REGISTRY.get(intent)


# =============================================================================
# INTENT CLASSIFICATION - Rule-based for determinism
# =============================================================================

# Intent patterns - explicit keyword matching
INTENT_PATTERNS = {
    CommandIntent.CREATE_INVOICE: [
        r'\b(invoice|facture|bill|billing|rechnung)\b',
        r'\b(create|make|generate|new)\b.*\b(invoice|facture|bill)\b',
    ],
    CommandIntent.CREATE_QUOTE: [
        r'\b(quote|estimate|devis|offerte|quotation|proposal)\b',
        r'\b(create|make|generate|new)\b.*\b(quote|estimate|devis|offerte)\b',
    ],
    CommandIntent.CREATE_MESSAGE: [
        r'\b(message|send|post|announce|update|notify)\b',
        r'\b(send|post)\b.*\b(message|update|announcement)\b',
        r'\btell\b.*\b(client|buyer|customer)\b',
    ],
}


def classify_intent(text: str) -> tuple[CommandIntent, float]:
    """
    Classify intent from text using rule-based matching.
    Returns (intent, confidence).
    
    Confidence levels:
    - 1.0: Exact match with explicit keywords
    - 0.8: Partial match
    - 0.5: Inferred from context
    - 0.0: Unknown
    """
    text_lower = text.lower().strip()
    
    scores = {}
    
    for intent, patterns in INTENT_PATTERNS.items():
        max_score = 0.0
        for pattern in patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                # Check if it's an explicit command vs. mention
                if re.search(r'^(create|make|generate|send|post|new)\b', text_lower):
                    max_score = max(max_score, 1.0)
                else:
                    max_score = max(max_score, 0.8)
        scores[intent] = max_score
    
    # Find best match
    best_intent = CommandIntent.UNKNOWN
    best_score = 0.0
    
    for intent, score in scores.items():
        if score > best_score:
            best_score = score
            best_intent = intent
    
    return best_intent, best_score


# =============================================================================
# FIELD EXTRACTION - Explicit patterns only
# =============================================================================

def extract_amount(text: str) -> Optional[float]:
    """
    Extract monetary amount from text.
    Handles both comma-as-decimal (European: 10,50) and comma-as-thousands (10,000).
    """
    # Patterns ordered from most specific to least specific
    patterns = [
        # Thousands separator formats (most specific first)
        r'(\d{1,3}(?:[,\']\d{3})+(?:\.\d{1,2})?)\s*(?:chf|eur|usd|\$|€|fr\.?)\b',  # 10,000.00 CHF
        r'(?:chf|eur|usd|\$|€)\s*(\d{1,3}(?:[,\']\d{3})+(?:\.\d{1,2})?)',  # CHF 10,000.00
        r'(\d{1,3}(?:[,\']\d{3})+(?:\.\d{1,2})?)\s*(?:francs?|euros?|dollars?)\b',  # 10,000 francs
        # European format with dot as thousands, comma as decimal
        r'(\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?)\s*(?:chf|eur|usd|\$|€|fr\.?)\b',  # 10.000,50 CHF
        # European decimal (comma as decimal, no thousands separator)
        r'(\d+,\d{1,2})\s*(?:chf|eur|usd|\$|€|fr\.?)\b',  # 10,50 CHF (comma required)
        # Standard decimal formats
        r'(\d+\.\d{1,2})\s*(?:chf|eur|usd|\$|€|fr\.?)\b',  # 10.50 CHF
        r'(?:chf|eur|usd|\$|€)\s*(\d+\.\d{1,2})',  # CHF 10.50
        r'(\d+\.\d{1,2})\s*(?:francs?|euros?|dollars?)\b',  # 10.50 francs
        # Whole numbers (least specific)
        r'(\d+)\s*(?:chf|eur|usd|\$|€|fr\.?)\b',  # 100 CHF
        r'(?:chf|eur|usd|\$|€)\s*(\d+)\b',  # CHF 100
        r'(\d+)\s*(?:francs?|euros?|dollars?)\b',  # 100 francs
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            amount_str = match.group(1)
            
            # Normalize the number based on format detected
            # Check if comma is thousands separator (pattern: 1,000 or 10,000,000)
            if re.match(r'^\d{1,3}(?:[,\']\d{3})+(?:\.\d{1,2})?$', amount_str):
                # Thousands separator format: remove commas and apostrophes
                amount_str = amount_str.replace(',', '').replace("'", '')
            elif re.match(r'^\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?$', amount_str):
                # European format: 10.000,50 (dot as thousands, comma as decimal)
                amount_str = amount_str.replace('.', '').replace(',', '.')
            elif re.match(r'^\d+,\d{1,2}$', amount_str):
                # European decimal: 10,50 (comma as decimal)
                amount_str = amount_str.replace(',', '.')
            
            try:
                return float(amount_str)
            except ValueError:
                continue
    
    return None


def extract_content_after_keyword(text: str, keywords: List[str]) -> Optional[str]:
    """Extract text content after certain keywords"""
    for keyword in keywords:
        pattern = rf'{keyword}\s*[:\-]?\s*["\']?(.+?)["\']?$'
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


def extract_fields_from_text(text: str, intent: CommandIntent) -> List[ExtractedField]:
    """
    Extract fields from command text.
    Only extracts explicitly mentioned values - does NOT guess.
    """
    fields = []
    
    # Extract amount (common to quotes and invoices)
    if intent in [CommandIntent.CREATE_QUOTE, CommandIntent.CREATE_INVOICE]:
        amount = extract_amount(text)
        if amount is not None:
            fields.append(ExtractedField(
                name="amount",
                value=amount,
                confidence=1.0,
                source="user_input"
            ))
    
    # Extract title/description
    title_keywords = ["for", "titled", "about", "regarding", "re:"]
    title = extract_content_after_keyword(text, title_keywords)
    if title and len(title) > 3:
        # Clean up common trailing words
        title = re.sub(r'\s+(at|for|of)\s+\d+.*$', '', title, flags=re.IGNORECASE)
        if len(title) > 3:
            fields.append(ExtractedField(
                name="title",
                value=title,
                confidence=0.8,
                source="user_input"
            ))
    
    # Extract message content for messages
    if intent == CommandIntent.CREATE_MESSAGE:
        # Look for quoted content or content after keywords
        quoted = re.search(r'["\'](.+?)["\']', text)
        if quoted:
            fields.append(ExtractedField(
                name="content",
                value=quoted.group(1),
                confidence=1.0,
                source="user_input"
            ))
        else:
            # Extract content after message-related keywords
            content = extract_content_after_keyword(text, ["saying", "message", "that"])
            if content:
                fields.append(ExtractedField(
                    name="content",
                    value=content,
                    confidence=0.7,
                    source="user_input"
                ))
    
    return fields


# =============================================================================
# DOCUMENT CLASSIFICATION - Rule-based first, AI fallback
# =============================================================================

# Classification patterns - keywords and layout hints
DOCUMENT_PATTERNS = {
    DocumentType.INVOICE: {
        "keywords": [
            r'\binvoice\b', r'\bfacture\b', r'\brechnung\b', r'\bbill\b',
            r'\binv[\-\s]?\d+', r'\binvoice\s*(no|number|#)',
            r'\bamount\s*due\b', r'\bpayment\s*due\b', r'\bdue\s*date\b',
            r'\btotal\s*due\b', r'\bbalance\s*due\b'
        ],
        "weight": 1.0
    },
    DocumentType.QUOTE: {
        "keywords": [
            r'\bquote\b', r'\bquotation\b', r'\bestimate\b', r'\bdevis\b',
            r'\bofferte\b', r'\bproposal\b', r'\bkosten\s*voranschlag\b',
            r'\bvalid\s*(until|for)\b', r'\bquote\s*(no|number|#)',
            r'\bestimated\s*cost\b'
        ],
        "weight": 1.0
    },
    DocumentType.TIMELINE: {
        "keywords": [
            r'\btimeline\b', r'\bschedule\b', r'\bplanning\b', r'\bplanner\b',
            r'\bphase\s*\d+\b', r'\bstage\s*\d+\b', r'\bmilestone\b',
            r'\bgantt\b', r'\bproject\s*plan\b', r'\bdelivery\s*schedule\b',
            r'q[1-4]\s*20\d{2}', r'\bweek\s*\d+\b'
        ],
        "weight": 1.0
    },
    DocumentType.CONTACTS: {
        "keywords": [
            r'\bcontact\s*list\b', r'\bdirectory\b', r'\bteam\s*members?\b',
            r'\bsuppliers?\s*list\b', r'\bsubcontractors?\b', r'\bvendors?\b',
            r'@[\w\.-]+\.\w+',  # Email patterns
            r'\+?\d{2,3}[\s\-]?\d{3}[\s\-]?\d{3,4}',  # Phone patterns
        ],
        "weight": 0.8
    }
}


def classify_document(text: str, filename: str = "") -> tuple[DocumentType, float]:
    """
    Classify document type using rule-based pattern matching.
    Returns (document_type, confidence).
    
    Confidence levels:
    - 0.9+: Multiple strong indicators
    - 0.7-0.9: Clear keyword match
    - 0.5-0.7: Weak indicators
    - <0.5: Uncertain/unknown
    """
    text_lower = text.lower()
    filename_lower = filename.lower()
    
    scores = {}
    
    for doc_type, config in DOCUMENT_PATTERNS.items():
        score = 0.0
        matches = 0
        
        for pattern in config["keywords"]:
            # Check in text
            text_matches = len(re.findall(pattern, text_lower, re.IGNORECASE))
            if text_matches > 0:
                matches += text_matches
                score += 0.3 * min(text_matches, 3)  # Cap contribution
            
            # Check in filename (stronger signal)
            if re.search(pattern, filename_lower, re.IGNORECASE):
                score += 0.4
        
        # Normalize and apply weight
        if matches > 0:
            score = min(score, 1.0) * config["weight"]
        
        scores[doc_type] = score
    
    # Find best match
    best_type = DocumentType.UNKNOWN
    best_score = 0.3  # Minimum threshold
    
    for doc_type, score in scores.items():
        if score > best_score:
            best_score = score
            best_type = doc_type
    
    return best_type, min(best_score, 0.95)


# =============================================================================
# DOCUMENT EXTRACTION MODELS
# =============================================================================

class ExtractedQuote(BaseModel):
    """Structured quote extraction result"""
    supplier_name: Optional[str] = None
    total_amount: Optional[float] = None
    currency: str = "CHF"
    description: Optional[str] = None
    valid_until: Optional[str] = None  # Keep as text
    line_items: List[Dict[str, Any]] = []
    reference_number: Optional[str] = None
    confidence: float = 0.0


class ExtractedInvoice(BaseModel):
    """Structured invoice extraction result"""
    supplier_name: Optional[str] = None
    total_amount: Optional[float] = None
    currency: str = "CHF"
    due_date: Optional[str] = None  # Keep as text
    reference_number: Optional[str] = None
    description: Optional[str] = None
    line_items: List[Dict[str, Any]] = []
    confidence: float = 0.0


class ExtractedTimeline(BaseModel):
    """Structured timeline extraction result"""
    stages: List[Dict[str, Any]] = []  # {name, date_text, description}
    project_duration: Optional[str] = None  # Keep as text: "6 months", "Q1-Q3 2025"
    confidence: float = 0.0


class ExtractedContact(BaseModel):
    """Single contact extraction"""
    name: str
    role: Optional[str] = None
    company: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    confidence: float = 0.0


class ExtractedContacts(BaseModel):
    """Batch contact extraction result"""
    contacts: List[ExtractedContact] = []
    source_document: Optional[str] = None
    confidence: float = 0.0


# =============================================================================
# COMMAND INTERPRETER
# =============================================================================

class CommandInterpreter:
    """
    Interprets user commands into structured plans.
    No side effects - pure function.
    """
    
    def __init__(self, db=None):
        self.db = db
    
    async def interpret(
        self,
        command_text: str,
        context: CommandContext,
        user_id: str,
        attachments: List[Dict] = None
    ) -> CommandPlan:
        """
        Interpret a command into a structured plan.
        
        Returns a CommandPlan with:
        - Detected intent
        - Extracted fields
        - Missing fields
        - Validation status
        """
        log = []
        log.append(f"Input: {command_text[:100]}...")
        
        # Step 1: Classify intent
        intent, confidence = classify_intent(command_text)
        log.append(f"Intent: {intent.value} (confidence: {confidence})")
        
        # Step 2: Get tool definition
        tool = get_tool(intent)
        
        if not tool:
            return CommandPlan(
                intent=CommandIntent.UNKNOWN,
                intent_confidence=0.0,
                is_valid=False,
                can_execute=False,
                validation_errors=["Could not determine command intent"],
                raw_command=command_text,
                interpretation_log=log
            )
        
        # Step 3: Extract fields from text
        extracted = extract_fields_from_text(command_text, intent)
        log.append(f"Extracted {len(extracted)} fields from text")
        
        # Step 4: Resolve entities from context
        entities = await self._resolve_entities(context)
        log.append(f"Resolved entities: {list(entities.keys())}")
        
        # Step 5: Build fields dict
        fields_dict = {f.name: f.value for f in extracted}
        
        # Add context-derived fields
        if context.project_id and "project_id" not in fields_dict:
            extracted.append(ExtractedField(
                name="project_id",
                value=context.project_id,
                confidence=1.0,
                source="context"
            ))
            fields_dict["project_id"] = context.project_id
        
        if context.client_id and "client_id" not in fields_dict:
            extracted.append(ExtractedField(
                name="client_id",
                value=context.client_id,
                confidence=1.0,
                source="context"
            ))
            fields_dict["client_id"] = context.client_id
        
        # Step 6: Validate
        is_valid, validation_errors = tool.validate(fields_dict, context)
        log.append(f"Validation: {'passed' if is_valid else 'failed'}")
        
        # Step 7: Get missing fields
        missing = tool.get_missing_fields(fields_dict, context)
        required_missing = [m for m in missing if m.required]
        log.append(f"Missing required fields: {len(required_missing)}")
        
        # Determine if can execute
        can_execute = is_valid and len(required_missing) == 0
        
        return CommandPlan(
            intent=intent,
            intent_confidence=confidence,
            entities=entities,
            fields=extracted,
            missing_fields=missing,
            is_valid=is_valid,
            validation_errors=validation_errors,
            requires_confirmation=True,  # Always require confirmation
            can_execute=can_execute,
            raw_command=command_text,
            interpretation_log=log
        )
    
    async def _resolve_entities(self, context: CommandContext) -> Dict[str, Any]:
        """Resolve entity names from IDs"""
        entities = {}
        
        if self.db is None:
            return entities
        
        try:
            if context.project_id:
                project = await self.db.projects.find_one(
                    {"project_id": context.project_id},
                    {"name": 1}
                )
                if project:
                    entities["project_name"] = project.get("name", "")
                    entities["project_id"] = context.project_id
            
            if context.client_id:
                client = await self.db.clients.find_one(
                    {"client_id": context.client_id},
                    {"name": 1}
                )
                if client:
                    entities["client_name"] = client.get("name", "")
                    entities["client_id"] = context.client_id
        except Exception as e:
            # Log but don't fail
            print(f"Entity resolution error: {e}")
        
        return entities


# =============================================================================
# COMMAND EXECUTOR — Pure routing to canonical services.
# No direct DB writes for domain objects. Only manages drafts/logs.
# =============================================================================

class CommandExecutor:
    """
    Executes validated command plans by routing to canonical services.
    Manages draft lifecycle (create/confirm/execute/cancel/fail).
    Does NOT write documents or activities directly.
    """
    
    def __init__(self, db):
        self.db = db
    
    async def create_draft(
        self,
        plan: CommandPlan,
        user_id: str
    ) -> CommandDraft:
        """
        Create a draft from a validated plan.
        Does NOT create the actual object yet.
        """
        tool = get_tool(plan.intent)
        if not tool:
            raise ValueError(f"No tool for intent: {plan.intent}")
        
        # Build draft data
        fields_dict = {f.name: f.value for f in plan.fields}
        context = CommandContext(
            project_id=plan.entities.get("project_id"),
            client_id=plan.entities.get("client_id")
        )
        
        draft_data = tool.build_draft_data(fields_dict, context, plan.entities)
        
        draft = CommandDraft(
            plan_id=plan.plan_id,
            intent=plan.intent,
            status=DraftStatus.PENDING,
            draft_data=draft_data,
            created_by=user_id
        )
        
        # Store draft in DB (draft management is orchestration's responsibility)
        await self.db.command_drafts.insert_one(draft.model_dump())
        
        # Log the action
        await self._log_action(draft.draft_id, user_id, "create_draft", {
            "plan_id": plan.plan_id,
            "intent": plan.intent.value
        })
        
        return draft
    
    async def execute_draft(
        self,
        draft_id: str,
        user_id: str,
        confirmed: bool = True,
    ) -> Dict[str, Any]:
        """
        Execute a confirmed draft by routing to canonical services.
        """
        # Fetch draft
        draft_doc = await self.db.command_drafts.find_one({"draft_id": draft_id})
        if not draft_doc:
            raise ValueError(f"Draft not found: {draft_id}")
        
        draft = CommandDraft(**draft_doc)
        
        # Verify status
        if draft.status != DraftStatus.PENDING:
            raise ValueError(f"Draft cannot be executed (status: {draft.status})")
        
        # Verify ownership
        if draft.created_by != user_id:
            raise ValueError("Not authorized to execute this draft")
        
        if not confirmed:
            # Cancel the draft
            await self.db.command_drafts.update_one(
                {"draft_id": draft_id},
                {"$set": {"status": DraftStatus.CANCELLED.value}}
            )
            await self._log_action(draft_id, user_id, "cancel", {})
            return {"status": "cancelled", "draft_id": draft_id}
        
        # Mark as confirmed
        await self.db.command_drafts.update_one(
            {"draft_id": draft_id},
            {"$set": {
                "status": DraftStatus.CONFIRMED.value,
                "confirmed_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        
        # Route to canonical service
        try:
            result = await self._route_to_service(draft, user_id)
            
            # Mark as executed
            await self.db.command_drafts.update_one(
                {"draft_id": draft_id},
                {"$set": {
                    "status": DraftStatus.EXECUTED.value,
                    "executed_at": datetime.now(timezone.utc).isoformat(),
                    "result_id": result.get("id"),
                    "result_type": result.get("type")
                }}
            )
            
            await self._log_action(draft_id, user_id, "execute", {
                "result_id": result.get("id"),
                "result_type": result.get("type")
            })
            
            return {
                "status": "executed",
                "draft_id": draft_id,
                "result": result
            }
            
        except Exception as e:
            # Mark as failed
            await self.db.command_drafts.update_one(
                {"draft_id": draft_id},
                {"$set": {
                    "status": DraftStatus.FAILED.value,
                    "error": str(e)
                }}
            )
            
            await self._log_action(draft_id, user_id, "execute_failed", {
                "error": str(e)
            }, success=False, error=str(e))
            
            raise
    
    async def _route_to_service(self, draft: CommandDraft, user_id: str) -> Dict[str, Any]:
        """Route draft execution to the correct canonical service."""
        data = draft.draft_data

        if draft.intent in (
            CommandIntent.CREATE_QUOTE,
            CommandIntent.CREATE_INVOICE,
            CommandIntent.EXTRACT_QUOTE,
            CommandIntent.EXTRACT_INVOICE,
        ):
            return await self._route_document(data, user_id)

        if draft.intent == CommandIntent.CREATE_MESSAGE:
            return await self._route_activity(data, user_id)

        raise ValueError(f"Unknown intent: {draft.intent}")

    async def _route_document(self, data: Dict, user_id: str) -> Dict[str, Any]:
        """Delegate document creation to document_service."""
        from services.document_service import create_document

        doc_type = data.get("document_type", "quote")
        client_id = data.get("client_id")
        if not client_id:
            raise ValueError("client_id is required to create a document")

        # Map extracted_data fields for extraction intents
        extracted = data.get("extracted_data", {})
        title = data.get("title") or extracted.get("description") or ""
        amount = data.get("total_amount") or extracted.get("total_amount") or 0
        items = data.get("items") or extracted.get("line_items", [])
        supplier_name = data.get("supplier_name") or extracted.get("supplier_name")
        notes = data.get("notes") or extracted.get("notes")
        due_date = data.get("due_date") or extracted.get("due_date")

        doc = await create_document(
            agent_id=user_id,
            doc_type=doc_type,
            client_id=client_id,
            title=title,
            amount=float(amount) if amount else 0,
            items=items,
            supplier_name=supplier_name,
            notes=notes,
            due_date=due_date,
        )

        return {
            "type": doc_type,
            "id": doc["document_id"],
            "number": doc["document_number"],
            "redirect": f"/agent/{doc_type}s/{doc['document_id']}",
        }

    async def _route_activity(self, data: Dict, user_id: str) -> Dict[str, Any]:
        """Delegate draft activity creation to activity_service."""
        from services.activity_service import create_draft_activity

        project_id = data.get("project_id")
        if not project_id:
            raise ValueError("project_id is required to create a message")

        recipient_ids = [data["client_id"]] if data.get("client_id") else []

        activity = await create_draft_activity(
            author_id=user_id,
            project_id=project_id,
            title=data.get("title"),
            content=data.get("content"),
            recipient_client_ids=recipient_ids,
        )

        return {
            "type": "message_draft",
            "id": activity["activity_id"],
            "message": "Message draft created. Please review and send from the Feed page.",
            "redirect": f"/agent/feed?draft={activity['activity_id']}",
        }
    
    async def _log_action(
        self,
        draft_id: str,
        user_id: str,
        action: str,
        details: Dict,
        success: bool = True,
        error: str = None
    ):
        """Log an execution action"""
        log = ExecutionLog(
            draft_id=draft_id,
            user_id=user_id,
            action=action,
            details=details,
            success=success,
            error=error
        )
        await self.db.command_logs.insert_one(log.model_dump())
