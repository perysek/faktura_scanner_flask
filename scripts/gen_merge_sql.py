"""Generate the transactional merge SQL for the 13 approved Tier-1 duplicates."""
import csv
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

# (label, survivor_id, loser_id, override_name | None)
GROUPS = [
    ("T1.1", 551, 58, None),
    ("T1.2", 652, 504, None),
    ("T1.4", 316, 56, None),
    ("T1.5", 244, 156, None),
    ("T1.6", 212, 22, None),
    ("T1.7", 34, 33, None),
    ("T1.8", 423, 27, None),
    ("T1.3", 573, 656, ("Aleksandra", "Piątek")),    # override: latest row is field-swapped
    ("T1.9", 673, 634, None),
    ("T1.10", 554, 457, None),
    ("T1.11", 106, 469, None),
    ("T1.12", 501, 476, None),
    ("T1.13", 98, 455, ("Małgorzata", "Kopyś")),     # override: latest row is the typo
]

rows = {}
with open("assets/temp/clients_dump.csv", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        rows[int(r["id"])] = r


def nz(*v):
    for x in v:
        if x and x.strip():
            return x.strip()
    return ""


def q(s):
    return "'" + s.replace("'", "''") + "'"


sql = ["BEGIN;"]
for label, S, L, override in GROUPS:
    auth, other = (S, L) if S > L else (L, S)        # higher id = 'latest entry'
    if override:
        fn, ln = override
    else:
        fn = nz(rows[auth]["first_name"], rows[other]["first_name"])
        ln = nz(rows[auth]["last_name"], rows[other]["last_name"])
    ph = nz(rows[auth]["phone"], rows[other]["phone"])
    sql.append(f"\n-- {label}: keep id={S}, soft-delete id={L}  ->  \"{fn} {ln}\"  tel={ph}")
    for tbl in ("appointments", "income_records", "sms_reminders", "client_preferences"):
        sql.append(f"UPDATE {tbl} SET client_id={S} WHERE client_id={L};")
    sql.append(
        f"UPDATE clients s SET first_name={q(fn)}, last_name={q(ln)}, phone={q(ph)}, "
        f"email=COALESCE(s.email, l.email), "
        f"date_of_birth=COALESCE(s.date_of_birth, l.date_of_birth), "
        f"first_visit_date=LEAST(s.first_visit_date, l.first_visit_date), "
        f"last_visit_date=GREATEST(s.last_visit_date, l.last_visit_date), "
        f"notes=COALESCE(s.notes, l.notes), preferences=COALESCE(s.preferences, l.preferences), "
        f"is_active=TRUE, updated_at=CURRENT_TIMESTAMP "
        f"FROM clients l WHERE s.id={S} AND l.id={L};"
    )
    sql.append(
        f"UPDATE clients SET is_deleted=TRUE, deleted_at=CURRENT_TIMESTAMP, "
        f"is_active=FALSE WHERE id={L};"
    )
sql.append("\nCOMMIT;")

out = "\n".join(sql)
with open("assets/temp/merge_clients.sql", "w", encoding="utf-8") as f:
    f.write(out + "\n")
print(out)
