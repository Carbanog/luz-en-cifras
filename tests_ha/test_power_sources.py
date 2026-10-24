"""Real HA state/timer tests for direct power sources and mixed groups."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.luz_en_cifras.const import DOMAIN
from custom_components.luz_en_cifras.coordinator import LuzEnCifrasCoordinator


@pytest.mark.parametrize("dynamic", [False, True])
async def test_startup_clock_advances_without_creating_a_price_gap(
    hass, contract, freezer, monkeypatch, dynamic
):
    """Frozen-clock tests must also cover real startup microsecond ordering."""
    freezer.move_to("2026-10-24 12:00:00+00:00")
    contract["groups"][0]["add_sources"] = ["sensor.row1", "sensor.row2"]
    contract["groups"].append(
        {
            "group_id": "car",
            "group_name": "Coche",
            "add_sources": ["sensor.car"],
            "eur_per_kwh": "0.1",
        }
    )
    for source, watts in (("sensor.row1", "600"), ("sensor.row2", "400"), ("sensor.car", "200")):
        hass.states.async_set(source, watts, {"unit_of_measurement": "W"})
    if dynamic:
        hass.states.async_set("sensor.quote", "0.2", {"unit_of_measurement": "€/kWh"})
        contract["groups"][0].update(tariff_mode="entity", price_entity="sensor.quote")
    original_now = dt_util.now

    def advancing_now(*args, **kwargs):
        freezer.tick(timedelta(microseconds=20))
        return original_now(*args, **kwargs)

    monkeypatch.setattr(dt_util, "now", advancing_now)
    entry = MockConfigEntry(domain=DOMAIN, data=contract, title="Casa", version=1)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    freezer.tick(timedelta(minutes=1))
    entry.runtime_data._tick(dt_util.now())
    assert entry.runtime_data.data.error is None
    assert entry.runtime_data.data.result.total_kwh > 0
    assert {
        line.metadata["group_id"]
        for line in entry.runtime_data.data.result.lines
        if line.category == "energy"
    } == {"home", "car"}
    assert min(rate.valid_from for rate in entry.runtime_data.ledger.rates) <= min(
        interval.start for interval in entry.runtime_data.ledger.intervals
    )


def test_invoice_cycles_monthly_bimonthly_and_short_month_boundaries():
    cycle = LuzEnCifrasCoordinator._current_period
    for today, day, months, anchor, start, end in (
        (date(2026, 10, 24), 23, 1, 1, date(2026, 10, 23), date(2026, 11, 23)),
        (date(2026, 10, 24), 23, 2, 1, date(2026, 9, 23), date(2026, 11, 23)),
        (date(2026, 1, 20), 23, 2, 1, date(2025, 11, 23), date(2026, 1, 23)),
        (date(2026, 2, 28), 31, 1, 1, date(2026, 2, 28), date(2026, 3, 31)),
    ):
        result = cycle(today, day, months, anchor)
        assert (result.start, result.end) == (start, end)


async def test_two_house_rows_and_separate_car_price(hass, contract, freezer):
    freezer.move_to("2026-10-23 12:00:00+00:00")
    contract["groups"][0]["add_sources"] = ["sensor.row1", "sensor.row2"]
    contract["groups"].append(
        {
            "group_id": "car",
            "group_name": "Coche",
            "add_sources": ["sensor.car"],
            "subtract_sources": [],
            "eur_per_kwh": "0.1",
        }
    )
    hass.states.async_set(
        "sensor.row1", "1000", {"unit_of_measurement": "W", "device_class": "power"}
    )
    hass.states.async_set(
        "sensor.row2", "2", {"unit_of_measurement": "kW", "device_class": "power"}
    )
    hass.states.async_set(
        "sensor.car", "100", {"unit_of_measurement": "kWh", "device_class": "energy"}
    )
    entry = MockConfigEntry(domain=DOMAIN, data=contract, title="Casa", version=1)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    freezer.tick(timedelta(minutes=2))
    entry.runtime_data._tick(dt_util.now())
    hass.states.async_set(
        "sensor.car", "100.1", {"unit_of_measurement": "kWh", "device_class": "energy"}
    )
    await hass.async_block_till_done()
    result = entry.runtime_data.data.result
    assert result.total_kwh == Decimal("0.200")
    assert abs(result.amount_for("energy") - Decimal("0.03")) < Decimal("1e-24")
    assert result.quality == "partial"


async def test_power_staleness_restart_and_unavailable_do_not_fill_gaps(hass, contract, freezer):
    freezer.move_to("2026-10-23 12:00:00+00:00")
    attributes = {"unit_of_measurement": "W", "device_class": "power"}
    hass.states.async_set("sensor.test_energy", "1000", attributes)
    entry = MockConfigEntry(domain=DOMAIN, data=contract, title="Casa", version=1)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    freezer.tick(timedelta(minutes=10))
    entry.runtime_data._tick(dt_util.now())
    assert entry.runtime_data.data.result.total_kwh == Decimal("0.083")
    await hass.config_entries.async_unload(entry.entry_id)
    freezer.tick(timedelta(hours=1))
    assert await hass.config_entries.async_setup(entry.entry_id)
    assert entry.runtime_data.data.result.total_kwh == Decimal("0.083")
    hass.states.async_set("sensor.test_energy", "2000", attributes)
    await hass.async_block_till_done()
    freezer.tick(timedelta(minutes=1))
    hass.states.async_set("sensor.test_energy", "unavailable", attributes)
    await hass.async_block_till_done()
    assert entry.runtime_data.data.result.total_kwh == Decimal("0.117")
    freezer.tick(timedelta(hours=1))
    hass.states.async_set("sensor.test_energy", "1000", attributes)
    await hass.async_block_till_done()
    assert entry.runtime_data.data.result.total_kwh == Decimal("0.117")


async def test_power_cycle_closes_at_local_boundary_without_carrying_previous_kwh(
    hass, contract, freezer
):
    freezer.move_to("2026-10-22 23:59:00+02:00")
    contract["billing_day"] = 23
    hass.states.async_set("sensor.test_energy", "1000", {"unit_of_measurement": "W"})
    entry = MockConfigEntry(domain=DOMAIN, data=contract, title="Casa", version=1)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    freezer.tick(timedelta(minutes=2))
    entry.runtime_data._tick(dt_util.now())
    assert entry.runtime_data.history[0]["result"]["total_kwh"] == "0.017"
    assert entry.runtime_data.data.result is None  # Wait for a measured new-cycle interval.
    assert "No measurements" in entry.runtime_data.data.error
    freezer.tick(timedelta(minutes=1))
    entry.runtime_data._tick(dt_util.now())
    assert entry.runtime_data.data.result.total_kwh == Decimal("0.017")


async def test_flow_accepts_power_and_rejects_incompatible_units(hass, contract):
    hass.states.async_set(
        "sensor.test_energy", "1000", {"unit_of_measurement": "W", "device_class": "power"}
    )
    hass.states.async_set("sensor.voltage", "230", {"unit_of_measurement": "V"})
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"default_tariff_mode": "fixed"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "contract_name": "Casa",
            "billing_day": 1,
            "billing_months": "1",
        },
    )
    group = {
        "group_name": "Casa",
        "add_sources": ["sensor.voltage"],
        "subtract_sources": [],
        "tariff_mode": "fixed",
    }
    result = await hass.config_entries.flow.async_configure(result["flow_id"], group)
    assert result["errors"]["base"] == "invalid_units"
    group["add_sources"] = ["sensor.test_energy"]
    result = await hass.config_entries.flow.async_configure(result["flow_id"], group)
    assert result["step_id"] == "tariff"


async def test_restored_power_waits_for_live_device_report(hass, contract, freezer):
    freezer.move_to("2026-10-23 12:00:00+00:00")
    hass.states.async_set(
        "sensor.test_energy", "1000", {"unit_of_measurement": "W", "restored": True}
    )
    entry = MockConfigEntry(domain=DOMAIN, data=contract, title="Casa", version=1)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    freezer.tick(timedelta(minutes=1))
    entry.runtime_data._tick(dt_util.now())
    assert not entry.runtime_data.ledger.intervals
    hass.states.async_set("sensor.test_energy", "1000", {"unit_of_measurement": "W"})
    await hass.async_block_till_done()
    freezer.tick(timedelta(minutes=1))
    entry.runtime_data._tick(dt_util.now())
    assert entry.runtime_data.data.result.total_kwh == Decimal("0.017")
