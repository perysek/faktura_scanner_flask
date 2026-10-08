"""services/sms_queue_service — which SMS the scheduler will still send, and on which tick.

The tick arithmetic is pure; the queue assembly runs against injected fakes (no DB). The real-SQL
parity with the scheduler's own query is proven separately on a scratch Postgres (see the ISA).
"""
from datetime import datetime, timedelta, timezone

import pytest

from services.sms_queue_service import (
    NOTE_ALREADY_SENT, NOTE_BAD_PHONE, NOTE_NEEDS_CONFIRMED, NOTE_NO_PHONE, NOTE_TYPE_OFF,
    SmsQueueService, estimate_tick, first_tick_at_or_after, format_sent_row,
)

NOW = datetime(2026, 10, 7, 4, 7, 51)             # naive Warsaw wall-clock
NEXT_RUN = datetime(2026, 10, 7, 4, 20, 53)       # the scheduler's next tick
T = timedelta(minutes=15)


class TestFirstTickAtOrAfter:
    def test_a_moment_before_the_next_tick_is_carried_by_it(self):
        assert first_tick_at_or_after(NOW, NEXT_RUN) == NEXT_RUN

    def test_a_moment_exactly_on_a_tick_is_that_tick(self):
        assert first_tick_at_or_after(NEXT_RUN + 2 * T, NEXT_RUN) == NEXT_RUN + 2 * T

    def test_one_second_past_a_tick_waits_for_the_following_one(self):
        assert first_tick_at_or_after(NEXT_RUN + T + timedelta(seconds=1), NEXT_RUN) == NEXT_RUN + 2 * T

    def test_far_in_the_future_stays_on_the_grid(self):
        moment = NEXT_RUN + timedelta(days=3, minutes=4)
        got = first_tick_at_or_after(moment, NEXT_RUN)
        assert got >= moment and got - moment < T
        assert (got - NEXT_RUN) % T == timedelta(0)

    def test_a_stale_anchor_in_the_past_still_yields_a_future_grid_point(self):
        stale = NOW - timedelta(minutes=40)
        got = first_tick_at_or_after(NOW, stale)
        assert got >= NOW and (got - stale) % T == timedelta(0)


class TestEstimateTick:
    @pytest.mark.parametrize('moment, expected', [
        (datetime(2026, 10, 7, 4, 7, 30), datetime(2026, 10, 7, 4, 15)),
        (datetime(2026, 10, 7, 4, 15), datetime(2026, 10, 7, 4, 15)),
        (datetime(2026, 10, 7, 4, 15, 1), datetime(2026, 10, 7, 4, 30)),
        (datetime(2026, 10, 7, 4, 59, 59), datetime(2026, 10, 7, 5, 0)),
        (datetime(2026, 10, 7, 23, 50), datetime(2026, 10, 8, 0, 0)),
    ])
    def test_rounds_up_to_the_next_quarter_hour(self, moment, expected):
        assert estimate_tick(moment) == expected


# ── injected fakes ──────────────────────────────────────────────────────────────

class _Settings:
    def __init__(self, active=True):
        self.active = active

    def get_settings(self):
        return {'is_active': self.active}


class _Types:
    def __init__(self, before_visit=(), enabled=()):
        self.before_visit, self.enabled = list(before_visit), list(enabled)

    def get_enabled_before_visit(self):
        return self.before_visit

    def get_enabled(self):
        return self.enabled


class _Appts:
    def __init__(self, by_key=None, appt=None):
        self.by_key, self.appt, self.calls = by_key or {}, appt, []

    def get_sms_queue_candidates(self, hours, key, *, only_confirmed=False, appointment_id=None, limit=2000):
        self.calls.append({'hours': hours, 'key': key, 'only_confirmed': only_confirmed, 'appointment_id': appointment_id})
        return self.by_key.get(key, [])

    def get_by_id(self, appointment_id):
        return self.appt


class _Events:
    def __init__(self, rows=()):
        self.rows, self.calls = list(rows), []

    def get_scheduled_for_queue(self, appointment_id=None):
        self.calls.append(appointment_id)
        return self.rows


