"""
Gantt Chart — isolated file parsers for draft extraction (Phase 3).
No CMP coupling; each parser returns GanttDraftTask-shaped dicts.
"""
import csv
import json
import logging
import os
import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import fitz  # PyMuPDF

from services.gantt_constants import LOW_CONFIDENCE_THRESHOLD
from services.ai_service import OPENAI_API_KEY

logger = logging.getLogger(__name__)

GANTT_AI_SYSTEM_PROMPT = """You extract Gantt chart / project schedule data from documents.

Return ONLY a JSON object with this shape:
{
  "tasks": [
    {
      "temp_id": "t1",
      "type": "task" | "milestone",
      "phase": "optional phase name",
      "title": "Task title",
      "description": "optional",
      "start_date": "YYYY-MM-DD or null",
      "end_date": "YYYY-MM-DD or null",
      "status": "not_started",
      "responsible_party": "optional",
      "dependencies": [{"temp_task_id": "t0", "type": "finish_to_start"}],
      "field_confidence": {"title": 0.0-1.0, "start_date": 0.0-1.0, "end_date": 0.0-1.0},
      "warnings": ["optional per-task warnings"]
    }
  ],
  "warnings": ["global warnings"]
}

Rules:
- Use unique temp_id values (t1, t2, ...).
- Dates must be YYYY-MM-DD when confident; null when uncertain.
- finish_to_start dependencies only; temp_task_id must reference another temp_id in tasks.
- Milestones: start_date required, end_date equals start_date.
- field_confidence: 0.0-1.0 per extracted field; use <= 0.5 when guessing.
- Include warnings for ambiguous dates, missing dependencies, or unclear titles."""


def _make_temp_id(index: int) -> str:
    return f"t{index + 1}"


def _normalize_date(value: Optional[str]) -> Tuple[Optional[str], float, List[str]]:
    """Try to normalize a date string; return (iso_date, confidence, warnings)."""
    warnings: List[str] = []
    if not value or not str(value).strip():
        return None, 0.0, warnings

    raw = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d"), 0.95, warnings
        except ValueError:
            continue

    warnings.append(f"Could not parse date: {raw}")
    return None, 0.3, warnings


def _apply_low_confidence_flags(task: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure low-confidence fields produce warnings in the task."""
    confidence = task.get("field_confidence") or {}
    warnings = list(task.get("warnings") or [])
    for field, score in confidence.items():
        if isinstance(score, (int, float)) and score < LOW_CONFIDENCE_THRESHOLD:
            warnings.append(f"Low confidence for {field} ({score:.0%})")
    task["warnings"] = warnings
    return task


def _normalize_ai_tasks(raw_tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for index, raw in enumerate(raw_tasks):
        task = {
            "temp_id": raw.get("temp_id") or _make_temp_id(index),
            "type": raw.get("type", "task"),
            "phase": raw.get("phase"),
            "title": raw.get("title") or f"Untitled task {index + 1}",
            "description": raw.get("description"),
            "start_date": raw.get("start_date"),
            "end_date": raw.get("end_date"),
            "duration_days": raw.get("duration_days"),
            "status": raw.get("status", "not_started"),
            "responsible_party": raw.get("responsible_party"),
            "dependencies": raw.get("dependencies") or [],
            "field_confidence": raw.get("field_confidence") or {},
            "warnings": raw.get("warnings") or [],
        }
        normalized.append(_apply_low_confidence_flags(task))
    return normalized


def _parse_ai_json_response(response_text: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    json_match = re.search(r"\{[\s\S]*\}", response_text)
    if not json_match:
        return [], ["AI response did not contain valid JSON"]
    try:
        payload = json.loads(json_match.group())
    except json.JSONDecodeError:
        return [], ["AI response JSON could not be parsed"]
    tasks = _normalize_ai_tasks(payload.get("tasks") or [])
    warnings = list(payload.get("warnings") or [])
    return tasks, warnings


async def parse_pdf_text(file_path: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Extract draft tasks from a PDF with a text layer via PyMuPDF + GPT-4o."""
    warnings: List[str] = []
    try:
        doc = fitz.open(file_path)
        text_content = "".join(page.get_text() for page in doc)
        doc.close()
    except Exception as exc:
        logger.error("PDF text extraction failed: %s", exc)
        return [], [f"PDF read failed: {exc}"]

    if not text_content.strip():
        return [], ["PDF contains no extractable text; try uploading a scanned image instead"]

    if not OPENAI_API_KEY:
        warnings.append("AI extraction unavailable (OPENAI_API_KEY not set)")
        return [], warnings

    try:
        import openai

        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": GANTT_AI_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Extract Gantt tasks from this PDF text:\n\n{text_content[:8000]}",
                },
            ],
            max_tokens=4000,
        )
        return _parse_ai_json_response(response.choices[0].message.content or "")
    except Exception as exc:
        logger.error("PDF AI extraction failed: %s", exc)
        return [], [f"AI extraction failed: {exc}"]


