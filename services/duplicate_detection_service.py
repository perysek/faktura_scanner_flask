"""
Serwis wykrywania duplikatów faktur
"""
from typing import Optional
from repositories.invoice_repository import InvoiceRepository
from database.models import Invoice


class DuplicateDetectionService:
	"""Serwis wykrywania duplikatów"""
	
	def __init__(self, invoice_repo: InvoiceRepository):
		self.invoice_repo = invoice_repo
	
	def check_duplicate(self, invoice: Invoice) -> Optional[int]:
		"""
		Sprawdź czy faktura jest duplikatem

		Returns:
			ID istniejącej faktury jeśli duplikat, None jeśli nie
		"""
		# Szukaj po numerze faktury
		existing = self.invoice_repo.find_by_invoice_number(
			invoice.invoice_number
			)
		
		if existing:
			return existing['id']
		
		return None
	
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