"""
Repository dla historii cen usług (service_price_history).

Śledzi zmiany cen katalogowych w czasie metodą "effective dating":
każdy wiersz reprezentuje cenę obowiązującą w przedziale
[effective_from, effective_to). Wiersz z effective_to IS NULL to cena aktualna.

Niezmiennik: dokładnie jeden otwarty wiersz (effective_to IS NULL) na usługę —
wymuszony częściowym indeksem UNIQUE idx_sph_open_entries.
"""
from datetime import datetime
from typing import Optional

from config.database import get_db_connection, safe_commit


class ServicePriceHistoryRepository:
    """Repository do śledzenia zmian cen usług katalogowych."""

    def record_price_change(
        self,
        service_id: int,
        new_price: float,
        currency: str = 'PLN',
        changed_by: Optional[int] = None,
        change_reason: Optional[str] = None,
    ) -> int:
        """Zamknij bieżący otwarty wpis i wstaw nowy. Zwraca id nowego wiersza.

        Obie operacje dzielą jedno połączenie/transakcję, więc niezmiennik
        "jeden otwarty wpis na usługę" nigdy nie jest naruszony pomiędzy krokami.
        """
        close_open = """
            UPDATE service_price_history
            SET effective_to = NOW()
            WHERE service_id = %s AND effective_to IS NULL
        """
        insert_new = """
            INSERT INTO service_price_history
                (service_id, price, currency, effective_from, changed_by, change_reason)
            VALUES (%s, %s, %s, NOW(), %s, %s)
            RETURNING id
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(close_open, (service_id,))
        cursor.execute(insert_new, (service_id, new_price, currency, changed_by, change_reason))
        new_id = cursor.fetchone()['id']
        safe_commit(conn)
        return new_id

    def get_history(self, service_id: int) -> list[dict]:
        """Zwróć wszystkie wpisy historii cen usługi, najnowsze pierwsze.

        Dołącza nazwę użytkownika, który dokonał zmiany (changed_by_name).
        """
        query = """
            SELECT sph.id,
                   sph.service_id,
                   sph.price,
                   sph.currency,
                   sph.effective_from,
                   sph.effective_to,
                   sph.changed_by,
                   u.full_name AS changed_by_name,
                   sph.change_reason,
                   sph.created_at
            FROM service_price_history sph
            LEFT JOIN users u ON u.id = sph.changed_by
            WHERE sph.service_id = %s
            ORDER BY sph.effective_from DESC, sph.id DESC
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(query, (service_id,))
        return [dict(row) for row in cursor.fetchall()]

    def get_price_at(self, service_id: int, at_time: datetime) -> Optional[float]:
        """Cena obowiązująca w danym momencie (point-in-time query).

        Zwraca cenę, której przedział ważności obejmuje `at_time`, lub None
        jeśli usługa nie miała jeszcze ceny w tym momencie.
        """
        query = """
            SELECT price
            FROM service_price_history
            WHERE service_id = %s
              AND effective_from <= %s
              AND (effective_to IS NULL OR effective_to > %s)
            ORDER BY effective_from DESC
            LIMIT 1
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(query, (service_id, at_time, at_time))
        row = cursor.fetchone()
        return float(row['price']) if row else None

    def delete_entry(self, service_id: int, entry_id: int) -> dict:
        """Delete one price-history row while keeping the effective-dated chain valid.

        Behaviour:
          * Row must belong to ``service_id`` → otherwise ``{'status': 'not_found'}``.
          * The only remaining row cannot be deleted → ``{'status': 'last_row'}``
            (a service must always keep at least one — its current — price).
          * Let P = the immediately-previous row (largest ``effective_from`` below
            the target's). The target is DELETED FIRST, then P.effective_to is set
            to the target's effective_to. Deleting first avoids a transient second
            open row that would violate the partial UNIQUE index.
              - If the target was the open (current) row, P.effective_to becomes
                NULL → P is REOPENED as the new current price, and the catalogue
                ``services.price``/``currency`` are synced to P so the live price
                matches. P keeps its original effective_from (its "changed on" date).
              - If the target was a closed row, extending P heals the gap so the
                chain stays contiguous.

        Returns a dict with ``status='ok'`` plus ``was_open``, ``reopened``,
        ``new_price``, ``currency`` and ``old_price``.
        """
        conn = get_db_connection()
        cursor = conn.cursor()

        # 1. Target must exist and belong to this service
        cursor.execute(
            "SELECT id, price, currency, effective_from, effective_to "
            "FROM service_price_history WHERE id = %s AND service_id = %s",
            (entry_id, service_id),
        )
        target = cursor.fetchone()
        if not target:
            return {'status': 'not_found'}

        # 2. Never delete the last remaining row
        cursor.execute(
            "SELECT COUNT(*) AS n FROM service_price_history WHERE service_id = %s",
            (service_id,),
        )
        if cursor.fetchone()['n'] <= 1:
            return {'status': 'last_row'}

        was_open = target['effective_to'] is None

        # 3. Locate the immediately-previous row (read before any write)
        cursor.execute(
            "SELECT id, price, currency FROM service_price_history "
            "WHERE service_id = %s AND effective_from < %s "
            "ORDER BY effective_from DESC, id DESC LIMIT 1",
            (service_id, target['effective_from']),
        )
        prev = cursor.fetchone()

        # 4. Delete the target FIRST (so reopening prev can't collide on the
        #    partial unique index of open rows)
        cursor.execute("DELETE FROM service_price_history WHERE id = %s", (entry_id,))

        reopened = False
        new_price = None
        new_currency = None

        # 5. Extend / reopen the previous row to cover the deleted range
        if prev:
            cursor.execute(
                "UPDATE service_price_history SET effective_to = %s WHERE id = %s",
                (target['effective_to'], prev['id']),
            )
            if was_open:
                reopened = True
                new_price = float(prev['price'])
                new_currency = prev['currency']

        # 6. Sync the catalogue's live price to the reopened row
        if reopened:
            cursor.execute(
                "UPDATE services SET price = %s, currency = %s, "
                "updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                (new_price, new_currency, service_id),
            )

        safe_commit(conn)
        return {
            'status': 'ok',
            'was_open': was_open,
            'reopened': reopened,
            'new_price': new_price,
            'currency': new_currency,
            'old_price': float(target['price']),
        }

    def get_last_change_dates(self, service_ids: list[int]) -> dict[int, datetime]:
        """Batch fetch: {service_id: najnowsze effective_from} dla listy usług.

        Używane przez listę usług, by uniknąć N+1 zapytań. Pomija usługi
        bez historii cen.
        """
        if not service_ids:
            return {}
        query = """
            SELECT service_id, MAX(effective_from) AS last_change
            FROM service_price_history
            WHERE service_id = ANY(%s)
            GROUP BY service_id
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(query, (service_ids,))
        return {row['service_id']: row['last_change'] for row in cursor.fetchall()}
