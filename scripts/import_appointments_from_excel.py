"""
Skrypt importu historycznych wizyt z plików *Rezerwacje*.xlsx z katalogu głównego projektu.

Mapowanie kolumn Excel → tabele bazy danych zgodnie z import_appointments.txt:
  Data utworzenia  → appointments.created_at / updated_at
  Od               → appointments.appointment_date (data) + start_time (czas)
  Do               → appointments.end_time
  Imię i nazwisko  → appointments.client_id  (dopasowanie po pełnym imieniu)
  Suma brutto      → appointments.total_price  (wiersze z wartością 0 są pomijane)
  Kalendarz        → appointments.employee_id  (dopasowanie po first_name)
  Kategoria        → appointment_services.service_id  (dopasowanie po nazwie usługi)

Reguły ogólne:
  - appointment.status = 'completed' dla każdej tworzonej wizyty
  - Dla każdej wizyty tworzone są: income_records + aktualizacja clients.last_visit_date
  - Duplikaty wykrywane są po (employee_id, appointment_date, start_time)

Użycie:
    python scripts/import_appointments_from_excel.py [katalog_z_plikami]

Domyślnie skanuje katalog główny projektu.
"""
import sys
import sqlite3
import glob
import re
from decimal import Decimal
from pathlib import Path
from datetime import datetime, date

# Dodaj katalog główny projektu do sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

from config.settings import DB_PATH

# Fallback service_id gdy nie udało się dopasować kategorii
DEFAULT_SERVICE_ID = 20

# Specjalne mapowania wartości kolumny 'Kalendarz' na (employee_id, service_id).
# Wartości niejednoznaczne lub wymagające ręcznego przypisania — muszą być
# rozwiązane przed uruchomieniem ogólnego resolvera.
# Klucz: wartość Kalendarz po strip().lower()  Wartość: (employee_id, service_id)
KALENDARZ_OVERRIDES: dict[str, tuple[int, int]] = {
    "zrecepcja asia": (3, 24),  # Joanna Asia → Masaż klasyczny
}


# ---------------------------------------------------------------------------
# Lookup builders
# ---------------------------------------------------------------------------

def build_employee_map(conn: sqlite3.Connection) -> dict:
    """
    Zwraca słownik {first_name_lower: employee_id} dla szybkiego wyszukiwania.
    Używane do dopasowania wartości kolumny 'Kalendarz'.
    """
    rows = conn.execute("SELECT id, first_name FROM employees").fetchall()
    return {r["first_name"].strip().lower(): r["id"] for r in rows}


def build_client_map(conn: sqlite3.Connection) -> dict:
    """
    Zwraca słownik {(first_name_lower, last_name_lower): client_id}.
    Zawiera oba porządki (imię-nazwisko i nazwisko-imię) dla odporności na
    przestawione kolejności w plikach Excel.
    """
    rows = conn.execute("SELECT id, first_name, last_name FROM clients").fetchall()
    result = {}
    for r in rows:
        fn = (r["first_name"] or "").strip().lower()
        ln = (r["last_name"] or "").strip().lower()
        # Normalny porządek (imię, nazwisko)
        result[(fn, ln)] = r["id"]
        # Odwrócony porządek (nazwisko jako imię, imię jako nazwisko)
        if ln:
            result.setdefault((ln, fn), r["id"])
    return result


def build_phone_map(conn: sqlite3.Connection) -> dict:
    """
    Zwraca słownik {normalized_phone: client_id} dla dopasowania po numerze telefonu.
    Telefony w bazie są już w formacie '48XXXXXXXXX' (11 cyfr).
    Używane jako fallback gdy dopasowanie po imieniu i nazwisku nie powiedzie się.
    """
    rows = conn.execute("SELECT id, phone FROM clients WHERE phone IS NOT NULL AND phone != ''").fetchall()
    return {r["phone"].strip(): r["id"] for r in rows}


def build_service_map(conn: sqlite3.Connection) -> list:
    """
    Zwraca listę (id, name_lower) wszystkich usług, posortowaną rosnąco po id.
    Używane do dopasowania kategorii — najpierw szukamy w tej liście.
    """
    rows = conn.execute("SELECT id, name FROM services ORDER BY id").fetchall()
    return [(r["id"], r["name"].strip().lower()) for r in rows]


# ---------------------------------------------------------------------------
# Resolvers
# ---------------------------------------------------------------------------