class _Reminders:
    def __init__(self, sent=()):
        self.sent = set(sent)

    def exists_active(self, appointment_id, type_key):
        return (appointment_id, type_key) in self.sent


def _type(key='confirmation_request', hours=24, only_confirmed=False, name='Prośba o potwierdzenie'):
    return {'type_key': key, 'name': name, 'send_hours_before': hours, 'send_only_if_confirmed': only_confirmed}


def _visit(appt_id, visit_at, name='Anna Nowak'):
    return {'appointment_id': appt_id, 'appointment_date': visit_at.date(), 'start_time': visit_at.time(),
            'status': 'scheduled', 'client_name': name, 'phone': '+48500100200', 'visit_at': visit_at}


def _service(*, active=True, types=(), candidates=None, events=(), enabled=(), appt=None, sent=()):
    appts = _Appts(candidates, appt)
    evs = _Events(events)
    svc = SmsQueueService(_Settings(active), _Types(types, enabled), appts, evs, _Reminders(sent))
    return svc, appts, evs


class TestPending:
    def test_a_window_that_is_already_open_goes_out_on_the_very_next_tick(self):
        visit = NOW + timedelta(hours=24)          # window opened 15 min before NOW + ... -> open now
        svc, _, _ = _service(types=[_type()], candidates={'confirmation_request': [_visit(1, visit)]})
        row = svc.pending(now=NOW, next_run=NEXT_RUN)['rows'][0]
        assert row['will_be_sent_at'] == NEXT_RUN.isoformat(timespec='seconds')
        assert row['estimated'] is False

    def test_a_window_that_opens_later_goes_out_on_the_first_tick_inside_it(self):
        # visit 24 h + 2 h from now: window opens in 1 h 45 min
        visit = NOW + timedelta(hours=26)
        window_open = visit - timedelta(hours=24) - timedelta(minutes=15)
        svc, _, _ = _service(types=[_type()], candidates={'confirmation_request': [_visit(1, visit)]})
        sent_at = datetime.fromisoformat(svc.pending(now=NOW, next_run=NEXT_RUN)['rows'][0]['will_be_sent_at'])
        assert window_open <= sent_at < window_open + T                 # the first tick in the window
        assert (sent_at - NEXT_RUN) % T == timedelta(0)                  # and on the scheduler's grid

    def test_a_visit_no_tick_can_reach_is_left_out(self):
        # scheduler paused for 2 h: its next tick is after this visit's window closes
        visit = NOW + timedelta(hours=24, minutes=5)
        svc, _, _ = _service(types=[_type()], candidates={'confirmation_request': [_visit(1, visit)]})
        out = svc.pending(now=NOW, next_run=NOW + timedelta(hours=2))
        assert out['rows'] == [] and out['total'] == 0

    def test_without_a_scheduler_anchor_the_times_are_estimates_and_say_so(self):
        visit = NOW + timedelta(hours=24)
        svc, _, _ = _service(types=[_type()], candidates={'confirmation_request': [_visit(1, visit)]})
        out = svc.pending(now=NOW, next_run=None)
        assert out['estimated'] is True and out['next_tick_at'] is None
        assert out['rows'][0]['estimated'] is True
        assert datetime.fromisoformat(out['rows'][0]['will_be_sent_at']).minute % 15 == 0

    def test_sms_switched_off_queues_nothing(self):
        svc, appts, _ = _service(active=False, types=[_type()],
                                 candidates={'confirmation_request': [_visit(1, NOW + timedelta(hours=24))]})
        out = svc.pending(now=NOW, next_run=NEXT_RUN)
        assert out['rows'] == [] and out['sms_active'] is False
        assert appts.calls == []                                          # not even queried

    def test_rows_come_out_soonest_first_and_paginate(self):
        v = lambda h: NOW + timedelta(hours=h)
        svc, _, _ = _service(types=[_type(hours=24)], candidates={'confirmation_request': [
            _visit(3, v(30)), _visit(1, v(25)), _visit(2, v(27))]})
        out = svc.pending(now=NOW, next_run=NEXT_RUN)
        assert [r['appointment_id'] for r in out['rows']] == [1, 2, 3]
        page = svc.pending(now=NOW, next_run=NEXT_RUN, offset=1, limit=1)
        assert [r['appointment_id'] for r in page['rows']] == [2] and page['total'] == 3

    def test_only_confirmed_types_ask_the_repository_for_confirmed_visits_only(self):
        svc, appts, _ = _service(types=[_type('reminder_1', 24, only_confirmed=True)])
        svc.pending(now=NOW, next_run=NEXT_RUN)
        assert appts.calls == [{'hours': 24, 'key': 'reminder_1', 'only_confirmed': True, 'appointment_id': None}]

    def test_the_appointment_filter_reaches_both_sources(self):
        svc, appts, evs = _service(types=[_type()])
        svc.pending(appointment_id=77, now=NOW, next_run=NEXT_RUN)
        assert appts.calls[0]['appointment_id'] == 77 and evs.calls == [77]


