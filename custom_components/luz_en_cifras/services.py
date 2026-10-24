"""Explicit history export, manual close and real-invoice reconciliation actions."""

from __future__ import annotations

from copy import deepcopy
from datetime import date
from decimal import Decimal, InvalidOperation

import probatio as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .coordinator import LuzEnCifrasCoordinator
from .domain.errors import BillingError


def register_services(hass: HomeAssistant) -> None:
    """Register once per HA instance; each action is scoped to one config entry."""
    if hass.services.has_service(DOMAIN, "export_history"):
        return

    def coordinator(call: ServiceCall) -> LuzEnCifrasCoordinator:
        entry = hass.config_entries.async_get_entry(call.data["entry_id"])
        if entry is None or entry.domain != DOMAIN or entry.state != ConfigEntryState.LOADED:
            raise HomeAssistantError("El contrato no existe o no está cargado")
        return entry.runtime_data

    async def export(call: ServiceCall) -> dict:
        return {"periods": deepcopy(coordinator(call).history)}

    async def compare(call: ServiceCall) -> dict:
        try:
            record = await coordinator(call).async_compare(
                call.data["record_id"],
                Decimal(str(call.data["real_total"])),
                Decimal(str(call.data["real_kwh"])),
            )
        except (ValueError, InvalidOperation, BillingError) as err:
            raise HomeAssistantError(str(err)) from err
        return {"id": record["id"], "comparison": record["comparison"]}

    async def close(call: ServiceCall) -> dict:
        try:
            record = await coordinator(call).async_archive_period(
                date.fromisoformat(call.data["start"]),
                date.fromisoformat(call.data["end"]),
                date.fromisoformat(call.data["tax_point"]),
                call.data["allow_boundary_estimate"],
            )
        except (ValueError, BillingError) as err:
            raise HomeAssistantError(str(err)) from err
        return {"id": record["id"], "result": record["result"]}

    async def recalculate(call: ServiceCall) -> dict:
        try:
            record = await coordinator(call).async_recalculate(
                call.data["record_id"],
                call.data["reason"],
                call.data["use_current_tax_profile"],
                date.fromisoformat(call.data["tax_point"]) if call.data.get("tax_point") else None,
            )
        except (ValueError, BillingError) as err:
            raise HomeAssistantError(str(err)) from err
        return {"id": record["id"], "supersedes": record["supersedes"], "result": record["result"]}

    hass.services.async_register(
        DOMAIN,
        "export_history",
        export,
        schema=vol.Schema({vol.Required("entry_id"): str}),
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        "record_invoice",
        compare,
        schema=vol.Schema(
            {
                vol.Required("entry_id"): str,
                vol.Required("record_id"): str,
                vol.Required("real_total"): vol.Coerce(str),
                vol.Required("real_kwh"): vol.Coerce(str),
            }
        ),
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        "archive_period",
        close,
        schema=vol.Schema(
            {
                vol.Required("entry_id"): str,
                vol.Required("start"): str,
                vol.Required("end"): str,
                vol.Required("tax_point"): str,
                vol.Required("allow_boundary_estimate", default=False): bool,
            }
        ),
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        "recalculate_period",
        recalculate,
        schema=vol.Schema(
            {
                vol.Required("entry_id"): str,
                vol.Required("record_id"): str,
                vol.Required("reason"): str,
                vol.Required("use_current_tax_profile", default=False): bool,
                vol.Optional("tax_point"): str,
            }
        ),
        supports_response=SupportsResponse.OPTIONAL,
    )
