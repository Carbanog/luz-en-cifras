"""Price measured intervals without hiding missing coverage or time ambiguity."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from itertools import pairwise

from .errors import ConfigurationError, IncompleteDataError
from .models import EnergyRate, EnergySample


@dataclass(frozen=True, slots=True)
class MeasuredInterval:
    """A measured delta with explicit start and exclusive end instants."""

    source_id: str
    start: datetime
    end: datetime
    kwh: Decimal

    def __post_init__(self) -> None:
        for value in (self.start, self.end):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ConfigurationError("Interval timestamps must be timezone-aware")
        if self.end.astimezone(UTC) <= self.start.astimezone(UTC):
            raise ConfigurationError("Interval end must follow start")
        if not self.kwh.is_finite() or self.kwh < 0:
            raise ConfigurationError("Measured energy must be finite and non-negative")


def normalize_price(value: Decimal, unit: str) -> Decimal:
    """Normalize supported source units; negative market prices remain valid."""
    if not value.is_finite():
        raise ConfigurationError("Price must be finite")
    if unit in {"EUR/kWh", "€/kWh"}:
        return value
    if unit in {"EUR/MWh", "€/MWh"}:
        return value / Decimal(1000)
    raise ConfigurationError(f"Unsupported price unit: {unit}")


def allocate_interval(
    interval: MeasuredInterval,
    rates: tuple[EnergyRate, ...],
    group_id: str,
    *,
    allow_uniform_estimate: bool = False,
) -> tuple[EnergySample, ...]:
    """Split a measured delta at price boundaries, only estimating with consent.

    A total delta crossing prices cannot reveal the actual consumption in each
    segment. Default to rejecting it. Uniform elapsed-time allocation is an
    explicitly partial estimate; it is never presented as metered hourly energy.
    """
    start, end = interval.start.astimezone(UTC), interval.end.astimezone(UTC)
    candidates = tuple(rate for rate in rates if rate.group_id == group_id)
    boundaries = {start, end}
    for rate in candidates:
        for boundary in (rate.valid_from, rate.valid_to):
            if boundary is not None and start < boundary.astimezone(UTC) < end:
                boundaries.add(boundary.astimezone(UTC))
    ordered = sorted(boundaries)
    segments: list[tuple[datetime, datetime, EnergyRate]] = []
    for left, right in pairwise(ordered):
        matches = [
            rate
            for rate in candidates
            if rate.valid_from.astimezone(UTC) <= left
            and (rate.valid_to is None or right <= rate.valid_to.astimezone(UTC))
        ]
        if len(matches) != 1:
            raise IncompleteDataError("Missing or overlapping prices in measured interval")
        segments.append((left, right, matches[0]))
    estimated = len(segments) > 1
    if estimated and not allow_uniform_estimate:
        raise IncompleteDataError("Measured delta crosses prices without interval consumption")
    duration = Decimal(str((end - start).total_seconds()))
    allocated = Decimal()
    samples: list[EnergySample] = []
    for index, (left, right, rate) in enumerate(segments):
        energy = (
            interval.kwh - allocated
            if index == len(segments) - 1
            else interval.kwh * Decimal(str((right - left).total_seconds())) / duration
        )
        allocated += energy
        samples.append(
            EnergySample(
                interval.source_id,
                left,
                energy,
                rate.tariff_period or "flat",
                complete=not estimated,
            )
        )
    return tuple(samples)
