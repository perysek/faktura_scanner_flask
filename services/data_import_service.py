"""
Data import service — orchestrates the caldis.pl Playwright download +
xlsx parse + PostgreSQL INSERTs for the Flask app's import feature.

This is the in-app equivalent of scripts/import_appointments_playwright.py:
  - DB layer: PostgreSQL via psycopg2 (not SQLite)
  - Execution: synchronous from a background thread (not __main__)
  - Output: structured progress events via callback (not stdout)
  - Audit: writes to import_logs (not just printing summary)

Reuses fetch_xlsx_playwright() from the reference script unchanged.
"""
import asyncio
import json
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Callable, Optional

import pandas as pd
import psycopg2.extensions

from config.database import get_pool
from exceptions import AppError
from repositories.data_import.import_log_repository import ImportLogRepository
from services.data_import_helpers import (
    DEFAULT_SERVICE_ID, KALENDARZ_OVERRIDES,
    build_employee_map, build_client_map, build_phone_map, build_service_map,
    resolve_employee_id, resolve_client_id, resolve_service_id,
    parse_appointment_date, parse_time, parse_created_at,
    calc_duration_minutes,
)

# Imported here so tests can patch it on this module's namespace
from scripts.import_appointments_playwright import fetch_xlsx_playwright

logger = logging.getLogger(__name__)


class ImportError(AppError):
    """Import pipeline failure — maps to HTTP 400."""
    status_code = 400


