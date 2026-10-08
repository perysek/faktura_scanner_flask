"""SmsReminderRepository.get_stats: the "Poprzedni miesiąc" cards on Ustawienia SMS.

The React page reads six `prev_*` counts (types/settings.ts SmsStats) and shows them under the button
"Poprzedni miesiąc" - the previous CALENDAR month, not "the last 3 months" it replaced. The legacy Jinja page
still reads `mtd3_*`, so those must keep coming back too (additive change).
"""
from unittest.mock import patch

from repositories.sms.sms_repository import SmsReminderRepository

PREV_KEYS = ['prev_total', 'prev_sent', 'prev_failed', 'prev_confirm_requests', 'prev_confirmed', 'prev_declined']
MTD_KEYS = ['mtd1_total', 'mtd1_sent', 'mtd1_failed', 'mtd1_confirm_requests', 'mtd1_confirmed', 'mtd1_declined']


def _sql():
    with patch.object(SmsReminderRepository, '_fetch_one', return_value={}) as fetch:
        SmsReminderRepository().get_stats()
    return fetch.call_args.args[0]


def _count_for(sql, key):
    return next(line for line in sql.splitlines() if line.rstrip(',').endswith(f'AS {key}'))


class TestPreviousMonthStats:
    def test_previous_month_is_the_calendar_month_before_the_current_one(self):
        assert "DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month') AS previous_month" in _sql()

    def test_every_count_the_page_reads_is_selected(self):
        sql = _sql()
        for key in PREV_KEYS:
            assert f'AS {key}' in sql

    def test_prev_counts_look_at_the_previous_month_only(self):
        sql = _sql()
        for key in PREV_KEYS:
            line = _count_for(sql, key)
            assert 'send_month = previous_month' in line
            assert 'current_month' not in line and 'three_months_ago' not in line

    def test_prev_counts_use_the_same_definitions_as_the_current_month_ones(self):
        """Same status / confirmation predicates, only the month differs - so the two tabs are comparable."""
        sql = _sql()
        for prev, mtd in zip(PREV_KEYS, MTD_KEYS):
            assert _count_for(sql, prev).replace('previous_month', 'M') == _count_for(sql, mtd).replace('current_month', 'M').replace(mtd, prev)

    def test_the_legacy_jinja_page_still_gets_its_three_month_counts(self):
        sql = _sql()
        for key in ('mtd3_total', 'mtd3_sent', 'mtd3_failed', 'mtd3_confirm_requests', 'mtd3_confirmed', 'mtd3_declined'):
            assert f'AS {key}' in sql