def resolve_employee_id(kalendarz: str, employee_map: dict) -> int | None:
    """
    Dopasuj wartość kolumny 'Kalendarz' do employee.id.
    Sprawdza, czy którykolwiek first_name pracownika zawiera się w wartości komórki
    (dopasowanie case-insensitive, od najdłuższego imienia, aby unikać fałszywych trafień).
    """
    if not kalendarz or pd.isna(kalendarz):
        return None
    val = str(kalendarz).strip().lower()
    # Dokładne dopasowanie
    if val in employee_map:
        return employee_map[val]
    # Sprawdź, czy first_name jest podciągiem wartości (np. 'zRecepcja Asia' → 'recepcja')
    # Sortuj od najdłuższego first_name żeby unikać fałszywych trafień
    for first_name_lower in sorted(employee_map, key=len, reverse=True):
        if first_name_lower in val:
            return employee_map[first_name_lower]
    return None


def normalize_phone(raw_phone) -> str | None:
    """
    Normalizuj numer telefonu z Excela do formatu '48XXXXXXXXX'.

    Obsługuje formaty:
      '504020116'      → '48504020116'
      ' 504 020 116'   → '48504020116'
      '+48504020116'   → '48504020116'
      '0048504020116'  → '48504020116'
    Zwraca None jeśli wartość jest pusta lub nie da się znormalizować.
    """
    if not raw_phone or (isinstance(raw_phone, float) and pd.isna(raw_phone)):
        return None
    phone = str(raw_phone).strip().replace(" ", "").replace("-", "")
    if not phone or phone.lower() == "nan":
        return None
    # Usuń istniejące prefiksy
    if phone.startswith("+48"):
        phone = phone[3:]
    elif phone.startswith("0048"):
        phone = phone[4:]
    elif phone.startswith("+"):
        phone = phone[1:]
    # Zostaw tylko cyfry
    phone = re.sub(r"\D", "", phone)
    # Po normalizacji powinniśmy mieć 9 cyfr (polski numer bez prefiksu)
    if len(phone) == 9:
        return f"48{phone}"
    # Jeśli ktoś podał pełny numer z 48 (11 cyfr) — zostawiamy
    if len(phone) == 11 and phone.startswith("48"):
        return phone
    return None


def _strip_prefix(full_name: str) -> str:
    """Usuń prefix 'p.' oraz białe znaki z pełnego imienia i nazwiska."""
    cleaned = re.sub(r"^\s*p\.\s*", "", full_name.strip(), flags=re.IGNORECASE)
    return cleaned.strip()


def resolve_client_id(full_name_raw: str, client_map: dict,
                      phone_raw=None, phone_map: dict | None = None) -> int | None:
    """
    Dopasuj klienta z Excela do client.id.

    Strategia (w kolejności priorytetu):
    1. Usuń prefix 'p.' z pełnego imienia i nazwiska
    2. Dokładne dopasowanie imię+nazwisko (case-insensitive)
    3. Odwrócony porządek: nazwisko+imię (case-insensitive)
    4. Dopasowanie tylko po imieniu (gdy brak nazwiska)
    5. FALLBACK: dopasowanie po znormalizowanym numerze telefonu
    6. Zwróć None jeśli żadna strategia nie zwróciła wyniku
    """
    if not full_name_raw or pd.isna(full_name_raw):
        return _resolve_by_phone(phone_raw, phone_map)

    cleaned = _strip_prefix(str(full_name_raw))
    if not cleaned or cleaned.lower() == "wolne":
        return None

    parts = cleaned.split(None, 1)  # Podziel na maksymalnie 2 części
    if len(parts) == 0:
        return _resolve_by_phone(phone_raw, phone_map)

    fn_lower = parts[0].lower()
    ln_lower = parts[1].lower() if len(parts) > 1 else ""

    # 1. Normalny porządek: (imię, nazwisko)
    if (fn_lower, ln_lower) in client_map:
        return client_map[(fn_lower, ln_lower)]
    # 2. Odwrócony porządek: (nazwisko, imię)
    if ln_lower and (ln_lower, fn_lower) in client_map:
        return client_map[(ln_lower, fn_lower)]
    # 3. Tylko imię (gdy brak nazwiska lub brak pasującego rekordu)
    if (fn_lower, "") in client_map:
        return client_map[(fn_lower, "")]
    if ln_lower and (ln_lower, "") in client_map:
        return client_map[(ln_lower, "")]

    # 4. Fallback: numer telefonu
    return _resolve_by_phone(phone_raw, phone_map)


