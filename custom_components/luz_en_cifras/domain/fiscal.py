"""Documented fiscal presets.

Only periods whose outcome is known are included. Conditional future periods must
not be guessed; callers can provide an explicit user-verified rule instead.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace
from datetime import date
from decimal import Decimal
from typing import Any
from urllib.parse import urlparse

from .errors import IncompleteDataError, MissingFiscalRuleError, UnconfirmedTaxesError
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
        raise MissingFiscalRuleError(
            f"No verified fiscal rule for tax point {tax_point.isoformat()}"
        )
    if len(matches) > 1:
        ids = ", ".join(rule.rule_id for rule in matches)
        raise IncompleteDataError(f"Overlapping fiscal rules for {tax_point.isoformat()}: {ids}")
    return matches[0]


def household_rule(tax_point: date, maximum_power_kw: Decimal) -> FiscalRule:
    """Apply the documented <=10 kW condition for the temporary reduced VAT."""
    rule = find_fiscal_rule(tax_point, SPAIN_MAINLAND_2026)
    if rule.vat_rate == Decimal("0.10") and maximum_power_kw <= 0:
        raise IncompleteDataError(
            "Contracted power is required to determine reduced VAT eligibility"
        )
    if rule.vat_rate == Decimal("0.10") and maximum_power_kw > 10:
        return replace(rule, rule_id=f"{rule.rule_id}-over-10kw", vat_rate=Decimal("0.21"))
    return rule


def configured_rule(config: dict[str, Any], tax_point: date) -> FiscalRule:
    """Explicit user-reviewed rules cover documented cases outside automatic presets."""
    if config.get("fiscal_mode") == "contract":
        if not config.get("tax_rules_confirmed"):
            raise UnconfirmedTaxesError("Review and confirm the contract's manual tax percentages")
        electricity = Decimal(str(config["tax_electricity_percent"])) / 100
        indirect = Decimal(str(config["tax_indirect_percent"])) / 100
        minimum = Decimal(str(config.get("tax_minimum_eur_mwh", 1)))
        return FiscalRule(
            rule_id=f"manual-contract:{electricity}:{indirect}:{minimum}",
            valid_from=date.min,
            valid_to=None,
            electricity_tax_rate=electricity,
            vat_rate=indirect,
            minimum_electricity_eur_per_mwh=minimum,
            # This is user-supplied configuration, not a claim of official verification.
            source_urls=("manual:contract",),
            indirect_tax_name=str(config.get("tax_name", "IVA")),
        )
    if config.get("fiscal_mode", "automatic") == "automatic":
        return household_rule(
            tax_point,
            max(
                Decimal(str(config.get("power_p1_kw", 0))),
                Decimal(str(config.get("power_p2_kw", 0))),
            ),
        )
    source = str(config.get("tax_source", ""))
    parsed = urlparse(source)
    if (
        not config.get("tax_rules_confirmed")
        or parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise IncompleteDataError(
            "Manual tax profile requires confirmation and a public HTTPS source without credentials"
        )
    rule = FiscalRule(
        rule_id="user-reviewed:" + str(config["tax_valid_from"]),
        valid_from=date.fromisoformat(config["tax_valid_from"]),
        valid_to=date.fromisoformat(config["tax_valid_to"]),
        electricity_tax_rate=Decimal(str(config["tax_electricity_percent"])) / 100,
        vat_rate=Decimal(str(config["tax_indirect_percent"])) / 100,
        minimum_electricity_eur_per_mwh=Decimal(str(config["tax_minimum_eur_mwh"])),
        source_urls=(source,),
        indirect_tax_name=str(config.get("tax_name", "Impuesto indirecto")),
    )
    return find_fiscal_rule(tax_point, (rule,))
