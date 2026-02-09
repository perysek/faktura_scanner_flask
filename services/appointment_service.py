"""
Serwis zarządzania wizytami — orkiestracja rezerwacji, statusów, mikrousług i przychodów.
"""
from datetime import date, time, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional

from database.models import (
    Appointment, AppointmentService, IncomeRecord
)
from repositories.appointments.appointment_repository import AppointmentRepository
from repositories.appointments.appointment_service_repository import AppointmentServiceRepository
from repositories.appointments.income_repository import IncomeRepository
from repositories.clients.client_repository import ClientRepository
from repositories.services.service_addon_repository import ServiceAddonRepository
from repositories.employees.employee_service_repository import EmployeeServiceRepository
from services.pricing_service import PricingService


# Dozwolone przejścia statusów
STATUS_TRANSITIONS = {
    'scheduled': ['confirmed', 'cancelled', 'no_show'],
    'confirmed': ['in_progress', 'cancelled'],
    'in_progress': ['completed', 'cancelled'],
}


class AppointmentError(Exception):
    """Błąd operacji na wizycie"""
    pass


class AppointmentBusinessService:
    """Serwis biznesowy wizyt — nie mylić z AppointmentService (model)"""

    def __init__(self):
        self.appt_repo = AppointmentRepository()
        self.appt_svc_repo = AppointmentServiceRepository()
        self.income_repo = IncomeRepository()
        self.client_repo = ClientRepository()
        self.addon_repo = ServiceAddonRepository()
        self.emp_svc_repo = EmployeeServiceRepository()
        self.pricing = PricingService()

    def create_appointment(self, client_id: int, employee_id: int,
                            service_ids: List[int], appt_date: date,
                            start_time: time, notes: Optional[str] = None,
                            created_by: Optional[int] = None) -> dict:
        """Utwórz nową wizytę z usługami.

        Kroki:
        1. Oblicz cenę i czas dla każdej usługi (COALESCE)
        2. Oblicz end_time na podstawie łącznego czasu
        3. Sprawdź konflikty czasowe
        4. Utwórz wizytę + appointment_services ze snapshotem cen

        Returns: dict z appointment_id i szczegółami
        Raises: AppointmentError jeśli walidacja nie przejdzie
        """
        # 1. Rozwiąż cenę dla wszystkich usług
        calculation = self.pricing.calculate_appointment_total(employee_id, service_ids)
        if not calculation:
            raise AppointmentError(
                "Pracownik nie może wykonać jednej lub więcej wybranych usług"
            )

        # 2. Oblicz end_time
        total_duration = calculation['total_duration']
        start_dt = datetime.combine(appt_date, start_time)
        end_dt = start_dt + timedelta(minutes=total_duration)
        end_time = end_dt.time()

        # 3. Sprawdź konflikty
        conflicts = self.appt_repo.check_conflicts(
            employee_id, appt_date, start_time, end_time
        )
        if conflicts:
            raise AppointmentError(
                f"Konflikt czasowy — pracownik ma {len(conflicts)} kolidującą wizytę/y"
            )

        # 4. Utwórz wizytę
        appointment = Appointment(
            client_id=client_id,
            employee_id=employee_id,
            appointment_date=appt_date,
            start_time=start_time,
            end_time=end_time,
            total_price=calculation['total_price'],
            total_duration=total_duration,
            notes=notes,
            created_by=created_by
        )
        appointment_id = self.appt_repo.create(appointment)

        # 5. Dodaj usługi ze snapshotem cenowym
        for svc in calculation['breakdown']:
            appt_svc = AppointmentService(
                appointment_id=appointment_id,
                service_id=svc['service_id'],
                price_charged=svc['effective_price'],
                duration_minutes=svc['effective_duration'],
                commission_rate=svc['effective_commission'],
                commission_amount=svc['commission_amount']
            )
            self.appt_svc_repo.add_service(appt_svc)

        return {
            'appointment_id': appointment_id,
            'total_price': calculation['total_price'],
            'total_duration': total_duration,
            'end_time': end_time.strftime('%H:%M'),
            'services_count': len(service_ids)
        }

    def transition_status(self, appointment_id: int, new_status: str,
                           cancellation_reason: Optional[str] = None) -> bool:
        """Zmień status wizyty z walidacją przepływu.

        Raises: AppointmentError jeśli przejście jest niedozwolone.
        """
        row = self.appt_repo.get_by_id(appointment_id)
        if not row:
            raise AppointmentError("Wizyta nie istnieje")

        current_status = row['status']
        allowed = STATUS_TRANSITIONS.get(current_status, [])

        if new_status not in allowed:
            raise AppointmentError(
                f"Nie można zmienić statusu z '{current_status}' na '{new_status}'. "
                f"Dozwolone: {', '.join(allowed) if allowed else 'brak'}"
            )

        return self.appt_repo.update_status(
            appointment_id, new_status, cancellation_reason
        )

    def complete_appointment(self, appointment_id: int,
                              payment_method: Optional[str] = None,
                              discount_amount: Optional[Decimal] = None) -> dict:
        """Zamknij wizytę — utwórz rekord przychodu.

        Kroki:
        1. Waliduj status (musi być in_progress)
        2. Oblicz sumy (main + addon)
        3. Utwórz income_record
        4. Zmień status na completed
        5. Zaktualizuj last_visit_date klienta

        Returns: dict z podsumowaniem finansowym
        """
        row = self.appt_repo.get_by_id(appointment_id)
        if not row:
            raise AppointmentError("Wizyta nie istnieje")

        if row['status'] != 'in_progress':
            raise AppointmentError(
                f"Wizytę można zamknąć tylko ze statusu 'in_progress', "
                f"aktualny status: '{row['status']}'"
            )

        # Sprawdź czy nie ma już rekordu przychodu
        existing = self.income_repo.get_by_appointment(appointment_id)
        if existing:
            raise AppointmentError("Wizyta ma już rekord przychodu")

        # Oblicz sumy
        totals = self.appt_svc_repo.get_appointment_totals(appointment_id)
        total_amount = totals['total_price']
        disc = discount_amount or Decimal(str(row['discount_amount'] or '0'))
        net_amount = total_amount - disc
        commission_total = totals['total_commission']

        # Utwórz income_record
        income = IncomeRecord(
            appointment_id=appointment_id,
            client_id=row['client_id'],
            employee_id=row['employee_id'],
            total_amount=total_amount,
            discount_amount=disc,
            net_amount=net_amount,
            commission_total=commission_total,
            payment_method=payment_method,
            payment_date=date.today()
        )
        income_id = self.income_repo.create(income)

        # Zaktualizuj status
        self.appt_repo.update_status(appointment_id, 'completed')

        # Zaktualizuj total_price na wizyt (mogło się zmienić po addonach)
        self.appt_repo.update_total_price(appointment_id, total_amount)

        # Zaktualizuj last_visit_date klienta
        self.client_repo.update_last_visit(row['client_id'], date.today())

        return {
            'income_id': income_id,
            'total_amount': total_amount,
            'discount_amount': disc,
            'net_amount': net_amount,
            'commission_total': commission_total,
            'main_total': totals['main_total'],
            'addon_total': totals['addon_total'],
            'addon_count': totals['addon_count'],
            'payment_method': payment_method
        }

    def cancel_appointment(self, appointment_id: int,
                            reason: Optional[str] = None) -> bool:
        """Anuluj wizytę."""
        return self.transition_status(appointment_id, 'cancelled', reason)

    def add_addon_to_appointment(self, appointment_id: int,
                                  addon_service_id: int) -> dict:
        """Dodaj mikrousługę do trwającej wizyty.

        Walidacje:
        1. Wizyta musi mieć status 'in_progress'
        2. Usługa musi być typu 'addon'
        3. Mikrousługa musi być kompatybilna z min. jedną usługą główną wizyty
        4. Pracownik musi móc wykonać tę usługę
        5. Mikrousługa nie może być już dodana

        Cena jest snapshot'owana w momencie dodania (nie przy rezerwacji).
        """
        # 1. Sprawdź status wizyty
        appt_row = self.appt_repo.get_by_id(appointment_id)
        if not appt_row:
            raise AppointmentError("Wizyta nie istnieje")

        if appt_row['status'] != 'in_progress':
            raise AppointmentError(
                "Mikrousługi można dodawać tylko do wizyt w trakcie (status: in_progress)"
            )

        # 2. Sprawdź czy już dodana
        if self.appt_svc_repo.is_addon_already_added(appointment_id, addon_service_id):
            raise AppointmentError("Ta mikrousługa została już dodana do tej wizyty")

        # 3. Sprawdź czy pracownik może wykonać usługę
        employee_id = appt_row['employee_id']
        if not self.emp_svc_repo.can_perform(employee_id, addon_service_id):
            raise AppointmentError(
                "Pracownik nie może wykonać tej mikrousługi"
            )

        # 4. Sprawdź kompatybilność z usługami głównymi wizyty
        main_services = self.appt_svc_repo.get_main_services(appointment_id)
        main_service_ids = [row['service_id'] for row in main_services]

        compatible_addons = self.addon_repo.get_compatible_addons_for_services(main_service_ids)
        compatible_addon_ids = {row['id'] for row in compatible_addons}

        if addon_service_id not in compatible_addon_ids:
            raise AppointmentError(
                "Mikrousługa nie jest kompatybilna z usługami głównymi tej wizyty"
            )

        # 5. Rozwiąż cenę (snapshot w momencie dodania)
        pricing = self.pricing.resolve_full(employee_id, addon_service_id)
        if not pricing:
            raise AppointmentError("Nie można rozwiązać ceny mikrousługi")

        # 6. Dodaj do wizyty
        appt_svc = AppointmentService(
            appointment_id=appointment_id,
            service_id=addon_service_id,
            price_charged=pricing['effective_price'],
            duration_minutes=pricing['effective_duration'],
            commission_rate=pricing['effective_commission'],
            commission_amount=pricing['commission_amount'],
            is_addon=True
        )
        svc_id = self.appt_svc_repo.add_addon_service(appt_svc)

        # 7. Zaktualizuj total_price wizyty (addony zwiększają cenę)
        totals = self.appt_svc_repo.get_appointment_totals(appointment_id)
        self.appt_repo.update_total_price(appointment_id, totals['total_price'])

        return {
            'appointment_service_id': svc_id,
            'service_name': pricing['service_name'],
            'price_charged': pricing['effective_price'],
            'commission_amount': pricing['commission_amount'],
            'new_total': totals['total_price']
        }

    def get_available_addons(self, appointment_id: int) -> List[dict]:
        """Pobierz dostępne mikrousługi dla wizyty.

        Filtruje po:
        1. Kompatybilność z usługami głównymi (UNION)
        2. Pracownik może wykonać
        3. Nie dodano jeszcze do wizyty
        """
        appt_row = self.appt_repo.get_by_id(appointment_id)
        if not appt_row:
            return []

        employee_id = appt_row['employee_id']

        # Pobierz usługi główne wizyty
        main_services = self.appt_svc_repo.get_main_services(appointment_id)
        main_service_ids = [row['service_id'] for row in main_services]

        if not main_service_ids:
            return []

        # Pobierz kompatybilne addony (UNION)
        compatible = self.addon_repo.get_compatible_addons_for_services(main_service_ids)

        available = []
        for addon_row in compatible:
            addon_id = addon_row['id']

            # Filtruj: pracownik musi móc wykonać
            if not self.emp_svc_repo.can_perform(employee_id, addon_id):
                continue

            # Filtruj: nie dodano jeszcze
            if self.appt_svc_repo.is_addon_already_added(appointment_id, addon_id):
                continue

            # Rozwiąż cenę
            pricing = self.pricing.resolve_full(employee_id, addon_id)
            if pricing:
                available.append({
                    'service_id': addon_id,
                    'service_name': addon_row['name'],
                    'category': addon_row['category'],
                    'price': pricing['effective_price'],
                    'duration': pricing['effective_duration'],
                })

        return available

    def get_available_slots(self, employee_id: int, slot_date: date,
                             duration_minutes: int,
                             work_start: time = time(9, 0),
                             work_end: time = time(18, 0),
                             slot_interval: int = 30) -> List[dict]:
        """Pobierz wolne sloty czasowe dla pracownika na dany dzień.

        Generuje sloty co `slot_interval` minut i sprawdza konflikty.
        """
        slots = []
        current = datetime.combine(slot_date, work_start)
        end_boundary = datetime.combine(slot_date, work_end)

        while current + timedelta(minutes=duration_minutes) <= end_boundary:
            slot_start = current.time()
            slot_end = (current + timedelta(minutes=duration_minutes)).time()

            conflicts = self.appt_repo.check_conflicts(
                employee_id, slot_date, slot_start, slot_end
            )

            slots.append({
                'start_time': slot_start.strftime('%H:%M'),
                'end_time': slot_end.strftime('%H:%M'),
                'available': len(conflicts) == 0
            })

            current += timedelta(minutes=slot_interval)

        return slots

    def get_appointment_details(self, appointment_id: int) -> Optional[dict]:
        """Pobierz pełne szczegóły wizyty z usługami i danymi klienta/pracownika."""
        appt_row = self.appt_repo.get_by_id_with_details(appointment_id)
        if not appt_row:
            return None

        services = self.appt_svc_repo.get_all_for_appointment(appointment_id)
        totals = self.appt_svc_repo.get_appointment_totals(appointment_id)

        main_services = [s for s in services if not s['is_addon']]
        addon_services = [s for s in services if s['is_addon']]

        return {
            'appointment': dict(appt_row),
            'main_services': [dict(s) for s in main_services],
            'addon_services': [dict(s) for s in addon_services],
            'totals': totals,
            'can_add_addon': appt_row['status'] == 'in_progress'
        }