def _resolve_by_phone(phone_raw, phone_map: dict | None) -> int | None:
    """
    Pomocnicza funkcja: dopasuj klienta po znormalizowanym numerze telefonu.
    Zwraca client.id lub None.
    """
    if phone_map is None:
        return None
    normalized = normalize_phone(phone_raw)
    if normalized is None:
        return None
    return phone_map.get(normalized)


def resolve_service_id(kategoria: str, service_list: list) -> int:
    """
    Dopasuj wartość 'Kategoria' do service.id.

    Strategia (w kolejności priorytetu):
    1. Dokładne dopasowanie (case-insensitive, po strip)
    2. Nazwa usługi zaczyna się od wartości Kategorii (np. 'Uzupełnienie żelu' → id 47)
    3. Wartość Kategorii zaczyna się od nazwy usługi
    4. Fallback: DEFAULT_SERVICE_ID (20 = Manicure klasyczny)

    Dla pustej wartości zwraca DEFAULT_SERVICE_ID.
    """
    if not kategoria or pd.isna(kategoria):
        return DEFAULT_SERVICE_ID

    kat = str(kategoria).strip().lower()
    if not kat:
        return DEFAULT_SERVICE_ID

    # 1. Dokładne dopasowanie
    for svc_id, svc_name in service_list:
        if svc_name == kat:
            return svc_id

    # 2. Nazwa usługi zaczyna się od kategorii (np. 'uzupełnienie żelu' → 'uzupełnienie żelu 1')
    for svc_id, svc_name in service_list:
        if svc_name.startswith(kat):
            return svc_id

    # 3. Kategoria zaczyna się od nazwy usługi (np. 'manicure' → 'manicure klasyczny')
    for svc_id, svc_name in service_list:
        if kat.startswith(svc_name):
            return svc_id

    return DEFAULT_SERVICE_ID


# ---------------------------------------------------------------------------
# Date / time helpers
# ---------------------------------------------------------------------------

def parse_appointment_date(cell_value) -> str | None:
    """
    Wyciągnij część daty 'YYYY-MM-DD' z wartości komórki kolumny 'Od'.
    Komórka może zawierać string 'YYYY-MM-DD HH:MM:SS' lub obiekt datetime.
    """
    if pd.isna(cell_value):
        return None
    if isinstance(cell_value, (datetime, date)):
        return cell_value.strftime("%Y-%m-%d")
    try:
        dt = pd.to_datetime(str(cell_value))
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return None


def parse_time(cell_value) -> str | None:
    """
    Wyciągnij część czasu 'HH:MM:SS' z wartości komórki 'Od' lub 'Do'.
    """
    if pd.isna(cell_value):
        return None
    if isinstance(cell_value, datetime):
        return cell_value.strftime("%H:%M:%S")
    try:
        dt = pd.to_datetime(str(cell_value))
        return dt.strftime("%H:%M:%S")
    except Exception:
        return None


def parse_created_at(cell_value) -> str:
    """
    Parsuj 'Data utworzenia' i zwróć string 'YYYY-MM-DD HH:MM:SS'.
    Fallback: aktualny timestamp.
    """
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if pd.isna(cell_value):
        return now_str
    try:
        dt = pd.to_datetime(str(cell_value))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return now_str


def calc_duration_minutes(od_cell, do_cell) -> int:
    """
    Oblicz czas trwania wizyty w minutach na podstawie komórek 'Od' i 'Do'.
    Zwraca 0 jeśli nie można obliczyć.
    """
    try:
        start = pd.to_datetime(str(od_cell))
        end = pd.to_datetime(str(do_cell))
        delta = end - start
        minutes = int(delta.total_seconds() / 60)
        return max(minutes, 0)
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# Core import logic
# ---------------------------------------------------------------------------

def appointment_exists(cursor: sqlite3.Cursor, employee_id: int,
                        appointment_date: str, start_time: str) -> bool:
    """Sprawdź, czy wizyta już istnieje (deduplicacja po pracowniku, dacie i godzinie)."""
    cursor.execute(
        "SELECT 1 FROM appointments WHERE employee_id=? AND appointment_date=? AND start_time=?",
        (employee_id, appointment_date, start_time),
    )
    return cursor.fetchone() is not None


