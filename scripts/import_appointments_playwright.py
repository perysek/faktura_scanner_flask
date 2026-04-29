"""
import_appointments_playwright.py

Pobiera plik Rezerwacje.xlsx z caldis.pl za pomocą Playwright (Chromium headless),
a następnie importuje wizyty do lokalnej bazy SQLite używając tej samej logiki co
import_appointments_from_excel.py.

Playwright steruje prawdziwą przeglądarką — klika dropdown "Eksportuj do .xlsx"
i przechwytuje pobrany plik. To najbardziej odporna metoda, niezależna od
struktury formularzy backendowych.

Użycie:
    python scripts/import_appointments_playwright.py [OPCJE]

Opcje:
    --date-start YYYY-MM-DD  Początek zakresu (domyślnie: 90 dni temu)
    --date-end   YYYY-MM-DD  Koniec zakresu   (domyślnie: dzisiaj)
    --email      TEXT        Email caldis.pl  (lub env CALDIS_EMAIL)
    --password   TEXT        Hasło caldis.pl  (lub env CALDIS_PASSWORD)
    --keep-xlsx              Zachowaj xlsx po imporcie
    --dry-run                Parsuj i pokaż statystyki, nie zapisuj do bazy
    --headed                 Uruchom przeglądarkę w trybie widocznym (debug)

Wymagania (jednorazowa instalacja):
    pip install playwright pandas
    python -m playwright install chromium

Zmienne środowiskowe:
    CALDIS_EMAIL     – email do caldis.pl
    CALDIS_PASSWORD  – hasło do caldis.pl
"""

import argparse
import asyncio
import os
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR  = PROJECT_ROOT / "scripts"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SCRIPTS_DIR))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(PROJECT_ROOT / ".env.local", override=True)

from config.settings import DB_PATH
from import_appointments_from_excel import (
    build_client_map,
    build_employee_map,
    build_phone_map,
    build_service_map,
    import_file,
)

CALDIS_BASE        = "https://caldis.pl"
CALDIS_LOGIN_URL   = f"{CALDIS_BASE}/logowanie"
CALDIS_BOOKING_URL = f"{CALDIS_BASE}/Booking"

# Session state saved here so subsequent headless runs skip login entirely
SESSION_FILE = PROJECT_ROOT / "assets" / "temp" / "caldis_session.json"


# ---------------------------------------------------------------------------
# Playwright download
# ---------------------------------------------------------------------------

