from decimal import Decimal
from typing import Any

import pytest

from cashpath.errors import PlanError
from cashpath.plan import Plan
from cashpath.whatif import Controls, build_whatif, clean_rows


def controls_for(plan: Plan, **changes: object) -> Controls:
    values: dict[str, object] = {
        "contribution_pct": plan.retirement.contribution_pct if plan.retirement else None,
        "investment_return_pct": plan.settings.investment_return_pct,
        "annual_raise_pct": plan.settings.annual_raise_pct,
        "cash_floor": plan.settings.cash_floor,
        "emergency_fund": plan.settings.emergency_fund,
        "priorities": plan.priorities,
    }
    values.update(changes)
    return Controls(**values)  # type: ignore[arg-type]


def test_unchanged_controls_give_back_an_equal_plan(demo_plan: Plan) -> None:
    assert build_whatif(demo_plan, controls_for(demo_plan)) == demo_plan


def test_controls_replace_settings_and_contribution(demo_plan: Plan) -> None:
    whatif = build_whatif(
        demo_plan,
        controls_for(demo_plan, contribution_pct=Decimal("10"), cash_floor=Decimal("500")),
    )
    assert whatif.retirement is not None
    assert whatif.retirement.contribution_pct == 10
    assert whatif.settings.cash_floor == 500
    assert whatif.debts == demo_plan.debts


def test_priority_order_comes_from_controls(demo_plan: Plan) -> None:
    whatif = build_whatif(demo_plan, controls_for(demo_plan, priorities=["roth", "extra_debt"]))
    assert whatif.priorities == ["roth", "extra_debt"]


def test_edited_tables_replace_rows(demo_plan: Plan) -> None:
    tables = {"one_time": [{"name": "bonus", "month": "2027-12", "amount": 3000.0}]}
    whatif = build_whatif(demo_plan, controls_for(demo_plan), tables)
    assert [item.name for item in whatif.one_time] == ["bonus"]


def test_invalid_edit_raises_plan_error(demo_plan: Plan) -> None:
    tables = {"debts": [{"name": "card", "balance": -5.0, "apr": 20.0, "payment": 10.0}]}
    with pytest.raises(PlanError, match="debts.0.balance"):
        build_whatif(demo_plan, controls_for(demo_plan), tables)


def test_clean_rows_drops_blank_cells_and_empty_rows() -> None:
    rows: list[dict[str, Any]] = [
        {"name": " rent ", "amount": 1400.0, "start": None, "end": ""},
        {"name": None, "amount": None, "start": None, "end": None},
    ]
    assert clean_rows(rows) == [{"name": "rent", "amount": 1400.0}]
