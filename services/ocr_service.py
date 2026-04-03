"""
Główny serwis OCR - orchestruje PDF → text → data
Supports:
- Hybrid processing (direct text extraction for text-based PDFs, OCR for scans)
- Retry logic with different preprocessing profiles when extraction quality is low
"""
import logging
from datetime import datetime
from decimal import Decimal
from typing import Dict, Tuple


from exceptions import AppError


class OCRExtractionError(AppError):
	"""Raised when OCR extraction fails completely after all retry attempts."""
	status_code = 422


class PDFPasswordRequired(Exception):
	"""Raised when a PDF is encrypted and no password (or wrong password) is available."""
	pass

from config.settings import (
	OCR_RETRY_ENABLED, OCR_MAX_RETRIES, OCR_MISSING_FIELDS_THRESHOLD,
	OCR_RETRY_PROFILE_ORDER
	)
from database.models import Invoice
from utils.pdf_processor import PDFProcessor
from utils.text_extractor import TextExtractor

logger = logging.getLogger(__name__)


class OCRService:
	"""Serwis OCR i ekstrakcji danych z faktur

	Features:
	- Hybrid processing: direct text extraction for text-based PDFs
	- OCR with preprocessing for scanned documents
	- Retry logic with different preprocessing profiles
	"""

	def __init__(self):
		self.pdf_processor = PDFProcessor()
		self.text_extractor = TextExtractor()
		self.retry_enabled = OCR_RETRY_ENABLED
		self.max_retries = OCR_MAX_RETRIES
		self.missing_threshold = OCR_MISSING_FIELDS_THRESHOLD
		self.retry_profiles = OCR_RETRY_PROFILE_ORDER

	def process_pdf(self, file_path: str, password: str = None) -> Dict:
		"""
		Przetworz PDF lub obraz faktury i zwróć słownik z danymi.
		Uses smart/hybrid processing and retry logic if enabled.

		Args:
			file_path: Ścieżka do PDF lub obrazu (JPG, PNG, TIFF, BMP)
			password: Optional password for encrypted PDFs

		Returns:
			Dictionary z wyekstraktowanymi danymi

		Raises:
			PDFPasswordRequired: If PDF is encrypted and no/wrong password provided
		"""
		# Use retry-enabled processing if enabled, otherwise use smart processing
		if self.retry_enabled:
			# P3-3: process_with_retry returns pre-extracted data to avoid duplicate extraction
			raw_text, confidence, profile_used, extracted_data = self.process_with_retry(file_path, password=password)
			logger.info(f"[OCR] Final result using profile '{profile_used}'")
		else:
			# Use smart processing (hybrid: direct extraction or OCR based on PDF type)
			raw_text, confidence = self.pdf_processor.process_file_smart(file_path)
			profile_used = 'smart'
			extracted_data = None

		logger.debug(f"[OCR RAW TEXT] First 2000 chars:\n{raw_text[:2000]}")

		# 2. Tekst → structured data (skip if already extracted during retry)
		if extracted_data is None:
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
			'raw_text': raw_text,
			'processing_profile': profile_used,
		}

		return result

	def process_with_retry(self, file_path: str, password: str = None) -> Tuple[str, float, str, Dict]:
		"""
		Process file with retry logic using different preprocessing profiles.
		Retries OCR with different profiles when too many fields are missing.
		P3-3: Returns extracted_data to avoid duplicate extraction in process_pdf.

		Args:
			file_path: Path to PDF or image file
			password: Optional password for encrypted PDFs

		Returns:
			Tuple[str, float, str, Dict]: (extracted_text, confidence, profile_name_used, extracted_data)

		Raises:
			PDFPasswordRequired: If PDF is encrypted and no/wrong password provided
		"""
		# First, try smart processing (direct extraction for text-based PDFs)
		pdf_type = self.pdf_processor.detect_pdf_type(file_path) \
			if not self.pdf_processor.is_image_file(file_path) else 'image'

		# Handle encrypted PDFs
		if pdf_type == PDFProcessor.PDF_TYPE_ENCRYPTED:
			if not password:
				logger.warning(f"[Retry] Encrypted PDF detected, no password available")
				raise PDFPasswordRequired(
					"Plik PDF jest zabezpieczony hasłem. "
					"Dodaj hasło dla tego sprzedawcy w ustawieniach."
				)
			# Try to unlock and extract with password
			logger.info("[Retry] Encrypted PDF detected, attempting unlock with password")
			try:
				raw_text, confidence = self.pdf_processor.extract_text_direct(file_path, password=password)
				extracted_data = self.text_extractor.extract_invoice_data(raw_text)
				return raw_text, confidence, 'password_unlock', extracted_data
			except ValueError as e:
				# Wrong password
				raise PDFPasswordRequired(str(e))
			except Exception:
				# Unlocked but extraction failed — try OCR with password
				logger.info("[Retry] Direct extraction failed after unlock, trying OCR")
				raw_text, confidence = self.pdf_processor.extract_text_from_pdf_with_password(file_path, password)
				extracted_data = self.text_extractor.extract_invoice_data(raw_text)
				return raw_text, confidence, 'password_ocr', extracted_data

		if pdf_type == PDFProcessor.PDF_TYPE_TEXT:
			# Text-based PDF - use direct extraction, no retry needed
			logger.info("[Retry] Text-based PDF detected, using direct extraction")
			raw_text, confidence = self.pdf_processor.extract_text_direct(file_path)
			extracted_data = self.text_extractor.extract_invoice_data(raw_text)
			return raw_text, confidence, 'direct_extraction', extracted_data

		# For image-based/mixed PDFs, use OCR with retry logic
		best_result = None
		best_missing_count = float('inf')
		profiles_to_try = ['default'] + list(self.retry_profiles)

		for attempt, profile in enumerate(profiles_to_try):
			if attempt > self.max_retries:
				logger.info(f"[Retry] Max retries ({self.max_retries}) reached")
				break

			logger.info(f"[Retry] Attempt {attempt + 1}/{self.max_retries + 1} with profile '{profile}'")

			try:
				# Process with current profile
				raw_text, confidence = self.pdf_processor.process_file_with_profile(
					file_path, profile
				)

				# Extract data and count missing fields
				extracted_data = self.text_extractor.extract_invoice_data(raw_text)
				missing_count = self.text_extractor.count_missing_fields(extracted_data)
				quality = self.text_extractor.get_extraction_quality(extracted_data)

				logger.info(f"[Retry] Profile '{profile}': missing={missing_count}, "
				           f"quality={quality['quality_score']}%, confidence={confidence:.1f}%")

				# Track best result
				if missing_count < best_missing_count:
					best_missing_count = missing_count
					best_result = (raw_text, confidence, profile, extracted_data)

				# Success: all critical fields found or below threshold
				if missing_count <= self.missing_threshold:
					logger.info(f"[Retry] Success with profile '{profile}' "
					           f"(missing={missing_count} <= threshold={self.missing_threshold})")
					return raw_text, confidence, profile, extracted_data

			except Exception as e:
				logger.warning(f"[Retry] Profile '{profile}' failed: {e}")
				continue

		# Return best result even if above threshold
		if best_result:
			logger.warning(f"[Retry] Using best result (profile='{best_result[2]}', "
			              f"missing={best_missing_count})")
			return best_result
		else:
			# All attempts failed - raise exception instead of returning empty result
			# This prevents saving garbage invoice records with empty fields
			logger.error("[Retry] All OCR attempts failed - unable to extract any text")
			raise OCRExtractionError(
				f"Nie udało się wyekstraktować tekstu z pliku po {self.max_retries + 1} próbach. "
				"Plik może być uszkodzony lub w nieobsługiwanym formacie."
			)

	def process_invoice_pdf(self, file_path: str, progress_callback=None) -> \
	tuple[Invoice, str]:
		"""
		Przetworz PDF lub obraz faktury.
		Uses smart/hybrid processing with retry logic if enabled.

		Args:
			file_path: Ścieżka do PDF lub obrazu (JPG, PNG, TIFF, BMP)
			progress_callback: Funkcja callback(progress_pct, message)

		Returns:
			(Invoice object, raw_text)
		"""
		if progress_callback:
			progress_callback(10, "Przetwarzanie pliku...")

		# 1. Plik → tekst - use retry logic if enabled
		if self.retry_enabled:
			if progress_callback:
				progress_callback(15, "Wykrywanie typu dokumentu...")
			raw_text, confidence, profile_used, _ = self.process_with_retry(file_path)
			logger.info(f"[Invoice PDF] Processed with profile '{profile_used}'")
		else:
			# Use smart processing (hybrid: direct extraction or OCR based on PDF type)
			raw_text, confidence = self.pdf_processor.process_file_smart(file_path)

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
			except (ValueError, TypeError) as e:
				logger.warning(f"Failed to parse invoice_date '{extracted_data['invoice_date']}': {e}")

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
				except (ValueError, TypeError) as e:
					logger.warning(f"Failed to parse payment_due_date '{extracted_data['payment_due_date']}': {e}")

		# 3.5. Walidacja dat - sprawdź czy termin płatności jest późniejszy niż data faktury
		if invoice_date and payment_due_date:
			if payment_due_date <= invoice_date:
				logger.warning(f"Termin płatności ({payment_due_date}) "
				              f"nie jest późniejszy niż data faktury ({invoice_date}) - możliwy błąd OCR")

		# 4. Stwórz Invoice object
		invoice = Invoice(
			seller_name=extracted_data['seller_name'] or "Nie wykryto",
			invoice_number=extracted_data['invoice_number'] or "BRAK",
			seller_nip=extracted_data['seller_nip'],
			invoice_date=invoice_date or datetime.now().date(),
			bank_account=extracted_data['bank_account'],
			amount=Decimal(str(extracted_data['amount'] or 0)),
			currency=extracted_data['currency'],
			payment_due_date=payment_due_date,
			payment_term=payment_term,
			pdf_path=file_path,
			ocr_confidence=confidence
			)
		
		if progress_callback:
			progress_callback(100, "Gotowe!")
		
		return invoice, raw_text