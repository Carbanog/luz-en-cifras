from __future__ import annotations

import unittest
from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from custom_components.luz_en_cifras.domain import (
    SPAIN_MAINLAND_2026,
    BillingEngine,
    BillingFrequency,
    BillingPeriod,
    ConfigurationError,
    ConsumptionGroup,
    DataQuality,
    EnergyRate,
    EnergySample,
    FiscalRule,
    FixedCharge,
    IncompleteDataError,
    InvoiceInput,
    PercentageDiscount,
    PowerCharge,
    find_fiscal_rule,
)

MADRID = ZoneInfo("Europe/Madrid")
D = Decimal


def at(day: int, hour: int = 0, month: int = 10) -> datetime:
    return datetime(2026, month, day, hour, tzinfo=MADRID)


def base_invoice(**overrides: object) -> InvoiceInput:
    values: dict[str, object] = {
        "contract_id": "home",
        "period": BillingPeriod(date(2026, 10, 1), date(2026, 11, 1)),
        "tax_point": date(2026, 10, 31),
        "samples": (EnergySample("meter", at(1), D("100")),),
        "groups": (ConsumptionGroup("home", "Vivienda", ("meter",)),),
        "energy_rates": (EnergyRate("fixed", "home", D("0.20"), at(1)),),
        "fiscal_rule": find_fiscal_rule(date(2026, 10, 31), SPAIN_MAINLAND_2026),
    }
    values.update(overrides)
    return InvoiceInput(**values)  # type: ignore[arg-type]


class BillingEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = BillingEngine()

    def test_fixed_price_invoice_uses_decimal_and_expected_taxes(self) -> None:
        result = self.engine.calculate(base_invoice())
        self.assertEqual(result.amount_for("energy"), D("20.00"))
        self.assertEqual(result.amount_for("electricity_tax"), D("1.022539264000"))
        self.assertEqual(result.total, D("25.44"))
        self.assertEqual(result.quality, DataQuality.COMPLETE)

    def test_three_period_rates(self) -> None:
        samples = (
            EnergySample("meter", at(1, 8), D("10"), "peak"),
            EnergySample("meter", at(1, 15), D("20"), "flat"),
            EnergySample("meter", at(1, 2), D("30"), "valley"),
        )
        rates = tuple(
            EnergyRate(code, "home", price, at(1), tariff_period=period)
            for code, period, price in (
                ("p1", "peak", D("0.30")),
                ("p2", "flat", D("0.20")),
                ("p3", "valley", D("0.10")),
            )
        )
        result = self.engine.calculate(base_invoice(samples=samples, energy_rates=rates))
        self.assertEqual(result.amount_for("energy"), D("10.00"))
        self.assertEqual(len([line for line in result.lines if line.category == "energy"]), 3)

    def test_vehicle_submeter_is_not_double_counted(self) -> None:
        samples = (
            EnergySample("main", at(1), D("100")),
            EnergySample("ev", at(1), D("25")),
        )
        groups = (
            ConsumptionGroup("home", "Vivienda", ("main",), ("ev",)),
            ConsumptionGroup("ev", "Vehículo eléctrico", ("ev",)),
        )
        rates = (
            EnergyRate("home", "home", D("0.20"), at(1)),
            EnergyRate("ev", "ev", D("0.08"), at(1)),
        )
        result = self.engine.calculate(
            base_invoice(samples=samples, groups=groups, energy_rates=rates)
        )
        self.assertEqual(result.total_kwh, D("100.000"))
        self.assertEqual(result.amount_for("energy"), D("17.00"))

    def test_independent_meters_are_summed(self) -> None:
        samples = (
            EnergySample("row1", at(1), D("45")),
            EnergySample("row2", at(1), D("55")),
        )
        groups = (ConsumptionGroup("home", "Vivienda", ("row1", "row2")),)
        result = self.engine.calculate(base_invoice(samples=samples, groups=groups))
        self.assertEqual(result.total_kwh, D("100.000"))

    def test_duplicate_billing_source_is_rejected(self) -> None:
        groups = (
            ConsumptionGroup("a", "A", ("meter",)),
            ConsumptionGroup("b", "B", ("meter",)),
        )
        rates = (
            EnergyRate("a", "a", D("0.10"), at(1)),
            EnergyRate("b", "b", D("0.10"), at(1)),
        )
        with self.assertRaisesRegex(ConfigurationError, "double counting"):
            self.engine.calculate(base_invoice(groups=groups, energy_rates=rates))

    def test_negative_residual_is_rejected(self) -> None:
        samples = (
            EnergySample("main", at(1), D("10")),
            EnergySample("child", at(1), D("11")),
        )
        groups = (ConsumptionGroup("home", "Vivienda", ("main",), ("child",)),)
        with self.assertRaisesRegex(ConfigurationError, "negative energy"):
            self.engine.calculate(base_invoice(samples=samples, groups=groups))

    def test_missing_measurement_is_not_silently_zero(self) -> None:
        groups = (ConsumptionGroup("home", "Vivienda", ("meter", "missing")),)
        with self.assertRaisesRegex(IncompleteDataError, "missing"):
            self.engine.calculate(base_invoice(groups=groups))

    def test_missing_price_is_not_silently_zero(self) -> None:
        with self.assertRaisesRegex(IncompleteDataError, "Expected one price"):
            self.engine.calculate(base_invoice(energy_rates=()))

    def test_ambiguous_prices_are_rejected(self) -> None:
        rates = (
            EnergyRate("one", "home", D("0.10"), at(1)),
            EnergyRate("two", "home", D("0.20"), at(1)),
        )
        with self.assertRaisesRegex(IncompleteDataError, "found 2"):
            self.engine.calculate(base_invoice(energy_rates=rates))

    def test_price_change_uses_interval_timestamp(self) -> None:
        samples = (
            EnergySample("meter", at(5), D("10")),
            EnergySample("meter", at(20), D("10")),
        )
        rates = (
            EnergyRate("old", "home", D("0.10"), at(1), valid_to=at(15)),
            EnergyRate("new", "home", D("0.30"), at(15)),
        )
        result = self.engine.calculate(base_invoice(samples=samples, energy_rates=rates))
        self.assertEqual(result.amount_for("energy"), D("4.00"))

    def test_negative_energy_price_is_supported(self) -> None:
        rates = (EnergyRate("negative", "home", D("-0.05"), at(1)),)
        result = self.engine.calculate(base_invoice(energy_rates=rates))
        self.assertEqual(result.amount_for("energy"), D("-5.00"))
        self.assertEqual(result.amount_for("electricity_tax"), D("0.10"))

    def test_power_uses_exact_calendar_days(self) -> None:
        charges = (PowerCharge("p1", "Potencia P1", D("4.6"), D("0.10")),)
        result = self.engine.calculate(base_invoice(power_charges=charges))
        self.assertEqual(result.amount_for("power"), D("14.26"))

    def test_daily_and_invoice_fixed_charges(self) -> None:
        charges = (
            FixedCharge("meter", "Alquiler", D("0.03"), BillingFrequency.DAILY),
            FixedCharge("service", "Servicio", D("2.00")),
        )
        result = self.engine.calculate(base_invoice(fixed_charges=charges))
        self.assertEqual(result.amount_for("fixed"), D("2.93"))

    def test_discount_reduces_taxable_energy_base(self) -> None:
        discounts = (PercentageDiscount("promo", "Promoción", D("0.10")),)
        result = self.engine.calculate(base_invoice(discounts=discounts))
        self.assertEqual(result.amount_for("discount"), D("-2.00"))
        self.assertEqual(result.amount_for("electricity_tax"), D("0.920285337600"))

    def test_incomplete_sample_produces_partial_not_fake_zero(self) -> None:
        samples = (EnergySample("meter", at(1), D("100"), complete=False),)
        result = self.engine.calculate(base_invoice(samples=samples))
        self.assertEqual(result.quality, DataQuality.PARTIAL)
        self.assertIn("meter", result.warnings[0])

    def test_irregular_period_prorates_power_by_exact_days(self) -> None:
        period = BillingPeriod(date(2026, 10, 10), date(2026, 10, 25))
        samples = (EnergySample("meter", at(10), D("1")),)
        charges = (PowerCharge("p1", "Potencia P1", D("2"), D("0.10")),)
        result = self.engine.calculate(
            base_invoice(period=period, samples=samples, power_charges=charges)
        )
        self.assertEqual(result.amount_for("power"), D("3.00"))

    def test_sample_at_exclusive_period_end_is_rejected(self) -> None:
        samples = (EnergySample("meter", at(1, month=11), D("1")),)
        with self.assertRaisesRegex(ConfigurationError, "outside"):
            self.engine.calculate(base_invoice(samples=samples))

    def test_tax_point_before_period_is_rejected(self) -> None:
        with self.assertRaisesRegex(ConfigurationError, "Tax point"):
            self.engine.calculate(base_invoice(tax_point=date(2026, 9, 30)))

    def test_naive_energy_timestamp_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            EnergySample("meter", datetime(2026, 10, 1), D("1"))

    def test_electricity_tax_minimum_applies(self) -> None:
        fiscal = FiscalRule(
            "minimum-test",
            date(2026, 1, 1),
            None,
            D("0"),
            D("0"),
            D("1"),
            ("https://example.invalid/test-rule",),
        )
        result = self.engine.calculate(base_invoice(fiscal_rule=fiscal))
        self.assertEqual(result.amount_for("electricity_tax"), D("0.1"))

    def test_invoice_charge_is_not_prorated(self) -> None:
        charges = (FixedCharge("service", "Servicio", D("2.75")),)
        result = self.engine.calculate(base_invoice(fixed_charges=charges))
        self.assertEqual(result.amount_for("fixed"), D("2.75"))

    def test_dst_start_period_still_has_31_calendar_days(self) -> None:
        period = BillingPeriod(date(2026, 3, 1), date(2026, 4, 1))
        self.assertEqual(period.days, 31)

    def test_dst_end_period_still_has_31_calendar_days(self) -> None:
        period = BillingPeriod(date(2026, 10, 1), date(2026, 11, 1))
        self.assertEqual(period.days, 31)