class TestQueuedEvents:
    def _event(self, **kw):
        base = {'id': 9, 'appointment_id': 5, 'event_type': 'employee_visit_reminder',
                'scheduled_at': datetime(2026, 10, 8, 7, 40, tzinfo=timezone.utc),   # 09:40 Warsaw
                'appointment_date': datetime(2026, 10, 8).date(), 'start_time': datetime(2026, 10, 8, 10).time(),
                'client_name': 'Anna Nowak', 'client_phone': '+48500100200',
                'employee_name': 'Daria Andreas', 'employee_phone': '+48600200300', 'type_name': None,
                # what SmsService.send() weighs for a client-facing event (an employee reminder ignores all of it)
                'visit_status': 'scheduled', 'type_enabled': True,
                'type_only_confirmed': False, 'already_sent': False}
        base.update(kw)
        return base

    def test_the_employee_reminder_goes_to_the_employee_on_the_tick_after_its_moment(self):
        svc, _, _ = _service(events=[self._event()])
        row = svc.pending(now=NOW, next_run=NEXT_RUN)['rows'][0]
        assert row['recipient_kind'] == 'employee' and row['recipient_name'] == 'Daria Andreas'
        assert row['phone_number'] == '+48600200300' and row['type_name'] == 'Przypomnienie dla pracownika'
        sent_at = datetime.fromisoformat(row['will_be_sent_at'])
        assert sent_at >= datetime(2026, 10, 8, 9, 40) and sent_at - datetime(2026, 10, 8, 9, 40) < T

    def test_any_other_event_goes_to_the_client_with_its_type_name(self):
        svc, _, _ = _service(events=[self._event(event_type='post_visit_message', type_name='Prośba o ocenę')])
        row = svc.pending(now=NOW, next_run=NEXT_RUN)['rows'][0]
        assert row['recipient_kind'] == 'client' and row['type_name'] == 'Prośba o ocenę'
        assert row['phone_number'] == '+48500100200'

    def test_an_event_already_due_goes_out_on_the_next_tick(self):
        svc, _, _ = _service(events=[self._event(scheduled_at=datetime(2026, 10, 7, 1, 0, tzinfo=timezone.utc))])   # 03:00 Warsaw: already due
        row = svc.pending(now=NOW, next_run=NEXT_RUN)['rows'][0]
        assert row['will_be_sent_at'] == NEXT_RUN.isoformat(timespec='seconds')

    def test_a_missing_phone_is_flagged_not_hidden(self):
        svc, _, _ = _service(events=[self._event(employee_phone=None)])
        row = svc.pending(now=NOW, next_run=NEXT_RUN)['rows'][0]
        assert 'Brak numeru telefonu' in row['note'] and row['deliverable'] is False

    # Events of a DELETED visit are not this layer's business: SmsEventRepository.PENDING_EVENT_FILTER keeps them
    # out of get_scheduled_for_queue() exactly as it keeps them out of get_due()
    # (tests/repositories/test_sms_event_repository_queries.py).

    # A client-facing event goes through SmsService.send(); its refusals decide whether the row is a promise.

    def _client_event(self, **kw):
        return self._event(event_type='post_visit_message', type_name='Prośba o ocenę', **kw)

    def _row(self, event):
        return _service(events=[event])[0].pending(now=NOW, next_run=NEXT_RUN)['rows'][0]

    def test_a_healthy_client_event_is_deliverable(self):
        row = self._row(self._client_event())
        assert row['deliverable'] is True and row['note'] is None

    @pytest.mark.parametrize('overrides, note', [
        ({'type_enabled': False}, NOTE_TYPE_OFF),                    # switched off in the settings
        ({'type_enabled': None}, NOTE_TYPE_OFF),                     # no sms_message_types row at all
        ({'already_sent': True}, NOTE_ALREADY_SENT),                 # idempotent: the event is closed as skipped
        ({'client_phone': '123456'}, NOTE_BAD_PHONE),
        ({'client_phone': ''}, NOTE_NO_PHONE),
        ({'type_only_confirmed': True, 'visit_status': 'scheduled'}, NOTE_NEEDS_CONFIRMED),
    ])
    def test_every_refusal_of_send_makes_a_client_event_undeliverable(self, overrides, note):
        row = self._row(self._client_event(**overrides))
        assert row['deliverable'] is False and row['note'] == note

    def test_an_only_confirmed_event_type_is_fine_once_the_visit_is_confirmed(self):
        assert self._row(self._client_event(type_only_confirmed=True, visit_status='confirmed'))['deliverable'] is True

    def test_the_refusals_are_weighed_in_sends_own_order(self):
        # type off beats everything; then already-texted; then the phone; then the only-confirmed rule
        everything = dict(type_enabled=False, already_sent=True, client_phone='123456',
                          type_only_confirmed=True, visit_status='scheduled')
        assert self._row(self._client_event(**everything))['note'] == NOTE_TYPE_OFF
        assert self._row(self._client_event(**{**everything, 'type_enabled': True}))['note'] == NOTE_ALREADY_SENT
        assert self._row(self._client_event(**{**everything, 'type_enabled': True, 'already_sent': False}))['note'] == NOTE_BAD_PHONE
        assert self._row(self._client_event(**{**everything, 'type_enabled': True, 'already_sent': False,
                                               'client_phone': '500 100 200'}))['note'] == NOTE_NEEDS_CONFIRMED

    def test_an_employee_reminder_ignores_the_type_switch_the_visit_status_and_earlier_texts(self):
        row = self._row(self._event(type_enabled=None, already_sent=True, visit_status='cancelled'))
        assert row['deliverable'] is True and row['note'] is None


