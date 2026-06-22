"""
Tests for the live client duplicate-detection service.

Pure-function tests — no app factory, no DB. Mirror the dedup strategies from
the 2026-06 cleanup so the create/edit form hints stay accurate.
"""
from services.client_duplicate_service import (
    normalize_phone,
    levenshtein,
    find_duplicate_warnings,
)

EXISTING = [
    {"id": 1, "first_name": "Anna", "last_name": "Turowska", "phone": "48537126534"},
    {"id": 2, "first_name": "Iwona", "last_name": "Pachnik", "phone": "48503011481"},
    {"id": 3, "first_name": "Irmina", "last_name": "", "phone": "48512078708"},
    {"id": 4, "first_name": "Aleksandra", "last_name": "Piątek", "phone": "48885909885"},
    {"id": 5, "first_name": "p. Anna", "last_name": "Kowalska", "phone": "48111222333"},
    {"id": 6, "first_name": "A", "last_name": "Nowak", "phone": "48999888777"},
]


def _cats(matches):
    return {(m["id"], m["category"]) for m in matches}


# ── normalisation helpers ─────────────────────────────────────────────────────

def test_normalize_phone_collapses_formats():
    assert normalize_phone("48537126534") == "537126534"
    assert normalize_phone("+48 537-126-534") == "537126534"
    assert normalize_phone("0537126534") == "537126534"
    assert normalize_phone("") == ""
    assert normalize_phone(None) == ""


def test_levenshtein_basic():
    assert levenshtein("balmas", "belmas") == 1
    assert levenshtein("brzeska", "brzezna") == 2
    assert levenshtein("anna", "anna") == 0


# ── detection strategies ──────────────────────────────────────────────────────

def test_phone_exact_match_is_high():
    m = find_duplicate_warnings("Anna", "Purowska", "537126534", EXISTING)
    assert (1, "PHONE") in _cats(m)
    assert m[0]["severity"] == "high"
    assert m[0]["field"] == "phone"


def test_single_char_typo_in_surname():
    m = find_duplicate_warnings("Anna", "Turowsk", "", EXISTING)
    assert (1, "TYPO") in _cats(m)


def test_swapped_first_last():
    m = find_duplicate_warnings("Piątek", "Aleksandra", "", EXISTING)
    assert (4, "SWAPPED") in _cats(m)


def test_identical_name_without_phone_is_same():
    m = find_duplicate_warnings("Iwona", "Pachnik", "", EXISTING)
    assert (2, "SAME") in _cats(m)


def test_blank_field_twin():
    m = find_duplicate_warnings("Irmina", "Średnicka", "", EXISTING)
    assert (3, "EMPTY") in _cats(m)


def test_courtesy_prefix():
    m = find_duplicate_warnings("Anna", "Kowalska", "", EXISTING)
    assert (5, "PREFIX") in _cats(m)


def test_initial_only():
    m = find_duplicate_warnings("Anna", "Nowak", "", EXISTING)
    assert (6, "INITIAL") in _cats(m)


# ── quiet cases (no false positives / not enough input) ───────────────────────

def test_clean_new_client_no_matches():
    assert find_duplicate_warnings("Zofia", "Lewandowska", "48000111222", EXISTING) == []


def test_partial_input_skips_scan():
    assert find_duplicate_warnings("Ann", "", "", EXISTING) == []
    assert find_duplicate_warnings("", "", "12", EXISTING) == []


def test_exclude_id_skips_self():
    # Editing client #2 with its own data must not flag itself.
    m = find_duplicate_warnings("Iwona", "Pachnik", "48503011481", EXISTING, exclude_id=2)
    assert all(x["id"] != 2 for x in m)
