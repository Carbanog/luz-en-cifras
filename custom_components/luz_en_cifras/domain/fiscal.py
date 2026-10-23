"""Documented fiscal presets.

Only periods whose outcome is known are included. Conditional future periods must
not be guessed; callers can provide an explicit user-verified rule instead.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from decimal import Decimal

from .errors import IncompleteDataError
from .models import FiscalRule

AEAT_ELECTRICITY_TAX = (
    "https://sede.agenciatributaria.gob.es/Sede/impuestos-especiales-medioambientales/"
    "impuesto-especial-sobre-electricidad/liquidacion-pago-impuesto/tipo-impositivo.html"
)
AEAT_VAT_2026 = (
    "https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/"
    "manuales-practicos/manual-iva-2026/capitulo-01-novedades-destacar-2026/"
    "tipos-impositivos.html"
)

SPAIN_MAINLAND_2026: tuple[FiscalRule, ...] = (
    FiscalRule(
        rule_id="es-mainland-2026-ordinary-before-relief",
        valid_from=date(2026, 1, 1),
        valid_to=date(2026, 3, 22),
        electricity_tax_rate=Decimal("0.0511269632"),
        vat_rate=Decimal("0.21"),
        minimum_electricity_eur_per_mwh=Decimal("1"),
        source_urls=(AEAT_ELECTRICITY_TAX, AEAT_VAT_2026),
    ),
    FiscalRule(
        rule_id="es-mainland-2026-temporary-relief",
        valid_from=date(2026, 3, 22),
        valid_to=date(2026, 6, 1),
        electricity_tax_rate=Decimal("0.005"),
        vat_rate=Decimal("0.10"),
        minimum_electricity_eur_per_mwh=Decimal("1"),
        source_urls=(AEAT_ELECTRICITY_TAX, AEAT_VAT_2026),
    ),
    FiscalRule(
        rule_id="es-mainland-2026-ordinary-from-june",
        valid_from=date(2026, 6, 1),
        valid_to=date(2026, 11, 1),
        electricity_tax_rate=Decimal("0.0511269632"),
        vat_rate=Decimal("0.21"),
        minimum_electricity_eur_per_mwh=Decimal("1"),
        source_urls=(AEAT_ELECTRICITY_TAX, AEAT_VAT_2026),
    ),
)


def find_fiscal_rule(tax_point: date, rules: Iterable[FiscalRule]) -> FiscalRule:
    """Find the single fiscal rule valid at the invoice tax point."""
    matches = [
        rule
        for rule in rules
        if rule.valid_from <= tax_point and (rule.valid_to is None or tax_point < rule.valid_to)
    ]
    if not matches:
        raise IncompleteDataError(f"No verified fiscal rule for tax point {tax_point.isoformat()}")
    if len(matches) > 1:
        ids = ", ".join(rule.rule_id for rule in matches)
        raise IncompleteDataError(f"Overlapping fiscal rules for {tax_point.isoformat()}: {ids}")
    return matches[0]
