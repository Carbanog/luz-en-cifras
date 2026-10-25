"""Minimal diagnostics without entity IDs, readings or user-provided names."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict:
    coordinator = entry.runtime_data
    return {
        "version": "0.3.1",
        "storage_schema": 3,
        "group_count": len(coordinator.config["groups"]),
        "tariff_modes": [
            group.get("tariff_mode", "fixed") for group in coordinator.config["groups"]
        ],
        "measured_intervals": len(coordinator.ledger.intervals),
        "price_intervals": len(coordinator.ledger.rates),
        "closed_periods": len(coordinator.history),
        "result_available": coordinator.data.result is not None,
        "warning_count": len(coordinator.ledger.warnings),
        "direct_pvpc_enabled": coordinator._pvpc is not None,
        "direct_pvpc_warning": bool(coordinator._pvpc and coordinator._pvpc.warning),
    }
