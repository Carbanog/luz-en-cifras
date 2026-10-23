"""Deterministic electricity bill estimation engine."""

from __future__ import annotations

from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal, localcontext

from .errors import ConfigurationError, IncompleteDataError
from .models import (
    BillingFrequency,
    DataQuality,
    EnergyRate,
    EnergySample,
    InvoiceInput,
    InvoiceLine,
    InvoiceResult,
)

CENT = Decimal("0.01")
DISPLAY_ENERGY = Decimal("0.001")


def _money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


class BillingEngine:
    """Calculate an auditable estimate from normalized, immutable inputs."""

    def calculate(self, invoice: InvoiceInput) -> InvoiceResult:
        """Validate and calculate one estimate.

        Missing prices and unsafe source topologies fail closed instead of silently
        treating data as zero.
        """
        with localcontext() as context:
            context.prec = 28
            self._validate(invoice)
            lines, total_kwh, incomplete_sources = self._energy_lines(invoice)
            lines.extend(self._power_lines(invoice))
            lines.extend(self._fixed_lines(invoice))
            lines.extend(self._discount_lines(invoice, lines))

            electricity_base = sum(
                (line.amount for line in lines if line.electricity_taxable), Decimal()
            )
            electricity_tax = electricity_base * invoice.fiscal_rule.electricity_tax_rate
            minimum_tax = (
                total_kwh / Decimal("1000") * (invoice.fiscal_rule.minimum_electricity_eur_per_mwh)
            )
            electricity_tax = max(electricity_tax, minimum_tax)
            tax_line = InvoiceLine(
                code="electricity_tax",
                label="Impuesto especial sobre la electricidad",
                category="electricity_tax",
                amount=electricity_tax,
                vat_taxable=True,
                metadata={"fiscal_rule_id": invoice.fiscal_rule.rule_id},
            )
            lines.append(tax_line)

            vat_base = sum((line.amount for line in lines if line.vat_taxable), Decimal())
            lines.append(
                InvoiceLine(
                    code="vat",
                    label="IVA",
                    category="vat",
                    amount=vat_base * invoice.fiscal_rule.vat_rate,
                    vat_taxable=False,
                    metadata={"fiscal_rule_id": invoice.fiscal_rule.rule_id},
                )
            )

            subtotal = sum((line.amount for line in lines if line.category != "vat"), Decimal())
            total = sum((line.amount for line in lines), Decimal())
            warnings = tuple(
                f"La fuente {source_id} contiene intervalos marcados como incompletos"
                for source_id in sorted(incomplete_sources)
            )
            return InvoiceResult(
                contract_id=invoice.contract_id,
                period=invoice.period,
                tax_point=invoice.tax_point,
                fiscal_rule_id=invoice.fiscal_rule.rule_id,
                lines=tuple(lines),
                subtotal=_money(subtotal),
                total=_money(total),
                total_kwh=total_kwh.quantize(DISPLAY_ENERGY, rounding=ROUND_HALF_UP),
                quality=DataQuality.PARTIAL if warnings else DataQuality.COMPLETE,
                warnings=warnings,
            )

    def _validate(self, invoice: InvoiceInput) -> None:
        if invoice.tax_point < invoice.period.start:
            raise ConfigurationError("Tax point cannot be before the billing period")
        if invoice.fiscal_rule.valid_from > invoice.tax_point or (
            invoice.fiscal_rule.valid_to is not None
            and invoice.tax_point >= invoice.fiscal_rule.valid_to
        ):
            raise ConfigurationError("Fiscal rule is not valid at the invoice tax point")

        for sample in invoice.samples:
            if not invoice.period.start <= sample.timestamp.date() < invoice.period.end:
                raise ConfigurationError(
                    f"Sample for {sample.source_id} falls outside the billing period"
                )

        coefficients: dict[str, int] = defaultdict(int)
        seen_group_ids: set[str] = set()
        for group in invoice.groups:
            if group.group_id in seen_group_ids:
                raise ConfigurationError(f"Duplicate group id: {group.group_id}")
            seen_group_ids.add(group.group_id)
            for source_id in group.add_sources:
                coefficients[source_id] += 1
            for source_id in group.subtract_sources:
                coefficients[source_id] -= 1
        # A negative aggregate coefficient is valid for a residual-only group
        # (for example, main meter minus an EV submeter). Values above one mean
        # the same measured energy is billed more than once.
        unsafe = {source_id: value for source_id, value in coefficients.items() if value > 1}
        if unsafe:
            details = ", ".join(f"{source}={coefficient}" for source, coefficient in unsafe.items())
            raise ConfigurationError(
                f"Unsafe source topology (possible double counting): {details}"
            )

        configured_sources = set(coefficients)
        measured_sources = {sample.source_id for sample in invoice.samples}
        missing = configured_sources - measured_sources
        if missing:
            raise IncompleteDataError(f"No measurements for sources: {', '.join(sorted(missing))}")

    def _energy_lines(self, invoice: InvoiceInput) -> tuple[list[InvoiceLine], Decimal, set[str]]:
        lines: list[InvoiceLine] = []
        total_kwh = Decimal()
        incomplete_sources: set[str] = set()

        for group in invoice.groups:
            buckets: dict[tuple[str, str], tuple[Decimal, Decimal]] = {}
            for sample in invoice.samples:
                coefficient = (1 if sample.source_id in group.add_sources else 0) - (
                    1 if sample.source_id in group.subtract_sources else 0
                )
                if coefficient == 0:
                    continue
                rate = self._find_rate(invoice.energy_rates, group.group_id, sample)
                key = (rate.rate_id, sample.tariff_period)
                quantity, amount = buckets.get(key, (Decimal(), Decimal()))
                signed_kwh = sample.kwh * coefficient
                buckets[key] = (quantity + signed_kwh, amount + signed_kwh * rate.eur_per_kwh)
                if not sample.complete:
                    incomplete_sources.add(sample.source_id)

            group_total = sum((quantity for quantity, _ in buckets.values()), Decimal())
            if group_total < 0:
                raise ConfigurationError(
                    f"Group {group.group_id} has physically impossible negative energy"
                )
            total_kwh += group_total
            for (rate_id, tariff_period), (quantity, amount) in sorted(buckets.items()):
                if quantity == 0:
                    continue
                unit_price = amount / quantity
                lines.append(
                    InvoiceLine(
                        code=f"energy:{group.group_id}:{rate_id}:{tariff_period}",
                        label=f"Energía — {group.name} ({tariff_period})",
                        category="energy",
                        amount=amount,
                        quantity=quantity,
                        unit_price=unit_price,
                        electricity_taxable=True,
                        metadata={
                            "group_id": group.group_id,
                            "rate_id": rate_id,
                            "tariff_period": tariff_period,
                        },
                    )
                )
        return lines, total_kwh, incomplete_sources

    @staticmethod
    def _find_rate(
        rates: tuple[EnergyRate, ...], group_id: str, sample: EnergySample
    ) -> EnergyRate:
        timestamp = sample.timestamp
        tariff_period = sample.tariff_period
        matches = [
            rate
            for rate in rates
            if rate.group_id == group_id
            and rate.valid_from <= timestamp
            and (rate.valid_to is None or timestamp < rate.valid_to)
            and (rate.tariff_period is None or rate.tariff_period == tariff_period)
        ]
        exact = [rate for rate in matches if rate.tariff_period == tariff_period]
        selected = exact or [rate for rate in matches if rate.tariff_period is None]
        if len(selected) != 1:
            raise IncompleteDataError(
                f"Expected one price for group {group_id}, period {tariff_period}, "
                f"timestamp {timestamp.isoformat()}; found {len(selected)}"
            )
        return selected[0]

    @staticmethod
    def _power_lines(invoice: InvoiceInput) -> list[InvoiceLine]:
        days = Decimal(invoice.period.days)
        return [
            InvoiceLine(
                code=f"power:{charge.code}",
                label=charge.label,
                category="power",
                amount=charge.contracted_kw * charge.eur_per_kw_day * days,
                quantity=charge.contracted_kw,
                unit_price=charge.eur_per_kw_day,
                electricity_taxable=True,
                metadata={"days": str(invoice.period.days)},
            )
            for charge in invoice.power_charges
        ]

    @staticmethod
    def _fixed_lines(invoice: InvoiceInput) -> list[InvoiceLine]:
        lines: list[InvoiceLine] = []
        for charge in invoice.fixed_charges:
            factor = (
                Decimal(invoice.period.days)
                if charge.frequency == BillingFrequency.DAILY
                else Decimal(1)
            )
            lines.append(
                InvoiceLine(
                    code=f"fixed:{charge.code}",
                    label=charge.label,
                    category="fixed",
                    amount=charge.amount * factor,
                    electricity_taxable=charge.electricity_taxable,
                    vat_taxable=charge.vat_taxable,
                    metadata={"frequency": charge.frequency},
                )
            )
        return lines

    @staticmethod
    def _discount_lines(invoice: InvoiceInput, lines: list[InvoiceLine]) -> list[InvoiceLine]:
        discount_lines: list[InvoiceLine] = []
        for discount in invoice.discounts:
            base = sum(
                (line.amount for line in lines if line.category in discount.categories), Decimal()
            )
            discount_lines.append(
                InvoiceLine(
                    code=f"discount:{discount.code}",
                    label=discount.label,
                    category="discount",
                    amount=-(base * discount.rate),
                    electricity_taxable=bool(discount.categories & {"energy", "power"}),
                    vat_taxable=True,
                    metadata={"rate": str(discount.rate)},
                )
            )
        return discount_lines
