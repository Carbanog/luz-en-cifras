"""Regression cases for hourly prices and repeated local-clock hours."""

from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from custom_components.luz_en_cifras.domain import (
    BillingEngine,
    ConfigurationError,
    EnergyRate,
    IncompleteDataError,
)
from custom_components.luz_en_cifras.domain.intervals import (
    MeasuredInterval,
    allocate_interval,
    normalize_price,
)

MADRID = ZoneInfo("Europe/Madrid")
D = Decimal


def hour(value: int, *, fold: int = 0) -> datetime:
    return datetime(2026, 10, 25, value, tzinfo=MADRID, fold=fold)


def test_autumn_repeated_hour_has_two_distinct_prices() -> None:
    first, second, end = hour(2), hour(2, fold=1), hour(3)
    rates = (
        EnergyRate("first", "home", D("0.1"), first, second),
        EnergyRate("second", "home", D("0.3"), second, end),
    )
    samples = allocate_interval(
        MeasuredInterval("meter", first, end, D(2)),
        rates,
        "home",
        allow_uniform_estimate=True,
    )
    assert [sample.kwh for sample in samples] == [D(1), D(1)]
    assert all(not sample.complete for sample in samples)
    assert BillingEngine._find_rate(rates, "home", samples[0]).rate_id == "first"
    assert BillingEngine._find_rate(rates, "home", samples[1]).rate_id == "second"


def test_crossing_price_change_requires_explicit_approximation() -> None:
    rates = (
        EnergyRate("a", "home", D("0.1"), hour(0), hour(1)),
        EnergyRate("b", "home", D("0.2"), hour(1), hour(2)),
    )
    with pytest.raises(IncompleteDataError, match="crosses prices"):
        allocate_interval(MeasuredInterval("meter", hour(0), hour(2), D(3)), rates, "home")


def test_missing_price_does_not_allocate_free_energy() -> None:
    rates = (EnergyRate("a", "home", D("0.1"), hour(0), hour(1)),)
    with pytest.raises(IncompleteDataError, match="Missing or overlapping"):
        allocate_interval(
            MeasuredInterval("meter", hour(0), hour(2), D(2)),
            rates,
            "home",
            allow_uniform_estimate=True,
        )


def test_single_price_preserves_measured_energy() -> None:
    rates = (EnergyRate("a", "home", D("-0.1"), hour(0), hour(1)),)
    samples = allocate_interval(MeasuredInterval("meter", hour(0), hour(1), D(4)), rates, "home")
    assert samples[0].complete
    assert samples[0].kwh == D(4)


def test_spring_forward_uses_elapsed_time_not_wall_clock() -> None:
    start = datetime(2026, 3, 29, 1, tzinfo=MADRID)
    middle = datetime(2026, 3, 29, 3, tzinfo=MADRID)
    end = datetime(2026, 3, 29, 4, tzinfo=MADRID)
    rates = (
        EnergyRate("a", "home", D("0.1"), start, middle),
        EnergyRate("b", "home", D("0.2"), middle, end),
    )
    samples = allocate_interval(
        MeasuredInterval("meter", start, end, D(6)),
        rates,
        "home",
        allow_uniform_estimate=True,
    )
    assert [sample.kwh for sample in samples] == [D(3), D(3)]


def test_allocation_conserves_energy_across_fractional_segments() -> None:
    rates = tuple(
        EnergyRate(str(index), "home", D("0.1"), hour(index), hour(index + 1)) for index in range(2)
    )
    samples = allocate_interval(
        MeasuredInterval("meter", hour(0), hour(2), D("0.000000001")),
        rates,
        "home",
        allow_uniform_estimate=True,
    )
    assert sum((sample.kwh for sample in samples), D()) == D("0.000000001")


def test_mwh_price_conversion() -> None:
    for unit in ("EUR/MWh", "€/MWh"):
        assert normalize_price(D("-50"), unit) == D("-0.05")


def test_nonfinite_prices_are_rejected() -> None:
    for value in ("NaN", "Infinity", "-Infinity"):
        with pytest.raises(ConfigurationError):
            normalize_price(D(value), "€/kWh")


def test_overlapping_prices_are_rejected() -> None:
    rates = (
        EnergyRate("a", "home", D("0.1"), hour(0), hour(2)),
        EnergyRate("b", "home", D("0.2"), hour(1), hour(2)),
    )
    with pytest.raises(IncompleteDataError, match="overlapping"):
        allocate_interval(
            MeasuredInterval("meter", hour(0), hour(2), D(2)),
            rates,
            "home",
            allow_uniform_estimate=True,
        )
