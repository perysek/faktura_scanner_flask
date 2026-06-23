"""
Functional test for price-history DELETE chain-healing — runs ON the Vultr
server against the LIVE database, but every write is rolled back.

Builds a controlled 3-row chain (80 closed, 100 closed, 120 open) on a real
service, then exercises ServicePriceHistoryRepository.delete_entry() across
scenarios using SAVEPOINTs so each starts from the same base.

Run:  source .venv/bin/activate && export $(grep -v '^#' .env | xargs)
      python scripts/test_price_history_delete_prod.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
import psycopg2.extras

DB_URL = os.environ["DATABASE_URL"]
PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
results = []


def check(name, cond, detail=""):
    results.append(bool(cond))
    print(f"  [{PASS if cond else FAIL}] {name}" + (f"  ({detail})" if detail else ""))


class _CtxConn:
    """Wrap a live connection so `with get_db_connection() as c:` doesn't close it."""
    def __init__(self, conn): self._conn = conn
    def __enter__(self): return self._conn
    def __exit__(self, *a): return False
    def cursor(self, *a, **k): return self._conn.cursor(*a, **k)


def main():
    conn = psycopg2.connect(DB_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    conn.autocommit = False
    cur = conn.cursor()

    print("=" * 70)
    print("PRICE-HISTORY DELETE — live functional test (all writes rolled back)")
    print("=" * 70)

    # Patch repo connection accessors to our rollback connection
    import repositories.services.service_price_history_repository as sph_mod
    sph_mod.get_db_connection = lambda: conn
    sph_mod.safe_commit = lambda c: None
    repo = sph_mod.ServicePriceHistoryRepository()

    import repositories.roles.role_repository as role_mod
    role_mod.get_db_connection = lambda: _CtxConn(conn)
    role_repo = role_mod.RoleRepository()

    # ── Build a controlled chain on a real service ──────────────────────────
    cur.execute("SELECT id, price, currency FROM services WHERE is_deleted = FALSE ORDER BY id LIMIT 1")
    svc = cur.fetchone()
    sid = svc["id"]

    cur.execute("DELETE FROM service_price_history WHERE service_id = %s", (sid,))
    def ins(price, frm, to):
        cur.execute(
            "INSERT INTO service_price_history (service_id, price, currency, effective_from, effective_to) "
            "VALUES (%s, %s, 'PLN', %s, %s) RETURNING id", (sid, price, frm, to))
        return cur.fetchone()["id"]
    a_id = ins(80,  "2026-01-01", "2026-03-01")   # closed
    b_id = ins(100, "2026-03-01", "2026-06-01")   # closed (middle)
    c_id = ins(120, "2026-06-01", None)           # open (current)
    cur.execute("UPDATE services SET price = 120 WHERE id = %s", (sid,))
    cur.execute("SAVEPOINT base")
    print(f"\nControlled chain on service {sid}: A={a_id}(80) B={b_id}(100) C={c_id}(120,open)")

    def open_row():
        cur.execute("SELECT id, price, effective_from FROM service_price_history "
                    "WHERE service_id=%s AND effective_to IS NULL", (sid,))
        return cur.fetchone()
    def svc_price():
        cur.execute("SELECT price FROM services WHERE id=%s", (sid,))
        return float(cur.fetchone()["price"])
    def row(rid):
        cur.execute("SELECT id, price, effective_from, effective_to FROM service_price_history WHERE id=%s", (rid,))
        return cur.fetchone()

    # ── Scenario A: delete the OPEN row → reopen previous + sync price ──────
    print("\n[A] Delete current/open row (C=120) → reopen B + sync services.price")
    res = repo.delete_entry(sid, c_id)
    check("status ok", res["status"] == "ok", res["status"])
    check("flagged reopened", res.get("reopened") is True)
    check("new_price == 100 (B)", res.get("new_price") == 100.0, res.get("new_price"))
    check("C row gone", row(c_id) is None)
    op = open_row()
    check("B is now the open row", op and op["id"] == b_id, op and op["id"])
    check("B kept its original effective_from", op and str(op["effective_from"])[:10] == "2026-03-01",
          op and str(op["effective_from"])[:10])
    check("services.price synced to 100", svc_price() == 100.0, svc_price())
    cur.execute("ROLLBACK TO SAVEPOINT base")

    # ── Scenario B: delete a CLOSED middle row → heal gap ──────────────────
    print("\n[B] Delete closed middle row (B=100) → extend A, no price change")
    res = repo.delete_entry(sid, b_id)
    check("status ok", res["status"] == "ok", res["status"])
    check("not reopened", res.get("reopened") is False)
    check("B row gone", row(b_id) is None)
    a = row(a_id)
    check("A extended to B.effective_to (2026-06-01)", a and str(a["effective_to"])[:10] == "2026-06-01",
          a and str(a["effective_to"])[:10])
    check("C still open (price unchanged)", svc_price() == 120.0, svc_price())
    cur.execute("ROLLBACK TO SAVEPOINT base")

    # ── Scenario C: cannot delete the last remaining row ───────────────────
    print("\n[C] Block deleting the only remaining row")
    cur.execute("DELETE FROM service_price_history WHERE service_id=%s AND id <> %s", (sid, c_id))
    res = repo.delete_entry(sid, c_id)
    check("status == last_row", res["status"] == "last_row", res["status"])
    check("row still present", row(c_id) is not None)
    cur.execute("ROLLBACK TO SAVEPOINT base")

    # ── Scenario D: not found (wrong id / wrong service) ───────────────────
    print("\n[D] Not-found handling")
    res = repo.delete_entry(sid, 999999999)
    check("status == not_found", res["status"] == "not_found", res["status"])
    cur.execute("ROLLBACK TO SAVEPOINT base")

    # ── Scenario E: permission helper ──────────────────────────────────────
    print("\n[E] role_can_edit_price_history()")
    check("superuser can edit", role_repo.role_can_edit_price_history("superuser") is True)
    check("admin can edit", role_repo.role_can_edit_price_history("admin") is True)
    check("accountant cannot edit", role_repo.role_can_edit_price_history("accountant") is False)
    check("stylist cannot edit", role_repo.role_can_edit_price_history("stylist") is False)

    # ── teardown ────────────────────────────────────────────────────────────
    conn.rollback()
    cur.close(); conn.close()

    print("\n" + "=" * 70)
    passed = sum(results); total = len(results)
    print(f"RESULT: {passed}/{total} checks passed — production data rolled back")
    print("=" * 70)
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
