"""
Skrypt importu pracowników z pliku CSV do tabeli 'employees' w bazie danych aplikacji.

Format CSV (separator: ';'):
    user_id;email;first_name;last_name;position;employment_status;phone;base_salary;commission_rate

Kolumna user_id w CSV zawiera adres e-mail (nie FK do users.id) — jest ignorowana.
Pola employees nieobecne w CSV otrzymują wartości domyślne z modelu Employee.

Użycie:
    python scripts/import_employees_from_csv.py [ścieżka_do_pliku.csv]

Domyślnie szuka pliku: users.csv w katalogu głównym projektu.
"""
import sys
import sqlite3
import csv
from pathlib import Path
from datetime import datetime

# Dodaj katalog główny projektu do sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import DB_PATH

# Dozwolone wartości employment_status (CHECK constraint w bazie)
VALID_STATUSES = {'active', 'on_leave', 'terminated'}


def parse_phone(raw_phone: str) -> str | None:
    """Normalizuj numer telefonu; zwraca None jeśli pusty."""
    if not raw_phone or not raw_phone.strip():
        return None
    return raw_phone.strip()


def parse_float(raw_value: str) -> float | None:
    """Parsuj wartość liczbową; zwraca None jeśli pusta lub nieprawidłowa."""
    if not raw_value or not raw_value.strip():
        return None
    try:
        return float(raw_value.strip())
    except ValueError:
        return None


def import_employees(csv_path: Path, db_path: Path) -> dict:
    """
    Wczytaj pracowników z pliku CSV i zapisz do tabeli employees.

    Duplikaty wykrywane są po kombinacji first_name + last_name.

    Returns:
        dict z kluczami: inserted, skipped, errors
    """
    print(f"Wczytywanie pliku: {csv_path}")

    rows = []
    # Próbuj odczyt z UTF-8 BOM, następnie cp1250 dla polskich znaków
    for encoding in ('utf-8-sig', 'utf-8', 'cp1250'):
        try:
            with open(csv_path, newline='', encoding=encoding) as f:
                reader = csv.DictReader(f, delimiter=';')
                rows = [row for row in reader if any(v.strip() for v in row.values())]
            print(f"Kodowanie: {encoding}, wierszy danych: {len(rows)}")
            break
        except (UnicodeDecodeError, Exception):
            rows = []
            continue

    if not rows:
        print("Błąd: nie udało się odczytać pliku CSV lub plik jest pusty.")
        sys.exit(1)

    print(f"Kolumny CSV: {list(rows[0].keys())}")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    stats = {"inserted": 0, "skipped": 0, "errors": 0}

    for idx, row in enumerate(rows, start=2):  # start=2: wiersz 1 to nagłówek
        first_name = row.get("first_name", "").strip()
        last_name = row.get("last_name", "").strip()

        if not first_name:
            print(f"  [POMIŃ] Wiersz {idx}: brak imienia")
            stats["skipped"] += 1
            continue

        # Normalizacja employment_status
        employment_status = row.get("employment_status", "active").strip().lower()
        if employment_status not in VALID_STATUSES:
            print(f"  [BŁĄD] Wiersz {idx}: nieprawidłowy status '{employment_status}' — pominięto")
            stats["errors"] += 1
            continue

        # is_active wyznaczone ze statusu zatrudnienia
        is_active = 1 if employment_status == "active" else 0

        email = row.get("email", "").strip() or None
        phone = parse_phone(row.get("phone", ""))
        position = row.get("position", "").strip() or None
        base_salary = parse_float(row.get("base_salary", ""))
        commission_rate = parse_float(row.get("commission_rate", ""))

        # Sprawdź duplikaty po imieniu i nazwisku
        cursor.execute(
            "SELECT id FROM employees WHERE first_name = ? AND last_name = ?",
            (first_name, last_name),
        )
        existing = cursor.fetchone()
        if existing:
            print(
                f"  [POMIŃ] '{first_name} {last_name}' — już istnieje (id={existing['id']})"
            )
            stats["skipped"] += 1
            continue

        try:
            cursor.execute(
                """
                INSERT INTO employees (
                    first_name, last_name, email, phone,
                    position, employment_status,
                    base_salary, commission_rate,
                    is_active, max_appointments_per_day,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 8, ?, ?)
                """,
                (
                    first_name, last_name, email, phone,
                    position, employment_status,
                    base_salary, commission_rate,
                    is_active,
                    now, now,
                ),
            )
            print(
                f"  [OK]   '{first_name} {last_name}' | {position} | {employment_status} "
                f"| tel: {phone} | wynagrodzenie: {base_salary} | prowizja: {commission_rate}%"
            )
            stats["inserted"] += 1
        except Exception as e:
            print(f"  [BŁĄD] Wiersz {idx} '{first_name} {last_name}': {e}")
            stats["errors"] += 1

    conn.commit()
    conn.close()
    return stats


def main():
    if len(sys.argv) > 1:
        csv_path = Path(sys.argv[1])
    else:
        csv_path = PROJECT_ROOT / "users.csv"

    if not csv_path.exists():
        print(f"Błąd: plik nie istnieje: {csv_path}")
        sys.exit(1)

    print(f"Baza danych: {DB_PATH}")
    print("-" * 60)

    stats = import_employees(csv_path, DB_PATH)

    print("-" * 60)
    print("Zakończono import pracowników:")
    print(f"  Dodano:    {stats['inserted']}")
    print(f"  Pominięto: {stats['skipped']}")
    print(f"  Błędy:     {stats['errors']}")


if __name__ == "__main__":
    main()
