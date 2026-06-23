"""
Duplicate-client detector (READ-ONLY analysis, no DB mutations).

Reads an exported CSV of the live `clients` table and reports duplicate
candidates in confidence tiers. Strong key = normalised phone (last 9 digits).

  TIER 1  Same phone number (exact). Members annotated with how their NAMES
          relate: SAME / TYPO / SWAPPED / PREFIX / INITIAL / EMPTY / DIFFERENT.
          A shared phone + matching/near name = near-certain duplicate.
  TIER 2  Near-identical names, phone differs or missing:
            - PREFIX  'p.'/'pani ' courtesy prefix on a name
            - INITIAL one name is a single-letter initial of the other
            - SWAPPED first/last fields swapped (often + a typo)
            - TYPO    one field identical, the other off by a single character
  TIER 3  Identical full name but different phone (common-name coincidence vs
          same person w/ new number — needs a human glance).
  TIER 4  Incomplete records (blank first OR last name) not already linked by
          phone — listed for manual reconciliation, NOT asserted as duplicates.

Usage:  python scripts/find_duplicate_clients.py [clients_dump.csv]
"""
import csv
import io
import sys
from collections import defaultdict

# Force UTF-8 so Polish diacritics render instead of console mojibake.
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

CSV_PATH = sys.argv[1] if len(sys.argv) > 1 else "assets/temp/clients_dump.csv"
REPORT_PATH = "assets/temp/duplicate_clients_report.md"


# ── normalisation ─────────────────────────────────────────────────────────────
def norm_phone(raw):
    digits = "".join(ch for ch in (raw or "") if ch.isdigit())
    if not digits:
        return ""
    return digits[-9:] if len(digits) >= 9 else digits


def clean(s):
    return " ".join((s or "").split())


PREFIX_TOKENS = ("p", "pan", "pani")


def strip_prefix(name_low):
    toks = name_low.split()
    if toks and toks[0].rstrip(".") in PREFIX_TOKENS:
        return " ".join(toks[1:]).strip()
    return name_low


def has_prefix(name_low):
    toks = name_low.split()
    return bool(toks) and toks[0].rstrip(".") in PREFIX_TOKENS


def deinitial(name_low):
    t = name_low.rstrip(".").strip()
    return t if len(t) == 1 and t.isalpha() else ""


def levenshtein(a, b):
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


# ── name-relationship classifier ──────────────────────────────────────────────
def classify(a, b):
    """Return (label, detail) describing how two clients' names relate."""
    fa, la, fb, lb = a["fn_l"], a["ln_l"], b["fn_l"], b["ln_l"]
    Fa, La, Fb, Lb = a["fn"], a["ln"], b["fn"], b["ln"]

    if fa and la and fa == fb and la == lb:
        return "SAME", "identical name"

    same_last = la and la == lb
    same_first = fa and fa == fb

    # prefix
    if same_last and (has_prefix(fa) or has_prefix(fb)) and strip_prefix(fa) == strip_prefix(fb) and fa != fb:
        return "PREFIX", f"'{Fa}' vs '{Fb}' (same last '{La}')"
    if same_first and (has_prefix(la) or has_prefix(lb)) and strip_prefix(la) == strip_prefix(lb) and la != lb:
        return "PREFIX", f"'{La}' vs '{Lb}' (same first '{Fa}')"

    # initial
    if same_last:
        ia, ib = deinitial(fa), deinitial(fb)
        if ia and not ib and fb[:1] == ia and len(fb) > 1:
            return "INITIAL", f"first '{Fa}' is initial of '{Fb}' (last '{La}')"
        if ib and not ia and fa[:1] == ib and len(fa) > 1:
            return "INITIAL", f"first '{Fb}' is initial of '{Fa}' (last '{La}')"
    if same_first:
        ia, ib = deinitial(la), deinitial(lb)
        if ia and not ib and lb[:1] == ia and len(lb) > 1:
            return "INITIAL", f"last '{La}' is initial of '{Lb}' (first '{Fa}')"
        if ib and not ia and la[:1] == ib and len(la) > 1:
            return "INITIAL", f"last '{Lb}' is initial of '{La}' (first '{Fa}')"

    # empty field (one side blank, populated parts consistent)
    if (la == "") ^ (lb == "") and same_first:
        full = b if la == "" else a
        return "EMPTY", f"blank last name; first='{Fa}', other last='{full['ln']}'"
    if (fa == "") ^ (fb == "") and same_last:
        full = b if fa == "" else a
        return "EMPTY", f"blank first name; last='{La}', other first='{full['fn']}'"

    # swapped first/last (allow a 1-char typo on each side)
    if fa and la and fb and lb and fa != la:
        d1, d2 = levenshtein(fa, lb), levenshtein(la, fb)
        if d1 <= 1 and d2 <= 1 and (d1 + d2) <= 1 or (d1 == 0 and d2 == 0):
            return "SWAPPED", f"'{Fa} {La}' vs '{Fb} {Lb}' (fields swapped)"
        if d1 <= 1 and d2 <= 1:
            return "SWAPPED", f"'{Fa} {La}' vs '{Fb} {Lb}' (fields swapped + typo)"

    # typo: one field identical, other off by 1-2 chars
    if same_last and fa and fb and fa != fb:
        d = levenshtein(fa, fb)
        ml = min(len(fa), len(fb))
        if d == 1 and ml >= 3:
            return "TYPO", f"first '{Fa}' vs '{Fb}' dist={d} (same last '{La}')"
        if d == 2 and ml >= 5:
            return "TYPO2", f"first '{Fa}' vs '{Fb}' dist={d} (same last '{La}')"
    if same_first and la and lb and la != lb:
        d = levenshtein(la, lb)
        ml = min(len(la), len(lb))
        if d == 1 and ml >= 4:
            return "TYPO", f"last '{La}' vs '{Lb}' dist={d} (same first '{Fa}')"
        if d == 2 and ml >= 6:
            return "TYPO2", f"last '{La}' vs '{Lb}' dist={d} (same first '{Fa}')"

    # combined typo: BOTH fields close (e.g. 'Małgorzata Kopyś' vs 'Magłorzata Kopys')
    if fa and la and fb and lb:
        df, dl = levenshtein(fa, fb), levenshtein(la, lb)
        if (df + dl) >= 1 and df <= 2 and dl <= 2 and (df + dl) <= 3 \
                and min(len(fa), len(fb)) >= 3 and min(len(la), len(lb)) >= 3:
            return "TYPO2", f"first '{Fa}'/'{Fb}' dist={df}, last '{La}'/'{Lb}' dist={dl}"

    # same surname, clearly different first name → probably relatives sharing a line
    if same_last and fa and fb and fa != fb:
        return "FAMILY", f"same last '{La}', different first '{Fa}' vs '{Fb}'"

    return "DIFFERENT", ""


