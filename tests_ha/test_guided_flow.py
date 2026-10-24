"""Progressive tariff-first setup and compatibility with existing contracts."""

from datetime import timedelta
from decimal import Decimal

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.luz_en_cifras.const import DOMAIN


async def test_old_decimal_day_values_are_migrated_without_truncation(hass, contract):
    contract.update(billing_day="1.0", billing_anchor_month="1.0")
    hass.states.async_set("sensor.test_energy", "100", {"unit_of_measurement": "kWh"})
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=contract,
        options={"billing_day": "1.0"},
        title="Casa",
        version=1,
        minor_version=2,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    assert entry.minor_version == 3
    assert entry.data["billing_day"] == 1
    assert entry.options["billing_day"] == 1
    assert entry.runtime_data.config["contract_id"] == contract["contract_id"]


async def test_fractional_billing_day_or_month_has_actionable_validation(hass):
    flow = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    flow = await hass.config_entries.flow.async_configure(
        flow["flow_id"], {"default_tariff_mode": "fixed"}
    )
    values = {"contract_name": "Casa", "billing_day": 1.5, "billing_months": "2"}
    flow = await hass.config_entries.flow.async_configure(flow["flow_id"], values)
    assert flow["errors"]["billing_day"] == "whole_number"
    flow = await hass.config_entries.flow.async_configure(
        flow["flow_id"], {**values, "billing_day": 15}
    )
    flow = await hass.config_entries.flow.async_configure(
        flow["flow_id"], {"billing_anchor_month": 2.5}
    )
    assert flow["errors"]["billing_anchor_month"] == "whole_number"


@pytest.mark.parametrize(
    "mode,expected",
    [
        ("fixed", {"eur_per_kwh"}),
        ("three_period", {"p1_price", "p2_price", "p3_price"}),
        ("entity", {"price_entity", "price_markup", "price_max_age_minutes"}),
    ],
)
async def test_tariff_precedes_power_and_only_relevant_prices_are_shown(hass, mode, expected):
    hass.states.async_set("sensor.energy", "10", {"unit_of_measurement": "kWh"})
    flow = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert flow["step_id"] == "modality"
    flow = await hass.config_entries.flow.async_configure(
        flow["flow_id"], {"default_tariff_mode": mode}
    )
    assert flow["step_id"] == "contract"
    assert {str(key) for key in flow["data_schema"].schema} == {
        "contract_name",
        "billing_day",
        "billing_months",
    }
    flow = await hass.config_entries.flow.async_configure(
        flow["flow_id"],
        {
            "contract_name": "Casa",
            "billing_day": 23,
            "billing_months": "1",
        },
    )
    assert flow["step_id"] == "group"
    marker = next(key for key in flow["data_schema"].schema if str(key) == "tariff_mode")
    assert marker.default() == mode
    flow = await hass.config_entries.flow.async_configure(
        flow["flow_id"],
        {
            "group_name": "Vivienda",
            "add_sources": ["sensor.energy"],
            "subtract_sources": [],
            "tariff_mode": mode,
        },
    )
    assert flow["step_id"] == "tariff"
    assert {str(key) for key in flow["data_schema"].schema} == expected


async def test_bimonthly_anchor_is_requested_only_after_choosing_two_months(hass):
    flow = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    flow = await hass.config_entries.flow.async_configure(
        flow["flow_id"], {"default_tariff_mode": "fixed"}
    )
    flow = await hass.config_entries.flow.async_configure(
        flow["flow_id"],
        {
            "contract_name": "Casa",
            "billing_day": 15,
            "billing_months": "2",
        },
    )
    assert flow["step_id"] == "cycle_anchor"
    assert {str(key) for key in flow["data_schema"].schema} == {"billing_anchor_month"}
    flow = await hass.config_entries.flow.async_configure(
        flow["flow_id"], {"billing_anchor_month": 2}
    )
    assert flow["step_id"] == "group"


async def test_editing_basic_contract_preserves_power_and_advanced_settings(
    hass, contract, freezer
):
    freezer.move_to("2026-10-23 12:00:00+00:00")
    attributes = {"unit_of_measurement": "kWh"}
    hass.states.async_set("sensor.test_energy", "100", attributes)
    contract.update(
        power_p1_kw="4.6",
        power_p2_kw="5.75",
        power_price_unit="year",
        power_p1_eur_per_kw_day="36",
        power_p2_eur_per_kw_day="1.2",
        approximate_intervals=True,
        power_max_age_minutes=15,
    )
    entry = MockConfigEntry(domain=DOMAIN, data=contract, title="Casa", version=1)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    freezer.tick(timedelta(minutes=1))
    hass.states.async_set("sensor.test_energy", "102", attributes)
    await hass.async_block_till_done()
    flow = await hass.config_entries.options.async_init(entry.entry_id)
    flow = await hass.config_entries.options.async_configure(
        flow["flow_id"], {"next_step_id": "contract"}
    )
    flow = await hass.config_entries.options.async_configure(
        flow["flow_id"],
        {
            "contract_name": "Casa",
            "billing_day": 1,
            "billing_months": "1",
        },
    )
    flow = await hass.config_entries.options.async_configure(
        flow["flow_id"], {"next_step_id": "power_unit"}
    )
    flow = await hass.config_entries.options.async_configure(
        flow["flow_id"], {"power_price_unit": "year"}
    )
    assert flow["description_placeholders"]["power_price_unit"] == "€/kW/año"
    assert (
        next(key for key in flow["data_schema"].schema if str(key) == "power_p1_kw").default()
        == 4.6
    )
    values = {
        key: value
        for key, value in contract.items()
        if key
        in {
            "power_p1_kw",
            "power_p2_kw",
            "power_p1_eur_per_kw_day",
            "power_p2_eur_per_kw_day",
            "meter_rental_daily",
        }
    }
    flow = await hass.config_entries.options.async_configure(flow["flow_id"], values)
    flow = await hass.config_entries.options.async_configure(
        flow["flow_id"], {"next_step_id": "advanced"}
    )
    assert {str(key) for key in flow["data_schema"].schema} == {
        "approximate_intervals",
        "show_secondary_entities",
        "power_max_age_minutes",
    }
    flow = await hass.config_entries.options.async_configure(
        flow["flow_id"],
        {
            "approximate_intervals": True,
            "show_secondary_entities": True,
            "power_max_age_minutes": 15,
        },
    )
    flow = await hass.config_entries.options.async_configure(
        flow["flow_id"], {"next_step_id": "finish"}
    )
    assert flow["type"] == "create_entry"
    await hass.async_block_till_done()
    assert Decimal(str(entry.runtime_data.config["power_p1_kw"])) == Decimal("4.6")
    assert Decimal(str(entry.runtime_data.config["power_p2_kw"])) == Decimal("5.75")
    assert Decimal(str(entry.runtime_data.config["power_p1_eur_per_kw_day"])) == Decimal("36")
    assert entry.runtime_data.config["power_max_age_minutes"] == 15
    assert entry.runtime_data.config["approximate_intervals"] is True
    assert entry.runtime_data.data.result.total_kwh == Decimal(2)
