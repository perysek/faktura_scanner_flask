"""services/status_timeline — the pure projection behind "Historia zmian statusu"."""
from datetime import datetime, timedelta

import pytest

from services.status_timeline import parse_status_value, standing_checkpoints

T0 = datetime(2026, 10, 2, 8, 0)


def _log(*steps):
    """steps: (new_value, minutes after T0) -> audit rows oldest-first."""
    return [{'new_value': value, 'timestamp': T0 + timedelta(minutes=m)} for value, m in steps]


class TestParseStatusValue:
    @pytest.mark.parametrize('raw, expected', [
        ('confirmed', ('confirmed', None)),
        ('cancelled (klientka zachorowała)', ('cancelled', 'klientka zachorowała')),
        ('scheduled (zmiana terminu przez salon)', ('scheduled', 'zmiana terminu przez salon')),
        ('  completed  ', ('completed', None)),
        ('cancelled ()', ('cancelled', None)),
        ('cancelled (bez nawiasu zamykającego', ('cancelled', 'bez nawiasu zamykającego')),
        ('cancelled (a (b))', ('cancelled', 'a (b)')),
        ('', ('', None)),
        (None, ('', None)),
    ])
    def test_split(self, raw, expected):
        assert parse_status_value(raw) == expected


class TestReplay:
    def test_a_forward_walk_keeps_every_checkpoint(self):
        got = standing_checkpoints(_log(('confirmed', 10), ('in_progress', 60), ('completed', 120)), 'completed')
        assert set(got) == {'confirmed', 'in_progress', 'completed'}

    def test_going_back_to_scheduled_voids_confirmation(self):
        got = standing_checkpoints(_log(('confirmed', 10), ('scheduled', 20)), 'scheduled')
        assert 'confirmed' not in got

    def test_going_back_voids_only_the_checkpoints_above_it(self):
        got = standing_checkpoints(_log(('confirmed', 10), ('in_progress', 60), ('completed', 120), ('in_progress', 130)),
                                   'in_progress')
        assert set(got) == {'confirmed', 'in_progress'}
        assert got['in_progress'] == T0 + timedelta(minutes=130)        # the LATEST entry stands

    def test_reconfirming_after_a_revert_uses_the_latest_confirmation(self):
        got = standing_checkpoints(_log(('confirmed', 10), ('scheduled', 20), ('confirmed', 30)), 'confirmed')
        assert got['confirmed'] == T0 + timedelta(minutes=30)

    def test_cancellation_keeps_how_far_the_visit_got(self):
        got = standing_checkpoints(_log(('confirmed', 10), ('cancelled (rezygnacja)', 20)), 'cancelled')
        assert set(got) == {'confirmed', 'cancelled'}

    def test_reopening_a_cancelled_visit_clears_the_cancellation_and_the_old_confirmation(self):
        got = standing_checkpoints(_log(('confirmed', 10), ('cancelled', 20), ('scheduled', 30)), 'scheduled')
        assert got == {'scheduled': T0 + timedelta(minutes=30)}

    def test_no_show_then_back_on_the_happy_path_clears_the_no_show(self):
        got = standing_checkpoints(_log(('confirmed', 10), ('no_show', 20), ('confirmed', 30)), 'confirmed')
        assert 'no_show' not in got

    def test_unknown_and_rescheduled_values_are_ignored_by_the_replay(self):
        got = standing_checkpoints(_log(('confirmed', 10), ('rescheduled', 20), ('pending', 25)), 'rescheduled')
        assert set(got) == {'confirmed'}


class TestReconciliationWithTheCurrentStatus:
    def test_nothing_above_the_current_status_survives_an_incomplete_log(self):
        # the log says completed, the row says confirmed (e.g. a status written without an audit row)
        got = standing_checkpoints(_log(('confirmed', 10), ('in_progress', 60), ('completed', 120)), 'confirmed')
        assert set(got) == {'confirmed'}

    def test_a_current_cancellation_drops_a_stale_no_show(self):
        got = standing_checkpoints(_log(('no_show', 10), ('cancelled', 20)), 'cancelled')
        assert set(got) == {'cancelled'}

    def test_the_current_status_is_filled_from_the_fallback_only_when_the_log_lacks_it(self):
        fallback = {'confirmed': T0 + timedelta(minutes=99)}
        assert standing_checkpoints([], 'confirmed', fallback) == fallback
        assert standing_checkpoints(_log(('confirmed', 10)), 'confirmed', fallback) == {'confirmed': T0 + timedelta(minutes=10)}

    def test_a_missing_fallback_leaves_the_checkpoint_pending(self):
        assert standing_checkpoints([], 'confirmed', {'confirmed': None}) == {}
        assert standing_checkpoints([], 'confirmed', None) == {}

    def test_scheduled_current_with_an_empty_log_reaches_nothing_else(self):
        assert standing_checkpoints([], 'scheduled') == {}
