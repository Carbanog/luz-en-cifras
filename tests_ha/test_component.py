"""Exercise real Home Assistant setup, state events, options and persistence."""

from datetime import timedelta
from decimal import Decimal

import pytest
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.luz_en_cifras.const import DOMAIN


async def test_setup_collect_unload_reload_preserves_measurements(hass, contract, freezer, caplog):
    freezer.move_to("2026-10-23 12:00:00+00:00")
    hass.states.async_set(
        "sensor.test_energy", "100", {"unit_of_measurement": "kWh", "device_class": "energy"}
    )
    entry = MockConfigEntry(domain=DOMAIN, data=contract, title="Casa", version=1)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    freezer.tick(timedelta(minutes=1))
    hass.states.async_set(
        "sensor.test_energy", "102", {"unit_of_measurement": "kWh", "device_class": "energy"}
    )
    await hass.async_block_till_done()
    assert entry.runtime_data.data.result.total_kwh == Decimal(2)
    assert "impossible considering device class" not in caplog.text
    assert entry.runtime_data.data.result.amount_for("energy") == Decimal("0.4")
    await hass.config_entries.async_unload(entry.entry_id)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.runtime_data.data.result.total_kwh == Decimal(2)


async def test_unknown_and_counter_correction_do_not_invent_consumption(hass, contract, freezer):
    freezer.move_to("2026-10-23 12:00:00+00:00")
    attributes = {"unit_of_measurement": "kWh", "device_class": "energy"}
    hass.states.async_set("sensor.test_energy", "100", attributes)
    entry = MockConfigEntry(domain=DOMAIN, data=contract, title="Casa", version=1)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    for value in ("unavailable", "NaN", "20", "21"):
        freezer.tick(timedelta(seconds=10))
        hass.states.async_set("sensor.test_energy", value, attributes)
        await hass.async_block_till_done()
    assert entry.runtime_data.data.result.total_kwh == Decimal(1)
    assert entry.runtime_data.data.collection_warnings


async def test_native_flow_creates_group(hass, contract):
    hass.states.async_set(
        "sensor.test_energy", "0", {"unit_of_measurement": "kWh", "device_class": "energy"}
    )
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["step_id"] == "contract"
    values = {key: value for key, value in contract.items() if key not in {"contract_id", "groups"}}
    values.update(
        billing_months="1",
        power_price_unit="day",
        approximate_intervals=False,
        show_secondary_entities=True,
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], values)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "add_group"}
    )
    group = {
        key: value
        for key, value in contract["groups"][0].items()
        if key not in {"group_id", "eur_per_kwh"}
    }
    group.update(tariff_mode="fixed")
    result = await hass.config_entries.flow.async_configure(result["flow_id"], group)
    assert result["step_id"] == "tariff"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"eur_per_kwh": 0.2})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "finish"}
    )
    assert result["type"] == "create_entry"
    assert len(result["data"]["groups"]) == 1


async def test_dynamic_prices_are_frozen_and_options_preserve_entity_ids(hass, contract, freezer):
    freezer.move_to("2026-10-23 12:00:00+00:00")
    attributes = {"unit_of_measurement": "kWh", "device_class": "energy"}
    contract["groups"][0].update(tariff_mode="entity", price_entity="sensor.test_price")
    hass.states.async_set("sensor.test_energy", "100", attributes)
    hass.states.async_set("sensor.test_price", "100", {"unit_of_measurement": "€/MWh"})
    entry = MockConfigEntry(domain=DOMAIN, data=contract, title="Casa", version=1)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    freezer.tick(timedelta(minutes=10))
    hass.states.async_set("sensor.test_energy", "110", attributes)
    await hass.async_block_till_done()
    hass.states.async_set("sensor.test_price", "300", {"unit_of_measurement": "€/MWh"})
    await hass.async_block_till_done()
    freezer.tick(timedelta(minutes=10))
    hass.states.async_set("sensor.test_energy", "120", attributes)
    await hass.async_block_till_done()
    assert entry.runtime_data.data.result.amount_for("energy") == Decimal(4)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["step_id"] == "menu"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "finish"}
    )
    assert result["type"] == "create_entry"
    await hass.async_block_till_done()
    assert entry.runtime_data.config["contract_id"] == "test-home"
    assert entry.runtime_data.data.result.amount_for("energy") == Decimal(4)


