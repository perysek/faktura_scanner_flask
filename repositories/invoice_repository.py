"""
Repository dla faktur
"""
import sqlite3
from datetime import date, datetime
from typing import List, Optional

from database.models import Invoice
from repositories.base_repository import BaseRepository


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
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
		
		cursor = self._execute(query, params)
		return cursor.lastrowid
	
	def update(self, invoice_id: int, invoice: Invoice, seller_id: int = None) -> bool:
		"""Zaktualizuj fakturę"""
		if seller_id is not None:
			query = """
				UPDATE invoices SET
					seller_name = ?,
					seller_nip = ?,
					invoice_number = ?,
					invoice_date = ?,
					bank_account = ?,
					amount = ?,
					currency = ?,
					payment_due_date = ?,
					payment_term = ?,
					status = ?,
					pdf_path = ?,
					ocr_confidence = ?,
					is_duplicate = ?,
					seller_id = ?,
					updated_at = CURRENT_TIMESTAMP
				WHERE id = ?
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
					seller_name = ?,
					seller_nip = ?,
					invoice_number = ?,
					invoice_date = ?,
					bank_account = ?,
					amount = ?,
					currency = ?,
					payment_due_date = ?,
					payment_term = ?,
					status = ?,
					pdf_path = ?,
					ocr_confidence = ?,
					is_duplicate = ?,
					updated_at = CURRENT_TIMESTAMP
				WHERE id = ?
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
		sqlite3.Row]:
		"""Znajdź fakturę po numerze"""
		query = "SELECT * FROM invoices WHERE invoice_number = ?"
		return self._fetch_one(query, (invoice_number,))
	
	def search(self, search_term: str) -> List[sqlite3.Row]:
		"""Wyszukaj faktury (seller, numer, NIP)"""
		query = """
            SELECT * FROM invoices
            WHERE seller_name LIKE ?
               OR invoice_number LIKE ?
               OR seller_nip LIKE ?
            ORDER BY invoice_date DESC
        """
		term = f"%{search_term}%"
		return self._fetch_all(query, (term, term, term))
	
	def get_by_date_range(self, start_date: date, end_date: date) -> List[
		sqlite3.Row]:
		"""Pobierz faktury z zakresu dat"""
		query = """
            SELECT * FROM invoices
            WHERE invoice_date BETWEEN ? AND ?
            ORDER BY invoice_date DESC
        """
		return self._fetch_all(
			query, (start_date.isoformat(), end_date.isoformat())
			)
	
	def get_by_seller(self, seller_id: int) -> List[sqlite3.Row]:
		"""Pobierz wszystkie faktury dla danego sprzedawcy"""
		query = """
            SELECT * FROM invoices
            WHERE seller_id = ?
            ORDER BY invoice_date DESC
        """
		return self._fetch_all(query, (seller_id,))
	
	def bulk_update_seller(self, old_seller_id: int, new_seller_id: int) -> int:
		"""Zmień seller_id dla wszystkich faktur"""
		query = """
            UPDATE invoices
            SET seller_id = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE seller_id = ?
        """
		cursor = self._execute(query, (new_seller_id, old_seller_id))
		return cursor.rowcount
	
	def get_recent(self, limit: int = 5) -> List[sqlite3.Row]:
		"""Pobierz ostatnio dodane faktury"""
		query = """
            SELECT * FROM invoices
            ORDER BY created_at DESC
            LIMIT ?
        """
		return self._fetch_all(query, (limit,))

	def get_upcoming_payments(self, limit: int = 5) -> List[sqlite3.Row]:
		"""Pobierz faktury z najbliższymi terminami płatności (nieopłacone, tylko przyszłe)"""
		query = """
            SELECT * FROM invoices
            WHERE status = 'Nieopłacona'
              AND payment_due_date IS NOT NULL
              AND payment_due_date >= date('now')
            ORDER BY payment_due_date ASC
            LIMIT ?
        """
		return self._fetch_all(query, (limit,))

	def get_overdue_payments(self, limit: int = 5) -> List[sqlite3.Row]:
		"""Pobierz przeterminowane faktury (nieopłacone, termin < dzisiaj)"""
		query = """
            SELECT * FROM invoices
            WHERE status = 'Nieopłacona'
              AND payment_due_date IS NOT NULL
              AND payment_due_date < date('now')
            ORDER BY payment_due_date ASC
            LIMIT ?
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
	
	def row_to_invoice(self, row: sqlite3.Row) -> Invoice:
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
			invoice_date=datetime.fromisoformat(row["invoice_date"]).date() if
			row["invoice_date"] else None,
			bank_account=row["bank_account"],
			amount=row["amount"],
			currency=row["currency"],
			payment_due_date=datetime.fromisoformat(
				row["payment_due_date"]
				).date() if row["payment_due_date"] else None,
			payment_term=payment_term,
			status=status,
			pdf_path=row["pdf_path"],
			ocr_confidence=row["ocr_confidence"],
			is_duplicate=bool(row["is_duplicate"]),
			created_at=datetime.fromisoformat(row["created_at"]) if row[
				"created_at"] else None,
			updated_at=datetime.fromisoformat(row["updated_at"]) if row[
				"updated_at"] else None
			)