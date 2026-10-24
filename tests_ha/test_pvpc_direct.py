"""Synthetic official calendars exercise the real HA adapter without network access."""

import asyncio
from copy import deepcopy
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

import aiohttp
from esios_api import EsiosApiData
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.luz_en_cifras.const import DOMAIN
from custom_components.luz_en_cifras.pvpc import PvpcClient


def published(day: date = date(2026, 10, 24)) -> EsiosApiData:
    zone = ZoneInfo("Europe/Madrid")
    start = datetime.combine(day, time(), zone).astimezone(UTC)
    end = datetime.combine(day + timedelta(days=1), time(), zone).astimezone(UTC)
    values = {
        start + timedelta(hours=index): 0.1
        for index in range(int((end - start).total_seconds() / 3600))
    }
    return EsiosApiData(start, "esios_public", {"PVPC": values}, {"PVPC": True})


async def test_direct_pvpc_prices_each_hour_and_restarts_offline_from_published_cache(
    hass, contract, freezer
):
    freezer.move_to("2026-10-24 12:00:00+00:00")
    contract["power_max_age_minutes"] = 120
    contract["groups"][0]["tariff_mode"] = "pvpc"
    contract["groups"].append(
        {
            "group_id": "car",
            "group_name": "Coche",
            "add_sources": ["sensor.car"],
            "eur_per_kwh": "0.05",
        }
    )
    hass.states.async_set("sensor.test_energy", "1000", {"unit_of_measurement": "W"})
    hass.states.async_set("sensor.car", "200", {"unit_of_measurement": "W"})
    data = published()
    data.sensors["PVPC"][datetime(2026, 10, 24, 13, tzinfo=UTC)] = 0.3
    with patch("custom_components.luz_en_cifras.pvpc.PVPCData") as factory:
        api = factory.return_value
        api.async_update_all = AsyncMock(return_value=data)
        entry = MockConfigEntry(domain=DOMAIN, data=contract, title="Casa", version=1)
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        assert not hass.config_entries.async_entries("pvpc_hourly_pricing")
        assert hass.states.get("sensor.casa_vivienda_precio_pvpc_sin_impuestos").state == "0.1"
        assert factory.call_args.kwargs["sensor_keys"] == ("PVPC",)
        assert "api_token" not in factory.call_args.kwargs
        for _ in range(2):
            freezer.tick(timedelta(hours=1))
            entry.runtime_data._tick(dt_util.now())
        result = entry.runtime_data.data.result
        assert result.total_kwh == Decimal("2.400")
        assert result.amount_for("energy") == Decimal("0.42")
        assert len(entry.runtime_data.ledger.rates) == 25
        # A genuine device report refreshes power TTL; reloading must not do so.
        hass.states.async_set("sensor.test_energy", "1000", {"unit_of_measurement": "W"})
        hass.states.async_set("sensor.car", "200", {"unit_of_measurement": "W"})
        await hass.config_entries.async_unload(entry.entry_id)
        api.async_update_all = AsyncMock(side_effect=TimeoutError)
        assert await hass.config_entries.async_setup(entry.entry_id)
        assert entry.runtime_data.data.result.total_kwh == Decimal("2.400")
        assert len(entry.runtime_data.ledger.rates) == 25
        freezer.tick(timedelta(minutes=1))
        entry.runtime_data._tick(dt_util.now())
        assert entry.runtime_data.data.result.total_kwh > Decimal("2.400")
        assert any("PVPC directo" in item for item in entry.runtime_data.data.collection_warnings)


async def test_cold_outage_collects_measurements_and_recovers_without_zero_price(
    hass, contract, freezer
):
    freezer.move_to("2026-10-24 12:00:00+00:00")
    contract["groups"][0]["tariff_mode"] = "pvpc"
    hass.states.async_set("sensor.test_energy", "1000", {"unit_of_measurement": "W"})
    with patch("custom_components.luz_en_cifras.pvpc.PVPCData") as factory:
        api = factory.return_value
        api.async_update_all = AsyncMock(side_effect=aiohttp.ClientConnectionError)
        entry = MockConfigEntry(domain=DOMAIN, data=contract, title="Casa", version=1)
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        freezer.tick(timedelta(minutes=1))
        coordinator = entry.runtime_data
        coordinator._tick(dt_util.now())
        assert coordinator.data.result is None
        original = deepcopy(coordinator.ledger.intervals)
        assert original
        api.async_update_all = AsyncMock(return_value=published())
        await coordinator._async_refresh_pvpc(dt_util.now())
        assert coordinator.data.error is None
        assert coordinator.data.result.total_kwh == Decimal("0.017")
        assert coordinator.ledger.intervals == original