def import_file(filepath: Path, conn: sqlite3.Connection,
                employee_map: dict, client_map: dict, phone_map: dict,
                service_list: list, cursor: sqlite3.Cursor) -> dict:
    """
    Importuj wizyty z jednego pliku Excel.

    Returns:
        dict z kluczami: inserted, skipped_zero, skipped_no_client,
                         skipped_no_employee, skipped_duplicate, errors
    """
    print(f"\nPlik: {filepath.name}")

    try:
        df = pd.read_excel(filepath, engine="openpyxl", dtype=str)
    except Exception as e:
        print(f"  [BŁĄD] Nie udało się wczytać pliku: {e}")
        return {"inserted": 0, "skipped_zero": 0, "skipped_no_client": 0,
                "skipped_no_employee": 0, "skipped_duplicate": 0, "errors": 1}

    # Znormalizuj nazwy kolumn: usuń białe znaki
    df.columns = [c.strip() for c in df.columns]
    print(f"  Wierszy: {len(df)}")

    stats = {
        "inserted": 0,
        "skipped_zero": 0,
        "skipped_no_client": 0,
        "skipped_no_employee": 0,
        "skipped_duplicate": 0,
        "errors": 0,
    }

    for idx, row in df.iterrows():
        excel_row = idx + 2  # Wiersz w pliku Excel (1-indeksowany + nagłówek)

        # --- Pobierz wartości kolumn ---
        suma_brutto_raw = row.get("Suma brutto", "0")
        try:
            suma_brutto = float(str(suma_brutto_raw).replace(",", ".")) if suma_brutto_raw else 0.0
        except (ValueError, TypeError):
            suma_brutto = 0.0

        # REGUŁA: pomiń wiersze z Suma brutto = 0
        if suma_brutto == 0:
            stats["skipped_zero"] += 1
            continue

        od_cell = row.get("Od", "")
        do_cell = row.get("Do", "")
        data_cell = row.get("Data utworzenia", "")
        imie_cell = row.get("Imi\u0119 i nazwisko", row.get("Imie i nazwisko", ""))
        telefon_cell = row.get("Telefon", "")
        kalendarz_cell = row.get("Kalendarz", "")
        kategoria_cell = row.get("Kategoria", "")

        # --- Parsuj daty i czasy ---
        appointment_date = parse_appointment_date(od_cell)
        start_time = parse_time(od_cell)
        end_time = parse_time(do_cell)
        created_at = parse_created_at(data_cell)
        duration_minutes = calc_duration_minutes(od_cell, do_cell)

        if not appointment_date or not start_time or not end_time:
            print(f"  [POMIŃ] Wiersz {excel_row}: brak daty/czasu (Od={od_cell!r}, Do={do_cell!r})")
            stats["errors"] += 1
            continue

        # --- Rozwiąż employee_id (z uwzględnieniem nadpisań dla specjalnych wartości) ---
        kal_lower = str(kalendarz_cell).strip().lower() if kalendarz_cell else ""
        if kal_lower in KALENDARZ_OVERRIDES:
            employee_id, forced_service_id = KALENDARZ_OVERRIDES[kal_lower]
        else:
            employee_id = resolve_employee_id(kalendarz_cell, employee_map)
            forced_service_id = None

        if employee_id is None:
            print(f"  [POMIŃ] Wiersz {excel_row}: nieznany pracownik '{kalendarz_cell}'")
            stats["skipped_no_employee"] += 1
            continue

        # --- Rozwiąż client_id (imię+nazwisko, następnie telefon jako fallback) ---
        client_id = resolve_client_id(imie_cell, client_map, telefon_cell, phone_map)
        if client_id is None:
            client_label = _strip_prefix(str(imie_cell)) if imie_cell else str(imie_cell)
            print(f"  [POMIŃ] Wiersz {excel_row}: nieznany klient '{client_label}'")
            stats["skipped_no_client"] += 1
            continue

        # --- Sprawdź duplikat ---
        if appointment_exists(cursor, employee_id, appointment_date, start_time):
            stats["skipped_duplicate"] += 1
            continue

        # --- Rozwiąż service_id (nadpisanie z KALENDARZ_OVERRIDES lub normalna ścieżka) ---
        service_id = forced_service_id if forced_service_id is not None \
            else resolve_service_id(kategoria_cell, service_list)

        # --- Oblicz prowizję ---
        cursor.execute("SELECT commission_rate FROM employees WHERE id=?", (employee_id,))
        emp_row = cursor.fetchone()
        commission_rate = float(emp_row["commission_rate"] or 0) if emp_row else 0.0
        commission_amount = round(suma_brutto * commission_rate / 100, 2)

        total_price = round(suma_brutto, 2)

        try:
            # INSERT appointments
            cursor.execute(
                """
                INSERT INTO appointments (
                    client_id, employee_id, status,
                    appointment_date, start_time, end_time,
                    total_price, total_duration, discount_amount,
                    created_at, updated_at
                ) VALUES (?, ?, 'completed', ?, ?, ?, ?, ?, 0, ?, ?)
                """,
                (
                    client_id, employee_id,
                    appointment_date, start_time, end_time,
                    total_price, duration_minutes,
                    created_at, created_at,
                ),
            )
            appointment_id = cursor.lastrowid

            # INSERT appointment_services
            cursor.execute(
                """
                INSERT INTO appointment_services (
                    appointment_id, service_id,
                    price_charged, duration_minutes,
                    commission_rate, commission_amount,
                    is_addon
                ) VALUES (?, ?, ?, ?, ?, ?, 0)
                """,
                (
                    appointment_id, service_id,
                    total_price, duration_minutes,
                    commission_rate, commission_amount,
                ),
            )

            # INSERT income_records
            cursor.execute(
                """
                INSERT INTO income_records (
                    appointment_id, client_id, employee_id,
                    total_amount, discount_amount, net_amount, commission_total,
                    payment_date, created_at
                ) VALUES (?, ?, ?, ?, 0, ?, ?, ?, ?)
                """,
                (
                    appointment_id, client_id, employee_id,
                    total_price,
                    total_price,       # net_amount = total (brak rabatu)
                    commission_amount,
                    appointment_date,  # payment_date = data wizyty
                    created_at,
                ),
            )

            # UPDATE clients.last_visit_date jeśli wizyta jest późniejsza
            cursor.execute(
                """
                UPDATE clients
                SET last_visit_date = ?
                WHERE id = ?
                  AND (last_visit_date IS NULL OR last_visit_date < ?)
                """,
                (appointment_date, client_id, appointment_date),
            )

            stats["inserted"] += 1

        except Exception as e:
            print(f"  [BŁĄD] Wiersz {excel_row}: {e}")
            stats["errors"] += 1

    return stats


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    scan_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else PROJECT_ROOT

    # Znajdź pliki Excel (pomiń tymczasowe pliki zaczynające się od '~$')
    pattern = str(scan_dir / "*Rezerwacje*.xlsx")
    all_files = [
        Path(p) for p in glob.glob(pattern)
        if not Path(p).name.startswith("~$")
    ]

    if not all_files:
        print(f"Nie znaleziono plików *Rezerwacje*.xlsx w: {scan_dir}")
        sys.exit(1)

    all_files.sort()
    print(f"Znaleziono {len(all_files)} plik(ów):")
    for f in all_files:
        print(f"  {f.name}")

    print(f"\nBaza danych: {DB_PATH}")
    print("-" * 60)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # Włącz klucze obce
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()

    # Zbuduj tabele wyszukiwania raz (przed przetwarzaniem plików)
    employee_map = build_employee_map(conn)
    client_map = build_client_map(conn)
    phone_map = build_phone_map(conn)
    service_list = build_service_map(conn)

    print(f"Pracownicy w bazie: {len(employee_map)}")
    print(f"Klienci w bazie: {len(client_map) // 2} unikalnych")  # // 2 bo dodajemy odwrócony
    print(f"Klienci z telefonem: {len(phone_map)}")
    print(f"Usługi w bazie: {len(service_list)}")

    totals = {
        "inserted": 0,
        "skipped_zero": 0,
        "skipped_no_client": 0,
        "skipped_no_employee": 0,
        "skipped_duplicate": 0,
        "errors": 0,
    }

    for filepath in all_files:
        stats = import_file(
            filepath, conn, employee_map, client_map, phone_map, service_list, cursor
        )
        conn.commit()  # Commit po każdym pliku
        for key in totals:
            totals[key] += stats.get(key, 0)
        print(
            f"  => Dodano: {stats['inserted']} | "
            f"Pominięto (kwota=0): {stats['skipped_zero']} | "
            f"Brak klienta: {stats['skipped_no_client']} | "
            f"Brak pracownika: {stats['skipped_no_employee']} | "
            f"Duplikaty: {stats['skipped_duplicate']} | "
            f"Błędy: {stats['errors']}"
        )

    conn.close()

    print("\n" + "=" * 60)
    print("PODSUMOWANIE IMPORTU:")
    print(f"  Dodano wizyt:              {totals['inserted']}")
    print(f"  Pominięto (suma=0):        {totals['skipped_zero']}")
    print(f"  Pominięto (brak klienta):  {totals['skipped_no_client']}")
    print(f"  Pominięto (brak pracown.): {totals['skipped_no_employee']}")
    print(f"  Pominięto (duplikaty):     {totals['skipped_duplicate']}")
    print(f"  Błędy:                     {totals['errors']}")


if __name__ == "__main__":
    main()
