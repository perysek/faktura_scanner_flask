"""
Ekstrakcja danych z tekstu faktury (regex patterns dla polskich faktur)
"""
import re
from typing import Optional, Dict
from datetime import datetime


class TextExtractor:
	"""Ekstraktor danych z tekstu faktury"""
	
	# Regex patterns dla polskich faktur
	PATTERNS = {
		# Numer faktury: F/006579/25/MG, FV/123/2024, FA-123-2024, itp.
		'invoice_number': [
			# Pattern with prefix included (F/, FV/, FA/, etc.) and optional suffix letters
			r'((?:FV|FA|F|FAKTURA)[\s\-/]*\d+[\-/]\d+(?:[\-/]\d+)?(?:[\-/][A-Z]+)?)',
			# Pattern after Polish keywords (Faktura nr, Nr faktury, etc.)
			r'(?:Faktura\s+nr|Nr\s+faktury|Numer\s+faktury|Faktura\s+numer|Nr|Numer|Number)[\s:\.]*([A-Z0-9\-/]+)',
			# Generic pattern for invoice numbers with letters
			r'([A-Z]{1,4}[\-/]\d+[\-/]\d+(?:[\-/]\d+)?(?:[\-/][A-Z]+)?)',
			# Numbers-only pattern (fallback)
			r'(\d{5,}[\-/]\d{2,}[\-/]?\d*)',
			],
		
		# NIP: 123-456-78-90 lub 1234567890
		'nip': [
			r'NIP[\s:]*(\d{3}[-\s]?\d{3}[-\s]?\d{2}[-\s]?\d{2})',
			r'NIP[\s:]*(\d{10})',
			],
		
		# Numer konta: PL 12 1234 1234 1234 1234 1234 1234
		'bank_account': [
			# Full IBAN with PL prefix (with various spacing)
			r'(?:Konto bankowe|Konto|Nr konta|Rachunek|Bank|Account)[\s:]*PL[\s]?(\d{2}(?:\s?\d{4}){6})',
			r'(?:IBAN)[\s:]*PL[\s]?(\d{2}(?:\s?\d{4}){6})',
			# Generic country code pattern
			r'(?:Konto bankowe|Konto|Nr konta|Rachunek|Bank|Account)[\s:]*([A-Z]{2}[\s]?\d{2}(?:\s?\d{4}){6})',
			r'(?:IBAN)[\s:]*([A-Z]{2}[\s]?\d{2}(?:\s?\d{4}){6})',
			# Just PL followed by numbers (anywhere in text)
			r'PL[\s]?(\d{26})',
			r'PL[\s]?(\d{2}(?:\s?\d{4}){6})',
			# Fallback: just numbers (26 digits for Polish IBAN without PL)
			r'(\d{2}\s?\d{4}\s?\d{4}\s?\d{4}\s?\d{4}\s?\d{4}\s?\d{4})',
			],
		
		# Kwota: 1 234,56 zł lub 1234.56 PLN
		'amount': [
			r'(?:Razem|Suma|Total|Do zapłaty)[\s:]*(\d+[\s\u00a0]?\d*[,\.]\d{2})[\s]*(?:zł|PLN)',
			r'(?:Brutto|Gross)[\s:]*(\d+[\s\u00a0]?\d*[,\.]\d{2})',
			],
		
		# Data: 2024-11-12, 12.11.2024, 12/11/2024
		'date': [
			r'(\d{4}-\d{2}-\d{2})',
			r'(\d{2}\.\d{2}\.\d{4})',
			r'(\d{2}/\d{2}/\d{4})',
			],
		}
	
	def extract_invoice_data(self, text: str) -> Dict[str, Optional[str]]:
		"""
		Ekstraktuj wszystkie dane z tekstu faktury
		"""
		# Extract bank account first to use for currency detection
		bank_account = self._extract_bank_account(text)

		data = {
			'seller_name': self._extract_seller_name(text),
			'invoice_number': self._extract_field(text, 'invoice_number'),
			'seller_nip': self._extract_field(text, 'nip'),
			'bank_account': bank_account,
			'amount': self._extract_amount(text),
			'currency': self._extract_currency(text, bank_account),
			'invoice_date': self._extract_invoice_date(text),
			'payment_due_date': self._extract_payment_due_date(text),
			}

		return data
	
	def _extract_field(self, text: str, field_name: str) -> Optional[str]:
		"""Ekstraktuj pole używając patterns"""
		patterns = self.PATTERNS.get(field_name, [])

		for pattern in patterns:
			match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
			if match:
				value = match.group(1).strip()
				# Czyszczenie białych znaków
				value = re.sub(r'\s+', ' ', value)
				return value

		return None

	def _extract_bank_account(self, text: str) -> Optional[str]:
		"""Ekstraktuj numer konta i dodaj PL jeśli brakuje"""
		account = self._extract_field(text, 'bank_account')

		if not account:
			return None

		# Remove all whitespace for processing
		clean_account = account.replace(' ', '')

		# If it's 26 digits without country code, prepend PL
		if re.match(r'^\d{26}$', clean_account):
			return f'PL{clean_account}'

		# If it already has country code, return as is (but clean spaces)
		if re.match(r'^[A-Z]{2}\d{26}$', clean_account):
			return clean_account

		# Return original if we can't determine the format
		return account
	
	def _extract_seller_name(self, text: str) -> Optional[str]:
		"""
		Ekstraktuj nazwę sprzedawcy (zazwyczaj na początku faktury)
		"""
		lines = text.split('\n')
		
		# Szukaj po słowach kluczowych
		keywords = ['Sprzedawca', 'Wystawca', 'Seller', 'Vendor']
		
		for i, line in enumerate(lines):
			if any(keyword.lower() in line.lower() for keyword in keywords):
				# Nazwa sprzedawcy zazwyczaj w następnej linii
				if i + 1 < len(lines):
					name = lines[i + 1].strip()
					if name and len(name) > 3:
						return name
		
		# Fallback: pierwsza linia która wygląda jak firma
		for line in lines[:10]:
			line = line.strip()
			if re.search(
					r'(Sp\.\s*z\s*o\.?o\.?|S\.A\.|P\.P\.H\.)', line,
					re.IGNORECASE
					):
				return line
		
		return None
	
	def _extract_amount(self, text: str) -> Optional[float]:
		"""Ekstraktuj kwotę i konwertuj na float"""
		amount_str = self._extract_field(text, 'amount')
		
		if not amount_str:
			return None
		
		# Konwersja: "1 234,56" → 1234.56
		amount_str = amount_str.replace(' ', '').replace('\u00a0', '')
		amount_str = amount_str.replace(',', '.')
		
		try:
			return float(amount_str)
		except ValueError:
			return None
	
	def _extract_currency(self, text: str, bank_account: Optional[str] = None) -> str:
		"""
		Ekstraktuj walutę z tekstu i numeru konta
		Priorytet: zł -> IBAN prefix -> text search -> PLN default
		"""
		# 1. Check for Polish złoty symbol 'zł'
		if 'zł' in text.lower() or 'zl' in text.lower():
			return 'PLN'

		# 2. Check IBAN country code if available
		if bank_account:
			bank_account_clean = bank_account.replace(' ', '').upper()
			# Map IBAN country codes to currencies
			iban_currency_map = {
				'PL': 'PLN',  # Poland
				'DE': 'EUR',  # Germany
				'FR': 'EUR',  # France
				'NL': 'EUR',  # Netherlands
				'BE': 'EUR',  # Belgium
				'AT': 'EUR',  # Austria
				'IT': 'EUR',  # Italy
				'ES': 'EUR',  # Spain
				'GB': 'GBP',  # United Kingdom
				'US': 'USD',  # United States (not IBAN but sometimes used)
			}
			# Check first 2 characters of IBAN
			if len(bank_account_clean) >= 2:
				country_code = bank_account_clean[:2]
				if country_code in iban_currency_map:
					return iban_currency_map[country_code]

		# 3. Search for currency codes in text (prioritize PLN)
		# Check PLN first to avoid false positives with EUR
		if 'PLN' in text.upper():
			return 'PLN'

		# Then check other currencies
		for currency in ['EUR', 'USD', 'GBP']:
			if currency in text.upper():
				return currency

		# 4. Default to PLN for Polish invoices
		return 'PLN'
	
	def _extract_invoice_date(self, text: str) -> Optional[str]:
		"""Ekstraktuj datę wystawienia faktury"""
		# Szukaj po kontekście
		date_keywords = [
			'Data wystawienia', 'Wystawiono', 'Data sprzedaży', 'Issue date'
			]
		
		lines = text.split('\n')
		for i, line in enumerate(lines):
			if any(
					keyword.lower() in line.lower() for keyword in date_keywords
					):
				# Data zazwyczaj w tej samej lub następnej linii
				search_text = line + '\n' + (
					lines[i + 1] if i + 1 < len(lines) else '')
				date_str = self._extract_date_from_text(search_text)
				if date_str:
					return date_str
		
		# Fallback: pierwsza znaleziona data
		return self._extract_date_from_text(text)
	
	def _extract_payment_due_date(self, text: str) -> Optional[str]:
		"""Ekstraktuj termin płatności lub wykryj 'za pobraniem'"""
		# First check for "za pobraniem" or "pobranie" (cash on delivery)
		if re.search(r'\b(za\s+pobraniem|pobranie)\b', text, re.IGNORECASE):
			return 'POBRANIE'  # Special marker for cash on delivery

		keywords = [
			'Termin płatności', 'Zapłaty do', 'Due date', 'Payment date'
			]

		lines = text.split('\n')
		for i, line in enumerate(lines):
			if any(keyword.lower() in line.lower() for keyword in keywords):
				search_text = line + '\n' + (
					lines[i + 1] if i + 1 < len(lines) else '')
				date_str = self._extract_date_from_text(search_text)
				if date_str:
					return date_str

		return None
	
	def _extract_date_from_text(self, text: str) -> Optional[str]:
		"""Ekstraktuj datę i normalizuj do ISO file_format (YYYY-MM-DD)"""
		patterns = self.PATTERNS['date']
		
		for pattern in patterns:
			match = re.search(pattern, text)
			if match:
				date_str = match.group(1)
				return self._normalize_date(date_str)
		
		return None
	
	def _normalize_date(self, date_str: str) -> Optional[str]:
		"""Konwertuj różne formaty dat na ISO (YYYY-MM-DD)"""
		formats = [
			'%Y-%m-%d',
			'%d.%m.%Y',
			'%d/%m/%Y',
			]
		
		for fmt in formats:
			try:
				dt = datetime.strptime(date_str, fmt)
				return dt.strftime('%Y-%m-%d')
			except ValueError:
				continue
		
		return None