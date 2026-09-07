"""
pages/2_Fetch_Schools.py — Google Places school discovery with live progress.
"""

from __future__ import annotations

import os
import time
from datetime import datetime
from threading import Event

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from database.connection import get_session
from database.migrations import initialise_database
from models.school import School
from services.google_places import GooglePlacesClient, PlacesAPIError, build_query_preview, QUERY_TEMPLATES
from services.website_scanner import WebsiteScanner
from utils.dedup_utils import deduplicate, is_duplicate_of_existing
from utils.india_geo import get_states, get_districts, get_cities
from utils.phone_utils import CONTACT_SOURCE_GOOGLE, CONTACT_SOURCE_WEBSITE, VERIFICATION_GOOGLE
from utils.rate_limiter import RateLimiter

initialise_database()

st.set_page_config(
    page_title="Fetch Schools — Veerexa Lead Finder", page_icon="🔍", layout="wide"
)

st.markdown(
    """<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    html,body,[class*="css"]{font-family:'Inter',sans-serif;}
    [data-testid="stSidebar"]{background:linear-gradient(160deg,#1E1060 0%,#3B2F8C 60%,#5A4FCF 100%);}
    [data-testid="stSidebar"] *{color:#E8E4FF!important;}
    .stButton>button{background:linear-gradient(135deg,#3B2F8C,#5A4FCF);color:#fff;border:none;border-radius:8px;font-weight:600;padding:.5rem 1.2rem;}
    h1{color:#1E1060;} h2{color:#3B2F8C;} h3{color:#5A4FCF;}
    </style>""",
    unsafe_allow_html=True,
)

st.title("🔍 Fetch Schools")
st.caption("Discover schools via Google Places API (New) and collect contact information.")

# ── API key check ─────────────────────────────────────────────────────────────
API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")
API_KEY_VALID = bool(API_KEY and API_KEY != "your_google_places_api_key_here")

if not API_KEY_VALID:
    st.error(
        "⛔ **Google Maps API key not configured.**\n\n"
        "Add your key to the `.env` file:\n"
        "```\nGOOGLE_MAPS_API_KEY=your_actual_key_here\n```\n\n"
        "**Setup steps:**\n"
        "1. Visit [Google Cloud Console](https://console.cloud.google.com/)\n"
        "2. Create a project and enable **Places API (New)**\n"
        "3. Create an API key and restrict it to **Places API (New)**\n"
        "4. Paste the key in your `.env` file and restart the app\n\n"
        "⚠️ **Important:** Configure billing alerts and hard quotas in Google Cloud Console. "
        "This app tracks daily usage locally but does NOT enforce cloud-side limits.",
    )
    st.markdown("---")
    st.info(
        "You can still **manually add school leads** without an API key. "
        "Use the form below to add a school manually.",
        icon="💡",
    )

# ─────────────────────────────────────────────────────────────────────────────
# Manual lead entry (always available)
# ─────────────────────────────────────────────────────────────────────────────
with st.expander("➕ Add School Manually", expanded=not API_KEY_VALID):
    with st.form("manual_entry_form", clear_on_submit=True):
        mc1, mc2 = st.columns(2)
        m_name = mc1.text_input("School Name *", placeholder="e.g. St. Mary's High School")
        m_phone = mc2.text_input("Phone", placeholder="+91-XXXXXXXXXX")
        mc3, mc4 = st.columns(2)
        m_website = mc3.text_input("Website", placeholder="https://")
        m_email = mc4.text_input("Email", placeholder="info@school.edu.in")
        mc5, mc6, mc7 = st.columns(3)
        m_city = mc5.text_input("City")
        m_district = mc6.text_input("District")
        m_state = mc7.selectbox("State", [""] + get_states())
        m_address = st.text_area("Address", height=68)
        m_notes = st.text_input("Notes")

        submitted = st.form_submit_button("💾 Save School")
        if submitted:
            if not m_name.strip():
                st.error("School name is required.")
            else:
                from utils.phone_utils import normalize_phone, CONTACT_SOURCE_MANUAL, VERIFICATION_MANUAL
                phone_norm, _ = normalize_phone(m_phone.strip()) if m_phone else ("", "")
                with get_session() as session:
                    school = School(
                        name=m_name.strip(),
                        phone=phone_norm or None,
                        website=m_website.strip() or None,
                        email=m_email.strip() or None,
                        city=m_city.strip() or None,
                        district=m_district.strip() or None,
                        state=m_state or None,
                        address=m_address.strip() or None,
                        notes=m_notes.strip() or None,
                        contact_source=CONTACT_SOURCE_MANUAL,
                        verification_status=VERIFICATION_MANUAL,
                        outreach_status="New",
                        created_at=datetime.utcnow(),
                    )
                    session.add(school)
                st.success(f"✅ **{m_name}** added successfully!")

