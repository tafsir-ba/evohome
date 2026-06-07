"""
Gantt Chart — export services (CSV, Excel, PDF).
"""
import csv
import io
import re
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

EXPORT_COLUMNS = [
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

# Backward-compatible alias used by CSV tests
CSV_COLUMNS = EXPORT_COLUMNS


def _sanitize_filename(title: str) -> str:
    safe = re.sub(r'[^\w\s\-]', '', title).strip()
    safe = re.sub(r'\s+', '_', safe)
    return safe or "gantt_export"


def _format_dependencies(dependencies: List[Dict[str, Any]]) -> str:
    if not dependencies:
        return ""
    return "|".join(dep["task_id"] for dep in dependencies)


def _export_rows(tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for task in tasks:
        row = {col: task.get(col, "") for col in EXPORT_COLUMNS}
        if row.get("duration_days") is None:
            row["duration_days"] = ""
        row["dependencies"] = _format_dependencies(task.get("dependencies", []))
        rows.append(row)
    return rows


def build_csv_content(tasks: List[Dict[str, Any]]) -> str:
    """Build CSV string from task list."""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=EXPORT_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for row in _export_rows(tasks):
        writer.writerow(row)
    return output.getvalue()


def build_csv_response(
    project: Dict[str, Any],
    tasks: List[Dict[str, Any]],
) -> Tuple[str, str, str]:
    """Returns (csv_content, content_type, content_disposition)."""
    content = build_csv_content(tasks)
    filename = f"{_sanitize_filename(project.get('title', 'gantt'))}.csv"
    content_type = "text/csv; charset=utf-8"
    disposition = f'attachment; filename="{filename}"'
    return content, content_type, disposition


def build_xlsx_bytes(
    project: Dict[str, Any],
    tasks: List[Dict[str, Any]],
) -> bytes:
    """Build Excel workbook bytes (tasks sheet + metadata sheet)."""
    from openpyxl import Workbook
    from openpyxl.styles import Font

    wb = Workbook()

    meta_ws = wb.active
    meta_ws.title = "Metadata"
    meta_ws["A1"] = "Project"
    meta_ws["A1"].font = Font(bold=True)
    meta_ws["B1"] = project.get("title", "")
    meta_ws["A2"] = "Description"
    meta_ws["A2"].font = Font(bold=True)
    meta_ws["B2"] = project.get("description") or ""
    meta_ws["A3"] = "Export date"
    meta_ws["A3"].font = Font(bold=True)
    meta_ws["B3"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    meta_ws["A4"] = "Task count"
    meta_ws["A4"].font = Font(bold=True)
    meta_ws["B4"] = len(tasks)

    excel_columns = EXPORT_COLUMNS + ["task_id"]
    tasks_ws = wb.create_sheet("Tasks")
    tasks_ws.append(excel_columns)
    for cell in tasks_ws[1]:
        cell.font = Font(bold=True)
    for task, row in zip(tasks, _export_rows(tasks)):
        tasks_ws.append([row[col] for col in EXPORT_COLUMNS] + [task.get("task_id", "")])

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def build_xlsx_response(
    project: Dict[str, Any],
    tasks: List[Dict[str, Any]],
) -> Tuple[bytes, str, str]:
    """Returns (xlsx_bytes, content_type, content_disposition)."""
    content = build_xlsx_bytes(project, tasks)
    filename = f"{_sanitize_filename(project.get('title', 'gantt'))}.xlsx"
    content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    disposition = f'attachment; filename="{filename}"'
    return content, content_type, disposition


def _parse_iso_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except ValueError:
        return None


def _timeline_bounds(tasks: List[Dict[str, Any]]) -> Tuple[Optional[date], Optional[date]]:
    dates: List[date] = []
    for task in tasks:
        start = _parse_iso_date(task.get("start_date"))
        end = _parse_iso_date(task.get("end_date")) or start
        if start:
            dates.append(start)
        if end:
            dates.append(end)
    if not dates:
        return None, None
    return min(dates), max(dates)


def _group_tasks_by_phase(tasks: List[Dict[str, Any]]) -> List[Tuple[str, List[Dict[str, Any]]]]:
    groups: Dict[str, List[Dict[str, Any]]] = {}
    order: List[str] = []
    for task in sorted(tasks, key=lambda t: t.get("order", 0)):
        phase = (task.get("phase") or "").strip() or "Unassigned"
        if phase not in groups:
            groups[phase] = []
            order.append(phase)
        groups[phase].append(task)
    return [(phase, groups[phase]) for phase in order]


def _format_month_range(min_d: Optional[date], max_d: Optional[date]) -> str:
    if not min_d or not max_d:
        return "Dates not set"
    if min_d.year == max_d.year and min_d.month == max_d.month:
        return min_d.strftime("%B %Y")
    return f"{min_d.strftime('%B %Y')} - {max_d.strftime('%B %Y')}"


def _month_tick_dates(min_d: date, max_d: date) -> List[date]:
    ticks: List[date] = []
    cursor = min_d.replace(day=1)
    while cursor <= max_d:
        if cursor >= min_d:
            ticks.append(cursor)
        if cursor.month == 12:
            cursor = cursor.replace(year=cursor.year + 1, month=1)
        else:
            cursor = cursor.replace(month=cursor.month + 1)
    return ticks


def _week_tick_dates(min_d: date, max_d: date) -> List[date]:
    ticks: List[date] = []
    cursor = min_d
    while cursor.weekday() != 0:
        cursor += timedelta(days=1)
    while cursor <= max_d:
        if cursor >= min_d:
            ticks.append(cursor)
        cursor += timedelta(days=7)
    return ticks


def build_pdf_bytes(
    project: Dict[str, Any],
    tasks: List[Dict[str, Any]],
    mode: str = "presentation",
) -> bytes:
    """Render PDF export. Default mode is one-page executive presentation."""
    from services.gantt_pdf_export import build_pdf_bytes as render_pdf

    return render_pdf(project, tasks, mode=mode)


def build_pdf_response(
    project: Dict[str, Any],
    tasks: List[Dict[str, Any]],
    mode: str = "presentation",
) -> Tuple[bytes, str, str]:
    """returns (pdf_bytes, content_type, content_disposition)."""
    content = build_pdf_bytes(project, tasks, mode=mode)
    base = _sanitize_filename(project.get("title", "gantt"))
    suffix = "" if mode == "presentation" else "_detailed"
    filename = f"{base}{suffix}.pdf"
    content_type = "application/pdf"
    disposition = f'attachment; filename="{filename}"'
    return content, content_type, disposition

