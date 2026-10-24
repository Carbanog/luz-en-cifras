"""Power/energy auto-detection, integration, gaps and persisted compatibility."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from custom_components.luz_en_cifras.domain import ConsumptionGroup, DataQuality
from custom_components.luz_en_cifras.domain.billing import calculate_contract
from custom_components.luz_en_cifras.domain.ledger import MeasurementLedger
from tests.test_engine import base_invoice

D = Decimal
START = datetime(2026, 10, 23, 12, tzinfo=UTC)


def total(ledger: MeasurementLedger) -> Decimal:
    return sum((interval.kwh for interval in ledger.intervals), D())


def test_month_of_minute_reports_preserves_energy_with_bounded_storage() -> None:
    ledger = MeasurementLedger()
    ledger.price("g", D("0.2"), START)
    for minute in range(31 * 24 * 60 + 1):
        ledger.observe_input("p", D(1), "kW", START + timedelta(minutes=minute))
    assert abs(total(ledger) - D(744)) < D("1e-20")
    assert len(ledger.intervals) <= 2 * 744 + 1
    assert ledger.serialize() == MeasurementLedger.restore(ledger.serialize()).serialize()


def test_repeated_autumn_hour_integrates_real_elapsed_time() -> None:
    zone = ZoneInfo("Europe/Madrid")
    start = datetime(2026, 10, 25, 2, 0, tzinfo=zone, fold=0)
    end = datetime(2026, 10, 25, 2, 0, tzinfo=zone, fold=1)
    ledger = MeasurementLedger()
    ledger.observe_input("p", D(1), "kW", start)
    ledger.advance_power("p", end, max_age_seconds=7200)
    assert total(ledger) == 1


def test_power_units_and_constant_updates() -> None:
    for unit, value in [("W", "1000"), ("kW", "1")]:
        ledger = MeasurementLedger()
        ledger.observe_input("p", D(value), unit, START)
        ledger.observe_input("p", D(value), unit, START + timedelta(minutes=1), reported_at=START)
        ledger.observe_input("p", D(0), unit, START + timedelta(minutes=2))
        assert abs(total(ledger) - D(1) / 30) < D("1e-24")
        assert all(item.estimated for item in ledger.intervals)
        assert ledger.serialize() == MeasurementLedger.restore(ledger.serialize()).serialize()


def test_energy_units() -> None:
    for unit, initial, final in [("Wh", "1000", "2000"), ("kWh", "1", "2")]:
        ledger = MeasurementLedger()
        ledger.observe_input("e", D(initial), unit, START)
        ledger.observe_input("e", D(final), unit, START + timedelta(minutes=1))
        assert total(ledger) == 1
        assert not ledger.intervals[0].estimated


def test_invalid_power_breaks_continuity() -> None:
    for value, unit in [(None, "W"), (D("NaN"), "W"), (D(-1), "W"), (D(1), "V")]:
        ledger = MeasurementLedger()
        ledger.observe_input("p", D(1000), "W", START)
        ledger.observe_input("p", value, unit, START + timedelta(minutes=1))
        ledger.observe_input("p", D(1000), "W", START + timedelta(hours=1))
        ledger.advance_power("p", START + timedelta(hours=1, minutes=1))
        assert abs(total(ledger) - D(1) / 30) < D("1e-24")
        assert ledger.warnings


def test_stale_power_is_capped_and_ticks_do_not_refresh_it() -> None:
    ledger = MeasurementLedger()
    ledger.observe_input("p", D(1000), "W", START)
    for minute in (1, 2, 10, 11):
        ledger.observe_input(
            "p", D(1000), "W", START + timedelta(minutes=minute), reported_at=START
        )
    assert abs(total(ledger) - D(5) / 60) < D("1e-24")
    assert any("caducada" in warning for warning in ledger.warnings)


def test_input_kind_changes_do_not_treat_power_as_absolute_energy() -> None:
    ledger = MeasurementLedger()
    ledger.observe_input("s", D(100), "kWh", START)
    ledger.observe_input("s", D(1), "kW", START + timedelta(minutes=1))
    ledger.observe_input("s", D(500), "kWh", START + timedelta(minutes=2))
    ledger.observe_input("s", D(501), "kWh", START + timedelta(minutes=3))
    assert total(ledger) == D(1) + D(1) / 60
    assert any("tipo de medición" in warning for warning in ledger.warnings)


def test_power_price_boundary_can_be_split_but_remains_estimated() -> None:
    ledger = MeasurementLedger()
    ledger.price("g", D("0.1"), START)
    ledger.price("g", D("0.3"), START + timedelta(minutes=1))
    ledger.observe_input("p", D(1000), "W", START)
    ledger.advance_power("p", START + timedelta(minutes=2))
    groups, samples, rates = ledger.billing_data((ConsumptionGroup("g", "Power", ("p",)),))
    from custom_components.luz_en_cifras.domain import BillingEngine

    result = BillingEngine().calculate(
        base_invoice(groups=groups, samples=samples, energy_rates=rates)
    )
    assert abs(result.amount_for("energy") - D("0.4") / 60) < D("1e-24")
    assert result.quality == DataQuality.PARTIAL


def test_house_rows_and_car_have_independent_prices_with_mixed_units() -> None:
    ledger = MeasurementLedger()
    config = {
        "contract_id": "house",
        "groups": [
            {
                "group_id": "house",
                "group_name": "Casa",
                "add_sources": ["row1", "row2"],
                "eur_per_kwh": "0.2",
            },
            {
                "group_id": "car",
                "group_name": "Coche",
                "add_sources": ["car"],
                "eur_per_kwh": "0.1",
            },
        ],
    }
    ledger.price("house", D("0.2"), START)
    ledger.price("car", D("0.1"), START)
    ledger.observe_input("row1", D(1000), "W", START)
    ledger.observe_input("row2", D(100), "kWh", START)
    ledger.observe_input("car", D(2), "kW", START)
    end = START + timedelta(hours=1)
    ledger.advance_power("row1", end, 3600)
    ledger.observe_input("row2", D(102), "kWh", end)
    ledger.advance_power("car", end, 3600)
    result = calculate_contract(config, ledger, base_invoice().period, base_invoice().tax_point)
    assert result.total_kwh == D(5)
    assert result.amount_for("energy") == D("0.8")
