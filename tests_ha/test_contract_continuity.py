"""Real config reloads retain one invoice across meter and tariff revisions."""

from copy import deepcopy
from datetime import timedelta
from decimal import Decimal

from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.luz_en_cifras.const import DOMAIN

D = Decimal
ENERGY = {"unit_of_measurement": "kWh", "device_class": "energy"}


async def test_replacing_and_reselecting_meter_keeps_one_bill_and_does_not_bridge_detached_usage(
    hass, contract, freezer
):
    freezer.move_to("2026-10-23 12:00:00+00:00")
    contract.update(
        power_p1_kw="3", power_p1_eur_per_kw_day="0.1", meter_rental_daily="0.1", invoice_fee="2"
    )
    hass.states.async_set("sensor.test_energy", "100", ENERGY)
    hass.states.async_set("sensor.replacement", "1000", ENERGY)
    entry = MockConfigEntry(domain=DOMAIN, data=contract, title="Casa", version=1)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    freezer.tick(timedelta(minutes=1))
    hass.states.async_set("sensor.test_energy", "110", ENERGY)
    await hass.async_block_till_done()
    fixed_before = entry.runtime_data.data.result.amount_for("fixed")
    power_before = entry.runtime_data.data.result.amount_for("power")
    original_collector = entry.runtime_data
    hass.states.async_set("sensor.replacement", "1000", ENERGY)  # Genuine report at transition.
    changed = deepcopy(contract)
    changed["groups"][0].update(add_sources=["sensor.replacement"], eur_per_kwh="0.5")
    hass.config_entries.async_update_entry(entry, options=changed)
    assert original_collector.config["groups"][0]["add_sources"] == ["sensor.test_energy"]
    await hass.async_block_till_done()
    assert entry.runtime_data.data.result.total_kwh == 10
    assert any(
        "esperando mediciones" in warning for warning in entry.runtime_data.data.collection_warnings
    )
    freezer.tick(timedelta(minutes=1))
    hass.states.async_set("sensor.replacement", "1004", ENERGY)
    hass.states.async_set("sensor.test_energy", "900", ENERGY)  # Detached device: not billable.
    await hass.async_block_till_done()
    result = entry.runtime_data.data.result
    assert result.total_kwh == 14
    assert result.amount_for("energy") == 4
    assert result.amount_for("fixed") == fixed_before
    assert result.amount_for("power") == power_before
    assert not entry.runtime_data.history
    changed = deepcopy(changed)
    changed["groups"][0].update(add_sources=["sensor.test_energy"], eur_per_kwh="0.3")
    hass.config_entries.async_update_entry(entry, options=deepcopy(changed))
    await hass.async_block_till_done()
    assert entry.runtime_data.data.result.total_kwh == 14
    freezer.tick(timedelta(minutes=1))
    hass.states.async_set("sensor.test_energy", "905", ENERGY)
    await hass.async_block_till_done()
    assert entry.runtime_data.data.result.total_kwh == 19
    assert entry.runtime_data.data.result.amount_for("energy") == D("5.5")
    await hass.config_entries.async_unload(entry.entry_id)
    assert await hass.config_entries.async_setup(entry.entry_id)
    assert entry.runtime_data.data.result.total_kwh == 19
    assert entry.runtime_data.data.result.amount_for("fixed") == fixed_before
    freezer.move_to("2026-11-01 00:01:00+01:00")
    entry.runtime_data._tick(dt_util.now())
    assert len(entry.runtime_data.history) == 1
    closed = entry.runtime_data.history[0]
    assert closed["result"]["total_kwh"] == "19.000"
    revised = await entry.runtime_data.async_recalculate(
        closed["id"], "Verificar continuidad", False
    )
    assert revised["result"]["total"] == closed["result"]["total"]
    assert revised["result"]["total_kwh"] == closed["result"]["total_kwh"]


async def test_fixed_three_period_and_dynamic_tariffs_share_one_energy_history(
    hass, contract, freezer
):
    freezer.move_to("2026-10-23 09:00:00+02:00")
    contract["groups"][0]["eur_per_kwh"] = "0.1"
    hass.states.async_set("sensor.test_energy", "100", ENERGY)
    entry = MockConfigEntry(domain=DOMAIN, data=contract, title="Casa", version=1)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    freezer.tick(timedelta(minutes=10))
    hass.states.async_set("sensor.test_energy", "110", ENERGY)
    await hass.async_block_till_done()
    changed = deepcopy(contract)
    changed["groups"][0].update(
        tariff_mode="three_period", p1_price="0.3", p2_price="0.2", p3_price="0.1"
    )
    hass.config_entries.async_update_entry(entry, options=changed)
    await hass.async_block_till_done()
    freezer.tick(timedelta(minutes=10))
    hass.states.async_set("sensor.test_energy", "120", ENERGY)
    await hass.async_block_till_done()
    assert entry.runtime_data.data.result.amount_for("energy") == 3
    hass.states.async_set("sensor.quote", "100", {"unit_of_measurement": "€/MWh"})
    changed = deepcopy(changed)
    changed["groups"][0].update(tariff_mode="entity", price_entity="sensor.quote")
    hass.config_entries.async_update_entry(entry, options=changed)
    await hass.async_block_till_done()
    freezer.tick(timedelta(minutes=10))
    hass.states.async_set("sensor.test_energy", "130", ENERGY)
    await hass.async_block_till_done()
    assert entry.runtime_data.data.result.total_kwh == 30
    assert entry.runtime_data.data.result.amount_for("energy") == 4
    assert all(
        line.metadata["group_id"] == "home"
        for line in entry.runtime_data.data.result.lines
        if line.category == "energy"
    )
    await hass.config_entries.async_unload(entry.entry_id)
    assert await hass.config_entries.async_setup(entry.entry_id)
    assert entry.runtime_data.data.result.amount_for("energy") == 4


