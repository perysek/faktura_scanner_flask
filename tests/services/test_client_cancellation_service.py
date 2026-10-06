"""P0-3 / D1 / D3 — client-initiated cancellation through the public SMS links.

One code path serves `/cancel` and the "Odwołuję wizytę" button, so the 12 h cut-off
and the side effects cannot drift between them. `now_local` is patched; the DB layer
is replaced by mocks (the suite never touches Postgres).
"""
from contextlib import contextmanager
from datetime import date, datetime, time
from unittest.mock import MagicMock, Mock, patch

import pytest

SVC = 'services.client_cancellation_service'
START = datetime(2026, 7, 2, 14, 0)          # the visit under test, Warsaw wall-clock


def appt(status='scheduled', start=START, **extra):
    return {'id': 100, 'status': status, 'appointment_date': start.date(),
            'start_time': start.time(), 'client_id': 1, **extra}


def at(hours_before):
    """A patched Warsaw 'now' that is `hours_before` hours ahead of START."""
    from datetime import timedelta
    return patch(f'{SVC}.now_local', return_value=START - timedelta(hours=hours_before))


@pytest.fixture
def svc_mod(app):
    import services.client_cancellation_service as mod
    with app.app_context():
        yield mod


class TestClassify:
    @pytest.mark.parametrize('hours_before, expected', [
        (48, 'cancelled'),        # 'cancelled' here means: "yes, the client may cancel now"
        (12.02, 'cancelled'),
        (12, 'cancelled'),        # exactly at the cut-off is still allowed (>= 12 h)
        (11.98, 'too_late'),      # 11 h 59 min
        (3, 'too_late'),
        (0, 'too_late'),
        (-2, 'too_late'),         # already started
    ])
    def test_cutoff_boundary_is_twelve_hours(self, svc_mod, hours_before, expected):
        with at(hours_before):
            assert svc_mod.classify(appt()) == expected

    @pytest.mark.parametrize('status', ['scheduled', 'confirmed', 'pending'])
    def test_open_statuses_may_be_cancelled(self, svc_mod, status):
        with at(48):
            assert svc_mod.classify(appt(status)) == 'cancelled'

    @pytest.mark.parametrize('status', ['in_progress', 'completed', 'no_show', 'rescheduled'])
    def test_other_statuses_are_not_cancelable(self, svc_mod, status):
        with at(48):
            assert svc_mod.classify(appt(status)) == 'not_cancelable'

    def test_already_cancelled_is_reported_not_repeated(self, svc_mod):
        with at(48):
            assert svc_mod.classify(appt('cancelled')) == 'already_cancelled'

    def test_cutoff_comes_from_config(self, app, svc_mod):
        app.config['CLIENT_CANCEL_CUTOFF_HOURS'] = 24
        with at(20):
            assert svc_mod.classify(appt()) == 'too_late'
        app.config['CLIENT_CANCEL_CUTOFF_HOURS'] = 12

    def test_string_start_time_is_understood(self, svc_mod):
        row = appt()
        row['start_time'] = '14:00:00'
        with at(13):
            assert svc_mod.classify(row) == 'cancelled'


class _World:
    """All collaborators of cancel_by_client, recording call order on one parent mock."""

    def __init__(self):
        self.order = MagicMock()
        self.repo = self.order.repo
        self.effects = self.order.effects
        self.sms_events = self.order.sms_events
        self.status_event = self.order.status_event
        self.audit = self.order.audit

    def __enter__(self):
        @contextmanager
        def fake_tx():
            self.order.tx_begin()
            yield
            self.order.tx_commit()

        self._patches = [
            patch(f'{SVC}.managed_transaction', fake_tx),
            patch(f'{SVC}.AppointmentRepository', return_value=self.repo),
            patch(f'{SVC}.AppointmentBusinessService', return_value=self.effects),
            patch(f'{SVC}.SmsEventRepository', return_value=self.sms_events),
            patch(f'{SVC}.StatusChangeEventRepository', return_value=self.status_event),
            patch(f'{SVC}.AuditRepository', return_value=self.audit),
        ]
        for p in self._patches:
            p.start()
        return self

    def __exit__(self, *exc):
        for p in self._patches:
            p.stop()

    def names(self):
        return [c[0] for c in self.order.mock_calls]


class TestCancelByClient:
    def test_happy_path_does_everything_in_one_transaction_then_notifies(self, svc_mod):
        with _World() as w, at(48):
            outcome = svc_mod.cancel_by_client(appt('confirmed'), reason='powód')

        assert outcome == 'cancelled'
        w.repo.update_status.assert_called_once_with(100, 'cancelled', cancellation_reason='powód')
        w.effects.apply_status_change_side_effects.assert_called_once_with(100, 'confirmed', 'cancelled')
        w.sms_events.cancel_pending_for_appointment.assert_called_once_with(100)
        w.repo.update_confirmation_status.assert_not_called()        # plain cancel: not a decline

        names = w.names()
        inside = names[names.index('tx_begin'):names.index('tx_commit')]
        assert 'repo.update_status' in inside
        assert 'effects.apply_status_change_side_effects' in inside
        assert 'sms_events.cancel_pending_for_appointment' in inside
        after = names[names.index('tx_commit'):]
        assert 'status_event.create' in after and 'audit.log_event' in after   # best-effort extras

    def test_status_event_tells_the_desk_it_was_the_client(self, svc_mod):
        with _World() as w, at(48):
            svc_mod.cancel_by_client(appt(), reason='x')
        w.status_event.create.assert_called_once_with(100, 'scheduled', 'cancelled', 'client_sms')
        kwargs = w.audit.log_event.call_args.kwargs
        assert kwargs['user_name'] == 'Klient (SMS)' and kwargs['new_value'] == 'cancelled'

    def test_decline_restamps_declined_after_the_cancel_blanks_it(self, svc_mod):
        # update_status(..., 'cancelled') sets confirmation_status = NULL; the SMS stats
        # count 'declined', so it must be written AFTER, inside the same transaction.
        with _World() as w, at(48):
            svc_mod.cancel_by_client(appt(), reason='x', declined=True)
        w.repo.update_confirmation_status.assert_called_once_with(100, 'declined')
        names = w.names()
        assert names.index('repo.update_status') < names.index('repo.update_confirmation_status') < names.index('tx_commit')

    @pytest.mark.parametrize('status, hours, expected', [
        ('scheduled', 5, 'too_late'),
        ('cancelled', 48, 'already_cancelled'),
        ('completed', 48, 'not_cancelable'),
    ])
    def test_refusals_write_nothing_at_all(self, svc_mod, status, hours, expected):
        with _World() as w, at(hours):
            outcome = svc_mod.cancel_by_client(appt(status), reason='x', declined=True)
        assert outcome == expected
        assert w.names() == []

    def test_notification_failures_never_undo_the_cancellation(self, svc_mod):
        with _World() as w, at(48):
            w.status_event.create.side_effect = RuntimeError('poller table gone')
            w.audit.log_event.side_effect = RuntimeError('audit down')
            outcome = svc_mod.cancel_by_client(appt(), reason='x')
        assert outcome == 'cancelled'
        w.repo.update_status.assert_called_once()

    def test_a_failure_inside_the_transaction_propagates(self, svc_mod):
        with _World() as w, at(48):
            w.effects.apply_status_change_side_effects.side_effect = RuntimeError('boom')
            with pytest.raises(RuntimeError):
                svc_mod.cancel_by_client(appt(), reason='x')
        assert 'status_event.create' not in w.names()     # nothing announced for a failed cancel