class TestWhatTheSenderWillAndWillNotDeliver:
    """Found on the live site: 2 of 434 pending visits had 6-digit phone numbers. SmsService.send() raises
    SmsError for them, send_due_reminders counts that as 'skipped' and writes nothing, so the visit is never
    texted — yet the page promised it a time. Rows like that are still listed (staff can fix the number) but
    must not promise anything."""

    def _svc(self, *phones):
        visits = []
        for i, phone in enumerate(phones, start=1):
            v = _visit(i, NOW + timedelta(hours=24, minutes=i))
            v['phone'] = phone
            visits.append(v)
        return _service(types=[_type()], candidates={'confirmation_request': visits})[0]

    def test_the_number_shown_is_the_one_twilio_receives(self):
        row = self._svc('48515472247').pending(now=NOW, next_run=NEXT_RUN)['rows'][0]   # how clients.phone stores it
        assert row['phone_number'] == '+48515472247'
        assert row['deliverable'] is True and row['note'] is None

    @pytest.mark.parametrize('phone', ['123456', '500 100', 'abc', '+48 0123', '12345'])
    def test_a_number_the_sender_refuses_is_listed_but_flagged_undeliverable(self, phone):
        out = self._svc(phone).pending(now=NOW, next_run=NEXT_RUN)
        row = out['rows'][0]
        assert row['deliverable'] is False and row['note'] == NOTE_BAD_PHONE
        assert row['phone_number'] == phone                      # shown as stored: staff must be able to find and fix it
        assert out['total'] == 1 and out['undeliverable'] == 1

    def test_only_the_undeliverable_rows_are_counted_as_such(self):
        out = self._svc('500 100 200', '123456', '+48 600 700 800').pending(now=NOW, next_run=NEXT_RUN)
        assert out['total'] == 3 and out['undeliverable'] == 1
        assert [r['deliverable'] for r in out['rows']] == [True, False, True]

    def test_nothing_queued_means_nothing_undeliverable(self):
        assert _service(types=[_type()])[0].pending(now=NOW, next_run=NEXT_RUN)['undeliverable'] == 0


