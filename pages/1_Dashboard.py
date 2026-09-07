"""
pages/1_Dashboard.py — Summary statistics and district-wise analytics.
"""

from __future__ import annotations

import os

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import func, text

load_dotenv()

from database.connection import get_session, get_db_size_mb
from database.migrations import initialise_database
from models.school import School
from utils.rate_limiter import RateLimiter

initialise_database()

st.set_page_config(page_title="Dashboard — Veerexa Lead Finder", page_icon="📊", layout="wide")

# Shared CSS (injected on each page for consistency)
st.markdown(
    """<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    html,body,[class*="css"]{font-family:'Inter',sans-serif;}
    [data-testid="stSidebar"]{background:linear-gradient(160deg,#1E1060 0%,#3B2F8C 60%,#5A4FCF 100%);}
    [data-testid="stSidebar"] *{color:#E8E4FF!important;}
    [data-testid="stMetric"]{background:linear-gradient(135deg,#f8f6ff,#ede9ff);border-radius:12px;padding:1rem 1.2rem;border:1px solid #d5cefd;box-shadow:0 2px 8px rgba(90,79,207,.08);}
    [data-testid="stMetricLabel"]{font-size:.8rem!important;font-weight:600!important;color:#5A4FCF!important;text-transform:uppercase;letter-spacing:.04em;}
    [data-testid="stMetricValue"]{font-size:2rem!important;font-weight:700!important;color:#1E1060!important;}
    h1{color:#1E1060;} h2{color:#3B2F8C;} h3{color:#5A4FCF;}
    </style>""",
    unsafe_allow_html=True,
)

st.title("📊 Dashboard")
st.caption("Real-time summary of your school lead database.")

# ---------------------------------------------------------------------------
# Fetch summary stats
# ---------------------------------------------------------------------------
with get_session() as session:
    total = session.query(func.count(School.id)).scalar() or 0
    with_phone = session.query(func.count(School.id)).filter(School.phone.isnot(None), School.phone != "").scalar() or 0
    with_website = session.query(func.count(School.id)).filter(School.website.isnot(None), School.website != "").scalar() or 0
    with_instagram = session.query(func.count(School.id)).filter(School.instagram.isnot(None), School.instagram != "").scalar() or 0
    with_email = session.query(func.count(School.id)).filter(School.email.isnot(None), School.email != "").scalar() or 0
    verified = session.query(func.count(School.id)).filter(School.is_verified == True).scalar() or 0
    contacted = session.query(func.count(School.id)).filter(
        School.outreach_status.in_(["WhatsApp sent", "Instagram DM sent", "Called", "Follow-up required"])
    ).scalar() or 0
    interested = session.query(func.count(School.id)).filter(
        School.outreach_status.in_(["Interested", "Demo scheduled"])
    ).scalar() or 0

    # Rate limiter data
    limiter = RateLimiter(session)
    used_today = limiter.get_used_today()
    daily_limit = limiter.daily_limit
    usage_history = limiter.get_usage_history(days=7)

    # District-wise stats
    district_rows = session.execute(
        text(
            """
            SELECT
                COALESCE(district,'Unknown') AS district,
                COALESCE(state,'Unknown') AS state,
                COUNT(*) AS total,
                SUM(CASE WHEN phone IS NOT NULL AND phone != '' THEN 1 ELSE 0 END) AS phones,
                SUM(CASE WHEN website IS NOT NULL AND website != '' THEN 1 ELSE 0 END) AS websites,
                SUM(CASE WHEN email IS NOT NULL AND email != '' THEN 1 ELSE 0 END) AS emails,
                SUM(CASE WHEN is_verified = 1 THEN 1 ELSE 0 END) AS verified
            FROM schools
            GROUP BY district, state
            ORDER BY total DESC
            """
        )
    ).fetchall()

# ---------------------------------------------------------------------------
# Summary cards
# ---------------------------------------------------------------------------
st.markdown("### 🏆 Summary")
c1, c2, c3, c4 = st.columns(4)
c1.metric("🏫 Total Schools", total)
c2.metric("📞 With Phone", with_phone)
c3.metric("🌐 With Website", with_website)
c4.metric("📸 With Instagram", with_instagram)

c5, c6, c7, c8 = st.columns(4)
c5.metric("📧 With Email", with_email)
c6.metric("✅ Verified Leads", verified)
c7.metric("📣 Contacted", contacted)
c8.metric("⭐ Interested", interested)

st.markdown("---")

# ---------------------------------------------------------------------------
# API usage
# ---------------------------------------------------------------------------
st.markdown("### 🔢 API Usage Today")
remaining = max(0, daily_limit - used_today)
usage_pct = min(1.0, used_today / daily_limit) if daily_limit > 0 else 0.0

col_u1, col_u2, col_u3 = st.columns(3)
col_u1.metric("Requests Used Today", used_today)
col_u2.metric("Daily Limit", daily_limit)
col_u3.metric("Remaining", remaining)

if usage_pct > 0.8:
    st.warning(f"⚠️ You have used {usage_pct*100:.0f}% of your daily API request limit.")
else:
    st.progress(usage_pct, text=f"{usage_pct*100:.0f}% of daily limit used")

# Usage history
if usage_history:
    hist_df = pd.DataFrame(usage_history)
    hist_df.columns = ["Date", "Requests"]
    st.markdown("**Last 7 days API usage:**")
    st.bar_chart(hist_df.set_index("Date"))

st.markdown("---")

# ---------------------------------------------------------------------------
# District-wise table
# ---------------------------------------------------------------------------
st.markdown("### 🗺️ District-wise Statistics")

if district_rows:
    df = pd.DataFrame(
        district_rows,
        columns=["District", "State", "Total", "📞 Phones", "🌐 Websites", "📧 Emails", "✅ Verified"],
    )
    st.dataframe(df, use_container_width=True, hide_index=True)
else:
    st.info(
        "No schools in the database yet. "
        "Go to **Fetch Schools** to discover schools in your target area.",
        icon="ℹ️",
    )

# ---------------------------------------------------------------------------
# DB info
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown(
    f"<small>💾 Database size: **{get_db_size_mb()} MB** &nbsp;|&nbsp; "
    f"Total records: **{total}**</small>",
    unsafe_allow_html=True,
)