class DataImportService:
    """Orchestrates a single import run end-to-end."""

    def __init__(self, log_repo: Optional[ImportLogRepository] = None):
        self.log_repo = log_repo or ImportLogRepository()
        self.temp_dir = Path(__file__).resolve().parent.parent / 'assets' / 'temp'

    # ── entry point ──────────────────────────────────────────────────────────
    def run_import(self, import_id: int,
                   date_start: date, date_end: date,
                   dry_run: bool,
                   progress_callback: Callable[[dict], None]) -> dict:
        """Run the full pipeline. Returns the final stats dict.

        Errors are caught, the log row is marked failed, and ImportError is raised
        so the runner can log it.
        """
        stats = self._zero_stats()
        conn: Optional[psycopg2.extensions.connection] = None
        pool = get_pool()
        xlsx_path: Optional[Path] = None

        try:
            self._emit(progress_callback, 'log',
                       f"Start importu (zakres {date_start} → {date_end}, dry_run={dry_run})")

            # ── Phase 1: Playwright download ─────────────────────────────────
            xlsx_path = self._download_xlsx(import_id, date_start, date_end,
                                            progress_callback)

            # ── Phase 2: open thread-local DB connection ─────────────────────
            conn = pool.getconn()

            # ── Phase 3: build lookup maps ───────────────────────────────────
            self._emit(progress_callback, 'log', 'Budowanie tablic wyszukiwania...')
            employee_map = build_employee_map(conn)
            client_map   = build_client_map(conn)
            phone_map    = build_phone_map(conn)
            service_list = build_service_map(conn)
            self._emit(progress_callback, 'log',
                       f"Pracownicy: {len(employee_map)}, "
                       f"klienci: {len(client_map) // 2}, "
                       f"klienci z telefonem: {len(phone_map)}, "
                       f"usługi: {len(service_list)}")

            # ── Phase 4: parse xlsx + insert ─────────────────────────────────
            df = pd.read_excel(xlsx_path, engine='openpyxl', dtype=str)
            df.columns = [c.strip() for c in df.columns]
            self._emit(progress_callback, 'log',
                       f"Wierszy do przetworzenia: {len(df)}")

            for idx, row in df.iterrows():
                self._process_row(row, idx, conn, dry_run, stats,
                                  employee_map, client_map, phone_map, service_list)
                processed = (stats['inserted'] + stats['skipped_zero']
                             + stats['skipped_no_client'] + stats['skipped_no_employee']
                             + stats['skipped_duplicate'] + stats['errors'])
                if processed % 10 == 0 and processed > 0:
                    self.log_repo.update_stats(import_id, stats, conn=conn)
                    self._emit(progress_callback, 'stats', None, stats=stats)

            # ── Phase 5: commit + mark completed ─────────────────────────────
            if not dry_run:
                conn.commit()
            else:
                conn.rollback()

            self.log_repo.mark_completed(import_id, stats, conn=conn)
            skipped = (stats['skipped_zero'] + stats['skipped_no_client']
                       + stats['skipped_no_employee'] + stats['skipped_duplicate'])
            self._emit(progress_callback, 'log',
                       f"Zakończono. Dodano: {stats['inserted']}, "
                       f"pominięto: {skipped}, błędy: {stats['errors']}")
            self._emit(progress_callback, 'status', None, status='completed')
            return stats

        except Exception as exc:
            logger.exception("Import %d failed", import_id)
            error_message = str(exc) or type(exc).__name__
            try:
                self.log_repo.mark_failed(import_id, error_message, stats=stats, conn=conn)
            except Exception:
                logger.exception("Could not write failure status to import_logs")
            if conn is not None:
                if 'Sesja wygasla' in error_message or 'Sesja wygas' in error_message:
                    try:
                        self.log_repo.update_session_status(import_id, 'expired', conn=conn)
                    except Exception:
                        pass
                elif 'Brak zapisanej sesji' in error_message:
                    try:
                        self.log_repo.update_session_status(import_id, 'missing', conn=conn)
                    except Exception:
                        pass
            self._emit(progress_callback, 'log', f"BŁĄD: {error_message}")
            self._emit(progress_callback, 'status', None, status='failed')
            raise ImportError(error_message) from exc

        finally:
            if conn is not None:
                try:
                    pool.putconn(conn)
                except Exception:
                    logger.exception("Could not return connection to pool")
            if xlsx_path is not None and xlsx_path.exists():
                try:
                    xlsx_path.unlink()
                except Exception:
                    logger.warning("Could not delete xlsx %s", xlsx_path)

    # ── helpers ──────────────────────────────────────────────────────────────
    @staticmethod
    def _zero_stats() -> dict:
        return {
            'inserted': 0,
            'skipped_zero': 0,
            'skipped_no_client': 0,
            'skipped_no_employee': 0,
            'skipped_duplicate': 0,
            'errors': 0,
        }

    @staticmethod
    def _emit(callback: Callable[[dict], None], event_type: str,
              message: Optional[str], **extra) -> None:
        """Build a progress event dict and call the callback."""
        event = {
            'type': event_type,
            'message': message,
            'timestamp': datetime.now().isoformat(),
            **extra,
        }
        callback(event)

    def _download_xlsx(self, import_id: int, date_start: date, date_end: date,
                       progress_callback: Callable[[dict], None]) -> Path:
        """Run Playwright download, update session_status accordingly."""
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        xlsx_name = f"caldis_pw_rezerwacje_{date_start}_{date_end}_{import_id}.xlsx"
        xlsx_path = self.temp_dir / xlsx_name
        self._emit(progress_callback, 'log', 'Pobieranie xlsx z caldis.pl (Playwright)...')
        asyncio.run(
            fetch_xlsx_playwright(
                email=None, password=None,
                date_start=date_start, date_end=date_end,
                output_path=xlsx_path,
                headed=False,
            )
        )
        try:
            self.log_repo.update_session_status(import_id, 'active')
        except Exception:
            pass
        self._emit(progress_callback, 'log', f"Pobrano: {xlsx_path.name}")
        return xlsx_path

    def _process_row(self, row, idx: int,
                     conn: psycopg2.extensions.connection,
                     dry_run: bool, stats: dict,
                     employee_map: dict, client_map: dict,
                     phone_map: dict, service_list: list) -> None:
        """Parse + dedupe + insert a single xlsx row. Updates stats in place."""
        try:
            suma_brutto_raw = row.get('Suma brutto', '0')
            try:
                suma_brutto = float(str(suma_brutto_raw).replace(',', '.')) if suma_brutto_raw else 0.0
            except (ValueError, TypeError):
                suma_brutto = 0.0
            if suma_brutto == 0:
                stats['skipped_zero'] += 1
                return

            od_cell       = row.get('Od', '')
            do_cell       = row.get('Do', '')
            imie_cell     = row.get('Imię i nazwisko', row.get('Imie i nazwisko', ''))
            telefon_cell  = row.get('Telefon', '')
            kalendarz_cell = row.get('Kalendarz', '')
            kategoria_cell = row.get('Kategoria', '')

            appointment_date = parse_appointment_date(od_cell)
            start_time       = parse_time(od_cell)
            end_time         = parse_time(do_cell)
            created_at       = parse_created_at(row.get('Data utworzenia', ''))
            duration_minutes = calc_duration_minutes(od_cell, do_cell)

            if not (appointment_date and start_time and end_time):
                stats['errors'] += 1
                return

            kal_lower = str(kalendarz_cell).strip().lower() if kalendarz_cell else ''
            if kal_lower in KALENDARZ_OVERRIDES:
                employee_id, forced_service_id = KALENDARZ_OVERRIDES[kal_lower]
            else:
                employee_id = resolve_employee_id(kalendarz_cell, employee_map)
                forced_service_id = None

            if employee_id is None:
                stats['skipped_no_employee'] += 1
                return

            client_id = resolve_client_id(imie_cell, client_map, telefon_cell, phone_map)
            if client_id is None:
                stats['skipped_no_client'] += 1
                return

            # Duplicate check
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT 1 FROM appointments
                WHERE employee_id = %s AND appointment_date = %s AND start_time = %s
                  AND is_deleted = FALSE
                """,
                (employee_id, appointment_date, start_time),
            )
            if cursor.fetchone() is not None:
                stats['skipped_duplicate'] += 1
                return

            service_id = (forced_service_id if forced_service_id is not None
                          else resolve_service_id(kategoria_cell, service_list))

            cursor.execute("SELECT commission_rate FROM employees WHERE id = %s",
                           (employee_id,))
            emp_row = cursor.fetchone()
            commission_rate = float(emp_row['commission_rate'] or 0) if emp_row else 0.0
            commission_amount = round(suma_brutto * commission_rate / 100, 2)
            total_price = round(suma_brutto, 2)

            if dry_run:
                stats['inserted'] += 1
                return

            # INSERT appointments
            cursor.execute(
                """
                INSERT INTO appointments (
                    client_id, employee_id, status,
                    appointment_date, start_time, end_time,
                    total_price, total_duration, discount_amount,
                    created_at, updated_at
                ) VALUES (%s, %s, 'completed', %s, %s, %s, %s, %s, 0, %s, %s)
                RETURNING id
                """,
                (client_id, employee_id,
                 appointment_date, start_time, end_time,
                 total_price, duration_minutes,
                 created_at, created_at),
            )
            appointment_id = cursor.fetchone()['id']

            # INSERT appointment_services
            cursor.execute(
                """
                INSERT INTO appointment_services (
                    appointment_id, service_id, price_charged, duration_minutes,
                    commission_rate, commission_amount, is_addon
                ) VALUES (%s, %s, %s, %s, %s, %s, FALSE)
                """,
                (appointment_id, service_id, total_price, duration_minutes,
                 commission_rate, commission_amount),
            )

            # INSERT income_records
            cursor.execute(
                """
                INSERT INTO income_records (
                    appointment_id, client_id, employee_id,
                    total_amount, discount_amount, net_amount, commission_total,
                    payment_date, created_at
                ) VALUES (%s, %s, %s, %s, 0, %s, %s, %s, %s)
                """,
                (appointment_id, client_id, employee_id,
                 total_price, total_price, commission_amount,
                 appointment_date, created_at),
            )

            # UPDATE clients.last_visit_date
            cursor.execute(
                """
                UPDATE clients
                SET last_visit_date = %s
                WHERE id = %s
                  AND (last_visit_date IS NULL OR last_visit_date < %s)
                """,
                (appointment_date, client_id, appointment_date),
            )

            stats['inserted'] += 1

        except Exception:
            logger.exception("Error processing row %d", idx)
            stats['errors'] += 1
