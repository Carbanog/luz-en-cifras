"""Immutable models used by the billing engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum


class DataQuality(StrEnum):
    """Trust level of a calculated invoice."""

    COMPLETE = "complete"
    PARTIAL = "partial"


class BillingFrequency(StrEnum):
    """How a fixed charge is prorated."""

    INVOICE = "invoice"
    DAILY = "daily"


@dataclass(frozen=True, slots=True)
class BillingPeriod:
    """A half-open local-date period: start is included and end is excluded."""

    start: date
    end: date

    def __post_init__(self) -> None:
        if self.end <= self.start:
            raise ValueError("Billing period end must be after start")

    @property
    def days(self) -> int:
        """Return exact calendar days, unaffected by daylight-saving transitions."""
        return (self.end - self.start).days


@dataclass(frozen=True, slots=True)
class EnergySample:
    """Normalized energy consumed during an interval represented by its start."""

    source_id: str
    timestamp: datetime
    kwh: Decimal
    tariff_period: str = "flat"
    complete: bool = True

    def __post_init__(self) -> None:
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError("Energy sample timestamp must be timezone-aware")
        if self.kwh < 0:
            raise ValueError("Energy sample cannot be negative")


@dataclass(frozen=True, slots=True)
class ConsumptionGroup:
    """A billed group expressed as additions and explicit subset deductions."""

    group_id: str
    name: str
    add_sources: tuple[str, ...]
    subtract_sources: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.group_id or not self.name:
            raise ValueError("Group id and name are required")
        if not self.add_sources:
            raise ValueError("A group requires at least one added source")
        if len(set(self.add_sources)) != len(self.add_sources):
            raise ValueError("A source cannot be added twice to one group")
        if len(set(self.subtract_sources)) != len(self.subtract_sources):
            raise ValueError("A source cannot be subtracted twice from one group")
        overlap = set(self.add_sources) & set(self.subtract_sources)
        if overlap:
            raise ValueError(f"Sources cannot be both added and subtracted: {sorted(overlap)}")


@dataclass(frozen=True, slots=True)
class EnergyRate:
    """Energy price applicable to a group, tariff period, and time window."""

    rate_id: str
    group_id: str
    eur_per_kwh: Decimal
    valid_from: datetime
    valid_to: datetime | None = None
    tariff_period: str | None = None

    def __post_init__(self) -> None:
        if self.valid_from.tzinfo is None or self.valid_from.utcoffset() is None:
            raise ValueError("Rate validity must be timezone-aware")
        if self.valid_to is not None:
            if self.valid_to.tzinfo is None or self.valid_to.utcoffset() is None:
                raise ValueError("Rate validity must be timezone-aware")
            if self.valid_to <= self.valid_from:
                raise ValueError("Rate valid_to must be after valid_from")


@dataclass(frozen=True, slots=True)
class PowerCharge:
    """Contracted power charge already normalized to EUR/kW/day."""

    code: str
    label: str
    contracted_kw: Decimal
    eur_per_kw_day: Decimal

    def __post_init__(self) -> None:
        if self.contracted_kw < 0 or self.eur_per_kw_day < 0:
            raise ValueError("Power and its price cannot be negative")


@dataclass(frozen=True, slots=True)
class FixedCharge:
    """A configurable charge or credit."""

    code: str
    label: str
    amount: Decimal
    frequency: BillingFrequency = BillingFrequency.INVOICE
    electricity_taxable: bool = False
    vat_taxable: bool = True


@dataclass(frozen=True, slots=True)
class PercentageDiscount:
    """A percentage discount over selected pre-tax categories."""

    code: str
    label: str
    rate: Decimal
    categories: frozenset[str] = frozenset({"energy"})

    def __post_init__(self) -> None:
        if self.rate < 0 or self.rate > 1:
            raise ValueError("Discount rate must be between 0 and 1")
        if not self.categories:
            raise ValueError("Discount needs at least one category")


@dataclass(frozen=True, slots=True)
class FiscalRule:
    """Versioned tax rule selected by invoice tax point (devengo)."""

    rule_id: str
    valid_from: date
    valid_to: date | None
    electricity_tax_rate: Decimal
    vat_rate: Decimal
    minimum_electricity_eur_per_mwh: Decimal
    source_urls: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.valid_to is not None and self.valid_to <= self.valid_from:
            raise ValueError("Fiscal rule valid_to must be after valid_from")
        if not 0 <= self.electricity_tax_rate <= 1 or not 0 <= self.vat_rate <= 1:
            raise ValueError("Tax rates must be decimal fractions between 0 and 1")
        if self.minimum_electricity_eur_per_mwh < 0:
            raise ValueError("Minimum electricity tax cannot be negative")
        if not self.source_urls:
            raise ValueError("Fiscal rules require at least one source URL")


@dataclass(frozen=True, slots=True)
class InvoiceInput:
    """All reproducible inputs required for one estimate."""

    contract_id: str
    period: BillingPeriod
    tax_point: date
    samples: tuple[EnergySample, ...]
    groups: tuple[ConsumptionGroup, ...]
    energy_rates: tuple[EnergyRate, ...]
    fiscal_rule: FiscalRule
    power_charges: tuple[PowerCharge, ...] = ()
    fixed_charges: tuple[FixedCharge, ...] = ()
    discounts: tuple[PercentageDiscount, ...] = ()


@dataclass(frozen=True, slots=True)
class InvoiceLine:
    """A traceable line in the estimated invoice."""

    code: str
    label: str
    category: str
    amount: Decimal
    quantity: Decimal | None = None
    unit_price: Decimal | None = None
    electricity_taxable: bool = False
    vat_taxable: bool = True
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class InvoiceResult:
    """Calculated estimate and enough metadata to explain its quality."""

    contract_id: str
    period: BillingPeriod
    tax_point: date
    fiscal_rule_id: str
    lines: tuple[InvoiceLine, ...]
    subtotal: Decimal
    total: Decimal
    total_kwh: Decimal
    quality: DataQuality
    warnings: tuple[str, ...]

    def amount_for(self, category: str) -> Decimal:
        """Sum line amounts for one category."""
        return sum((line.amount for line in self.lines if line.category == category), Decimal())
