"""
Serwis rozwiązywania cen, prowizji i czasu trwania usług.

Implementuje łańcuch COALESCE:
  effective_price      = employee_services.custom_price  → services.price
  effective_commission = employee_services.commission_rate → employees.commission_rate → 0
  effective_duration   = employee_services.duration_override → services.duration_minutes
"""
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional

from repositories.employees.employee_service_repository import EmployeeServiceRepository
from repositories.services.service_repository import ServiceRepository


class PricingService:
    """Serwis cenowy — rozwiązuje efektywne ceny dla par pracownik-usługa"""

    def __init__(self):
        self.employee_service_repo = EmployeeServiceRepository()
        self.service_repo = ServiceRepository()

    def resolve_price(self, employee_id: int, service_id: int) -> Optional[Decimal]:
        """Rozwiąż efektywną cenę dla pary pracownik-usługa.

        Returns: Decimal z ceną lub None jeśli pracownik nie może wykonać usługi.
        """
        row = self.employee_service_repo.get_effective_pricing(employee_id, service_id)
        if not row:
            return None
        return Decimal(str(row['effective_price']))

    def resolve_commission(self, employee_id: int, service_id: int) -> Optional[Decimal]:
        """Rozwiąż efektywną stawkę prowizji (%) dla pary pracownik-usługa."""
        row = self.employee_service_repo.get_effective_pricing(employee_id, service_id)
        if not row:
            return None
        return Decimal(str(row['effective_commission']))

    def resolve_duration(self, employee_id: int, service_id: int) -> Optional[int]:
        """Rozwiąż efektywny czas trwania (minuty) dla pary pracownik-usługa."""
        row = self.employee_service_repo.get_effective_pricing(employee_id, service_id)
        if not row:
            return None
        return int(row['effective_duration'])

    def resolve_full(self, employee_id: int, service_id: int) -> Optional[dict]:
        """Rozwiąż wszystkie parametry cenowe naraz.

        Returns: dict z effective_price, effective_commission, effective_duration,
                 commission_amount, service_name, service_type
                 lub None jeśli pracownik nie może wykonać usługi.
        """
        row = self.employee_service_repo.get_effective_pricing(employee_id, service_id)
        if not row:
            return None

        price = Decimal(str(row['effective_price']))
        commission_rate = Decimal(str(row['effective_commission']))
        commission_amount = (price * commission_rate / Decimal('100')).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )

        return {
            'service_id': service_id,
            'service_name': row['service_name'],
            'service_type': row['service_type'],
            'effective_price': price,
            'effective_commission': commission_rate,
            'effective_duration': int(row['effective_duration']),
            'commission_amount': commission_amount,
            'default_price': Decimal(str(row['default_price'])),
            'default_duration': int(row['default_duration']),
            'has_custom_price': row['custom_price'] is not None,
            'has_custom_commission': row['commission_rate'] is not None,
        }

    def calculate_appointment_total(self, employee_id: int,
                                     service_ids: List[int]) -> Optional[dict]:
        """Oblicz łączny koszt wizyty dla listy usług.

        Returns: dict z total_price, total_duration, total_commission, breakdown[]
                 lub None jeśli pracownik nie może wykonać którejś usługi.
        """
        total_price = Decimal('0')
        total_duration = 0
        total_commission = Decimal('0')
        breakdown = []

        for service_id in service_ids:
            resolved = self.resolve_full(employee_id, service_id)
            if not resolved:
                return None  # Pracownik nie może wykonać tej usługi

            total_price += resolved['effective_price']
            total_duration += resolved['effective_duration']
            total_commission += resolved['commission_amount']
            breakdown.append(resolved)

        return {
            'total_price': total_price,
            'total_duration': total_duration,
            'total_commission': total_commission,
            'breakdown': breakdown
        }
