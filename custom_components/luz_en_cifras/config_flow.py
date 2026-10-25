"""Native configuration flows with reusable contract and group forms."""

from __future__ import annotations

from copy import deepcopy
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import uuid4

import probatio as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.helpers.selector import (
    BooleanSelector,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
)

from .const import DOMAIN
from .domain.errors import BillingError
from .domain.fiscal import configured_rule


def number(minimum: float = 0, maximum: float = 10000, step: float = 0.000001) -> NumberSelector:
    return NumberSelector(
        NumberSelectorConfig(
            min=minimum,
            max=maximum,
            step="any" if step < 0.001 else step,
            mode=NumberSelectorMode.BOX,
        )
    )


def select(options: list[tuple[str, str]]) -> SelectSelector:
    return SelectSelector(
        SelectSelectorConfig(
            options=[SelectOptionDict(value=value, label=label) for value, label in options]
        )
    )


ENERGY = EntitySelector(EntitySelectorConfig(domain="sensor", multiple=True))
SENSOR = EntitySelector(EntitySelectorConfig(domain="sensor"))


def tariff_selector() -> SelectSelector:
    return select(
        [
            ("fixed", "Precio fijo: el mismo €/kWh a cualquier hora"),
            ("three_period", "Tres precios: punta, llano y valle"),
            ("pvpc", "PVPC directo de Red Eléctrica (Península/Baleares)"),
            ("entity", "Precio variable: PVPC o indexada desde un sensor"),
        ]
    )


def contract_schema(current: dict[str, Any]) -> vol.Schema:
    fields: dict[Any, Any] = {
        vol.Required("contract_name", default=current.get("contract_name", "Casa")): TextSelector(),
        vol.Required("billing_day", default=current.get("billing_day", 1)): number(1, 31, 1),
        vol.Required("billing_months", default=current.get("billing_months", 1)): select(
            [("1", "Mensual"), ("2", "Bimestral")]
        ),
    }
    return vol.Schema(fields)


def advanced_schema(current: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                "approximate_intervals", default=current.get("approximate_intervals", False)
            ): BooleanSelector(),
            vol.Required(
                "show_secondary_entities", default=current.get("show_secondary_entities", True)
            ): BooleanSelector(),
            vol.Required(
                "power_max_age_minutes", default=float(current.get("power_max_age_minutes", 5))
            ): number(1, 1440, 1),
        }
    )


def power_schema(current: dict[str, Any]) -> vol.Schema:
    fields: dict[Any, Any] = {}
    for key in (
        "power_p1_kw",
        "power_p2_kw",
        "power_p1_eur_per_kw_day",
        "power_p2_eur_per_kw_day",
        "meter_rental_daily",
    ):
        fields[
            vol.Required(key, **({"default": float(current[key])} if key in current else {}))
        ] = number()
    return vol.Schema(fields)


def group_schema(current: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required("group_name", default=current.get("group_name", "")): TextSelector(),
            vol.Required("add_sources", default=current.get("add_sources", [])): ENERGY,
            vol.Optional("subtract_sources", default=current.get("subtract_sources", [])): ENERGY,
            vol.Required(
                "tariff_mode", default=current.get("tariff_mode", "fixed")
            ): tariff_selector(),
            vol.Required("eur_per_kwh", default=float(current.get("eur_per_kwh", 0))): number(
                -100, 100
            ),
            vol.Required("p1_price", default=float(current.get("p1_price", 0))): number(-100, 100),
            vol.Required("p2_price", default=float(current.get("p2_price", 0))): number(-100, 100),
            vol.Required("p3_price", default=float(current.get("p3_price", 0))): number(-100, 100),
            vol.Optional(
                "price_entity",
                **({"default": current["price_entity"]} if current.get("price_entity") else {}),
            ): SENSOR,
            vol.Required("price_markup", default=float(current.get("price_markup", 0))): number(
                -100, 100
            ),
            vol.Required(
                "price_max_age_minutes", default=float(current.get("price_max_age_minutes", 65))
            ): number(1, 1440, 1),
        }
    )


def cleaned(values: dict[str, Any]) -> dict[str, Any]:
    return {
        key: int(value)
        if isinstance(value, float) and value.is_integer()
        else str(Decimal(str(value)))
        if isinstance(value, float)
        else value
        for key, value in values.items()
    }


