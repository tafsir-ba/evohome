"""
Gantt Chart — validation rules (standalone, testable without DB).
"""
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from services.gantt_constants import (
    ALLOWED_UPLOAD_EXTENSIONS,
    GANTT_APP_NAME,
    GANTT_EXTRACTION_MODEL,
    GANTT_REVIEW_MESSAGE,
    LOW_CONFIDENCE_THRESHOLD,
    MAX_UPLOAD_SIZE_BYTES,
)


class GanttValidationError(Exception):
    """Raised when gantt task/project data fails validation."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


VALID_STATUSES = {"not_started", "in_progress", "completed", "blocked"}
VALID_DEPENDENCY_TYPES = {"finish_to_start"}
DEPENDENCY_TYPE_FINISH_TO_START = "finish_to_start"
VALID_TASK_TYPES = ("task", "milestone")


def get_gantt_config() -> Dict[str, Any]:
    """Canonical gantt metadata for frontend consumption."""
    return {
        "app_name": GANTT_APP_NAME,
        "requires_auth": True,
        "task_statuses": sorted(VALID_STATUSES),
        "task_types": list(VALID_TASK_TYPES),
        "dependency_types": sorted(VALID_DEPENDENCY_TYPES),
        "import": {
            "allowed_extensions": sorted(ALLOWED_UPLOAD_EXTENSIONS),
            "max_size_bytes": MAX_UPLOAD_SIZE_BYTES,
            "max_size_mb": MAX_UPLOAD_SIZE_BYTES // (1024 * 1024),
            "review_message": GANTT_REVIEW_MESSAGE,
            "low_confidence_threshold": LOW_CONFIDENCE_THRESHOLD,
            "extraction_model": GANTT_EXTRACTION_MODEL,
        },
    }


def parse_date(value: Optional[str], field_name: str) -> Optional[date]:
    """Parse YYYY-MM-DD into a date; reject invalid calendar dates."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise GanttValidationError(f"{field_name} must be a string in YYYY-MM-DD format")
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise GanttValidationError(
            f"{field_name} must be a valid calendar date in YYYY-MM-DD format"
        ) from exc


def compute_duration_days(
    task_type: str,
    start: Optional[date],
    end: Optional[date],
) -> Optional[int]:
    """Compute duration_days per task type and date rules."""
    if start is None and end is None:
        return None
    if start is not None and end is None:
        return None
    if start is None and end is not None:
        raise GanttValidationError("end_date requires start_date")

    if task_type == "milestone":
        return 0

    assert start is not None and end is not None
    return (end - start).days


def normalize_task_dates(
    task_type: str,
    start_date: Optional[str],
    end_date: Optional[str],
) -> Tuple[Optional[str], Optional[str], Optional[int]]:
    """
    Validate and normalize dates for a task.
    Returns (start_date, end_date, duration_days).
    """
    start = parse_date(start_date, "start_date")
    end = parse_date(end_date, "end_date")

    if start is None and end is not None:
        raise GanttValidationError("end_date requires start_date")

    if start is not None and end is not None and end < start:
        raise GanttValidationError("end_date must not be before start_date")

    if task_type == "milestone":
        if start is None:
            raise GanttValidationError("Milestones require start_date")
        if end is not None and end != start:
            raise GanttValidationError("Milestone start_date and end_date must match")
        normalized_start = start.isoformat()
        return normalized_start, normalized_start, 0

    duration = compute_duration_days(task_type, start, end)
    return (
        start.isoformat() if start else None,
        end.isoformat() if end else None,
        duration,
    )


def validate_status(status: Optional[str]) -> str:
    if status is None:
        return "not_started"
    if status not in VALID_STATUSES:
        raise GanttValidationError(f"Invalid status: {status}")
    return status


def validate_dependencies(
    dependencies: List[Dict[str, Any]],
    task_id: str,
    project_task_ids: Set[str],
) -> List[Dict[str, str]]:
    """Validate dependency list: same project, no self-ref, finish_to_start only."""
    if not dependencies:
        return []

    normalized: List[Dict[str, str]] = []
    seen: Set[str] = set()

    for dep in dependencies:
        dep_task_id = dep.get("task_id")
        dep_type = dep.get("type", DEPENDENCY_TYPE_FINISH_TO_START)

        if not dep_task_id:
            raise GanttValidationError("Dependency task_id is required")

        if dep_task_id == task_id:
            raise GanttValidationError("A task cannot depend on itself")

        if dep_task_id not in project_task_ids:
            raise GanttValidationError(f"Dependency task {dep_task_id} not found in project")

        if dep_type not in VALID_DEPENDENCY_TYPES:
            raise GanttValidationError(f"Unsupported dependency type: {dep_type}")

        if dep_task_id in seen:
            continue

        seen.add(dep_task_id)
        normalized.append({"task_id": dep_task_id, "type": DEPENDENCY_TYPE_FINISH_TO_START})

    return normalized


def validate_reorder_task_ids(
    task_ids: List[str],
    existing_tasks: List[Dict[str, Any]],
) -> None:
    """Ensure task_ids is a full, duplicate-free permutation of project tasks."""
    existing_ids = {t["task_id"] for t in existing_tasks}

    if len(task_ids) != len(existing_tasks):
        raise GanttValidationError("task_ids must be a full permutation of project tasks")

    if len(set(task_ids)) != len(task_ids):
        raise GanttValidationError("task_ids must not contain duplicates")

    if set(task_ids) != existing_ids:
        raise GanttValidationError("task_ids must be a full permutation of project tasks")


