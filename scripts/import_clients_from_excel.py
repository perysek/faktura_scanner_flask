"""
Skrypt importu klientów z pliku Excel do bazy danych aplikacji.

Użycie:
    python scripts/import_clients_from_excel.py [ścieżka_do_pliku.xlsx]

Domyślnie szuka pliku: 2026-02-09T21_07_09-Klienci.xlsx w katalogu głównym projektu.
"""
import sys
import sqlite3
from pathlib import Path
from datetime import datetime

import pandas as pd

# Dodaj katalog główny projektu do sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import DB_PATH


def parse_phone(raw_phone) -> str | None:
    """Normalizuj numer telefonu i dodaj prefix '48'."""
    if pd.isna(raw_phone):
        return None
    phone = str(raw_phone).strip()
    # Usuń spacje, myślniki, nawiasy
    phone = phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    # Usuń istniejące prefiksy (+48, 0048, +)
    if phone.startswith("+48"):
        phone = phone[3:]
    elif phone.startswith("0048"):
        phone = phone[4:]
    elif phone.startswith("+"):
        phone = phone[1:]
    # Dodaj prefix '48'
    return f"48{phone}"


def parse_date(raw_date) -> str | None:
    """Konwertuj wartość daty na string ISO (YYYY-MM-DD) lub None."""
    if pd.isna(raw_date):
        return None
    if isinstance(raw_date, str):
        raw_date = raw_date.strip()
        if not raw_date:
            return None
    try:
        return pd.to_datetime(raw_date).strftime("%Y-%m-%d")
    except Exception:
        return None


def import_clients(excel_path: Path, db_path: Path) -> dict:
    """
    Wczytaj klientów z pliku Excel i zapisz do bazy danych.

    Returns:
        dict z kluczami: inserted, skipped, errors
    """
    print(f"Wczytywanie pliku: {excel_path}")
    df = pd.read_excel(excel_path, engine="openpyxl")
    print(f"Wczytano {len(df)} wierszy. Kolumny: {list(df.columns)}")

    required_cols = {"first_name"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"Brak wymaganych kolumn w pliku Excel: {missing}")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    stats = {"inserted": 0, "skipped": 0, "errors": 0}

    for idx, row in df.iterrows():
        first_name = str(row.get("first_name", "")).strip() if not pd.isna(row.get("first_name", float("nan"))) else ""
        last_name_raw = row.get("last_name", None)
        last_name = str(last_name_raw).strip() if not pd.isna(last_name_raw) else ""
        phone = parse_phone(row.get("phone", None))
        last_visit_date = parse_date(row.get("last_visit_date", None))

        if not first_name:
            print(f"  [POMIŃ] Wiersz {idx + 2}: brak imienia")
            stats["skipped"] += 1
            continue

        # Sprawdź duplikaty po imieniu, nazwisku i numerze telefonu
        cursor.execute(
            "SELECT id FROM clients WHERE first_name = ? AND last_name = ? AND (phone = ? OR (phone IS NULL AND ? IS NULL))",
            (first_name, last_name, phone, phone),
        )
        existing = cursor.fetchone()
        if existing:
            print(f"  [POMIŃ] '{first_name} {last_name}' (tel: {phone}) — już istnieje (id={existing['id']})")
            stats["skipped"] += 1
            continue

        try:
            cursor.execute(
                """
                INSERT INTO clients (first_name, last_name, phone, last_visit_date, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, 1, ?, ?)
                """,
                (first_name, last_name, phone, last_visit_date, now, now),
            )
            print(f"  [OK]   '{first_name} {last_name}' (tel: {phone}, ostatnia wizyta: {last_visit_date})")
            stats["inserted"] += 1
        except Exception as e:
            print(f"  [BŁĄD] Wiersz {idx + 2}: {e}")
            stats["errors"] += 1

    conn.commit()
    conn.close()
    return stats


def main():
    if len(sys.argv) > 1:
        excel_path = Path(sys.argv[1])
    else:
        excel_path = PROJECT_ROOT / "2026-02-09T21_07_09-Klienci.xlsx"

    if not excel_path.exists():
        print(f"Błąd: plik nie istnieje: {excel_path}")
        sys.exit(1)

    print(f"Baza danych: {DB_PATH}")
    print("-" * 60)

    stats = import_clients(excel_path, DB_PATH)

    print("-" * 60)
    print(f"Zakończono import:")
    print(f"  Dodano:    {stats['inserted']}")
    print(f"  Pominięto: {stats['skipped']}")
    print(f"  Błędy:     {stats['errors']}")


if __name__ == "__main__":
    main()