# ── load ──────────────────────────────────────────────────────────────────────
rows = []
with open(CSV_PATH, encoding="utf-8", newline="") as f:
    for r in csv.DictReader(f):
        r["id"] = int(r["id"])
        r["fn"] = clean(r["first_name"])
        r["ln"] = clean(r["last_name"])
        r["fn_l"] = r["fn"].lower()
        r["ln_l"] = r["ln"].lower()
        r["ph"] = norm_phone(r["phone"])
        rows.append(r)
by_id = {r["id"]: r for r in rows}
n = len(rows)


def fmt(r):
    name = (r["fn"] + " " + r["ln"]).strip() or "(no name)"
    lv = r["last_visit_date"] or "—"
    created = (r["created_at"] or "")[:10]
    return f"  id={r['id']:>4} | {name:<30.30} | tel={r['phone'] or '—':<13} | last_visit={lv:<10} | created={created}"


out = []
def emit(s=""):
    out.append(s)


# ── TIER 1: shared phone ──────────────────────────────────────────────────────
phone_groups = defaultdict(list)
for r in rows:
    if r["ph"]:
        phone_groups[r["ph"]].append(r["id"])
phone_groups = {p: sorted(ids) for p, ids in phone_groups.items() if len(ids) > 1}

# best name-relationship within each phone group (for sorting/labelling)
def group_rel(ids):
    labels = set()
    details = []
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            lbl, det = classify(by_id[ids[i]], by_id[ids[j]])
            labels.add(lbl)
            if det:
                details.append(f"      [{lbl}] {det}")
    return labels, details

RANK = {"SAME": 0, "EMPTY": 1, "PREFIX": 1, "INITIAL": 1, "SWAPPED": 1,
        "TYPO": 2, "TYPO2": 3, "FAMILY": 4, "DIFFERENT": 5}
TAG = {
    "SAME": "DUPLICATE (identical name)",
    "EMPTY": "DUPLICATE (blank name field)",
    "PREFIX": "DUPLICATE (courtesy prefix)",
    "INITIAL": "DUPLICATE (initial only)",
    "SWAPPED": "DUPLICATE (fields swapped)",
    "TYPO": "DUPLICATE (1-char typo)",
    "TYPO2": "LIKELY DUP (small typo)",
    "FAMILY": "CHECK — same surname, different first name (family?)",
    "DIFFERENT": "CHECK — names differ (family/shared line?)",
}
DUP_LABELS = {"SAME", "EMPTY", "PREFIX", "INITIAL", "SWAPPED", "TYPO", "TYPO2"}
t1 = []
for p, ids in phone_groups.items():
    labels, details = group_rel(ids)
    best = min(labels, key=lambda l: RANK.get(l, 9))
    t1.append((RANK.get(best, 9), best, p, ids, labels, details))
