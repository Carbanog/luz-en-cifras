"""Translate versioned contract settings into reproducible domain inputs."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime, time
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from .engine import BillingEngine
from .errors import ConfigurationError, IncompleteDataError
from .fiscal import configured_rule
from .intervals import allocate_interval
from .ledger import MeasurementLedger
from .models import (
    BillingFrequency,
    BillingPeriod,
    ConsumptionGroup,
    EnergyRate,
    FixedCharge,
    InvoiceInput,
    InvoiceResult,
    PowerCharge,
)
from .tariffs import three_period_rates


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
    groups = tuple(
        ConsumptionGroup(
            item["group_id"],
            item["group_name"],
            tuple(item["add_sources"]),
            tuple(item.get("subtract_sources", [])),
        )
        for item in config["groups"]
    )
    zone = ZoneInfo("Europe/Madrid")
    begin = datetime.combine(period.start, time(), zone)
    finish = datetime.combine(period.end, time(), zone)
    timeline = revisions or [{"from": begin.isoformat(), "config": config}]
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
    extra: list[EnergyRate] = []
    power: list[PowerCharge] = []
    charges: list[FixedCharge] = []
    for start, end, revision in windows:
        discount = Decimal(str(revision.get("energy_discount_percent", 0))) / 100
        for group in revision["groups"]:
            if group.get("tariff_mode") == "three_period":
                extra.extend(
                    replace(rate, discount_rate=discount)
                    for rate in three_period_rates(
                        group["group_id"],
                        start,
                        end,
                        {f"P{n}": Decimal(str(group[f"p{n}_price"])) for n in (1, 2, 3)},
                    )
                )
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
    working = MeasurementLedger.restore(ledger.serialize())
    if revisions is None:
        discount = Decimal(str(config.get("energy_discount_percent", 0))) / 100
        working.rates = [replace(rate, discount_rate=discount) for rate in working.rates]
    aliases, samples, rates = working.billing_data(
        groups,
        tuple(extra),
        approximate=bool(config.get("approximate_intervals", False)),
    )
    credit = Decimal()
    if config.get("enable_surplus"):
        if period.days > 31:
            raise ConfigurationError(
                "Simplified surplus compensation requires a cycle no longer than one month"
            )
        source = config["export_source"]
        exports = [interval for interval in ledger.intervals if interval.source_id == source]
        if not exports:
            raise IncompleteDataError("No measured export intervals")
        for interval in exports:
            for sample in allocate_interval(
                interval,
                tuple(ledger.rates),
                "__surplus",
                allow_uniform_estimate=bool(config.get("approximate_intervals", False)),
            ):
                rate = BillingEngine._find_rate(tuple(ledger.rates), "__surplus", sample)
                credit += sample.kwh * rate.eur_per_kwh
    return BillingEngine().calculate(
        InvoiceInput(
            contract_id=config["contract_id"],
            period=period,
            tax_point=tax_point,
            samples=samples,
            groups=aliases,
            energy_rates=rates,
            fiscal_rule=fiscal_rule,
            power_charges=tuple(power),
            fixed_charges=tuple(charges),
            surplus_credit=credit,
        )
    )
