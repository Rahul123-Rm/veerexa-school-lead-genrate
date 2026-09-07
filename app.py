"""
app.py — Veerexa School Lead Finder
Entry point. Run with: streamlit run app.py
"""

from __future__ import annotations

import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialise database (idempotent — safe to call every startup)
from database.migrations import initialise_database
initialise_database()

# ---------------------------------------------------------------------------
# Page configuration
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Veerexa School Lead Finder",
    page_icon="🏫",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "About": "Veerexa School Lead Finder v1.0 — Built for Veerexa Technologies",
    },
)

# ---------------------------------------------------------------------------
# Global CSS — blue / white / purple brand theme
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    /* ── Sidebar ── */
    [data-testid="stSidebar"] {
        background: linear-gradient(160deg, #1E1060 0%, #3B2F8C 60%, #5A4FCF 100%);
        border-right: none;
    }
    [data-testid="stSidebar"] * {
        color: #E8E4FF !important;
    }
    [data-testid="stSidebar"] .stSelectbox label,
    [data-testid="stSidebar"] .stTextInput label {
        color: #C8C0EE !important;
    }
    [data-testid="stSidebarNav"] a {
        color: #C8C0EE !important;
        border-radius: 8px;
        transition: background 0.2s;
    }
    [data-testid="stSidebarNav"] a:hover {
        background: rgba(255,255,255,0.12) !important;
        color: #fff !important;
    }
    [data-testid="stSidebarNav"] a[aria-current="page"] {
        background: rgba(255,255,255,0.18) !important;
        color: #fff !important;
        font-weight: 600;
    }

    /* ── Main area ── */
    .main .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
    }

    /* ── Metric cards ── */
    [data-testid="stMetric"] {
        background: linear-gradient(135deg, #f8f6ff 0%, #ede9ff 100%);
        border-radius: 12px;
        padding: 1rem 1.2rem;
        border: 1px solid #d5cefd;
        box-shadow: 0 2px 8px rgba(90,79,207,0.08);
        transition: transform 0.2s, box-shadow 0.2s;
    }
    [data-testid="stMetric"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 18px rgba(90,79,207,0.15);
    }
    [data-testid="stMetricLabel"] {
        font-size: 0.8rem !important;
        font-weight: 600 !important;
        color: #5A4FCF !important;
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }
    [data-testid="stMetricValue"] {
        font-size: 2rem !important;
        font-weight: 700 !important;
        color: #1E1060 !important;
    }

    /* ── Buttons ── */
    .stButton > button {
        background: linear-gradient(135deg, #3B2F8C, #5A4FCF);
        color: white;
        border: none;
        border-radius: 8px;
        font-weight: 600;
        padding: 0.5rem 1.2rem;
        transition: all 0.2s;
        box-shadow: 0 2px 8px rgba(59,47,140,0.3);
    }
    .stButton > button:hover {
        background: linear-gradient(135deg, #4d3fb0, #6a5fdf);
        box-shadow: 0 4px 14px rgba(59,47,140,0.4);
        transform: translateY(-1px);
    }
    .stButton > button:active {
        transform: translateY(0);
    }

    /* ── Danger button ── */
    .stButton > button[kind="secondary"] {
        background: linear-gradient(135deg, #c0392b, #e74c3c);
        color: white;
    }

    /* ── Progress bar ── */
    .stProgress > div > div > div > div {
        background: linear-gradient(90deg, #3B2F8C, #5A4FCF, #7C6FEF);
    }

    /* ── DataFrames / tables ── */
    .stDataFrame {
        border-radius: 10px;
        overflow: hidden;
        border: 1px solid #d5cefd;
    }

    /* ── Section headers ── */
    h1 { color: #1E1060; }
    h2 { color: #3B2F8C; }
    h3 { color: #5A4FCF; }

    /* ── Status badges ── */
    .badge {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
    }
    .badge-new        { background: #e8f4fd; color: #1a73e8; }
    .badge-interested { background: #e6f4ea; color: #1e8e3e; }
    .badge-contacted  { background: #fef7e0; color: #b06000; }
    .badge-notint     { background: #fce8e6; color: #c5221f; }

    /* ── Info boxes ── */
    .info-box {
        background: linear-gradient(135deg, #ede9ff, #f8f6ff);
        border-left: 4px solid #5A4FCF;
        padding: 1rem 1.2rem;
        border-radius: 0 10px 10px 0;
        margin: 0.5rem 0;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Sidebar branding
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown(
        """
        <div style="text-align:center; padding: 1rem 0 0.5rem;">
            <div style="font-size:2.5rem;">🏫</div>
            <div style="font-size:1.1rem; font-weight:700; color:#fff; letter-spacing:0.02em;">
                Veerexa
            </div>
            <div style="font-size:0.75rem; color:#C8C0EE; letter-spacing:0.08em; text-transform:uppercase;">
                School Lead Finder
            </div>
        </div>
        <hr style="border-color:rgba(255,255,255,0.15); margin: 0.8rem 0;">
        """,
        unsafe_allow_html=True,
    )

    # API key status
    api_key = os.getenv("GOOGLE_MAPS_API_KEY", "")
    if api_key and api_key != "your_google_places_api_key_here":
        st.markdown(
            '<div style="text-align:center;margin-bottom:0.5rem;">'
            '<span style="background:#1e8e3e;color:#fff;padding:3px 12px;border-radius:20px;font-size:0.72rem;font-weight:600;">✓ API KEY CONFIGURED</span>'
            "</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div style="text-align:center;margin-bottom:0.5rem;">'
            '<span style="background:#c5221f;color:#fff;padding:3px 12px;border-radius:20px;font-size:0.72rem;font-weight:600;">⚠ API KEY MISSING</span>'
            "</div>",
            unsafe_allow_html=True,
        )

# ---------------------------------------------------------------------------
# Default landing page content (Dashboard will handle the real dashboard)
# ---------------------------------------------------------------------------
st.markdown(
    """
    <div style="text-align:center; padding: 3rem 2rem;">
        <div style="font-size:4rem; margin-bottom:1rem;">🏫</div>
        <h1 style="color:#1E1060; font-size:2.2rem; font-weight:800; margin-bottom:0.5rem;">
            Veerexa School Lead Finder
        </h1>
        <p style="color:#5A4FCF; font-size:1.1rem; margin-bottom:2rem;">
            Discover schools, collect contact information, and manage your outreach pipeline.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

# API key warning
api_key = os.getenv("GOOGLE_MAPS_API_KEY", "")
if not api_key or api_key == "your_google_places_api_key_here":
    st.warning(
        "⚠️ **Google Maps API key not configured.** "
        "The app runs in offline mode — you can manually add and manage leads, "
        "but school discovery via Google Places is disabled until an API key is set. "
        "See the **README** for setup instructions.",
        icon="⚠️",
    )

# Quick navigation cards
col1, col2, col3, col4, col5 = st.columns(5)
cards = [
    ("📊", "Dashboard", "View summary stats and district-wise analytics"),
    ("🔍", "Fetch Schools", "Search schools via Google Places API"),
    ("📋", "Leads", "Browse, filter, and manage all school leads"),
    ("📣", "Outreach Tracker", "Track communication status and follow-ups"),
    ("📤", "Export", "Export leads to CSV, Excel or PDF"),
]
for col, (icon, title, desc) in zip([col1, col2, col3, col4, col5], cards):
    with col:
        st.markdown(
            f"""
            <div style="
                background: linear-gradient(135deg, #f8f6ff, #ede9ff);
                border: 1px solid #d5cefd;
                border-radius: 12px;
                padding: 1.2rem;
                text-align: center;
                cursor: pointer;
                transition: all 0.2s;
                min-height: 130px;
            ">
                <div style="font-size:2rem;">{icon}</div>
                <div style="font-weight:700; color:#1E1060; margin-top:0.4rem;">{title}</div>
                <div style="font-size:0.75rem; color:#6c5fcc; margin-top:0.3rem;">{desc}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

st.markdown("<br>", unsafe_allow_html=True)
st.info(
    "👈 **Use the sidebar** to navigate between pages. "
    "Start with **Fetch Schools** to discover schools in your target area.",
    icon="ℹ️",
)

# Attribution notice
st.markdown(
    """
    <div style="margin-top: 2rem; padding: 1rem; background:#f8f6ff; border-radius:8px;
                border: 1px solid #d5cefd; font-size:0.8rem; color:#5A4FCF;">
        <strong>📌 Google Places Data Attribution</strong><br>
        School data is sourced from the Google Places API (New).
        By using this application you agree to comply with
        <a href="https://cloud.google.com/maps-platform/terms" target="_blank">Google Maps Platform Terms of Service</a>.
        Ensure billing alerts and API quotas are configured in
        <a href="https://console.cloud.google.com/" target="_blank">Google Cloud Console</a>.
        This tool does not store API keys in exported files or logs.
    </div>
    """,
    unsafe_allow_html=True,
)
