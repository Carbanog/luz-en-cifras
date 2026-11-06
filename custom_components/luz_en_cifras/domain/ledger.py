"""Persistable raw counter intervals and effective price revisions."""

from __future__ import annotations

from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from .errors import ConfigurationError
from .history import json_safe
from .intervals import MeasuredInterval, allocate_interval, clip_interval
from .models import ConsumptionGroup, EnergyRate, EnergySample
from .prices import PriceIndex


class MeasurementLedger:
    """Retain measurements and prices independently, including explicit gaps."""

    def __init__(self) -> None:
        self.baselines: dict[str, tuple[Decimal, datetime]] = {}
        self.intervals: list[MeasuredInterval] = []
        self.rates: list[EnergyRate] = []
        self.warnings: set[str] = set()
        self._last_interval: dict[str, int] = {}
        self.input_kinds: dict[str, str] = {}
        self.power_samples: dict[str, tuple[Decimal, datetime, datetime]] = {}
        self.revision_boundaries: list[datetime] = []
        self.pending_energy_sources: dict[str, datetime] = {}

    def observe_input(
        self,
        source: str,
        value: Decimal | None,
        unit: str,
        when: datetime,
        *,
        reported_at: datetime | None = None,
        max_age_seconds: int = 300,
    ) -> None:
        """Detect units, normalize to kWh and integrate power using the left rule."""
        kind = "power" if unit in {"W", "kW"} else "energy" if unit in {"Wh", "kWh"} else None
        if kind is None or value is None or not value.is_finite() or value < 0:
            self.advance_power(source, when, max_age_seconds)
            self.power_samples.pop(source, None)
            self.warnings.add(
                f"{source}: lectura/unidad no válida o no disponible; sin inventar consumo"
            )
            return
        if source in self.input_kinds and self.input_kinds[source] != kind:
            self.advance_power(source, when, max_age_seconds)
            self.power_samples.pop(source, None)
            self.baselines.pop(source, None)
            self.warnings.add(f"{source}: tipo de medición cambiado; nueva referencia")
        self.input_kinds[source] = kind
        normalized = value / 1000 if unit in {"W", "Wh"} else value
        if kind == "energy":
            reported = reported_at or when
            activation = self.pending_energy_sources.get(source)
            if activation is not None:
                if reported.astimezone(UTC) < activation.astimezone(UTC):
                    self.warnings.add(
                        f"{source}: esperando lectura nueva tras seleccionar el contador"
                    )
                    return
                self.pending_energy_sources.pop(source)
                self.baselines.pop(source, None)
            self.observe(source, normalized, reported)
            return
        self.advance_power(source, when, max_age_seconds)
        self.power_samples[source] = (normalized, reported_at or when, when)
        self.warnings.add(f"{source}: energía estimada desde potencia (regla izquierda)")

    def advance_power(self, source: str, when: datetime, max_age_seconds: int = 300) -> None:
        """Accumulate only observed live time, bounded by the last genuine report."""
        previous = self.power_samples.get(source)
        if previous is None:
            return
        kw, reported, cursor = previous
        end = min(
            when.astimezone(UTC), reported.astimezone(UTC) + timedelta(seconds=max_age_seconds)
        )
        start = cursor.astimezone(UTC)
        if end > start:
            energy = kw * Decimal(str((end - start).total_seconds())) / Decimal(3600)
            self._append_interval(MeasuredInterval(source, start, end, energy, estimated=True))
        if when.astimezone(UTC) > end:
            self.warnings.add(f"{source}: potencia caducada; hueco no reconstruido")
        self.power_samples[source] = (kw, reported, max(when.astimezone(UTC), start))

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
        self._append_interval(interval)

    def _append_interval(self, interval: MeasuredInterval) -> None:
        source, start, when = interval.source_id, interval.start, interval.end
        index = self._last_interval.get(source)
        if index is not None:
            prior = self.intervals[index]
            first, last = prior.start.astimezone(UTC), when.astimezone(UTC)
            same_hour = first.replace(minute=0, second=0, microsecond=0) == last.replace(
                minute=0, second=0, microsecond=0
            )
            price_changed = any(
                first < rate.valid_from.astimezone(UTC) < last for rate in self.rates
            ) or any(
                first < boundary.astimezone(UTC) < last for boundary in self.revision_boundaries
            )
            if (
                prior.end == start
                and same_hour
                and not price_changed
                and prior.estimated == interval.estimated
            ):
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
        price_index = PriceIndex(rates)
        samples: list[EnergySample] = []
        aliases: list[ConsumptionGroup] = []
        for group in groups:

            def alias(source: str, group_id: str = group.group_id) -> str:
                return f"{group_id}|{source}"

            selected = [
                interval
                for interval in self.intervals
                if interval.source_id in (*group.add_sources, *group.subtract_sources)
            ]
            if group.subtract_sources:
                sources = (*group.add_sources, *group.subtract_sources)
                original = selected
                while True:
                    coverage = {
                        source: [item for item in selected if item.source_id == source]
                        for source in sources
                    }
                    if any(not intervals for intervals in coverage.values()):
                        selected = []
                        break
                    left = max(
                        min(item.start.astimezone(UTC) for item in values)
                        for values in coverage.values()
                    )
                    right = min(
                        max(item.end.astimezone(UTC) for item in values)
                        for values in coverage.values()
                    )
                    aligned = []
                    for interval in selected:
                        if (
                            interval.end.astimezone(UTC) <= left
                            or interval.start.astimezone(UTC) >= right
                        ):
                            continue
                        if not (approximate or interval.estimated) and (
                            interval.start.astimezone(UTC) < left
                            or interval.end.astimezone(UTC) > right
                        ):
                            continue
                        clipped = clip_interval(interval, left, right, approximate=approximate)
                        if clipped is not None:
                            aligned.append(clipped)
                    if aligned == selected:
                        break
                    # Dropping an unsplittable tail can move the common horizon
                    # again. Recheck every source before comparing residuals.
                    selected = aligned
                if not selected:
                    self.warnings.add(f"{group.name}: esperando cobertura común de contadores")
                    continue
                if selected != original:
                    self.warnings.add(
                        f"{group.name}: consumos fuera de la cobertura común pendientes"
                    )
            aliases.append(
                ConsumptionGroup(
                    group.group_id,
                    group.name,
                    tuple(alias(source) for source in group.add_sources),
                    tuple(alias(source) for source in group.subtract_sources),
                )
            )
            for interval in selected:
                samples.extend(
                    allocate_interval(
                        replace(interval, source_id=alias(interval.source_id)),
                        price_index.window(group.group_id, interval.start, interval.end),
                        group.group_id,
                        allow_uniform_estimate=approximate,
                    )
                )
        return tuple(aliases), tuple(samples), tuple(rates)

    def next_cycle(self, boundary: datetime) -> MeasurementLedger:
        """Carry real meter cursors over a cycle; never reset an unread delta."""
        following = MeasurementLedger()
        following.baselines = dict(self.baselines)
        following.input_kinds = dict(self.input_kinds)
        following.power_samples = dict(self.power_samples)
        following.pending_energy_sources = dict(self.pending_energy_sources)
        following.rates = [
            rate
            for rate in self.rates
            if rate.valid_to is None or rate.valid_to.astimezone(UTC) > boundary.astimezone(UTC)
        ]
        for interval in self.intervals:
            if interval.end.astimezone(UTC) > boundary.astimezone(UTC):
                following._append_interval(interval)
        return following

    def last_interval(self, source: str) -> MeasuredInterval | None:
        index = self._last_interval.get(source)
        return self.intervals[index] if index is not None else None

    def serialize(self) -> dict[str, Any]:
        return {
            "pending_energy_sources": {
                source: instant.isoformat()
                for source, instant in self.pending_energy_sources.items()
            },
            "revision_boundaries": [boundary.isoformat() for boundary in self.revision_boundaries],
            "input_kinds": dict(self.input_kinds),
            "power_samples": {
                source: [str(kw), report.isoformat(), cursor.isoformat()]
                for source, (kw, report, cursor) in self.power_samples.items()
            },
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
        ledger.pending_energy_sources = {
            source: datetime.fromisoformat(value)
            for source, value in data.get("pending_energy_sources", {}).items()
        }
        ledger.revision_boundaries = [
            datetime.fromisoformat(value) for value in data.get("revision_boundaries", [])
        ]
        ledger.input_kinds = dict(data.get("input_kinds", {}))
        ledger.power_samples = {
            source: (Decimal(kw), datetime.fromisoformat(report), datetime.fromisoformat(cursor))
            for source, (kw, report, cursor) in data.get("power_samples", {}).items()
        }
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
                bool(item.get("estimated", False)),
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
