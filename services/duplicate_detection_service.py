"""
Serwis wykrywania duplikatów faktur

Strategia wykrywania:
- Duplikat = ta sama faktura (numer) od tego samego sprzedawcy (NIP lub nazwa)
- Różni sprzedawcy mogą mieć faktury o tym samym numerze (np. FV/2024/001)
- Priorytet identyfikacji sprzedawcy: NIP > nazwa
"""
from typing import Optional

from database.models import Invoice
from repositories.invoice_repository import InvoiceRepository


class DuplicateDetectionService:
	"""Serwis wykrywania duplikatów"""

	def __init__(self, invoice_repo: InvoiceRepository):
		self.invoice_repo = invoice_repo

	def check_duplicate(self, invoice: Invoice) -> tuple[bool, Optional[dict]]:
		"""
		Sprawdź czy faktura jest duplikatem.

		Ulepszona logika:
		- Szuka faktury z tym samym numerem OD TEGO SAMEGO sprzedawcy
		- Używa NIP jako głównego identyfikatora sprzedawcy
		- Fallback na nazwę sprzedawcy jeśli NIP niedostępny

		Returns:
			Tuple of (is_duplicate: bool, duplicate_info: Optional[dict])
			- is_duplicate: True if duplicate found
			- duplicate_info: Dict with duplicate invoice details if found, None otherwise
		"""
		# Szukaj po numerze faktury + sprzedawcy (NIP lub nazwa)
		existing = self.invoice_repo.find_by_invoice_number_and_seller(
			invoice_number=invoice.invoice_number,
			seller_nip=invoice.seller_nip,
			seller_name=invoice.seller_name
		)

		if existing:
			# Use bracket notation for sqlite3.Row objects
			return (True, {
				'id': existing['id'],
				'invoice_number': existing['invoice_number'],
				'seller_name': existing['seller_name'],
				'seller_nip': existing['seller_nip'],
				'amount': existing['amount']
			})

		return (False, None)

	def check_duplicate_simple(self, invoice: Invoice) -> tuple[bool, Optional[dict]]:
		"""
		Proste sprawdzenie duplikatu - tylko po numerze faktury.
		Używane gdy chcemy sprawdzić czy numer jest unikalny globalnie.

		Returns:
			Tuple of (is_duplicate: bool, duplicate_info: Optional[dict])
		"""
		existing = self.invoice_repo.find_by_invoice_number(invoice.invoice_number)

		if existing:
			return (True, {
				'id': existing['id'],
				'invoice_number': existing['invoice_number'],
				'seller_name': existing['seller_name'],
				'amount': existing['amount']
			})

		return (False, None)
	
	def calculate_similarity(
			self, invoice1: Invoice, invoice2: Invoice
			) -> float:
		"""
		Oblicz podobieństwo dwóch faktur (0-100%)
		Możesz rozbudować tę metodę w przyszłości
		"""
		score = 0.0
		
		# Numer faktury (najważniejsze)
		if invoice1.invoice_number == invoice2.invoice_number:
			score += 50
		
		# Sprzedawca
		if invoice1.seller_name == invoice2.seller_name:
			score += 20
		
		# Kwota
		if abs(invoice1.amount - invoice2.amount) < 0.01:
			score += 20
		
		# Data
		if invoice1.invoice_date == invoice2.invoice_date:
			score += 10
		
		return score