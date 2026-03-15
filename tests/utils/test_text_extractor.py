"""Tests for TextExtractor regex patterns and extraction logic (P17)

Covers:
    - NIP extraction (with/without dashes, PL prefix, EU VAT)
    - IBAN / bank account number extraction
    - Invoice number extraction (various Polish formats, KSeF)
    - Monetary amount extraction (comma/dot decimals, spacing)
    - Date extraction and normalization (multiple formats, Polish months)
    - Currency detection
    - Seller name extraction
    - Extraction quality scoring
"""
import pytest
from utils.text_extractor import TextExtractor


class TestNIPExtraction:
    """Test NIP (polski numer identyfikacji podatkowej) extraction patterns"""

    def setup_method(self):
        self.extractor = TextExtractor()

    def test_nip_z_myslnikami(self):
        """NIP w formacie XXX-XXX-XX-XX"""
        text = "NIP: 123-456-78-90"
        result = self.extractor._extract_field(text, 'nip')
        assert result is not None
        assert "123" in result
        assert "90" in result

    def test_nip_bez_myslnikow(self):
        """NIP w formacie ciaglyml 10 cyfr"""
        text = "NIP: 1234567890"
        result = self.extractor._extract_field(text, 'nip')
        assert result is not None
        assert "1234567890" in result

    def test_nip_z_prefiksem_pl(self):
        """NIP z prefiksem PL (format europejski)"""
        text = "NIP: PL 123-456-78-90"
        result = self.extractor._extract_field(text, 'nip')
        assert result is not None
        assert "123" in result

    def test_nip_z_prefiksem_pl_ciagly(self):
        """NIP z prefiksem PL bez myslnikow"""
        text = "NIP: PL1234567890"
        result = self.extractor._extract_field(text, 'nip')
        assert result is not None
        assert "1234567890" in result

    def test_nip_ze_spacjami(self):
        """NIP z spacjami zamiast myslnikow"""
        text = "NIP: 123 456 78 90"
        result = self.extractor._extract_field(text, 'nip')
        assert result is not None

    def test_nip_po_dwukropku(self):
        """NIP po dwukropku bez spacji"""
        text = "NIP:1234567890"
        result = self.extractor._extract_field(text, 'nip')
        assert result is not None

    def test_eu_vat_format(self):
        """EU VAT ID format (np. DE123456789)"""
        text = "VAT ID: DE123456789"
        result = self.extractor._extract_field(text, 'nip')
        assert result is not None
        assert "DE123456789" in result

    def test_tax_id_format(self):
        """Tax ID keyword"""
        text = "Tax ID: PL1234567890"
        result = self.extractor._extract_field(text, 'nip')
        assert result is not None

    def test_brak_nip_w_tekscie(self):
        """Tekst bez NIP nie powinien zwrocic wyniku"""
        text = "Faktura VAT nr 123/2024\nKwota: 1500,00 zl"
        result = self.extractor._extract_field(text, 'nip')
        assert result is None

    def test_nip_zbyt_krotki(self):
        """Zbyt krotki ciag cyfr po NIP nie powinien pasowac"""
        text = "NIP: 12345"
        result = self.extractor._extract_field(text, 'nip')
        assert result is None

    def test_nip_case_insensitive(self):
        """NIP keyword powinien byc case-insensitive"""
        text = "nip: 1234567890"
        result = self.extractor._extract_field(text, 'nip')
        assert result is not None


