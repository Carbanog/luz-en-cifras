"""Exercise audit fixes with HA states, events, reload and persisted history."""

from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal

import pytest
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.luz_en_cifras.const import DOMAIN
from custom_components.luz_en_cifras.domain import DataQuality

ENERGY = {"unit_of_measurement": "kWh", "device_class": "energy"}
D = Decimal


async def test_three_period_contract_crosses_unlisted_year_offline(hass, contract, freezer):
    freezer.move_to("2027-12-31 23:59:00+01:00")
    contract["groups"][0].update(
        tariff_mode="three_period", p1_price="0.3", p2_price="0.2", p3_price="0.1"
    )
    hass.states.async_set("sensor.test_energy", "100", ENERGY)
    entry = MockConfigEntry(domain=DOMAIN, data=contract, title="Fixture", version=1)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    freezer.tick(timedelta(minutes=1))
    hass.states.async_set("sensor.test_energy", "101", ENERGY)
    await hass.async_block_till_done()
    assert D(entry.runtime_data.history[0]["result"]["total_kwh"]) == 1
    freezer.tick(timedelta(minutes=1))
    hass.states.async_set("sensor.test_energy", "102", ENERGY)
    await hass.async_block_till_done()
    assert entry.runtime_data.billing_period.start == date(2028, 1, 1)
    assert entry.runtime_data.data.result.total_kwh == 1
    assert entry.runtime_data.data.result.amount_for("energy") == D("0.1")
    await hass.config_entries.async_unload(entry.entry_id)
    assert await hass.config_entries.async_setup(entry.entry_id)
    assert entry.runtime_data.data.result.amount_for("energy") == D("0.1")


async def test_edit_billing_day_defers_calendar_and_preserves_open_ledger(hass, contract, freezer):
    freezer.move_to("2026-10-15 11:00:00+02:00")
    contract.update(power_p1_kw="3", power_p1_eur_per_kw_day="0.1")
    hass.states.async_set("sensor.test_energy", "100", ENERGY)
    entry = MockConfigEntry(domain=DOMAIN, data=contract, title="Fixture", version=1)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    freezer.tick(timedelta(hours=1))
    hass.states.async_set("sensor.test_energy", "101", ENERGY)
    await hass.async_block_till_done()
    changed = deepcopy(contract)
    changed["billing_day"] = 10
    hass.config_entries.async_update_entry(entry, options=changed)
    await hass.async_block_till_done()
    assert entry.runtime_data.data.result.total_kwh == 1
    assert entry.runtime_data.data.result.amount_for("power") == D("4.5")
    assert not entry.runtime_data.history
    assert entry.runtime_data.billing_period.end == date(2026, 11, 1)
    freezer.move_to("2026-11-01 00:00:00+01:00")
    entry.runtime_data._tick(dt_util.now())
    assert len(entry.runtime_data.history) == 1
    assert entry.runtime_data.billing_period.start == date(2026, 11, 1)
    assert entry.runtime_data.billing_period.end == date(2026, 11, 10)


@pytest.mark.parametrize("estimate", [False, True])
async def test_late_boundary_counter_preserves_delta_and_closed_original(
    hass, contract, freezer, estimate
):
    freezer.move_to("2026-10-31 23:58:00+01:00")
    contract["approximate_intervals"] = estimate
    hass.states.async_set("sensor.test_energy", "100", ENERGY)
    entry = MockConfigEntry(domain=DOMAIN, data=contract, title="Fixture", version=1)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    freezer.tick(timedelta(minutes=1))
    hass.states.async_set("sensor.test_energy", "101", ENERGY)
    await hass.async_block_till_done()
    freezer.tick(timedelta(minutes=1))
    entry.runtime_data._tick(dt_util.now())
    original = deepcopy(entry.runtime_data.history[0])
    freezer.tick(timedelta(minutes=1))
    hass.states.async_set("sensor.test_energy", "103", ENERGY)
    await hass.async_block_till_done()
    assert entry.runtime_data.history[0] == original
    assert len(entry.runtime_data.history) == 2
    assert entry.runtime_data.history[-1]["supersedes"] == original["id"]
    if not estimate:
        assert any(
            "2 kWh" in warning and "pendiente de reparto" in warning
            for warning in entry.runtime_data.data.collection_warnings
        )
    freezer.tick(timedelta(minutes=1))
    hass.states.async_set("sensor.test_energy", "104", ENERGY)
    await hass.async_block_till_done()
    result = entry.runtime_data.data.result
    closed = entry.runtime_data.history[-1]
    if estimate:
        assert D(closed["result"]["total_kwh"]) + result.total_kwh == 4
    else:
        assert result.total_kwh == 1
        assert any("pendiente de reparto" in warning for warning in result.warnings)
        assert any(D(item["kwh"]) == 2 for item in closed["raw"]["intervals"])
    await hass.config_entries.async_unload(entry.entry_id)
    assert await hass.config_entries.async_setup(entry.entry_id)
    assert entry.runtime_data.data.result.total_kwh == result.total_kwh
    assert len(entry.runtime_data.history) == 2


async def test_report_exactly_on_boundary_counts_in_closed_cycle_and_next_is_complete(
    hass, contract, freezer
):
    freezer.move_to("2026-10-31 23:59:00+01:00")
    hass.states.async_set("sensor.test_energy", "100", ENERGY)
    entry = MockConfigEntry(domain=DOMAIN, data=contract, title="Fixture", version=1)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    freezer.tick(timedelta(minutes=1))
    hass.states.async_set("sensor.test_energy", "101", ENERGY)
    await hass.async_block_till_done()
    assert D(entry.runtime_data.history[0]["result"]["total_kwh"]) == 1
    freezer.tick(timedelta(minutes=1))
    hass.states.async_set("sensor.test_energy", "102", ENERGY)
    await hass.async_block_till_done()
    assert entry.runtime_data.data.result.total_kwh == 1
    assert entry.runtime_data.data.result.quality == DataQuality.COMPLETE


@pytest.mark.parametrize("repeated", [False, True])
async def test_identical_dynamic_quote_freshness_and_real_expiry(hass, contract, freezer, repeated):
    freezer.move_to("2026-10-15 12:00:00+02:00")
    contract["groups"][0].update(
        tariff_mode="entity", price_entity="sensor.quote", price_max_age_minutes=65
    )
    hass.states.async_set("sensor.quote", "0.12", {"unit_of_measurement": "€/kWh"})
    hass.states.async_set("sensor.test_energy", "100", ENERGY)
    entry = MockConfigEntry(domain=DOMAIN, data=contract, title="Fixture", version=1)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    initial = hass.states.get("sensor.quote").last_updated
    for _ in range(4):
        freezer.tick(timedelta(minutes=30))
        if repeated:
            hass.states.async_set("sensor.quote", "0.12", {"unit_of_measurement": "€/kWh"})
            assert hass.states.get("sensor.quote").last_updated == initial
            assert hass.states.get("sensor.quote").last_reported > initial
        entry.runtime_data._tick(dt_util.now())
    freezer.tick(timedelta(minutes=1))
    hass.states.async_set("sensor.test_energy", "101", ENERGY)
    await hass.async_block_till_done()
    if repeated:
        assert entry.runtime_data.data.result.amount_for("energy") == D("0.12")
        await hass.config_entries.async_unload(entry.entry_id)
        assert await hass.config_entries.async_setup(entry.entry_id)
        assert entry.runtime_data.data.result.amount_for("energy") == D("0.12")
    else:
        assert entry.runtime_data.data.result is None
        assert any("caducado" in warning for warning in entry.runtime_data.data.collection_warnings)
