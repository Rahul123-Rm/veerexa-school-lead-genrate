"""
services/website_scanner.py — Extract contact information from school websites.

Rules enforced:
  • Respects robots.txt
  • Maximum 5 pages per school
  • 15-second connect timeout, 30-second read timeout
  • Up to 2 retries with exponential back-off
  • Descriptive User-Agent
  • No CAPTCHA bypass or login attempts
  • Never scrape Instagram directly
"""

from __future__ import annotations

import re
import time
import urllib.robotparser
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

USER_AGENT = (
    "VeeRexaSchoolFinder/1.0 (educational-lead-research-tool; "
    "contact: info@veerexa.com)"
)

CONTACT_PAGES = ["/contact", "/contact-us", "/about", "/about-us"]
MAX_PAGES_PER_SCHOOL = 5
CONNECT_TIMEOUT = 10
READ_TIMEOUT = 20
MAX_RETRIES = 2

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(
    r"(?:(?:\+|00)?91[-.\s]?)?(?:\(0\d{2,4}\)|0\d{2,4})?[-.\s]?[6-9]\d{4}[-.\s]?\d{5}"
)
WHATSAPP_RE = re.compile(r"(?:wa\.me|api\.whatsapp\.com/send\?phone=)[^\s\"'>]+", re.I)
INSTAGRAM_RE = re.compile(r"(?:instagram\.com/)[a-zA-Z0-9._]+", re.I)
FACEBOOK_RE = re.compile(r"(?:facebook\.com/)[a-zA-Z0-9._\-/]+", re.I)
LINKEDIN_RE = re.compile(r"(?:linkedin\.com/(?:company|in)/)[a-zA-Z0-9._\-/]+", re.I)


class WebsiteScanner:
    def __init__(self):
        self._client = httpx.Client(
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
            timeout=httpx.Timeout(CONNECT_TIMEOUT, read=READ_TIMEOUT),
            verify=True,
        )

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    # ------------------------------------------------------------------
    # Robots.txt
    # ------------------------------------------------------------------

    def _is_allowed(self, base_url: str, path: str) -> bool:
        try:
            rp = urllib.robotparser.RobotFileParser()
            robots_url = urljoin(base_url, "/robots.txt")
            rp.set_url(robots_url)
            rp.read()
            return rp.can_fetch(USER_AGENT, urljoin(base_url, path))
        except Exception:
            return True  # If robots.txt cannot be read, proceed cautiously

    # ------------------------------------------------------------------
    # HTTP fetch with retry
    # ------------------------------------------------------------------

    def _fetch(self, url: str) -> str | None:
        for attempt in range(MAX_RETRIES + 1):
            try:
                resp = self._client.get(url)
                if resp.status_code == 200:
                    return resp.text
                return None
            except (httpx.TimeoutException, httpx.RequestError):
                if attempt < MAX_RETRIES:
                    time.sleep(2 ** attempt)
        return None

    # ------------------------------------------------------------------
    # Extraction helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_emails(soup: BeautifulSoup, raw_html: str) -> list[str]:
        found: set[str] = set()
        # From href="mailto:..."
        for tag in soup.find_all("a", href=True):
            href = tag["href"]
            if href.startswith("mailto:"):
                addr = href[7:].split("?")[0].strip().lower()
                if addr:
                    found.add(addr)
        # From raw text
        for m in EMAIL_RE.findall(raw_html):
            found.add(m.lower())
        # Filter out image/CSS/JS false positives
        return [
            e for e in found
            if not any(e.endswith(ext) for ext in [".png", ".jpg", ".gif", ".css", ".js"])
        ]

    @staticmethod
    def _extract_phones(raw_html: str) -> list[str]:
        from utils.phone_utils import extract_phones_from_text
        return extract_phones_from_text(raw_html)

    @staticmethod
    def _extract_social(soup: BeautifulSoup, raw_html: str) -> dict:
        links = {"instagram": None, "facebook": None, "linkedin": None, "whatsapp": None}

        for tag in soup.find_all("a", href=True):
            href = tag["href"].lower()
            if "instagram.com" in href and not links["instagram"]:
                # Extract handle cleanly
                m = re.search(r"instagram\.com/([a-zA-Z0-9._]+)", tag["href"], re.I)
                if m:
                    links["instagram"] = f"https://www.instagram.com/{m.group(1)}"
            elif "facebook.com" in href and not links["facebook"]:
                links["facebook"] = tag["href"]
            elif "linkedin.com" in href and not links["linkedin"]:
                links["linkedin"] = tag["href"]
            elif ("wa.me" in href or "api.whatsapp.com" in href) and not links["whatsapp"]:
                links["whatsapp"] = tag["href"]

        return links

    # ------------------------------------------------------------------
    # Main scanner
    # ------------------------------------------------------------------

    def scan(self, website_url: str, school_name: str = "", city: str = "") -> dict:
        """
        Scan a school website and return extracted contact details.

        Returns a dict with keys:
          emails, phones, instagram, instagram_status,
          facebook, linkedin, whatsapp
        """
        result: dict = {
            "emails": [],
            "phones": [],
            "instagram": None,
            "instagram_status": None,
            "facebook": None,
            "linkedin": None,
            "whatsapp": None,
            "scan_error": None,
        }

        # Normalise base URL
        if not website_url.startswith(("http://", "https://")):
            website_url = "https://" + website_url

        parsed = urlparse(website_url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"

        pages_visited = 0
        pages_to_visit = [website_url] + [
            urljoin(base_url, p) for p in CONTACT_PAGES
        ]

        all_emails: set[str] = set()
        all_phones: set[str] = set()

        for page_url in pages_to_visit:
            if pages_visited >= MAX_PAGES_PER_SCHOOL:
                break

            # Robots check
            path = urlparse(page_url).path or "/"
            if not self._is_allowed(base_url, path):
                continue

            html = self._fetch(page_url)
            if not html:
                continue

            pages_visited += 1
            soup = BeautifulSoup(html, "lxml")

            for email in self._extract_emails(soup, html):
                all_emails.add(email)

            for phone in self._extract_phones(html):
                all_phones.add(phone)

            socials = self._extract_social(soup, html)
            if socials["instagram"] and not result["instagram"]:
                result["instagram"] = socials["instagram"]
                result["instagram_status"] = "Verified from official website"
            if socials["facebook"] and not result["facebook"]:
                result["facebook"] = socials["facebook"]
            if socials["linkedin"] and not result["linkedin"]:
                result["linkedin"] = socials["linkedin"]
            if socials["whatsapp"] and not result["whatsapp"]:
                result["whatsapp"] = socials["whatsapp"]

        result["emails"] = sorted(all_emails)
        result["phones"] = sorted(all_phones)

        # If no Instagram found, generate a search URL
        if not result["instagram"] and school_name:
            search_query = f"{school_name} {city}".strip().replace(" ", "+")
            result["instagram"] = (
                f"https://www.instagram.com/explore/search/keyword/?q={search_query}"
            )
            result["instagram_status"] = "Needs manual verification"

        return result
