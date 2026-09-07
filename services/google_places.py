"""
services/google_places.py — Google Places API (New) client.

Uses:
  • Text Search (POST /v1/places:searchText)
  • Place Details  (GET  /v1/places/{place_id})

Field masks are kept minimal to avoid unnecessary billable fields.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from typing import Callable, Generator

import httpx

from database.connection import get_session
from models.school import SearchCache
from utils.phone_utils import normalize_phone, VERIFICATION_GOOGLE, CONTACT_SOURCE_GOOGLE

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PLACES_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
PLACES_DETAIL_URL = "https://places.googleapis.com/v1/places/{place_id}"

# Fields fetched in Text Search — minimal set (Basic tier only)
SEARCH_FIELD_MASK = (
    "places.id,"
    "places.displayName,"
    "places.formattedAddress,"
    "places.location,"
    "places.businessStatus,"
    "places.rating,"
    "places.userRatingCount,"
    "places.googleMapsUri,"
    "places.types,"
    "nextPageToken"
)

# Fields fetched in Place Details — adds phone + website (Contact tier)
DETAIL_FIELD_MASK = (
    "id,"
    "displayName,"
    "formattedAddress,"
    "location,"
    "businessStatus,"
    "rating,"
    "userRatingCount,"
    "googleMapsUri,"
    "nationalPhoneNumber,"
    "internationalPhoneNumber,"
    "websiteUri,"
    "addressComponents,"
    "types"
)

# Query templates — each gets formatted with city, district, state
QUERY_TEMPLATES = [
    "schools in {city}, {district}, {state}",
    "private schools in {city}, {state}",
    "CBSE schools in {city}, {state}",
    "English medium schools in {city}, {state}",
    "public schools in {city}, {state}",
    "higher secondary schools in {city}, {state}",
]

REQUEST_TIMEOUT = 20  # seconds


class PlacesAPIError(Exception):
    """Raised when the Google Places API returns an error."""

    def __init__(self, message: str, status_code: int = 0):
        super().__init__(message)
        self.status_code = status_code


class GooglePlacesClient:
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("GOOGLE_MAPS_API_KEY is not set.")
        self.api_key = api_key
        self._headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
        }

    # ------------------------------------------------------------------
    # Cache helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _cache_key(query: str, page_token: str = "") -> str:
        raw = f"{query}||{page_token}"
        return hashlib.sha256(raw.encode()).hexdigest()

    @staticmethod
    def _get_cached(cache_key: str) -> dict | None:
        with get_session() as session:
            row = session.query(SearchCache).filter_by(cache_key=cache_key).first()
            if row:
                return json.loads(row.response_json)
        return None

    @staticmethod
    def _store_cache(cache_key: str, data: dict) -> None:
        with get_session() as session:
            existing = session.query(SearchCache).filter_by(cache_key=cache_key).first()
            if not existing:
                session.add(SearchCache(cache_key=cache_key, response_json=json.dumps(data)))

    # ------------------------------------------------------------------
    # Text Search
    # ------------------------------------------------------------------

    def text_search(
        self,
        query: str,
        max_results: int = 20,
        page_token: str = "",
        use_cache: bool = True,
    ) -> dict:
        """
        Perform a single Text Search request.
        Returns the raw API response dict.
        Raises PlacesAPIError on failure.
        """
        ck = self._cache_key(query, page_token)
        if use_cache:
            cached = self._get_cached(ck)
            if cached is not None:
                return cached

        body: dict = {
            "textQuery": query,
            "maxResultCount": min(max_results, 20),
            "languageCode": "en",
        }
        if page_token:
            body["pageToken"] = page_token

        headers = {**self._headers, "X-Goog-FieldMask": SEARCH_FIELD_MASK}

        try:
            resp = httpx.post(
                PLACES_SEARCH_URL,
                headers=headers,
                json=body,
                timeout=REQUEST_TIMEOUT,
            )
        except httpx.TimeoutException:
            raise PlacesAPIError("Request timed out while calling Places API.")
        except httpx.RequestError as exc:
            raise PlacesAPIError(f"Network error: {exc}")

        if resp.status_code == 200:
            data = resp.json()
            self._store_cache(ck, data)
            return data

        self._handle_error(resp)

    def place_details(self, place_id: str, use_cache: bool = True) -> dict:
        """
        Fetch full Place Details for a given place_id.
        """
        ck = self._cache_key(f"detail:{place_id}")
        if use_cache:
            cached = self._get_cached(ck)
            if cached is not None:
                return cached

        url = PLACES_DETAIL_URL.format(place_id=place_id)
        headers = {**self._headers, "X-Goog-FieldMask": DETAIL_FIELD_MASK}

        try:
            resp = httpx.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        except httpx.TimeoutException:
            raise PlacesAPIError(f"Timeout fetching details for {place_id}")
        except httpx.RequestError as exc:
            raise PlacesAPIError(f"Network error: {exc}")

        if resp.status_code == 200:
            data = resp.json()
            self._store_cache(ck, data)
            return data

        self._handle_error(resp)

    @staticmethod
    def _handle_error(resp: httpx.Response) -> None:
        try:
            err_data = resp.json()
            msg = err_data.get("error", {}).get("message", resp.text)
            status_code = resp.status_code
        except Exception:
            msg = resp.text
            status_code = resp.status_code

        if status_code == 400:
            raise PlacesAPIError(f"Bad request: {msg}", status_code)
        elif status_code == 401:
            raise PlacesAPIError(
                "API key is invalid or missing. Please check your .env file.", status_code
            )
        elif status_code == 403:
            raise PlacesAPIError(
                "Access denied. Ensure Places API (New) is enabled in Google Cloud Console "
                f"and billing is active. Detail: {msg}",
                status_code,
            )
        elif status_code == 429:
            raise PlacesAPIError(
                "Quota exceeded. You have hit the Google Places API rate limit.", status_code
            )
        else:
            raise PlacesAPIError(f"API error {status_code}: {msg}", status_code)

    # ------------------------------------------------------------------
    # High-level: search across multiple query templates + pagination
    # ------------------------------------------------------------------

    def search_schools(
        self,
        city: str,
        district: str,
        state: str,
        max_results_per_query: int = 20,
        max_requests: int = 100,
        fetch_details: bool = True,
        on_progress: Callable[[str], None] | None = None,
        stop_flag: Callable[[], bool] | None = None,
    ) -> Generator[dict, None, None]:
        """
        Generator that yields normalised school dicts.

        For each query template:
          1. Run Text Search (paginated)
          2. Optionally fetch Place Details per result

        Each yielded dict has keys matching the School model fields.
        """
        request_count = 0

        def _emit(msg: str):
            if on_progress:
                on_progress(msg)

        def _should_stop() -> bool:
            if stop_flag and stop_flag():
                return True
            if request_count >= max_requests:
                return True
            return False

        for template in QUERY_TEMPLATES:
            if _should_stop():
                break

            query = template.format(city=city, district=district, state=state)
            _emit(f"🔍 Searching: **{query}**")
            page_token = ""

            while True:
                if _should_stop():
                    break

                try:
                    result = self.text_search(
                        query,
                        max_results=max_results_per_query,
                        page_token=page_token,
                    )
                    request_count += 1
                    _emit(f"   ✓ Request {request_count}/{max_requests}")
                except PlacesAPIError as exc:
                    _emit(f"   ⚠️ Error: {exc}")
                    break

                places = result.get("places", [])
                if not places:
                    break

                for place in places:
                    if _should_stop():
                        break

                    place_id = place.get("id", "")
                    basic = self._parse_search_result(place, city, district, state)

                    if fetch_details and place_id and not _should_stop():
                        try:
                            detail = self.place_details(place_id)
                            request_count += 1
                            basic = self._merge_details(basic, detail)
                        except PlacesAPIError as exc:
                            _emit(f"   ⚠️ Details failed for {basic['name']}: {exc}")

                    yield basic

                page_token = result.get("nextPageToken", "")
                if not page_token:
                    break

                # Small pause before paginated request
                time.sleep(0.5)

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_search_result(place: dict, city: str, district: str, state: str) -> dict:
        loc = place.get("location", {})
        lat = loc.get("latitude")
        lng = loc.get("longitude")
        maps_uri = place.get("googleMapsUri", "")
        if not maps_uri and place.get("id"):
            maps_uri = f"https://maps.google.com/?cid={place['id']}"

        phone_raw = place.get("nationalPhoneNumber") or place.get("internationalPhoneNumber") or ""
        phone_norm, _ = normalize_phone(phone_raw)

        return {
            "place_id": place.get("id"),
            "name": place.get("displayName", {}).get("text", "Unknown"),
            "address": place.get("formattedAddress", ""),
            "city": city,
            "district": district,
            "state": state,
            "postal_code": None,
            "latitude": lat,
            "longitude": lng,
            "maps_url": maps_uri,
            "rating": place.get("rating"),
            "review_count": place.get("userRatingCount"),
            "business_status": place.get("businessStatus"),
            "phone": phone_norm or None,
            "website": None,
            "email": None,
            "instagram": None,
            "instagram_status": None,
            "facebook": None,
            "linkedin": None,
            "whatsapp": None,
            "contact_source": CONTACT_SOURCE_GOOGLE,
            "verification_status": VERIFICATION_GOOGLE,
        }

    @staticmethod
    def _merge_details(basic: dict, detail: dict) -> dict:
        """Merge Place Details response into the basic search result dict."""
        phone_raw = (
            detail.get("internationalPhoneNumber")
            or detail.get("nationalPhoneNumber")
            or ""
        )
        if phone_raw:
            phone_norm, _ = normalize_phone(phone_raw)
            basic["phone"] = phone_norm or basic.get("phone")

        basic["website"] = detail.get("websiteUri") or basic.get("website")
        basic["maps_url"] = detail.get("googleMapsUri") or basic.get("maps_url")
        basic["rating"] = detail.get("rating") or basic.get("rating")
        basic["review_count"] = detail.get("userRatingCount") or basic.get("review_count")
        basic["business_status"] = detail.get("businessStatus") or basic.get("business_status")

        # Extract postal code from addressComponents
        for component in detail.get("addressComponents", []):
            types = component.get("types", [])
            if "postal_code" in types:
                basic["postal_code"] = component.get("longText") or component.get("shortText")
                break

        return basic


def build_query_preview(
    locations: list[tuple[str, str, str]],
) -> dict:
    """
    Return a preview dict describing the planned API requests
    before the user triggers a real search.

    locations: list of (city, district, state) tuples
    """
    num_locations = len(locations)
    num_templates = len(QUERY_TEMPLATES)
    # Minimum requests = num_locations * num_templates (text search only)
    # Max if paginating 3 pages + details per result = rough estimate
    min_requests = num_locations * num_templates
    max_requests_estimate = min_requests * 3  # assume up to 3 pages of results

    return {
        "locations": num_locations,
        "query_templates": num_templates,
        "queries": [
            t.format(city=city, district=district, state=state)
            for (city, district, state) in locations
            for t in QUERY_TEMPLATES
        ],
        "min_requests": min_requests,
        "max_requests_estimate": max_requests_estimate,
        "fields_requested": SEARCH_FIELD_MASK.split(","),
        "detail_fields_requested": DETAIL_FIELD_MASK.split(","),
    }
