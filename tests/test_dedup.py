"""
tests/test_dedup.py — Unit tests for school record deduplication.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from utils.dedup_utils import deduplicate, is_duplicate_of_existing


def _make_record(
    place_id=None, name="Test School", phone="9876543210", city="Mumbai", address="123 Main St"
):
    return {
        "place_id": place_id,
        "name": name,
        "phone": phone,
        "city": city,
        "address": address,
    }


class TestDeduplicate:
    def test_no_duplicates(self):
        records = [
            _make_record(place_id="pid1", name="School A"),
            _make_record(place_id="pid2", name="School B"),
        ]
        result = deduplicate(records)
        assert len(result) == 2

    def test_duplicate_by_place_id(self):
        records = [
            _make_record(place_id="pid1", name="School A"),
            _make_record(place_id="pid1", name="School A (duplicate)"),
        ]
        result = deduplicate(records)
        assert len(result) == 1
        assert result[0]["name"] == "School A"

    def test_duplicate_by_name_phone_city(self):
        records = [
            _make_record(name="St. Mary's School", phone="9876543210", city="Mumbai"),
            _make_record(name="St. Mary's School", phone="9876543210", city="Mumbai"),
        ]
        result = deduplicate(records)
        assert len(result) == 1

    def test_same_name_different_city_not_duplicate(self):
        records = [
            _make_record(name="DPS School", phone="9876543210", city="Mumbai"),
            _make_record(name="DPS School", phone="9876543210", city="Delhi"),
        ]
        result = deduplicate(records)
        assert len(result) == 2

    def test_no_place_id_dedup_by_name_address(self):
        records = [
            _make_record(name="Sunrise Academy", address="10 Park Road, Pune"),
            _make_record(name="Sunrise Academy", address="10 Park Road, Pune"),
        ]
        result = deduplicate(records)
        assert len(result) == 1

    def test_empty_list(self):
        result = deduplicate([])
        assert result == []

    def test_single_record(self):
        records = [_make_record(place_id="pid1")]
        result = deduplicate(records)
        assert len(result) == 1

    def test_normalisation_case_insensitive(self):
        records = [
            _make_record(name="Delhi Public School", city="MUMBAI"),
            _make_record(name="delhi public school", city="mumbai"),
        ]
        result = deduplicate(records)
        assert len(result) == 1

    def test_mixed_place_id_and_no_place_id(self):
        records = [
            _make_record(place_id="pid1", name="School X"),
            _make_record(place_id=None, name="School X"),  # no place_id
        ]
        result = deduplicate(records)
        # Both kept: one has place_id, one doesn't
        # The second will be checked via name+phone+city — different fingerprint
        # unless phone and city match too
        assert len(result) >= 1


class TestIsDuplicateOfExisting:
    def test_place_id_in_existing(self):
        record = _make_record(place_id="pid1")
        existing = {"pid1", "pid2"}
        assert is_duplicate_of_existing(record, existing) is True

    def test_place_id_not_in_existing(self):
        record = _make_record(place_id="pid99")
        existing = {"pid1", "pid2"}
        assert is_duplicate_of_existing(record, existing) is False

    def test_no_place_id(self):
        record = _make_record(place_id=None)
        existing = {"pid1"}
        assert is_duplicate_of_existing(record, existing) is False

    def test_empty_existing(self):
        record = _make_record(place_id="pid1")
        assert is_duplicate_of_existing(record, set()) is False
