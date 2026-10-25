"""Contract, calendar, history and measurement regression cases."""

import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from custom_components.luz_en_cifras.domain import (
    BillingEngine,
    BillingPeriod,
    ConsumptionGroup,
    PercentageDiscount,
    PowerCharge,
)
from custom_components.luz_en_cifras.domain.billing import calculate_contract
from custom_components.luz_en_cifras.domain.errors import ConfigurationError, IncompleteDataError
from custom_components.luz_en_cifras.domain.fiscal import configured_rule, household_rule
from custom_components.luz_en_cifras.domain.history import reconcile, snapshot
from custom_components.luz_en_cifras.domain.ledger import MeasurementLedger
from custom_components.luz_en_cifras.domain.tariffs import period_20td, three_period_rates
from tests.test_engine import base_invoice

D = Decimal
ZONE = ZoneInfo("Europe/Madrid")


def at(day: int, hour: int = 0) -> datetime:
    return datetime(2026, 10, day, hour, tzinfo=ZONE)


def test_calendar_boundaries_and_weekends() -> None:
    assert [period_20td(at(23, hour)) for hour in (7, 8, 10, 14, 18, 22)] == [
        "P3",
        "P2",
        "P1",
        "P2",
        "P1",
        "P2",
    ]
    assert period_20td(at(24, 12)) == "P3"
    assert period_20td(at(12, 12)) == "P3"
    assert period_20td(datetime(2026, 1, 6, 12, tzinfo=ZONE)) == "P3"


def test_power_discount_does_not_reduce_surplus_energy_cap() -> None:
    result = BillingEngine().calculate(
        base_invoice(
            power_charges=(PowerCharge("p1", "Potencia", D(1), D(1)),),
            discounts=(PercentageDiscount("power", "Potencia", D("0.5"), frozenset({"power"})),),
            surplus_credit=D(100),
        )
    )
    assert result.amount_for("energy") == D(20)
    assert result.amount_for("compensation") == D(-20)


def test_movable_easter_holiday_is_not_valley() -> None:
    assert period_20td(datetime(2026, 4, 3, 12, tzinfo=ZONE)) == "P1"


def test_calendar_does_not_assume_unknown_year() -> None:
    with pytest.raises(ConfigurationError):
        period_20td(datetime(2027, 1, 1, tzinfo=ZONE))


def test_autumn_day_has_25_hourly_rates() -> None:
    rates = three_period_rates("g", at(25), at(26), {"P1": D(1), "P2": D(2), "P3": D(3)})
    assert len(rates) == 25
    assert len({rate.rate_id for rate in rates}) == 25


def test_price_revisions_do_not_revalue_old_measurements() -> None:
    ledger = MeasurementLedger()
    ledger.price("g", D("0.10"), at(1))
    ledger.observe("meter", D(100), at(1))
    ledger.observe("meter", D(110), at(1, 1))
    ledger.price("g", D("0.30"), at(1, 1))
    ledger.observe("meter", D(120), at(1, 2))
    groups, samples, rates = ledger.billing_data((ConsumptionGroup("g", "Casa", ("meter",)),))
    result = BillingEngine().calculate(
        base_invoice(groups=groups, samples=samples, energy_rates=rates)
    )
    assert result.amount_for("energy") == D(4)
    restored = MeasurementLedger.restore(json.loads(json.dumps(ledger.serialize())))
    assert restored.serialize() == ledger.serialize()


def test_unavailable_price_creates_real_gap() -> None:
    ledger = MeasurementLedger()
    ledger.price("g", D("0.10"), at(1))
    ledger.price("g", None, at(1, 1))
    ledger.price("g", D("0.20"), at(1, 2))
    ledger.observe("meter", D(0), at(1))
    ledger.observe("meter", D(3), at(1, 3))
    with pytest.raises(IncompleteDataError):
        ledger.billing_data((ConsumptionGroup("g", "Casa", ("meter",)),), approximate=True)


def test_counter_correction_does_not_count_new_absolute_reading() -> None:
    ledger = MeasurementLedger()
    ledger.observe("meter", D(100), at(1))
    ledger.observe("meter", D(30), at(1, 1))
    ledger.observe("meter", D(31), at(1, 2))
    assert sum((interval.kwh for interval in ledger.intervals), D()) == D(1)
    assert any("corrección" in warning for warning in ledger.warnings)


def test_invoice_snapshot_and_real_comparison_are_auditable() -> None:
    result = BillingEngine().calculate(base_invoice())
    record = snapshot(result, {"price": "0.2"})
    updated = reconcile(record, D(30), D(105), at(23))
    assert updated["comparison"]["difference_eur"] == "4.56"
    assert updated["comparison"]["difference_kwh"] == "5.000"
    assert record["audit"] == []
    assert len(reconcile(updated, D(29), D(104), at(24))["audit"]) == 2
    json.dumps(updated)


def test_power_change_is_prorated_by_effective_dates() -> None:
    result = BillingEngine().calculate(
        base_invoice(
            power_charges=(
                PowerCharge("old", "Anterior", D(3), D("0.1"), valid_to=date(2026, 10, 16)),
                PowerCharge("new", "Nueva", D(4), D("0.1"), valid_from=date(2026, 10, 16)),
            )
        )
    )
    assert result.amount_for("power") == D("10.9")


def test_surplus_credit_cannot_offset_power_or_services() -> None:
    result = BillingEngine().calculate(
        base_invoice(
            surplus_credit=D(999),
            power_charges=(PowerCharge("p1", "P1", D(3), D("0.1")),),
        )
    )
    assert result.amount_for("compensation") == D(-20)
    assert result.amount_for("power") == D("9.3")


