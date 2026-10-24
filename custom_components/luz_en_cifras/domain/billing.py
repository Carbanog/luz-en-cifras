"""Translate versioned contract settings into reproducible domain inputs."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime, time
from decimal import Decimal
from itertools import pairwise
from typing import Any
from zoneinfo import ZoneInfo

from .engine import BillingEngine
from .errors import ConfigurationError, IncompleteDataError
from .fiscal import configured_rule
from .intervals import allocate_interval, clip_interval
from .ledger import MeasurementLedger
from .models import (
    BillingFrequency,
    BillingPeriod,
    ConsumptionGroup,
    DataQuality,
    EnergyRate,
    EnergySample,
    FixedCharge,
    InvoiceInput,
    InvoiceResult,
    PowerCharge,
)
from .tariffs import three_period_rates


def _energy_settings(config: dict[str, Any]) -> dict[str, Any]:
    """Ignore presentation and daily fees when deciding measurement boundaries."""
    return {
        "groups": sorted(
            (
                {key: value for key, value in group.items() if key != "group_name"}
                for group in config["groups"]
            ),
            key=lambda group: group["group_id"],
        ),
        **{
            key: config.get(key, default)
            for key, default in (
                ("energy_discount_percent", 0),
                ("enable_surplus", False),
                ("export_source", None),
                ("surplus_price", 0),
            )
        },
    }


def _window_energy(
    config: dict[str, Any],
    ledger: MeasurementLedger,
    start: datetime,
    end: datetime,
    suffix: str,
    *,
    approximate: bool,
) -> tuple[
    tuple[ConsumptionGroup, ...],
    tuple[EnergySample, ...],
    tuple[EnergyRate, ...],
    dict[str, str],
    set[str],
]:
    """Price only the source expression effective in one revision, with unique aliases."""
    working = MeasurementLedger()
    source_ids = {
        source
        for group in config["groups"]
        for source in (*group["add_sources"], *group.get("subtract_sources", []))
    }
    for interval in ledger.intervals:
        if interval.source_id in source_ids:
            clipped = clip_interval(interval, start, end, approximate=approximate)
            if clipped is not None:
                working.intervals.append(clipped)
    # Validate physical double-counting before aliases hide the original source IDs.
    coefficients: dict[str, int] = {}
    for item in config["groups"]:
        for source in item["add_sources"]:
            coefficients[source] = coefficients.get(source, 0) + 1
        for source in item.get("subtract_sources", []):
            coefficients[source] = coefficients.get(source, 0) - 1
    if any(value > 1 for value in coefficients.values()):
        raise ConfigurationError("Duplicate billed source in configuration revision")
    groups = []
    identities = {}
    warnings = set()
    measured = {interval.source_id for interval in working.intervals}
    discount = Decimal(str(config.get("energy_discount_percent", 0))) / 100
    for item in config["groups"]:
        physical = (*item["add_sources"], *item.get("subtract_sources", []))
        if not measured.intersection(physical):
            warnings.add(
                f"{item['group_name']}: esperando mediciones del tramo desde "
                f"{start.isoformat()}; no se asume consumo cero"
            )
            continue
        virtual = f"{item['group_id']}@{suffix}"
        identities[virtual] = item["group_id"]
        groups.append(
            ConsumptionGroup(
                virtual,
                item["group_name"],
                tuple(item["add_sources"]),
                tuple(item.get("subtract_sources", [])),
            )
        )
        mode = item.get("tariff_mode", "fixed")
        if mode == "fixed" and "eur_per_kwh" in item:
            # Fixed contractual prices are known for the whole revision, unlike
            # observed dynamic quotes. This also prices pre-0.2.1 startup data
            # without deleting measurements or modifying stored quote history.
            working.rates.append(
                EnergyRate(
                    f"{virtual}:fixed",
                    virtual,
                    Decimal(str(item["eur_per_kwh"])),
                    start,
                    valid_to=end,
                    discount_rate=discount,
                )
            )
        elif mode == "three_period":
            working.rates.extend(
                replace(rate, discount_rate=discount)
                for rate in three_period_rates(
                    virtual,
                    start,
                    end,
                    {f"P{n}": Decimal(str(item[f"p{n}_price"])) for n in (1, 2, 3)},
                )
            )
        else:
            for rate in ledger.rates:
                if rate.group_id != item["group_id"]:
                    continue
                if (mode == "pvpc") != rate.rate_id.startswith("pvpc:"):
                    continue
                left = max(start.astimezone(UTC), rate.valid_from.astimezone(UTC))
                right = min(
                    end.astimezone(UTC),
                    rate.valid_to.astimezone(UTC) if rate.valid_to else end.astimezone(UTC),
                )
                if left < right:
                    working.rates.append(
                        replace(
                            rate,
                            rate_id=f"{rate.rate_id}@{suffix}",
                            group_id=virtual,
                            valid_from=left,
                            valid_to=right,
                            discount_rate=discount,
                        )
                    )
    aliases, samples, rates = working.billing_data(tuple(groups), approximate=approximate)
    return aliases, samples, rates, identities, warnings


def calculate_contract(
    config: dict[str, Any],
    ledger: MeasurementLedger,
    period: BillingPeriod,
    tax_point: date,
    *,
    revisions: list[dict[str, Any]] | None = None,
) -> InvoiceResult:
    """Use effective energy prices and daily contract revisions without rewriting history."""
    fiscal_rule = configured_rule(config, tax_point)
    zone = ZoneInfo("Europe/Madrid")
    begin = datetime.combine(period.start, time(), zone)
    finish = datetime.combine(period.end, time(), zone)
    timeline = revisions or [{"from": begin.isoformat(), "config": config}]
    instants = [datetime.fromisoformat(item["from"]).astimezone(UTC) for item in timeline]
    if any(left > right for left, right in pairwise(instants)):
        raise ConfigurationError("Configuration revisions must be chronological")
    windows = []
    for index, revision in enumerate(timeline):
        start = max(begin, datetime.fromisoformat(revision["from"]))
        end = min(
            finish,
            datetime.fromisoformat(timeline[index + 1]["from"])
            if index + 1 < len(timeline)
            else finish,
        )
        if start.astimezone(UTC) < end.astimezone(UTC):
            windows.append((start, end, revision["config"]))
    aliases: list[ConsumptionGroup] = []
    samples: list[EnergySample] = []
    rates: list[EnergyRate] = []
    identities: dict[str, str] = {}
    warnings: set[str] = set()
    credit = Decimal()
    approximate = bool(config.get("approximate_intervals", False))
    power: list[PowerCharge] = []
    charges: list[FixedCharge] = []
    energy_windows: list[tuple[datetime, datetime, dict[str, Any]]] = []
    for start, end, revision in windows:
        if (
            energy_windows
            and energy_windows[-1][1] == start
            and _energy_settings(energy_windows[-1][2]) == _energy_settings(revision)
        ):
            previous_start, _, _ = energy_windows[-1]
            energy_windows[-1] = (previous_start, end, revision)
        else:
            energy_windows.append((start, end, revision))
    for index, (start, end, revision) in enumerate(energy_windows):
        window_groups, window_samples, window_rates, window_ids, window_warnings = _window_energy(
            revision,
            ledger,
            start,
            end,
            f"{index}:{start.isoformat()}",
            approximate=approximate,
        )
        aliases.extend(window_groups)
        samples.extend(window_samples)
        rates.extend(window_rates)
        identities.update(window_ids)
        warnings.update(window_warnings)
        if revision.get("enable_surplus"):
            if period.days > 31:
                raise ConfigurationError(
                    "Simplified surplus compensation requires a cycle no longer than one month"
                )
            exports = [
                clipped
                for interval in ledger.intervals
                if interval.source_id == revision["export_source"]
                and (
                    clipped := clip_interval(
                        interval,
                        start,
                        end,
                        approximate=approximate,
                    )
                )
                is not None
            ]
            if not exports and window_samples:
                raise IncompleteDataError("No measured export intervals in configuration revision")
            for interval in exports:
                for sample in allocate_interval(
                    interval,
                    tuple(ledger.rates),
                    "__surplus",
                    allow_uniform_estimate=approximate,
                ):
                    rate = BillingEngine._find_rate(tuple(ledger.rates), "__surplus", sample)
                    credit += sample.kwh * rate.eur_per_kwh
    for start, end, revision in windows:
        divisor = Decimal(365) if revision.get("power_price_unit") == "year" else Decimal(1)
        # Power and daily charges change at the effective local calendar date.
        left, right = start.astimezone(zone).date(), end.astimezone(zone).date()
        for code in ("p1", "p2"):
            power.append(
                PowerCharge(
                    f"{code}:{start.isoformat()}",
                    f"Potencia {code.upper()}",
                    Decimal(str(revision.get(f"power_{code}_kw", 0))),
                    Decimal(str(revision.get(f"power_{code}_eur_per_kw_day", 0))) / divisor,
                    left,
                    right,
                )
            )
        for code, label, key, taxable in (
            ("rental", "Alquiler de contador", "meter_rental_daily", False),
            (
                "daily",
                "Cuota diaria",
                "daily_fee",
                bool(revision.get("daily_fee_electricity_taxable", False)),
            ),
        ):
            charges.append(
                FixedCharge(
                    f"{code}:{start.isoformat()}",
                    label,
                    Decimal(str(revision.get(key, 0))),
                    BillingFrequency.DAILY,
                    electricity_taxable=taxable,
                    vat_rate_override=(
                        Decimal(str(revision.get("fees_tax_percent", 21))) / 100
                        if code == "daily"
                        else None
                    ),
                    valid_from=left,
                    valid_to=right,
                )
            )
    # An invoice-level service is charged once according to the latest configuration.
    if config.get("invoice_fee"):
        charges.append(
            FixedCharge(
                "invoice",
                "Servicio por factura",
                Decimal(str(config["invoice_fee"])),
                vat_rate_override=Decimal(str(config.get("fees_tax_percent", 21))) / 100,
            )
        )
    if not samples:
        raise IncompleteDataError("No measurements for sources in the billing period")
    result = BillingEngine().calculate(
        InvoiceInput(
            contract_id=config["contract_id"],
            period=period,
            tax_point=tax_point,
            samples=tuple(samples),
            groups=tuple(aliases),
            energy_rates=tuple(rates),
            fiscal_rule=fiscal_rule,
            power_charges=tuple(power),
            fixed_charges=tuple(charges),
            surplus_credit=credit,
        )
    )
    lines = tuple(
        replace(
            line,
            metadata={
                **line.metadata,
                "segment_group_id": line.metadata["group_id"],
                "group_id": identities[line.metadata["group_id"]],
            },
        )
        if line.category == "energy"
        else line
        for line in result.lines
    )
    return replace(
        result,
        lines=lines,
        quality=DataQuality.PARTIAL if warnings else result.quality,
        warnings=(*result.warnings, *sorted(warnings)),
    )