class TestBankAccountExtraction:
    """Test IBAN / bank account extraction and PL prefix logic"""

    def setup_method(self):
        self.extractor = TextExtractor()

    def test_iban_z_prefiksem_pl(self):
        """IBAN z PL i 26 cyframi"""
        text = "Konto: PL 12345678901234567890123456"
        result = self.extractor._extract_bank_account(text)
        assert result is not None
        assert result.startswith("PL")

    def test_iban_26_cyfr_bez_pl(self):
        """26 cyfr bez prefiksu PL - powinno dodac PL"""
        text = "Konto: 12 1234 1234 1234 1234 1234 1234"
        result = self.extractor._extract_bank_account(text)
        assert result is not None
        assert result.startswith("PL")

    def test_iban_z_keyword_rachunek(self):
        """Numer konta po slowie 'Rachunek'"""
        text = "Rachunek: PL 12345678901234567890123456"
        result = self.extractor._extract_bank_account(text)
        assert result is not None

    def test_iban_z_keyword_nr_konta(self):
        """Numer konta po slowie 'Nr konta'"""
        text = "Nr konta: PL 12345678901234567890123456"
        result = self.extractor._extract_bank_account(text)
        assert result is not None

    def test_iban_keyword_explicit(self):
        """IBAN keyword"""
        text = "IBAN: PL12345678901234567890123456"
        result = self.extractor._extract_bank_account(text)
        assert result is not None
        assert result.startswith("PL")

    def test_iban_z_grupowanymi_cyframi(self):
        """IBAN z cyframi pogrupowanymi po 4"""
        text = "Nr konta: PL 12 1234 1234 1234 1234 1234 1234"
        result = self.extractor._extract_bank_account(text)
        assert result is not None
        assert result.startswith("PL")

    def test_iban_po_nazwie_banku(self):
        """Numer konta po nazwie banku (PKO, ING, itp.)"""
        text = "PKO BP SA 12 1234 1234 1234 1234 1234 1234"
        result = self.extractor._extract_bank_account(text)
        assert result is not None

    def test_brak_konta_w_tekscie(self):
        """Tekst bez numeru konta"""
        text = "Faktura VAT nr 123/2024\nNIP: 1234567890"
        result = self.extractor._extract_bank_account(text)
        assert result is None

    def test_iban_inny_kraj(self):
        """IBAN z kodem innego kraju (np. DE) - regex wymaga 26 cyfr po kodzie kraju"""
        # DE IBAN has only 20 digits (not 26 like PL), so the PL-focused patterns won't match
        # The generic country-code pattern expects 2+4*6 = 26 digits after country code
        text = "IBAN: DE12345678901234567890123456"
        result = self.extractor._extract_bank_account(text)
        assert result is not None

    def test_iban_ocr_blad_dodatkowa_cyfra(self):
        """OCR error - 27 cyfr zamiast 26 - powinno dodac PL"""
        text = "Konto: 123456789012345678901234567"
        result = self.extractor._extract_bank_account(text)
        # Non-standard digit count still gets PL prefix
        assert result is not None
        assert result.startswith("PL")


class TestInvoiceNumberExtraction:
    """Test invoice number extraction patterns"""

    def setup_method(self):
        self.extractor = TextExtractor()

    def test_format_fv_z_ukosnikami(self):
        """Format FV/123/2024"""
        text = "Faktura VAT FV/123/2024"
        result = self.extractor._extract_field(text, 'invoice_number')
        assert result is not None
        assert "FV" in result or "123" in result

    def test_format_fa_z_myslnikami(self):
        """Format FA-123-2024"""
        text = "Faktura nr FA-123-2024"
        result = self.extractor._extract_field(text, 'invoice_number')
        assert result is not None

    def test_format_f_z_segmentami(self):
        """Format F/006579/25/MG"""
        text = "Nr faktury: F/006579/25/MG"
        result = self.extractor._extract_field(text, 'invoice_number')
        assert result is not None

    def test_format_ksef(self):
        """Format KSeF (polski system e-faktur)"""
        text = "KSeF1234567890123"
        result = self.extractor._extract_field(text, 'invoice_number')
        assert result is not None
        assert "KSeF" in result

    def test_format_ksef_z_myslnikiem(self):
        """Format KSeF z myslnikiem"""
        text = "KSeF-1234567890123"
        result = self.extractor._extract_field(text, 'invoice_number')
        assert result is not None
        assert "KSeF" in result

    def test_format_store_prefix(self):
        """Format z prefiksem sklepu S634/F001937/12/2025"""
        text = "nr S634/F001937/12/2025"
        result = self.extractor._extract_field(text, 'invoice_number')
        assert result is not None

    def test_format_rok_prefix(self):
        """Format z rokiem na poczatku 2024/001"""
        text = "Numer: 2024/001"
        result = self.extractor._extract_field(text, 'invoice_number')
        assert result is not None

    def test_faktura_vat_keyword(self):
        """Numer po slowach 'Faktura VAT'"""
        text = "Faktura VAT ABC-123/2024"
        result = self.extractor._extract_field(text, 'invoice_number')
        assert result is not None

    def test_numer_faktury_keyword(self):
        """Numer po slowach 'Numer faktury'"""
        text = "Numer faktury: FV/2024/001"
        result = self.extractor._extract_field(text, 'invoice_number')
        assert result is not None

    def test_format_elektroniczny_dluga_liczba(self):
        """Format elektroniczny z dluga liczba"""
        text = "FV-2024-01-000123"
        result = self.extractor._extract_field(text, 'invoice_number')
        assert result is not None

    def test_brak_numeru_faktury(self):
        """Tekst bez numeru faktury"""
        text = "To jest zwykly tekst bez danych fakturowych"
        result = self.extractor._extract_field(text, 'invoice_number')
        assert result is None


