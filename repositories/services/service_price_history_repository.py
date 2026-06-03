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
