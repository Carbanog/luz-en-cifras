"""Sensor entities for Luz en Cifras contracts."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CURRENCY_EURO, EntityCategory, UnitOfEnergy, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import CONF_CONTRACT_ID, CONF_CONTRACT_NAME, CONF_SHOW_SECONDARY, DOMAIN
from .coordinator import CoordinatorData, LuzEnCifrasCoordinator
from .domain import DataQuality, InvoiceResult


@dataclass(frozen=True, kw_only=True)
class LuzSensorDescription(SensorEntityDescription):
    """Describe how a contract result maps to a sensor."""

    value_fn: Callable[[InvoiceResult], Decimal | int | str | None]
    primary: bool = False


SENSORS: tuple[LuzSensorDescription, ...] = (
    LuzSensorDescription(
        key="estimated_total",
        name="Factura actual estimada",
        translation_key="estimated_total",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=CURRENCY_EURO,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=2,
        value_fn=lambda result: result.total,
        primary=True,
    ),
    LuzSensorDescription(
        key="energy_cost",
        name="Coste de energía",
        translation_key="energy_cost",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=CURRENCY_EURO,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=2,
        value_fn=lambda result: result.amount_for("energy"),
    ),
    LuzSensorDescription(
        key="power_cost",
        name="Coste de potencia",
        translation_key="power_cost",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=CURRENCY_EURO,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=2,
        value_fn=lambda result: result.amount_for("power"),
    ),
    LuzSensorDescription(
        key="electricity_tax",
        name="Impuesto eléctrico",
        translation_key="electricity_tax",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=CURRENCY_EURO,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=2,
        value_fn=lambda result: result.amount_for("electricity_tax"),
    ),
    LuzSensorDescription(
        key="vat",
        name="IVA",
        translation_key="vat",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=CURRENCY_EURO,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=2,
        value_fn=lambda result: result.amount_for("vat"),
    ),
    LuzSensorDescription(
        key="other_charges",
        name="Otros cargos",
        translation_key="other_charges",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=CURRENCY_EURO,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=2,
        value_fn=lambda result: result.amount_for("fixed"),
    ),
    LuzSensorDescription(
        key="discounts",
        name="Descuentos",
        translation_key="discounts",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=CURRENCY_EURO,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=2,
        value_fn=lambda result: result.amount_for("discount"),
    ),
    LuzSensorDescription(
        key="surplus_compensation",
        name="Compensación de excedentes",
        translation_key="surplus_compensation",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=CURRENCY_EURO,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=2,
        value_fn=lambda result: result.amount_for("compensation"),
    ),
    LuzSensorDescription(
        key="period_energy",
        name="Energía del periodo",
        translation_key="period_energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=3,
        value_fn=lambda result: result.total_kwh,
    ),
    LuzSensorDescription(
        key="billing_days",
        name="Días del periodo",
        translation_key="billing_days",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.DAYS,
        value_fn=lambda result: result.period.days,
    ),
    LuzSensorDescription(
        key="effective_price",
        name="Precio medio efectivo",
        translation_key="effective_price",
        native_unit_of_measurement="€/kWh",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=4,
        value_fn=lambda result: result.total / result.total_kwh if result.total_kwh else None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create stable entities for one logical contract device."""
    coordinator: LuzEnCifrasCoordinator = entry.runtime_data
    show_secondary = coordinator.config.get(CONF_SHOW_SECONDARY, True)
    descriptions = [description for description in SENSORS if show_secondary or description.primary]
    entities: list[SensorEntity] = [
        LuzContractSensor(coordinator, description) for description in descriptions
    ]
    entities.append(LuzQualitySensor(coordinator))
    if show_secondary:
        entities.extend(
            LuzGroupSensor(coordinator, group, metric)
            for group in coordinator.config["groups"]
            for metric in ("energy", "cost")
        )
        entities.extend(
            LuzPvpcPriceSensor(coordinator, group)
            for group in coordinator.config["groups"]
            if group.get("tariff_mode") == "pvpc"
        )
    async_add_entities(entities)


