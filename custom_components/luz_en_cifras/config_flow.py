"""Config and options flows for Luz en Cifras."""

from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
from typing import Any
from uuid import uuid4

import voluptuous as vol
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import Platform
from homeassistant.helpers.selector import (
    BooleanSelector,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
)

from .const import (
    CONF_ADD_SOURCES,
    CONF_BILLING_DAY,
    CONF_CONTRACT_ID,
    CONF_CONTRACT_NAME,
    CONF_EUR_PER_KWH,
    CONF_GROUP_ID,
    CONF_GROUP_NAME,
    CONF_GROUPS,
    CONF_METER_RENTAL_DAILY,
    CONF_POWER_P1_KW,
    CONF_POWER_P1_PRICE,
    CONF_POWER_P2_KW,
    CONF_POWER_P2_PRICE,
    CONF_SHOW_SECONDARY,
    CONF_SUBTRACT_SOURCES,
    DOMAIN,
)


def _number(minimum: float, maximum: float, step: float) -> NumberSelector:
    return NumberSelector(
        NumberSelectorConfig(
            min=minimum,
            max=maximum,
            step=step,
            mode=NumberSelectorMode.BOX,
        )
    )


ENERGY_ENTITIES = EntitySelector(
    EntitySelectorConfig(
        domain=Platform.SENSOR,
        device_class=SensorDeviceClass.ENERGY,
        multiple=True,
    )
)