t1.sort(key=lambda x: (x[0], by_id[x[3][0]]["fn_l"]))

# ── TIER 2/3: name pairs WITHOUT a shared phone ───────────────────────────────
phone_pair_set = set()
for ids in phone_groups.values():
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            phone_pair_set.add((ids[i], ids[j]))

tier2 = defaultdict(list)   # label -> list of (a,b,detail)
same_name_diffphone = []
for i in range(n):
    a = rows[i]
    for j in range(i + 1, n):
        b = rows[j]
        if (a["id"], b["id"]) in phone_pair_set:
            continue  # already in Tier 1
        lbl, det = classify(a, b)
        if lbl in ("PREFIX", "INITIAL", "SWAPPED", "TYPO"):
            # for TYPO without phone, keep only the tighter dist==1 cases
            if lbl == "TYPO" and "dist=2" in det:
                continue
            tier2[lbl].append((a["id"], b["id"], det))
        elif lbl == "SAME":
            same_name_diffphone.append((a["id"], b["id"]))

# ── TIER 4: incomplete records not linked by phone ────────────────────────────
linked = set()
for ids in phone_groups.values():
    linked.update(ids)
incomplete = [r for r in rows if (r["fn"] == "" or r["ln"] == "") and r["id"] not in linked]


# ── render ────────────────────────────────────────────────────────────────────
n_t1 = len(t1)
n_t1_dup = sum(1 for r in t1 if r[1] in DUP_LABELS)
n_t1_fam = n_t1 - n_t1_dup
n_t2 = sum(len(v) for v in tier2.values())

emit("# Duplicate-client candidates — review before merging")
emit(f"\nSource: {CSV_PATH} · {n} live (non-deleted) clients\n")
emit("## Summary")
emit(f"- **Tier 1 — shared phone number:** {n_t1} groups "
     f"({n_t1_dup} with matching/near names = near-certain duplicates, "
     f"{n_t1_fam} with differing names = possible family/shared line)")
emit(f"- **Tier 2 — near-identical name, phone differs/missing:** {n_t2} pairs "
     f"(PREFIX={len(tier2['PREFIX'])}, INITIAL={len(tier2['INITIAL'])}, "
     f"SWAPPED={len(tier2['SWAPPED'])}, TYPO={len(tier2['TYPO'])})")
emit(f"- **Tier 3 — identical full name, different phone:** {len(same_name_diffphone)} pairs (low confidence)")
emit(f"- **Tier 4 — incomplete records (blank name field), unlinked:** {len(incomplete)}")

emit("\n---\n## TIER 1 — Same phone number (exact match)")
emit("_A shared number with a matching or near-matching name is a near-certain duplicate._\n")
k = 0
for rank, best, p, ids, labels, details in t1:
    k += 1
    tag = TAG.get(best, best)
    lblstr = ",".join(sorted(labels - {"DIFFERENT"})) or "DIFFERENT"
    emit(f"### T1.{k}  phone {p}  →  {tag}   [{lblstr}]")
    for rid in ids:
        emit(fmt(by_id[rid]))
    for d in details:
        emit(d)
    emit("")

emit("\n---\n## TIER 2 — Near-identical name, phone differs or missing")
emit("_Likely the same person with the phone also changed/mistyped, or close relatives. Verify each._\n")
for lbl in ("SWAPPED", "PREFIX", "INITIAL", "TYPO"):
    pairs = tier2[lbl]
    if not pairs:
        continue
    emit(f"### {lbl} ({len(pairs)})")
    for aid, bid, det in sorted(pairs, key=lambda x: by_id[x[0]]["fn_l"]):
        emit(fmt(by_id[aid]))
        emit(fmt(by_id[bid]))
        emit(f"      [{lbl}] {det}")
        emit("")

emit("\n---\n## TIER 3 — Identical full name, different phone (low confidence)")
emit("_Common names coincide; could be two people or one person with a new number._\n")
for aid, bid in sorted(same_name_diffphone, key=lambda x: by_id[x[0]]["fn_l"]):
    emit(fmt(by_id[aid]))
    emit(fmt(by_id[bid]))
    emit("")

emit("\n---\n## TIER 4 — Incomplete records (blank first OR last name), not phone-linked")
emit("_Not asserted as duplicates — listed so you can complete or reconcile them manually._\n")
for r in sorted(incomplete, key=lambda r: (r["fn_l"], r["ln_l"])):
    emit(fmt(r))

report = "\n".join(out)
with open(REPORT_PATH, "w", encoding="utf-8") as f:
    f.write(report)
print(report)
print(f"\n\n[report written to {REPORT_PATH}]")