async def test_adding_car_group_and_residual_house_does_not_reprice_previous_whole_house(
    hass, contract, freezer
):
    freezer.move_to("2026-10-23 12:00:00+00:00")
    hass.states.async_set("sensor.test_energy", "100", ENERGY)
    hass.states.async_set("sensor.car", "50", ENERGY)
    entry = MockConfigEntry(domain=DOMAIN, data=contract, title="Casa", version=1)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    freezer.tick(timedelta(minutes=1))
    hass.states.async_set("sensor.test_energy", "110", ENERGY)
    await hass.async_block_till_done()
    changed = deepcopy(contract)
    changed["groups"][0]["subtract_sources"] = ["sensor.car"]
    hass.states.async_set("sensor.car", "50", ENERGY)
    changed["groups"].append(
        {
            "group_id": "car",
            "group_name": "Coche",
            "add_sources": ["sensor.car"],
            "subtract_sources": [],
            "eur_per_kwh": "0.1",
        }
    )
    hass.config_entries.async_update_entry(entry, options=changed)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.casa_coche_energia").state == "unknown"
    freezer.tick(timedelta(minutes=1))
    hass.states.async_set("sensor.test_energy", "120", ENERGY)
    hass.states.async_set("sensor.car", "54", ENERGY)
    await hass.async_block_till_done()
    assert entry.runtime_data.data.result.total_kwh == 20
    assert entry.runtime_data.data.result.amount_for("energy") == D("3.6")


async def test_power_meter_can_be_replaced_by_energy_counter_without_losing_previous_kwh(
    hass, contract, freezer
):
    freezer.move_to("2026-10-23 12:00:00+00:00")
    hass.states.async_set("sensor.test_energy", "1000", {"unit_of_measurement": "W"})
    hass.states.async_set("sensor.counter", "100", ENERGY)
    entry = MockConfigEntry(domain=DOMAIN, data=contract, title="Casa", version=1)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    freezer.tick(timedelta(minutes=1))
    entry.runtime_data._tick(dt_util.now())
    assert entry.runtime_data.data.result.total_kwh == D("0.017")
    changed = deepcopy(contract)
    changed["groups"][0]["add_sources"] = ["sensor.counter"]
    hass.states.async_set("sensor.counter", "100", ENERGY)
    hass.config_entries.async_update_entry(entry, options=changed)
    await hass.async_block_till_done()
    freezer.tick(timedelta(minutes=1))
    hass.states.async_set("sensor.counter", "101", ENERGY)
    await hass.async_block_till_done()
    assert entry.runtime_data.data.result.total_kwh == D("1.017")
    assert not entry.runtime_data.history


async def test_cached_replacement_waits_for_genuine_baseline_even_after_reload(
    hass, contract, freezer
):
    freezer.move_to("2026-10-23 12:00:00+00:00")
    hass.states.async_set("sensor.test_energy", "100", ENERGY)
    hass.states.async_set("sensor.replacement", "1000", ENERGY)
    entry = MockConfigEntry(domain=DOMAIN, data=contract, title="Casa", version=1)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    freezer.tick(timedelta(minutes=1))
    hass.states.async_set("sensor.test_energy", "110", ENERGY)
    await hass.async_block_till_done()
    changed = deepcopy(contract)
    changed["groups"][0]["add_sources"] = ["sensor.replacement"]
    hass.config_entries.async_update_entry(entry, options=changed)
    await hass.async_block_till_done()
    assert "sensor.replacement" in entry.runtime_data.ledger.pending_energy_sources
    await hass.config_entries.async_unload(entry.entry_id)
    assert await hass.config_entries.async_setup(entry.entry_id)
    freezer.tick(timedelta(minutes=1))
    hass.states.async_set("sensor.replacement", "1007", ENERGY)
    await hass.async_block_till_done()
    assert entry.runtime_data.data.result.total_kwh == 10  # Baseline, not seven billable kWh.
    freezer.tick(timedelta(minutes=1))
    hass.states.async_set("sensor.replacement", "1010", ENERGY)
    await hass.async_block_till_done()
    assert entry.runtime_data.data.result.total_kwh == 13


async def test_tariff_crossing_needs_consent_and_later_consent_keeps_historical_prices(
    hass, contract, freezer
):
    freezer.move_to("2026-10-23 12:00:00+00:00")
    hass.states.async_set("sensor.test_energy", "100", ENERGY)
    entry = MockConfigEntry(domain=DOMAIN, data=contract, title="Casa", version=1)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    freezer.tick(timedelta(minutes=1))
    changed = deepcopy(contract)
    changed["groups"][0]["eur_per_kwh"] = "0.4"
    hass.config_entries.async_update_entry(entry, options=deepcopy(changed))
    await hass.async_block_till_done()
    freezer.tick(timedelta(minutes=1))
    hass.states.async_set("sensor.test_energy", "110", ENERGY)
    await hass.async_block_till_done()
    assert entry.runtime_data.data.result is None
    assert "configuration boundary" in entry.runtime_data.data.error
    freezer.tick(timedelta(seconds=30))
    changed["approximate_intervals"] = True
    hass.config_entries.async_update_entry(entry, options=changed)
    await hass.async_block_till_done()
    assert entry.runtime_data.data.result.total_kwh == 10
    assert entry.runtime_data.data.result.amount_for("energy") == 3  # 5*.2 + 5*.4
    assert entry.runtime_data.data.result.quality == "partial"