class TestAmountExtraction:
    """Test monetary amount extraction and conversion"""

    def setup_method(self):
        self.extractor = TextExtractor()

    def test_kwota_z_przecinkiem_i_zl(self):
        """Kwota z przecinkiem dziesietnym i symbolem zl"""
        text = "Kwota do zap\u0142aty: 1234,56 z\u0142"
        result = self.extractor._extract_amount(text)
        assert result is not None
        assert result == pytest.approx(1234.56)

    def test_kwota_z_kropka_i_pln(self):
        """Kwota z kropka dziesietna i PLN"""
        text = "Wartosc brutto: 1234.56 PLN"
        result = self.extractor._extract_amount(text)
        assert result is not None
        assert result == pytest.approx(1234.56)

    def test_kwota_z_separatorem_tysiecy(self):
        """Kwota z separatorem tysiecy (spacja)"""
        text = "Kwota do zap\u0142aty: 1 234,56 z\u0142"
        result = self.extractor._extract_amount(text)
        assert result is not None
        assert result == pytest.approx(1234.56)

    def test_kwota_brutto(self):
        """Kwota z keyword 'Wartosc brutto'"""
        text = "Warto\u015b\u0107 brutto: 5000,00 PLN"
        result = self.extractor._extract_amount(text)
        assert result is not None
        assert result == pytest.approx(5000.0)

    def test_kwota_razem_brutto(self):
        """Kwota z keyword 'Razem brutto'"""
        text = "Razem brutto: 3456,78 z\u0142"
        result = self.extractor._extract_amount(text)
        assert result is not None
        assert result == pytest.approx(3456.78)

    def test_kwota_do_zaplaty_priorytet(self):
        """'Kwota do zaplaty' powinna miec najwyzszy priorytet"""
        text = "Warto\u015b\u0107 netto: 100,00 z\u0142\nWarto\u015b\u0107 brutto: 123,00 z\u0142\nKwota do zap\u0142aty: 150,00 z\u0142"
        result = self.extractor._extract_amount(text)
        assert result is not None
        assert result == pytest.approx(150.0)

    def test_kwota_suma(self):
        """Kwota z keyword 'Suma'"""
        text = "Suma: 789,00 PLN"
        result = self.extractor._extract_amount(text)
        assert result is not None
        assert result == pytest.approx(789.0)

    def test_kwota_ogolem(self):
        """Kwota z keyword 'OGOLEM' (with Polish diacritics)"""
        text = "OG\u00d3\u0141EM: 2500,00"
        result = self.extractor._extract_amount(text)
        assert result is not None
        assert result == pytest.approx(2500.0)

    def test_kwota_z_nbsp(self):
        """Kwota z non-breaking space jako separator tysiecy"""
        text = "Kwota do zap\u0142aty: 1\u00a0234,56 z\u0142"
        result = self.extractor._extract_amount(text)
        assert result is not None
        assert result == pytest.approx(1234.56)

    def test_kwota_z_symbolem_zl_jest_rozpoznana(self):
        """Kwota z symbolem zl powinna byc rozpoznana (priorytet 2 — pierwsza dopasowana)"""
        # Extractor priority 2 matches first zł amount via regex patterns
        text = "Wartosc: 250,00 z\u0142"
        result = self.extractor._extract_amount(text)
        assert result is not None
        assert result == pytest.approx(250.0)

    def test_ignoruj_male_kwoty(self):
        """Kwoty ponizej 1 zl powinny byc ignorowane (np. stawki VAT)"""
        text = "Kwota do zaplaty: 0,23 zl"
        result = self.extractor._extract_amount(text)
        # 0.23 is below 1.0 threshold
        assert result is None

    def test_brak_kwoty(self):
        """Tekst bez kwoty"""
        text = "Faktura nr 123\nNIP: 1234567890"
        result = self.extractor._extract_amount(text)
        assert result is None

    def test_kwota_do_zaplaty_wieloliniowa(self):
        """Kwota do zaplaty na oddzielnej linii"""
        text = "Kwota do zap\u0142aty\n1500,00 z\u0142"
        result = self.extractor._extract_amount(text)
        assert result is not None
        assert result == pytest.approx(1500.0)


