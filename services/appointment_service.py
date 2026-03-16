"""
Serwis zarządzania wizytami — orkiestracja rezerwacji, statusów, mikrousług i przychodów.
"""
from datetime import date, time, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional

from database.models import (
    Appointment, AppointmentService, IncomeRecord
)
from config.appointment_statuses import AppointmentStatus
from repositories.appointments.appointment_repository import AppointmentRepository
from repositories.appointments.appointment_service_repository import AppointmentServiceRepository
from repositories.appointments.income_repository import IncomeRepository
from repositories.clients.client_repository import ClientRepository
from repositories.services.service_addon_repository import ServiceAddonRepository
from repositories.employees.employee_service_repository import EmployeeServiceRepository
from services.pricing_service import PricingService


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

        # 3. Sprawdź konflikty pracownika
        employee_conflicts = self.appt_repo.check_conflicts(
            employee_id, appt_date, start_time, end_time
        )
        if employee_conflicts:
            raise AppointmentError(
                f"Konflikt czasowy — pracownik ma {len(employee_conflicts)} kolidującą wizytę/y"
            )

        # 3b. Sprawdź konflikty klienta (czy klient ma już wizytę w tym czasie)
        client_conflicts = self.appt_repo.check_client_conflicts(
            client_id, appt_date, start_time, end_time
        )
        if client_conflicts:
            conflict = client_conflicts[0]
            conflict_time = f"{conflict['start_time']}-{conflict['end_time']}"
            try:
                employee_name = conflict['employee_name']
            except (KeyError, TypeError):
                employee_name = 'inny pracownik'
            raise AppointmentError(
                f"Konflikt czasowy — klient ma już wizytę o {conflict_time} z {employee_name}"
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

        if not AppointmentStatus.can_transition(current_status, new_status):
            allowed = AppointmentStatus.VALID_TRANSITIONS.get(current_status, set())
            raise AppointmentError(
                f"Nie można zmienić statusu z '{current_status}' na '{new_status}'. "
                f"Dozwolone: {', '.join(sorted(allowed)) if allowed else 'brak'}"
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
        2. Waliduj datę (musi być w przeszłości)
        3. Oblicz sumy (main + addon)
        4. Utwórz income_record
        5. Zmień status na completed
        6. Zaktualizuj last_visit_date klienta

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

        # Walidacja: wizyta musi być w przeszłości
        appointment_date = row['appointment_date']
        start_time = row['start_time']

        # Parse date and time
        if isinstance(appointment_date, str):
            appointment_date = datetime.strptime(appointment_date, '%Y-%m-%d').date()
        if isinstance(start_time, str):
            start_time = datetime.strptime(start_time, '%H:%M:%S').time()

        appointment_datetime = datetime.combine(appointment_date, start_time)
        now = datetime.now()

        if appointment_datetime > now:
            raise AppointmentError(
                "Nie można zamknąć wizyty zaplanowanej w przyszłości. "
                f"Data wizyty: {appointment_datetime.strftime('%Y-%m-%d %H:%M')}, "
                f"obecna data: {now.strftime('%Y-%m-%d %H:%M')}"
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

        # Dołącz payment_method z income_records (nie istnieje w appointments)
        appt_dict = dict(appt_row)
        income = self.income_repo.get_by_appointment(appointment_id)
        if income:
            appt_dict['payment_method'] = income['payment_method']

        return {
            'appointment': appt_dict,
            'main_services': [dict(s) for s in main_services],
            'addon_services': [dict(s) for s in addon_services],
            'totals': totals,
            'can_add_addon': appt_row['status'] == 'in_progress'
        }

    def update_appointment(
        self,
        appointment_id: int,
        client_id: int,
        employee_id: int,
        appointment_date: date,
        start_time: time,
        end_time: time,
        status: str,
        notes: Optional[str],
        services: List[dict],
        force_save: bool = False,
        satisfaction_score: Optional[int] = None,
        cancellation_reason: Optional[str] = None,
        payment_method: Optional[str] = None,
    ) -> dict:
        """
        Aktualizuj wizytę wraz z usługami (diff strategy).

        TASK#1: Strategia diff — UPDATE istniejące, INSERT nowe, DELETE usunięte.
        TASK#2: Obsługa commission_rate z payloadu lub auto-resolve z employee_services.
        TASK#4: Aktualizacja income_record gdy status pozostaje 'completed' a ceny się zmieniły.
        TASK#5: Aktualizacja tabel powiązanych — income_records, clients.last_visit_date.

        Args:
            services: [{appointment_service_id?, service_id, price_charged,
                        duration_minutes, commission_rate?, is_addon}]
            payment_method: Metoda płatności — aktualizuje income_records.payment_method
        """
        # 1. Sprawdź czy wizyta istnieje i pobierz stary status
        appt_row = self.appt_repo.get_by_id(appointment_id)
        if not appt_row:
            raise AppointmentError("Wizyta nie istnieje")

        old_status = appt_row['status']
        old_client_id = appt_row['client_id']
        old_employee_id = appt_row['employee_id']
        old_appointment_date = appt_row['appointment_date']

        # 2. Walidacja: zmiana statusu na 'completed' wymaga daty w przeszłości
        if status == 'completed' and old_status != 'completed':
            appointment_datetime = datetime.combine(appointment_date, start_time)
            if appointment_datetime > datetime.now():
                raise AppointmentError(
                    "Nie można zmienić statusu na 'zakończona' dla wizyty w przyszłości. "
                    f"Data wizyty: {appointment_datetime.strftime('%Y-%m-%d %H:%M')}, "
                    f"obecna data: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                )

        # 2b. Sprawdź konflikty (pomijane gdy force_save=True)
        if not force_save:
            employee_conflicts = self.appt_repo.check_conflicts(
                employee_id, appointment_date, start_time, end_time,
                exclude_appointment_id=appointment_id
            )
            if employee_conflicts:
                raise AppointmentError(
                    f"Konflikt czasowy — pracownik ma {len(employee_conflicts)} kolidującą wizytę/y"
                )

            client_conflicts = self.appt_repo.check_client_conflicts(
                client_id, appointment_date, start_time, end_time,
                exclude_appointment_id=appointment_id
            )
            if client_conflicts:
                conflict = client_conflicts[0]
                conflict_time = f"{conflict['start_time']}-{conflict['end_time']}"
                try:
                    employee_name = conflict['employee_name']
                except (KeyError, TypeError):
                    employee_name = 'inny pracownik'
                raise AppointmentError(
                    f"Konflikt czasowy — klient ma już wizytę o {conflict_time} z {employee_name}"
                )

        # 3. Policz sumy
        total_price = sum(Decimal(str(s['price_charged'])) for s in services)
        total_duration = sum(s['duration_minutes'] for s in services)

        # 4. Ustal cancelled_at: ustaw gdy zmiana na cancelled/no_show, wyczyść gdy zmiana Z
        is_cancelling = status in ('cancelled', 'no_show') and old_status not in ('cancelled', 'no_show')
        is_uncancelling = status not in ('cancelled', 'no_show') and old_status in ('cancelled', 'no_show')

        if is_cancelling:
            cancelled_at = datetime.now()
        elif is_uncancelling:
            cancelled_at = None
        else:
            cancelled_at = appt_row.get('cancelled_at')

        # 5. Zaktualizuj appointment (wszystkie pola — superadmin bypass)
        appt = Appointment(
            id=appointment_id,
            client_id=client_id,
            employee_id=employee_id,
            appointment_date=appointment_date,
            start_time=start_time,
            end_time=end_time,
            status=status,
            total_price=total_price,
            total_duration=total_duration,
            notes=notes,
            satisfaction_score=satisfaction_score,
            cancellation_reason=cancellation_reason,
            cancelled_at=cancelled_at,
        )
        self.appt_repo.update(appointment_id, appt)

        # 6. DIFF strategy — aktualizuj usługi bez delete-all
        pricing_svc = PricingService()

        existing_rows = self.appt_svc_repo.get_all_for_appointment(appointment_id)
        existing_by_id = {row['id']: row for row in existing_rows}
        incoming_existing_ids = set()

        for svc in services:
            price_charged = Decimal(str(svc['price_charged']))
            appt_svc_id = svc.get('appointment_service_id')

            # Commission rate: from payload if explicitly provided, else resolve from employee_services
            if svc.get('commission_rate') is not None:
                commission_rate = Decimal(str(svc['commission_rate']))
            else:
                commission_rate = pricing_svc.resolve_commission(employee_id, int(svc['service_id'])) or Decimal('0')

            commission_amount = (price_charged * commission_rate / Decimal('100')).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )
            is_addon = bool(svc.get('is_addon', False))

            if appt_svc_id and appt_svc_id in existing_by_id:
                # UPDATE existing record — preserves id, added_at
                self.appt_svc_repo.update_service(
                    appt_svc_id, price_charged, int(svc['duration_minutes']),
                    commission_rate, commission_amount, is_addon
                )
                incoming_existing_ids.add(appt_svc_id)
            else:
                # INSERT new record
                new_svc = AppointmentService(
                    appointment_id=appointment_id,
                    service_id=int(svc['service_id']),
                    price_charged=price_charged,
                    duration_minutes=int(svc['duration_minutes']),
                    commission_rate=commission_rate,
                    commission_amount=commission_amount,
                    is_addon=is_addon,
                )
                self.appt_svc_repo.add_service(new_svc)

        # DELETE records removed by the user
        for existing_id in existing_by_id:
            if existing_id not in incoming_existing_ids:
                self.appt_svc_repo.delete(existing_id)

        # 7. TASK#4/5 — obsługa income_record i tabel powiązanych
        existing_income = self.income_repo.get_by_appointment(appointment_id)

        if status == 'completed' and old_status != 'completed':
            # Zmiana NA 'completed' → utwórz income_record
            if not existing_income:
                totals = self.appt_svc_repo.get_appointment_totals(appointment_id)
                income = IncomeRecord(
                    appointment_id=appointment_id,
                    client_id=client_id,
                    employee_id=employee_id,
                    total_amount=total_price,
                    discount_amount=Decimal('0'),
                    net_amount=total_price,
                    commission_total=Decimal(str(totals.get('total_commission', 0))),
                    payment_method=payment_method,
                    payment_date=appointment_date,
                )
                self.income_repo.create(income)

            # Aktualizuj last_visit_date klienta
            self.client_repo.update_last_visit(client_id, appointment_date)

        elif status != 'completed' and old_status == 'completed':
            # Zmiana Z 'completed' → usuń income_record
            if existing_income:
                self.income_repo.delete_by_appointment(appointment_id)

        elif status == 'completed' and old_status == 'completed' and existing_income:
            # TASK#4: status pozostaje 'completed' — aktualizuj income_record gdy zmieniły się ceny
            totals = self.appt_svc_repo.get_appointment_totals(appointment_id)
            self.income_repo.update(
                appointment_id=appointment_id,
                total_amount=total_price,
                net_amount=total_price,
                commission_total=Decimal(str(totals.get('total_commission', 0))),
                client_id=client_id if client_id != old_client_id else None,
                employee_id=employee_id if employee_id != old_employee_id else None,
                payment_method=payment_method,
            )
            # Aktualizuj last_visit_date gdy zmieniono datę wizyty
            if appointment_date != old_appointment_date:
                self.client_repo.update_last_visit(client_id, appointment_date)

        return {
            'appointment_id': appointment_id,
            'total_price': float(total_price),
            'total_duration': total_duration,
            'service_count': len(services)
        }
