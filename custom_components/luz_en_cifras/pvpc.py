"""Direct public REE prices; no dependency on another HA integration."""

import asyncio
from datetime import UTC, datetime
from decimal import Decimal

import aiohttp
from esios_api import EsiosApiData, PVPCData

from .domain.errors import ConfigurationError
from .domain.pvpc import validated_pvpc_prices


class PvpcClient:
    """Keep only validated published prices; network failures never invent quotes."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._api = PVPCData(
            session=session,
            tariff="2.0TD",
            local_timezone="Europe/Madrid",
            timeout=10,
            sensor_keys=("PVPC",),
        )
        self._data: EsiosApiData | None = None
        self.prices: dict[datetime, Decimal] = {}
        self.warning: str | None = None

    async def async_refresh(self, now: datetime) -> None:
        try:
            async with asyncio.timeout(20):
                data = await self._api.async_update_all(self._data, now.astimezone(UTC))
            if not isinstance(data, EsiosApiData) or not isinstance(data.sensors, dict):
                raise ConfigurationError("PVPC: invalid API response")
            prices = validated_pvpc_prices(data.sensors.get("PVPC", {}))
        except (
            aiohttp.ClientError,
            TimeoutError,
            ConfigurationError,
            ValueError,
            KeyError,
            TypeError,
        ):
            self._data = None
            self.warning = (
                "PVPC directo: descarga no disponible o calendario no válido; "
                "sin extrapolar precios"
            )
            return
        self._data = data
        self.prices = prices
        current_hour = now.astimezone(UTC).replace(minute=0, second=0, microsecond=0)
        self.warning = (
            None if current_hour in prices else "PVPC directo: falta el precio de la hora actual"
        )
