"""
Repository dla haseł PDF sprzedawców
"""
from typing import Any, List, Optional

from database.models import SellerPdfPassword
from repositories.base_repository import BaseRepository


class SellerPasswordRepository(BaseRepository):
    """Repository dla operacji na hasłach PDF sprzedawców"""

    def __init__(self):
        super().__init__("seller_pdf_passwords")

    def create(self, entry: SellerPdfPassword) -> int:
        """Stwórz nowy wpis hasła PDF"""
        query = """
            INSERT INTO seller_pdf_passwords (
                seller_id, email_sender_pattern, pdf_password, description
            ) VALUES (%s, %s, %s, %s)
        """
        params = (
            entry.seller_id,
            entry.email_sender_pattern,
            entry.pdf_password,
            entry.description,
        )
        return self._execute_insert(query, params)

    def find_by_seller_id(self, seller_id: int) -> Optional[Any]:
        """Znajdź hasło PDF po ID sprzedawcy"""
        query = "SELECT * FROM seller_pdf_passwords WHERE seller_id = %s ORDER BY updated_at DESC LIMIT 1"
        return self._fetch_one(query, (seller_id,))

    def find_by_email_sender(self, email_sender: str) -> Optional[Any]:
        """
        Znajdź hasło PDF pasujące do adresu e-mail nadawcy.
        Obsługuje zarówno dokładne dopasowanie jak i wzorce z % (LIKE).
        """
        if not email_sender:
            return None
        # Try exact match first, then pattern match
        query = """
            SELECT * FROM seller_pdf_passwords
            WHERE email_sender_pattern IS NOT NULL
              AND (
                LOWER(email_sender_pattern) = LOWER(%s)
                OR LOWER(%s) LIKE LOWER(email_sender_pattern)
              )
            ORDER BY
                CASE WHEN LOWER(email_sender_pattern) = LOWER(%s) THEN 0 ELSE 1 END,
                updated_at DESC
            LIMIT 1
        """
        return self._fetch_one(query, (email_sender, email_sender, email_sender))

    def find_password_for_file(self, seller_id: int = None, email_sender: str = None) -> Optional[str]:
        """
        Znajdź hasło PDF dla pliku na podstawie seller_id lub email_sender.
        Zwraca sam string hasła lub None.
        """
        # Priority 1: seller_id lookup
        if seller_id:
            row = self.find_by_seller_id(seller_id)
            if row:
                return row['pdf_password']

        # Priority 2: email sender pattern match
        if email_sender:
            row = self.find_by_email_sender(email_sender)
            if row:
                return row['pdf_password']

        return None

    def get_all(self) -> List[Any]:
        """Pobierz wszystkie wpisy haseł z danymi sprzedawcy"""
        query = """
            SELECT p.*, s.seller_name, s.seller_nip
            FROM seller_pdf_passwords p
            LEFT JOIN sellers s ON p.seller_id = s.id
            ORDER BY COALESCE(s.seller_name, p.email_sender_pattern, 'zzz')
        """
        return self._fetch_all(query)

    def update(self, password_id: int, entry: SellerPdfPassword) -> bool:
        """Zaktualizuj wpis hasła"""
        query = """
            UPDATE seller_pdf_passwords SET
                seller_id = %s,
                email_sender_pattern = %s,
                pdf_password = %s,
                description = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """
        params = (
            entry.seller_id,
            entry.email_sender_pattern,
            entry.pdf_password,
            entry.description,
            password_id,
        )
        cursor = self._execute(query, params)
        return cursor.rowcount > 0

    def delete(self, password_id: int) -> bool:
        """Usuń wpis hasła"""
        query = "DELETE FROM seller_pdf_passwords WHERE id = %s"
        cursor = self._execute(query, (password_id,))
        return cursor.rowcount > 0

    def row_to_model(self, row: Any) -> SellerPdfPassword:
        """Konwertuj Row → SellerPdfPassword"""
        from repositories.db_utils import parse_dt
        return SellerPdfPassword(
            id=row['id'],
            seller_id=row['seller_id'],
            email_sender_pattern=row['email_sender_pattern'],
            pdf_password=row['pdf_password'],
            description=row.get('description'),
            created_at=parse_dt(row['created_at']),
            updated_at=parse_dt(row['updated_at']),
        )
