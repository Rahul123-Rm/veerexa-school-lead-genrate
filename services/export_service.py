"""
services/export_service.py — Export leads to CSV, Excel, and PDF formats.

Supports:
  • CSV  — flat file via pandas
  • Excel — single sheet and district-wise workbook (openpyxl)
  • PDF  — district-wise branded report (reportlab)
"""

from __future__ import annotations

import io
from datetime import datetime
from typing import Any

import pandas as pd

# ---------------------------------------------------------------------------
# Column definitions
# ---------------------------------------------------------------------------

EXPORT_COLUMNS = [
    ("name", "School Name"),
    ("phone", "Phone"),
    ("website", "Website"),
    ("instagram", "Instagram"),
    ("email", "Email"),
    ("address", "Address"),
    ("city", "City"),
    ("district", "District"),
    ("state", "State"),
    ("postal_code", "Postal Code"),
    ("maps_url", "Google Maps URL"),
    ("place_id", "Place ID"),
    ("latitude", "Latitude"),
    ("longitude", "Longitude"),
    ("rating", "Rating"),
    ("review_count", "Reviews"),
    ("business_status", "Business Status"),
    ("contact_source", "Data Source"),
    ("verification_status", "Verification"),
    ("outreach_status", "Outreach Status"),
    ("notes", "Notes"),
    ("created_at", "Created Date"),
    ("last_checked", "Last Checked"),
]

FIELD_NAMES = [c[0] for c in EXPORT_COLUMNS]
HEADER_NAMES = [c[1] for c in EXPORT_COLUMNS]


def _records_to_df(records: list[dict]) -> pd.DataFrame:
    rows = []
    for r in records:
        row = {header: r.get(field, "") for field, header in EXPORT_COLUMNS}
        rows.append(row)
    return pd.DataFrame(rows, columns=HEADER_NAMES)


# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------

def export_csv(records: list[dict]) -> bytes:
    """Return CSV bytes for the given records."""
    df = _records_to_df(records)
    buf = io.BytesIO()
    df.to_csv(buf, index=False, encoding="utf-8-sig")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Excel — single sheet
# ---------------------------------------------------------------------------

def export_excel_single(records: list[dict]) -> bytes:
    """Return an Excel workbook with a single 'Leads' sheet."""
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter
    except ImportError:
        raise ImportError("openpyxl is required for Excel export.")

    wb = Workbook()
    ws = wb.active
    ws.title = "School Leads"

    _write_excel_sheet(ws, records)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Excel — district-wise workbook
# ---------------------------------------------------------------------------

def export_excel_district(records: list[dict]) -> bytes:
    """Return an Excel workbook with one sheet per district."""
    try:
        from openpyxl import Workbook
    except ImportError:
        raise ImportError("openpyxl is required for Excel export.")

    wb = Workbook()
    # Remove default sheet
    wb.remove(wb.active)

    # Group by district
    by_district: dict[str, list[dict]] = {}
    for r in records:
        district = (r.get("district") or "Unknown").strip()
        by_district.setdefault(district, []).append(r)

    for district, rows in sorted(by_district.items()):
        safe_name = district[:31]  # Excel sheet name limit
        ws = wb.create_sheet(title=safe_name)
        _write_excel_sheet(ws, rows, title=f"{district} — School Leads")

    if not wb.sheetnames:
        wb.create_sheet(title="No Data")

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _write_excel_sheet(ws: Any, records: list[dict], title: str = "School Leads") -> None:
    """Write records to an openpyxl worksheet with formatting."""
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    HEADER_FILL = PatternFill("solid", fgColor="3B2F8C")  # deep purple
    HEADER_FONT = Font(bold=True, color="FFFFFF", name="Calibri", size=10)
    BODY_FONT = Font(name="Calibri", size=10)
    LINK_FONT = Font(name="Calibri", size=10, color="1155CC", underline="single")
    THIN_BORDER = Border(
        bottom=Side(style="thin", color="D0D0D0"),
    )

    URL_FIELDS = {"Website", "Google Maps URL", "Instagram"}

    # Write header
    ws.append(HEADER_NAMES)
    ws.freeze_panes = "A2"

    # Style header row
    for col_idx, _ in enumerate(HEADER_NAMES, start=1):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center")

    ws.row_dimensions[1].height = 20

    # Write data rows
    for row_idx, record in enumerate(records, start=2):
        for col_idx, (field, header) in enumerate(EXPORT_COLUMNS, start=1):
            value = record.get(field) or ""
            cell = ws.cell(row=row_idx, column=col_idx, value=value)
            cell.font = BODY_FONT
            cell.border = THIN_BORDER
            cell.alignment = Alignment(vertical="top", wrap_text=False)

            if header in URL_FIELDS and isinstance(value, str) and value.startswith("http"):
                cell.hyperlink = value
                cell.font = LINK_FONT

        # Alternate row shading
        if row_idx % 2 == 0:
            for col_idx in range(1, len(HEADER_NAMES) + 1):
                ws.cell(row=row_idx, column=col_idx).fill = PatternFill(
                    "solid", fgColor="F3F0FF"
                )

    # Auto-fit column widths
    for col_idx, header in enumerate(HEADER_NAMES, start=1):
        max_len = len(header)
        for row_idx in range(2, len(records) + 2):
            val = ws.cell(row=row_idx, column=col_idx).value
            if val:
                max_len = max(max_len, min(len(str(val)), 60))
        ws.column_dimensions[get_column_letter(col_idx)].width = max_len + 2

    # Add auto-filter on header row
    ws.auto_filter.ref = ws.dimensions