def test_contract_builder_annual_power_and_optional_discount() -> None:
    config: dict[str, Any] = {
        "contract_id": "home",
        "power_price_unit": "year",
        "power_p1_kw": "3",
        "power_p1_eur_per_kw_day": "36.5",
        "energy_discount_percent": "10",
        "groups": [{"group_id": "g", "group_name": "Casa", "add_sources": ["meter"]}],
    }
    ledger = MeasurementLedger()
    ledger.price("g", D("0.2"), at(1))
    ledger.observe("meter", D(0), at(1))
    ledger.observe("meter", D(10), at(1, 1))
    result = calculate_contract(
        config, ledger, BillingPeriod(date(2026, 10, 1), date(2026, 11, 1)), date(2026, 10, 31)
    )
    assert result.amount_for("power") == D("9.3")
    assert result.amount_for("discount") == D("-0.2")


def test_repeated_counter_updates_are_compacted_without_losing_energy() -> None:
    ledger = MeasurementLedger()
    ledger.price("g", D("0.1"), at(1))
    for minute in range(60):
        ledger.observe("meter", D(minute), at(1).replace(minute=minute))
    assert len(ledger.intervals) == 1
    assert ledger.intervals[0].kwh == D(59)


def test_compaction_preserves_price_change_boundaries() -> None:
    ledger = MeasurementLedger()
    ledger.price("g", D("0.1"), at(1))
    ledger.observe("meter", D(0), at(1))
    ledger.observe("meter", D(1), at(1).replace(minute=10))
    ledger.price("g", D("0.2"), at(1).replace(minute=10))
    ledger.observe("meter", D(2), at(1).replace(minute=20))
    assert len(ledger.intervals) == 2


def test_three_period_price_revision_preserves_previous_price() -> None:
    old: dict[str, Any] = {
        "contract_id": "home",
        "groups": [
            {
                "group_id": "g",
                "group_name": "Casa",
                "add_sources": ["meter"],
                "tariff_mode": "three_period",
                "p1_price": "0.1",
                "p2_price": "0.1",
                "p3_price": "0.1",
            }
        ],
    }
    new = {**old, "groups": [{**old["groups"][0], "p1_price": "0.3"}]}
    ledger = MeasurementLedger()
    ledger.observe("meter", D(0), at(23, 10))
    ledger.observe("meter", D(10), at(23, 11))
    ledger.observe("meter", D(20), at(23, 12))
    result = calculate_contract(
        new,
        ledger,
        BillingPeriod(date(2026, 10, 23), date(2026, 10, 24)),
        date(2026, 10, 23),
        revisions=[
            {"from": at(23, 10).isoformat(), "config": old},
            {"from": at(23, 11).isoformat(), "config": new},
        ],
    )
    assert result.amount_for("energy") == D(4)


def test_reduced_vat_requires_eligible_power() -> None:
    assert household_rule(date(2026, 4, 1), D(10)).vat_rate == D("0.1")
    assert household_rule(date(2026, 4, 1), D(11)).vat_rate == D("0.21")


def test_manual_fiscal_profile_requires_source_and_confirmation() -> None:
    config: dict[str, Any] = {
        "fiscal_mode": "manual",
        "tax_valid_from": "2026-11-01",
        "tax_valid_to": "2026-12-01",
        "tax_electricity_percent": "5",
        "tax_indirect_percent": "21",
        "tax_minimum_eur_mwh": "1",
        "tax_source": "https://www.boe.es/",
        "tax_rules_confirmed": False,
    }
    with pytest.raises(IncompleteDataError):
        configured_rule(config, date(2026, 11, 2))
    config["tax_rules_confirmed"] = True
    assert configured_rule(config, date(2026, 11, 2)).electricity_tax_rate == D("0.05")
    with pytest.raises(IncompleteDataError):
        configured_rule(config, date(2026, 12, 1))


def test_manual_contract_percentages_do_not_expire_at_a_month_boundary() -> None:
    config: dict[str, Any] = {
        "fiscal_mode": "contract",
        "tax_electricity_percent": "5.11269632",
        "tax_indirect_percent": "21",
        "tax_minimum_eur_mwh": "1",
        "tax_rules_confirmed": True,
    }
    for tax_point in (date(2026, 11, 1), date(2027, 1, 1), date(2030, 6, 15)):
        rule = configured_rule(config, tax_point)
        assert rule.electricity_tax_rate == D("0.0511269632")
        assert rule.vat_rate == D("0.21")
        assert rule.valid_to is None
        assert rule.source_urls == ("manual:contract",)
        assert rule.rule_id.startswith("manual-contract:")


def test_manual_contract_rejects_invalid_tax_values() -> None:
    config: dict[str, Any] = {
        "fiscal_mode": "contract",
        "tax_electricity_percent": "5",
        "tax_indirect_percent": "21",
        "tax_minimum_eur_mwh": "1",
        "tax_rules_confirmed": True,
    }
    for field, value in (
        ("tax_electricity_percent", "-1"),
        ("tax_electricity_percent", "101"),
        ("tax_indirect_percent", "NaN"),
        ("tax_indirect_percent", "Infinity"),
        ("tax_minimum_eur_mwh", "-1"),
    ):
        with pytest.raises(ValueError):
            configured_rule({**config, field: value}, date(2027, 1, 1))


def test_manual_contract_requires_explicit_confirmation() -> None:
    with pytest.raises(IncompleteDataError, match="confirm"):
        configured_rule({"fiscal_mode": "contract"}, date(2026, 10, 25))
