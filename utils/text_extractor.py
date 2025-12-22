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
			# Pattern after Polish keywords (Faktura VAT, Faktura nr, Nr faktury, etc.)
			r'(?:Faktura\s+VAT|Faktura\s+nr|Nr\s+faktury|Numer\s+faktury|Faktura\s+numer|Nr|Numer|Number)[\s:\.]*([A-Z0-9\-/]+)',
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
		# Priorytet dla kwot brutto i kwoty do zapłaty
		'amount': [
			# Kwota do zapłaty (highest priority) - flexible spacing between words
			r'(?:Kwota\s+do\s+zapłaty|Do\s+zapłaty|Amount\s+to\s+pay)[\s:.]*(\d+[\s\u00a0]?\d*[,\.]\d{2})[\s]*(?:zł|PLN)?',
			# Wartość brutto
			r'(?:Wartość\s+brutto|Brutto|Gross|Razem\s+brutto)[\s:.]*(\d+[\s\u00a0]?\d*[,\.]\d{2})[\s]*(?:zł|PLN)?',
			# Razem (lowest priority - often net amount)
			r'(?:Razem|Suma|Total)[\s:.]*(\d+[\s\u00a0]?\d*[,\.]\d{2})[\s]*(?:zł|PLN)',
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
		Uwzględnia przypadki gdy 'Nabywca' jest w kolumnie obok
		"""
		lines = text.split('\n')

		# Szukaj po słowach kluczowych
		seller_keywords = ['Sprzedawca', 'Wystawca', 'Seller', 'Vendor']
		buyer_keywords = ['Nabywca', 'Buyer', 'Płatnik']

		for i, line in enumerate(lines):
			# Sprawdź czy linia zawiera keyword sprzedawcy
			if any(keyword.lower() in line.lower() for keyword in seller_keywords):
				# Sprawdź czy w tej samej linii nie ma słowa "Nabywca" po "Sprzedawca"
				# (co może oznaczać kolumny obok siebie)
				line_lower = line.lower()

				# Znajdź pozycje słów kluczowych w linii
				seller_pos = -1
				buyer_pos = -1

				for keyword in seller_keywords:
					pos = line_lower.find(keyword.lower())
					if pos != -1:
						seller_pos = pos
						break

				for keyword in buyer_keywords:
					pos = line_lower.find(keyword.lower())
					if pos != -1:
						buyer_pos = pos
						break

				# Jeśli oba słowa są w tej samej linii (kolumny)
				if seller_pos != -1 and buyer_pos != -1:
					# Szukaj nazwy sprzedawcy w następnych liniach
					# ale tylko do momentu znalezienia buyer keywords
					for j in range(i + 1, min(i + 10, len(lines))):
						next_line = lines[j].strip()

						# Pomiń puste linie i linie z samymi separatorami
						if not next_line or all(c in '=-_|/\\' for c in next_line):
							continue

						# Sprawdź czy linia zawiera buyer keywords - jeśli tak, przerwij
						if any(kw.lower() in next_line.lower() for kw in buyer_keywords):
							break

						# Przypadek gdy obie nazwy są w jednej linii (OCR scalił kolumny)
						# np. "Łukasz Rybczyński My Way Aneta Kozłowska"
						# Szukaj separacji po 2-3+ spacjach lub po buyer name patterns

						# Sprawdź czy jest długa sekwencja spacji (typowe dla tabel)
						if '  ' in next_line:  # Co najmniej 2 spacje
							# Podziel po długich spacjach i weź pierwszą część
							parts = re.split(r'\s{2,}', next_line)
							if parts and len(parts[0].strip()) > 3:
								return parts[0].strip()

						# Sprawdź czy w linii są oba fragmenty tekstu (seller i buyer)
						# Jeśli linia jest długa i wygląda na scalenie, spróbuj wyciąć część przed buyer
						if len(next_line) > 30:  # Długa linia może być scaleniem
							words = next_line.split()

							# Strategia 1: Szukaj typowych wzorców firmy (Sp. z o.o., S.A., SA, itp.)
							# Wzorce z kropkami i bez (różne zapisy)
							company_patterns = [
								r'Sp\.\s*z\s*o\.?o\.?',  # Sp. z o.o., Sp z oo, Sp. z o.o
								r'S\.?\s*A\.?',           # S.A., S.A, SA, S A
								r'P\.?P\.?H\.?',          # P.P.H., PPH
								r'sp\.\s*j\.',            # sp. j.
								r's\.?c\.',               # s.c.
							]

							for pattern in company_patterns:
								match = re.search(pattern, next_line, re.IGNORECASE)
								if match:
									# Weź tekst od początku do końca wzorca firmy
									end_pos = match.end()
									seller_candidate = next_line[:end_pos].strip()

									# Usuń seller keywords z początku (np. "Sprzedawca:", "Wystawca:")
									for kw in seller_keywords:
										kw_pattern = kw + r'[\s:]*'
										seller_candidate = re.sub(kw_pattern, '', seller_candidate, flags=re.IGNORECASE).strip()

									# Sprawdź czy po wzorcu nie ma jeszcze części nazwy firmy
									# (np. "S.A." może być w środku nazwy)
									remaining = next_line[end_pos:].strip()

									# Jeśli po wzorcu są separatory (|, przecinek) lub buyer keywords lub długi tekst
									if not remaining or remaining[0] in '|,;' or any(kw.lower() in remaining.lower() for kw in buyer_keywords) or len(remaining) > 20:
										if len(seller_candidate) > 3:
											return seller_candidate

							# Strategia 2: Dla osób - weź pierwsze 2 słowa (imię nazwisko)
							# ale sprawdź czy nie ma formy firmowej
							if len(words) >= 4 and not any(pattern in next_line for pattern in ['Sp.', 'S.A.', 'P.P.H.']):
								# Prawdopodobnie dwie osoby/firmy w jednej linii
								# Weź pierwsze 2 słowa (imię + nazwisko)
								seller_candidate = ' '.join(words[:2])
								if len(seller_candidate) > 3:
									return seller_candidate.strip()

							# Strategia 3: Jeśli są buyer keywords w środku linii
							for kw in buyer_keywords:
								if kw in next_line:
									# Weź tekst przed buyer keyword
									parts = next_line.split(kw)
									if parts[0].strip() and len(parts[0].strip()) > 3:
										return parts[0].strip()

						# Standardowy przypadek - cała linia to seller
						if len(next_line) > 3 and not next_line.startswith('   '):
							return next_line

				else:
					# Standardowy przypadek - słowo tylko "Sprzedawca"
					# Sprawdź najpierw czy nazwa jest w TEJ SAMEJ linii (np. "Sprzedawca: Axpo Polska sp. z o.o.")
					current_line = line.strip()

					# Usuń seller keyword z początku linii
					for kw in seller_keywords:
						kw_pattern = kw + r'[\s:]*'
						current_line = re.sub(kw_pattern, '', current_line, flags=re.IGNORECASE).strip()

					# Jeśli po usunięciu keyword coś zostało, sprawdź czy to nazwa firmy
					if current_line and len(current_line) > 3:
						# Szukaj wzorców firmy w tej linii
						company_patterns = [
							r'Sp\.\s*z\s*o\.?o\.?',
							r'S\.?\s*A\.?',
							r'P\.?P\.?H\.?',
							r'sp\.\s*j\.',
							r's\.?c\.',
						]

						for pattern in company_patterns:
							match = re.search(pattern, current_line, re.IGNORECASE)
							if match:
								# Wyciągnij nazwę do końca wzorca
								end_pos = match.end()
								seller_candidate = current_line[:end_pos].strip()
								remaining = current_line[end_pos:].strip()

								# Sprawdź czy po wzorcu jest separator lub długi tekst
								if not remaining or (remaining and remaining[0] in '|,;') or len(remaining) > 20:
									return seller_candidate

					# Jeśli nie znaleziono w tej samej linii, sprawdź następną linię
					if i + 1 < len(lines):
						name = lines[i + 1].strip()

						# Usuń seller keywords z początku jeśli są
						for kw in seller_keywords:
							kw_pattern = kw + r'[\s:]*'
							name = re.sub(kw_pattern, '', name, flags=re.IGNORECASE).strip()

						if name and len(name) > 3:
							# Upewnij się że to nie buyer name
							if not any(kw.lower() in name.lower() for kw in buyer_keywords):
								return name

		# Fallback: pierwsza linia która wygląda jak firma
		for line in lines[:10]:
			line = line.strip()
			if re.search(
					r'(Sp\.\s*z\s*o\.?o\.?|S\.A\.|P\.P\.H\.)', line,
					re.IGNORECASE
					):
				# Upewnij się że to nie linia z "Nabywca"
				if not any(kw.lower() in line.lower() for kw in buyer_keywords):
					return line

		return None
	
	def _extract_amount(self, text: str) -> Optional[float]:
		"""
		Ekstraktuj kwotę i konwertuj na float
		Strategia: priorytet dla "Kwota do zapłaty" -> wzorce brutto -> największa kwota
		Dla PDF wielostronicowych: priorytet dla kwot z pierwszej strony
		"""
		# PRIORYTET 1: Szukaj "Kwota do zapłaty" z obsługą wieloliniowych
		# Szukaj najpierw w kontekście linii (może być na oddzielnych liniach)
		lines = text.split('\n')
		for i, line in enumerate(lines):
			if re.search(r'Kwota\s+do\s+zapłaty|Do\s+zapłaty', line, re.IGNORECASE):
				# Sprawdź tę linię i następne 2 linie
				search_context = '\n'.join(lines[i:min(i+3, len(lines))])
				# Szukaj kwoty w tym kontekście
				amount_match = re.search(r'(\d+[\s\u00a0]?\d*[,\.]\d{2})[\s]*(?:zł|PLN)?', search_context)
				if amount_match:
					amount_str = amount_match.group(1)
					amount_str = amount_str.replace(' ', '').replace('\u00a0', '')
					amount_str = amount_str.replace(',', '.')
					try:
						amount = float(amount_str)
						if amount > 1.0:  # Ignoruj bardzo małe kwoty
							print(f"  [PLN] Znaleziono 'Kwota do zaplaty': {amount:.2f} zl")
							return amount
					except ValueError:
						pass

		# PRIORYTET 2: Spróbuj standardowych wzorców (Brutto, itp.)
		amount_str = self._extract_field(text, 'amount')

		if amount_str:
			# Konwersja: "1 234,56" → 1234.56
			amount_str = amount_str.replace(' ', '').replace('\u00a0', '')
			amount_str = amount_str.replace(',', '.')
			try:
				amount = float(amount_str)
				if amount > 1.0:
					print(f"  [PLN] Znaleziono kwote z wzorca: {amount:.2f} zl")
					return amount
			except ValueError:
				pass

		# PRIORYTET 3: Szukaj wszystkich kwot w tekście i weź największą
		# PDF jest już ograniczony do max 2 stron w pdf_processor.py

		# Wzorzec dla kwot: liczba z 2 miejscami po przecinku + zł lub PLN
		all_amounts_pattern = r'(\d+[\s\u00a0]?\d*[,\.]\d{2})[\s]*(?:zł|PLN)'
		matches = re.findall(all_amounts_pattern, text, re.IGNORECASE)

		if matches:
			amounts = []
			for match in matches:
				try:
					# Konwersja na float
					amount_str = match.replace(' ', '').replace('\u00a0', '')
					amount_str = amount_str.replace(',', '.')
					amount = float(amount_str)
					# Filtruj bardzo małe kwoty (prawdopodobnie stawki VAT, np. 23%)
					if amount > 1.0:  # Ignoruj kwoty poniżej 1 zł
						amounts.append(amount)
				except ValueError:
					continue

			if amounts:
				# Zwróć największą kwotę (brutto)
				max_amount = max(amounts)
				print(f"  [PLN] Znaleziono najwieksza kwote: {max_amount:.2f} zl")
				return max_amount

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
		"""
		Ekstraktuj datę wystawienia faktury
		UWAGA: NIE używa "Data sprzedaży" - to jest data transakcji, nie data faktury
		"""
		# Szukaj po kontekście - priorytet dla "Data dokumentu" i "Data faktury"
		# NIE szukaj po "Data sprzedaży" - to jest data sprzedaży, nie data wystawienia faktury
		date_keywords = [
			'Data dokumentu',           # Highest priority
			'Data faktury',
			'Data wystawienia faktury',
			'Data wystawienia dokumentu',
			'Data wystawienia',
			'Wystawiono',
			'Issue date'
			]

		lines = text.split('\n')
		for i, line in enumerate(lines):
			# Sprawdź czy linia NIE zawiera "Data sprzedaży" (ignoruj tę datę)
			if 'sprzedaż' in line.lower():
				continue

			if any(
					keyword.lower() in line.lower() for keyword in date_keywords
					):
				# Data zazwyczaj w tej samej lub następnej linii
				search_text = line + '\n' + (
					lines[i + 1] if i + 1 < len(lines) else '')
				date_str = self._extract_date_from_text(search_text)
				if date_str:
					print(f"  [DATE] Znaleziono date faktury: {date_str}")
					return date_str

		# Fallback: pierwsza znaleziona data (ale NIE z linii zawierającej "sprzedaż")
		for i, line in enumerate(lines):
			if 'sprzedaż' in line.lower():
				continue
			date_str = self._extract_date_from_text(line)
			if date_str:
				print(f"  [DATE] Znaleziono date faktury (fallback): {date_str}")
				return date_str

		return None
	
	def _extract_payment_due_date(self, text: str) -> Optional[str]:
		"""Ekstraktuj termin płatności lub wykryj 'za pobraniem'"""
		# First check for "za pobraniem" or "pobranie" (cash on delivery)
		if re.search(r'\b(za\s+pobraniem|pobranie)\b', text, re.IGNORECASE):
			return 'POBRANIE'  # Special marker for cash on delivery

		keywords = [
			'Termin płatności', 'Zapłata do', 'Due date', 'Payment date', 'Płatność do', 'Do zapłaty do', 'Termin płatności do', 'Termin do', 'Termin'
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