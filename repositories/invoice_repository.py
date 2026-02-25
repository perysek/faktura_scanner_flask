"""
Repository dla faktur
"""
from datetime import date, datetime
from typing import Any, List, Optional

from database.models import Invoice
from repositories.base_repository import BaseRepository
from repositories.db_utils import parse_dt, parse_date


class InvoiceRepository(BaseRepository):
	"""Repository dla operacji na fakturach"""
	
	def __init__(self):
		super().__init__("invoices")
	
	def create(self, invoice: Invoice, seller_id: int = None) -> int:
		"""
		Stwórz nową fakturę
		Args:
			seller_id: Optional seller ID to link invoice to seller
		Returns: ID nowej faktury
		"""
		query = """
            INSERT INTO invoices (
                seller_name, seller_nip, invoice_number, invoice_date,
                bank_account, amount, currency, payment_due_date, payment_term, status,
                pdf_path, ocr_confidence, is_duplicate, seller_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
		params = (
			invoice.seller_name,
			invoice.seller_nip,
			invoice.invoice_number,
			invoice.invoice_date.isoformat() if invoice.invoice_date else None,
			invoice.bank_account,
			invoice.amount,
			invoice.currency,
			invoice.payment_due_date.isoformat() if invoice.payment_due_date else None,
			invoice.payment_term,
			invoice.status,
			invoice.pdf_path,
			invoice.ocr_confidence,
			invoice.is_duplicate,
			seller_id
			)
		
		return self._execute_insert(query, params)
	
	def update(self, invoice_id: int, invoice: Invoice, seller_id: int = None) -> bool:
		"""Zaktualizuj fakturę"""
		if seller_id is not None:
			query = """
				UPDATE invoices SET
					seller_name = %s,
					seller_nip = %s,
					invoice_number = %s,
					invoice_date = %s,
					bank_account = %s,
					amount = %s,
					currency = %s,
					payment_due_date = %s,
					payment_term = %s,
					status = %s,
					pdf_path = %s,
					ocr_confidence = %s,
					is_duplicate = %s,
					seller_id = %s,
					updated_at = CURRENT_TIMESTAMP
				WHERE id = %s
			"""
			params = (
				invoice.seller_name,
				invoice.seller_nip,
				invoice.invoice_number,
				invoice.invoice_date.isoformat() if invoice.invoice_date else None,
				invoice.bank_account,
				invoice.amount,
				invoice.currency,
				invoice.payment_due_date.isoformat() if invoice.payment_due_date else None,
				invoice.payment_term,
				invoice.status,
				invoice.pdf_path,
				invoice.ocr_confidence,
				invoice.is_duplicate,
				seller_id,
				invoice_id
			)
		else:
			query = """
				UPDATE invoices SET
					seller_name = %s,
					seller_nip = %s,
					invoice_number = %s,
					invoice_date = %s,
					bank_account = %s,
					amount = %s,
					currency = %s,
					payment_due_date = %s,
					payment_term = %s,
					status = %s,
					pdf_path = %s,
					ocr_confidence = %s,
					is_duplicate = %s,
					updated_at = CURRENT_TIMESTAMP
				WHERE id = %s
			"""
			params = (
				invoice.seller_name,
				invoice.seller_nip,
				invoice.invoice_number,
				invoice.invoice_date.isoformat() if invoice.invoice_date else None,
				invoice.bank_account,
				invoice.amount,
				invoice.currency,
				invoice.payment_due_date.isoformat() if invoice.payment_due_date else None,
				invoice.payment_term,
				invoice.status,
				invoice.pdf_path,
				invoice.ocr_confidence,
				invoice.is_duplicate,
				invoice_id
			)
		
		cursor = self._execute(query, params)
		return cursor.rowcount > 0
	
	def find_by_invoice_number(self, invoice_number: str) -> Optional[
		Any]:
		"""Znajdź fakturę po numerze"""
		query = "SELECT * FROM invoices WHERE invoice_number = %s"
		return self._fetch_one(query, (invoice_number,))

	def find_by_invoice_number_and_seller(
			self,
			invoice_number: str,
			seller_nip: str = None,
			seller_name: str = None
	) -> Optional[Any]:
		"""
		Znajdź fakturę po numerze i sprzedawcy (NIP lub nazwa).

		Strategia:
		1. Jeśli podano seller_nip: szukaj po (invoice_number, seller_nip)
		2. Jeśli brak NIP ale jest nazwa: szukaj po (invoice_number, seller_name)
		3. Jeśli brak obu: szukaj tylko po invoice_number (fallback)

		Args:
			invoice_number: Numer faktury
			seller_nip: NIP sprzedawcy (opcjonalny)
			seller_name: Nazwa sprzedawcy (opcjonalny, używana gdy brak NIP)

		Returns:
			Row jeśli znaleziono duplikat, None jeśli brak
		"""
		if seller_nip:
			# Najbardziej precyzyjne wyszukiwanie: numer + NIP
			query = """
				SELECT * FROM invoices
				WHERE invoice_number = %s AND seller_nip = %s
			"""
			return self._fetch_one(query, (invoice_number, seller_nip))
		elif seller_name:
			# Fallback: numer + nazwa (mniej precyzyjne, bo nazwy mogą się różnić)
			query = """
				SELECT * FROM invoices
				WHERE invoice_number = %s AND seller_name = %s
			"""
			return self._fetch_one(query, (invoice_number, seller_name))
		else:
			# Ostateczny fallback: tylko numer (stare zachowanie)
			return self.find_by_invoice_number(invoice_number)
	
	def search(self, search_term: str) -> List[Any]:
		"""Wyszukaj faktury (seller, numer, NIP)"""
		query = """
            SELECT * FROM invoices
            WHERE seller_name LIKE %s
               OR invoice_number LIKE %s
               OR seller_nip LIKE %s
            ORDER BY invoice_date DESC
        """
		term = f"%{search_term}%"
		return self._fetch_all(query, (term, term, term))
	
	def get_by_date_range(self, start_date: date, end_date: date) -> List[
		Any]:
		"""Pobierz faktury z zakresu dat"""
		query = """
            SELECT * FROM invoices
            WHERE invoice_date BETWEEN %s AND %s
            ORDER BY invoice_date DESC
        """
		return self._fetch_all(
			query, (start_date.isoformat(), end_date.isoformat())
			)
	
	def get_by_seller(self, seller_id: int) -> List[Any]:
		"""Pobierz wszystkie faktury dla danego sprzedawcy"""
		query = """
            SELECT * FROM invoices
            WHERE seller_id = %s
            ORDER BY invoice_date DESC
        """
		return self._fetch_all(query, (seller_id,))
	
	def bulk_update_seller(self, old_seller_id: int, new_seller_id: int) -> int:
		"""Zmień seller_id dla wszystkich faktur"""
		query = """
            UPDATE invoices
            SET seller_id = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE seller_id = %s
        """
		cursor = self._execute(query, (new_seller_id, old_seller_id))
		return cursor.rowcount
	
	def get_recent(self, limit: int = 5) -> List[Any]:
		"""Pobierz ostatnio dodane faktury"""
		query = """
            SELECT * FROM invoices
            ORDER BY created_at DESC
            LIMIT %s
        """
		return self._fetch_all(query, (limit,))

	def get_upcoming_payments(self, limit: int = 5) -> List[Any]:
		"""Pobierz faktury z najbliższymi terminami płatności (nieopłacone, tylko przyszłe)"""
		query = """
            SELECT * FROM invoices
            WHERE status = 'Nieopłacona'
              AND payment_due_date IS NOT NULL
              AND payment_due_date >= date('now')
            ORDER BY payment_due_date ASC
            LIMIT %s
        """
		return self._fetch_all(query, (limit,))

	def get_overdue_payments(self, limit: int = 5) -> List[Any]:
		"""Pobierz przeterminowane faktury (nieopłacone, termin < dzisiaj)"""
		query = """
            SELECT * FROM invoices
            WHERE status = 'Nieopłacona'
              AND payment_due_date IS NOT NULL
              AND payment_due_date < date('now')
            ORDER BY payment_due_date ASC
            LIMIT %s
        """
		return self._fetch_all(query, (limit,))

	def get_statistics(self) -> dict:
		"""Pobierz statystyki faktur z podziałem na status płatności"""
		# Podstawowe statystyki
		query_basic = """
            SELECT
                COUNT(*) as total_count,
                COUNT(CASE WHEN status = 'Opłacona' THEN 1 END) as paid_count,
                COUNT(CASE WHEN status = 'Nieopłacona' THEN 1 END) as unpaid_count
            FROM invoices
        """
		basic_stats = self._fetch_one(query_basic)

		# Statystyki kwot po walutach i statusach
		query_amounts = """
            SELECT
                currency,
                status,
                CASE
                    WHEN status = 'Nieopłacona' AND payment_due_date < date('now') THEN 'overdue'
                    WHEN status = 'Nieopłacona' THEN 'unpaid'
                    WHEN status = 'Opłacona' THEN 'paid'
                    ELSE 'unpaid'
                END as payment_status,
                SUM(amount) as total_amount,
                COUNT(*) as count
            FROM invoices
            GROUP BY currency, payment_status
        """
		amount_results = self._fetch_all(query_amounts)

		stats = {
			"total_invoices": basic_stats["total_count"],
			"paid_invoices": basic_stats["paid_count"],
			"unpaid_invoices": basic_stats["unpaid_count"],
			"by_currency": {},
			"totals": {
				"total_amount": 0.0,
				"total_unpaid": 0.0,
				"total_vat": 0.0
			}
		}

		# Organizuj dane po walutach
		for row in amount_results:
			currency = row["currency"] or "PLN"
			payment_status = row["payment_status"]
			amount = row["total_amount"] or 0.0

			if currency not in stats["by_currency"]:
				stats["by_currency"][currency] = {
					"paid": 0.0,
					"unpaid": 0.0,
					"overdue": 0.0,
					"total": 0.0
				}

			# Accumulate properly
			stats["by_currency"][currency][payment_status] += amount
			stats["by_currency"][currency]["total"] += amount

		# Oblicz sumy globalne (dla walut PLN - główna waluta)
		if "PLN" in stats["by_currency"]:
			pln_data = stats["by_currency"]["PLN"]
			stats["totals"]["total_amount"] = pln_data["total"]
			stats["totals"]["total_unpaid"] = pln_data["unpaid"] + pln_data["overdue"]
			# VAT z kwoty brutto: amount * 23 / 123
			stats["totals"]["total_vat"] = pln_data["total"] * 23 / 123
		elif stats["by_currency"]:
			# Fallback: if no PLN, take the first available currency for totals
			# This prevents showing 0.00 when there is data
			first_curr = list(stats["by_currency"].keys())[0]
			first_data = stats["by_currency"][first_curr]
			stats["totals"]["total_amount"] = first_data["total"]
			stats["totals"]["total_unpaid"] = first_data["unpaid"] + first_data["overdue"]
			stats["totals"]["total_vat"] = first_data["total"] * 23 / 123

		return stats
	
	def row_to_invoice(self, row: Any) -> Invoice:
		"""Konwertuj Row → Invoice object"""
		# Safely get payment_term (may not exist in older databases)
		payment_term = None
		try:
			payment_term = row["payment_term"]
		except (KeyError, IndexError):
			pass

		# Safely get status (may not exist in older databases)
		status = "Nieopłacona"
		try:
			status = row["status"] or "Nieopłacona"
		except (KeyError, IndexError):
			pass

		return Invoice(
			id=row["id"],
			seller_name=row["seller_name"],
			seller_nip=row["seller_nip"],
			invoice_number=row["invoice_number"],
			invoice_date=parse_date(row["invoice_date"]),
			bank_account=row["bank_account"],
			amount=row["amount"],
			currency=row["currency"],
			payment_due_date=parse_date(row["payment_due_date"]),
			payment_term=payment_term,
			status=status,
			pdf_path=row["pdf_path"],
			ocr_confidence=row["ocr_confidence"],
			is_duplicate=bool(row["is_duplicate"]),
			created_at=parse_dt(row["created_at"]),
			updated_at=parse_dt(row["updated_at"])
			)