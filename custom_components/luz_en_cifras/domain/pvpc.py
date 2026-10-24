"""Validate published FEU hours without extending a price into missing time."""

from datetime import UTC, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any
from zoneinfo import ZoneInfo

from .errors import ConfigurationError


def validated_pvpc_prices(values: dict[datetime, Any]) -> dict[datetime, Decimal]:
    """Accept complete Madrid calendar days, including 23/25-hour DST days."""
    if not isinstance(values, dict) or not values or len(values) > 72:
        raise ConfigurationError("PVPC: empty or oversized published calendar")
    result: dict[datetime, Decimal] = {}
    for instant, value in values.items():
        if (
            not isinstance(instant, datetime)
            or instant.tzinfo is None
            or instant.utcoffset() is None
            or instant.minute
            or instant.second
            or instant.microsecond
        ):
            raise ConfigurationError("PVPC: invalid hourly timestamp")
        try:
            price = Decimal(str(value))
        except InvalidOperation as err:
            raise ConfigurationError("PVPC: invalid published price") from err
        if not price.is_finite():
            raise ConfigurationError("PVPC: non-finite published price")
        stamp = instant.astimezone(UTC)
        if stamp in result:
            raise ConfigurationError("PVPC: duplicate hour")
        result[stamp] = price
    zone = ZoneInfo("Europe/Madrid")
    for day in {instant.astimezone(zone).date() for instant in result}:
        start = datetime.combine(day, time(), zone).astimezone(UTC)
        end = datetime.combine(day + timedelta(days=1), time(), zone).astimezone(UTC)
        expected = {
            start + timedelta(hours=index)
            for index in range(int((end - start).total_seconds() / 3600))
        }
        actual = {stamp for stamp in result if start <= stamp < end}
        if actual != expected:
            raise ConfigurationError("PVPC: incomplete published day")
    return dict(sorted(result.items()))
