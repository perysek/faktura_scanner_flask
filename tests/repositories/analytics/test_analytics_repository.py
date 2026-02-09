"""Tests for AnalyticsRepository date range calculations"""
import pytest
from datetime import date
from dateutil.relativedelta import relativedelta
from unittest.mock import Mock, patch
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


class TestRevenueSummary:
    """Test revenue summary query"""

    def setup_method(self):
        self.repo = AnalyticsRepository()

    @patch('repositories.analytics.analytics_repository.DatabaseConnection')
    def test_get_revenue_summary_executes_correct_query(self, mock_db):
        """Revenue summary should query appointments and income_records"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = {
            'total_appointments': 124,
            'unique_clients': 87,
            'total_revenue': 45600.00,
            'avg_ticket': 367.74,
            'total_commissions': 18240.00
        }
        mock_db.get_connection.return_value = mock_conn

        start = date(2026, 2, 1)
        end = date(2026, 2, 28)
        result = self.repo.get_revenue_summary(start, end)

        # Verify query was executed
        assert mock_cursor.execute.called
        query = mock_cursor.execute.call_args[0][0]
        assert 'appointments' in query.lower()
        assert 'income_records' in query.lower()
        assert 'completed' in query.lower()

        # Verify result structure
        assert result['total_appointments'] == 124
        assert result['unique_clients'] == 87
        assert result['total_revenue'] == 45600.00
