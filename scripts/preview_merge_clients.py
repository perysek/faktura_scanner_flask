"""
PREVIEW ONLY — shows what each Tier 1 merge would produce. No DB writes.

Rule (user): authoritative record = the 'latest entry created'. Since every row
shares the same created_at timestamp, we use the higher id as the proxy for
'latest'. name/surname/phone/email come from the authoritative row; any BLANK
field there is backfilled from the other row. The physically surviving row is
the one with more live appointments (less FK re-pointing); dates are merged
(first_visit=min, last_visit=max).
"""
import csv
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

# (label, idA, idB, classification)
GROUPS = [
    ("T1.1", 58, 551, "SAME"),
    ("T1.2", 504, 652, "SAME"),
    ("T1.4", 56, 316, "EMPTY"),
    ("T1.5", 156, 244, "TYPO"),
    ("T1.6", 22, 212, "TYPO"),
    ("T1.7", 33, 34, "TYPO"),
    ("T1.8", 27, 423, "TYPO"),
    ("T1.3", 573, 656, "SWAPPED"),
    ("T1.9", 634, 673, "TYPO2"),
    ("T1.10", 457, 554, "TYPO2"),
    ("T1.11", 106, 469, "TYPO2"),
    ("T1.12", 476, 501, "TYPO2"),
    ("T1.13", 98, 455, "TYPO2"),
    ("T1.14", 36, 240, "FAMILY"),
    ("T1.15", 322, 364, "FAMILY"),
    ("T1.16", 66, 598, "FAMILY"),
    ("T1.17", 373, 548, "FAMILY"),
    ("T1.18", 557, 649, "FAMILY"),
    ("T1.19", 213, 676, "DIFFERENT"),
    ("T1.20", 97, 166, "DIFFERENT"),
    ("T1.21", 108, 473, "DIFFERENT"),
]

APPTS = {22: 0, 27: 11, 33: 7, 34: 19, 36: 63, 56: 10, 58: 3, 66: 1, 97: 5,
         98: 21, 106: 18, 108: 6, 156: 3, 166: 3, 212: 4, 213: 1, 240: 16,
         244: 4, 316: 13, 322: 3, 364: 22, 373: 3, 423: 12, 455: 10, 457: 3,
         469: 7, 473: 3, 476: 2, 501: 31, 504: 4, 548: 13, 551: 5, 554: 8,
         557: 9, 573: 9, 598: 13, 634: 1, 649: 5, 652: 4, 656: 7, 673: 1, 676: 2}

rows = {}
with open("assets/temp/clients_dump.csv", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        rows[int(r["id"])] = r


def nz(*vals):
    for v in vals:
        if v and v.strip():
            return v.strip()
    return ""


VERDICT = {
    "SAME": "✅ clean", "EMPTY": "✅ clean (blank backfilled)",
    "TYPO": "✅ clean (latest spelling kept)",
    "TYPO2": "🟠 review — latest spelling kept, both plausible",
    "SWAPPED": "🟠 OVERRIDE — latest row is field-swapped garbage",
    "FAMILY": "🔴 likely DIFFERENT people (same surname, diff first name)",
    "DIFFERENT": "🔴 likely DIFFERENT people (names differ)",
}

print(f"{'grp':5} {'survivor':>8} {'soft-del':>8}  {'resulting name':<26} {'phone':<11} appts→  verdict")
print("-" * 110)
for label, a, b, cls in GROUPS:
    auth, other = (a, b) if a > b else (b, a)        # higher id = 'latest'
    ra, ro = rows[auth], rows[other]
    fn = nz(ra["first_name"], ro["first_name"])
    ln = nz(ra["last_name"], ro["last_name"])
    ph = nz(ra["phone"], ro["phone"])
    em = nz(ra["email"], ro["email"])
    # physical survivor = more live appts (tie -> higher id)
    survivor = a if APPTS[a] > APPTS[b] else b if APPTS[b] > APPTS[a] else auth
    loser = b if survivor == a else a
    # recommended override name for swap/typo where latest is the bad copy
    rec = ""
    if cls == "SWAPPED":
        clean = ro if auth in (656, 676) else ra
        rec = f"  ↳ RECOMMEND name: '{clean['first_name']} {clean['last_name']}'"
    if label == "T1.13":
        rec = "  ↳ RECOMMEND name: 'Małgorzata Kopyś' (id 98, latest is the typo)"
    name = f"{fn} {ln}".strip()
    moved = APPTS[loser]
    print(f"{label:5} {survivor:>8} {loser:>8}  {name:<26.26} {ph:<11} {moved:>5}   {VERDICT[cls]}")
    if rec:
        print(rec)
        print(f"        (latest-id rule would instead set: '{name}')")
