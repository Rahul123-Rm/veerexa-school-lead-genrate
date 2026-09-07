"""
dedup_utils.py — Deduplication helpers for school records.

Priority:
  1. Google Place ID (exact match) — definitive
  2. Normalised (name + phone + city) — fuzzy fallback
  3. Normalised (name + address) — last resort
"""

from __future__ import annotations

import re
import unicodedata


def _normalise_str(value: str) -> str:
    """Lowercase, strip accents, collapse whitespace, remove punctuation."""
    if not value:
        return ""
    value = unicodedata.normalize("NFKD", value)
    value = value.encode("ascii", "ignore").decode("ascii")
    value = value.lower()
    value = re.sub(r"[^\w\s]", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _fingerprint_by_place_id(record: dict) -> str | None:
    pid = (record.get("place_id") or "").strip()
    return pid if pid else None


def _fingerprint_by_name_phone_city(record: dict) -> str:
    name = _normalise_str(record.get("name", ""))
    phone = re.sub(r"\D", "", record.get("phone", "") or "")
    city = _normalise_str(record.get("city", ""))
    return f"{name}||{phone}||{city}"


def _fingerprint_by_name_address(record: dict) -> str:
    name = _normalise_str(record.get("name", ""))
    address = _normalise_str(record.get("address", ""))
    city = _normalise_str(record.get("city", ""))
    return f"{name}||{address}||{city}"


def deduplicate(records: list[dict]) -> list[dict]:
    """
    Return a deduplicated list of school record dicts.

    Each record dict is expected to have at minimum:
      - place_id (str | None)
      - name (str)
      - phone (str | None)
      - city (str | None)
      - address (str | None)
    """
    seen_place_ids: set[str] = set()
    seen_name_phone_city: set[str] = set()
    seen_name_address: set[str] = set()
    unique: list[dict] = []

    for record in records:
        pid = _fingerprint_by_place_id(record)
        if pid:
            if pid in seen_place_ids:
                continue
            seen_place_ids.add(pid)
        else:
            npc = _fingerprint_by_name_phone_city(record)
            na = _fingerprint_by_name_address(record)
            if npc in seen_name_phone_city or na in seen_name_address:
                continue
            seen_name_phone_city.add(npc)
            seen_name_address.add(na)

        unique.append(record)

    return unique


def is_duplicate_of_existing(new_record: dict, existing_place_ids: set[str]) -> bool:
    """
    Check whether a single new_record is a duplicate of already-stored records.
    existing_place_ids is a set of place_ids already in the database.
    """
    pid = _fingerprint_by_place_id(new_record)
    if pid and pid in existing_place_ids:
        return True
    return False