class TestDateExtraction:
    """Test date extraction and normalization to ISO format"""

    def setup_method(self):
        self.extractor = TextExtractor()

    def test_format_iso_yyyy_mm_dd(self):
        """Format ISO YYYY-MM-DD"""
        result = self.extractor._normalize_date("2024-11-12")
        assert result == "2024-11-12"

    def test_format_iso_z_kropkami(self):
        """Format YYYY.MM.DD"""
        result = self.extractor._normalize_date("2024.11.12")
        assert result == "2024-11-12"

    def test_format_europejski_z_kropkami(self):
        """Format europejski DD.MM.YYYY"""
        result = self.extractor._normalize_date("12.11.2024")
        assert result == "2024-11-12"

    def test_format_europejski_z_ukosnikami(self):
        """Format europejski DD/MM/YYYY"""
        result = self.extractor._normalize_date("12/11/2024")
        assert result == "2024-11-12"

    def test_format_europejski_z_myslnikami(self):
        """Format europejski DD-MM-YYYY"""
        result = self.extractor._normalize_date("12-11-2024")
        assert result == "2024-11-12"

    def test_polskie_nazwy_miesiecy_styczen(self):
        """Data z polska nazwa miesiaca - styczen"""
        result = self.extractor._normalize_date("15 stycznia 2024")
        assert result == "2024-01-15"

    def test_polskie_nazwy_miesiecy_luty(self):
        """Data z polska nazwa miesiaca - luty"""
        result = self.extractor._normalize_date("28 lutego 2024")
        assert result == "2024-02-28"

    def test_polskie_nazwy_miesiecy_marzec(self):
        """Data z polska nazwa miesiaca - marzec"""
        result = self.extractor._normalize_date("1 marca 2024")
        assert result == "2024-03-01"

    def test_polskie_nazwy_miesiecy_kwiecien(self):
        """Data z polska nazwa miesiaca - kwiecien"""
        result = self.extractor._normalize_date("30 kwietnia 2024")
        assert result == "2024-04-30"

    def test_polskie_nazwy_miesiecy_maj(self):
        """maja"""
        result = self.extractor._normalize_date("15 maja 2024")
        assert result == "2024-05-15"

    def test_polskie_nazwy_miesiecy_czerwiec(self):
        """czerwca"""
        result = self.extractor._normalize_date("10 czerwca 2024")
        assert result == "2024-06-10"

    def test_polskie_nazwy_miesiecy_lipiec(self):
        """lipca"""
        result = self.extractor._normalize_date("20 lipca 2024")
        assert result == "2024-07-20"

    def test_polskie_nazwy_miesiecy_sierpien(self):
        """sierpnia"""
        result = self.extractor._normalize_date("5 sierpnia 2024")
        assert result == "2024-08-05"

    def test_polskie_nazwy_miesiecy_wrzesien(self):
        """wrzesnia"""
        result = self.extractor._normalize_date("12 wrzesnia 2024")
        # 'wrzesnia' without Polish characters won't match 'wrzesnia' in POLISH_MONTHS
        # The actual key is 'wrzesnia' with accent: 'wrzesnia'
        # Let's test with proper Polish chars
        result2 = self.extractor._normalize_date("12 wrze\u015bnia 2024")
        assert result2 == "2024-09-12"

    def test_polskie_nazwy_miesiecy_pazdziernik(self):
        """pazdziernika"""
        result = self.extractor._normalize_date("31 pa\u017adziernika 2024")
        assert result == "2024-10-31"

    def test_polskie_nazwy_miesiecy_listopad(self):
        """listopada"""
        result = self.extractor._normalize_date("25 listopada 2024")
        assert result == "2024-11-25"

    def test_polskie_nazwy_miesiecy_grudzien(self):
        """grudnia"""
        result = self.extractor._normalize_date("24 grudnia 2024")
        assert result == "2024-12-24"

    def test_niepoprawna_data_none(self):
        """Zupelnie niepoprawny format daty"""
        result = self.extractor._normalize_date("not-a-date")
        assert result is None

    def test_pusty_string(self):
        """Pusty string nie powinien pasowac"""
        result = self.extractor._extract_date_from_text("")
        assert result is None

    def test_data_wystawienia_z_kontekstem(self):
        """Data wystawienia z keyword 'Data wystawienia'"""
        text = """Faktura VAT
Data wystawienia: 15.03.2024
Data sprzedazy: 10.03.2024"""
        result = self.extractor._extract_invoice_date(text)
        assert result == "2024-03-15"

    def test_data_wystawienia_ignoruje_date_sprzedazy(self):
        """Data sprzedazy (z polskim znakiem) NIE powinna byc uzyta jako data faktury"""
        # Extractor checks for 'sprzedaż' (with ż) to skip these lines
        text = "Data sprzeda\u017cy: 10.03.2024"
        result = self.extractor._extract_invoice_date(text)
        # _extract_invoice_date skips lines containing 'sprzedaż'
        assert result is None

    def test_data_dokumentu_priorytet(self):
        """'Data dokumentu' powinno miec najwyzszy priorytet"""
        text = """Data dokumentu: 20.03.2024
Data wystawienia: 15.03.2024"""
        result = self.extractor._extract_invoice_date(text)
        assert result == "2024-03-20"

    def test_termin_platnosci_data(self):
        """Termin platnosci jako data"""
        text = "Termin platnosci: 30.04.2024"
        result = self.extractor._extract_payment_due_date(text)
        assert result == "2024-04-30"

    def test_termin_platnosci_za_pobraniem(self):
        """Termin platnosci - za pobraniem"""
        text = "Platnosc: za pobraniem"
        result = self.extractor._extract_payment_due_date(text)
        assert result == "POBRANIE"

    def test_regex_wyciaganie_dat_iso(self):
        """Regex pattern powinien wyciagnac date ISO z tekstu"""
        text = "Wystawiono dnia 2024-11-12 w Warszawie"
        result = self.extractor._extract_date_from_text(text)
        assert result == "2024-11-12"

    def test_regex_wyciaganie_dat_europejskich(self):
        """Regex pattern powinien wyciagnac date DD.MM.YYYY z tekstu"""
        text = "Data: 12.11.2024"
        result = self.extractor._extract_date_from_text(text)
        assert result == "2024-11-12"

    def test_regex_wyciaganie_dat_ukosniki(self):
        """Regex pattern powinien wyciagnac date DD/MM/YYYY z tekstu"""
        text = "Data: 12/11/2024"
        result = self.extractor._extract_date_from_text(text)
        assert result == "2024-11-12"

    def test_regex_polskie_miesiace_w_tekscie(self):
        """Regex powinien wyciagnac date z polskim miesiacem z tekstu"""
        text = "Wystawiono 15 stycznia 2024 roku"
        result = self.extractor._extract_date_from_text(text)
        assert result == "2024-01-15"


