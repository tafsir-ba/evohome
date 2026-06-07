"""
Gantt Chart — shared constants (Single Source of Truth for backend + config API).
"""

ALLOWED_UPLOAD_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".csv", ".xlsx"}
MAX_UPLOAD_SIZE_BYTES = 15 * 1024 * 1024
UPLOAD_RETENTION_HOURS = 24
GANTT_TEMP_SUBDIR = "gantt_temp"
GANTT_REVIEW_MESSAGE = (
    "AI will attempt to extract a draft schedule. "
    "Please review all dates, tasks, and dependencies before confirming."
)
LOW_CONFIDENCE_THRESHOLD = 0.6
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
GANTT_EXTRACTION_MODEL = "gpt-5.4"
