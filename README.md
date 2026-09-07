# 🏫 Veerexa School Lead Finder

A complete local lead-generation tool for **Veerexa Technologies** — discover schools area-wise using the **Google Places API (New)**, collect publicly available contact information, manage your outreach pipeline, and export leads to CSV, Excel, and PDF.

> **Runs entirely locally. No cloud server required. One command to start.**

---

## 📋 Table of Contents

1. [Features](#features)
2. [Project Structure](#project-structure)
3. [Prerequisites](#prerequisites)
4. [Google Cloud Setup](#google-cloud-setup)
5. [Installation](#installation)
6. [Configuration](#configuration)
7. [Running the Application](#running-the-application)
8. [Using the Application](#using-the-application)
9. [Exporting Leads](#exporting-leads)
10. [Google Places Data Attribution](#google-places-data-attribution)
11. [Cost Control & Security](#cost-control--security)
12. [Troubleshooting](#troubleshooting)

---

## ✨ Features

- 🔍 **School Discovery** — search by state, district, city, or custom localities
- 📞 **Contact Collection** — phone, email, website, Instagram, WhatsApp, Facebook, LinkedIn
- 🌐 **Website Scanner** — automatically extracts contact info from school official websites
- 📸 **Instagram Finder** — generates search URLs when direct links aren't found
- 💾 **Local SQLite Storage** — all data stored locally, no cloud required
- 📊 **Dashboard** — summary cards and district-wise analytics
- 📣 **Outreach Tracker** — log communications, schedule follow-ups, track status
- 📤 **Export** — CSV, Excel (single + district-wise), branded PDF reports
- 🛡️ **Cost Controls** — daily request limits, caching, field masks, billing warnings
- ✅ **Works without API key** — manual lead entry always available

---

## 🗂️ Project Structure

```
Marketing tool veerexa/
├── app.py                      ← Entry point (streamlit run app.py)
├── pages/
│   ├── 1_Dashboard.py          ← Summary stats & district analytics
│   ├── 2_Fetch_Schools.py      ← Google Places search + manual entry
│   ├── 3_Leads.py              ← Browse, filter, edit leads
│   ├── 4_Outreach_Tracker.py   ← Log outreach, schedule follow-ups
│   └── 5_Export.py             ← CSV / Excel / PDF export
├── database/
│   ├── connection.py           ← SQLAlchemy engine & session
│   └── migrations.py           ← Schema creation on startup
├── models/
│   └── school.py               ← ORM models (School, OutreachLog, etc.)
├── services/
│   ├── google_places.py        ← Places API (New) client
│   ├── website_scanner.py      ← Website contact extractor
│   └── export_service.py       ← CSV / Excel / PDF generators
├── utils/
│   ├── india_geo.py            ← Static state/district/city data
│   ├── phone_utils.py          ← Indian phone normalisation
│   ├── dedup_utils.py          ← Record deduplication
│   └── rate_limiter.py         ← Daily API request counter
├── tests/
│   ├── test_phone_utils.py
│   ├── test_dedup.py
│   └── test_export.py
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

## ⚙️ Prerequisites

- **Python 3.12** (or 3.10+)
- **pip**
- A modern web browser
- *(Optional)* A Google Cloud account with billing enabled

---

## ☁️ Google Cloud Setup

> Skip this section if you only want to use manual lead entry.

### Step 1 — Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/).
2. Click **Select a project → New Project**.
3. Name it (e.g. `veerexa-school-finder`) and click **Create**.

### Step 2 — Enable Places API (New)

> ⚠️ Make sure you enable **"Places API (New)"** — NOT the legacy "Places API".

1. In your project, go to **APIs & Services → Library**.
2. Search for **Places API (New)**.
3. Click **Enable**.

### Step 3 — Create an API Key

1. Go to **APIs & Services → Credentials**.
2. Click **Create Credentials → API key**.
3. Copy the generated key.

### Step 4 — Restrict the API Key (Recommended)

1. Click the pencil icon next to your new key.
2. Under **API restrictions**, choose **Restrict key**.
3. Select **Places API (New)** from the dropdown.
4. Click **Save**.

### Step 5 — Set Up Billing Alerts & Quotas (Critical!)

> ⚠️ **This app tracks usage locally only. You MUST configure cloud-side protection.**

1. Go to **Billing → Budgets & alerts** and create a budget alert.
2. Go to **APIs & Services → Places API (New) → Quotas**.
3. Set a hard daily quota limit appropriate for your usage.

See [Google's pricing page](https://developers.google.com/maps/documentation/places/web-service/usage-and-billing) for current rates.

---

## 📦 Installation

```bash
# Clone or navigate to the project directory
cd "Marketing tool veerexa"

# Create a virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate       # macOS / Linux
# venv\Scripts\activate        # Windows

# Install dependencies
pip install -r requirements.txt
```

---

## 🔧 Configuration

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env and add your API key
nano .env   # or open in any text editor
```

Your `.env` file:
```env
GOOGLE_MAPS_API_KEY=AIzaSy...your_actual_key_here...

# Optional: adjust limits
MAX_REQUESTS_PER_RUN=100
DAILY_REQUEST_LIMIT=500
```

> 🔒 **The `.env` file is listed in `.gitignore` and is never exported or logged.**

---

## 🚀 Running the Application

```bash
streamlit run app.py
```

The app will open automatically in your browser at `http://localhost:8501`.

---

## 📖 Using the Application

### Dashboard
- See total schools, phones, websites, Instagram accounts, emails.
- View daily API usage and the last 7-day history.
- District-wise breakdown table.

### Fetch Schools
1. Select **State → District → City** from the dropdowns (or type custom localities).
2. Click **Preview Search** to see exactly how many API requests will be made.
3. *(Optional)* Enable **"Scan school websites"** to extract emails and social links.
4. Click **Fetch Schools** to start. Use **Stop Search** to interrupt at any time.
5. Results are saved automatically. Duplicates are skipped.

### Leads
- Search, filter, and sort all schools.
- Click table rows to select them for bulk actions.
- Open websites, Maps, Instagram links directly.
- Edit individual records inline.
- Delete unwanted records.

### Outreach Tracker
- Search for a school and log each communication.
- Select status (WhatsApp sent, Called, Interested, etc.).
- Set a follow-up date — upcoming follow-ups appear in a dedicated table.
- View the full outreach history per school.

### Export
- Apply filters, then download:
  - **CSV** — for CRMs, Google Sheets
  - **Excel (single sheet)** — formatted with frozen headers and hyperlinks
  - **District-wise Excel** — one worksheet per district
  - **District-wise PDF** — branded Veerexa Technologies report

---

## 📤 Exporting Leads

The Export page respects all active filters. You can export:

| Format | Description |
|--------|-------------|
| CSV | UTF-8 with BOM, compatible with Excel & Google Sheets |
| Excel (single) | Frozen header, auto-widths, hyperlinks, alternate row shading |
| Excel (district-wise) | Separate worksheets per district |
| PDF (district-wise) | Branded A4 landscape, Veerexa logo, one section per district |

---

## 📌 Google Places Data Attribution

School data in this application is sourced from the **Google Places API (New)**.

- You must comply with [Google Maps Platform Terms of Service](https://cloud.google.com/maps-platform/terms).
- Data must not be used in violation of Google's usage policies.
- Google attribution must be maintained when displaying or sharing data.
- This tool does not modify, resell, or redistribute Google Places data.

---

## 🔐 Cost Control & Security

| Feature | Detail |
|---------|--------|
| API key storage | `.env` file only — never in code, logs, or exports |
| Field masks | Only billable fields actually needed are requested |
| Local caching | Completed searches are cached in SQLite |
| Per-run limit | Configurable `MAX_REQUESTS_PER_RUN` (default: 100) |
| Daily limit | Configurable `DAILY_REQUEST_LIMIT` (default: 500) |
| Cloud protection | Must be configured separately in Google Cloud Console |

---

## 🛠️ Troubleshooting

| Problem | Solution |
|---------|----------|
| `API key not configured` | Add `GOOGLE_MAPS_API_KEY` to `.env` and restart |
| `403 Access denied` | Enable Places API (New) and ensure billing is active |
| `401 Invalid API key` | Check the key in `.env` — no extra spaces |
| `429 Quota exceeded` | Reduce `MAX_REQUESTS_PER_RUN` or wait until tomorrow |
| Website scan timeout | Normal for unreachable school sites — data is skipped |
| No results returned | Try different search terms; some areas have limited coverage |
| Database locked | Ensure only one Streamlit instance is running |
| Export fails | Ensure `openpyxl` and `reportlab` are installed |

---

## 🧪 Running Tests

```bash
python -m pytest tests/ -v
```

Tests cover:
- Indian phone number normalisation (12 scenarios)
- Record deduplication (8 scenarios)
- CSV, Excel, and PDF export validation (15 scenarios)

---

## 📜 License

Internal tool for Veerexa Technologies. Not for redistribution.

---

*Built with ❤️ for Veerexa Technologies | Streamlit + SQLite + Google Places API (New)*
# veerexa-school-lead-genrate