async def test_malformed_download_preserves_good_calendar_and_cancellation_propagates(hass):
    with patch("custom_components.luz_en_cifras.pvpc.PVPCData") as factory:
        api = factory.return_value
        api.async_update_all = AsyncMock(return_value=published())
        client = PvpcClient(async_get_clientsession(hass))
        now = datetime(2026, 10, 24, 12, tzinfo=UTC)
        await client.async_refresh(now)
        original = dict(client.prices)
        broken = published()
        broken.sensors["PVPC"].pop(next(iter(broken.sensors["PVPC"])))
        api.async_update_all = AsyncMock(return_value=broken)
        await client.async_refresh(now)
        assert client.warning and client.prices == original
        api.async_update_all = AsyncMock(side_effect=asyncio.CancelledError)
        try:
            await client.async_refresh(now)
        except asyncio.CancelledError:
            pass
        else:
            raise AssertionError("Cancellation must not be converted into an API warning")


async def test_switching_direct_pvpc_to_entity_keeps_old_prices_without_overlaps(
    hass, contract, freezer
):
    freezer.move_to("2026-10-24 12:00:00+00:00")
    contract["power_max_age_minutes"] = 120
    contract["groups"][0]["tariff_mode"] = "pvpc"
    hass.states.async_set("sensor.test_energy", "1000", {"unit_of_measurement": "W"})
    with patch("custom_components.luz_en_cifras.pvpc.PVPCData") as factory:
        factory.return_value.async_update_all = AsyncMock(return_value=published())
        entry = MockConfigEntry(domain=DOMAIN, data=contract, title="Casa", version=1)
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        freezer.tick(timedelta(hours=1))
        entry.runtime_data._tick(dt_util.now())
        changed = deepcopy(contract)
        changed["groups"][0].update(tariff_mode="entity", price_entity="sensor.price")
        hass.states.async_set("sensor.price", "0.2", {"unit_of_measurement": "€/kWh"})
        hass.config_entries.async_update_entry(entry, options=changed)
        await hass.async_block_till_done()
        freezer.tick(timedelta(hours=1))
        entry.runtime_data._tick(dt_util.now())
        assert entry.runtime_data.data.result.total_kwh == 2
        assert entry.runtime_data.data.result.amount_for("energy") == Decimal("0.3")


async def test_unload_cancels_inflight_pvpc_refresh_before_persisting(hass, contract, freezer):
    freezer.move_to("2026-10-24 12:00:00+00:00")
    contract["groups"][0]["tariff_mode"] = "pvpc"
    hass.states.async_set("sensor.test_energy", "1000", {"unit_of_measurement": "W"})
    with patch("custom_components.luz_en_cifras.pvpc.PVPCData") as factory:
        api = factory.return_value
        api.async_update_all = AsyncMock(return_value=published())
        entry = MockConfigEntry(domain=DOMAIN, data=contract, title="Casa", version=1)
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        entered, blocked = asyncio.Event(), asyncio.Event()

        async def waiting(*args):
            entered.set()
            await blocked.wait()
            return published()

        api.async_update_all.side_effect = waiting
        coordinator = entry.runtime_data
        task = hass.async_create_task(coordinator._async_refresh_pvpc(dt_util.now()))
        async with asyncio.timeout(2):
            await entered.wait()
            assert await hass.config_entries.async_unload(entry.entry_id)
        assert task.cancelled()
        assert coordinator._stopping


async def test_fixed_contract_never_initializes_a_network_client(hass, contract):
    hass.states.async_set("sensor.test_energy", "100", {"unit_of_measurement": "kWh"})
    with patch("custom_components.luz_en_cifras.pvpc.PVPCData") as factory:
        entry = MockConfigEntry(domain=DOMAIN, data=contract, title="Casa", version=1)
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        factory.assert_not_called()


async def test_cached_calendar_is_not_extrapolated_into_a_missing_day(hass, contract, freezer):
    freezer.move_to("2026-10-24 23:58:00+02:00")
    contract["groups"][0]["tariff_mode"] = "pvpc"
    hass.states.async_set("sensor.test_energy", "1000", {"unit_of_measurement": "W"})
    with patch("custom_components.luz_en_cifras.pvpc.PVPCData") as factory:
        api = factory.return_value
        api.async_update_all = AsyncMock(return_value=published())
        entry = MockConfigEntry(domain=DOMAIN, data=contract, title="Casa", version=1)
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        freezer.tick(timedelta(minutes=2))
        entry.runtime_data._tick(dt_util.now())
        assert entry.runtime_data.data.result.total_kwh == Decimal("0.033")
        freezer.tick(timedelta(minutes=1))
        entry.runtime_data._tick(dt_util.now())
        assert entry.runtime_data.data.result is None
        assert (
            hass.states.get("sensor.casa_vivienda_precio_pvpc_sin_impuestos").state == "unavailable"
        )
        api.async_update_all = AsyncMock(return_value=published(date(2026, 10, 25)))
        await entry.runtime_data._async_refresh_pvpc(dt_util.now())
        assert entry.runtime_data.data.result.total_kwh == Decimal("0.050")
