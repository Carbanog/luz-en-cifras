"""JSON-safe invoice snapshots and explicitly audited reconciliation."""

from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from .errors import ConfigurationError
from .models import InvoiceResult


def json_safe(value: Any) -> Any:
    """Encode domain values without converting money through floating point."""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    return value


def snapshot(result: InvoiceResult, config: dict[str, Any]) -> dict[str, Any]:
    """Freeze output, price configuration and tax provenance for a closed period."""
    return {
        "schema_version": 1,
        "id": f"{result.contract_id}:{result.period.start}:{result.period.end}",
        "result": json_safe(asdict(result)),
        "config": json_safe(config),
        "audit": [],
    }


def reconcile(
    record: dict[str, Any], total: Decimal, kwh: Decimal, changed_at: datetime
) -> dict[str, Any]:
    """Return a new record retaining every previous real-invoice comparison."""
    if not record.get("result"):
        raise ConfigurationError("Cannot reconcile a period without a valid estimate")
    if not total.is_finite() or not kwh.is_finite() or kwh < 0:
        raise ConfigurationError("Real invoice values must be finite; energy cannot be negative")
    estimated = Decimal(record["result"]["total"])
    measured = Decimal(record["result"]["total_kwh"])
    comparison = {
        "changed_at": changed_at.isoformat(),
        "real_total": str(total),
        "real_kwh": str(kwh),
        "difference_eur": str(total - estimated),
        "difference_kwh": str(kwh - measured),
        "difference_percent": str((total - estimated) / estimated * 100) if estimated else None,
    }
    return {**record, "comparison": comparison, "audit": [*record.get("audit", []), comparison]}
