"""Event-driven accumulation and invoice coordination."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    CONF_ADD_SOURCES,
    CONF_BILLING_DAY,
    CONF_CONTRACT_ID,
    CONF_EUR_PER_KWH,
    CONF_GROUP_ID,
    CONF_GROUP_NAME,
    CONF_GROUPS,
    CONF_METER_RENTAL_DAILY,
    CONF_POWER_P1_KW,
    CONF_POWER_P1_PRICE,
    CONF_POWER_P2_KW,
    CONF_POWER_P2_PRICE,
    CONF_SUBTRACT_SOURCES,
    DOMAIN,
    STORAGE_VERSION,
)
from .domain import (
    SPAIN_MAINLAND_2026,
    BillingEngine,
    BillingFrequency,
    BillingPeriod,
    ConsumptionGroup,
    EnergyRate,
    EnergySample,
    FixedCharge,
    InvoiceInput,
    InvoiceResult,
    PowerCharge,
    find_fiscal_rule,
)
from .domain.errors import BillingError

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class CoordinatorData:
    """Latest trustworthy result, or an explicit reason it is unavailable."""

    result: InvoiceResult | None
    error: str | None
    collection_warnings: tuple[str, ...] = ()


class LuzEnCifrasCoordinator(DataUpdateCoordinator[CoordinatorData]):
    """Accumulate deltas from energy counters without querying Recorder repeatedly."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, _LOGGER, config_entry=entry, name=DOMAIN)
        self.entry = entry
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}"
        )
        self._baselines: dict[str, Decimal] = {}
        self._samples: list[EnergySample] = []
        self._collection_warnings: set[str] = set()
        self._period: BillingPeriod | None = None

    @property
    def config(self) -> dict[str, Any]:
        """Return config-entry data with options as explicit overrides."""
        return {**self.entry.data, **self.entry.options}

    @property
    def source_ids(self) -> set[str]:
        """Return every configured entity used by a group expression."""
        sources: set[str] = set()
        for group in self.config[CONF_GROUPS]:
            sources.update(group[CONF_ADD_SOURCES])
            sources.update(group.get(CONF_SUBTRACT_SOURCES, []))
        return sources

    async def async_initialize(self) -> None:
        """Load persisted state, establish baselines, and start listening."""
        stored = await self._store.async_load() or {}
        self._restore(stored)
        self._roll_period_if_needed(dt_util.now().date())
        self._establish_missing_baselines()
        self.data = self._calculate()
        self.entry.async_on_unload(
            async_track_state_change_event(
                self.hass,
                list(self.source_ids),
                self._handle_state_event,
            )
        )

    async def _async_update_data(self) -> CoordinatorData:
        return self._calculate()

    @callback
    def _handle_state_event(self, event: Event) -> None:
        entity_id = event.data["entity_id"]
        new_state: State | None = event.data.get("new_state")
        if new_state is None:
            self._collection_warnings.add(f"{entity_id}: entidad eliminada")
            self.async_set_updated_data(self._calculate())
            return

        now = dt_util.now()
        self._roll_period_if_needed(now.date())
        reading = self._reading_kwh(new_state)
        if reading is None:
            self._collection_warnings.add(f"{entity_id}: lectura no disponible o no válida")
            self.async_set_updated_data(self._calculate())
            return

        previous = self._baselines.get(entity_id)
        self._baselines[entity_id] = reading
        if previous is None:
            self._collection_warnings.add(
                f"{entity_id}: falta la lectura inicial del periodo; la estimación es parcial"
            )
        else:
            if reading >= previous:
                delta = reading - previous
            else:
                delta = reading
                self._collection_warnings.add(
                    f"{entity_id}: reinicio o corrección del contador detectado"
                )
            if delta:
                self._samples.append(
                    EnergySample(
                        source_id=entity_id,
                        timestamp=now,
                        kwh=delta,
                        complete=not self._collection_warnings,
                    )
                )

        self._store.async_delay_save(self._serialize, 60)
        self.async_set_updated_data(self._calculate())

    def _establish_missing_baselines(self) -> None:
        sampled_sources = {sample.source_id for sample in self._samples}
        now = dt_util.now()
        for entity_id in self.source_ids:
            if entity_id in self._baselines:
                continue
            state = self.hass.states.get(entity_id)
            reading = self._reading_kwh(state) if state else None
            if reading is not None:
                self._baselines[entity_id] = reading
                if entity_id not in sampled_sources:
                    # A zero marker lets the engine produce an explicitly partial
                    # estimate from now onward instead of pretending prior usage was zero.
                    self._samples.append(EnergySample(entity_id, now, Decimal(), complete=False))
            self._collection_warnings.add(
                f"{entity_id}: seguimiento iniciado sin histórico anterior"
            )
        self._store.async_delay_save(self._serialize, 60)

    @staticmethod
    def _reading_kwh(state: State) -> Decimal | None:
        if state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            return None
        try:
            reading = Decimal(state.state)
        except InvalidOperation:
            return None
        unit = state.attributes.get("unit_of_measurement")
        if unit == "Wh":
            reading /= Decimal("1000")
        elif unit != "kWh":
            return None
        return reading if reading >= 0 else None

    def _roll_period_if_needed(self, today: date) -> None:
        period = self._current_period(today, int(self.config[CONF_BILLING_DAY]))
        if self._period == period:
            return
        if self._period is not None:
            self._collection_warnings.add(
                "El cierre histórico aún no está implementado; se ha iniciado el nuevo periodo"
            )
        self._period = period
        self._samples.clear()

    @staticmethod
    def _current_period(today: date, billing_day: int) -> BillingPeriod:
        def safe_date(year: int, month: int, day: int) -> date:
            next_month = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
            last_day = (next_month - timedelta(days=1)).day
            return date(year, month, min(day, last_day))

        this_month = safe_date(today.year, today.month, billing_day)
        if today >= this_month:
            start = this_month
            if today.month == 12:
                end = safe_date(today.year + 1, 1, billing_day)
            else:
                end = safe_date(today.year, today.month + 1, billing_day)
        else:
            end = this_month
            if today.month == 1:
                start = safe_date(today.year - 1, 12, billing_day)
            else:
                start = safe_date(today.year, today.month - 1, billing_day)
        return BillingPeriod(start, end)

    def _calculate(self) -> CoordinatorData:
        if self._period is None:
            return CoordinatorData(None, "No se ha podido determinar el periodo")
        try:
            tax_point = dt_util.now().date()
            fiscal_rule = find_fiscal_rule(tax_point, SPAIN_MAINLAND_2026)
            groups = tuple(
                ConsumptionGroup(
                    group_id=group[CONF_GROUP_ID],
                    name=group[CONF_GROUP_NAME],
                    add_sources=tuple(group[CONF_ADD_SOURCES]),
                    subtract_sources=tuple(group.get(CONF_SUBTRACT_SOURCES, [])),
                )
                for group in self.config[CONF_GROUPS]
            )
            rates = tuple(
                EnergyRate(
                    rate_id=f"{group[CONF_GROUP_ID]}-fixed",
                    group_id=group[CONF_GROUP_ID],
                    eur_per_kwh=Decimal(group[CONF_EUR_PER_KWH]),
                    valid_from=datetime.combine(
                        self._period.start,
                        datetime.min.time(),
                        tzinfo=dt_util.get_time_zone("Europe/Madrid"),
                    ),
                )
                for group in self.config[CONF_GROUPS]
            )
            power_charges = tuple(
                PowerCharge(code, label, Decimal(self.config[kw]), Decimal(self.config[price]))
                for code, label, kw, price in (
                    ("p1", "Potencia P1", CONF_POWER_P1_KW, CONF_POWER_P1_PRICE),
                    ("p2", "Potencia P2", CONF_POWER_P2_KW, CONF_POWER_P2_PRICE),
                )
                if Decimal(self.config.get(kw, "0")) > 0
            )
            fixed_charges: tuple[FixedCharge, ...] = ()
            rental = Decimal(self.config.get(CONF_METER_RENTAL_DAILY, "0"))
            if rental:
                fixed_charges = (
                    FixedCharge(
                        "meter_rental",
                        "Alquiler de contador",
                        rental,
                        BillingFrequency.DAILY,
                    ),
                )
            result = BillingEngine().calculate(
                InvoiceInput(
                    contract_id=self.config[CONF_CONTRACT_ID],
                    period=self._period,
                    tax_point=tax_point,
                    samples=tuple(self._samples),
                    groups=groups,
                    energy_rates=rates,
                    fiscal_rule=fiscal_rule,
                    power_charges=power_charges,
                    fixed_charges=fixed_charges,
                )
            )
        except (BillingError, KeyError, ValueError) as err:
            return CoordinatorData(None, str(err), tuple(sorted(self._collection_warnings)))
        return CoordinatorData(result, None, tuple(sorted(self._collection_warnings)))

    def _serialize(self) -> dict[str, Any]:
        return {
            "period": {
                "start": self._period.start.isoformat(),
                "end": self._period.end.isoformat(),
            }
            if self._period
            else None,
            "baselines": {key: str(value) for key, value in self._baselines.items()},
            "samples": [
                {
                    "source_id": sample.source_id,
                    "timestamp": sample.timestamp.isoformat(),
                    "kwh": str(sample.kwh),
                    "tariff_period": sample.tariff_period,
                    "complete": sample.complete,
                }
                for sample in self._samples
            ],
            "warnings": sorted(self._collection_warnings),
        }

    def _restore(self, stored: dict[str, Any]) -> None:
        period = stored.get("period")
        if period:
            self._period = BillingPeriod(
                date.fromisoformat(period["start"]), date.fromisoformat(period["end"])
            )
        self._baselines = {
            key: Decimal(value) for key, value in stored.get("baselines", {}).items()
        }
        self._samples = [
            EnergySample(
                source_id=item["source_id"],
                timestamp=datetime.fromisoformat(item["timestamp"]),
                kwh=Decimal(item["kwh"]),
                tariff_period=item.get("tariff_period", "flat"),
                complete=bool(item.get("complete", True)),
            )
            for item in stored.get("samples", [])
        ]
        self._collection_warnings = set(stored.get("warnings", []))