class LuzBaseSensor(CoordinatorEntity[LuzEnCifrasCoordinator], SensorEntity):
    """Common stable identity and device mapping."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: LuzEnCifrasCoordinator, key: str) -> None:
        super().__init__(coordinator)
        contract_id = coordinator.config[CONF_CONTRACT_ID]
        self._attr_unique_id = f"{contract_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, contract_id)},
            name=coordinator.config[CONF_CONTRACT_NAME],
            manufacturer="Luz en Cifras",
            model="Contrato eléctrico estimado",
        )

    @property
    def last_reset(self) -> datetime | None:
        """Identify cycle/segment resets without using total_increasing for corrections."""
        if self.state_class != SensorStateClass.TOTAL:
            return None
        intervals = self.coordinator.ledger.intervals
        if intervals:
            return min(
                (interval.start for interval in intervals),
                key=lambda instant: instant.astimezone(UTC),
            )
        period = self.coordinator.billing_period
        return (
            datetime.combine(period.start, datetime.min.time(), ZoneInfo("Europe/Madrid"))
            if period
            else None
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data: CoordinatorData = self.coordinator.data
        attributes: dict[str, Any] = {
            "estimate": True,
            "data_quality": self._quality,
        }
        period = self.coordinator.billing_period
        if period:
            attributes["scheduled_period_end_exclusive"] = period.end.isoformat()
        attributes["closed_period_count"] = len(self.coordinator.history)
        if self.coordinator.history:
            previous = self.coordinator.history[-1].get("result")
            if previous:
                attributes["previous_period_total"] = previous["total"]
        if data.error:
            attributes["error"] = data.error
        if data.collection_warnings:
            attributes["warnings"] = list(data.collection_warnings)
        if data.result:
            attributes.update(
                {
                    "period_start": data.result.period.start.isoformat(),
                    "period_end_exclusive": data.result.period.end.isoformat(),
                    "tax_point": data.result.tax_point.isoformat(),
                    "fiscal_rule_id": data.result.fiscal_rule_id,
                }
            )
        return attributes

    @property
    def _quality(self) -> str:
        data: CoordinatorData = self.coordinator.data
        if data.result is None:
            return "error"
        if data.collection_warnings or data.result.quality == DataQuality.PARTIAL:
            return "partial"
        return "complete"


class LuzContractSensor(LuzBaseSensor):
    """A numeric value from the latest invoice estimate."""

    entity_description: LuzSensorDescription

    def __init__(
        self, coordinator: LuzEnCifrasCoordinator, description: LuzSensorDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def available(self) -> bool:
        return self.coordinator.data.result is not None

    @property
    def native_value(self) -> Decimal | int | str | None:
        result = self.coordinator.data.result
        return self.entity_description.value_fn(result) if result else None


class LuzQualitySensor(LuzBaseSensor):
    """Diagnostic sensor that remains available when the estimate cannot be calculated."""

    _attr_translation_key = "data_quality"
    _attr_name = "Calidad de los datos"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = SensorDeviceClass.ENUM

    def __init__(self, coordinator: LuzEnCifrasCoordinator) -> None:
        super().__init__(coordinator, "data_quality")
        self._attr_options = ["complete", "partial", "error"]

    @property
    def native_value(self) -> str:
        return self._quality


class LuzGroupSensor(LuzBaseSensor):
    """Expose each configured group's measured energy and pre-tax energy cost."""

    def __init__(
        self, coordinator: LuzEnCifrasCoordinator, group: dict[str, Any], metric: str
    ) -> None:
        super().__init__(coordinator, f"group_{group['group_id']}_{metric}")
        self.group_id = group["group_id"]
        self.metric = metric
        self._attr_name = (
            f"{group['group_name']} — {'energía' if metric == 'energy' else 'coste de energía'}"
        )
        self._attr_native_unit_of_measurement = (
            UnitOfEnergy.KILO_WATT_HOUR if metric == "energy" else CURRENCY_EURO
        )
        self._attr_device_class = (
            SensorDeviceClass.ENERGY if metric == "energy" else SensorDeviceClass.MONETARY
        )
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_suggested_display_precision = 3 if metric == "energy" else 2

    @property
    def available(self) -> bool:
        return self.coordinator.data.result is not None

    @property
    def native_value(self) -> Decimal | None:
        result = self.coordinator.data.result
        if not result:
            return None
        lines = [
            line
            for line in result.lines
            if line.category == "energy" and line.metadata.get("group_id") == self.group_id
        ]
        if not lines:
            return None
        return sum(
            (
                (line.quantity or Decimal()) if self.metric == "energy" else line.amount
                for line in lines
            ),
            Decimal(),
        )


class LuzPvpcPriceSensor(LuzBaseSensor):
    """Show the published current-hour FEU even before a consumption interval exists."""

    _attr_native_unit_of_measurement = "€/kWh"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 5

    def __init__(self, coordinator: LuzEnCifrasCoordinator, group: dict[str, Any]) -> None:
        super().__init__(coordinator, f"group_{group['group_id']}_pvpc_price")
        self.group_id = group["group_id"]
        self._attr_name = f"{group['group_name']} — precio PVPC sin impuestos"

    @property
    def available(self) -> bool:
        return self.native_value is not None

    @property
    def native_value(self) -> Decimal | None:
        now = dt_util.utcnow()
        matches = [
            rate
            for rate in self.coordinator.ledger.rates
            if rate.group_id == self.group_id
            and rate.rate_id.startswith("pvpc:")
            and rate.valid_from.astimezone(UTC) <= now
            and rate.valid_to is not None
            and now < rate.valid_to.astimezone(UTC)
        ]
        return matches[0].eur_per_kwh if len(matches) == 1 else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "attribution": "Red Eléctrica / ESIOS",
            "price_term": "FEU",
            "taxes_included": False,
        }
