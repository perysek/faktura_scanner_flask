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
	"""Walidator IBAN (międzynarodowy numer konta)"""
	
	@staticmethod
	def clean_iban(iban: str) -> str:
		"""Usuń białe znaki z IBAN"""
		return re.sub(r'\s', '', iban.upper())
	
	@staticmethod
	def validate(iban: str) -> bool:
		"""
		Waliduj IBAN używając algorytmu mod-97
		"""
		if not iban:
			return False
		
		iban = IBANValidator.clean_iban(iban)
		
		# Polski IBAN: PL + 26 cyfr
		if not re.match(r'^PL\d{26}$', iban):
			return False
		
		# Algorytm mod-97
		# Przenieś pierwsze 4 znaki na koniec
		rearranged = iban[4:] + iban[:4]
		
		# Zamień litery na cyfry (A=10, B=11, ..., Z=35)
		numeric = ''
		for char in rearranged:
			if char.isdigit():
				numeric += char
			else:
				numeric += str(ord(char) - ord('A') + 10)
		
		# Sprawdź mod 97
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