# ---------------------------------------------------------------------------
# PDF — district-wise branded report
# ---------------------------------------------------------------------------

def export_pdf_district(records: list[dict], state: str = "") -> bytes:
    """
    Return a PDF report grouped by district with Veerexa Technologies branding.
    """
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            SimpleDocTemplate,
            Paragraph,
            Spacer,
            Table,
            TableStyle,
            PageBreak,
            HRFlowable,
        )
    except ImportError:
        raise ImportError("reportlab is required for PDF export.")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=20 * mm,
        bottomMargin=15 * mm,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "VeeTitle",
        parent=styles["Title"],
        fontSize=18,
        textColor=colors.HexColor("#3B2F8C"),
        spaceAfter=4,
        fontName="Helvetica-Bold",
    )
    subtitle_style = ParagraphStyle(
        "VeeSub",
        parent=styles["Normal"],
        fontSize=11,
        textColor=colors.HexColor("#5A4FCF"),
        spaceAfter=2,
        fontName="Helvetica",
    )
    section_style = ParagraphStyle(
        "VeeSec",
        parent=styles["Heading2"],
        fontSize=13,
        textColor=colors.HexColor("#1E1060"),
        spaceBefore=12,
        spaceAfter=4,
        fontName="Helvetica-Bold",
    )
    caption_style = ParagraphStyle(
        "VeeCaption",
        parent=styles["Normal"],
        fontSize=8,
        textColor=colors.grey,
        fontName="Helvetica-Oblique",
    )

    table_headers = [
        "School Name", "Address", "Phone", "Website", "Instagram", "Email", "Outreach"
    ]
    BRAND_PURPLE = colors.HexColor("#3B2F8C")
    BRAND_LIGHT = colors.HexColor("#EDE9FF")

    # Group by district
    by_district: dict[str, list[dict]] = {}
    for r in records:
        district = (r.get("district") or "Unknown").strip()
        by_district.setdefault(district, []).append(r)

    story = []
    gen_date = datetime.now().strftime("%d %B %Y, %I:%M %p")

    def _add_header():
        story.append(Paragraph("Veerexa Technologies", title_style))
        story.append(Paragraph("School Lead Finder — District-wise Report", subtitle_style))
        if state:
            story.append(Paragraph(f"State: {state}", subtitle_style))
        story.append(Paragraph(f"Generated: {gen_date}  |  Total Leads: {len(records)}", caption_style))
        story.append(HRFlowable(width="100%", thickness=2, color=BRAND_PURPLE, spaceAfter=8))

    _add_header()

    for district, rows in sorted(by_district.items()):
        story.append(Paragraph(f"📍 {district} ({len(rows)} leads)", section_style))

        table_data = [table_headers]
        for r in rows:
            table_data.append([
                Paragraph(_trunc(r.get("name", ""), 40), styles["Normal"]),
                Paragraph(_trunc(r.get("address", ""), 45), styles["Normal"]),
                Paragraph(r.get("phone", "") or "", styles["Normal"]),
                Paragraph(_trunc(r.get("website", "") or "", 30), styles["Normal"]),
                Paragraph(_trunc(r.get("instagram", "") or "", 30), styles["Normal"]),
                Paragraph(r.get("email", "") or "", styles["Normal"]),
                Paragraph(r.get("outreach_status", "") or "New", styles["Normal"]),
            ])

        col_widths = [90*mm, 80*mm, 35*mm, 55*mm, 55*mm, 55*mm, 35*mm]
        tbl = Table(table_data, colWidths=col_widths, repeatRows=1)
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), BRAND_PURPLE),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 8),
            ("FONTSIZE", (0, 1), (-1, -1), 7),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BRAND_LIGHT]),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#C8C0EE")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(tbl)
        story.append(Spacer(1, 8))
        story.append(PageBreak())

    # Remove trailing page break
    if story and isinstance(story[-1], PageBreak):
        story.pop()

    doc.build(story)
    return buf.getvalue()


def _trunc(text: str, max_len: int) -> str:
    """Truncate a string and add ellipsis if too long."""
    if not text:
        return ""
    return text if len(text) <= max_len else text[: max_len - 1] + "…"
