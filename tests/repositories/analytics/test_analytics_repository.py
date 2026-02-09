"""Tests for AnalyticsRepository date range calculations"""
import pytest
from datetime import date
from dateutil.relativedelta import relativedelta
from repositories.analytics.analytics_repository import AnalyticsRepository


class TestDateRanges:
    """Test date range calculation for different periods"""

    def setup_method(self):
        self.repo = AnalyticsRepository()

    def test_current_month_ranges(self):
        """Current month should return this month vs. last month"""
        ref = date(2026, 2, 15)  # Feb 15, 2026
        current_start, current_end, prev_start, prev_end = self.repo.get_date_ranges('current_month', ref)

        assert current_start == date(2026, 2, 1)
        assert current_end == date(2026, 2, 28)
        assert prev_start == date(2026, 1, 1)
        assert prev_end == date(2026, 1, 31)

    def test_last_month_ranges(self):
        """Last month should return previous month vs. month before that"""
        ref = date(2026, 2, 15)
        current_start, current_end, prev_start, prev_end = self.repo.get_date_ranges('last_month', ref)

        assert current_start == date(2026, 1, 1)
        assert current_end == date(2026, 1, 31)
        assert prev_start == date(2025, 12, 1)
        assert prev_end == date(2025, 12, 31)

    def test_current_year_ranges(self):
        """Current year should return YTD vs. same period last year"""
        ref = date(2026, 2, 15)
        current_start, current_end, prev_start, prev_end = self.repo.get_date_ranges('current_year', ref)

        assert current_start == date(2026, 1, 1)
        assert current_end == date(2026, 2, 15)
        assert prev_start == date(2025, 1, 1)
        assert prev_end == date(2025, 2, 15)
