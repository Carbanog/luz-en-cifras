"""Luz en Cifras Home Assistant integration.

The billing domain deliberately has no Home Assistant imports, so it can be tested
and reused without starting Home Assistant.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

PLATFORMS = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Luz en Cifras from a config entry."""
    from .coordinator import LuzEnCifrasCoordinator
    from .services import register_services

    coordinator = LuzEnCifrasCoordinator(hass, entry)
    await coordinator.async_initialize()
    entry.runtime_data = coordinator
    register_services(hass)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Luz en Cifras config entry."""
    await entry.runtime_data.async_persist()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload after an options change so subscriptions match the new config."""
    await entry.runtime_data.async_persist()
    await hass.config_entries.async_reload(entry.entry_id)


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove persisted measurements only when the user deletes the contract."""
    from homeassistant.helpers.storage import Store

    from .const import DOMAIN, STORAGE_VERSION

    await Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}").async_remove()


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Upgrade configuration additively; the coordinator retains the original v1 store."""
    if entry.version != 1:
        return False
    data = {
        "billing_months": "1",
        "power_price_unit": "day",
        "approximate_intervals": False,
        **entry.data,
    }
    hass.config_entries.async_update_entry(entry, data=data, version=1, minor_version=2)
    return True
