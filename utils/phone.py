"""
Phone-number helpers shared by the staff client form, the public booking page
and the SMS service. Default region: Poland (+48).

Why this exists: before it, three places each had their own idea of "a phone
number" — the SMS service normalised leniently and passed garbage straight to
Twilio, the public booking page stored whatever was typed (into a VARCHAR(20)),
and client lookup used `ILIKE '%<input>%'`, which let the input `600` match a
random client. One strict function removes all three.
"""
import re
import unicodedata
from typing import List, Optional

_SEPARATORS = re.compile(r'[\s\-\(\)\. ]')
_ONLY_DIGITS = re.compile(r'[0-9]+')

# E.164: '+' then 8-15 digits, first digit non-zero. (Shortest real subscriber
# numbers are ~7-8 digits incl. country code; 15 is the ITU hard cap.)
_E164_MIN_DIGITS = 8
_E164_MAX_DIGITS = 15

PHONE_FORMAT_HINT = 'Podaj numer w formacie 600 100 200 lub z kodem kraju, np. +49 151 1234567.'


def normalize_phone(raw) -> Optional[str]:
    """Return the number in E.164 (``+48600123456``) or ``None`` if it cannot
    be a dialable number.

    Accepted spellings (spaces, dashes, dots, parentheses are ignored):
      * ``600123456`` / ``600 123 456``       — 9 Polish digits
      * ``0600123456``                          — legacy trunk-prefix form
      * ``48600123456``                         — country code without ``+``
      * ``+48600123456`` / ``0048600123456``    — international
      * ``+4915112345678`` / ``004915112345678`` — any other country, 8-15 digits

    Rejected: letters, empty input, wrong length, a 9-digit Polish number that
    starts with 0, and a foreign number typed without ``+``/``00`` (ambiguous —
    we refuse to guess a country).
    """
    if raw is None:
        return None
    s = _SEPARATORS.sub('', str(raw))
    if not s:
        return None

    if s.startswith('00'):
        s = '+' + s[2:]

    if s.startswith('+'):
        digits = s[1:]
        if not _ONLY_DIGITS.fullmatch(digits) or digits.startswith('0'):
            return None
        if digits.startswith('48'):
            national = digits[2:]
            return f'+48{national}' if len(national) == 9 and national[0] != '0' else None
        if _E164_MIN_DIGITS <= len(digits) <= _E164_MAX_DIGITS:
            return f'+{digits}'
        return None

    if not _ONLY_DIGITS.fullmatch(s):
        return None
    if len(s) == 9 and s[0] != '0':
        return f'+48{s}'
    if len(s) == 10 and s[0] == '0' and s[1] != '0':
        return f'+48{s[1:]}'
    if len(s) == 11 and s.startswith('48') and s[2] != '0':
        return f'+{s}'
    return None


def phone_match_keys(e164: str) -> List[str]:
    """Every digits-only spelling under which the *same subscriber* may already
    be stored in ``clients.phone`` (which was free text for years).

    Used with ``regexp_replace(phone, '[^0-9]', '', 'g') = ANY(keys)`` — an
    exact match over a closed set, never a substring match.
    """
    digits = e164.lstrip('+')
    keys = {digits, '00' + digits}
    if digits.startswith('48') and len(digits) == 11:
        national = digits[2:]
        keys.update({national, '0' + national})
    return sorted(keys)


def fold_name(value: Optional[str]) -> str:
    """Case-, accent- and punctuation-insensitive form of a person's name, so
    ``"Kowalska"``, ``" kowalska "`` and ``"KOWALSKA"`` (and ``"Łukasz"`` vs
    ``"Lukasz"``) compare equal. ``ł`` has no Unicode decomposition, hence the
    explicit replacement before stripping combining marks."""
    if not value:
        return ''
    text = str(value).strip().casefold().replace('ł', 'l')
    text = unicodedata.normalize('NFKD', text)
    text = ''.join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r'[\s\-]+', ' ', text).strip()
