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