"""
Repository dla sprzedawców
"""
from typing import Any, List, Optional

from database.models import Seller
from repositories.base_repository import BaseRepository
from repositories.db_utils import parse_dt


class SellerRepository(BaseRepository):
    """Repository dla operacji na sprzedawcach"""
    
    def __init__(self):
        super().__init__("sellers")
    
    def create(self, seller: Seller) -> int:
        """
        Stwórz nowego sprzedawcę
        Returns: ID nowego sprzedawcy
        """
        query = """
            INSERT INTO sellers (
                seller_nip, seller_name, address, invoice_count
            ) VALUES (%s, %s, %s, %s)
        """
        params = (
            seller.seller_nip,
            seller.seller_name,
            seller.address,
            seller.invoice_count
        )
        
        return self._execute_insert(query, params)
    
    def update(self, seller_id: int, seller: Seller) -> bool:
        """Zaktualizuj sprzedawcę"""
        query = """
            UPDATE sellers SET
                seller_nip = %s,
                seller_name = %s,
                address = %s,
                invoice_count = %s,
                last_updated = CURRENT_TIMESTAMP
            WHERE id = %s
        """
        params = (
            seller.seller_nip,
            seller.seller_name,
            seller.address,
            seller.invoice_count,
            seller_id
        )
        
        cursor = self._execute(query, params)
        return cursor.rowcount > 0
    
    def find_by_nip(self, nip: str) -> Optional[Any]:
        """Znajdź sprzedawcę po numerze NIP"""
        query = "SELECT * FROM sellers WHERE seller_nip = %s"
        return self._fetch_one(query, (nip,))
    
    def find_by_name(self, name: str) -> List[Any]:
        """Wyszukaj sprzedawców po nazwie lub NIP (fuzzy matching)"""
        query = """
            SELECT
                s.*,
                COUNT(i.id) as actual_invoice_count,
                SUM(CASE WHEN i.status = 'Opłacona' THEN i.amount ELSE 0 END) as total_paid,
                SUM(CASE WHEN i.status IN ('Nieopłacona', 'Przeterminowana') THEN i.amount ELSE 0 END) as total_unpaid
            FROM sellers s
            LEFT JOIN invoices i ON (
                i.seller_id = s.id
                OR (
                    i.seller_id IS NULL
                    AND s.seller_nip IS NOT NULL
                    AND regexp_replace(COALESCE(i.seller_nip, ''), '[^0-9]', '', 'g') = s.seller_nip
                )
            )
            WHERE s.seller_name ILIKE %s OR s.seller_nip ILIKE %s
            GROUP BY s.id
            ORDER BY s.seller_name
        """
        search_pattern = f"%{name}%"
        return self._fetch_all(query, (search_pattern, search_pattern))
    
    def get_or_create(self, nip: str, name: str, address: str = None) -> tuple[int, bool]:
        """
        Pobierz sprzedawcę lub stwórz nowego
        
        Returns:
            Tuple of (seller_id: int, created: bool)
        """
        # Sprawdź czy istnieje
        existing = self.find_by_nip(nip)
        if existing:
            return existing['id'], False
        
        # Stwórz nowego
        seller = Seller(
            seller_nip=nip,
            seller_name=name,
            address=address,
            invoice_count=0
        )
        seller_id = self.create(seller)
        return seller_id, True
    
    def increment_invoice_count(self, seller_id: int) -> bool:
        """Zwiększ licznik faktur dla sprzedawcy"""
        query = """
            UPDATE sellers 
            SET invoice_count = invoice_count + 1,
                last_updated = CURRENT_TIMESTAMP
            WHERE id = %s
        """
        cursor = self._execute(query, (seller_id,))
        return cursor.rowcount > 0
    
    def decrement_invoice_count(self, seller_id: int) -> bool:
        """Zmniejsz licznik faktur dla sprzedawcy"""
        query = """
            UPDATE sellers 
            SET invoice_count = CASE 
                WHEN invoice_count > 0 THEN invoice_count - 1 
                ELSE 0 
            END,
                last_updated = CURRENT_TIMESTAMP
            WHERE id = %s
        """
        cursor = self._execute(query, (seller_id,))
        return cursor.rowcount > 0
    
    def get_top_sellers(self, limit: int = 5) -> List[Any]:
        """
        Pobierz najczęstszych sprzedawców na podstawie danych z faktur.
        Liczy wszystkie faktury, nawet te niepowiązane z tabelą sellers.
        """
        query = """
            SELECT 
                seller_name, 
                seller_nip, 
                COUNT(*) as actual_invoice_count, 
                SUM(amount) as total_amount,
                MAX(seller_id) as id
            FROM invoices
            WHERE seller_name IS NOT NULL AND seller_name != ''
            GROUP BY seller_name, seller_nip
            ORDER BY actual_invoice_count DESC, total_amount DESC
            LIMIT %s
        """
        return self._fetch_all(query, (limit,))

    def get_all_with_stats(self) -> List[Any]:
        """Pobierz wszystkich sprzedawców wraz z statystykami"""
        query = """
            SELECT
                s.*,
                COUNT(i.id) as actual_invoice_count,
                SUM(CASE WHEN i.status = 'Opłacona' THEN i.amount ELSE 0 END) as total_paid,
                SUM(CASE WHEN i.status IN ('Nieopłacona', 'Przeterminowana') THEN i.amount ELSE 0 END) as total_unpaid
            FROM sellers s
            LEFT JOIN invoices i ON (
                i.seller_id = s.id
                OR (
                    i.seller_id IS NULL
                    AND s.seller_nip IS NOT NULL
                    AND regexp_replace(COALESCE(i.seller_nip, ''), '[^0-9]', '', 'g') = s.seller_nip
                )
            )
            GROUP BY s.id
            ORDER BY s.seller_name
        """
        return self._fetch_all(query)
    
    def update_name(self, seller_id: int, new_name: str) -> bool:
        """Zaktualizuj tylko nazwę sprzedawcy"""
        query = """
            UPDATE sellers
            SET seller_name = %s,
                last_updated = CURRENT_TIMESTAMP
            WHERE id = %s
        """
        cursor = self._execute(query, (new_name, seller_id))
        return cursor.rowcount > 0
    
    def update_address(self, seller_id: int, new_address: str) -> bool:
        """Zaktualizuj tylko adres sprzedawcy"""
        query = """
            UPDATE sellers
            SET address = %s,
                last_updated = CURRENT_TIMESTAMP
            WHERE id = %s
        """
        cursor = self._execute(query, (new_address, seller_id))
        return cursor.rowcount > 0
    
    def sync_invoice_counts(self) -> int:
        """
        Zsynchronizuj liczniki faktur ze stanem faktycznym w bazie.
        Przelicza invoice_count dla wszystkich sprzedawców na podstawie aktualnej liczby faktur.

        Returns:
            Liczba zaktualizowanych sprzedawców
        """
        query = """
            UPDATE sellers
            SET invoice_count = (
                SELECT COUNT(*)
                FROM invoices
                WHERE invoices.seller_id = sellers.id
            ),
            last_updated = CURRENT_TIMESTAMP
        """
        cursor = self._execute(query)
        return cursor.rowcount

    def row_to_seller(self, row: Any) -> Seller:
        """Konwertuj Row → Seller object"""
        from datetime import datetime

        return Seller(
            id=row["id"],
            seller_nip=row["seller_nip"],
            seller_name=row["seller_name"],
            address=row["address"] if "address" in row.keys() else None,
            first_seen=parse_dt(row["first_seen"]),
            last_updated=parse_dt(row["last_updated"]),
            invoice_count=row["invoice_count"] if "invoice_count" in row.keys() else 0
        )