class ContractForms:
    """Share forms between initial setup and options, preserving group identities."""

    _config: dict[str, Any]
    _editing: str | None = None
    _draft_group: dict[str, Any]
    _initial_setup = False

    async def async_step_modality(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self._config.update(cleaned(user_input))
            return await self.async_step_contract()
        return self.async_show_form(
            step_id="modality",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "default_tariff_mode",
                        default=self._config.get("default_tariff_mode", "fixed"),
                    ): tariff_selector(),
                }
            ),
        )

    async def _after_contract(self) -> ConfigFlowResult:
        return (
            await self.async_step_add_group()
            if self._initial_setup
            else await self.async_step_menu()
        )

    async def async_step_contract(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            if not user_input["contract_name"].strip():
                errors["base"] = "empty_name"
            elif not float(user_input["billing_day"]).is_integer():
                errors["billing_day"] = "whole_number"
            else:
                self._config.update(cleaned(user_input))
                self._config["contract_name"] = user_input["contract_name"].strip()
                if str(self._config.get("billing_months", "1")) == "2":
                    return await self.async_step_cycle_anchor()
                return await self._after_contract()
        return self.async_show_form(
            step_id="contract", data_schema=contract_schema(self._config), errors=errors
        )

    async def async_step_cycle_anchor(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            if float(user_input["billing_anchor_month"]).is_integer():
                self._config.update(cleaned(user_input))
                return await self._after_contract()
            errors["billing_anchor_month"] = "whole_number"
        return self.async_show_form(
            step_id="cycle_anchor",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "billing_anchor_month", default=self._config.get("billing_anchor_month", 1)
                    ): number(1, 12, 1),
                }
            ),
        )

    async def async_step_power_unit(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self._config.update(cleaned(user_input))
            return await self.async_step_power()
        return self.async_show_form(
            step_id="power_unit",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "power_price_unit", default=self._config.get("power_price_unit", "day")
                    ): select(
                        [
                            ("day", "Mi factura indica €/kW/día"),
                            ("year", "Mi contrato indica €/kW/año (divisor 365)"),
                        ]
                    ),
                }
            ),
        )

    async def async_step_power(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            self._config.update(cleaned(user_input))
            initial = self._initial_setup
            self._initial_setup = False
            if initial:
                return await self.async_step_fiscal()
            return await self.async_step_menu()
        return self.async_show_form(
            step_id="power",
            data_schema=power_schema(self._config),
            description_placeholders={
                "power_price_unit": "€/kW/año"
                if self._config.get("power_price_unit") == "year"
                else "€/kW/día"
            },
        )

    async def async_step_advanced(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self._config.update(cleaned(user_input))
            return await self.async_step_menu()
        return self.async_show_form(step_id="advanced", data_schema=advanced_schema(self._config))

    async def async_step_menu(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return self.async_show_menu(
            step_id="menu",
            menu_options=[
                "contract",
                "power_unit",
                "add_group",
                "select_group",
                "extras",
                "fiscal",
                "advanced",
                "finish",
            ],
        )

    async def async_step_add_group(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        self._editing = None
        return await self.async_step_group()

    async def async_step_select_group(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        groups = self._config.get("groups", [])
        if not groups:
            return await self.async_step_add_group()
        if user_input is not None:
            self._editing = user_input["group_id"]
            return await self.async_step_group()
        return self.async_show_form(
            step_id="select_group",
            data_schema=vol.Schema(
                {
                    vol.Required("group_id"): select(
                        [(group["group_id"], group["group_name"]) for group in groups]
                    ),
                }
            ),
        )

    async def async_step_group(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        groups = self._config.setdefault("groups", [])
        current = next(
            (group for group in groups if group["group_id"] == self._editing),
            {"tariff_mode": self._config.get("default_tariff_mode", "fixed")},
        )
        errors: dict[str, str] = {}
        if user_input is not None:
            if user_input.get("delete_group") and self._editing:
                groups[:] = [group for group in groups if group["group_id"] != self._editing]
                return await self.async_step_menu()
            additions = user_input["add_sources"]
            subtractions = user_input.get("subtract_sources", [])
            if not user_input["group_name"].strip() or not additions:
                errors["base"] = "empty_group"
            elif set(additions) & set(subtractions):
                errors["base"] = "source_overlap"
            elif any(
                (state := self.hass.states.get(source)) is None
                or state.attributes.get("unit_of_measurement") not in {"Wh", "kWh", "W", "kW"}
                for source in (*additions, *subtractions)
            ):
                errors["base"] = "invalid_units"
            else:
                self._draft_group = {
                    **current,
                    **cleaned(user_input),
                    "group_id": self._editing or uuid4().hex,
                }
                self._draft_group["group_name"] = self._draft_group["group_name"].strip()
                return await self.async_step_tariff()
        schema = vol.Schema(
            {
                key: value
                for key, value in group_schema(current).schema.items()
                if str(key) in {"group_name", "add_sources", "subtract_sources", "tariff_mode"}
            }
        )
        if self._editing:
            schema = schema.extend({vol.Optional("delete_group", default=False): BooleanSelector()})
        return self.async_show_form(step_id="group", data_schema=schema, errors=errors)

    async def async_step_tariff(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        mode = self._draft_group["tariff_mode"]
        errors: dict[str, str] = {}
        if user_input is not None:
            if mode == "entity" and not user_input.get("price_entity"):
                errors["base"] = "missing_price_entity"
            elif mode == "entity" and (
                (state := self.hass.states.get(user_input["price_entity"])) is None
                or state.attributes.get("unit_of_measurement")
                not in {"€/kWh", "EUR/kWh", "€/MWh", "EUR/MWh"}
            ):
                errors["base"] = "invalid_price_units"
            else:
                self._draft_group.update(cleaned(user_input))
                groups = self._config["groups"]
                groups[:] = [group for group in groups if group["group_id"] != self._editing]
                groups.append(self._draft_group)
                if self._initial_setup:
                    return await self.async_step_power_unit()
                return await self.async_step_menu()
        keys = (
            {"eur_per_kwh"}
            if mode == "fixed"
            else {"p1_price", "p2_price", "p3_price"}
            if mode == "three_period"
            else set()
            if mode == "pvpc"
            else {"price_entity", "price_markup", "price_max_age_minutes"}
        )
        schema = vol.Schema(
            {
                key: value
                for key, value in group_schema(self._draft_group).schema.items()
                if str(key) in keys
            }
        )
        return self.async_show_form(step_id="tariff", data_schema=schema, errors=errors)

    async def async_step_extras(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            self._config.update(cleaned(user_input))
            return await self.async_step_menu()
        fields: dict[Any, Any] = {}
        fields[
            vol.Required(
                "fees_tax_percent", default=float(self._config.get("fees_tax_percent", 21))
            )
        ] = number(0, 100)
        for key in ("daily_fee", "invoice_fee", "energy_discount_percent"):
            fields[vol.Required(key, default=float(self._config.get(key, 0)))] = number(
                0, 100 if key.endswith("percent") else 10000
            )
        fields[
            vol.Required("enable_surplus", default=self._config.get("enable_surplus", False))
        ] = BooleanSelector()
        fields[
            vol.Optional(
                "export_source",
                **(
                    {"default": self._config["export_source"]}
                    if self._config.get("export_source")
                    else {}
                ),
            )
        ] = SENSOR
        fields[
            vol.Required("surplus_price", default=float(self._config.get("surplus_price", 0)))
        ] = number()
        fields[
            vol.Required(
                "daily_fee_electricity_taxable",
                default=self._config.get("daily_fee_electricity_taxable", False),
            )
        ] = BooleanSelector()
        return self.async_show_form(step_id="extras", data_schema=vol.Schema(fields))

    async def async_step_finish(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return await self.async_step_menu()
        if self._config.get("fiscal_mode") == "contract":
            try:
                configured_rule(self._config, date.today())
            except BillingError, ValueError, KeyError:
                return await self.async_step_fiscal()
        groups = self._config.get("groups", [])
        coefficients: dict[str, int] = {}
        for group in groups:
            for source in group["add_sources"]:
                coefficients[source] = coefficients.get(source, 0) + 1
            for source in group.get("subtract_sources", []):
                coefficients[source] = coefficients.get(source, 0) - 1
        error = (
            "missing_groups"
            if not groups
            else (
                "duplicate_sources" if any(value > 1 for value in coefficients.values()) else None
            )
        )
        if self._config.get("enable_surplus"):
            source = self._config.get("export_source")
            state = self.hass.states.get(source) if source else None
            if (
                not state
                or state.attributes.get("unit_of_measurement") not in {"Wh", "kWh", "W", "kW"}
                or source in coefficients
                or int(self._config.get("billing_months", 1)) != 1
            ):
                error = "invalid_surplus"
        if error:
            return self.async_show_form(
                step_id="finish", errors={"base": error}, data_schema=vol.Schema({})
            )
        return self.async_create_entry(title=self._config["contract_name"], data=self._config)

    async def async_step_fiscal(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            candidate = {**self._config, **cleaned(user_input), "fiscal_mode": "contract"}
            try:
                configured_rule(candidate, date.today())
            except BillingError, ValueError, KeyError:
                errors["base"] = "invalid_tax_profile"
            else:
                self._config = candidate
                return await self.async_step_menu()
        fields: dict[Any, Any] = {}
        for key, suggested in (
            ("tax_electricity_percent", 5.11269632),
            ("tax_indirect_percent", 21),
            ("tax_minimum_eur_mwh", 1),
        ):
            fields[vol.Required(key, default=float(self._config.get(key, suggested)))] = number(
                0, 100
            )
        fields[
            vol.Required(
                "tax_rules_confirmed", default=self._config.get("tax_rules_confirmed", False)
            )
        ] = BooleanSelector()
        return self.async_show_form(step_id="fiscal", data_schema=vol.Schema(fields), errors=errors)


class LuzEnCifrasConfigFlow(ContractForms, ConfigFlow, domain=DOMAIN):
    """Create an independently identified electricity contract."""

    VERSION = 1
    MINOR_VERSION = 4

    def __init__(self) -> None:
        self._config = {
            "contract_id": uuid4().hex,
            "groups": [],
            "billing_months": "1",
            "fiscal_mode": "contract",
        }
        self._initial_setup = True

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return await self.async_step_modality(user_input)

    @staticmethod
    def async_get_options_flow(config_entry: Any) -> LuzEnCifrasOptionsFlow:
        return LuzEnCifrasOptionsFlow(config_entry)


class LuzEnCifrasOptionsFlow(ContractForms, OptionsFlow):
    """Edit with readable group names, keeping contract and entity unique IDs."""

    def __init__(self, config_entry: Any) -> None:
        self._config = deepcopy({**config_entry.data, **config_entry.options})
        self._config["billing_months"] = str(self._config.get("billing_months", "1"))

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return await self.async_step_menu()