class TestCurrencyExtraction:
    """Test currency detection from text and IBAN"""

    def setup_method(self):
        self.extractor = TextExtractor()

    def test_waluta_zl(self):
        """Symbol 'zl' powinien dac PLN"""
        result = self.extractor._extract_currency("Kwota: 100,00 zl")
        assert result == "PLN"

    def test_waluta_pln_text(self):
        """'PLN' w tekscie"""
        result = self.extractor._extract_currency("Kwota: 100,00 PLN")
        assert result == "PLN"

    def test_waluta_eur_text(self):
        """'EUR' w tekscie"""
        result = self.extractor._extract_currency("Amount: 100,00 EUR")
        assert result == "EUR"

    def test_waluta_usd_text(self):
        """'USD' w tekscie"""
        result = self.extractor._extract_currency("Amount: 100.00 USD")
        assert result == "USD"

    def test_waluta_gbp_text(self):
        """'GBP' w tekscie"""
        result = self.extractor._extract_currency("Amount: 100.00 GBP")
        assert result == "GBP"

    def test_waluta_z_iban_pl(self):
        """Waluta z IBAN PL -> PLN"""
        result = self.extractor._extract_currency("Amount: 100", "PL12345678901234567890123456")
        assert result == "PLN"

    def test_waluta_z_iban_de(self):
        """Waluta z IBAN DE -> EUR"""
        result = self.extractor._extract_currency("Amount: 100", "DE89370400440532013000")
        assert result == "EUR"

    def test_waluta_z_iban_gb(self):
        """Waluta z IBAN GB -> GBP"""
        result = self.extractor._extract_currency("Amount: 100", "GB29NWBK60161331926819")
        assert result == "GBP"

    def test_waluta_domyslna_pln(self):
        """Brak wskazowek waluty -> domyslnie PLN"""
        result = self.extractor._extract_currency("Faktura nr 123")
        assert result == "PLN"

    def test_zl_priorytet_nad_iban(self):
        """'zl' w tekscie powinno miec priorytet nad IBAN"""
        result = self.extractor._extract_currency("Kwota: 100 zl", "DE89370400440532013000")
        assert result == "PLN"


