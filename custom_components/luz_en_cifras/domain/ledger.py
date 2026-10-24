"""Persistable raw counter intervals and effective price revisions."""

from __future__ import annotations

from dataclasses import asdict, replace
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from .errors import ConfigurationError
from .history import json_safe
from .intervals import MeasuredInterval, allocate_interval
from .models import ConsumptionGroup, EnergyRate, EnergySample


class MeasurementLedger:
    """Retain measurements and prices independently, including explicit gaps."""

    def __init__(self) -> None:
        self.baselines: dict[str, tuple[Decimal, datetime]] = {}
        self.intervals: list[MeasuredInterval] = []
        self.rates: list[EnergyRate] = []
        self.warnings: set[str] = set()
        self._last_interval: dict[str, int] = {}

    def observe(self, source: str, reading: Decimal, when: datetime) -> None:
        if not reading.is_finite() or reading < 0:
            raise ConfigurationError("Counter must be finite and non-negative")
        previous = self.baselines.get(source)
        self.baselines[source] = (reading, when)
        if previous is None:
            self.warnings.add(f"{source}: seguimiento sin histórico anterior")
            return
        old, start = previous
        if when.astimezone(UTC) <= start.astimezone(UTC):
            self.baselines[source] = previous
            return
        if reading < old:
            # A correction and a reset are indistinguishable without meter metadata.
            # Establish a new baseline; do not invent consumption equal to the reading.
            self.warnings.add(f"{source}: reinicio/corrección; intervalo no contabilizado")
            return
        interval = MeasuredInterval(source, start, when, reading - old)
        index = self._last_interval.get(source)
        if index is not None:
            prior = self.intervals[index]
            first, last = prior.start.astimezone(UTC), when.astimezone(UTC)
            same_hour = first.replace(minute=0, second=0, microsecond=0) == last.replace(
                minute=0, second=0, microsecond=0
            )
            price_changed = any(
                first < rate.valid_from.astimezone(UTC) < last for rate in self.rates
            )
            if prior.end == start and same_hour and not price_changed:
                self.intervals[index] = replace(prior, end=when, kwh=prior.kwh + interval.kwh)
                return
        self._last_interval[source] = len(self.intervals)
        self.intervals.append(interval)

    def price(
        self,
        group_id: str,
        value: Decimal | None,
        when: datetime,
        *,
        discount_rate: Decimal = Decimal(0),
    ) -> None:
        active = next(
            (
                rate
                for rate in reversed(self.rates)
                if rate.group_id == group_id and rate.valid_to is None
            ),
            None,
        )
        if active and value == active.eur_per_kwh and discount_rate == active.discount_rate:
            return
        if active:
            index = self.rates.index(active)
            if when.astimezone(UTC) <= active.valid_from.astimezone(UTC):
                self.rates.pop(index)
            else:
                self.rates[index] = replace(active, valid_to=when)
        if value is not None:
            if not value.is_finite():
                raise ConfigurationError("Price must be finite")
            self.rates.append(
                EnergyRate(
                    f"{group_id}:{when.isoformat()}",
                    group_id,
                    value,
                    when,
                    discount_rate=discount_rate,
                )
            )

    def billing_data(
        self,
        groups: tuple[ConsumptionGroup, ...],
        extra_rates: tuple[EnergyRate, ...] = (),
        *,
        approximate: bool = False,
    ) -> tuple[tuple[ConsumptionGroup, ...], tuple[EnergySample, ...], tuple[EnergyRate, ...]]:
        """Create independent priced source aliases per group after topology validation."""
        coefficients: dict[str, int] = {}
        for group in groups:
            for source in group.add_sources:
                coefficients[source] = coefficients.get(source, 0) + 1
            for source in group.subtract_sources:
                coefficients[source] = coefficients.get(source, 0) - 1
        if any(value > 1 for value in coefficients.values()):
            raise ConfigurationError("Duplicate billed source")
        rates = (*self.rates, *extra_rates)
        samples: list[EnergySample] = []
        aliases: list[ConsumptionGroup] = []
        for group in groups:

            def alias(source: str, group_id: str = group.group_id) -> str:
                return f"{group_id}|{source}"

            aliases.append(
                ConsumptionGroup(
                    group.group_id,
                    group.name,
                    tuple(alias(source) for source in group.add_sources),
                    tuple(alias(source) for source in group.subtract_sources),
                )
            )
            for interval in self.intervals:
                if interval.source_id not in (*group.add_sources, *group.subtract_sources):
                    continue
                samples.extend(
                    allocate_interval(
                        replace(interval, source_id=alias(interval.source_id)),
                        rates,
                        group.group_id,
                        allow_uniform_estimate=approximate,
                    )
                )
        return tuple(aliases), tuple(samples), tuple(rates)

    def serialize(self) -> dict[str, Any]:
        return {
            "baselines": {
                source: [str(value), when.isoformat()]
                for source, (value, when) in self.baselines.items()
            },
            "intervals": [json_safe(asdict(item)) for item in self.intervals],
            "rates": [json_safe(asdict(rate)) for rate in self.rates],
            "warnings": sorted(self.warnings),
        }

    @classmethod
    def restore(cls, data: dict[str, Any]) -> MeasurementLedger:
        ledger = cls()
        ledger.baselines = {
            source: (Decimal(value), datetime.fromisoformat(when))
            for source, (value, when) in data.get("baselines", {}).items()
        }
        ledger.intervals = [
            MeasuredInterval(
                item["source_id"],
                datetime.fromisoformat(item["start"]),
                datetime.fromisoformat(item["end"]),
                Decimal(item["kwh"]),
            )
            for item in data.get("intervals", [])
        ]
        ledger.rates = [
            EnergyRate(
                item["rate_id"],
                item["group_id"],
                Decimal(item["eur_per_kwh"]),
                datetime.fromisoformat(item["valid_from"]),
                datetime.fromisoformat(item["valid_to"]) if item.get("valid_to") else None,
                item.get("tariff_period"),
                Decimal(item.get("discount_rate", "0")),
            )
            for item in data.get("rates", [])
        ]
        ledger.warnings = set(data.get("warnings", []))
        ledger._last_interval = {
            item.source_id: index for index, item in enumerate(ledger.intervals)
        }
        return ledger
