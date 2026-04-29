"""
import_appointments_from_url.py

Pobiera plik Rezerwacje.xlsx z caldis.pl (uwierzytelniony POST do
/BookingExport/ExportToXlsx), a następnie importuje wizyty do lokalnej bazy
SQLite używając tej samej logiki co import_appointments_from_excel.py.

Użycie:
    python scripts/import_appointments_from_url.py [OPCJE]

Opcje:
    --date-start YYYY-MM-DD  Początek zakresu (domyślnie: 90 dni temu)
    --date-end   YYYY-MM-DD  Koniec zakresu   (domyślnie: dzisiaj)
    --email      TEXT        Email caldis.pl  (lub env CALDIS_EMAIL)
    --password   TEXT        Hasło caldis.pl  (lub env CALDIS_PASSWORD)
    --keep-xlsx              Zachowaj xlsx po imporcie
    --dry-run                Parsuj i pokaż statystyki, nie zapisuj do bazy

Zmienne środowiskowe:
    CALDIS_EMAIL     – email do caldis.pl
    CALDIS_PASSWORD  – hasło do caldis.pl
"""

import argparse
import os
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR  = PROJECT_ROOT / "scripts"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SCRIPTS_DIR))

from config.settings import DB_PATH
from import_appointments_from_excel import (
    build_client_map,
    build_employee_map,
    build_phone_map,
    build_service_map,
    import_file,
)

