"""
Walidatory NIP i IBAN
"""
import re


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