"""utils.timezone month helpers behind the Historia SMS month picker (`?month=YYYY-MM`)."""
from datetime import datetime

import pytest

from utils.timezone import first_of_next_month, parse_year_month


class TestParseYearMonth:
    def test_a_month_parses(self):
        assert parse_year_month('2026-10') == (2026, 10)
        assert parse_year_month(' 2026-01 ') == (2026, 1)

    @pytest.mark.parametrize('empty', [None, ''])
    def test_absent_means_no_filter(self, empty):
        assert parse_year_month(empty) is None

    @pytest.mark.parametrize('bad', ['2026-13', '2026-00', '26-10', '2026/10', '2026-1', 'abc', '1999-12', '2101-01', '2026-10-01'])
    def test_anything_else_is_rejected(self, bad):
        with pytest.raises(ValueError):
            parse_year_month(bad)


class TestFirstOfNextMonth:
    def test_it_opens_the_following_month(self):
        assert first_of_next_month(2026, 10) == datetime(2026, 11, 1)

    def test_december_rolls_the_year(self):
        assert first_of_next_month(2026, 12) == datetime(2027, 1, 1)

    def test_february_of_a_leap_year_needs_no_special_case(self):
        assert first_of_next_month(2028, 2) == datetime(2028, 3, 1)
