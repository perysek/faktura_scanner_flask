"""
Główny serwis OCR - orchestruje PDF → text → data
"""
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime

from utils.pdf_processor import PDFProcessor
from utils.text_extractor import TextExtractor
from database.models import Invoice


class OCRService:
	"""Serwis OCR i ekstrakcji danych z faktur"""

	def __init__(self):
		self.pdf_processor = PDFProcessor()
		self.text_extractor = TextExtractor()

	def process_pdf(self, pdf_path: str) -> Dict:
		"""
		Przetworz PDF faktury i zwróć słownik z danymi

		Args:
			pdf_path: Ścieżka do PDF

		Returns:
			Dictionary z wyekstraktowanymi danymi
		"""
		# 1. PDF → tekst (OCR)
		raw_text, confidence = self.pdf_processor.extract_text_from_pdf(pdf_path)

		# 2. Tekst → structured data
		extracted_data = self.text_extractor.extract_invoice_data(raw_text)

		# 3. Konwersja dat string → date (zwracamy jako stringi dla API)
		result = {
			'invoice_number': extracted_data.get('invoice_number', ''),
			'seller_name': extracted_data.get('seller_name', ''),
			'seller_nip': extracted_data.get('seller_nip', ''),
			'seller_address': extracted_data.get('seller_address', ''),
			'issue_date': extracted_data.get('invoice_date'),
			'sale_date': extracted_data.get('sale_date'),
			'payment_due_date': extracted_data.get('payment_due_date'),
			'payment_method': extracted_data.get('payment_method', ''),
			'bank_account': extracted_data.get('bank_account', ''),
			'net_amount': extracted_data.get('net_amount', 0.0),
			'vat_amount': extracted_data.get('vat_amount', 0.0),
			'total_amount': extracted_data.get('amount', 0.0),
			'currency': extracted_data.get('currency', 'PLN'),
			'ocr_confidence': confidence,
			'raw_text': raw_text
		}

		return result

	def process_invoice_pdf(self, pdf_path: str, progress_callback=None) -> \
	tuple[Invoice, str]:
		"""
		Przetworz PDF faktury

		Args:
			pdf_path: Ścieżka do PDF
			progress_callback: Funkcja callback(progress_pct, message)

		Returns:
			(Invoice object, raw_text)
		"""
		if progress_callback:
			progress_callback(10, "Konwersja PDF...")
		
		# 1. PDF → tekst (OCR)
		raw_text, confidence = self.pdf_processor.extract_text_from_pdf(
			pdf_path
			)
		
		if progress_callback:
			progress_callback(50, "Ekstrakcja danych...")
		
		# 2. Tekst → structured data
		extracted_data = self.text_extractor.extract_invoice_data(raw_text)
		
		if progress_callback:
			progress_callback(80, "Tworzenie obiektu faktury...")
		
		# 3. Konwersja dat string → date
		invoice_date = None
		if extracted_data['invoice_date']:
			try:
				invoice_date = datetime.strptime(
					extracted_data['invoice_date'], '%Y-%m-%d'
					).date()
			except:
				pass
		
		payment_due_date = None
		payment_term = None
		if extracted_data['payment_due_date']:
			# Check if it's a special payment term like 'POBRANIE'
			if extracted_data['payment_due_date'] == 'POBRANIE':
				payment_term = 'POBRANIE'
			else:
				# Try to parse as date
				try:
					payment_due_date = datetime.strptime(
						extracted_data['payment_due_date'], '%Y-%m-%d'
						).date()
				except:
					pass

		# 3.5. Walidacja dat - sprawdź czy termin płatności jest późniejszy niż data faktury
		if invoice_date and payment_due_date:
			if payment_due_date <= invoice_date:
				print(f"  ⚠️  OSTRZEŻENIE: Termin płatności ({payment_due_date}) "
				      f"nie jest późniejszy niż data faktury ({invoice_date})!")
				print(f"  ⚠️  Możliwy błąd w OCR - sprawdź daty ręcznie!")

		# 4. Stwórz Invoice object
		invoice = Invoice(
			seller_name=extracted_data['seller_name'] or "Nie wykryto",
			invoice_number=extracted_data['invoice_number'] or "BRAK",
			seller_nip=extracted_data['seller_nip'],
			invoice_date=invoice_date or datetime.now().date(),
			bank_account=extracted_data['bank_account'],
			amount=extracted_data['amount'] or 0.0,
			currency=extracted_data['currency'],
			payment_due_date=payment_due_date,
			payment_term=payment_term,
			pdf_path=pdf_path,
			ocr_confidence=confidence
			)
		
		if progress_callback:
			progress_callback(100, "Gotowe!")
		
		return invoice, raw_text