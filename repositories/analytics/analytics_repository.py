"""
Analytics repository for dashboard metrics
"""
from datetime import date, timedelta
from typing import Tuple
from dateutil.relativedelta import relativedelta


class AnalyticsRepository:
    """Repository for analytics queries with time period support"""

    def get_date_ranges(
        self,
        period: str,
        reference_date: date = None
    ) -> Tuple[date, date, date, date]:
        """
        Calculate date ranges for current and comparison periods.

        Args:
            period: 'current_month' | 'last_month' | 'current_year' | 'custom'
            reference_date: Reference date for calculations (defaults to today)

        Returns:
            (current_start, current_end, previous_start, previous_end)
        """
        ref = reference_date or date.today()

        if period == 'current_month':
            current_start = ref.replace(day=1)
            current_end = (current_start + relativedelta(months=1)) - timedelta(days=1)
            previous_start = current_start - relativedelta(months=1)
            previous_end = current_start - timedelta(days=1)

        elif period == 'last_month':
            current_start = (ref.replace(day=1) - relativedelta(months=1))
            current_end = ref.replace(day=1) - timedelta(days=1)
            previous_start = current_start - relativedelta(months=1)
            previous_end = current_start - timedelta(days=1)

        elif period == 'current_year':
            current_start = ref.replace(month=1, day=1)
            current_end = ref
            previous_start = current_start - relativedelta(years=1)
            previous_end = ref - relativedelta(years=1)

        else:
            raise ValueError(f"Unsupported period: {period}")

        return (current_start, current_end, previous_start, previous_end)
