"""
tests/test_phone_utils.py — Unit tests for Indian phone normalisation.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.phone_utils import (
    normalize_phone,
    is_valid_phone,
    extract_phones_from_text,
    format_phone_display,
    VERIFICATION_INVALID,
    VERIFICATION_GOOGLE,
)


class TestNormalizePhone:
    def test_plain_10_digit(self):
        phone, status = normalize_phone("9876543210")
        assert phone == "+91-9876543210"
        assert status == VERIFICATION_GOOGLE

    def test_with_country_code_91(self):
        phone, status = normalize_phone("919876543210")
        assert phone == "+91-9876543210"

    def test_with_plus_91(self):
        phone, status = normalize_phone("+919876543210")
        assert phone == "+91-9876543210"

    def test_with_spaces(self):
        phone, status = normalize_phone("98765 43210")
        assert phone == "+91-9876543210"

    def test_with_dashes(self):
        phone, status = normalize_phone("98765-43210")
        assert phone == "+91-9876543210"

    def test_with_trunk_prefix_0(self):
        phone, status = normalize_phone("09876543210")
        assert phone == "+91-9876543210"

    def test_with_plus_91_and_space(self):
        phone, status = normalize_phone("+91 98765 43210")
        assert phone == "+91-9876543210"

    def test_invalid_too_short(self):
        phone, status = normalize_phone("12345")
        assert status == VERIFICATION_INVALID

    def test_invalid_starts_with_1(self):
        # In India, mobile numbers start with 6-9
        phone, status = normalize_phone("1234567890")
        assert status == VERIFICATION_INVALID

    def test_empty_string(self):
        phone, status = normalize_phone("")
        assert status == VERIFICATION_INVALID

    def test_landline_starts_with_0(self):
        # 044 landline — 11 digits with STD. After stripping trunk, 10 digits.
        # 044 + 8-digit = 10 digits starting with 0 → strip → 9 digits
        # This is a landline, may not match mobile rule
        phone, status = normalize_phone("044-12345678")
        # 04412345678 → strip trunk 0 → 4412345678 (10 digits, starts with 4)
        assert status == VERIFICATION_INVALID  # starts with 4, not 6-9

    def test_valid_mobile_starting_6(self):
        phone, status = normalize_phone("6123456789")
        assert phone == "+91-6123456789"
        assert status == VERIFICATION_GOOGLE

    def test_valid_mobile_starting_7(self):
        phone, status = normalize_phone("7012345678")
        assert phone == "+91-7012345678"

    def test_valid_mobile_starting_8(self):
        phone, status = normalize_phone("8765432109")
        assert phone == "+91-8765432109"


class TestIsValidPhone:
    def test_valid(self):
        assert is_valid_phone("9876543210") is True

    def test_invalid(self):
        assert is_valid_phone("12345") is False

    def test_empty(self):
        assert is_valid_phone("") is False


class TestExtractPhonesFromText:
    def test_extract_from_text(self):
        text = "Call us at 9876543210 or 8765432109 for admission."
        phones = extract_phones_from_text(text)
        assert len(phones) >= 1
        assert "+91-9876543210" in phones or "+91-8765432109" in phones

    def test_no_phone_in_text(self):
        text = "Welcome to our school website."
        phones = extract_phones_from_text(text)
        assert phones == []

    def test_deduplication(self):
        text = "9876543210 and 9876543210"
        phones = extract_phones_from_text(text)
        assert len(phones) == 1


class TestFormatPhoneDisplay:
    def test_e164_format(self):
        display = format_phone_display("+91-9876543210")
        assert "98765" in display
        assert "43210" in display

    def test_raw_10_digits(self):
        display = format_phone_display("9876543210")
        assert display  # Just ensure it returns something