class TestSellerNameExtraction:
    """Test seller name extraction from invoice text"""

    def setup_method(self):
        self.extractor = TextExtractor()

    def test_sprzedawca_w_nastepnej_linii(self):
        """Nazwa sprzedawcy w linii po 'Sprzedawca'"""
        text = """Sprzedawca:
Firma ABC Sp. z o.o."""
        result = self.extractor._extract_seller_name(text)
        assert result is not None
        assert "Firma ABC" in result or "Sp. z o.o." in result

    def test_sprzedawca_w_tej_samej_linii(self):
        """Nazwa sprzedawcy w tej samej linii co 'Sprzedawca:'"""
        text = "Sprzedawca: Axpo Polska sp. z o.o."
        result = self.extractor._extract_seller_name(text)
        assert result is not None
        assert "Axpo" in result

    def test_sprzedawca_sa(self):
        """Sprzedawca w formie S.A."""
        text = """Sprzedawca:
Wielka Korporacja S.A."""
        result = self.extractor._extract_seller_name(text)
        assert result is not None
        assert "S.A." in result or "Wielka" in result

    def test_fallback_spolka_w_pierwszych_liniach(self):
        """Fallback: pierwsza linia wyglada jak firma (Sp. z o.o.)"""
        text = """Kowalski i Synowie Sp. z o.o.
ul. Testowa 1
00-001 Warszawa"""
        result = self.extractor._extract_seller_name(text)
        assert result is not None
        assert "Kowalski" in result or "Sp. z o.o." in result

    def test_brak_sprzedawcy(self):
        """Tekst bez danych sprzedawcy"""
        text = """Kwota do zaplaty: 100,00 zl
NIP: 1234567890"""
        result = self.extractor._extract_seller_name(text)
        assert result is None

    def test_kolumny_sprzedawca_nabywca(self):
        """Sprzedawca i Nabywca w tej samej linii (kolumny w OCR)"""
        text = """Sprzedawca                     Nabywca
Firma XYZ Sp. z o.o.          Klient ABC
ul. Testowa 1                 ul. Inna 2"""
        result = self.extractor._extract_seller_name(text)
        assert result is not None
        # Should extract seller, not buyer
        assert "Klient ABC" not in result