class FiscalRegistryTests(unittest.TestCase):
    def test_known_2026_boundaries(self) -> None:
        before = find_fiscal_rule(date(2026, 3, 21), SPAIN_MAINLAND_2026)
        relief = find_fiscal_rule(date(2026, 3, 22), SPAIN_MAINLAND_2026)
        june = find_fiscal_rule(date(2026, 6, 1), SPAIN_MAINLAND_2026)
        self.assertEqual(before.vat_rate, D("0.21"))
        self.assertEqual(relief.vat_rate, D("0.10"))
        self.assertEqual(june.vat_rate, D("0.21"))

    def test_unknown_conditional_future_period_fails_closed(self) -> None:
        with self.assertRaises(IncompleteDataError):
            find_fiscal_rule(date(2026, 11, 1), SPAIN_MAINLAND_2026)

    def test_overlapping_rules_fail_closed(self) -> None:
        first = SPAIN_MAINLAND_2026[0]
        overlapping = FiscalRule(
            "overlap",
            date(2026, 1, 1),
            date(2026, 2, 1),
            D("0.01"),
            D("0.21"),
            D("1"),
            ("https://example.invalid/overlap",),
        )
        with self.assertRaisesRegex(IncompleteDataError, "Overlapping"):
            find_fiscal_rule(date(2026, 1, 15), (first, overlapping))


if __name__ == "__main__":
    unittest.main()
