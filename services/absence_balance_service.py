"""
Serwis zarządzania bilansem nieobecności.

Odpowiada za:
- Obliczanie bieżącego bilansu (wykorzystane / limit / procent)
- Zarządzanie indywidualnymi limitami pracowników
- Tworzenie i usuwanie korekt bilansu
- Sprawdzanie przekroczenia limitu przed złożeniem wniosku
"""
from datetime import date, timedelta
from typing import Dict, List, Optional

from config.database import managed_transaction
from database.models import AbsenceBalanceAdjustment, EmployeeAbsenceLimit
from repositories.absences.absence_balance_repository import AbsenceBalanceRepository
from repositories.absences.absence_limit_repository import AbsenceLimitRepository
from repositories.absences.absence_adjustment_repository import AbsenceAdjustmentRepository
from repositories.absences.absence_category_repository import AbsenceCategoryRepository
from repositories.audit_repository import AuditRepository


class AbsenceBalanceService:
    """Logika bilansu nieobecności — odczyt, limity, korekty, kontrola wniosków."""

    def __init__(self):
        self.balance_repo = AbsenceBalanceRepository()
        self.limit_repo = AbsenceLimitRepository()
        self.adjustment_repo = AbsenceAdjustmentRepository()
        self.category_repo = AbsenceCategoryRepository()
        self.audit_repo = AuditRepository()

    # ── core period calculation ───────────────────────────────────────────────

    def compute_period_start(self, count_period: str,
                              resets_at: Optional[int],
                              rolling_days: Optional[int]) -> date:
        """Zwróć datę początku bieżącego okresu rozliczeniowego."""
        today = date.today()
        if count_period == 'yearly':
            day_offset = (resets_at or 1) - 1
            reset = date(today.year, 1, 1) + timedelta(days=day_offset)
            if today >= reset:
                return reset
            return date(today.year - 1, 1, 1) + timedelta(days=day_offset)

        elif count_period == 'monthly':
            day = min(resets_at or 1, 28)
            if today.day >= day:
                return date(today.year, today.month, day)
            if today.month == 1:
                return date(today.year - 1, 12, day)
            return date(today.year, today.month - 1, day)

        else:  # 'rolling'
            return today - timedelta(days=rolling_days or 365)

    def _period_label(self, count_period: str, period_start: date) -> str:
        if count_period == 'yearly':
            return str(period_start.year)
        elif count_period == 'monthly':
            return period_start.strftime('%Y-%m')
        return f"rolling {period_start.isoformat()}"

    # ── balance snapshot ──────────────────────────────────────────────────────

    def get_balance(self, employee_id: int, category_id: int) -> dict:
        """
        Pełny snapshot bilansu dla pary pracownik+kategoria.

        Raises ValueError jeśli kategoria nie istnieje lub nie jest śledzona.
        """
        cat_row = self.category_repo.get_by_id(category_id)
        if not cat_row:
            raise ValueError(f"Kategoria {category_id} nie istnieje")
        if not bool(cat_row['is_tracked']):
            raise ValueError(f"Kategoria '{cat_row['name']}' nie ma włączonego śledzenia")

        full_day = bool(cat_row['absence_full_day'])
        period_start = self.compute_period_start(
            cat_row['count_period'],
            cat_row['resets_at'],
            cat_row['rolling_days'],
        )

        used = self.balance_repo.compute_used(
            employee_id, category_id, period_start, full_day
        )
        adjustments = self.balance_repo.compute_adjustments(employee_id, category_id)
        net_used = used + adjustments

        # Effective limit: employee override > category default
        limit_row = self.limit_repo.get_for_employee_category(employee_id, category_id)
        limit = float(limit_row['max_value']) if limit_row else float(cat_row['default_max_value'])
        has_limit = limit > 0.0

        warning_pct = float(cat_row['warning_threshold_pct'])
        pct = (net_used / limit * 100.0) if has_limit else 0.0

        if not has_limit:
            status = 'unlimited'
        elif net_used > limit:
            status = 'exceeded'
        elif net_used >= limit * warning_pct:
            status = 'warning'
        else:
            status = 'ok'

        return {
            'category_id': category_id,
            'category_name': cat_row['name'],
            'absence_full_day': full_day,
            'unit': 'days' if full_day else 'hours',
            'used': round(used, 2),
            'adjustments': round(adjustments, 2),
            'net_used': round(net_used, 2),
            'limit': limit,
            'default_max_value': float(cat_row['default_max_value']),
            'has_limit': has_limit,
            'pct': round(pct, 2),
            'warning_threshold_pct': warning_pct,
            'status': status,
            'period_start': period_start.isoformat(),
            'period_label': self._period_label(cat_row['count_period'], period_start),
        }

    def get_all_balances_for_employee(self, employee_id: int) -> List[dict]:
        """Bilanse wszystkich śledzonych kategorii dla pracownika."""
        tracked = self.category_repo.list_tracked()
        result = []
        for cat_row in tracked:
            try:
                b = self.get_balance(employee_id, cat_row['id'])
                result.append(b)
            except ValueError:
                pass
        return result

    def get_balance_summary_for_list(self) -> Dict[int, dict]:
        """
        Zwraca słownik {employee_id → primary_balance_dict} do kolumny na liście pracowników.
        Używa jednego zapytania zbiorczego, a następnie oblicza 'used' per-pracownik.
        """
        rows = self.balance_repo.bulk_summary_for_list()
        result: Dict[int, dict] = {}

        for row in rows:
            emp_id = row['employee_id']
            cat_id = row['category_id']
            full_day = bool(row['full_day'])
            lim = float(row['lim'])
            adj = float(row['adj_total'])
            warning_pct = float(row['warning_threshold_pct'])

            # We still need per-employee used — compute from DB (one call per employee)
            # This is acceptable: the bulk query already did the heavy join work
            try:
                cat_row = self.category_repo.get_by_id(cat_id)
                if not cat_row:
                    continue
                period_start = self.compute_period_start(
                    cat_row['count_period'],
                    cat_row['resets_at'],
                    cat_row['rolling_days'],
                )
                used = self.balance_repo.compute_used(emp_id, cat_id, period_start, full_day)
            except Exception:
                used = 0.0

            net_used = used + adj
            has_limit = lim > 0.0
            pct = (net_used / lim * 100.0) if has_limit else 0.0

            if not has_limit:
                status = 'unlimited'
            elif net_used > lim:
                status = 'exceeded'
            elif net_used >= lim * warning_pct:
                status = 'warning'
            else:
                status = 'ok'

            result[emp_id] = {
                'category_id': cat_id,
                'category_name': row['category_name'],
                'unit': 'days' if full_day else 'hours',
                'used': round(net_used, 2),
                'limit': lim,
                'pct': round(pct, 2),
                'status': status,
            }

        return result

    # ── limit management ──────────────────────────────────────────────────────

    def set_limit(self, employee_id: int, category_id: int, max_value: float,
                  notes: Optional[str], created_by: int,
                  employee_name: str = '', category_name: str = '') -> int:
        """Utwórz lub zaktualizuj indywidualny limit. Loguje do audit_log."""
        old_row = self.limit_repo.get_for_employee_category(employee_id, category_id)
        old_value = str(old_row['max_value']) if old_row else None

        limit = EmployeeAbsenceLimit(
            employee_id=employee_id,
            category_id=category_id,
            max_value=max_value,
            notes=notes,
            created_by=created_by,
        )
        # Atomic: the limit upsert and its audit row commit together (#7). A failed
        # audit write rolls back the limit change — no silent "limit changed, no record".
        with managed_transaction():
            limit_id = self.limit_repo.upsert(limit)
            self.audit_repo.log_event(
                entity_type='absence_limit',
                action='UPDATE' if old_row else 'CREATE',
                entity_id=limit_id,
                entity_label=f"{employee_name} — {category_name}",
                field_name='max_value',
                old_value=old_value,
                new_value=str(max_value),
                user_id=created_by,
            )
        return limit_id

    def remove_limit(self, limit_id: int, user_id: int,
                     user_name: str = '') -> None:
        """Soft-delete limitu. Loguje do audit_log."""
        # Atomic: the soft-delete and its audit row commit together (#7).
        with managed_transaction():
            self.limit_repo.soft_delete(limit_id)
            self.audit_repo.log_event(
                entity_type='absence_limit',
                action='DELETE',
                entity_id=limit_id,
                entity_label=user_name,
                field_name='is_deleted',
                old_value='false',
                new_value='true',
                user_id=user_id,
            )

    # ── adjustments ───────────────────────────────────────────────────────────

    def create_adjustment(self, employee_id: int, category_id: int,
                           delta_value: float, reason: str,
                           period_label: Optional[str],
                           created_by: int,
                           employee_name: str = '',
                           category_name: str = '') -> int:
        """Dodaj manualną korektę bilansu. Loguje do audit_log."""
        if not reason or not reason.strip():
            raise ValueError("Powód korekty jest wymagany")

        adj = AbsenceBalanceAdjustment(
            employee_id=employee_id,
            category_id=category_id,
            delta_value=delta_value,
            reason=reason.strip(),
            period_label=period_label,
            created_by=created_by,
        )
        # Atomic: the adjustment insert and its audit row commit together (#7). A leave
        # balance can never move without a forensic record of who moved it and why.
        with managed_transaction():
            adj_id = self.adjustment_repo.create(adj)
            self.audit_repo.log_event(
                entity_type='absence_adjustment',
                action='CREATE',
                entity_id=adj_id,
                entity_label=f"{employee_name} — {category_name}: {delta_value:+.1f}",
                field_name='delta_value',
                old_value=None,
                new_value=str(delta_value),
                user_id=created_by,
            )
        return adj_id

    def delete_adjustment(self, adj_id: int, user_id: int,
                           user_name: str = '') -> None:
        """Soft-delete korekty. Loguje do audit_log."""
        # Atomic: the soft-delete and its audit row commit together (#7).
        with managed_transaction():
            self.adjustment_repo.soft_delete(adj_id)
            self.audit_repo.log_event(
                entity_type='absence_adjustment',
                action='DELETE',
                entity_id=adj_id,
                entity_label=user_name,
                field_name='is_deleted',
                old_value='false',
                new_value='true',
                user_id=user_id,
            )

    # ── pre-submission check ──────────────────────────────────────────────────

    def check_before_submit(self, employee_id: int, category_id: int,
                             proposed_value: float, source: str) -> dict:
        """
        Sprawdź czy proponowana nieobecność przekroczy limit.

        source='request' → hard block jeśli przekroczony
        source='manual'  → soft warning, nie blokuje

        Returns dict:
          {ok, blocked, warning, message, balance}
        """
        cat_row = self.category_repo.get_by_id(category_id)
        if not cat_row or not bool(cat_row['is_tracked']):
            return {'ok': True, 'blocked': False, 'warning': False,
                    'message': '', 'balance': None}

        try:
            balance = self.get_balance(employee_id, category_id)
        except ValueError:
            return {'ok': True, 'blocked': False, 'warning': False,
                    'message': '', 'balance': None}

        if not balance['has_limit']:
            return {'ok': True, 'blocked': False, 'warning': False,
                    'message': '', 'balance': balance}

        net_used_after = balance['net_used'] + proposed_value
        limit = balance['limit']
        unit = 'dni' if balance['absence_full_day'] else 'godzin'
        warning_pct = balance['warning_threshold_pct']

        if net_used_after > limit:
            msg = (
                f"Limit {balance['category_name']}: {balance['net_used']:.1f}/{limit} {unit}. "
                f"Proponowana nieobecność ({proposed_value:.1f} {unit}) "
                f"przekroczy limit o {net_used_after - limit:.1f} {unit}."
            )
            blocked = (source == 'request')
            return {
                'ok': not blocked,
                'blocked': blocked,
                'warning': True,
                'message': msg,
                'balance': balance,
            }

        if net_used_after >= limit * warning_pct:
            msg = (
                f"Uwaga: po tej nieobecności wykorzystano by "
                f"{net_used_after:.1f}/{limit} {unit} "
                f"({net_used_after / limit * 100:.0f}% limitu)."
            )
            return {'ok': True, 'blocked': False, 'warning': True,
                    'message': msg, 'balance': balance}

        return {'ok': True, 'blocked': False, 'warning': False,
                'message': '', 'balance': balance}
