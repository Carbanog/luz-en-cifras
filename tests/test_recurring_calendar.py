"""Recurring tariff rules remain local and usable beyond published annual tables."""

from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from custom_components.luz_en_cifras.domain.errors import ConfigurationError
from custom_components.luz_en_cifras.domain.tariffs import period_20td, three_period_rates

ZONE = ZoneInfo("Europe/Madrid")


def test_fixed_holidays_recur_across_years_and_centuries() -> None:
    for year in (2026, 2027, 2028, 2030, 2050, 2100, 2400):
        for month, day in (
            (1, 1),
            (1, 6),
            (5, 1),
            (8, 15),
            (10, 12),
            (11, 1),
            (12, 6),
            (12, 8),
            (12, 25),
        ):
            assert period_20td(datetime(year, month, day, 12, tzinfo=ZONE)) == "P3"


def test_future_weekday_hours_and_weekend() -> None:
    # Tuesday 29 February 2028: leap day is an ordinary weekday.
    assert [
        period_20td(datetime(2028, 2, 29, hour, tzinfo=ZONE)) for hour in (7, 8, 10, 14, 18, 22)
    ] == ["P3", "P2", "P1", "P2", "P1", "P2"]
    assert period_20td(datetime(2028, 3, 4, 12, tzinfo=ZONE)) == "P3"
    # 2100 is not a leap year; 2400 is. Neither needs an annual release.
    assert period_20td(datetime(2100, 3, 1, 12, tzinfo=ZONE)) == "P1"
    assert period_20td(datetime(2400, 2, 29, 12, tzinfo=ZONE)) == "P1"


def test_movable_and_substitute_holidays_are_not_added_to_valley() -> None:
    # Good Friday 2030 and Monday after the 2028 New Year's Day Saturday.
    assert period_20td(datetime(2030, 4, 19, 12, tzinfo=ZONE)) == "P1"
    assert period_20td(datetime(2028, 1, 3, 12, tzinfo=ZONE)) == "P1"


def test_rate_generation_crosses_future_new_year_and_leap_day() -> None:
    prices = {"P1": Decimal("0.3"), "P2": Decimal("0.2"), "P3": Decimal("0.1")}
    for start, hours in (
        (datetime(2027, 12, 31, tzinfo=ZONE), 48),
        (datetime(2028, 2, 28, tzinfo=ZONE), 72),
    ):
        rates = three_period_rates("g", start, start + timedelta(hours=hours), prices)
        assert len(rates) == len({rate.rate_id for rate in rates}) == hours
        assert (
            sum(
                (
                    Decimal(str((rate.valid_to - rate.valid_from).total_seconds()))
                    for rate in rates
                    if rate.valid_to
                ),
                Decimal(),
            )
            == hours * 3600
        )
    january = three_period_rates(
        "g", datetime(2100, 1, 1, tzinfo=ZONE), datetime(2100, 1, 2, tzinfo=ZONE), prices
    )
    assert {rate.tariff_period for rate in january} == {"P3"}


def test_future_dst_still_uses_real_elapsed_hours() -> None:
    prices = {"P1": Decimal(1), "P2": Decimal(2), "P3": Decimal(3)}
    for month, day, hours in ((3, 31, 23), (10, 27, 25)):
        start = datetime(2030, month, day, tzinfo=ZONE)
        rates = three_period_rates("g", start, start + timedelta(days=1), prices)
        assert len(rates) == len({rate.rate_id for rate in rates}) == hours


def test_naive_dates_still_rejected() -> None:
    with pytest.raises(ConfigurationError, match="timezone-aware"):
        period_20td(datetime(2030, 1, 1))
