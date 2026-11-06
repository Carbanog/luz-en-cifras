"""Billing continuity, counter coverage and legal calendar regressions."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from custom_components.luz_en_cifras.domain import BillingPeriod, ConsumptionGroup
from custom_components.luz_en_cifras.domain.billing import calculate_contract
from custom_components.luz_en_cifras.domain.errors import ConfigurationError, IncompleteDataError
from custom_components.luz_en_cifras.domain.intervals import MeasuredInterval, allocate_interval
from custom_components.luz_en_cifras.domain.ledger import MeasurementLedger
from custom_components.luz_en_cifras.domain.models import EnergyRate
from custom_components.luz_en_cifras.domain.prices import PriceIndex
from custom_components.luz_en_cifras.domain.tariffs import period_20td, three_period_rates

D = Decimal
ZONE = ZoneInfo("Europe/Madrid")
START = datetime(2026, 10, 31, 23, 58, tzinfo=ZONE)


def contract() -> dict[str, Any]:
    return {
        "contract_id": "fixture",
        "fiscal_mode": "contract",
        "tax_electricity_percent": "5.11269632",
        "tax_indirect_percent": "21",
        "tax_minimum_eur_mwh": "1",
        "tax_rules_confirmed": True,
        "groups": [
            {
                "group_id": "g",
                "group_name": "Fixture",
                "add_sources": ["meter"],
                "subtract_sources": [],
                "eur_per_kwh": "0.2",
            }
        ],
    }


def test_next_cycle_preserves_unread_counter_delta_and_storage_roundtrip() -> None:
    ledger = MeasurementLedger()
    ledger.observe("meter", D(100), START)
    ledger.observe("meter", D(101), START + timedelta(minutes=1))
    boundary = START + timedelta(minutes=2)
    following = MeasurementLedger.restore(ledger.next_cycle(boundary).serialize())
    assert not following.warnings
    following.observe("meter", D(103), boundary + timedelta(minutes=1))
    following.observe("meter", D(104), boundary + timedelta(minutes=2))
    assert sum((item.kwh for item in ledger.intervals + following.intervals), D()) == 4
    assert following.intervals[0].start < boundary < following.intervals[0].end
    result = calculate_contract(
        contract(),
        following,
        BillingPeriod(date(2026, 11, 1), date(2026, 11, 2)),
        date(2026, 11, 1),
    )
    assert result.total_kwh == 1
    assert any(
        "2 kWh" in warning and "pendiente de reparto" in warning for warning in result.warnings
    )


def test_consented_cycle_split_conserves_energy_on_both_sides() -> None:
    ledger = MeasurementLedger()
    ledger.observe("meter", D(100), START)
    ledger.observe("meter", D(104), START + timedelta(minutes=4))
    cfg = contract()
    cfg["approximate_intervals"] = True
    old = calculate_contract(
        cfg, ledger, BillingPeriod(date(2026, 10, 1), date(2026, 11, 1)), date(2026, 10, 31)
    )
    new = calculate_contract(
        cfg, ledger, BillingPeriod(date(2026, 11, 1), date(2026, 11, 2)), date(2026, 11, 1)
    )
    assert old.total_kwh == new.total_kwh == 2
    assert old.total_kwh + new.total_kwh == 4


def test_residual_waits_for_common_coverage_without_blocking_independent_group() -> None:
    ledger = MeasurementLedger()
    start = START.astimezone(UTC) - timedelta(hours=1)
    for source, values in (("main", (100, 102)), ("ev", (50, 51))):
        ledger.observe(source, D(values[0]), start)
        ledger.observe(source, D(values[1]), start + timedelta(hours=1))
    ledger.observe("ev", D(54), start + timedelta(hours=1, minutes=1))
    ledger.price("house", D("0.2"), start)
    ledger.price("car", D("0.1"), start)
    groups = (
        ConsumptionGroup("house", "House", ("main",), ("ev",)),
        ConsumptionGroup("car", "Car", ("ev",)),
    )
    _, samples, _ = ledger.billing_data(groups)
    assert sum(item.kwh for item in samples if item.source_id == "house|ev") == 1
    assert sum(item.kwh for item in samples if item.source_id == "car|ev") == 4
    assert any("cobertura común" in warning for warning in ledger.warnings)


def test_verified_2027_fixed_holidays_are_valley() -> None:
    for month, day in [
        (1, 1),
        (1, 6),
        (5, 1),
        (8, 15),
        (10, 12),
        (11, 1),
        (12, 6),
        (12, 8),
        (12, 25),
    ]:
        assert period_20td(datetime(2027, month, day, 12, tzinfo=ZONE)) == "P3"


def test_2027_movable_holiday_and_regional_transfer_are_not_national_valley() -> None:
    assert period_20td(datetime(2027, 3, 26, 12, tzinfo=ZONE)) == "P1"
    assert period_20td(datetime(2027, 8, 16, 12, tzinfo=ZONE)) == "P1"
    with pytest.raises(ConfigurationError):
        period_20td(datetime(2028, 1, 1, tzinfo=ZONE))


def test_three_period_invoice_lines_preserve_labels_and_prices() -> None:
    cfg = contract()
    cfg["groups"][0].update(
        tariff_mode="three_period", p1_price="0.3", p2_price="0.2", p3_price="0.1"
    )
    ledger = MeasurementLedger()
    for hour in (2, 8, 10):
        start = datetime(2027, 1, 7, hour, tzinfo=ZONE)
        ledger.intervals.append(MeasuredInterval("meter", start, start + timedelta(hours=1), D(1)))
    result = calculate_contract(
        cfg, ledger, BillingPeriod(date(2027, 1, 7), date(2027, 1, 8)), date(2027, 1, 7)
    )
    assert result.amount_for("energy") == D("0.6")
    assert {
        line.metadata["tariff_period"] for line in result.lines if line.category == "energy"
    } == {"P1", "P2", "P3"}


def test_price_index_preserves_older_overlap_instead_of_accepting_latest_quote() -> None:
    rates = (
        EnergyRate("older", "g", D("0.1"), START),
        EnergyRate("newer", "g", D("0.2"), START + timedelta(minutes=1)),
    )
    start = START + timedelta(minutes=2)
    end = start + timedelta(minutes=1)
    selected = PriceIndex(rates).window("g", start, end)
    with pytest.raises(IncompleteDataError):
        allocate_interval(MeasuredInterval("meter", start, end, D(1)), selected, "g")


def test_2027_dst_days_have_23_and_25_distinct_prices() -> None:
    for month, day, hours in ((3, 28, 23), (10, 31, 25)):
        start = datetime(2027, month, day, tzinfo=ZONE)
        rates = three_period_rates(
            "g", start, start + timedelta(days=1), {"P1": D(1), "P2": D(2), "P3": D(3)}
        )
        assert len(rates) == len({item.rate_id for item in rates}) == hours


def test_comparable_negative_submeter_residual_still_rejects_bad_topology() -> None:
    cfg = contract()
    cfg["groups"][0]["subtract_sources"] = ["ev"]
    ledger = MeasurementLedger()
    for source, delta in (("meter", 1), ("ev", 2)):
        ledger.observe(source, D(100), START)
        ledger.observe(source, D(100 + delta), START + timedelta(minutes=1))
    with pytest.raises(ConfigurationError, match="negative energy"):
        calculate_contract(
            cfg, ledger, BillingPeriod(date(2026, 10, 1), date(2026, 11, 1)), date(2026, 10, 31)
        )


def test_unaligned_unsplittable_tails_do_not_leave_different_residual_horizons() -> None:
    ledger = MeasurementLedger()
    for source, begin, end, quantity in (
        ("main", 0, 1, 2),
        ("main", 1, 3, 1),
        ("ev", 0, 1, 1),
        ("ev", 1, 2, 10),
    ):
        ledger.intervals.append(
            MeasuredInterval(
                source, START + timedelta(hours=begin), START + timedelta(hours=end), D(quantity)
            )
        )
    ledger.price("g", D("0.2"), START)
    _, samples, _ = ledger.billing_data((ConsumptionGroup("g", "Residual", ("main",), ("ev",)),))
    assert sum(item.kwh for item in samples if item.source_id == "g|main") == 2
    assert sum(item.kwh for item in samples if item.source_id == "g|ev") == 1


def test_common_coverage_excludes_internal_submeter_gaps() -> None:
    ledger = MeasurementLedger()
    for source, begin, end, quantity in (
        ("main", 0, 3, 6),
        ("ev", 0, 1, 1),
        ("ev", 2, 3, 1),
    ):
        ledger.intervals.append(
            MeasuredInterval(
                source,
                START + timedelta(hours=begin),
                START + timedelta(hours=end),
                D(quantity),
                estimated=True,
            )
        )
    ledger.price("g", D("0.2"), START)
    _, samples, _ = ledger.billing_data((ConsumptionGroup("g", "Residual", ("main",), ("ev",)),))
    assert sum(item.kwh for item in samples if item.source_id == "g|main") == 4
    assert sum(item.kwh for item in samples if item.source_id == "g|ev") == 2