async def fetch_xlsx_playwright(
    email: str,
    password: str,
    date_start: date,
    date_end: date,
    output_path: Path,
    headed: bool = False,
) -> Path:
    """
    Download the Rezerwacje.xlsx export from caldis.pl using Playwright.

    Session persistence strategy:
      - First run (no saved session): requires --headed so the user can log in
        manually in the visible browser window. reCAPTCHA v3 blocks all
        programmatic login attempts — only a real visible browser passes it.
        After login the session is saved to caldis_session.json automatically.
      - Subsequent runs: loads saved session, navigates directly to /Booking,
        no login step needed. If the session has expired, prompts to re-run
        with --headed.

    Returns:
        output_path - path to the downloaded xlsx file.
    Raises:
        RuntimeError on authentication failure or missing export button.
    """
    from playwright.async_api import async_playwright, TimeoutError as PwTimeout

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=not headed)

        # Load saved session if it exists
        storage_kwarg = (
            {"storage_state": str(SESSION_FILE)} if SESSION_FILE.exists() else {}
        )
        ctx  = await browser.new_context(accept_downloads=True, **storage_kwarg)
        page = await ctx.new_page()

        # Step 1 — Ensure authenticated session
        print("Krok 1/4: Sprawdzanie sesji caldis.pl...")
        await page.goto(CALDIS_BOOKING_URL, wait_until="networkidle")

        if "logowanie" in page.url.lower():
            if not headed:
                await browser.close()
                session_hint = (
                    "  Sesja wygasla." if SESSION_FILE.exists()
                    else "  Brak zapisanej sesji."
                )
                raise RuntimeError(
                    f"{session_hint}\n"
                    "Uruchom raz z flaga --headed, zaloguj sie recznie w przegladarce:\n"
                    "  python scripts/import_appointments_playwright.py --headed\n"
                    "Sesja zostanie zapisana i kolejne uruchomienia beda headless."
                )

            # Headed mode — wait for user to complete login (including reCAPTCHA)
            await page.goto(CALDIS_LOGIN_URL, wait_until="networkidle")
            print("  Zaloguj sie recznie w oknie przegladarki (czekam do 2 minut)...")
            await page.wait_for_url(
                lambda url: "logowanie" not in url.lower(), timeout=120_000
            )
            print("  Zalogowano pomyslnie!")

            SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
            await ctx.storage_state(path=str(SESSION_FILE))
            print(f"  Sesja zapisana: {SESSION_FILE.name}")

            await page.goto(CALDIS_BOOKING_URL, wait_until="networkidle")
        else:
            print("  Sesja aktywna.")

        # Step 2 — Set date filter via JS (bypasses datepicker widget)
        print("Krok 2/4: Ustawianie zakresu dat...")
        ds = f"{date_start.strftime('%Y-%m-%d')}T00:00:00.000Z"
        de = f"{date_end.strftime('%Y-%m-%d')}T23:59:59.999Z"
        await page.evaluate(f"""
            const dsEl = document.getElementById('DateStart');
            const deEl = document.getElementById('DateEnd');
            if (dsEl) dsEl.value = '{ds}';
            if (deEl) deEl.value = '{de}';
        """)
        try:
            await page.wait_for_selector(
                "#table-booking-list tbody tr", timeout=15_000
            )
        except PwTimeout:
            print("  [INFO] Tabela nie zaladowala sie w czasie - kontynuuje.")
        print(f"  Zakres: {date_start} -> {date_end}")

        # Step 3 — Open the "..." actions dropdown
        print("Krok 3/4: Otwieranie menu eksportu...")
        try:
            await page.click("#dropdownMenuSend", timeout=10_000)
            await page.wait_for_selector(
                '[data-export-bookings]', state="visible", timeout=10_000
            )
        except PwTimeout:
            await browser.close()
            raise RuntimeError(
                "Nie znaleziono przycisku '#dropdownMenuSend'.\n"
                "Sprawdz czy strona caldis.pl nie zmienila struktury UI."
            )

        # Step 4 — Intercept file download
        print("Krok 4/4: Pobieranie pliku xlsx...")
        async with page.expect_download(timeout=60_000) as dl_info:
            await page.click('[data-export-bookings="/BookingExport/ExportToXlsx"]')

        download = await dl_info.value
        output_path.parent.mkdir(parents=True, exist_ok=True)
        await download.save_as(str(output_path))

        size_kb = output_path.stat().st_size // 1024
        print(f"  Zapisano: {output_path.name} ({size_kb} KB)")
        await browser.close()

    return output_path


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Pobierz wizyty z caldis.pl (Playwright/Chromium) i zaimportuj do bazy danych."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Przykłady:\n"
            "  python scripts/import_appointments_playwright.py\n"
            "  python scripts/import_appointments_playwright.py "
            "--date-start 2026-01-01 --date-end 2026-04-30\n"
            "  python scripts/import_appointments_playwright.py --dry-run --keep-xlsx\n"
            "  python scripts/import_appointments_playwright.py --headed  # tryb widoczny\n"
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
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Uruchom przeglądarkę w trybie widocznym (przydatne do debugowania)",
    )

    args = parser.parse_args()

    if not args.email or not args.password:
        parser.error(
            "Brak danych logowania.\n"
            "Ustaw zmienne środowiskowe CALDIS_EMAIL i CALDIS_PASSWORD\n"
            "lub użyj opcji --email / --password."
        )

    try:
        date_start = date.fromisoformat(args.date_start)
        date_end   = date.fromisoformat(args.date_end)
    except ValueError as exc:
        parser.error(f"Nieprawidłowy format daty: {exc}")
        return

    if date_start > date_end:
        parser.error("--date-start musi być wcześniejszy niż --date-end.")

    # -------------------------------------------------------------------------
    # Phase 1 — Download xlsx via Playwright
    # -------------------------------------------------------------------------
    temp_dir  = PROJECT_ROOT / "assets" / "temp"
    xlsx_name = f"caldis_pw_rezerwacje_{date_start}_{date_end}.xlsx"
    xlsx_path = temp_dir / xlsx_name

    try:
        asyncio.run(
            fetch_xlsx_playwright(
                args.email, args.password,
                date_start, date_end,
                xlsx_path,
                headed=args.headed,
            )
        )
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