CALDIS_BASE  = "https://caldis.pl"
LOGIN_URL    = f"{CALDIS_BASE}/Account/Login"
BOOKING_URL  = f"{CALDIS_BASE}/Booking"
EXPORT_URL   = f"{CALDIS_BASE}/BookingExport/ExportToXlsx"
XLSX_MIME    = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _get_csrf(session: requests.Session, url: str) -> str:
    """GET url and return the __RequestVerificationToken hidden input value."""
    resp = session.get(url, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    tag  = soup.find("input", {"name": "__RequestVerificationToken"})
    if not tag:
        raise RuntimeError(
            f"Nie znaleziono __RequestVerificationToken na stronie {url}\n"
            "Możliwe że strona wymaga innego sposobu logowania lub sesja wygasła."
        )
    return tag["value"]


def _scrape_room_guids(session: requests.Session) -> list[str]:
    """
    Scrape filterRoomMultiselect option values from the Booking page.
    Returns list of GUID strings; empty list if the element is not found
    (server will then return all rooms by default).
    """
    resp   = session.get(BOOKING_URL, timeout=30)
    soup   = BeautifulSoup(resp.text, "html.parser")
    select = (
        soup.find("select", {"name": "filterRoomMultiselect"})
        or soup.find("select", {"id": "filterRoomMultiselect"})
    )
    if not select:
        return []
    return [opt["value"] for opt in select.find_all("option") if opt.get("value")]


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------

def fetch_xlsx(
    email: str,
    password: str,
    date_start: date,
    date_end: date,
    output_path: Path,
) -> Path:
    """
    Authenticate to caldis.pl and download the booking export as .xlsx.

    Returns the path to the saved file.
    Raises RuntimeError with a user-friendly message on any failure.
    """
    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    })

    # Step 1 — Log in
    print("Krok 1/3: Logowanie do caldis.pl...")
    login_token = _get_csrf(session, LOGIN_URL)
    login_resp  = session.post(
        LOGIN_URL,
        data={
            "__RequestVerificationToken": login_token,
            "Email":    email,
            "Password": password,
        },
        timeout=30,
        allow_redirects=True,
    )
    login_resp.raise_for_status()

    # Detect failed login — if redirected back to login page
    final_url  = login_resp.url
    body_lower = login_resp.text.lower()[:1000]
    if "account/login" in final_url.lower() or (
        "nieprawidłow" in body_lower or "invalid" in body_lower
    ):
        raise RuntimeError(
            "Logowanie nie powiodło się — sprawdź e-mail i hasło (CALDIS_EMAIL / CALDIS_PASSWORD)."
        )

    print("  Zalogowano pomyślnie.")

    # Step 2 — Fresh CSRF token + room GUIDs from booking page
    print("Krok 2/3: Pobieranie tokenu CSRF i listy kalendarzy...")
    csrf  = _get_csrf(session, BOOKING_URL)
    rooms = _scrape_room_guids(session)
    print(f"  Znaleziono {len(rooms)} kalendarzy (pokoi).")

    # ISO 8601 UTC format expected by caldis.pl JS layer
    ds = f"{date_start.strftime('%Y-%m-%d')}T00:00:00.000Z"
    de = f"{date_end.strftime('%Y-%m-%d')}T23:59:59.999Z"

    # Build form data as list-of-tuples to support multi-value fields
    form_data: list[tuple[str, str]] = [
        ("__RequestVerificationToken", csrf),
        ("DateStart",                  ds),
        ("DateEnd",                    de),
        ("filterCalendarType",         "List"),
        ("f.Order.Name",               ""),
        ("f.Order.Descending",         "False"),
    ]
    for guid in rooms:
        form_data.append(("filterRoomMultiselect", guid))

    # Step 3 — POST to export endpoint
    print(f"Krok 3/3: Eksport danych {date_start} → {date_end}...")
    export_resp = session.post(EXPORT_URL, data=form_data, timeout=60)
    export_resp.raise_for_status()

    content_type = export_resp.headers.get("Content-Type", "")
    if "spreadsheet" not in content_type and "octet-stream" not in content_type:
        raise RuntimeError(
            f"Serwer zwrócił nieoczekiwany typ pliku: {content_type!r}\n"
            "Sprawdź czy zakres dat jest prawidłowy i czy konto ma dostęp do eksportu."
        )

    output_path.write_bytes(export_resp.content)
    size_kb = len(export_resp.content) // 1024
    print(f"  Zapisano: {output_path.name} ({size_kb} KB)")
    return output_path


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Pobierz wizyty z caldis.pl i zaimportuj do bazy danych.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Przykłady:\n"
            "  python scripts/import_appointments_from_url.py\n"
            "  python scripts/import_appointments_from_url.py --date-start 2026-01-01 --date-end 2026-04-30\n"
            "  python scripts/import_appointments_from_url.py --dry-run --keep-xlsx\n"
            "\n"
            "Zmienne środowiskowe:\n"
            "  CALDIS_EMAIL      email do logowania\n"
            "  CALDIS_PASSWORD   hasło do logowania\n"
        ),
    )
    default_start = (date.today() - timedelta(days=90)).strftime("%Y-%m-%d")
    default_end   = date.today().strftime("%Y-%m-%d")

    parser.add_argument(
        "--date-start",
        default=default_start,
        metavar="YYYY-MM-DD",
        help=f"Początek zakresu dat (domyślnie: {default_start})",
    )
    parser.add_argument(
        "--date-end",
        default=default_end,
        metavar="YYYY-MM-DD",
        help=f"Koniec zakresu dat (domyślnie: {default_end})",
    )
    parser.add_argument(
        "--email",
        default=os.environ.get("CALDIS_EMAIL"),
        help="Email caldis.pl (lub env CALDIS_EMAIL)",
    )
    parser.add_argument(
        "--password",
        default=os.environ.get("CALDIS_PASSWORD"),
        help="Hasło caldis.pl (lub env CALDIS_PASSWORD)",
    )
    parser.add_argument(
        "--keep-xlsx",
        action="store_true",
        help="Zachowaj pobrany plik xlsx po imporcie",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parsuj dane i pokaż statystyki, ale nie zapisuj do bazy",
    )

    args = parser.parse_args()

    # Validate credentials
    if not args.email or not args.password:
        parser.error(
            "Brak danych logowania.\n"
            "Ustaw zmienne środowiskowe CALDIS_EMAIL i CALDIS_PASSWORD\n"
            "lub użyj opcji --email / --password."
        )

    # Validate date range
    try:
        date_start = date.fromisoformat(args.date_start)
        date_end   = date.fromisoformat(args.date_end)
    except ValueError as exc:
        parser.error(f"Nieprawidłowy format daty: {exc}")
        return  # unreachable but satisfies type checkers

    if date_start > date_end:
        parser.error("--date-start musi być wcześniejszy niż --date-end.")

    # -------------------------------------------------------------------------
    # Phase 1 — Download xlsx from caldis.pl
    # -------------------------------------------------------------------------
    temp_dir  = PROJECT_ROOT / "assets" / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    xlsx_name = f"caldis_rezerwacje_{date_start}_{date_end}.xlsx"
    xlsx_path = temp_dir / xlsx_name

    try:
        fetch_xlsx(args.email, args.password, date_start, date_end, xlsx_path)
    except Exception as exc:
        print(f"\n[BŁĄD] Pobieranie nie powiodło się:\n  {exc}")
        sys.exit(1)

    # -------------------------------------------------------------------------
    # Phase 2 — Import into SQLite database
    # -------------------------------------------------------------------------
    print(f"\nBaza danych: {DB_PATH}")
    if args.dry_run:
        print("[DRY-RUN] Zmiany NIE zostaną zapisane do bazy.")
    print("-" * 60)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()

    employee_map = build_employee_map(conn)
    client_map   = build_client_map(conn)
    phone_map    = build_phone_map(conn)
    service_list = build_service_map(conn)

    print(f"Pracownicy w bazie:  {len(employee_map)}")
    print(f"Klienci z telefonem: {len(phone_map)}")
    print(f"Usługi w bazie:      {len(service_list)}")

    stats = import_file(
        xlsx_path, conn,
        employee_map, client_map, phone_map,
        service_list, cursor,
    )

    if args.dry_run:
        conn.rollback()
        print("\n[DRY-RUN] Rollback — baza pozostaje bez zmian.")
    else:
        conn.commit()

    conn.close()

    # -------------------------------------------------------------------------
    # Summary
    # -------------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("PODSUMOWANIE IMPORTU:")
    print(f"  Dodano wizyt:              {stats['inserted']}")
    print(f"  Pominięto (suma=0):        {stats['skipped_zero']}")
    print(f"  Pominięto (brak klienta):  {stats['skipped_no_client']}")
    print(f"  Pominięto (brak pracown.): {stats['skipped_no_employee']}")
    print(f"  Pominięto (duplikaty):     {stats['skipped_duplicate']}")
    print(f"  Błędy:                     {stats['errors']}")

    if args.keep_xlsx:
        print(f"\nPlik xlsx zachowany: {xlsx_path}")
    else:
        xlsx_path.unlink(missing_ok=True)
        print(f"\nUsunięto tymczasowy plik: {xlsx_name}")


if __name__ == "__main__":
    main()
