"""Luz en Cifras Home Assistant integration.

The billing domain deliberately has no Home Assistant imports, so it can be tested
and reused without starting Home Assistant.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
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
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.async_shutdown()
    return unloaded


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload after an options change so subscriptions match the new config."""
    await entry.runtime_data.async_prepare_reload()
    await hass.config_entries.async_reload(entry.entry_id)


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove persisted measurements only when the user deletes the contract."""
    from homeassistant.helpers.storage import Store

    from .const import DOMAIN, STORAGE_VERSION

    await Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}").async_remove()


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Upgrade configuration additively; the coordinator retains the original v1 store."""
    if entry.version != 1 or entry.minor_version > 4:
        return False
    data = {
        "billing_months": "1",
        "power_price_unit": "day",
        "approximate_intervals": False,
        **entry.data,
    }
    options = dict(entry.options)
    effective = {**data, **options}
    if effective.get("fiscal_mode", "automatic") == "automatic":
        from datetime import date

        from .domain.fiscal import configured_rule

        # Carry forward the currently applicable values as suggestions, never as
        # a user confirmation. Retain the original Store and closed invoices.
        suggested = ("5.11269632", "21", "1")
        try:
            rule = configured_rule(effective, date.today())
            suggested = (
                str(rule.electricity_tax_rate * 100),
                str(rule.vat_rate * 100),
                str(rule.minimum_electricity_eur_per_mwh),
            )
        except ValueError:
            pass  # Explicit confirmation is required even when no old rule is available.
        target = options if options else data
        target.update(
            fiscal_mode="contract",
            tax_electricity_percent=suggested[0],
            tax_indirect_percent=suggested[1],
            tax_minimum_eur_mwh=suggested[2],
            tax_rules_confirmed=False,
        )
    # Older numeric selectors stored whole days as strings like "1.0".
    # Normalize only exact whole values; never truncate an invalid billing date.
    for values in (data, options):
        for key in ("billing_day", "billing_anchor_month"):
            if key not in values:
                continue
            try:
                number = Decimal(str(values[key]))
                if not number.is_finite() or number != number.to_integral_value():
                    return False
                values[key] = int(number)
            except InvalidOperation:
                return False
    hass.config_entries.async_update_entry(
        entry, data=data, options=options, version=1, minor_version=4
    )
    return True
