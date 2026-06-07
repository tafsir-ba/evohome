"""
Gantt Chart — export services (CSV, Excel, PDF).
"""
import csv
import io
import re
from datetime import date, datetime
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


def build_pdf_bytes(
    project: Dict[str, Any],
    tasks: List[Dict[str, Any]],
) -> bytes:
    """Render paginated PDF with task table and simple Gantt bars."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas

    page_size = landscape(A4)
    width, height = page_size
    margin = 15 * mm
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=page_size)

    def draw_header(page_num: int) -> float:
        y = height - margin
        pdf.setFont("Helvetica-Bold", 14)
        pdf.drawString(margin, y, project.get("title", "Gantt Export"))
        y -= 14
        pdf.setFont("Helvetica", 9)
        pdf.drawString(
            margin,
            y,
            f"Exported {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')} · {len(tasks)} tasks",
        )
        y -= 10
        pdf.setFont("Helvetica", 8)
        pdf.drawRightString(width - margin, height - margin, f"Page {page_num}")
        return y - 8

    def new_page(page_num: int) -> float:
        if page_num > 1:
            pdf.showPage()
        return draw_header(page_num)

    # ── Task table pages ──
    table_headers = ["#", "Phase", "Title", "Start", "End", "Days", "Status"]
    col_widths = [8 * mm, 28 * mm, 70 * mm, 22 * mm, 22 * mm, 14 * mm, 22 * mm]
    row_height = 5.5 * mm

    page_num = 1
    y = new_page(page_num)
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(margin, y, "Task schedule")
    y -= 10
    pdf.setFont("Helvetica-Bold", 8)
    x = margin
    for header, col_w in zip(table_headers, col_widths):
        pdf.drawString(x + 1 * mm, y, header)
        x += col_w
    y -= row_height
    pdf.setFont("Helvetica", 8)

    for task in tasks:
        if y < margin + row_height:
            page_num += 1
            y = new_page(page_num)
            pdf.setFont("Helvetica-Bold", 8)
            x = margin
            for header, col_w in zip(table_headers, col_widths):
                pdf.drawString(x + 1 * mm, y, header)
                x += col_w
            y -= row_height
            pdf.setFont("Helvetica", 8)

        duration = task.get("duration_days")
        if duration is None:
            duration_str = ""
        else:
            duration_str = str(duration)

        cells = [
            str(task.get("order", 0) + 1),
            (task.get("phase") or "")[:18],
            (task.get("title") or "")[:42],
            task.get("start_date") or "",
            task.get("end_date") or "",
            duration_str,
            (task.get("status") or "").replace("_", " "),
        ]
        x = margin
        for value, col_w in zip(cells, col_widths):
            pdf.drawString(x + 1 * mm, y, value)
            x += col_w
        y -= row_height

    # ── Gantt bar chart page(s) ──
    dated_tasks = [t for t in tasks if t.get("start_date")]
    min_date, max_date = _timeline_bounds(dated_tasks)
    if min_date and max_date and dated_tasks:
        page_num += 1
        y = new_page(page_num)
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(margin, y, "Timeline")
        y -= 12

        chart_left = margin + 55 * mm
        chart_right = width - margin
        chart_width = chart_right - chart_left
        total_days = max((max_date - min_date).days, 1)

        label_y = y
        pdf.setFont("Helvetica", 7)
        pdf.drawString(margin, label_y, min_date.isoformat())
        pdf.drawRightString(chart_right, label_y, max_date.isoformat())
        y -= 6
        pdf.line(chart_left, y, chart_right, y)
        y -= 4

        bar_height = 4 * mm
        bar_gap = 2 * mm
        pdf.setFont("Helvetica", 7)

        for task in dated_tasks:
            if y < margin + bar_height + bar_gap:
                page_num += 1
                y = new_page(page_num)
                pdf.setFont("Helvetica-Bold", 10)
                pdf.drawString(margin, y, "Timeline (continued)")
                y -= 12
                pdf.setFont("Helvetica", 7)

            start = _parse_iso_date(task.get("start_date"))
            end = _parse_iso_date(task.get("end_date")) or start
            if not start:
                continue

            title_label = (task.get("title") or "")[:28]
            pdf.drawString(margin, y, title_label)

            start_offset = (start - min_date).days
            end_offset = (end - min_date).days if end else start_offset
            bar_start_x = chart_left + (start_offset / total_days) * chart_width
            bar_end_x = chart_left + (max(end_offset, start_offset) / total_days) * chart_width
            bar_width = max(bar_end_x - bar_start_x, 2)

            if task.get("type") == "milestone":
                pdf.setFillColor(colors.HexColor("#2563eb"))
                pdf.circle(bar_start_x, y + 1.5, 2, fill=1, stroke=0)
            else:
                pdf.setFillColor(colors.HexColor("#3b82f6"))
                pdf.setStrokeColor(colors.HexColor("#1d4ed8"))
                pdf.rect(bar_start_x, y - 1, bar_width, bar_height, fill=1, stroke=1)

            pdf.setFillColor(colors.black)
            y -= bar_height + bar_gap

    pdf.save()
    return buffer.getvalue()


def build_pdf_response(
    project: Dict[str, Any],
    tasks: List[Dict[str, Any]],
) -> Tuple[bytes, str, str]:
    """Returns (pdf_bytes, content_type, content_disposition)."""
    content = build_pdf_bytes(project, tasks)
    filename = f"{_sanitize_filename(project.get('title', 'gantt'))}.pdf"
    content_type = "application/pdf"
    disposition = f'attachment; filename="{filename}"'
    return content, content_type, disposition
