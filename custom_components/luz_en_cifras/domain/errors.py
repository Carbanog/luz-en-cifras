"""Domain errors with messages suitable for diagnostics, not end-user translation."""


class BillingError(ValueError):
    """Base class for a calculation that cannot produce a trustworthy result."""


class ConfigurationError(BillingError):
    """The contract or source topology is invalid."""


class IncompleteDataError(BillingError):
    """Required measurements, prices, or fiscal rules are missing."""


class MissingFiscalRuleError(IncompleteDataError):
    """No verified rule covers the invoice tax point."""


class UnconfirmedTaxesError(IncompleteDataError):
    """The user must confirm the contract's manual tax settings."""
