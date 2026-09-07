"""
phone_utils.py — Indian phone number normalisation and validation.

Rules applied:
  • Strip all non-digit characters.
  • Handle leading 0 (STD trunk prefix).
  • Handle leading 91 or +91 (country code).
  • Validate that the resulting number is 10 digits.
  • Validate the first digit is 6–9 (valid Indian mobile range).
  • Format output as +91-XXXXXXXXXX.
"""

from __future__ import annotations

import re

# Regex that captures anything that looks like a phone number in free text
_PHONE_RAW_RE = re.compile(
    r"""
    (?:(?:\+|00)?91[-.\s]?)?        # optional country code
    (?:\(0\d{2,4}\)|0\d{2,4})?      # optional STD code with or without parens
    [-.\s]?
    [6-9]\d{4}                       # first 5 digits of mobile
    [-.\s]?
    \d{5}                            # last 5 digits
    """,
    re.VERBOSE,
)

CONTACT_SOURCE_GOOGLE = "Google Places"
CONTACT_SOURCE_WEBSITE = "Official website"
CONTACT_SOURCE_MANUAL = "Manual entry"

VERIFICATION_OFFICIAL = "Verified from official website"
VERIFICATION_GOOGLE = "Found on Google Places"
VERIFICATION_MANUAL = "Needs manual verification"
VERIFICATION_INVALID = "Invalid/unavailable"


def _strip_non_digits(value: str) -> str:
    return re.sub(r"\D", "", value)


def normalize_phone(raw: str) -> tuple[str, str]:
    """
    Normalise a raw phone string to E.164 format (+91XXXXXXXXXX).

    Returns
    -------
    (formatted, verification_status)
    """
    if not raw:
        return "", VERIFICATION_INVALID

    digits = _strip_non_digits(raw)

    # Remove leading 91 country code
    if digits.startswith("91") and len(digits) > 10:
        digits = digits[2:]

    # Remove leading trunk prefix 0
    if digits.startswith("0") and len(digits) > 10:
        digits = digits[1:]

    if len(digits) != 10:
        return raw, VERIFICATION_INVALID

    if digits[0] not in "6789":
        return raw, VERIFICATION_INVALID

    formatted = f"+91-{digits}"
    return formatted, VERIFICATION_GOOGLE


def is_valid_phone(raw: str) -> bool:
    _, status = normalize_phone(raw)
    return status != VERIFICATION_INVALID


def extract_phones_from_text(text: str) -> list[str]:
    """
    Extract and normalise all phone-like strings from a block of text.
    Returns a deduplicated list of normalised phone numbers.
    """
    raw_matches = _PHONE_RAW_RE.findall(text)
    result: list[str] = []
    seen: set[str] = set()
    for raw in raw_matches:
        normalized, status = normalize_phone(raw.strip())
        if status != VERIFICATION_INVALID and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result


def format_phone_display(phone: str) -> str:
    """Return a human-friendly display string (e.g. +91-98765 43210)."""
    digits = _strip_non_digits(phone)
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    if len(digits) == 10:
        return f"+91-{digits[:5]} {digits[5:]}"
    return phone
