"""
Client duplicate-detection service (pure logic, no Flask/DB deps).

Mirrors the offline analysis in ``scripts/find_duplicate_clients.py`` but is
shaped for a single candidate vs. the existing client list, so it can power the
live "possible duplicate" hints on the client create/edit forms.

Strategies (all the ones surfaced in the 2026-06 dedup pass):
  - PHONE   exact phone match (normalised to last 9 digits)        → high
  - SAME    identical first + last name                            → medium
  - SWAPPED first/last fields swapped                              → medium
  - PREFIX  courtesy prefix ('p.'/'pani') on a name                → medium
  - TYPO    one field identical, other off by a single character   → medium
  - INITIAL one name is a single-letter initial of the other       → low
  - EMPTY   existing record has a blank first/last that we'd fill  → low
  - TYPO2   2-char / both-field small typo                         → low

``find_duplicate_warnings`` returns a list of dicts ready for JSON:
    {id, name, phone, category, severity, field, message}
where ``field`` is 'phone' or 'name' so the UI knows which input to flag.
"""
from typing import List, Optional

PREFIX_TOKENS = ("p", "pan", "pani")
SEVERITY_RANK = {"high": 0, "medium": 1, "low": 2}


def normalize_phone(raw: Optional[str]) -> str:
    """Canonical phone key: digits only, last 9 (Polish mobile length)."""
    digits = "".join(ch for ch in (raw or "") if ch.isdigit())
    if not digits:
        return ""
    return digits[-9:] if len(digits) >= 9 else digits


def _clean(s: Optional[str]) -> str:
    return " ".join((s or "").split())


def _strip_prefix(name_low: str) -> str:
    toks = name_low.split()
    if toks and toks[0].rstrip(".") in PREFIX_TOKENS:
        return " ".join(toks[1:]).strip()
    return name_low


def _has_prefix(name_low: str) -> bool:
    toks = name_low.split()
    return bool(toks) and toks[0].rstrip(".") in PREFIX_TOKENS


def _deinitial(name_low: str) -> str:
    """Return the letter if the name is a single-letter initial ('a' / 'a.')."""
    t = name_low.rstrip(".").strip()
    return t if len(t) == 1 and t.isalpha() else ""


def levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a or not b:
        return len(a) or len(b)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _classify(cfn, cln, cph, efn, eln, eph):
    """Return (category, severity, field) for candidate vs existing, or None."""
    # Strongest signal: exact phone match (independent of name).
    if cph and cph == eph:
        return ("PHONE", "high", "phone")

    both_names = cfn and cln and efn and eln
    if both_names:
        if cfn == efn and cln == eln:
            return ("SAME", "medium", "name")
        if cfn == eln and cln == efn and cfn != cln:
            return ("SWAPPED", "medium", "name")
        # courtesy prefix on first (same last) or last (same first)
        if cln == eln and (_has_prefix(cfn) or _has_prefix(efn)) \
                and _strip_prefix(cfn) == _strip_prefix(efn) and cfn != efn:
            return ("PREFIX", "medium", "name")
        if cfn == efn and (_has_prefix(cln) or _has_prefix(eln)) \
                and _strip_prefix(cln) == _strip_prefix(eln) and cln != eln:
            return ("PREFIX", "medium", "name")
        # single-letter initial (same last)
        if cln == eln:
            ie, ic = _deinitial(efn), _deinitial(cfn)
            if ie and not ic and cfn[:1] == ie and len(cfn) > 1:
                return ("INITIAL", "low", "name")
            if ic and not ie and efn[:1] == ic and len(efn) > 1:
                return ("INITIAL", "low", "name")
        # single-field typo
        if cln == eln and cfn != efn:
            d, ml = levenshtein(cfn, efn), min(len(cfn), len(efn))
            if d == 1 and ml >= 3:
                return ("TYPO", "medium", "name")
            if d == 2 and ml >= 5:
                return ("TYPO2", "low", "name")
        if cfn == efn and cln != eln:
            d, ml = levenshtein(cln, eln), min(len(cln), len(eln))
            if d == 1 and ml >= 4:
                return ("TYPO", "medium", "name")
            if d == 2 and ml >= 6:
                return ("TYPO2", "low", "name")
        # combined small typo across both fields
        df, dl = levenshtein(cfn, efn), levenshtein(cln, eln)
        if 1 <= df + dl <= 3 and df <= 2 and dl <= 2 \
                and min(len(cfn), len(efn)) >= 3 and min(len(cln), len(eln)) >= 3:
            return ("TYPO2", "low", "name")

    # empty-field twin: the existing record is missing a name part we would fill
    if cfn and cln:
        if eln == "" and efn and efn == cfn:
            return ("EMPTY", "low", "name")
        if efn == "" and eln and eln == cln:
            return ("EMPTY", "low", "name")

    return None


def _message(category: str, name: str, phone: str) -> str:
    return {
        "PHONE": f"Ten numer telefonu ma już klient „{name}”. Sprawdź poprawność "
                 f"danych i potwierdź albo wyczyść.",
        "SAME": f"Klient „{name}” już istnieje (identyczne imię i nazwisko).",
        "SWAPPED": f"Możliwa zamiana imienia z nazwiskiem — istnieje „{name}”.",
        "PREFIX": f"Istnieje podobny klient „{name}” (różnica w przedrostku).",
        "INITIAL": f"Istnieje „{name}” — różnica tylko w inicjale imienia.",
        "EMPTY": f"Istnieje niekompletny wpis pasujący do „{name}”.",
        "TYPO": f"Bardzo podobny klient „{name}” — możliwa literówka.",
        "TYPO2": f"Podobny klient „{name}” — sprawdź, czy to nie literówka.",
    }.get(category, f"Możliwy duplikat: „{name}”.")


def find_duplicate_warnings(first_name, last_name, phone, existing,
                            *, exclude_id=None, limit=8) -> List[dict]:
    """Compare a candidate against existing client rows; return warning dicts.

    ``existing`` is an iterable of mappings with id/first_name/last_name/phone.
    Name-based checks require both candidate name fields; phone checks fire as
    soon as a full (>=9 digit) number is present. Results are sorted strongest
    first and capped at ``limit``.
    """
    cfn = _clean(first_name).lower()
    cln = _clean(last_name).lower()
    cph = normalize_phone(phone)

    # Nothing actionable yet (still typing) — skip the scan entirely.
    if not cph and not (cfn and cln):
        return []

    out = []
    for e in existing:
        eid = e["id"]
        if exclude_id is not None and eid == exclude_id:
            continue
        efn_raw, eln_raw = _clean(e.get("first_name")), _clean(e.get("last_name"))
        res = _classify(cfn, cln, cph, efn_raw.lower(), eln_raw.lower(),
                        normalize_phone(e.get("phone")))
        if not res:
            continue
        category, severity, field = res
        name = (efn_raw + " " + eln_raw).strip() or "(bez nazwiska)"
        out.append({
            "id": eid,
            "name": name,
            "phone": e.get("phone") or "",
            "category": category,
            "severity": severity,
            "field": field,
            "message": _message(category, name, e.get("phone") or ""),
        })

    out.sort(key=lambda m: (SEVERITY_RANK.get(m["severity"], 9), m["name"]))
    return out[:limit]