class TestManualSendOptions:
    def _svc(self, *, active=True, status='scheduled', phone='+48500100200', enabled=None, sent=()):
        enabled = enabled if enabled is not None else [
            {'type_key': 'confirmation_request', 'name': 'Prośba o potwierdzenie', 'send_only_if_confirmed': False},
            {'type_key': 'reminder_1', 'name': 'Przypomnienie', 'send_only_if_confirmed': True}]
        svc, _, _ = _service(active=active, enabled=enabled, sent=sent,
                             appt={'id': 5, 'client_id': 3, 'status': status})
        return svc, phone

    def _options(self, svc, phone):
        from unittest.mock import patch, MagicMock
        client_repo = MagicMock()
        client_repo.get_by_id.return_value = {'phone': phone} if phone is not None else None
        with patch('repositories.clients.client_repository.ClientRepository', return_value=client_repo):
            return {t['type_key']: t for t in svc.manual_send_options(5)['types']}

    def test_an_only_confirmed_type_is_unavailable_until_the_visit_is_confirmed(self):
        svc, phone = self._svc(status='scheduled')
        got = self._options(svc, phone)
        assert got['confirmation_request']['available'] is True
        assert got['reminder_1']['available'] is False and 'Potwierdzona' in got['reminder_1']['reason']
        svc, phone = self._svc(status='confirmed')
        assert self._options(svc, phone)['reminder_1']['available'] is True

    def test_no_phone_makes_every_type_unavailable(self):
        svc, _ = self._svc()
        got = self._options(svc, '')
        assert all(not t['available'] and 'numeru telefonu' in t['reason'] for t in got.values())

    def test_a_number_the_sender_cannot_parse_greys_every_type_out_and_says_so(self):
        # send() raises SmsError("Nieprawidłowy numer telefonu") for it, so the click would fail
        svc, _ = self._svc()
        got = self._options(svc, '12345')
        assert all(not t['available'] and 'Nieprawidłowy numer' in t['reason'] for t in got.values())

    def test_a_number_stored_without_a_plus_is_fine(self):
        svc, _ = self._svc()
        assert self._options(svc, '48515472247')['confirmation_request']['available'] is True

    def test_sms_switched_off_makes_every_type_unavailable(self):
        svc, phone = self._svc(active=False)
        got = self._options(svc, phone)
        assert all(not t['available'] and 'wyłączone' in t['reason'] for t in got.values())

    def test_already_sent_is_reported_so_the_ui_can_warn(self):
        svc, phone = self._svc(sent={(5, 'confirmation_request')})
        got = self._options(svc, phone)
        assert got['confirmation_request']['already_sent'] is True and got['reminder_1']['already_sent'] is False

    def test_an_unknown_visit_offers_nothing(self):
        svc, _, _ = _service(appt=None)
        assert svc.manual_send_options(999)['types'] == []


