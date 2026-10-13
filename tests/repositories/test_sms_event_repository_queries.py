"""SmsEventRepository: the scheduler must never act on a queued event of a deleted visit.

Found on the live site (2026-10-07): delete_appointment never cancelled a visit's queued sms_events and
get_due() did not look at the visit, so an `employee_visit_reminder` of a soft-deleted visit would still have
been texted to the employee (the principal's own deleted test visit had one queued for his own phone).

get_due() (what the scheduler sends) and get_scheduled_for_queue() (what the "Oczekujące" page lists) share ONE
definition of "a pending event" so the page can never list something the scheduler will not send, nor hide
something it will.
"""
from unittest.mock import patch

from repositories.sms import sms_event_repository as module
from repositories.sms.sms_event_repository import SmsEventRepository


def _sql(method, *args):
    with patch.object(SmsEventRepository, '_fetch_all', return_value=[]) as fetch:
        getattr(SmsEventRepository(), method)(*args)
    return fetch.call_args.args[0]


class TestWhatTheSchedulerMayPickUp:
    def test_an_event_of_a_deleted_visit_is_never_due(self):
        assert 'a.is_deleted IS NOT TRUE' in _sql('get_due')

    def test_a_due_event_is_still_a_scheduled_one_whose_time_has_come(self):
        sql = _sql('get_due')
        assert "e.status = 'scheduled'" in sql and 'e.scheduled_at <= NOW()' in sql


class TestWhatThePageLists:
    def test_the_queue_view_hides_the_same_events_the_scheduler_ignores(self):
        assert 'a.is_deleted IS NOT TRUE' in _sql('get_scheduled_for_queue', None)

    def test_the_queue_view_looks_ahead_so_it_has_no_due_time_cut(self):
        assert 'scheduled_at <= NOW()' not in _sql('get_scheduled_for_queue', None)

    def test_one_visit_can_be_asked_for(self):
        assert 'e.appointment_id = %s' in _sql('get_scheduled_for_queue', 42)


class TestOneDefinitionOfPending:
    def test_both_queries_embed_the_shared_filter(self):
        shared = module.PENDING_EVENT_FILTER
        assert shared in _sql('get_due')
        assert shared in _sql('get_scheduled_for_queue', None)

    def test_the_shared_filter_is_exactly_scheduled_and_visit_not_deleted(self):
        assert module.PENDING_EVENT_FILTER == "e.status = 'scheduled' AND a.is_deleted IS NOT TRUE"


class TestHeldEvents:
    """A 'held' event (absence auto-cancel notice) is invisible to every scheduler until released."""

    def test_held_is_not_due(self):
        assert "e.status = 'scheduled'" in _sql('get_due')

    def test_release_only_flips_held_events_and_makes_them_due_now(self):
        with patch.object(SmsEventRepository, '_execute') as ex:
            ex.return_value.rowcount = 1
            assert SmsEventRepository().release(7) is True
        sql, params = ex.call_args.args
        assert "status = 'held'" in sql and "status = 'scheduled'" in sql and 'scheduled_at = NOW()' in sql
        assert params == (7,)

    def test_create_defaults_to_scheduled(self):
        with patch.object(SmsEventRepository, '_execute_insert', return_value=1) as ins:
            SmsEventRepository().create(1, 'x', None)
        assert ins.call_args.args[1][-1] == 'scheduled'
