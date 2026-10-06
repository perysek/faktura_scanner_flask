"""Tests for utils.phone — the single definition of "a valid phone number"
shared by the booking page, the staff client form and the SMS service."""
import pytest

from utils.phone import normalize_phone, phone_match_keys, fold_name


@pytest.mark.parametrize('raw, expected', [
    # Polish, every spelling staff/clients actually type
    ('600123456', '+48600123456'),
    ('600 123 456', '+48600123456'),
    ('600-123-456', '+48600123456'),
    ('(600) 123.456', '+48600123456'),
    ('  600 123 456  ', '+48600123456'),
    ('600 123 456', '+48600123456'),          # non-breaking spaces (copy/paste from web)
    ('0600123456', '+48600123456'),                      # legacy trunk prefix
    ('48600123456', '+48600123456'),
    ('+48600123456', '+48600123456'),
    ('+48 600 123 456', '+48600123456'),
    ('0048600123456', '+48600123456'),
    ('00 48 600 123 456', '+48600123456'),
    # Polish landline (SMS can't reach it, but it is a *valid* number)
    ('22 123 45 67', '+48221234567'),
    ('221234567', '+48221234567'),
    # Foreign numbers need an explicit international prefix
    ('+49 151 1234567', '+491511234567'),
    ('0049 151 1234567', '+491511234567'),
    ('+380 50 123 4567', '+380501234567'),
    ('+1 202 555 0143', '+12025550143'),
])
def test_valid_numbers_are_normalised_to_e164(raw, expected):
    assert normalize_phone(raw) == expected


@pytest.mark.parametrize('raw', [
    None, '', '   ', '---',
    '600',                       # the old ILIKE '%600%' would have matched this to a random client
    '12',
    '60012345',                  # 8 digits, no country code
    '6001234567',                # 10 digits, doesn't start with 0
    '012345678',                 # 9 digits starting with 0
    '+48012345678',              # +48 then national number starting with 0
    '+4860012345',               # +48 but only 8 national digits
    '+486001234567',             # +48 but 10 national digits
    '4915112345678',             # foreign number without '+'/00 — ambiguous, refuse to guess
    '+0123456789',               # country code can't start with 0
    '+1234567',                  # 7 digits < E.164 minimum we accept
    '+1234567890123456',         # 16 digits > E.164 maximum
    'abc',
    '600 123 45a',
    '600+123+456',
    '+48 600 123 456 w.12',      # extension / free text
    '<script>alert(1)</script>',
    "600123456'; DROP TABLE clients;--",
])
def test_invalid_numbers_are_rejected(raw):
    assert normalize_phone(raw) is None


def test_non_ascii_digits_are_not_accepted():
    # str.isdigit() accepts these; our ASCII-only check must not.
    assert normalize_phone('٦٠٠١٢٣٤٥٦') is None
    assert normalize_phone('²²²²²²²²²') is None


def test_normalisation_is_idempotent():
    once = normalize_phone('600 123 456')
    assert normalize_phone(once) == once


def test_result_always_fits_varchar_20():
    # clients.phone / sms_reminders.phone_number are VARCHAR(20): '+' + 15 digits = 16.
    assert len(normalize_phone('+123456789012345')) <= 20


class TestMatchKeys:
    def test_polish_number_matches_every_stored_spelling(self):
        keys = phone_match_keys('+48600123456')
        # regexp_replace(stored, '[^0-9]', '', 'g') for each of these stored values:
        #   '600 123 456' -> '600123456', '+48 600 123 456' -> '48600123456',
        #   '0600123456' -> '0600123456', '0048600123456' -> '0048600123456'
        assert {'600123456', '48600123456', '0600123456', '0048600123456'} <= set(keys)

    def test_foreign_number_keys_have_no_polish_variants(self):
        keys = phone_match_keys('+491511234567')
        assert set(keys) == {'491511234567', '00491511234567'}

    def test_keys_are_exact_not_substrings(self):
        # The bug being fixed: '600' used to match every number containing 600.
        for key in phone_match_keys('+48600123456'):
            assert len(key) >= 9
        assert '600' not in phone_match_keys('+48600123456')

    def test_keys_are_digits_only_and_sorted_unique(self):
        keys = phone_match_keys('+48600123456')
        assert all(k.isdigit() for k in keys)
        assert keys == sorted(set(keys))


class TestFoldName:
    @pytest.mark.parametrize('a, b', [
        ('Kowalska', 'kowalska'),
        ('  Kowalska ', 'KOWALSKA'),
        ('Łukasz', 'Lukasz'),
        ('Żółć', 'zolc'),
        ('Kowalska-Nowak', 'kowalska nowak'),
        ('Anna  Maria', 'anna maria'),
    ])
    def test_equivalent_spellings_fold_together(self, a, b):
        assert fold_name(a) == fold_name(b)

    def test_different_names_stay_different(self):
        assert fold_name('Kowalska') != fold_name('Kowalski')
        assert fold_name('Kowalska') != fold_name('Kowalska-Nowak')

    @pytest.mark.parametrize('empty', [None, '', '   '])
    def test_empty_folds_to_empty_string(self, empty):
        assert fold_name(empty) == ''