st.markdown("---")

# ─────────────────────────────────────────────────────────────────────────────
# Google Places search (only when API key is configured)
# ─────────────────────────────────────────────────────────────────────────────
if API_KEY_VALID:
    st.subheader("🌐 Google Places Search")

    # ── Search configuration ──────────────────────────────────────────────────
    with st.expander("⚙️ Search Configuration", expanded=True):
        col1, col2, col3 = st.columns(3)
        selected_state = col1.selectbox("State *", [""] + get_states(), key="fetch_state")
        districts = get_districts(selected_state) if selected_state else []
        selected_district = col2.selectbox("District", [""] + districts, key="fetch_district")
        cities = get_cities(selected_state, selected_district) if selected_district else []

        col4, col5 = st.columns(2)
        city_options = cities if cities else []
        selected_cities_dropdown = col4.multiselect(
            "Cities / Tehsils (from list)", city_options, key="fetch_cities_dropdown"
        )
        manual_cities = col5.text_area(
            "Additional locations (one per line)",
            placeholder="Enter town, tehsil or locality names",
            height=100,
            key="fetch_cities_manual",
        )

        col6, col7 = st.columns(2)
        max_results = col6.slider("Max results per query", 1, 20, 20)
        max_requests = col7.number_input(
            "Max API requests this run",
            min_value=1,
            max_value=int(os.getenv("MAX_REQUESTS_PER_RUN", "100")),
            value=int(os.getenv("MAX_REQUESTS_PER_RUN", "100")),
        )

        col8, col9 = st.columns(2)
        fetch_details = col8.checkbox("Fetch full Place Details (phone + website)", value=True)
        scan_websites = col9.checkbox(
            "Scan school websites for contact info (slower, more data)", value=False
        )

    # Build location list
    all_cities: list[str] = list(selected_cities_dropdown)
    if manual_cities:
        for line in manual_cities.strip().splitlines():
            line = line.strip()
            if line and line not in all_cities:
                all_cities.append(line)

    # ── Preview ───────────────────────────────────────────────────────────────
    col_prev, col_fetch, col_stop = st.columns([1, 1, 1])

    if col_prev.button("👁️ Preview Search", use_container_width=True):
        if not selected_state:
            st.warning("Please select a state.")
        elif not all_cities:
            st.warning("Please select or enter at least one city/location.")
        else:
            locations = [
                (city, selected_district or city, selected_state)
                for city in all_cities
            ]
            preview = build_query_preview(locations)

            st.markdown("#### 📋 Search Preview")
            p1, p2, p3 = st.columns(3)
            p1.metric("Locations", preview["locations"])
            p2.metric("Query templates", preview["query_templates"])
            p3.metric("Min API requests", preview["min_requests"])

            with get_session() as session:
                limiter = RateLimiter(session)
                remaining = limiter.remaining_today()
            st.info(
                f"Daily API budget remaining: **{remaining}** requests | "
                f"Estimated minimum requests this run: **{preview['min_requests']}**"
            )

            if preview["min_requests"] > max_requests:
                st.warning(
                    f"⚠️ Planned queries ({preview['min_requests']}) exceed your max-requests limit ({max_requests}). "
                    "Increase the limit or reduce locations."
                )

            with st.expander("All planned queries"):
                for q in preview["queries"]:
                    st.markdown(f"• {q}")

            with st.expander("Fields requested"):
                st.markdown("**Text Search:** " + ", ".join(preview["fields_requested"]))
                if fetch_details:
                    st.markdown("**Place Details:** " + ", ".join(preview["detail_fields_requested"]))

    # ── Stop flag (session state) ─────────────────────────────────────────────
    if "stop_search" not in st.session_state:
        st.session_state["stop_search"] = False

    if col_stop.button("🛑 Stop Search", use_container_width=True):
        st.session_state["stop_search"] = True
        st.info("Stop signal sent. The current search will halt after the current request.")

    # ── Fetch button ──────────────────────────────────────────────────────────
    if col_fetch.button("🚀 Fetch Schools", use_container_width=True, type="primary"):
        if not selected_state:
            st.error("Please select a state.")
        elif not all_cities:
            st.error("Please select or enter at least one city/location.")
        else:
            st.session_state["stop_search"] = False

            # Rate limit check
            with get_session() as session:
                limiter = RateLimiter(session)
                if not limiter.can_make_request(1):
                    st.error(
                        f"🚫 Daily API request limit reached ({limiter.daily_limit}). "
                        "Try again tomorrow or increase DAILY_REQUEST_LIMIT in .env."
                    )
                    st.stop()

            st.markdown("---")
            st.subheader("⏳ Fetching in progress…")

            progress_bar = st.progress(0.0)
            status_text = st.empty()
            stats_cols = st.columns(4)
            new_col = stats_cols[0].empty()
            dup_col = stats_cols[1].empty()
            req_col = stats_cols[2].empty()
            fail_col = stats_cols[3].empty()

            log_expander = st.expander("📜 Detailed log", expanded=False)
            log_area = log_expander.empty()
            log_lines: list[str] = []

            new_count = 0
            dup_count = 0
            req_count = 0
            fail_count = 0

            def update_stats():
                new_col.metric("🆕 New", new_count)
                dup_col.metric("🔁 Duplicates", dup_count)
                req_col.metric("📡 Requests", req_count)
                fail_col.metric("❌ Failed", fail_count)

            update_stats()

            def on_progress(msg: str):
                log_lines.append(msg)
                log_area.markdown("\n".join(log_lines[-50:]))
                status_text.markdown(f"**{msg}**")

            def stop_flag() -> bool:
                return st.session_state.get("stop_search", False)

            # Load existing place IDs for deduplication
            with get_session() as session:
                existing_pids: set[str] = {
                    row[0]
                    for row in session.execute(
                        __import__("sqlalchemy").text("SELECT place_id FROM schools WHERE place_id IS NOT NULL")
                    ).fetchall()
                }

            client = GooglePlacesClient(API_KEY)
            scanner = WebsiteScanner() if scan_websites else None

            total_locations = len(all_cities)
            batch: list[dict] = []

            try:
                for loc_idx, city in enumerate(all_cities):
                    district = selected_district or city
                    on_progress(f"\n📍 **Location {loc_idx+1}/{total_locations}: {city}, {district}, {selected_state}**")

                    for school_data in client.search_schools(
                        city=city,
                        district=district,
                        state=selected_state,
                        max_results_per_query=max_results,
                        max_requests=max_requests,
                        fetch_details=fetch_details,
                        on_progress=on_progress,
                        stop_flag=stop_flag,
                    ):
                        req_count += 1

                        # Deduplication check
                        if is_duplicate_of_existing(school_data, existing_pids):
                            dup_count += 1
                            update_stats()
                            continue

                        # Scan website if requested
                        if scan_websites and scanner and school_data.get("website"):
                            on_progress(f"   🌐 Scanning: {school_data['website'][:50]}")
                            try:
                                scan_result = scanner.scan(
                                    school_data["website"],
                                    school_name=school_data.get("name", ""),
                                    city=city,
                                )
                                if scan_result.get("emails"):
                                    school_data["email"] = scan_result["emails"][0]
                                if scan_result.get("phones") and not school_data.get("phone"):
                                    school_data["phone"] = scan_result["phones"][0]
                                if scan_result.get("instagram"):
                                    school_data["instagram"] = scan_result["instagram"]
                                    school_data["instagram_status"] = scan_result.get("instagram_status")
                                if scan_result.get("facebook"):
                                    school_data["facebook"] = scan_result["facebook"]
                                if scan_result.get("linkedin"):
                                    school_data["linkedin"] = scan_result["linkedin"]
                                if scan_result.get("whatsapp"):
                                    school_data["whatsapp"] = scan_result["whatsapp"]
                                school_data["contact_source"] = CONTACT_SOURCE_WEBSITE
                            except Exception as exc:
                                fail_count += 1
                                on_progress(f"   ⚠️ Website scan failed: {exc}")

                        # Generate Instagram search URL if none found
                        if not school_data.get("instagram"):
                            q = f"{school_data.get('name','')} {city}".replace(" ", "+")
                            school_data["instagram"] = (
                                f"https://www.instagram.com/explore/search/keyword/?q={q}"
                            )
                            school_data["instagram_status"] = "Needs manual verification"

                        batch.append(school_data)
                        if school_data.get("place_id"):
                            existing_pids.add(school_data["place_id"])
                        new_count += 1
                        update_stats()

                    progress_bar.progress(min(1.0, (loc_idx + 1) / total_locations))

                    if stop_flag():
                        on_progress("🛑 Search stopped by user.")
                        break

                progress_bar.progress(1.0)

            except PlacesAPIError as exc:
                fail_count += 1
                update_stats()
                st.error(f"❌ **Google Places API error:** {exc}")

            finally:
                if scanner:
                    scanner.close()

            # Record API usage
            if req_count > 0:
                with get_session() as session:
                    RateLimiter(session).record_requests(req_count)

            # Save results
            if batch:
                # In-batch deduplication
                batch = deduplicate(batch)
                with get_session() as session:
                    for data in batch:
                        school = School(
                            place_id=data.get("place_id"),
                            name=data.get("name", "Unknown"),
                            phone=data.get("phone"),
                            website=data.get("website"),
                            email=data.get("email"),
                            instagram=data.get("instagram"),
                            instagram_status=data.get("instagram_status"),
                            facebook=data.get("facebook"),
                            linkedin=data.get("linkedin"),
                            whatsapp=data.get("whatsapp"),
                            address=data.get("address"),
                            city=data.get("city"),
                            district=data.get("district"),
                            state=data.get("state"),
                            postal_code=data.get("postal_code"),
                            latitude=data.get("latitude"),
                            longitude=data.get("longitude"),
                            maps_url=data.get("maps_url"),
                            rating=data.get("rating"),
                            review_count=data.get("review_count"),
                            business_status=data.get("business_status"),
                            contact_source=data.get("contact_source", CONTACT_SOURCE_GOOGLE),
                            verification_status=data.get("verification_status", VERIFICATION_GOOGLE),
                            outreach_status="New",
                            created_at=datetime.utcnow(),
                        )
                        session.add(school)

                st.success(
                    f"✅ **Done!** Saved **{len(batch)}** new schools | "
                    f"Skipped **{dup_count}** duplicates | "
                    f"API requests: **{req_count}**"
                )
            else:
                if dup_count > 0:
                    st.info(f"All {dup_count} results were already in the database.")
                else:
                    st.warning(
                        "No results returned. Try different search terms, "
                        "check your API key, or ensure billing is enabled in Google Cloud."
                    )

    # ── Cost warning ──────────────────────────────────────────────────────────
    with st.expander("💰 Google Cloud Billing Note", expanded=False):
        st.markdown(
            """
            > **⚠️ This tool uses the Google Places API (New) which incurs billing costs.**
            >
            > - Text Search requests are billed per request (Basic data tier).
            > - Place Details with phone/website fields are billed at a higher tier.
            > - This app tracks daily usage **locally** only.
            > - **You must configure billing alerts and hard quotas in your [Google Cloud Console](https://console.cloud.google.com/).**
            > - Refer to the [Places API pricing page](https://developers.google.com/maps/documentation/places/web-service/usage-and-billing) for current rates.
            """
        )