class TestFormatSentRow:
    def test_timestamptz_is_shown_in_warsaw_time_and_automatic_sends_are_labelled(self):
        out = format_sent_row({'id': 1, 'sent_at': datetime(2026, 7, 19, 15, 0, 59, tzinfo=timezone.utc),
                               'message_type_key': 'reminder_1', 'type_name': 'Przypomnienie', 'status': 'sent',
                               'created_by_user_id': None, 'created_by_name': 'System (auto)', 'sender_name': None})
        assert out['sent_at'] == '2026-07-19T17:00:59'           # CEST = UTC+2: the page used to print 15:00
        assert out['automatic'] is True and out['sent_by'] == 'System (auto)'

    def test_a_manual_send_names_the_staff_member(self):
        out = format_sent_row({'id': 2, 'sent_at': None, 'message_type_key': 'x', 'status': 'failed',
                               'created_by_user_id': 5, 'created_by_name': 'Ola', 'sender_name': 'Ola K.',
                               'error_message': 'boom'})
        assert out['automatic'] is False and out['sent_by'] == 'Ola K.' and out['sent_at'] is None
        assert out['type_name'] == 'x' and out['error_message'] == 'boom'


class TestMonthFilterOrderAndPhoneProblem:
    """Historia SMS: the month picker asks for "everything up to the end of that month", newest first."""

    def _three(self):
        v = lambda h: NOW + timedelta(hours=h)
        return _service(types=[_type(hours=24)], candidates={'confirmation_request': [
            _visit(1, v(25)), _visit(2, v(27)), _visit(3, v(24 * 30))]})[0]       # the last one is a month away

    def test_newest_first_reverses_the_order_without_touching_the_default(self):
        svc = self._three()
        assert [r['appointment_id'] for r in svc.pending(now=NOW, next_run=NEXT_RUN)['rows']] == [1, 2, 3]
        assert [r['appointment_id'] for r in svc.pending(now=NOW, next_run=NEXT_RUN, newest_first=True)['rows']] == [3, 2, 1]

    def test_before_drops_what_is_due_at_or_after_the_cutoff(self):
        out = self._three().pending(now=NOW, next_run=NEXT_RUN, before=datetime(2026, 11, 1))
        assert [r['appointment_id'] for r in out['rows']] == [1, 2]

    def test_the_cutoff_is_exclusive(self):
        svc = self._three()
        tick = svc.pending(now=NOW, next_run=NEXT_RUN)['rows'][0]['will_be_sent_at']
        at = datetime.fromisoformat(tick)
        assert svc.pending(now=NOW, next_run=NEXT_RUN, before=at)['rows'] == []
        assert len(svc.pending(now=NOW, next_run=NEXT_RUN, before=at + timedelta(seconds=1))['rows']) >= 1

    def test_total_undeliverable_and_paging_describe_the_filtered_list(self):
        v = lambda h: NOW + timedelta(hours=h)
        visits = [_visit(1, v(25)), _visit(2, v(26)), _visit(3, v(24 * 30))]
        visits[1]['phone'] = '123456'                                            # refused by the sender
        visits[2]['phone'] = '123456'                                            # ... but a month away: filtered out
        svc = _service(types=[_type(hours=24)], candidates={'confirmation_request': visits})[0]
        out = svc.pending(now=NOW, next_run=NEXT_RUN, before=datetime(2026, 11, 1), limit=1)
        assert out['total'] == 2 and out['undeliverable'] == 1 and len(out['rows']) == 1

    def test_a_phone_problem_is_named_so_the_table_can_print_a_short_label(self):
        visits = [_visit(1, NOW + timedelta(hours=24, minutes=1)), _visit(2, NOW + timedelta(hours=24, minutes=2)),
                  _visit(3, NOW + timedelta(hours=24, minutes=3))]
        visits[1]['phone'] = ''
        visits[2]['phone'] = 'abc'
        rows = _service(types=[_type()], candidates={'confirmation_request': visits})[0].pending(now=NOW, next_run=NEXT_RUN)['rows']
        assert [r['phone_problem'] for r in rows] == [None, 'missing', 'invalid']

    def test_queued_events_name_their_phone_problem_too(self):
        event = TestQueuedEvents()._event(employee_phone=None)
        row = _service(events=[event])[0].pending(now=NOW, next_run=NEXT_RUN)['rows'][0]
        assert row['phone_problem'] == 'missing'
