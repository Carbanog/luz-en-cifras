"""One invoice across dated source expressions and tariff revisions."""

from copy import deepcopy
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from custom_components.luz_en_cifras.domain import BillingPeriod
from custom_components.luz_en_cifras.domain.billing import calculate_contract
from custom_components.luz_en_cifras.domain.errors import ConfigurationError, IncompleteDataError
from custom_components.luz_en_cifras.domain.ledger import MeasurementLedger

D = Decimal
ZONE = ZoneInfo("Europe/Madrid")
PERIOD = BillingPeriod(date(2026, 10, 1), date(2026, 11, 1))


def at(day: int, hour: int = 0) -> datetime:
    return datetime(2026, 10, day, hour, tzinfo=ZONE)


def config(source: str = "old") -> dict[str, Any]:
    return {
        "contract_id": "home",
        "power_p1_kw": "3",
        "power_p1_eur_per_kw_day": "0.1",
        "meter_rental_daily": "0.05",
        "daily_fee": "0.1",
        "invoice_fee": "2",
        "groups": [
            {
                "group_id": "g",
                "group_name": "Casa",
                "add_sources": [source],
                "subtract_sources": [],
                "eur_per_kwh": "0.1",
            }
        ],
    }


def test_replacing_meter_and_price_keeps_energy_with_one_set_of_fixed_costs() -> None:
    old, new = config(), config("new")
    new["groups"][0]["eur_per_kwh"] = "0.2"
    ledger = MeasurementLedger()
    ledger.price("g", D("0.1"), at(1))
    ledger.observe("old", D(0), at(1))
    ledger.observe("old", D(10), at(15))
    ledger.revision_boundaries.append(at(15))
    ledger.price("g", D("0.2"), at(15))
    ledger.observe("new", D(100), at(15))
    ledger.observe("new", D(120), at(20))
    revisions = [
        {"from": at(1).isoformat(), "config": old},
        {"from": at(15).isoformat(), "config": new},
    ]
    result = calculate_contract(new, ledger, PERIOD, date(2026, 10, 31), revisions=revisions)
    assert result.total_kwh == 30
    assert result.amount_for("energy") == 5
    assert result.amount_for("power") == D("9.3")
    assert result.amount_for("fixed") == D("6.65")
    assert result.amount_for("electricity_tax") == D("14.3") * D("0.0511269632")
    assert len([line for line in result.lines if line.category == "vat"]) == 1
    assert all(
        line.metadata["group_id"] == "g" for line in result.lines if line.category == "energy"
    )
    subset = calculate_contract(
        new,
        ledger,
        BillingPeriod(date(2026, 10, 15), date(2026, 10, 21)),
        date(2026, 10, 31),
        revisions=revisions,
    )
    assert subset.total_kwh == 20
    assert subset.amount_for("fixed") == D("2.9")


def test_pending_new_meter_preserves_known_old_amount_with_explicit_warning() -> None:
    old, new = config(), config("new")
    ledger = MeasurementLedger()
    ledger.price("g", D("0.1"), at(1))
    ledger.observe("old", D(0), at(1))
    ledger.observe("old", D(10), at(15))
    result = calculate_contract(
        new,
        ledger,
        PERIOD,
        date(2026, 10, 31),
        revisions=[
            {"from": at(1).isoformat(), "config": old},
            {"from": at(15).isoformat(), "config": new},
        ],
    )
    assert result.total_kwh == 10
    assert result.amount_for("energy") == 1
    assert result.quality == "partial"
    assert any("esperando mediciones" in warning for warning in result.warnings)


def test_measured_zero_retains_an_energy_line_instead_of_looking_unmeasured() -> None:
    ledger = MeasurementLedger()
    ledger.price("g", D("0.1"), at(1))
    ledger.observe("old", D(100), at(1))
    ledger.observe("old", D(100), at(2))
    result = calculate_contract(config(), ledger, PERIOD, date(2026, 10, 31))
    assert result.total_kwh == 0
    lines = [line for line in result.lines if line.category == "energy"]
    assert len(lines) == 1
    assert lines[0].quantity == 0
    assert lines[0].metadata["group_id"] == "g"


def test_compaction_never_merges_across_a_persisted_configuration_boundary() -> None:
    ledger = MeasurementLedger()
    ledger.observe("meter", D(0), at(1))
    ledger.observe("meter", D(1), at(1).replace(minute=10))
    ledger.revision_boundaries.append(at(1).replace(minute=10))
    restored = MeasurementLedger.restore(ledger.serialize())
    restored.observe("meter", D(2), at(1).replace(minute=20))
    assert len(restored.intervals) == 2
    assert sum((interval.kwh for interval in restored.intervals), D()) == 2


