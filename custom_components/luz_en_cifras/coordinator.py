"""Event-driven, persisted measurement and immutable billing history."""

from __future__ import annotations

import asyncio
import calendar
import logging
from contextlib import suppress
from copy import deepcopy
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import DOMAIN, STORAGE_VERSION
from .domain import BillingPeriod, DataQuality, InvoiceResult
from .domain.billing import calculate_contract
from .domain.errors import BillingError, MissingFiscalRuleError
from .domain.history import reconcile, snapshot
from .domain.intervals import MeasuredInterval, normalize_price
from .domain.ledger import MeasurementLedger
from .domain.models import EnergyRate

_LOGGER = logging.getLogger(__name__)


def _now() -> datetime:
    """Use the supported contract's timezone independently of the HA server setting."""
    return dt_util.now().astimezone(ZoneInfo("Europe/Madrid"))


@dataclass(frozen=True, slots=True)
class CoordinatorData:
    result: InvoiceResult | None
    error: str | None
    collection_warnings: tuple[str, ...] = ()


class LuzEnCifrasCoordinator(DataUpdateCoordinator[CoordinatorData]):
    """Keep raw data, effective prices and frozen historical calculations."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, _LOGGER, config_entry=entry, name=DOMAIN)
        self.entry = entry
        # Options mutate the entry before its reload listener runs. Keep the old
        # collector bound to its original settings until unloading has finished.
        self._config = deepcopy({**entry.data, **entry.options})
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}"
        )
        self.ledger = MeasurementLedger()
        self.history: list[dict[str, Any]] = []
        self._period: BillingPeriod | None = None
        self._stored_config: dict[str, Any] = {}
        self._legacy: dict[str, Any] | None = None
        self.revisions: list[dict[str, Any]] = []
        self._pvpc = None
        self._pvpc_task: asyncio.Task | None = None
        self._stopping = False

    @property
    def config(self) -> dict[str, Any]:
        return self._config

    @property
    def billing_period(self) -> BillingPeriod | None:
        return self._period

    @property
    def source_ids(self) -> set[str]:
        return self._sources_for(self.config)

    @property
    def price_ids(self) -> set[str]:
        return {
            group["price_entity"]
            for group in self.config["groups"]
            if group.get("tariff_mode") == "entity" and group.get("price_entity")
        }

    async def async_initialize(self) -> None:
        stored = await self._store.async_load() or {}
        self.history = stored.get("history", [])
        self._legacy = stored.get("legacy_v1")
        self._stored_config = stored.get("config", self.config)
        now = _now()
        if any(group.get("tariff_mode") == "pvpc" for group in self.config["groups"]):
            from .pvpc import PvpcClient

            self._pvpc = PvpcClient(async_get_clientsession(self.hass))
            await self._pvpc.async_refresh(now)
            now = _now()
        self.revisions = stored.get("revisions", [])
        if stored.get("period"):
            self._period = BillingPeriod(
                date.fromisoformat(stored["period"]["start"]),
                date.fromisoformat(stored["period"]["end"]),
            )
        if "ledger" in stored:
            self.ledger = MeasurementLedger.restore(stored["ledger"])
            if self.ledger.power_samples:
                self.ledger.power_samples.clear()
                self.ledger.warnings.add(
                    "Potencia durante parada no reconstruida; energía anterior conservada"
                )
            if stored.get("saved_at"):
                for group in self._stored_config["groups"]:
                    if group.get("tariff_mode") == "entity":
                        state = self.hass.states.get(group.get("price_entity", ""))
                        saved_at = datetime.fromisoformat(stored["saved_at"])
                        # A live reload can retain a quote if HA confirms the
                        # source has not changed and it is still within its TTL.
                        if (
                            state
                            and state.last_updated <= saved_at
                            and (now - state.last_updated).total_seconds()
                            <= 60 * float(group.get("price_max_age_minutes", 65))
                        ):
                            continue
                        self.ledger.price(group["group_id"], None, saved_at)
                        self.ledger.warnings.add("Precio dinámico durante parada no reconstruido")
        elif stored:
            # Retain the original payload, and import point samples as micro-intervals.
            # Their original collection precision cannot be reconstructed.
            self._legacy = stored
            for item in stored.get("samples", []):
                stamp = datetime.fromisoformat(item["timestamp"])
                self.ledger.intervals.append(
                    MeasuredInterval(
                        item["source_id"],
                        stamp,
                        stamp + timedelta(microseconds=1),
                        Decimal(item["kwh"]),
                    )
                )
            self.ledger.baselines = {
                source: (Decimal(value), now)
                for source, value in stored.get("baselines", {}).items()
            }
            self.ledger.warnings.add(
                "Migración 0.1: precisión temporal anterior desconocida; copia original conservada"
            )
            start = (
                datetime.combine(self._period.start, datetime.min.time(), now.tzinfo)
                if self._period
                else now
            )
            for group in self.config["groups"]:
                self.ledger.price(group["group_id"], Decimal(str(group["eur_per_kwh"])), start)

        changed = self._stored_config != self.config
        if changed:
            old_sources = self._sources_for(self._stored_config)
            retained = old_sources & self.source_ids
            # Detached meters must not contribute their off-contract increments
            # if they are selected again later in the same billing period.
            for source in set(self.ledger.baselines) - retained:
                self.ledger.baselines.pop(source, None)
            for source in set(self.ledger.pending_energy_sources) - retained:
                self.ledger.pending_energy_sources.pop(source, None)
            for source in retained:
                self._collect_source(source, now)
            self.ledger.revision_boundaries.append(now)
            if old_sources != self.source_ids or self._stored_config.get(
                "groups"
            ) != self.config.get("groups"):
                self.ledger.warnings.add(
                    "Fuentes/tarifa revisadas: se conserva el consumo anterior; "
                    "las fuentes nuevas parten de una nueva referencia"
                )
        self._roll(now.date(), when=now)
        if not self.revisions:
            self.revisions.append(
                {
                    "from": datetime.combine(
                        self._period.start, datetime.min.time(), now.tzinfo
                    ).isoformat(),
                    "config": deepcopy(self._stored_config),
                }
            )
        if self._stored_config != self.config:
            self.revisions.append({"from": now.isoformat(), "config": deepcopy(self.config)})
        self._capture_prices(now)
        for source in self.source_ids:
            self._collect_source(source, now)
        self._stored_config = self.config
        self.data = self._calculate()
        self.entry.async_on_unload(
            async_track_state_change_event(
                self.hass, list(self.source_ids | self.price_ids), self._handle_state_event
            )
        )
        self.entry.async_on_unload(
            async_track_time_interval(self.hass, self._tick, timedelta(minutes=1))
        )
        if self._pvpc is not None:
            self.entry.async_on_unload(
                async_track_time_interval(
                    self.hass, self._async_refresh_pvpc, timedelta(minutes=30)
                )
            )
        await self.async_persist()

    async def _async_refresh_pvpc(self, when: datetime) -> None:
        if self._stopping or self._pvpc_task is not None or self._pvpc is None:
            return
        self._pvpc_task = asyncio.current_task()
        try:
            await self._pvpc.async_refresh(when)
            if not self._stopping:
                self._capture_prices(_now())
                self._publish()
        finally:
            self._pvpc_task = None

    async def async_shutdown(self) -> None:
        """Do not let an in-flight download write after unloading the contract."""
        self._stopping = True
        if task := self._pvpc_task:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        await self.async_persist()

    async def _async_update_data(self) -> CoordinatorData:
        return self._calculate()

    @callback
    def _tick(self, now: datetime) -> None:
        local = now.astimezone(ZoneInfo("Europe/Madrid"))
        self._roll(local.date(), when=local)
        self._collect_power(local)
        self._capture_prices(local)
        self._publish()

    @callback
    def _handle_state_event(self, event: Event) -> None:
        now = _now()
        self._roll(now.date(), when=now)
        source = event.data["entity_id"]
        state = event.data.get("new_state")
        if source in self.price_ids:
            self._collect_power(now)
            self._capture_prices(now)
        if source in self.source_ids:
            self._collect_source(source, now, state)
        self._publish()

    def _publish(self) -> None:
        self._store.async_delay_save(self._serialize, 10)
        self.async_set_updated_data(self._calculate())

    def _capture_prices(self, when: datetime) -> None:
        active_groups = {group["group_id"] for group in self.config["groups"]}
        if self.config.get("enable_surplus"):
            active_groups.add("__surplus")
        for group_id in {
            rate.group_id for rate in self.ledger.rates if rate.valid_to is None
        } - active_groups:
            self.ledger.price(group_id, None, when)
        if self.config.get("enable_surplus"):
            self.ledger.price("__surplus", Decimal(str(self.config.get("surplus_price", 0))), when)
        for group in self.config["groups"]:
            mode = group.get("tariff_mode", "fixed")
            if mode == "pvpc":
                self.ledger.price(group["group_id"], None, when)
                self._capture_pvpc(group)
                continue
            if mode == "three_period":
                self.ledger.price(group["group_id"], None, when)
                continue
            value: Decimal | None = None
            if mode == "fixed":
                value = Decimal(str(group["eur_per_kwh"]))
            elif mode == "entity":
                state = self.hass.states.get(group.get("price_entity", ""))
                age = (when - state.last_updated).total_seconds() if state else float("inf")
                max_age = 60 * float(group.get("price_max_age_minutes", 65))
                if state and state.state not in {"unknown", "unavailable"} and age <= max_age:
                    try:
                        value = normalize_price(
                            Decimal(state.state), state.attributes.get("unit_of_measurement", "")
                        )
                        value += Decimal(str(group.get("price_markup", 0)))
                    except BillingError, InvalidOperation:
                        self.ledger.warnings.add(f"{group['group_name']}: precio no válido")
                elif age > max_age:
                    self.ledger.warnings.add(
                        f"{group['group_name']}: precio caducado o no disponible"
                    )
            self.ledger.price(
                group["group_id"],
                value,
                when,
                discount_rate=Decimal(str(self.config.get("energy_discount_percent", 0))) / 100,
            )

    def _capture_pvpc(self, group: dict[str, Any]) -> None:
        if self._pvpc is None:
            return
        if self._pvpc.warning:
            self.ledger.warnings.add(self._pvpc.warning)
        known = {rate.rate_id: rate for rate in self.ledger.rates}
        for stamp, price in self._pvpc.prices.items():
            key = f"pvpc:{group['group_id']}:{stamp.isoformat()}"
            if key in known:
                if known[key].eur_per_kwh != price:
                    self.ledger.warnings.add(
                        "PVPC publicado revisado: se conserva la cotización original guardada"
                    )
                continue
            self.ledger.rates.append(
                EnergyRate(key, group["group_id"], price, stamp, stamp + timedelta(hours=1))
            )

    def _collect_source(self, source: str, when: datetime, state: State | None = None) -> None:
        state = state or self.hass.states.get(source)
        if (
            state
            and state.attributes.get("unit_of_measurement") in {"Wh", "kWh"}
            and source not in self.ledger.baselines
        ):
            self.ledger.pending_energy_sources.setdefault(source, when)
        value = None
        try:
            value = Decimal(state.state) if state and not state.attributes.get("restored") else None
        except InvalidOperation:
            value = None  # Domain collector records the gap; never substitute zero.
        self.ledger.observe_input(
            source,
            value,
            state.attributes.get("unit_of_measurement", "") if state else "",
            when,
            reported_at=state.last_reported if state else when,
            max_age_seconds=int(float(self.config.get("power_max_age_minutes", 5)) * 60),
        )

    def _collect_power(self, when: datetime) -> None:
        for source in self.source_ids:
            state = self.hass.states.get(source)
            if source in self.ledger.power_samples or (
                state and state.attributes.get("unit_of_measurement") in {"W", "kW"}
            ):
                self._collect_source(source, when, state)

    def _roll(self, today: date, *, when: datetime | None = None) -> None:
        period = self._current_period(
            today,
            int(self.config["billing_day"]),
            int(self.config.get("billing_months", 1)),
            int(self.config.get("billing_anchor_month", 1)),
        )
        if self._period == period:
            return
        if self._period:
            boundary = datetime.combine(
                self._period.end, datetime.min.time(), ZoneInfo("Europe/Madrid")
            )
            for source in tuple(self.ledger.power_samples):
                self.ledger.advance_power(
                    source, boundary, int(float(self.config.get("power_max_age_minutes", 5)) * 60)
                )
            self._archive("cycle_closed")
            self.ledger = MeasurementLedger()
        self._period = period
        # One event instant must govern both prices and measurement cursors.
        # Reading the clock again here used to leave startup microsecond gaps.
        instant = when if when is not None else _now()
        self._capture_prices(instant)
        for source in self.source_ids:
            self._collect_source(source, instant)

    @staticmethod
    def _current_period(
        today: date, billing_day: int, months: int = 1, anchor_month: int = 1
    ) -> BillingPeriod:
        if not 1 <= billing_day <= 31 or months not in {1, 2} or not 1 <= anchor_month <= 12:
            raise ValueError("Invalid billing cycle")
        index = today.year * 12 + today.month - 1
        anchor = index - (today.month - anchor_month) % months

        def boundary(value: int) -> date:
            year, month = divmod(value, 12)
            return date(year, month + 1, min(billing_day, calendar.monthrange(year, month + 1)[1]))

        if today < boundary(anchor):
            anchor -= months
        return BillingPeriod(boundary(anchor), boundary(anchor + months))

    def _calculate(
        self, *, closed: bool = False, config: dict[str, Any] | None = None
    ) -> CoordinatorData:
        if self._period is None:
            return CoordinatorData(None, "No se ha determinado el periodo")
        try:
            today = _now().date()
            end = self._period.end if closed else min(self._period.end, today + timedelta(days=1))
            period = BillingPeriod(self._period.start, end)
            result = calculate_contract(
                config or self.config,
                self.ledger,
                period,
                self._period.end - timedelta(days=1) if closed else today,
                revisions=self.revisions,
            )
        except (BillingError, ValueError, KeyError, InvalidOperation) as err:
            if isinstance(err, MissingFiscalRuleError):
                ir.async_create_issue(
                    self.hass,
                    DOMAIN,
                    f"fiscal_{self.entry.entry_id}",
                    is_fixable=False,
                    severity=ir.IssueSeverity.WARNING,
                    translation_key="missing_fiscal_rule",
                )
            return CoordinatorData(None, str(err), tuple(sorted(self.ledger.warnings)))
        ir.async_delete_issue(self.hass, DOMAIN, f"fiscal_{self.entry.entry_id}")
        if self.ledger.warnings:
            result = replace(
                result,
                quality=DataQuality.PARTIAL,
                warnings=(*result.warnings, *sorted(self.ledger.warnings)),
            )
        return CoordinatorData(result, None, tuple(sorted(set(result.warnings))))

    def _archive(self, reason: str) -> None:
        self.ledger.warnings.add("Devengo provisional: último día del periodo de consumo")
        data = self._calculate(closed=True, config=self._stored_config or self.config)
        if data.result:
            record = snapshot(data.result, self._stored_config or self.config)
        else:
            record = {
                "schema_version": 1,
                "result": None,
                "error": data.error,
                "config": deepcopy(self._stored_config or self.config),
                "id": f"{self.config['contract_id']}:incomplete:{uuid4().hex}",
            }
        record.update(
            {
                "closed_at": dt_util.now().isoformat(),
                "reason": reason,
                "raw": self.ledger.serialize(),
                "revisions": deepcopy(self.revisions),
                "warnings": sorted(self.ledger.warnings),
                "period": {
                    "start": self._period.start.isoformat(),
                    "end": self._period.end.isoformat(),
                },
            }
        )
        if any(item.get("id") == record.get("id") for item in self.history):
            record["id"] = f"{record['id']}:segment:{uuid4().hex}"
        self.history.append(record)

    async def async_recalculate(
        self, record_id: str, reason: str, current_tax_profile: bool, tax_point: date | None = None
    ) -> dict[str, Any]:
        """Create a superseding snapshot; never overwrite the original estimate."""
        original = next((item for item in self.history if item.get("id") == record_id), None)
        if not original or not original.get("raw") or not reason.strip():
            raise ValueError(
                "Se requiere un periodo con datos guardados y el motivo de la revisión"
            )
        values = original.get("period") or original["result"]["period"]
        period = BillingPeriod(
            date.fromisoformat(values["start"]), date.fromisoformat(values["end"])
        )
        config = deepcopy(original["config"])
        if current_tax_profile:
            for key, value in self.config.items():
                if key.startswith("tax_") or key == "fiscal_mode":
                    config[key] = value
        ledger = MeasurementLedger.restore(original["raw"])
        effective_tax_point = tax_point or (
            date.fromisoformat(original["result"]["tax_point"])
            if original.get("result")
            else period.end - timedelta(days=1)
        )
        if tax_point:
            ledger.warnings.discard("Devengo provisional: último día del periodo de consumo")
        result = calculate_contract(
            config,
            ledger,
            period,
            effective_tax_point,
            revisions=original.get("revisions"),
        )
        if ledger.warnings:
            result = replace(
                result,
                quality=DataQuality.PARTIAL,
                warnings=(*result.warnings, *sorted(ledger.warnings)),
            )
        record = snapshot(result, config)
        record.update(
            id=f"{record['id']}:revision:{uuid4().hex}",
            supersedes=record_id,
            reason=reason.strip(),
            closed_at=_now().isoformat(),
            raw=deepcopy(original["raw"]),
            revisions=deepcopy(original.get("revisions", [])),
        )
        self.history.append(record)
        await self.async_persist()
        return deepcopy(record)

    async def async_persist(self) -> None:
        await self._store.async_save(self._serialize())

    async def async_prepare_reload(self) -> None:
        """Read the old meters at the transition without using the new options."""
        now = _now()
        self._roll(now.date(), when=now)
        for source in self.source_ids:
            self._collect_source(source, now)
        await self.async_persist()

    @staticmethod
    def _sources_for(config: dict[str, Any]) -> set[str]:
        sources = {
            source
            for group in config.get("groups", [])
            for source in (*group["add_sources"], *group.get("subtract_sources", []))
        }
        if config.get("enable_surplus") and config.get("export_source"):
            sources.add(config["export_source"])
        return sources

    async def async_archive_period(
        self, start: date, end: date, tax_point: date, allow_boundary_estimate: bool = False
    ) -> dict[str, Any]:
        """Freeze a past date range without deleting or reinterpreting live data."""
        period = BillingPeriod(start, end)
        if end > _now().date():
            raise ValueError("Solo se pueden cerrar días completos anteriores a hoy")
        ledger = MeasurementLedger.restore(self.ledger.serialize())
        bounds = [
            datetime.combine(day, datetime.min.time(), dt_util.get_time_zone("Europe/Madrid"))
            for day in (start, end)
        ]
        selected = []
        for interval in ledger.intervals:
            if interval.end <= bounds[0] or interval.start >= bounds[1]:
                continue
            if interval.start < bounds[0] or interval.end > bounds[1]:
                if not allow_boundary_estimate:
                    raise ValueError(
                        "Una lectura cruza el límite: requiere autorizar la estimación parcial"
                    )
                left, right = max(interval.start, bounds[0]), min(interval.end, bounds[1])
                fraction = Decimal(
                    str((right.astimezone(UTC) - left.astimezone(UTC)).total_seconds())
                ) / Decimal(
                    str(
                        (
                            interval.end.astimezone(UTC) - interval.start.astimezone(UTC)
                        ).total_seconds()
                    )
                )
                interval = replace(interval, start=left, end=right, kwh=interval.kwh * fraction)
                ledger.warnings.add(
                    "Consumo en límites de factura repartido por tiempo: estimación parcial"
                )
            selected.append(interval)
        ledger.intervals = selected
        result = calculate_contract(
            self.config, ledger, period, tax_point, revisions=self.revisions
        )
        if ledger.warnings:
            result = replace(
                result,
                quality=DataQuality.PARTIAL,
                warnings=(*result.warnings, *sorted(ledger.warnings)),
            )
        record = snapshot(result, self.config)
        if any(item.get("id") == record["id"] for item in self.history):
            raise ValueError("El periodo ya está cerrado; el original se conserva")
        record.update(
            reason="manual",
            closed_at=_now().isoformat(),
            raw=ledger.serialize(),
            revisions=deepcopy(self.revisions),
            original_measurements=self.ledger.serialize() if allow_boundary_estimate else None,
        )
        self.history.append(record)
        await self.async_persist()
        return deepcopy(record)

    async def async_compare(self, record_id: str, total: Decimal, kwh: Decimal) -> dict[str, Any]:
        index = next(
            (n for n, item in enumerate(self.history) if item.get("id") == record_id), None
        )
        if index is None:
            raise ValueError("No existe ese periodo cerrado")
        self.history[index] = reconcile(self.history[index], total, kwh, dt_util.now())
        await self.async_persist()
        return self.history[index]

    def _serialize(self) -> dict[str, Any]:
        return {
            "schema_version": 3,
            "saved_at": dt_util.now().isoformat(),
            "revisions": self.revisions,
            "ledger": self.ledger.serialize(),
            "history": self.history,
            "config": self._stored_config or self.config,
            "legacy_v1": self._legacy,
            "period": {"start": self._period.start.isoformat(), "end": self._period.end.isoformat()}
            if self._period
            else None,
        }