def detect_dependency_cycle(
    tasks: List[Dict[str, Any]],
    candidate_task_id: str,
    candidate_dependencies: List[Dict[str, str]],
) -> None:
    """DFS cycle detection across all tasks with a candidate dependency update."""
    graph: Dict[str, List[str]] = {}

    for task in tasks:
        tid = task["task_id"]
        if tid == candidate_task_id:
            deps = [d["task_id"] for d in candidate_dependencies]
        else:
            deps = [d["task_id"] for d in task.get("dependencies", [])]
        graph[tid] = deps

    if candidate_task_id not in graph:
        graph[candidate_task_id] = [d["task_id"] for d in candidate_dependencies]

    visited: Set[str] = set()
    stack: Set[str] = set()

    def dfs(node: str) -> bool:
        visited.add(node)
        stack.add(node)
        for neighbor in graph.get(node, []):
            if neighbor not in visited:
                if dfs(neighbor):
                    return True
            elif neighbor in stack:
                return True
        stack.remove(node)
        return False

    for node in graph:
        if node not in visited and dfs(node):
            raise GanttValidationError("Circular dependency detected")


def validate_task_payload(
    payload: Dict[str, Any],
    *,
    task_id: str,
    task_type: str,
    project_task_ids: Set[str],
    existing_tasks: List[Dict[str, Any]],
    is_create: bool = False,
) -> Dict[str, Any]:
    """
    Full task validation for create/update.
    Returns normalized fields ready for persistence.
    """
    if not payload.get("title") and is_create:
        raise GanttValidationError("title is required")

    start_date = payload.get("start_date")
    end_date = payload.get("end_date")
    normalized_start, normalized_end, duration = normalize_task_dates(
        task_type, start_date, end_date
    )

    client_duration = payload.get("duration_days")
    if client_duration is not None and duration is not None and client_duration != duration:
        raise GanttValidationError(
            f"duration_days mismatch: expected {duration}, got {client_duration}"
        )

    status = validate_status(payload.get("status"))

    raw_deps = payload.get("dependencies") or []
    dependencies = validate_dependencies(raw_deps, task_id, project_task_ids)
    detect_dependency_cycle(existing_tasks, task_id, dependencies)

    result = {
        "type": task_type,
        "start_date": normalized_start,
        "end_date": normalized_end,
        "duration_days": duration,
        "status": status,
        "dependencies": dependencies,
    }

    if "title" in payload and payload["title"] is not None:
        result["title"] = payload["title"]
    if "phase" in payload:
        result["phase"] = payload["phase"]
    if "description" in payload:
        result["description"] = payload["description"]
    if "responsible_party" in payload:
        result["responsible_party"] = payload["responsible_party"]

    return result


def validate_draft_tasks(
    draft_tasks: List[Dict[str, Any]],
    existing_tasks: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """
    Validate draft tasks before confirm.
    Uses temp_id for dependency references within the draft batch.
    Returns normalized draft task dicts ready for remapping.
    """
    if not draft_tasks:
        raise GanttValidationError("Draft must contain at least one task")

    temp_ids: Set[str] = set()
    for task in draft_tasks:
        temp_id = task.get("temp_id")
        if not temp_id:
            raise GanttValidationError("Each draft task requires temp_id")
        if temp_id in temp_ids:
            raise GanttValidationError(f"Duplicate temp_id: {temp_id}")
        temp_ids.add(temp_id)

        if not (task.get("title") or "").strip():
            raise GanttValidationError(f"Task {temp_id} requires a title")

    normalized_batch: List[Dict[str, Any]] = []
    for task in draft_tasks:
        task_type = task.get("type", "task")
        normalized_start, normalized_end, duration = normalize_task_dates(
            task_type,
            task.get("start_date"),
            task.get("end_date"),
        )
        status = validate_status(task.get("status"))

        raw_deps = task.get("dependencies") or []
        normalized_deps: List[Dict[str, str]] = []
        seen_deps: Set[str] = set()
        for dep in raw_deps:
            temp_task_id = dep.get("temp_task_id")
            if not temp_task_id:
                raise GanttValidationError("Draft dependency temp_task_id is required")
            if temp_task_id == task["temp_id"]:
                raise GanttValidationError("A task cannot depend on itself")
            if temp_task_id not in temp_ids:
                raise GanttValidationError(
                    f"Dependency temp_task_id {temp_task_id} not found in draft"
                )
            dep_type = dep.get("type", DEPENDENCY_TYPE_FINISH_TO_START)
            if dep_type not in VALID_DEPENDENCY_TYPES:
                raise GanttValidationError(f"Unsupported dependency type: {dep_type}")
            if temp_task_id in seen_deps:
                continue
            seen_deps.add(temp_task_id)
            normalized_deps.append(
                {"temp_task_id": temp_task_id, "type": DEPENDENCY_TYPE_FINISH_TO_START}
            )

        normalized_batch.append({
            **task,
            "type": task_type,
            "start_date": normalized_start,
            "end_date": normalized_end,
            "duration_days": duration,
            "status": status,
            "dependencies": normalized_deps,
        })

    # Cycle detection using temp_ids as graph nodes
    graph: Dict[str, List[str]] = {
        t["temp_id"]: [d["temp_task_id"] for d in t["dependencies"]]
        for t in normalized_batch
    }
    visited: Set[str] = set()
    stack: Set[str] = set()

    def dfs(node: str) -> bool:
        visited.add(node)
        stack.add(node)
        for neighbor in graph.get(node, []):
            if neighbor not in visited:
                if dfs(neighbor):
                    return True
            elif neighbor in stack:
                return True
        stack.remove(node)
        return False

    for node in graph:
        if node not in visited and dfs(node):
            raise GanttValidationError("Circular dependency detected in draft")

    return normalized_batch