async def test_cycle_close_and_export_keep_immutable_result(hass, contract, freezer):
    freezer.move_to("2026-10-22 12:00:00+00:00")
    contract["billing_day"] = 23
    attributes = {"unit_of_measurement": "kWh", "device_class": "energy"}
    hass.states.async_set("sensor.test_energy", "100", attributes)
    entry = MockConfigEntry(domain=DOMAIN, data=contract, title="Casa", version=1)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    freezer.tick(timedelta(minutes=1))
    hass.states.async_set("sensor.test_energy", "110", attributes)
    await hass.async_block_till_done()
    freezer.move_to("2026-10-23 00:01:00+02:00")
    entry.runtime_data._tick(dt_util.now())
    await hass.async_block_till_done()
    exported = await hass.services.async_call(
        DOMAIN, "export_history", {"entry_id": entry.entry_id}, blocking=True, return_response=True
    )
    record = exported["periods"][0]
    assert record["result"]["total_kwh"] == "10.000"
    response = await hass.services.async_call(
        DOMAIN,
        "record_invoice",
        {
            "entry_id": entry.entry_id,
            "record_id": record["id"],
            "real_total": "3.5",
            "real_kwh": "10",
        },
        blocking=True,
        return_response=True,
    )
    assert response["comparison"]["real_total"] == "3.5"
    assert entry.runtime_data.history[0]["result"] == record["result"]
    revised = await hass.services.async_call(
        DOMAIN,
        "recalculate_period",
        {
            "entry_id": entry.entry_id,
            "record_id": record["id"],
            "reason": "Regresión de revisión auditable",
        },
        blocking=True,
        return_response=True,
    )
    assert revised["supersedes"] == record["id"]
    assert entry.runtime_data.history[0]["result"] == record["result"]


async def test_three_period_tariff_and_fixed_surplus(hass, contract, freezer):
    freezer.move_to("2026-10-23 08:00:00+00:00")
    attributes = {"unit_of_measurement": "kWh", "device_class": "energy"}
    contract["groups"][0].update(
        tariff_mode="three_period", p1_price="0.3", p2_price="0.2", p3_price="0.1"
    )
    contract.update(enable_surplus=True, export_source="sensor.test_export", surplus_price="0.1")
    hass.states.async_set("sensor.test_energy", "100", attributes)
    hass.states.async_set("sensor.test_export", "0", attributes)
    entry = MockConfigEntry(domain=DOMAIN, data=contract, title="Casa", version=1)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    freezer.tick(timedelta(minutes=10))
    hass.states.async_set("sensor.test_energy", "110", attributes)
    hass.states.async_set("sensor.test_export", "50", attributes)
    await hass.async_block_till_done()
    result = entry.runtime_data.data.result
    assert result.amount_for("energy") == Decimal(3)
    assert result.amount_for("compensation") == Decimal(-3)


async def test_v1_storage_migration_retains_original_payload(hass, contract, freezer, hass_storage):
    freezer.move_to("2026-10-23 12:00:00+00:00")
    attributes = {"unit_of_measurement": "kWh", "device_class": "energy"}
    hass.states.async_set("sensor.test_energy", "102", attributes)
    entry = MockConfigEntry(domain=DOMAIN, data=contract, title="Casa", version=1, minor_version=1)
    entry.add_to_hass(hass)
    original = {
        "period": {"start": "2026-10-01", "end": "2026-11-01"},
        "baselines": {"sensor.test_energy": "102"},
        "samples": [
            {
                "source_id": "sensor.test_energy",
                "timestamp": "2026-10-22T12:00:00+02:00",
                "kwh": "2",
            }
        ],
        "warnings": [],
    }
    hass_storage[f"{DOMAIN}.{entry.entry_id}"] = {"version": 1, "data": original}
    assert await hass.config_entries.async_setup(entry.entry_id)
    assert entry.runtime_data._legacy == original
    assert entry.runtime_data.data.result.total_kwh == Decimal(2)
    assert entry.minor_version == 2


