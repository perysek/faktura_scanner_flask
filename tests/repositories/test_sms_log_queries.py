"""SmsReminderRepository.get_log / count_log: Historia SMS, tab "Wysłane".

Newest first; an optional upper bound keeps only texts sent before it ("everything up to the end of the month the
picker shows"); the count and the list read the same rows; `response` says whether the client answered the link.
"""
from datetime import datetime
from unittest.mock import patch

from repositories.sms.sms_repository import SmsReminderRepository
from utils.timezone import WARSAW_TZ

BEFORE = datetime(2026, 11, 1, tzinfo=WARSAW_TZ)


def _list(**kw):
    with patch.object(SmsReminderRepository, '_fetch_all', return_value=[]) as fetch:
        SmsReminderRepository().get_log(limit=100, offset=200, **kw)
    return fetch.call_args.args


def _count(**kw):
    with patch.object(SmsReminderRepository, '_fetch_one', return_value={'n': 7}) as fetch:
        n = SmsReminderRepository().count_log(**kw)
    return n, fetch.call_args.args


class TestGetLog:
    def test_without_a_bound_it_is_the_whole_log_newest_first(self):
        sql, params = _list()
        assert 'ORDER BY sr.sent_at DESC' in sql and 'WHERE' not in sql
        assert params == (100, 200)

    def test_with_a_bound_only_earlier_texts_are_listed_and_the_bound_is_a_parameter(self):
        sql, params = _list(before=BEFORE)
        assert 'WHERE sr.sent_at < %s' in sql
        assert params == (BEFORE, 100, 200)
        assert '2026' not in sql                            # never interpolated into the SQL text

    def test_the_text_and_the_sender_travel_with_every_row(self):
        sql, _ = _list()
        assert 'sr.*' in sql                                # message_body, created_by_user_id, created_by_name, status

    def test_response_reads_the_visit_for_the_links_the_text_carried(self):
        sql, _ = _list()
        assert "message_body LIKE '%%/rate/%%' AND a.rated_on IS NOT NULL THEN 'rated'" in sql
        for link in ('/confirm/', '/cancel/'):
            assert f"LIKE '%%{link}%%'" in sql
        assert "THEN 'confirmed'" in sql and "THEN 'declined'" in sql

    def test_the_percent_signs_are_doubled_because_the_query_always_carries_parameters(self):
        sql, _ = _list()
        assert '%/' not in sql.replace('%%/', '')           # a bare % before a slash would be read by psycopg2 as a placeholder


class TestCountLog:
    def test_it_counts_exactly_what_the_list_can_reach(self):
        n, (sql, params) = _count(before=BEFORE)
        assert n == 7 and params == (BEFORE,)
        list_sql, _ = _list(before=BEFORE)
        for join in ('JOIN clients c ON c.id = sr.client_id', 'JOIN appointments a ON a.id = sr.appointment_id'):
            assert join in sql and join in list_sql         # an inner join drops orphans from BOTH, so the pill never lies
        assert 'WHERE sr.sent_at < %s' in sql

    def test_without_a_bound_it_counts_everything(self):
        n, (sql, params) = _count()
        assert n == 7 and params == () and 'WHERE' not in sql
