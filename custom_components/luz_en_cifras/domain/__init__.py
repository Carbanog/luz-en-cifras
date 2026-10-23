"""Public API for the Home Assistant-independent billing domain."""

from .engine import BillingEngine
from .errors import BillingError, ConfigurationError, IncompleteDataError
from .fiscal import SPAIN_MAINLAND_2026, find_fiscal_rule
from .models import (
    BillingFrequency,
    BillingPeriod,
    ConsumptionGroup,
    DataQuality,
    EnergyRate,
    EnergySample,
    FiscalRule,
    FixedCharge,
    InvoiceInput,
    InvoiceLine,
    InvoiceResult,
    PercentageDiscount,
    PowerCharge,
)

__all__ = [
    "SPAIN_MAINLAND_2026",
    "BillingEngine",
    "BillingError",
    "BillingFrequency",
    "BillingPeriod",
    "ConfigurationError",
    "ConsumptionGroup",
    "DataQuality",
    "EnergyRate",
    "EnergySample",
    "FiscalRule",
    "FixedCharge",
    "IncompleteDataError",
    "InvoiceInput",
    "InvoiceLine",
    "InvoiceResult",
    "PercentageDiscount",
    "PowerCharge",
    "find_fiscal_rule",
]
