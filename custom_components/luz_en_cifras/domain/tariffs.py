"""Explicit contract prices and Spanish 2.0TD calendar."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from .errors import ConfigurationError
from .models import EnergyRate

# Circular 3/2020, art. 7.3: fixed national non-substitutable holidays plus Jan 6.
# Calendar is intentionally bounded to the verified year; no silent extrapolation.
HOLIDAYS_2026 = frozenset(
    date(2026, month, day)
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
    )
)


def period_20td(instant: datetime, zone: str = "Europe/Madrid") -> str:
    """Return P1/P2/P3 using the legal local calendar, including Ceuta/Melilla."""
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ConfigurationError("Tariff timestamp must be timezone-aware")
    local = instant.astimezone(ZoneInfo(zone))
    if local.year != 2026:
        raise ConfigurationError("No verified 2.0TD holiday calendar for this year")
    if local.weekday() >= 5 or local.date() in HOLIDAYS_2026 or local.hour < 8:
        return "P3"
    if zone in {"Africa/Ceuta", "Africa/Melilla"}:
        peak = 11 <= local.hour < 15 or 19 <= local.hour < 23
    else:
        peak = 10 <= local.hour < 14 or 18 <= local.hour < 22
    return "P1" if peak else "P2"


def three_period_rates(
    group_id: str,
    start: datetime,
    end: datetime,
    prices: dict[str, Decimal],
    zone: str = "Europe/Madrid",
) -> tuple[EnergyRate, ...]:
    """Generate real elapsed hourly intervals; repeated hours have distinct IDs."""
    if set(prices) != {"P1", "P2", "P3"} or not all(p.is_finite() for p in prices.values()):
        raise ConfigurationError("Three finite period prices are required")
    current, stop = start.astimezone(UTC), end.astimezone(UTC)
    result: list[EnergyRate] = []
    while current < stop:
        following = min(
            current.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1), stop
        )
        period = period_20td(current, zone)
        result.append(
            EnergyRate(
                f"{group_id}:{current.isoformat()}", group_id, prices[period], current, following
            )
        )
        current = following
    return tuple(result)
