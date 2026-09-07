"""
pages/3_Leads.py — Browse, filter, search, and manage school leads.
"""

from __future__ import annotations

import os
from datetime import datetime

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import text

load_dotenv()

from database.connection import get_session
from database.migrations import initialise_database
from models.school import School, OutreachLog
from utils.india_geo import get_states, get_districts
from utils.phone_utils import normalize_phone

initialise_database()

st.set_page_config(
    page_title="Leads — Veerexa Lead Finder", page_icon="📋", layout="wide"
)

st.markdown(
    """<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    html,body,[class*="css"]{font-family:'Inter',sans-serif;}
    [data-testid="stSidebar"]{background:linear-gradient(160deg,#1E1060 0%,#3B2F8C 60%,#5A4FCF 100%);}
    [data-testid="stSidebar"] *{color:#E8E4FF!important;}
    .stButton>button{background:linear-gradient(135deg,#3B2F8C,#5A4FCF);color:#fff;border:none;border-radius:8px;font-weight:600;padding:.4rem 1rem;}
    h1{color:#1E1060;} h2{color:#3B2F8C;} h3{color:#5A4FCF;}
    </style>""",
    unsafe_allow_html=True,
)

OUTREACH_STATUSES = [
    "New", "Needs verification", "Ready to contact",
    "WhatsApp sent", "Instagram DM sent", "Called",
    "Follow-up required", "Interested", "Demo scheduled",
    "Not interested", "No response",
]

st.title("📋 Leads")
st.caption("Browse, filter, and manage all discovered school leads.")

# ─────────────────────────────────────────────────────────────────────────────
# Filters sidebar
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🔎 Filters")
    f_state = st.selectbox("State", ["All"] + get_states(), key="leads_state")
    f_district = st.text_input("District (type to filter)", key="leads_district")
    f_city = st.text_input("City (type to filter)", key="leads_city")
    f_search = st.text_input("Search school name", key="leads_search")
    st.markdown("---")
    f_phone = st.checkbox("Has phone", key="leads_phone")
    f_website = st.checkbox("Has website", key="leads_website")
    f_instagram = st.checkbox("Has Instagram", key="leads_instagram")
    f_email = st.checkbox("Has email", key="leads_email")
    f_verified = st.checkbox("Verified only", key="leads_verified")
    st.markdown("---")
    f_outreach = st.selectbox("Outreach status", ["All"] + OUTREACH_STATUSES, key="leads_outreach")
    f_min_rating = st.slider("Min rating", 0.0, 5.0, 0.0, 0.1, key="leads_rating")
    st.markdown("---")
    page_size = st.selectbox("Rows per page", [25, 50, 100, 200], key="leads_pagesize")

# ─────────────────────────────────────────────────────────────────────────────
# Query
# ─────────────────────────────────────────────────────────────────────────────
with get_session() as session:
    query = session.query(School)

    if f_state != "All":
        query = query.filter(School.state == f_state)
    if f_district:
        query = query.filter(School.district.ilike(f"%{f_district}%"))
    if f_city:
        query = query.filter(School.city.ilike(f"%{f_city}%"))
    if f_search:
        query = query.filter(School.name.ilike(f"%{f_search}%"))
    if f_phone:
        query = query.filter(School.phone.isnot(None), School.phone != "")
    if f_website:
        query = query.filter(School.website.isnot(None), School.website != "")
    if f_instagram:
        query = query.filter(School.instagram.isnot(None), School.instagram != "")
    if f_email:
        query = query.filter(School.email.isnot(None), School.email != "")
    if f_verified:
        query = query.filter(School.is_verified == True)
    if f_outreach != "All":
        query = query.filter(School.outreach_status == f_outreach)
    if f_min_rating > 0:
        query = query.filter(School.rating >= f_min_rating)

    total_count = query.count()
    schools = query.order_by(School.created_at.desc()).all()
    records = [s.to_dict() for s in schools]

# ─────────────────────────────────────────────────────────────────────────────
# Pagination
# ─────────────────────────────────────────────────────────────────────────────
total_pages = max(1, (total_count + page_size - 1) // page_size)
col_count, col_page = st.columns([3, 1])
col_count.markdown(f"**{total_count} schools found**")
current_page = col_page.number_input("Page", min_value=1, max_value=total_pages, value=1, key="leads_page")
start_idx = (current_page - 1) * page_size
end_idx = start_idx + page_size
page_records = records[start_idx:end_idx]

# ─────────────────────────────────────────────────────────────────────────────
# Table display
# ─────────────────────────────────────────────────────────────────────────────
if not page_records:
    st.info(
        "No schools match your filters. Try clearing some filters or fetch schools first.",
        icon="ℹ️",
    )
else:
    # Build display dataframe
    display_rows = []
    for r in page_records:
        display_rows.append({
            "ID": r["id"],
            "School Name": r["name"],
            "City": r["city"] or "",
            "District": r["district"] or "",
            "State": r["state"] or "",
            "Phone": r["phone"] or "—",
            "Email": r["email"] or "—",
            "Rating": r["rating"] if r["rating"] else "—",
            "Status": r["outreach_status"] or "New",
            "Verified": "✅" if r["is_verified"] else "—",
            "Website": r["website"] or "",
            "Maps": r["maps_url"] or "",
            "Instagram": r["instagram"] or "",
        })

    df = pd.DataFrame(display_rows)

    # Column configuration with links
    col_config = {
        "Website": st.column_config.LinkColumn("🌐 Website", display_text="Open"),
        "Maps": st.column_config.LinkColumn("🗺️ Maps", display_text="Open"),
        "Instagram": st.column_config.LinkColumn("📸 Instagram", display_text="Open"),
        "ID": st.column_config.NumberColumn("ID", width="small"),
        "Rating": st.column_config.NumberColumn("⭐ Rating", format="%.1f"),
    }

    selected_ids: list[int] = []
    selection_event = st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config=col_config,
        on_select="rerun",
        selection_mode="multi-row",
        key="leads_table",
    )

    if selection_event and selection_event.selection.rows:
        selected_ids = [page_records[i]["id"] for i in selection_event.selection.rows]

