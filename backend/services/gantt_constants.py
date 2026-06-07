"""
Gantt Chart — shared constants (Single Source of Truth for backend + config API).
"""

GANTT_APP_NAME = "Caribbean Regional Connectivity"

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

# Phase bar colors (index order matches cockpit UI palette)
PHASE_CHART_COLORS_HEX = [
    "#3b82f6",
    "#10b981",
    "#f59e0b",
    "#8b5cf6",
    "#f43f5e",
    "#06b6d4",
    "#f97316",
]
PHASE_CHART_STROKES_HEX = [
    "#1d4ed8",
    "#047857",
    "#b45309",
    "#6d28d9",
    "#be123c",
    "#0e7490",
    "#c2410c",
]
