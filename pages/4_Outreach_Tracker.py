"""
pages/4_Outreach_Tracker.py — Track communication status, log outreach, and schedule follow-ups.
"""

from __future__ import annotations

from datetime import datetime, date

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import func

load_dotenv()

from database.connection import get_session
from database.migrations import initialise_database
from models.school import School, OutreachLog

initialise_database()

st.set_page_config(
    page_title="Outreach Tracker — Veerexa Lead Finder", page_icon="📣", layout="wide"
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

CHANNELS = ["", "WhatsApp", "Instagram DM", "Phone Call", "Email", "LinkedIn", "Other"]

STATUS_COLORS = {
    "New": "#1a73e8",
    "Needs verification": "#b06000",
    "Ready to contact": "#1E1060",
    "WhatsApp sent": "#25D366",
    "Instagram DM sent": "#C13584",
    "Called": "#5A4FCF",
    "Follow-up required": "#f4511e",
    "Interested": "#1e8e3e",
    "Demo scheduled": "#0a7c42",
    "Not interested": "#c5221f",
    "No response": "#80868b",
}

st.title("📣 Outreach Tracker")
st.caption("Log and manage your school outreach communications.")

# ─────────────────────────────────────────────────────────────────────────────
# Summary by outreach status
# ─────────────────────────────────────────────────────────────────────────────
with get_session() as session:
    status_counts = (
        session.query(School.outreach_status, func.count(School.id))
        .group_by(School.outreach_status)
        .all()
    )

status_map = {s: c for s, c in status_counts}
total = sum(status_map.values())

st.markdown("### 📊 Pipeline Overview")
if total == 0:
    st.info("No schools in the database yet. Fetch schools first.", icon="ℹ️")
else:
    col_count = 4
    cols = st.columns(col_count)
    for idx, status in enumerate(OUTREACH_STATUSES):
        count = status_map.get(status, 0)
        color = STATUS_COLORS.get(status, "#5A4FCF")
        cols[idx % col_count].markdown(
            f"""
            <div style="background:linear-gradient(135deg,#f8f6ff,#ede9ff);
                        border-left:4px solid {color};
                        border-radius:0 10px 10px 0;
                        padding:.7rem 1rem;margin-bottom:.5rem;">
                <div style="font-size:.7rem;font-weight:700;color:{color};
                            text-transform:uppercase;letter-spacing:.04em;">{status}</div>
                <div style="font-size:1.6rem;font-weight:800;color:#1E1060;">{count}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

st.markdown("---")

# ─────────────────────────────────────────────────────────────────────────────
# Log outreach for a school
# ─────────────────────────────────────────────────────────────────────────────
st.subheader("📝 Log Outreach Activity")

# Search for school
search_name = st.text_input("Search school by name", placeholder="Start typing…", key="outreach_search")

if search_name:
    with get_session() as session:
        results = (
            session.query(School.id, School.name, School.city, School.outreach_status)
            .filter(School.name.ilike(f"%{search_name}%"))
            .limit(20)
            .all()
        )
    school_options = {f"[{r[0]}] {r[1]} — {r[2] or ''} ({r[3] or 'New'})": r[0] for r in results}

    if school_options:
        selected_label = st.selectbox("Select school", list(school_options.keys()))
        selected_school_id = school_options[selected_label]

        with get_session() as session:
            school = session.query(School).filter_by(id=selected_school_id).first()
            school_data = school.to_dict() if school else {}

        if school_data:
            # Quick actions (read-only info, links only — no auto-send)
            st.markdown("#### 🔗 Contact Details")
            qa1, qa2, qa3, qa4 = st.columns(4)
            if school_data.get("phone"):
                qa1.markdown(
                    f"📞 **Phone**\n\n`{school_data['phone']}`\n\n"
                    f"*(Copy and dial manually)*"
                )
            if school_data.get("website"):
                qa2.markdown(
                    f"🌐 **Website**\n\n[Open]({school_data['website']})"
                )
            if school_data.get("maps_url"):
                qa3.markdown(
                    f"🗺️ **Maps**\n\n[Open]({school_data['maps_url']})"
                )
            if school_data.get("instagram"):
                qa4.markdown(
                    f"📸 **Instagram**\n\n[Open]({school_data['instagram']})"
                )
            if school_data.get("whatsapp"):
                st.markdown(
                    f"💬 **WhatsApp link:** [{school_data['whatsapp']}]({school_data['whatsapp']}) "
                    f"*(open manually in WhatsApp)*"
                )

            st.markdown("---")
            st.markdown("#### ✍️ Log New Outreach")

            with st.form("log_outreach_form"):
                lc1, lc2, lc3 = st.columns(3)
                new_status = lc1.selectbox(
                    "New Status",
                    OUTREACH_STATUSES,
                    index=OUTREACH_STATUSES.index(school_data.get("outreach_status", "New"))
                    if school_data.get("outreach_status") in OUTREACH_STATUSES
                    else 0,
                )
                channel = lc2.selectbox("Communication Channel", CHANNELS)
                contact_date = lc3.date_input("Contact Date", value=date.today())

                lc4, lc5 = st.columns(2)
                follow_up_date = lc4.date_input("Follow-up Date (optional)", value=None)
                _ = lc5.empty()

                log_notes = st.text_area("Notes / details", height=80, placeholder="What was discussed?")

                if st.form_submit_button("📋 Save Outreach Log"):
                    with get_session() as session:
                        # Update school status
                        school = session.query(School).filter_by(id=selected_school_id).first()
                        if school:
                            school.outreach_status = new_status
                            school.last_checked = datetime.utcnow()

                        # Add log entry
                        log = OutreachLog(
                            school_id=selected_school_id,
                            status=new_status,
                            channel=channel or None,
                            contact_date=datetime.combine(contact_date, datetime.min.time()) if contact_date else None,
                            follow_up_date=datetime.combine(follow_up_date, datetime.min.time()) if follow_up_date else None,
                            notes=log_notes.strip() or None,
                            created_at=datetime.utcnow(),
                        )
                        session.add(log)
                    st.success(f"✅ Outreach logged. Status updated to **{new_status}**.")
                    st.rerun()

            # Show log history
            with get_session() as session:
                logs = (
                    session.query(OutreachLog)
                    .filter_by(school_id=selected_school_id)
                    .order_by(OutreachLog.created_at.desc())
                    .all()
                )
                log_rows = [
                    {
                        "Date": l.contact_date.strftime("%d %b %Y") if l.contact_date else "—",
                        "Status": l.status,
                        "Channel": l.channel or "—",
                        "Follow-up": l.follow_up_date.strftime("%d %b %Y") if l.follow_up_date else "—",
                        "Notes": l.notes or "",
                        "Logged at": l.created_at.strftime("%d %b %Y %H:%M") if l.created_at else "",
                    }
                    for l in logs
                ]

            if log_rows:
                st.markdown("#### 📜 Outreach History")
                st.dataframe(pd.DataFrame(log_rows), use_container_width=True, hide_index=True)
    else:
        st.info("No schools found matching that name.")

st.markdown("---")

# ─────────────────────────────────────────────────────────────────────────────
# Upcoming follow-ups
# ─────────────────────────────────────────────────────────────────────────────
st.subheader("⏰ Upcoming Follow-ups")

with get_session() as session:
    follow_ups = (
        session.query(OutreachLog, School)
        .join(School, OutreachLog.school_id == School.id)
        .filter(
            OutreachLog.follow_up_date.isnot(None),
            OutreachLog.follow_up_date >= datetime.utcnow(),
        )
        .order_by(OutreachLog.follow_up_date)
        .limit(50)
        .all()
    )

    fu_rows = [
        {
            "Follow-up Date": log.follow_up_date.strftime("%d %b %Y") if log.follow_up_date else "",
            "School": school.name,
            "City": school.city or "",
            "Phone": school.phone or "—",
            "Status": log.status,
            "Notes": log.notes or "",
        }
        for log, school in follow_ups
    ]

if fu_rows:
    st.dataframe(pd.DataFrame(fu_rows), use_container_width=True, hide_index=True)
else:
    st.info("No upcoming follow-ups scheduled.", icon="✅")

st.markdown("---")

# ─────────────────────────────────────────────────────────────────────────────
# Kanban-style summary table
# ─────────────────────────────────────────────────────────────────────────────
st.subheader("📋 All Leads by Status")
filter_status = st.selectbox("Filter by status", ["All"] + OUTREACH_STATUSES, key="tracker_status_filter")

with get_session() as session:
    q = session.query(School)
    if filter_status != "All":
        q = q.filter(School.outreach_status == filter_status)
    schools = q.order_by(School.created_at.desc()).limit(200).all()

    rows = [
        {
            "ID": s.id,
            "School": s.name,
            "City": s.city or "",
            "District": s.district or "",
            "Phone": s.phone or "—",
            "Email": s.email or "—",
            "Status": s.outreach_status or "New",
            "Last Checked": s.last_checked.strftime("%d %b %Y") if s.last_checked else "—",
            "Notes": s.notes or "",
        }
        for s in schools
    ]

if rows:
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
else:
    st.info("No records found.", icon="ℹ️")