def test_renaming_or_daily_fee_edit_does_not_need_an_estimated_energy_split() -> None:
    old, new = config(), config()
    new["groups"][0]["group_name"] = "Vivienda"
    new["meter_rental_daily"] = "0.1"
    ledger = MeasurementLedger()
    ledger.price("g", D("0.1"), at(1))
    ledger.observe("old", D(0), at(1))
    ledger.observe("old", D(20), at(21))
    result = calculate_contract(
        new,
        ledger,
        PERIOD,
        date(2026, 10, 31),
        revisions=[
            {"from": at(1).isoformat(), "config": old},
            {"from": at(11).isoformat(), "config": new},
        ],
    )
    assert result.total_kwh == 20
    assert result.amount_for("energy") == 2
    assert result.amount_for("fixed") == D("7.7")  # Rental .5+2.1, daily3.1, invoice2.


def test_ambiguous_delta_at_source_change_requires_explicit_estimation() -> None:
    old, new = config(), config("new")
    ledger = MeasurementLedger()
    ledger.price("g", D("0.1"), at(1))
    ledger.observe("old", D(0), at(1))
    ledger.observe("old", D(20), at(21))
    ledger.observe("new", D(0), at(11))
    ledger.observe("new", D(10), at(21))
    revisions = [
        {"from": at(1).isoformat(), "config": old},
        {"from": at(11).isoformat(), "config": new},
    ]
    with pytest.raises(IncompleteDataError, match="configuration boundary"):
        calculate_contract(new, ledger, PERIOD, date(2026, 10, 31), revisions=revisions)
    accepted: list[dict[str, Any]] = deepcopy(revisions)
    for revision in accepted:
        revision["config"]["approximate_intervals"] = True
    result = calculate_contract(
        {**new, "approximate_intervals": True},
        ledger,
        PERIOD,
        date(2026, 10, 31),
        revisions=accepted,
    )
    assert result.total_kwh == 20
    assert result.quality == "partial"


def test_revisions_cannot_be_applied_out_of_order() -> None:
    with pytest.raises(ConfigurationError, match="chronological"):
        calculate_contract(
            config(),
            MeasurementLedger(),
            PERIOD,
            date(2026, 10, 31),
            revisions=[
                {"from": at(15).isoformat(), "config": config()},
                {"from": at(1).isoformat(), "config": config()},
            ],
        )


def test_export_meter_and_price_changes_and_later_disable_preserve_previous_credit() -> None:
    old, new = config("import"), config("import")
    old.update(enable_surplus=True, export_source="old_export")
    new.update(enable_surplus=True, export_source="new_export")
    disabled = {**new, "enable_surplus": False}
    ledger = MeasurementLedger()
    ledger.price("g", D("0.1"), at(1))
    ledger.price("__surplus", D("0.1"), at(1))
    ledger.observe("import", D(0), at(1))
    ledger.observe("old_export", D(0), at(1))
    ledger.observe("import", D(50), at(15))
    ledger.observe("old_export", D(10), at(15))
    ledger.price("__surplus", D("0.2"), at(15))
    ledger.observe("new_export", D(0), at(15))
    ledger.observe("import", D(100), at(20))
    ledger.observe("new_export", D(20), at(20))
    ledger.price("__surplus", None, at(20))
    ledger.observe("import", D(110), at(30))
    result = calculate_contract(
        disabled,
        ledger,
        PERIOD,
        date(2026, 10, 31),
        revisions=[
            {"from": at(1).isoformat(), "config": old},
            {"from": at(15).isoformat(), "config": new},
            {"from": at(20).isoformat(), "config": disabled},
        ],
    )
    assert result.total_kwh == 110
    assert result.amount_for("energy") == 11
    assert result.amount_for("compensation") == -5


def test_removed_group_keeps_past_energy_but_does_not_bill_later_readings() -> None:
    old = config("house")
    old["groups"].append({"group_id": "car", "group_name": "Coche", "add_sources": ["car"]})
    new = config("house")
    ledger = MeasurementLedger()
    ledger.price("g", D("0.1"), at(1))
    ledger.price("car", D("0.1"), at(1))
    for source in ("house", "car"):
        ledger.observe(source, D(0), at(1))
    ledger.observe("house", D(10), at(15))
    ledger.observe("car", D(5), at(15))
    ledger.observe("house", D(20), at(20))
    ledger.observe("car", D(15), at(20))
    result = calculate_contract(
        new,
        ledger,
        PERIOD,
        date(2026, 10, 31),
        revisions=[
            {"from": at(1).isoformat(), "config": old},
            {"from": at(15).isoformat(), "config": new},
        ],
    )
    assert result.total_kwh == 25
    assert result.amount_for("energy") == D("2.5")