class LuzEnCifrasConfigFlow(ConfigFlow, domain=DOMAIN):
    """Create one electricity contract and one or more billing groups."""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        self._contract: dict[str, Any] = {}
        self._groups: list[dict[str, Any]] = []

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Collect contract-wide values."""
        if user_input is not None:
            self._contract = {
                CONF_CONTRACT_ID: uuid4().hex,
                CONF_CONTRACT_NAME: user_input[CONF_CONTRACT_NAME].strip(),
                CONF_BILLING_DAY: int(user_input[CONF_BILLING_DAY]),
                CONF_POWER_P1_KW: str(Decimal(str(user_input[CONF_POWER_P1_KW]))),
                CONF_POWER_P1_PRICE: str(Decimal(str(user_input[CONF_POWER_P1_PRICE]))),
                CONF_POWER_P2_KW: str(Decimal(str(user_input[CONF_POWER_P2_KW]))),
                CONF_POWER_P2_PRICE: str(Decimal(str(user_input[CONF_POWER_P2_PRICE]))),
                CONF_METER_RENTAL_DAILY: str(Decimal(str(user_input[CONF_METER_RENTAL_DAILY]))),
            }
            return await self.async_step_group()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_CONTRACT_NAME): TextSelector(),
                    vol.Required(CONF_BILLING_DAY, default=1): _number(1, 31, 1),
                    vol.Required(CONF_POWER_P1_KW, default=0): _number(0, 100, 0.1),
                    vol.Required(CONF_POWER_P1_PRICE, default=0): _number(0, 10, 0.000001),
                    vol.Required(CONF_POWER_P2_KW, default=0): _number(0, 100, 0.1),
                    vol.Required(CONF_POWER_P2_PRICE, default=0): _number(0, 10, 0.000001),
                    vol.Required(CONF_METER_RENTAL_DAILY, default=0): _number(0, 10, 0.000001),
                }
            ),
        )

    async def async_step_group(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Add a source expression with its own fixed price."""
        errors: dict[str, str] = {}
        if user_input is not None:
            additions = list(user_input[CONF_ADD_SOURCES])
            subtractions = list(user_input.get(CONF_SUBTRACT_SOURCES, []))
            if set(additions) & set(subtractions):
                errors["base"] = "source_overlap"
            elif invalid := self._invalid_units(set(additions) | set(subtractions)):
                errors["base"] = "invalid_units"
                self.context["invalid_entities"] = ", ".join(sorted(invalid))
            else:
                self._groups.append(
                    {
                        CONF_GROUP_ID: uuid4().hex,
                        CONF_GROUP_NAME: user_input[CONF_GROUP_NAME].strip(),
                        CONF_ADD_SOURCES: additions,
                        CONF_SUBTRACT_SOURCES: subtractions,
                        CONF_EUR_PER_KWH: str(Decimal(str(user_input[CONF_EUR_PER_KWH]))),
                    }
                )
                return await self.async_step_group_menu()

        return self.async_show_form(
            step_id="group",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_GROUP_NAME): TextSelector(),
                    vol.Required(CONF_ADD_SOURCES): ENERGY_ENTITIES,
                    vol.Optional(CONF_SUBTRACT_SOURCES, default=[]): ENERGY_ENTITIES,
                    vol.Required(CONF_EUR_PER_KWH): _number(-10, 10, 0.000001),
                }
            ),
            errors=errors,
            description_placeholders={"invalid_entities": self.context.get("invalid_entities", "")},
        )

    async def async_step_group_menu(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user add any number of groups without YAML."""
        return self.async_show_menu(step_id="group_menu", menu_options=["add_group", "finish"])

    async def async_step_add_group(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Start another group form."""
        return await self.async_step_group()

    async def async_step_finish(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Create the config entry after topology-level duplicate validation."""
        coefficients: dict[str, int] = {}
        for group in self._groups:
            for entity_id in group[CONF_ADD_SOURCES]:
                coefficients[entity_id] = coefficients.get(entity_id, 0) + 1
            for entity_id in group[CONF_SUBTRACT_SOURCES]:
                coefficients[entity_id] = coefficients.get(entity_id, 0) - 1
        duplicates = sorted(
            source for source, coefficient in coefficients.items() if coefficient > 1
        )
        if duplicates:
            return self.async_abort(
                reason="duplicate_sources",
                description_placeholders={"entities": ", ".join(duplicates)},
            )
        await self.async_set_unique_id(self._contract[CONF_CONTRACT_ID])
        self._abort_if_unique_id_configured()
        data = {**self._contract, CONF_GROUPS: self._groups}
        return self.async_create_entry(title=self._contract[CONF_CONTRACT_NAME], data=data)

    def _invalid_units(self, entity_ids: set[str]) -> set[str]:
        invalid: set[str] = set()
        for entity_id in entity_ids:
            state = self.hass.states.get(entity_id)
            if state is not None and state.attributes.get("unit_of_measurement") not in {
                "Wh",
                "kWh",
            }:
                invalid.add(entity_id)
        return invalid

    @staticmethod
    def async_get_options_flow(config_entry: Any) -> LuzEnCifrasOptionsFlow:
        return LuzEnCifrasOptionsFlow(config_entry)


class LuzEnCifrasOptionsFlow(OptionsFlow):
    """Edit contract prices and presentation without deleting history."""

    def __init__(self, config_entry: Any) -> None:
        self._entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        current = {**self._entry.data, **self._entry.options}
        groups = deepcopy(current[CONF_GROUPS])
        if user_input is not None:
            for group in groups:
                group[CONF_EUR_PER_KWH] = str(
                    Decimal(str(user_input[f"price_{group[CONF_GROUP_ID]}"]))
                )
            return self.async_create_entry(
                data={
                    CONF_BILLING_DAY: int(user_input[CONF_BILLING_DAY]),
                    CONF_POWER_P1_KW: str(Decimal(str(user_input[CONF_POWER_P1_KW]))),
                    CONF_POWER_P1_PRICE: str(Decimal(str(user_input[CONF_POWER_P1_PRICE]))),
                    CONF_POWER_P2_KW: str(Decimal(str(user_input[CONF_POWER_P2_KW]))),
                    CONF_POWER_P2_PRICE: str(Decimal(str(user_input[CONF_POWER_P2_PRICE]))),
                    CONF_METER_RENTAL_DAILY: str(Decimal(str(user_input[CONF_METER_RENTAL_DAILY]))),
                    CONF_SHOW_SECONDARY: bool(user_input[CONF_SHOW_SECONDARY]),
                    CONF_GROUPS: groups,
                }
            )

        schema: dict[vol.Marker, Any] = {
            vol.Required(CONF_BILLING_DAY, default=current[CONF_BILLING_DAY]): _number(1, 31, 1),
            vol.Required(CONF_POWER_P1_KW, default=float(current[CONF_POWER_P1_KW])): _number(
                0, 100, 0.1
            ),
            vol.Required(CONF_POWER_P1_PRICE, default=float(current[CONF_POWER_P1_PRICE])): _number(
                0, 10, 0.000001
            ),
            vol.Required(CONF_POWER_P2_KW, default=float(current[CONF_POWER_P2_KW])): _number(
                0, 100, 0.1
            ),
            vol.Required(CONF_POWER_P2_PRICE, default=float(current[CONF_POWER_P2_PRICE])): _number(
                0, 10, 0.000001
            ),
            vol.Required(
                CONF_METER_RENTAL_DAILY, default=float(current[CONF_METER_RENTAL_DAILY])
            ): _number(0, 10, 0.000001),
            vol.Required(
                CONF_SHOW_SECONDARY, default=current.get(CONF_SHOW_SECONDARY, True)
            ): BooleanSelector(),
        }
        for group in groups:
            schema[
                vol.Required(
                    f"price_{group[CONF_GROUP_ID]}",
                    default=float(group[CONF_EUR_PER_KWH]),
                    description={"suggested_value": float(group[CONF_EUR_PER_KWH])},
                )
            ] = _number(-10, 10, 0.000001)
        return self.async_show_form(step_id="init", data_schema=vol.Schema(schema))
