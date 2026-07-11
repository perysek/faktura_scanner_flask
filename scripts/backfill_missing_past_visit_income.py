"""
Backfill income_records for 'completed' appointments that never got one.

Context: before the fix in services/appointment_service.py (resolve_past_status),
the Past Visits Scanner modal (PUT /api/appointments/<id>/past-status) set an
appointment's status to 'completed' by calling AppointmentRepository.update_status()
directly, bypassing every code path that creates an income_records row. Any visit
resolved as "zakończona" through that modal before the fix landed is 'completed'
in the appointments table but has NO matching income_records row at all — it's
invisible on the /income dashboard.

This script finds exactly that set and creates the missing rows, using each
appointment's own appointment_date as payment_date (not today), matching how
resolve_past_status computes income now.

Scope, deliberately conservative:
  * Only appointments with ZERO income_records rows (any is_deleted state) are
    touched. If a row exists — even soft-deleted — that appointment went through
    a working code path at least once; we leave staff's own delete/edit history
    alone rather than guessing at intent.
  * Appointments with no appointment_services line items are listed separately
    and SKIPPED — a completed visit with no services attached is a data anomaly,
    not something to silently backfill as a 0,00 zł income record.

Run from the app directory with the venv active and DATABASE_URL exported:

    python scripts/backfill_missing_past_visit_income.py            # dry run (default)
    python scripts/backfill_missing_past_visit_income.py --apply    # write for real
"""
import os
import sys
import io
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

import psycopg2
import psycopg2.extras

DB_URL = os.environ["DATABASE_URL"]

CANDIDATES_SQL = """
    SELECT
        a.id, a.appointment_date, a.discount_amount,
        a.client_id, a.employee_id,
        c.first_name || ' ' || c.last_name AS client_name,
        e.first_name || ' ' || e.last_name AS employee_name
    FROM appointments a
    JOIN clients c ON c.id = a.client_id
    JOIN employees e ON e.id = a.employee_id
    WHERE a.status = 'completed'
      AND a.is_deleted = FALSE
      AND NOT EXISTS (
          SELECT 1 FROM income_records ir WHERE ir.appointment_id = a.id
      )
    ORDER BY a.appointment_date
"""

TOTALS_SQL = """
    SELECT
        COALESCE(SUM(price_charged), 0) AS total_price,
        COALESCE(SUM(commission_amount), 0) AS total_commission,
        COUNT(*) AS service_count
    FROM appointment_services
    WHERE appointment_id = %s
"""

INSERT_SQL = """
    INSERT INTO income_records (
        appointment_id, client_id, employee_id,
        total_amount, discount_amount, net_amount,
        commission_total, payment_method, payment_date, notes
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    RETURNING id
"""


def main():
    apply_changes = "--apply" in sys.argv

    conn = psycopg2.connect(DB_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    conn.autocommit = False
    cur = conn.cursor()

    cur.execute(CANDIDATES_SQL)
    candidates = cur.fetchall()

    if not candidates:
        print("Brak wizyt do uzupelnienia — kazda 'completed' wizyta ma juz rekord przychodu.")
        cur.close()
        conn.close()
        return

    to_create = []
    skipped_no_services = []

    for appt in candidates:
        cur.execute(TOTALS_SQL, (appt["id"],))
        totals = cur.fetchone()

        if totals["service_count"] == 0:
            skipped_no_services.append(appt)
            continue

        disc = Decimal(str(appt["discount_amount"] or "0"))
        total_price = Decimal(str(totals["total_price"]))
        to_create.append({
            "appointment": appt,
            "total_amount": total_price,
            "discount_amount": disc,
            "net_amount": total_price - disc,
            "commission_total": Decimal(str(totals["total_commission"])),
        })

    label = "[DRY RUN] " if not apply_changes else ""

    if to_create:
        print(f"{label}Wizyty do uzupelnienia ({len(to_create)}):\n")
        print(f"  {'ID':>5}  {'Data wizyty':11}  {'Klient':25}  {'Pracownik':20}  {'Brutto':>10}  {'Netto':>10}  {'Prowizja':>10}")
        print("  " + "-" * 100)
        for item in to_create:
            a = item["appointment"]
            print(
                f"  {a['id']:>5}  {str(a['appointment_date']):11}  "
                f"{a['client_name'][:25]:25}  {a['employee_name'][:20]:20}  "
                f"{item['total_amount']:>10.2f}  {item['net_amount']:>10.2f}  {item['commission_total']:>10.2f}"
            )

    if skipped_no_services:
        print(f"\nPOMINIETO — brak pozycji uslug, wymaga recznego przegladu ({len(skipped_no_services)}):\n")
        for a in skipped_no_services:
            print(f"  ID {a['id']}  {a['appointment_date']}  {a['client_name']} / {a['employee_name']}")

    if not to_create:
        print("\nNic do wstawienia (wszystkie kandydatki pominiete — brak uslug).")
        conn.rollback()
        cur.close()
        conn.close()
        return

    total_revenue = sum(item["total_amount"] for item in to_create)
    print(f"\nRazem: {len(to_create)} rekordow, laczny przychod brutto: {total_revenue:.2f} zl")

    if not apply_changes:
        print("\nTo jest podglad, nic nie zostalo zapisane. Aby wykonac zmiany, uruchom z flaga --apply:")
        print("  python scripts/backfill_missing_past_visit_income.py --apply")
        conn.rollback()
    else:
        for item in to_create:
            a = item["appointment"]
            cur.execute(INSERT_SQL, (
                a["id"], a["client_id"], a["employee_id"],
                str(item["total_amount"]), str(item["discount_amount"]), str(item["net_amount"]),
                str(item["commission_total"]), None, a["appointment_date"].isoformat(), None,
            ))
        conn.commit()
        print(f"\nUtworzono {len(to_create)} rekordow przychodu.")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