class TestExtractionQuality:
    """Test extraction quality scoring and missing field counting"""

    def setup_method(self):
        self.extractor = TextExtractor()

    def test_wszystkie_pola_uzupelnione(self):
        """Wszystkie pola krytyczne i wazne uzupelnione"""
        data = {
            'invoice_number': 'FV/123/2024',
            'seller_name': 'Test Sp. z o.o.',
            'amount': 1500.0,
            'invoice_date': '2024-01-15',
            'seller_nip': '1234567890',
            'bank_account': 'PL12345678901234567890123456',
        }
        result = self.extractor.count_missing_fields(data)
        assert result == 0

    def test_brakujace_pole_krytyczne(self):
        """Brakujace jedno pole krytyczne = score 1"""
        data = {
            'invoice_number': None,
            'seller_name': 'Test Sp. z o.o.',
            'amount': 1500.0,
            'invoice_date': '2024-01-15',
            'seller_nip': '1234567890',
            'bank_account': 'PL12345678901234567890123456',
        }
        result = self.extractor.count_missing_fields(data)
        assert result == 1

    def test_brakujace_pole_wazne(self):
        """Brakujace jedno pole wazne = score 0.5 (zaokraglone do 1)"""
        data = {
            'invoice_number': 'FV/123/2024',
            'seller_name': 'Test Sp. z o.o.',
            'amount': 1500.0,
            'invoice_date': '2024-01-15',
            'seller_nip': None,
            'bank_account': 'PL12345678901234567890123456',
        }
        result = self.extractor.count_missing_fields(data)
        assert result == 1  # ceil(0.5) = 1

    def test_brakujace_oba_pola_wazne(self):
        """Brakujace oba pola wazne = score 1.0"""
        data = {
            'invoice_number': 'FV/123/2024',
            'seller_name': 'Test Sp. z o.o.',
            'amount': 1500.0,
            'invoice_date': '2024-01-15',
            'seller_nip': None,
            'bank_account': None,
        }
        result = self.extractor.count_missing_fields(data)
        assert result == 1  # ceil(1.0) = 1

    def test_kwota_zero_jako_brakujaca(self):
        """Kwota rowna 0 powinna byc traktowana jako brakujaca"""
        data = {
            'invoice_number': 'FV/123/2024',
            'seller_name': 'Test Sp. z o.o.',
            'amount': 0,
            'invoice_date': '2024-01-15',
            'seller_nip': '1234567890',
            'bank_account': 'PL12345678901234567890123456',
        }
        result = self.extractor.count_missing_fields(data)
        assert result == 1

    def test_quality_score(self):
        """Quality score z pelnym zestawem danych"""
        data = {
            'invoice_number': 'FV/123/2024',
            'seller_name': 'Test Sp. z o.o.',
            'amount': 1500.0,
            'invoice_date': '2024-01-15',
            'seller_nip': '1234567890',
            'bank_account': 'PL12345678901234567890123456',
        }
        quality = self.extractor.get_extraction_quality(data)
        assert quality['quality_score'] == 100
        assert quality['needs_retry'] is False
        assert quality['missing_critical'] == []
        assert quality['missing_important'] == []

    def test_quality_needs_retry_when_critical_missing(self):
        """needs_retry powinno byc True gdy brakuje pola krytycznego"""
        data = {
            'invoice_number': None,
            'seller_name': None,
            'amount': None,
            'invoice_date': None,
            'seller_nip': None,
            'bank_account': None,
        }
        quality = self.extractor.get_extraction_quality(data)
        assert quality['needs_retry'] is True
        assert quality['quality_score'] == 0


class TestFullExtraction:
    """Integration tests for full invoice data extraction"""

    def setup_method(self):
        self.extractor = TextExtractor()

    def test_pelna_faktura_polska(self):
        """Pelna polska faktura z wszystkimi danymi"""
        text = """Faktura VAT
Numer faktury: FV/001/2024
Data wystawienia: 15.01.2024

Sprzedawca:
Salon Pieknosci Sp. z o.o.
NIP: 123-456-78-90

Konto bankowe: PL 12 1234 1234 1234 1234 1234 1234

Kwota do zap\u0142aty: 2 500,00 z\u0142

Termin platnosci: 30.01.2024"""

        result = self.extractor.extract_invoice_data(text)

        assert result['invoice_number'] is not None
        assert result['seller_name'] is not None
        assert result['seller_nip'] is not None
        assert result['bank_account'] is not None
        assert result['amount'] is not None
        assert result['amount'] == pytest.approx(2500.0)
        assert result['currency'] == 'PLN'
        assert result['invoice_date'] is not None
        assert result['payment_due_date'] is not None

    def test_minimalna_faktura(self):
        """Faktura z minimalna iloscia danych"""
        text = """Faktura nr 123
100,00 zl"""
        result = self.extractor.extract_invoice_data(text)
        # Should extract at least something
        assert isinstance(result, dict)
        assert 'invoice_number' in result
        assert 'amount' in result