async def parse_image_vision(file_path: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Extract draft tasks from scanned Gantt / images via GPT-4o Vision."""
    if not OPENAI_API_KEY:
        return [], ["AI extraction unavailable (OPENAI_API_KEY not set)"]

    file_ext = os.path.splitext(file_path)[1].lower()
    mime_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }
    mime_type = mime_types.get(file_ext)
    if not mime_type:
        return [], [f"Unsupported image type: {file_ext}"]

    try:
        import base64
        import openai

        with open(file_path, "rb") as img_file:
            image_data = base64.b64encode(img_file.read()).decode("utf-8")

        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": GANTT_AI_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Extract all Gantt chart tasks, phases, dates, and dependencies from this image.",
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime_type};base64,{image_data}"},
                        },
                    ],
                },
            ],
            max_tokens=4000,
        )
        return _parse_ai_json_response(response.choices[0].message.content or "")
    except Exception as exc:
        logger.error("Image vision extraction failed: %s", exc)
        return [], [f"AI extraction failed: {exc}"]


def _find_column(row_keys: List[str], candidates: List[str]) -> Optional[str]:
    normalized = {k.lower().strip(): k for k in row_keys}
    for candidate in candidates:
        if candidate in normalized:
            return normalized[candidate]
    return None


async def parse_csv_milestones(file_path: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Deterministic CSV milestone/task row mapping."""
    global_warnings: List[str] = []
    tasks: List[Dict[str, Any]] = []

    try:
        with open(file_path, newline="", encoding="utf-8-sig") as handle:
            sample = handle.read(4096)
            handle.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
            except csv.Error:
                dialect = csv.excel
            reader = csv.DictReader(handle, dialect=dialect)
            if not reader.fieldnames:
                return [], ["CSV has no header row"]

            for index, row in enumerate(reader):
                title_col = _find_column(
                    list(row.keys()),
                    ["title", "name", "task", "milestone", "task name", "activity"],
                )
                if not title_col or not (row.get(title_col) or "").strip():
                    continue

                phase_col = _find_column(list(row.keys()), ["phase", "stage", "group"])
                start_col = _find_column(
                    list(row.keys()),
                    ["start_date", "start", "begin", "start date"],
                )
                end_col = _find_column(
                    list(row.keys()),
                    ["end_date", "end", "finish", "due", "end date"],
                )
                type_col = _find_column(list(row.keys()), ["type"])
                desc_col = _find_column(list(row.keys()), ["description", "notes", "details"])
                status_col = _find_column(list(row.keys()), ["status"])
                resp_col = _find_column(
                    list(row.keys()),
                    ["responsible_party", "owner", "assignee", "responsible"],
                )
                dep_col = _find_column(
                    list(row.keys()),
                    ["dependencies", "depends_on", "predecessor", "predecessors"],
                )

                raw_type = (row.get(type_col) or "task").strip().lower() if type_col else "task"
                task_type = "milestone" if raw_type in {"milestone", "m"} else "task"

                start_date, start_conf, start_warn = _normalize_date(
                    row.get(start_col) if start_col else None
                )
                end_date, end_conf, end_warn = _normalize_date(
                    row.get(end_col) if end_col else None
                )

                field_confidence = {"title": 0.98}
                task_warnings = start_warn + end_warn

                if start_col and start_date is None and row.get(start_col):
                    field_confidence["start_date"] = start_conf
                elif start_date:
                    field_confidence["start_date"] = start_conf

                if end_col and end_date is None and row.get(end_col):
                    field_confidence["end_date"] = end_conf
                elif end_date:
                    field_confidence["end_date"] = end_conf

                if task_type == "milestone" and start_date:
                    end_date = start_date

                dependencies: List[Dict[str, str]] = []
                if dep_col and row.get(dep_col):
                    # References by temp_id or row index — resolved after all rows built
                    dep_refs = [p.strip() for p in re.split(r"[;,|]", row[dep_col]) if p.strip()]
                    for ref in dep_refs:
                        dependencies.append({"temp_task_id": ref, "type": "finish_to_start"})
                    field_confidence["dependencies"] = 0.7
                    task_warnings.append("CSV dependency references need review after import")

                task = {
                    "temp_id": _make_temp_id(index),
                    "type": task_type,
                    "phase": (row.get(phase_col) or "").strip() or None if phase_col else None,
                    "title": row[title_col].strip(),
                    "description": (row.get(desc_col) or "").strip() or None if desc_col else None,
                    "start_date": start_date,
                    "end_date": end_date,
                    "status": (row.get(status_col) or "not_started").strip() if status_col else "not_started",
                    "responsible_party": (row.get(resp_col) or "").strip() or None if resp_col else None,
                    "dependencies": dependencies,
                    "field_confidence": field_confidence,
                    "warnings": task_warnings,
                }
                tasks.append(_apply_low_confidence_flags(task))

    except Exception as exc:
        logger.error("CSV parse failed: %s", exc)
        return [], [f"CSV parse failed: {exc}"]

    if not tasks:
        global_warnings.append("No tasks found in CSV")
        return tasks, global_warnings

    # Resolve dependency references (title or temp_id) to temp_ids
    title_to_temp: Dict[str, str] = {}
    for task in tasks:
        title_key = task["title"].strip().lower()
        if title_key and title_key not in title_to_temp:
            title_to_temp[title_key] = task["temp_id"]

    for task in tasks:
        resolved: List[Dict[str, str]] = []
        for dep in task.get("dependencies") or []:
            ref = dep.get("temp_task_id", "").strip()
            if not ref:
                continue
            ref_lower = ref.lower()
            target = None
            if ref in {t["temp_id"] for t in tasks}:
                target = ref
            elif ref_lower in title_to_temp:
                target = title_to_temp[ref_lower]
            if target and target != task["temp_id"]:
                resolved.append({"temp_task_id": target, "type": "finish_to_start"})
            elif not target:
                task.setdefault("warnings", []).append(
                    f"Unresolved dependency reference: {ref}"
                )
                task.setdefault("field_confidence", {})["dependencies"] = 0.3
        task["dependencies"] = resolved
        task["warnings"] = _apply_low_confidence_flags(task)["warnings"]

    return tasks, global_warnings


def make_temp_id() -> str:
    """Generate a unique temp_id for manually added draft rows."""
    return f"t_{uuid.uuid4().hex[:8]}"
