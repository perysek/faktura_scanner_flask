"""
Serwis zarządzania nieobecnościami pracowników.

Obsługuje cykl życia wniosków, manualnych nieobecności (L4), i kategorii.
Odpowiada za walidację, sprawdzanie konfliktów z wizytami klientów,
i zatwierdzanie/odrzucanie wniosków.
"""
from datetime import datetime, date, time
from typing import List, Optional

from database.models import EmployeeAbsence
from exceptions import AppError
from repositories.absences.absence_category_repository import AbsenceCategoryRepository
from repositories.absences.absence_repository import AbsenceRepository
from repositories.absences.employee_supervisor_repository import EmployeeSupervisorRepository
from repositories.employees.employee_repository import EmployeeRepository


class AbsenceError(AppError):
    """Błąd operacji na nieobecności."""
    status_code = 400


class AbsenceService:
    """Orkiestracja wniosków o nieobecności i manualnych rejestracji."""

    def __init__(self):
        self.absence_repo = AbsenceRepository()
        self.category_repo = AbsenceCategoryRepository()
        self.supervisor_repo = EmployeeSupervisorRepository()
        self.employee_repo = EmployeeRepository()

    # ── submission ────────────────────────────────────────────────────────────

    def submit_request(self, employee_id: int, category_id: int,
                       date_from: date, date_to: date,
                       time_from: Optional[time], time_to: Optional[time],
                       approver_employee_id: int,
                       notes: Optional[str] = None,
                       created_by: Optional[int] = None) -> int:
        """Złóż wniosek o nieobecność.

        Waliduje kategorię, uprawnienia przełożonego, spójność pól czasowych
        oraz brak nakładających się wniosków. Tworzy rekord ze status='pending'.

        Returns: ID nowej nieobecności
        Raises: AbsenceError przy naruszeniu walidacji
        """
        cat_row = self.category_repo.get_by_id(category_id)
        if not cat_row or cat_row['is_deleted']:
            raise AbsenceError("Nieprawidłowa kategoria nieobecności")

        full_day = bool(cat_row['absence_full_day'])
        if full_day:
            if time_from is not None or time_to is not None:
                raise AbsenceError("Kategoria całodniowa — pola godzinowe muszą być puste")
            if date_to < date_from:
                raise AbsenceError("Data zakończenia nie może być wcześniejsza niż data rozpoczęcia")
        else:
            if time_from is None or time_to is None:
                raise AbsenceError("Kategoria slotowa — wymagane pola time_from i time_to")
            if time_to <= time_from:
                raise AbsenceError("Godzina zakończenia musi być późniejsza niż godzina rozpoczęcia")
            date_to = date_from  # D5: time-slot absences always span a single day

        supervisors = self.supervisor_repo.list_supervisors_for(employee_id)
        supervisor_ids = {row['id'] for row in supervisors}
        if approver_employee_id not in supervisor_ids:
            raise AbsenceError("Wybrany przełożony nie jest przypisany do tego pracownika")

        conflicts = self.absence_repo.check_absence_conflicts(
            employee_id, date_from, date_to, time_from, time_to
        )
        if conflicts:
            raise AbsenceError(
                f"Wniosek koliduje z istniejącą nieobecnością: "
                f"{conflicts[0]['category_name']} ({conflicts[0]['date_from']})"
            )

        absence = EmployeeAbsence(
            employee_id=employee_id,
            category_id=category_id,
            date_from=date_from,
            date_to=date_to,
            time_from=time_from,
            time_to=time_to,
            approver_id=approver_employee_id,
            status='pending',
            notes=notes,
            source='request',
            created_by=created_by,
        )
        return self.absence_repo.create(absence)

    # ── approval flow ─────────────────────────────────────────────────────────

    def approve(self, absence_id: int, approver_employee_id: int) -> dict:
        """Zatwierdź wniosek.

        Sprawdza konflikty z wizytami klientów przed zatwierdzeniem.

        Returns:
            {'status': 'approved'} — sukces, brak konfliktów
            {'status': 'conflict', 'conflicts': [...]} — są kolidujące wizyty
        Raises: AbsenceError jeśli wniosek nie istnieje lub brak uprawnień
        """
        row = self._get_pending_or_raise(absence_id, approver_employee_id)

        appt_conflicts = self.absence_repo.get_overlapping_appointments(
            row['employee_id'],
            row['date_from'],
            row['date_to'],
            row['time_from'],
            row['time_to'],
        )

        if appt_conflicts:
            return {
                'status': 'conflict',
                'conflicts': [self._format_appt_conflict(c) for c in appt_conflicts],
            }

        self.absence_repo.respond(absence_id, 'approved', approver_employee_id)
        return {'status': 'approved'}

    def force_approve(self, absence_id: int, approver_employee_id: int) -> None:
        """Zatwierdź wniosek pomijając konflikty z wizytami (po ręcznej rozgrywce)."""
        self._get_pending_or_raise(absence_id, approver_employee_id)
        self.absence_repo.respond(absence_id, 'approved', approver_employee_id)

    def reject(self, absence_id: int, approver_employee_id: int,
               rejection_reason: str) -> None:
        """Odrzuć wniosek. rejection_reason jest wymagany (wymuszane przez DB constraint)."""
        if not rejection_reason or not rejection_reason.strip():
            raise AbsenceError("Powód odrzucenia jest wymagany")
        self._get_pending_or_raise(absence_id, approver_employee_id)
        self.absence_repo.respond(absence_id, 'rejected', approver_employee_id,
                                  rejection_reason=rejection_reason.strip())

    def cancel_own(self, absence_id: int, employee_id: int) -> None:
        """Anuluj własny wniosek (tylko status=pending). D8."""
        row = self.absence_repo.get_by_id(absence_id)
        if not row:
            raise AbsenceError("Wniosek nie istnieje")
        if row['employee_id'] != employee_id:
            raise AbsenceError("Brak uprawnień do anulowania tego wniosku")
        if row['status'] != 'pending':
            raise AbsenceError("Można anulować tylko wnioski oczekujące na zatwierdzenie")
        self.absence_repo.cancel(absence_id)

    # ── manual creation (supervisor) ──────────────────────────────────────────

    def create_manual(self, employee_id: int, category_id: int,
                      date_from: date, date_to: date,
                      time_from: Optional[time], time_to: Optional[time],
                      notes: Optional[str],
                      creator_employee_id: int,
                      created_by: Optional[int] = None) -> dict:
        """Utwórz nieobecność manualnie (np. L4).

        Auto-zatwierdzona, source='manual', approver_id = creator_employee_id. D6.
        Zwraca dict {'absence_id': ..., 'conflicts': [...]} — konflikty są ostrzeżeniem,
        nie blokują zapisu (force-create; supervisor świadomie wprowadza L4).
        """
        cat_row = self.category_repo.get_by_id(category_id)
        if not cat_row or cat_row['is_deleted']:
            raise AbsenceError("Nieprawidłowa kategoria nieobecności")

        full_day = bool(cat_row['absence_full_day'])
        if not full_day:
            if time_from is None or time_to is None:
                raise AbsenceError("Kategoria slotowa wymaga pól godzinowych")
            if time_to <= time_from:
                raise AbsenceError("Godzina zakończenia musi być późniejsza niż rozpoczęcia")
            date_to = date_from
        else:
            time_from = None
            time_to = None

        now = datetime.now()
        absence = EmployeeAbsence(
            employee_id=employee_id,
            category_id=category_id,
            date_from=date_from,
            date_to=date_to,
            time_from=time_from,
            time_to=time_to,
            approver_id=creator_employee_id,
            status='approved',
            notes=notes,
            source='manual',
            requested_at=now,
            responded_at=now,
            created_by=created_by,
        )
        absence_id = self.absence_repo.create(absence)

        appt_conflicts = self.absence_repo.get_overlapping_appointments(
            employee_id, date_from, date_to, time_from, time_to
        )
        return {
            'absence_id': absence_id,
            'conflicts': [self._format_appt_conflict(c) for c in appt_conflicts],
        }

    def update_manual(self, absence_id: int, category_id: int,
                      date_from: date, date_to: date,
                      time_from: Optional[time], time_to: Optional[time],
                      notes: Optional[str]) -> dict:
        """Edytuj manualną nieobecność. Przeliczy konflikty z wizytami."""
        row = self.absence_repo.get_by_id(absence_id)
        if not row:
            raise AbsenceError("Nieobecność nie istnieje")
        if row['source'] != 'manual':
            raise AbsenceError("Można edytować tylko ręcznie dodane nieobecności")

        cat_row = self.category_repo.get_by_id(category_id)
        if not cat_row or cat_row['is_deleted']:
            raise AbsenceError("Nieprawidłowa kategoria nieobecności")

        full_day = bool(cat_row['absence_full_day'])
        if not full_day:
            if time_from is None or time_to is None:
                raise AbsenceError("Kategoria slotowa wymaga pól godzinowych")
            if time_to <= time_from:
                raise AbsenceError("Godzina zakończenia musi być późniejsza niż rozpoczęcia")
            date_to = date_from
        else:
            time_from = None
            time_to = None

        updated = EmployeeAbsence(
            employee_id=row['employee_id'],
            category_id=category_id,
            date_from=date_from,
            date_to=date_to,
            time_from=time_from,
            time_to=time_to,
            notes=notes,
        )
        self.absence_repo.update(absence_id, updated)

        appt_conflicts = self.absence_repo.get_overlapping_appointments(
            row['employee_id'], date_from, date_to, time_from, time_to
        )
        return {'conflicts': [self._format_appt_conflict(c) for c in appt_conflicts]}

    def soft_delete(self, absence_id: int) -> None:
        if not self.absence_repo.soft_delete(absence_id):
            raise AbsenceError("Nieobecność nie istnieje lub już usunięta")

    # ── list helpers ──────────────────────────────────────────────────────────

    def list_for_employee(self, employee_id: int,
                           status_in: Optional[List[str]] = None) -> List[dict]:
        return [dict(r) for r in self.absence_repo.list_for_employee(employee_id, status_in)]

    def list_for_approver(self, approver_employee_id: int,
                           status_in: Optional[List[str]] = None) -> List[dict]:
        return [dict(r) for r in self.absence_repo.list_for_approver(approver_employee_id, status_in)]

    def list_all(self, **filters) -> List[dict]:
        return [dict(r) for r in self.absence_repo.list_all(**filters)]

    # ── private ───────────────────────────────────────────────────────────────

    def _get_pending_or_raise(self, absence_id: int, approver_employee_id: int):
        """Pobierz oczekujący wniosek i zweryfikuj uprawnienia przełożonego."""
        row = self.absence_repo.get_by_id(absence_id)
        if not row:
            raise AbsenceError("Wniosek nie istnieje")
        if row['status'] != 'pending':
            raise AbsenceError(f"Wniosek ma status '{row['status']}' — nie można go zatwierdzić/odrzucić")
        if row['approver_id'] != approver_employee_id:
            raise AbsenceError("Nie jesteś wskazanym przełożonym dla tego wniosku")
        return row

    @staticmethod
    def _format_appt_conflict(row) -> dict:
        return {
            'appointment_id': row['id'],
            'date': row['appointment_date'].isoformat() if hasattr(row['appointment_date'], 'isoformat') else str(row['appointment_date']),
            'start_time': str(row['start_time']),
            'end_time': str(row['end_time']),
            'client_name': row['client_name'],
            'service_name': row['service_name'],
        }
