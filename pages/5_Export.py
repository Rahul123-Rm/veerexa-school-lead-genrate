"""
pages/5_Export.py — Export leads to CSV, Excel, and PDF formats.
"""

from __future__ import annotations

from datetime import datetime

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from database.connection import get_session
from database.migrations import initialise_database
from models.school import School
from services.export_service import (
    export_csv,
    export_excel_single,
    export_excel_district,
    export_pdf_district,
)
from utils.india_geo import get_states

initialise_database()

st.set_page_config(
    page_title="Export — Veerexa Lead Finder", page_icon="📤", layout="wide"
)

st.markdown(
    """<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    html,body,[class*="css"]{font-family:'Inter',sans-serif;}
    [data-testid="stSidebar"]{background:linear-gradient(160deg,#1E1060 0%,#3B2F8C 60%,#5A4FCF 100%);}
    [data-testid="stSidebar"] *{color:#E8E4FF!important;}
    .stButton>button{background:linear-gradient(135deg,#3B2F8C,#5A4FCF);color:#fff;border:none;border-radius:8px;font-weight:600;padding:.5rem 1.2rem;}
    h1{color:#1E1060;} h2{color:#3B2F8C;} h3{color:#5A4FCF;}
    .export-card{background:linear-gradient(135deg,#f8f6ff,#ede9ff);border:1px solid #d5cefd;border-radius:12px;padding:1.2rem;margin-bottom:.8rem;}
    </style>""",
    unsafe_allow_html=True,
)

OUTREACH_STATUSES = [
    "New", "Needs verification", "Ready to contact",
    "WhatsApp sent", "Instagram DM sent", "Called",
    "Follow-up required", "Interested", "Demo scheduled",
    "Not interested", "No response",
]

st.title("📤 Export")
st.caption("Export filtered leads to CSV, Excel, or PDF — API keys are never included in exports.")

# ─────────────────────────────────────────────────────────────────────────────
# Filter panel
# ─────────────────────────────────────────────────────────────────────────────
st.subheader("🔎 Export Filters")

col1, col2, col3 = st.columns(3)
f_state = col1.selectbox("State", ["All"] + get_states(), key="export_state")
f_district = col2.text_input("District (leave blank for all)", key="export_district")
f_city = col3.text_input("City (leave blank for all)", key="export_city")

col4, col5, col6 = st.columns(3)
f_outreach = col4.selectbox("Outreach Status", ["All"] + OUTREACH_STATUSES, key="export_outreach")
f_verified = col5.checkbox("Verified only", key="export_verified")
f_min_rating = col6.slider("Min rating", 0.0, 5.0, 0.0, 0.1, key="export_rating")

col7, col8 = st.columns(2)
f_has_phone = col7.checkbox("Has phone", key="export_phone")
f_has_website = col8.checkbox("Has website", key="export_website")

# ─────────────────────────────────────────────────────────────────────────────
# Apply filters and count
# ─────────────────────────────────────────────────────────────────────────────
with get_session() as session:
    query = session.query(School)

    if f_state != "All":
        query = query.filter(School.state == f_state)
    if f_district:
        query = query.filter(School.district.ilike(f"%{f_district}%"))
    if f_city:
        query = query.filter(School.city.ilike(f"%{f_city}%"))
    if f_outreach != "All":
        query = query.filter(School.outreach_status == f_outreach)
    if f_verified:
        query = query.filter(School.is_verified == True)
    if f_min_rating > 0:
        query = query.filter(School.rating >= f_min_rating)
    if f_has_phone:
        query = query.filter(School.phone.isnot(None), School.phone != "")
    if f_has_website:
        query = query.filter(School.website.isnot(None), School.website != "")

    schools = query.order_by(School.state, School.district, School.name).all()
    records = [s.to_dict() for s in schools]

match_count = len(records)
st.markdown(f"**{match_count} schools match your filters.**")

if match_count == 0:
    st.info("No records match the selected filters. Adjust filters and try again.", icon="ℹ️")
    st.stop()

# ─────────────────────────────────────────────────────────────────────────────
# Export buttons
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("---")
st.subheader("📁 Download Exports")

