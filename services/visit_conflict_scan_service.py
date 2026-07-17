"""
Skan konfliktów przeszłych wizyt — wykrywa duplikaty powstałe z przekładania
terminów w caldis.pl (poprzedni termin nie został poprawnie zamknięty przy
przełożeniu, więc w bazie zostają dwie/trzy wizyty zamiast jednej ostatecznej).

Dwie heurystyki:
  H1 time_overlap                — ten sam klient + pracownik + usługa,
                                    nakładające się przedziały czasowe.
  H2 same_day_different_stylist  — ten sam klient + usługa + dzień,
                                    różni pracownicy.

W obu przypadkach wizyta o najwyższym id w grupie ("ostatni zapis") jest
uznawana za ostateczny termin; reszta w grupie jest nadpisana (superseded)
i przy apply() soft-deletowana — tak samo odwracalnie jak ręczne usunięcie
wizyty (patrz routes/appointment_routes.py: delete_appointment/restore_appointment).
"""
from collections import defaultdict
from datetime import date
from typing import Any, Dict, List, Tuple

from config.database import managed_transaction
from repositories.appointments.appointment_repository import AppointmentRepository
from repositories.appointments.income_repository import IncomeRepository
from repositories.db_utils import parse_date
from exceptions import ValidationError

REASON_LABELS = {
    'time_overlap': 'nakładający się termin',
    'same_day_different_stylist': 'ten sam dzień, inny fryzjer',
}


def _minutes(value: Any) -> int:
    """Parsuje TIME/timedelta/str (patrz repositories/db_utils.py) na minuty od północy."""
    parts = str(value).split(':')
    return int(parts[0]) * 60 + int(parts[1])


class _UnionFind:
    def __init__(self, n: int):
        self.parent = list(range(n))

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, x: int, y: int) -> None:
        rx, ry = self.find(x), self.find(y)
        if rx != ry:
            self.parent[rx] = ry


class VisitConflictScanService:
    """Wykrywa i (opcjonalnie) usuwa nadpisane wizyty w zadanym zakresie dat."""

    def __init__(self):
        self.appt_repo = AppointmentRepository()
        self.income_repo = IncomeRepository()

    def _validate_range(self, date_start: date, date_end: date) -> None:
        if date_start > date_end:
            raise ValidationError('date_start musi być przed lub równy date_end')
        if date_end > date.today():
            raise ValidationError('Skan dotyczy tylko przeszłych wizyt — data do nie może być w przyszłości')

    def _build_groups(self, rows: List[Any]) -> List[Dict[str, Any]]:
        n = len(rows)
        uf = _UnionFind(n)
        edge_reasons: Dict[Tuple[int, int], set] = defaultdict(set)

        buckets: Dict[Tuple[int, int, date], List[int]] = defaultdict(list)
        for i, row in enumerate(rows):
            key = (row['client_id'], row['service_id'], parse_date(row['appointment_date']))
            buckets[key].append(i)

        for idxs in buckets.values():
            if len(idxs) < 2:
                continue
            for a in range(len(idxs)):
                for b in range(a + 1, len(idxs)):
                    i, j = idxs[a], idxs[b]
                    ri, rj = rows[i], rows[j]
                    if ri['employee_id'] == rj['employee_id']:
                        si, ei = _minutes(ri['start_time']), _minutes(ri['end_time'])
                        sj, ej = _minutes(rj['start_time']), _minutes(rj['end_time'])
                        if si < ej and sj < ei:
                            uf.union(i, j)
                            edge_reasons[(i, j)].add('time_overlap')
                    else:
                        uf.union(i, j)
                        edge_reasons[(i, j)].add('same_day_different_stylist')

        components: Dict[int, List[int]] = defaultdict(list)
        for i in range(n):
            components[uf.find(i)].append(i)

        groups = []
        for idxs in components.values():
            if len(idxs) < 2:
                continue
            members = [rows[i] for i in idxs]
            keeper = max(members, key=lambda r: r['id'])
            idx_set = set(idxs)
            reasons = set()
            for (i, j), rs in edge_reasons.items():
                if i in idx_set and j in idx_set:
                    reasons |= rs

            appointments = sorted((
                {
                    'id': r['id'],
                    'appointment_date': parse_date(r['appointment_date']).isoformat(),
                    'start_time': str(r['start_time'])[:5],
                    'end_time': str(r['end_time'])[:5],
                    'employee_name': r['employee_name'],
                    'status': r['status'],
                    'total_price': str(r['total_price']),
                    'is_keeper': r['id'] == keeper['id'],
                }
                for r in members
            ), key=lambda a: a['id'])

            groups.append({
                'client_id': keeper['client_id'],
                'client_name': keeper['client_name'],
                'service_id': keeper['service_id'],
                'service_name': keeper['service_name'],
                'reasons': sorted(reasons),
                'keeper_id': keeper['id'],
                'appointments': appointments,
            })

        groups.sort(key=lambda g: (g['client_name'], g['appointments'][0]['appointment_date']))
        return groups

    def scan(self, date_start: date, date_end: date) -> Dict[str, Any]:
        """Skan tylko do odczytu — nic nie zapisuje do bazy."""
        self._validate_range(date_start, date_end)
        rows = self.appt_repo.get_candidates_for_conflict_scan(date_start, date_end)
        groups = self._build_groups(rows)
        superseded_count = sum(len(g['appointments']) - 1 for g in groups)
        return {
            'candidate_count': len(rows),
            'group_count': len(groups),
            'superseded_count': superseded_count,
            'groups': groups,
        }

    def apply(self, date_start: date, date_end: date) -> Dict[str, Any]:
        """Ponownie skanuje (nie ufa danym z frontu) i soft-deletuje nadpisane wizyty.

        Odwracalne przez POST /appointments/<id>/restore (istniejący endpoint) —
        przywraca zarówno wizytę, jak i jej rekord przychodu.
        """
        result = self.scan(date_start, date_end)
        removed_ids: List[int] = []

        with managed_transaction():
            for group in result['groups']:
                reasons = ', '.join(REASON_LABELS.get(r, r) for r in group['reasons']) or 'przełożenie'
                for appt in group['appointments']:
                    if appt['is_keeper']:
                        continue
                    note = (f"[Skan konfliktów] Nadpisana przez wizytę #{group['keeper_id']} "
                            f"({reasons}).")
                    self.appt_repo.soft_delete_as_superseded(appt['id'], note)
                    self.income_repo.soft_delete_by_appointment(appt['id'])
                    removed_ids.append(appt['id'])

        return {
            'group_count': result['group_count'],
            'removed_count': len(removed_ids),
            'removed_ids': removed_ids,
        }