async def test_unverified_fiscal_period_creates_repair_and_manual_profile_can_resolve(
    hass, contract, freezer
):
    freezer.move_to("2026-11-03 12:00:00+00:00")
    attributes = {"unit_of_measurement": "kWh", "device_class": "energy"}
    hass.states.async_set("sensor.test_energy", "100", attributes)
    entry = MockConfigEntry(domain=DOMAIN, data=contract, title="Casa", version=1)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    assert entry.runtime_data.data.result is None
    assert ir.async_get(hass).async_get_issue(DOMAIN, f"fiscal_{entry.entry_id}") is not None
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "fiscal"}
    )
    profile = {
        "fiscal_mode": "manual",
        "tax_name": "Impuesto de prueba",
        "tax_valid_from": "2026-11-01",
        "tax_valid_to": "2026-12-01",
        "tax_electricity_percent": 5,
        "tax_indirect_percent": 21,
        "tax_minimum_eur_mwh": 1,
        "tax_source": "https://www.boe.es/",
        "tax_rules_confirmed": True,
    }
    result = await hass.config_entries.options.async_configure(result["flow_id"], profile)
    assert result["step_id"] == "menu"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "finish"}
    )
    await hass.async_block_till_done()
    freezer.tick(timedelta(minutes=1))
    hass.states.async_set("sensor.test_energy", "101", attributes)
    await hass.async_block_till_done()
    assert entry.runtime_data.data.result.fiscal_rule_id.startswith("user-reviewed:")
    assert ir.async_get(hass).async_get_issue(DOMAIN, f"fiscal_{entry.entry_id}") is None


async def test_actions_reject_other_domains(hass, contract, freezer):
    freezer.move_to("2026-10-23 12:00:00+00:00")
    hass.states.async_set("sensor.test_energy", "0", {"unit_of_measurement": "kWh"})
    entry = MockConfigEntry(domain=DOMAIN, data=contract, title="Casa", version=1)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            "export_history",
            {"entry_id": "unrelated-entry"},
            blocking=True,
            return_response=True,
        )


async def test_manual_archive_requires_consent_for_boundary_allocation(hass, contract, freezer):
    freezer.move_to("2026-10-21 23:50:00+02:00")
    attributes = {"unit_of_measurement": "kWh", "device_class": "energy"}
    hass.states.async_set("sensor.test_energy", "100", attributes)
    entry = MockConfigEntry(domain=DOMAIN, data=contract, title="Casa", version=1)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    freezer.tick(timedelta(minutes=20))
    hass.states.async_set("sensor.test_energy", "102", attributes)
    await hass.async_block_till_done()
    freezer.move_to("2026-10-23 12:00:00+02:00")
    parameters = {
        "entry_id": entry.entry_id,
        "start": "2026-10-22",
        "end": "2026-10-23",
        "tax_point": "2026-10-23",
    }
    with pytest.raises(HomeAssistantError, match="límite"):
        await hass.services.async_call(
            DOMAIN, "archive_period", parameters, blocking=True, return_response=True
        )
    assert not entry.runtime_data.history
    archived = await hass.services.async_call(
        DOMAIN,
        "archive_period",
        {**parameters, "allow_boundary_estimate": True},
        blocking=True,
        return_response=True,
    )
    assert Decimal(archived["result"]["total_kwh"]) == Decimal(1)
    assert archived["result"]["tax_point"] == "2026-10-23"
    assert archived["result"]["quality"] == "partial"
    saved = entry.runtime_data.history[-1]
    assert saved["original_measurements"]["intervals"][0]["kwh"] == "2"
    assert entry.runtime_data.data.result.total_kwh == Decimal(2)
