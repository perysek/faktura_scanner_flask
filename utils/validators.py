"""
Walidatory NIP, IBAN i parser dat
"""
import re
from datetime import date, datetime
from typing import Optional


class NIPValidator:
	"""Walidator NIP (polski numer identyfikacji podatkowej)"""
	
	@staticmethod
	def clean_nip(nip: str) -> str:
		"""Usuń znaki specjalne z NIP"""
		return re.sub(r'[\s\-]', '', nip)
	
	@staticmethod
	def validate(nip: str) -> bool:
		"""
		Waliduj NIP używając algorytmu kontrolnego
		https://pl.wikipedia.org/wiki/NIP#Sprawdzanie_poprawności_numeru
		"""
		if not nip:
			return False
		
		nip = NIPValidator.clean_nip(nip)
		
		# NIP musi mieć 10 cyfr
		if not re.match(r'^\d{10}$', nip):
			return False
		
		# Algorytm kontrolny
		weights = [6, 5, 7, 2, 3, 4, 5, 6, 7]
		digits = [int(d) for d in nip]
		
		checksum = sum(w * d for w, d in zip(weights, digits[:9]))
		control = checksum % 11
		
		if control == 10:
			return False
		
		return control == digits[9]


class IBANValidator:
	"""Walidator IBAN (międzynarodowy numer konta) — P2-6: supports EU IBANs"""

	# IBAN length per country (ISO 13616)
	IBAN_LENGTHS = {
		'AL': 28, 'AD': 24, 'AT': 20, 'AZ': 28, 'BH': 22, 'BY': 28,
		'BE': 16, 'BA': 20, 'BR': 29, 'BG': 22, 'CR': 22, 'HR': 21,
		'CY': 28, 'CZ': 24, 'DK': 18, 'DO': 28, 'TL': 23, 'EE': 20,
		'FO': 18, 'FI': 18, 'FR': 27, 'GE': 22, 'DE': 22, 'GI': 23,
		'GR': 27, 'GL': 18, 'GT': 28, 'HU': 28, 'IS': 26, 'IQ': 23,
		'IE': 22, 'IL': 23, 'IT': 27, 'JO': 30, 'KZ': 20, 'XK': 20,
		'KW': 30, 'LV': 21, 'LB': 28, 'LI': 21, 'LT': 20, 'LU': 20,
		'MT': 31, 'MR': 27, 'MU': 30, 'MC': 27, 'MD': 24, 'ME': 22,
		'NL': 18, 'MK': 19, 'NO': 15, 'PK': 24, 'PS': 29, 'PL': 28,
		'PT': 25, 'QA': 29, 'RO': 24, 'LC': 32, 'SM': 27, 'ST': 25,
		'SA': 24, 'RS': 22, 'SC': 31, 'SK': 24, 'SI': 19, 'ES': 24,
		'SE': 24, 'CH': 21, 'TN': 24, 'TR': 26, 'UA': 29, 'AE': 23,
		'GB': 22, 'VA': 22, 'VG': 24,
	}

	@staticmethod
	def clean_iban(iban: str) -> str:
		"""Usuń białe znaki z IBAN"""
		return re.sub(r'\s', '', iban.upper())

	@classmethod
	def validate(cls, iban: str) -> bool:
		"""
		Waliduj IBAN używając algorytmu mod-97.
		Supports all EU/international IBAN formats (not just Polish).
		"""
		if not iban:
			return False

		iban = cls.clean_iban(iban)

		# Must start with 2 letters + 2 check digits
		if not re.match(r'^[A-Z]{2}\d{2}', iban):
			return False

		# Validate length for known country
		country = iban[:2]
		expected_len = cls.IBAN_LENGTHS.get(country)
		if expected_len and len(iban) != expected_len:
			return False

		# Validate all remaining chars are alphanumeric
		if not re.match(r'^[A-Z0-9]+$', iban):
			return False

		# Algorytm mod-97
		rearranged = iban[4:] + iban[:4]
		numeric = ''
		for char in rearranged:
			if char.isdigit():
				numeric += char
			else:
				numeric += str(ord(char) - ord('A') + 10)

		return int(numeric) % 97 == 1


class DateParser:
	"""
	Centralized date parsing utility.
	Handles multiple date formats commonly found in Polish invoices.
	"""

	# Polish month names for text date parsing
	POLISH_MONTHS = {
		'stycznia': 1, 'lutego': 2, 'marca': 3, 'kwietnia': 4,
		'maja': 5, 'czerwca': 6, 'lipca': 7, 'sierpnia': 8,
		'września': 9, 'października': 10, 'listopada': 11, 'grudnia': 12
	}

	# Standard date formats to try
	DATE_FORMATS = [
		'%Y-%m-%d',   # ISO: 2024-11-12
		'%Y.%m.%d',   # 2024.11.12
		'%d.%m.%Y',   # European: 12.11.2024
		'%d/%m/%Y',   # European slash: 12/11/2024
		'%d-%m-%Y',   # European dash: 12-11-2024
	]

	@classmethod
	def parse(cls, date_str: Optional[str]) -> Optional[date]:
		"""
		Parse date string to date object.
		Handles multiple formats: YYYY-MM-DD, DD.MM.YYYY, DD/MM/YYYY, Polish text dates.

		Args:
			date_str: Date string in various formats, or None

		Returns:
			date object if parsing successful, None otherwise
		"""
		if not date_str:
			return None

		date_str = date_str.strip()

		# First, try to normalize using TextExtractor's logic if it looks like it needs it
		normalized = cls._normalize_date(date_str)
		if normalized:
			try:
				return datetime.strptime(normalized, '%Y-%m-%d').date()
			except (ValueError, TypeError):
				pass

		# Try standard formats directly
		for fmt in cls.DATE_FORMATS:
			try:
				return datetime.strptime(date_str, fmt).date()
			except ValueError:
				continue

		return None

	@classmethod
	def _normalize_date(cls, date_str: str) -> Optional[str]:
		"""
		Normalize various date formats to ISO (YYYY-MM-DD).

		Args:
			date_str: Date string in various formats

		Returns:
			ISO format string (YYYY-MM-DD) or None if parsing fails
		"""
		if not date_str:
			return None

		# Try standard formats
		for fmt in cls.DATE_FORMATS:
			try:
				dt = datetime.strptime(date_str, fmt)
				return dt.strftime('%Y-%m-%d')
			except ValueError:
				continue

		# Try Polish text month format (e.g., "15 stycznia 2024")
		try:
			parts = date_str.lower().split()
			if len(parts) == 3:
				day = int(parts[0])
				month = cls.POLISH_MONTHS.get(parts[1])
				year = int(parts[2])
				if month and 1 <= day <= 31 and 1900 <= year <= 2100:
					return f"{year:04d}-{month:02d}-{day:02d}"
		except (ValueError, AttributeError):
			pass

		return None

	@classmethod
	def format_for_display(cls, date_obj: Optional[date], format_str: str = '%d.%m.%Y') -> str:
		"""
		Format date object for display.

		Args:
			date_obj: date object or None
			format_str: Output format (default: Polish format DD.MM.YYYY)

		Returns:
			Formatted date string or empty string if None
		"""
		if not date_obj:
			return ''
		return date_obj.strftime(format_str)