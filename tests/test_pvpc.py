"""Synthetic published calendars exercise validation and both DST transitions."""

from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from custom_components.luz_en_cifras.domain.errors import ConfigurationError
from custom_components.luz_en_cifras.domain.pvpc import validated_pvpc_prices


def calendar(day: date) -> dict[datetime, str]:
    zone = ZoneInfo("Europe/Madrid")
    start = datetime.combine(day, time(), zone).astimezone(UTC)
    end = datetime.combine(day + timedelta(days=1), time(), zone).astimezone(UTC)
    return {
        start + timedelta(hours=index): "0.12345"
        for index in range(int((end - start).total_seconds() / 3600))
    }


def test_complete_days_respect_short_and_repeated_autumn_hours() -> None:
    for day, count in ((date(2026, 3, 29), 23), (date(2026, 10, 25), 25), (date(2026, 10, 24), 24)):
        values = validated_pvpc_prices(calendar(day))
        assert len(values) == count
        assert set(values.values()) == {Decimal("0.12345")}
        assert all(stamp.tzinfo == UTC for stamp in values)


def test_negative_prices_and_published_zero_remain_valid() -> None:
    values = calendar(date(2026, 10, 24))
    first, second, *_ = values
    values[first], values[second] = "-0.01", "0"
    result = validated_pvpc_prices(values)
    assert result[first] == Decimal("-0.01")
    assert result[second] == 0


def test_missing_hours_never_extend_the_previous_price() -> None:
    values = calendar(date(2026, 10, 24))
    values.pop(next(iter(values)))
    with pytest.raises(ConfigurationError, match="incomplete"):
        validated_pvpc_prices(values)


def test_invalid_price_and_unzoned_timestamp_are_rejected() -> None:
    for invalid in ("NaN", "Infinity", "not-a-price"):
        values = calendar(date(2026, 10, 24))
        values[next(iter(values))] = invalid
        with pytest.raises(ConfigurationError, match="price"):
            validated_pvpc_prices(values)
    with pytest.raises(ConfigurationError, match="timestamp"):
        validated_pvpc_prices({datetime(2026, 10, 24): "0.1"})
    with pytest.raises(ConfigurationError, match="empty"):
        validated_pvpc_prices({})
