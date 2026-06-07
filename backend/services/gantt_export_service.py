"""
Gantt Chart — CSV export (stdlib csv module).
"""
import csv
import io
import re
from typing import Any, Dict, List, Tuple


CSV_COLUMNS = [
    "order",
    "type",
    "phase",
    "title",
    "description",
    "start_date",
    "end_date",
    "duration_days",
    "status",
    "responsible_party",
    "dependencies",
    "source",
]


def _sanitize_filename(title: str) -> str:
    safe = re.sub(r'[^\w\s\-]', '', title).strip()
    safe = re.sub(r'\s+', '_', safe)
    return safe or "gantt_export"


def _format_dependencies(dependencies: List[Dict[str, Any]]) -> str:
    if not dependencies:
        return ""
    return "|".join(dep["task_id"] for dep in dependencies)


def build_csv_content(tasks: List[Dict[str, Any]]) -> str:
    """Build CSV string from task list."""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=CSV_COLUMNS, extrasaction="ignore")
    writer.writeheader()

    for task in tasks:
        row = {col: task.get(col, "") for col in CSV_COLUMNS}
        if row.get("duration_days") is None:
            row["duration_days"] = ""
        row["dependencies"] = _format_dependencies(task.get("dependencies", []))
        writer.writerow(row)

    return output.getvalue()


def build_csv_response(
    project: Dict[str, Any],
    tasks: List[Dict[str, Any]],
) -> Tuple[str, str, str]:
    """
    Returns (csv_content, content_type, content_disposition).
    """
    content = build_csv_content(tasks)
    filename = f"{_sanitize_filename(project.get('title', 'gantt'))}.csv"
    content_type = "text/csv; charset=utf-8"
    disposition = f'attachment; filename="{filename}"'
    return content, content_type, disposition
