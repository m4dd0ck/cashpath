"""Shared plan factories."""

from typing import Any

import pytest

from cashpath.plan import DEMO_PLAN, Plan, load_plan, plan_from_data


def make_plan(**overrides: Any) -> Plan:
    """Build a small valid plan; keyword arguments replace top-level fields."""
    data: dict[str, Any] = {
        "name": "Test",
        "start": "2027-01",
        "horizon_months": 12,
        "settings": {"investment_return_pct": 0},
        "income": [{"name": "paycheck", "amount": 3000}],
    }
    data.update(overrides)
    return plan_from_data(data)


@pytest.fixture
def demo_plan() -> Plan:
    return load_plan(DEMO_PLAN)
