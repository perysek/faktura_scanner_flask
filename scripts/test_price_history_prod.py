"""
Functional test for the service_price_history feature — runs ON the Vultr server
against the LIVE database, but every write is rolled back so production data is
left byte-for-byte unchanged.

Strategy:
  * Use one psycopg2 connection with autocommit=False.
  * Do all mutating work (create service, change price) inside it.
  * Assert the repository methods + SQL joins behave correctly.
  * conn.rollback() at the end — nothing persists.

Run:  source .venv/bin/activate && export $(grep -v '^#' .env | xargs)
      python scripts/test_price_history_prod.py
"""
import os
import sys
from datetime import datetime, timedelta

# Running `python scripts/foo.py` puts scripts/ on sys.path, not the project
# root — add the parent dir so `repositories.*` / `config.*` imports resolve.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
import psycopg2.extras

DB_URL = os.environ["DATABASE_URL"]

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
results = []


def check(name, cond, detail=""):
    results.append(cond)
    mark = PASS if cond else FAIL
    line = f"  [{mark}] {name}"
    if detail:
        line += f"  ({detail})"
    print(line)


def main():
    conn = psycopg2.connect(DB_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    conn.autocommit = False
    cur = conn.cursor()

    print("=" * 70)
    print("SERVICE PRICE HISTORY — live functional test (all writes rolled back)")
    print("=" * 70)

    # ── 0. Schema sanity ────────────────────────────────────────────────────
    print("\n[0] Schema")
    cur.execute("""
        SELECT column_name, data_type FROM information_schema.columns
        WHERE table_name = 'service_price_history' ORDER BY ordinal_position
    """)
    cols = {r["column_name"]: r["data_type"] for r in cur.fetchall()}
    expected = {"id", "service_id", "price", "currency", "effective_from",
                "effective_to", "changed_by", "change_reason", "created_at"}
    check("all expected columns present", expected.issubset(cols.keys()),
          f"missing={expected - set(cols.keys())}")
    check("price is numeric", cols.get("price") == "numeric", cols.get("price"))

    # ── 1. Seed invariant: exactly one open row per service ─────────────────
    print("\n[1] Seed invariant (pre-existing data)")
    cur.execute("""
        SELECT COUNT(*) AS bad FROM (
            SELECT service_id FROM service_price_history WHERE effective_to IS NULL
            GROUP BY service_id HAVING COUNT(*) > 1
        ) x
    """)
    check("no service has >1 open price row", cur.fetchone()["bad"] == 0)

    cur.execute("SELECT COUNT(*) AS n FROM services WHERE is_deleted = FALSE")
    n_services = cur.fetchone()["n"]
    cur.execute("SELECT COUNT(*) AS n FROM service_price_history WHERE effective_to IS NULL")
    n_open = cur.fetchone()["n"]
    check("open rows >= active services", n_open >= n_services,
          f"open={n_open}, active_services={n_services}")

    # ── 2. record_price_change() via the repository ─────────────────────────
    # Import the actual repo, but force it to use OUR rollback connection by
    # monkeypatching get_db_connection in the module it imported.
    print("\n[2] ServicePriceHistoryRepository.record_price_change()")
    import repositories.services.service_price_history_repository as sph_mod
    sph_mod.get_db_connection = lambda: conn          # use our txn connection
    sph_mod.safe_commit = lambda c: None              # never commit during test
    repo = sph_mod.ServicePriceHistoryRepository()

    # Pick a real service to mutate (rolled back later)
    cur.execute("SELECT id, name, price, currency FROM services WHERE is_deleted = FALSE ORDER BY id LIMIT 1")
    svc = cur.fetchone()
    sid = svc["id"]
    old_price = float(svc["price"])
    new_price = round(old_price + 17.50, 2)

    # baseline open-row count for this service
    cur.execute("SELECT COUNT(*) AS n FROM service_price_history WHERE service_id=%s AND effective_to IS NULL", (sid,))
    open_before = cur.fetchone()["n"]

    new_id = repo.record_price_change(
        service_id=sid, new_price=new_price, currency=svc["currency"],
        changed_by=None, change_reason="TEST — automated, will roll back",
    )
    check("returned a new row id", isinstance(new_id, int) and new_id > 0, f"id={new_id}")

    # Still exactly one open row for this service (old closed, new opened)
    cur.execute("SELECT COUNT(*) AS n FROM service_price_history WHERE service_id=%s AND effective_to IS NULL", (sid,))
    open_after = cur.fetchone()["n"]
    check("still exactly one open row after change", open_after == 1, f"before={open_before}, after={open_after}")

    # The new open row carries the new price
    cur.execute("SELECT price, change_reason FROM service_price_history WHERE id=%s", (new_id,))
    row = cur.fetchone()
    check("new open row has the new price", float(row["price"]) == new_price,
          f"{float(row['price'])} vs {new_price}")
    check("change_reason stored", row["change_reason"] == "TEST — automated, will roll back")

    # The previously-open row is now closed
    cur.execute("""
        SELECT effective_to FROM service_price_history
        WHERE service_id=%s AND id<>%s ORDER BY effective_from DESC LIMIT 1
    """, (sid, new_id))
    prev = cur.fetchone()
    check("previous row was closed (effective_to set)", prev and prev["effective_to"] is not None)

    # ── 3. Partial UNIQUE index actually blocks a second open row ───────────
    print("\n[3] Partial UNIQUE index enforcement")
    blocked = False
    try:
        with conn.cursor() as c2:
            c2.execute("""
                INSERT INTO service_price_history (service_id, price, currency, effective_from)
                VALUES (%s, %s, 'PLN', NOW())
            """, (sid, 999.99))
    except psycopg2.errors.UniqueViolation:
        blocked = True
        conn.rollback()  # clear the aborted-txn state
    check("second open row rejected by unique index", blocked)

    # NOTE: rollback above wiped our test writes; re-do the record for steps 4-5
    # (they only need read-level correctness, so re-run the change).
    new_id = repo.record_price_change(
        service_id=sid, new_price=new_price, currency=svc["currency"],
        changed_by=None, change_reason="TEST2",
    )

    # ── 4. get_history / get_price_at / get_last_change_dates ───────────────
    print("\n[4] Repository read methods")
    hist = repo.get_history(sid)
    check("get_history returns >= 2 rows (orig + change)", len(hist) >= 2, f"len={len(hist)}")
    check("get_history newest-first", len(hist) >= 2 and hist[0]["effective_from"] >= hist[1]["effective_from"])
    check("history row exposes changed_by_name key", "changed_by_name" in hist[0])

    price_now = repo.get_price_at(sid, datetime.now())
    check("get_price_at(now) == new price", price_now == new_price, f"{price_now} vs {new_price}")

    # A point in time before this feature existed → should be the seeded price,
    # or None if the seed timestamp is after it. Either way must not raise.
    price_past = repo.get_price_at(sid, datetime.now() - timedelta(days=3650))
    check("get_price_at(10y ago) does not error", True, f"returned {price_past}")

    last = repo.get_last_change_dates([sid])
    check("get_last_change_dates returns this service", sid in last, f"keys={list(last.keys())}")
    check("get_last_change_dates empty input → {}", repo.get_last_change_dates([]) == {})

    # ── 5. Analytics lateral-join query shape ───────────────────────────────
    print("\n[5] Analytics get_service_price_analysis() new columns")
    import repositories.analytics.analytics_repository as an_mod
    # Patch its connection accessor to our txn connection
    an_mod.DatabaseConnection.get_connection = staticmethod(lambda: conn)
    an_repo = an_mod.AnalyticsRepository()
    today = datetime.now().date()
    rows = an_repo.get_service_price_analysis(today - timedelta(days=30), today)
    check("analysis returns rows", len(rows) > 0, f"len={len(rows)}")
    if rows:
        keys = rows[0].keys()
        check("row has last_price_change", "last_price_change" in keys)
        check("row has price_at_period_start", "price_at_period_start" in keys)

    # ── 6. Appointment line items expose current_catalogue_price ────────────
    print("\n[6] Appointment service join — current_catalogue_price")
    cur.execute("""
        SELECT aps.appointment_id
        FROM appointment_services aps LIMIT 1
    """)
    appt = cur.fetchone()
    if appt:
        import repositories.appointments.appointment_service_repository as as_mod
        as_mod.get_db_connection = lambda: _CtxConn(conn)   # supports `with ... as conn`
        as_repo = as_mod.AppointmentServiceRepository()
        items = as_repo.get_all_for_appointment(appt["appointment_id"])
        check("line items returned", len(items) > 0, f"len={len(items)}")
        check("each line item has current_catalogue_price",
              all("current_catalogue_price" in dict(r) for r in items))
    else:
        check("no appointment_services rows to test (skipped)", True, "empty table")

    # ── teardown ────────────────────────────────────────────────────────────
    conn.rollback()
    cur.close()
    conn.close()

    print("\n" + "=" * 70)
    passed = sum(1 for r in results if r)
    total = len(results)
    print(f"RESULT: {passed}/{total} checks passed — production data rolled back")
    print("=" * 70)
    sys.exit(0 if passed == total else 1)


class _CtxConn:
    """Wrap a live connection so `with get_db_connection() as conn:` works
    without closing/committing the underlying shared test connection."""
    def __init__(self, conn):
        self._conn = conn
    def __enter__(self):
        return self._conn
    def __exit__(self, *a):
        return False  # do not suppress, do not close
    def cursor(self, *a, **k):
        return self._conn.cursor(*a, **k)


if __name__ == "__main__":
    main()
