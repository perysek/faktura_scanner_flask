"""
Serwis walidacji danych faktur
"""
from typing import List, Dict
from database.models import Invoice
from utils.validators import NIPValidator, IBANValidator


class ValidationService:
	"""Serwis walidacji danych"""
	
	def __init__(self):
		self.nip_validator = NIPValidator()
		self.iban_validator = IBANValidator()
	
	def validate_invoice(self, invoice: Invoice) -> Dict[str, List[str]]:
		"""
		Waliduj fakturę

		Returns:
			Dict z ostrzeżeniami i błędami:
			{
				'errors': ['Brak numeru faktury', ...],
				'warnings': ['NIP niepoprawny', ...]
			}
		"""
		errors = []
		warnings = []
		
		# Wymagane pola
		if not invoice.seller_name or invoice.seller_name == "Nie wykryto":
			errors.append("Brak nazwy sprzedawcy")
		
		if not invoice.invoice_number or invoice.invoice_number == "BRAK":
			errors.append("Brak numeru faktury")
		
		if not invoice.invoice_date:
			errors.append("Brak daty faktury")
		
		if invoice.amount <= 0:
			errors.append("Nieprawidłowa kwota")
		
		# Walidacja NIP
		if invoice.seller_nip:
			if not self.nip_validator.validate(invoice.seller_nip):
				warnings.append(f"NIP niepoprawny: {invoice.seller_nip}")
		else:
			warnings.append("Brak numeru NIP")
		
		# Walidacja IBAN
		if invoice.bank_account:
			if not self.iban_validator.validate(invoice.bank_account):
				warnings.append(
					f"Numer konta niepoprawny: {invoice.bank_account}"
					)
		else:
			warnings.append("Brak numeru konta")
		
		# OCR confidence
		if invoice.ocr_confidence and invoice.ocr_confidence < 50:
			warnings.append(f"Niska pewność OCR: {invoice.ocr_confidence:.1f}%")
		
		return {
			'errors': errors,
			'warnings': warnings
			}
	
	def is_valid(self, invoice: Invoice) -> bool:
		"""Sprawdź czy faktura jest poprawna (brak errors)"""
		result = self.validate_invoice(invoice)
		return len(result['errors']) == 0