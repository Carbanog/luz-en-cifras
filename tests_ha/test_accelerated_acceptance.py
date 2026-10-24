"""Move only the isolated test clock: 61 synthetic days, never the user's HA clock."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.luz_en_cifras.const import DOMAIN


@pytest.mark.parametrize("months", [1, 2])
async def test_sixty_one_days_close_and_restore_monthly_or_bimonthly_without_duplicates(
    hass, contract, freezer, months
):
    zone = ZoneInfo("Europe/Madrid")
    start, finish = datetime(2026, 9, 1, tzinfo=zone), datetime(2026, 11, 1, tzinfo=zone)
    freezer.move_to(start)
    contract.update(
        billing_months=str(months),
        billing_anchor_month=9,
        power_max_age_minutes=1440,
        invoice_fee="1",
        meter_rental_daily="0.03",
        power_p1_kw="3",
        power_p1_eur_per_kw_day="0.1",
    )
    contract["groups"][0]["add_sources"] = ["sensor.row1", "sensor.row2"]
    contract["groups"].append(
        {
            "group_id": "car",
            "group_name": "Coche",
            "add_sources": ["sensor.car"],
            "eur_per_kwh": "0.1",
        }
    )
    readings = {"sensor.row1": "600", "sensor.row2": "400", "sensor.car": "200"}
    for source, value in readings.items():
        hass.states.async_set(source, value, {"unit_of_measurement": "W"})
    entry = MockConfigEntry(domain=DOMAIN, data=contract, title="Synthetic acceptance", version=1)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    instant = start
    while instant < finish:
        instant += timedelta(hours=6)
        freezer.move_to(instant)
        for source, value in readings.items():
            hass.states.async_set(source, value, {"unit_of_measurement": "W"})
        entry.runtime_data._tick(instant)
        if instant == datetime(2026, 10, 10, 12, tzinfo=zone):
            before = entry.runtime_data.data.result.total_kwh
            await hass.config_entries.async_unload(entry.entry_id)
            assert await hass.config_entries.async_setup(entry.entry_id)
            assert entry.runtime_data.data.result.total_kwh == before
    history = entry.runtime_data.history
    assert len(history) == (2 if months == 1 else 1)
    for record in list(history):
        assert record["result"] is not None
        first = datetime.fromisoformat(record["period"]["start"]).replace(tzinfo=zone)
        last = datetime.fromisoformat(record["period"]["end"]).replace(tzinfo=zone)
        hours = Decimal(str((last.astimezone(UTC) - first.astimezone(UTC)).total_seconds())) / 3600
        assert Decimal(record["result"]["total_kwh"]) == hours * Decimal("1.2")
        lines = record["result"]["lines"]
        energy = sum(Decimal(line["amount"]) for line in lines if line["category"] == "energy")
        assert abs(energy - hours * Decimal("0.22")) < Decimal("1e-20")
        fixed = sum(Decimal(line["amount"]) for line in lines if line["category"] == "fixed")
        assert fixed == Decimal((last - first).days) * Decimal("0.03") + 1
        revised = await entry.runtime_data.async_recalculate(record["id"], "Synthetic audit", False)
        assert revised["result"]["total"] == record["result"]["total"]
        assert revised["result"]["total_kwh"] == record["result"]["total_kwh"]
    # November remains explicitly unsupported in automatic fiscal mode. Accelerating
    # the test is not permission to invent a tax rule or report acceptance there.
    assert entry.runtime_data.data.result is None
    assert entry.runtime_data.data.error
