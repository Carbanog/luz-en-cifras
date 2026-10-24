"""Real HA fixtures; all synthetic sensor readings are confined to tests."""

import pytest


@pytest.fixture(autouse=True)
def custom_integrations(enable_custom_integrations):
    """Enable the component loader solely for this test suite."""


@pytest.fixture
def contract():
    return {
        "contract_id": "test-home",
        "contract_name": "Casa",
        "billing_day": 1,
        "power_p1_kw": "0",
        "power_p2_kw": "0",
        "power_p1_eur_per_kw_day": "0",
        "power_p2_eur_per_kw_day": "0",
        "meter_rental_daily": "0",
        "groups": [
            {
                "group_id": "home",
                "group_name": "Vivienda",
                "add_sources": ["sensor.test_energy"],
                "subtract_sources": [],
                "eur_per_kwh": "0.2",
            }
        ],
    }