# ─────────────────────────────────────────────────────────────────────────────
# Bulk actions
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("---")
st.subheader("⚡ Bulk Actions")
ba1, ba2, ba3, ba4 = st.columns(4)

if ba1.button("✅ Mark Selected Verified", use_container_width=True):
    if not selected_ids:
        st.warning("No rows selected. Click rows in the table to select them.")
    else:
        with get_session() as session:
            session.query(School).filter(School.id.in_(selected_ids)).update(
                {"is_verified": True, "verification_status": "Verified from official website"},
                synchronize_session=False,
            )
        st.success(f"Marked {len(selected_ids)} schools as verified.")
        st.rerun()

if ba2.button("📣 Mark Selected Contacted", use_container_width=True):
    if not selected_ids:
        st.warning("No rows selected.")
    else:
        with get_session() as session:
            session.query(School).filter(School.id.in_(selected_ids)).update(
                {"outreach_status": "Called"}, synchronize_session=False
            )
        st.success(f"Marked {len(selected_ids)} schools as contacted.")
        st.rerun()

bulk_status = ba3.selectbox("Change status to", OUTREACH_STATUSES, key="bulk_status")
if ba3.button("🔄 Apply Status", use_container_width=True):
    if not selected_ids:
        st.warning("No rows selected.")
    else:
        with get_session() as session:
            session.query(School).filter(School.id.in_(selected_ids)).update(
                {"outreach_status": bulk_status}, synchronize_session=False
            )
        st.success(f"Updated {len(selected_ids)} schools to '{bulk_status}'.")
        st.rerun()

if ba4.button("🗑️ Delete Selected", use_container_width=True):
    if not selected_ids:
        st.warning("No rows selected.")
    else:
        with get_session() as session:
            session.query(School).filter(School.id.in_(selected_ids)).delete(
                synchronize_session=False
            )
        st.success(f"Deleted {len(selected_ids)} records.")
        st.rerun()

# ─────────────────────────────────────────────────────────────────────────────
# Edit / detail panel
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("---")
st.subheader("✏️ Edit Lead")
edit_id = st.number_input("Enter school ID to edit", min_value=1, step=1, key="edit_id_input")

if st.button("Load School for Editing", key="load_edit"):
    with get_session() as session:
        school = session.query(School).filter_by(id=int(edit_id)).first()
        if school:
            st.session_state["edit_school"] = school.to_dict()
        else:
            st.error(f"No school found with ID {edit_id}.")

if "edit_school" in st.session_state:
    es = st.session_state["edit_school"]
    with st.form("edit_school_form"):
        st.markdown(f"**Editing:** {es['name']}")
        ec1, ec2 = st.columns(2)
        e_name = ec1.text_input("School Name", value=es.get("name", ""))
        e_phone = ec2.text_input("Phone", value=es.get("phone", "") or "")
        ec3, ec4 = st.columns(2)
        e_website = ec3.text_input("Website", value=es.get("website", "") or "")
        e_email = ec4.text_input("Email", value=es.get("email", "") or "")
        ec5, ec6 = st.columns(2)
        e_instagram = ec5.text_input("Instagram URL", value=es.get("instagram", "") or "")
        e_instagram_status = ec6.selectbox(
            "Instagram Status",
            ["Needs manual verification", "Verified from official website"],
            index=0 if es.get("instagram_status") == "Needs manual verification" else 1,
        )
        ec7, ec8, ec9 = st.columns(3)
        e_city = ec7.text_input("City", value=es.get("city", "") or "")
        e_district = ec8.text_input("District", value=es.get("district", "") or "")
        e_state = ec9.text_input("State", value=es.get("state", "") or "")
        e_address = st.text_area("Address", value=es.get("address", "") or "", height=68)
        e_outreach = st.selectbox(
            "Outreach Status",
            OUTREACH_STATUSES,
            index=OUTREACH_STATUSES.index(es.get("outreach_status", "New"))
            if es.get("outreach_status") in OUTREACH_STATUSES
            else 0,
        )
        e_notes = st.text_area("Notes", value=es.get("notes", "") or "", height=68)
        e_verified = st.checkbox("Mark as Verified", value=bool(es.get("is_verified")))

        if st.form_submit_button("💾 Save Changes"):
            phone_norm, _ = normalize_phone(e_phone.strip()) if e_phone else ("", "")
            with get_session() as session:
                school = session.query(School).filter_by(id=es["id"]).first()
                if school:
                    school.name = e_name.strip()
                    school.phone = phone_norm or None
                    school.website = e_website.strip() or None
                    school.email = e_email.strip() or None
                    school.instagram = e_instagram.strip() or None
                    school.instagram_status = e_instagram_status
                    school.city = e_city.strip() or None
                    school.district = e_district.strip() or None
                    school.state = e_state.strip() or None
                    school.address = e_address.strip() or None
                    school.outreach_status = e_outreach
                    school.notes = e_notes.strip() or None
                    school.is_verified = e_verified
                    school.last_checked = datetime.utcnow()
            st.success(f"✅ '{e_name}' updated.")
            del st.session_state["edit_school"]
            st.rerun()