timestamp = datetime.now().strftime("%Y%m%d_%H%M")
state_slug = f_state.replace(" ", "_") if f_state != "All" else "All"
base_filename = f"veerexa_leads_{state_slug}_{timestamp}"

ec1, ec2 = st.columns(2)

# ── CSV ───────────────────────────────────────────────────────────────────────
with ec1:
    st.markdown(
        '<div class="export-card">📄 <strong>CSV Export</strong><br>'
        '<small>Flat comma-separated file, compatible with Excel, Google Sheets, and CRMs.</small></div>',
        unsafe_allow_html=True,
    )
    try:
        csv_bytes = export_csv(records)
        st.download_button(
            label=f"⬇️ Download CSV ({match_count} rows)",
            data=csv_bytes,
            file_name=f"{base_filename}.csv",
            mime="text/csv",
            use_container_width=True,
            key="dl_csv",
        )
    except Exception as exc:
        st.error(f"CSV export failed: {exc}")

# ── Excel single ──────────────────────────────────────────────────────────────
with ec2:
    st.markdown(
        '<div class="export-card">📊 <strong>Excel Export (Single Sheet)</strong><br>'
        '<small>Formatted Excel workbook with frozen headers, hyperlinks, and auto-fit columns.</small></div>',
        unsafe_allow_html=True,
    )
    try:
        xl_bytes = export_excel_single(records)
        st.download_button(
            label=f"⬇️ Download Excel ({match_count} rows)",
            data=xl_bytes,
            file_name=f"{base_filename}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            key="dl_excel",
        )
    except Exception as exc:
        st.error(f"Excel export failed: {exc}")

ec3, ec4 = st.columns(2)

# ── Excel district-wise ───────────────────────────────────────────────────────
with ec3:
    st.markdown(
        '<div class="export-card">🗂️ <strong>District-wise Excel Workbook</strong><br>'
        '<small>One worksheet per district, each with full formatting and filters.</small></div>',
        unsafe_allow_html=True,
    )
    try:
        xl_dist_bytes = export_excel_district(records)
        st.download_button(
            label=f"⬇️ Download District Excel",
            data=xl_dist_bytes,
            file_name=f"{base_filename}_district.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            key="dl_excel_dist",
        )
    except Exception as exc:
        st.error(f"District Excel export failed: {exc}")

# ── PDF district-wise ─────────────────────────────────────────────────────────
with ec4:
    st.markdown(
        '<div class="export-card">📑 <strong>District-wise PDF Report</strong><br>'
        '<small>Branded PDF with Veerexa Technologies header, one section per district.</small></div>',
        unsafe_allow_html=True,
    )
    try:
        pdf_bytes = export_pdf_district(records, state=f_state if f_state != "All" else "")
        st.download_button(
            label=f"⬇️ Download PDF Report",
            data=pdf_bytes,
            file_name=f"{base_filename}_report.pdf",
            mime="application/pdf",
            use_container_width=True,
            key="dl_pdf",
        )
    except Exception as exc:
        st.error(f"PDF export failed: {exc}")

# ─────────────────────────────────────────────────────────────────────────────
# Preview
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("---")
with st.expander("👁️ Preview exported data (first 20 rows)"):
    import pandas as pd
    from services.export_service import EXPORT_COLUMNS

    preview_rows = []
    for r in records[:20]:
        row = {header: r.get(field, "") for field, header in EXPORT_COLUMNS}
        preview_rows.append(row)

    if preview_rows:
        st.dataframe(
            pd.DataFrame(preview_rows),
            use_container_width=True,
            hide_index=True,
        )

# ─────────────────────────────────────────────────────────────────────────────
# Attribution notice
# ─────────────────────────────────────────────────────────────────────────────
st.markdown(
    """
    <div style="margin-top:1.5rem;padding:1rem;background:#f8f6ff;border-radius:8px;
                border:1px solid #d5cefd;font-size:0.78rem;color:#5A4FCF;">
        <strong>📌 Data Attribution</strong><br>
        Exported data sourced from the Google Places API (New).
        When sharing or using this data, you must comply with
        <a href="https://cloud.google.com/maps-platform/terms" target="_blank">
        Google Maps Platform Terms of Service</a>.
        API keys are <em>never</em> included in exported files.
    </div>
    """,
    unsafe_allow_html=True,
)
