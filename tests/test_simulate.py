import datetime as dt
from decimal import Decimal

import pytest

from cashpath.errors import PlanError
from cashpath.plan import Plan
from cashpath.simulate import Change, apply_change, describe_change, parse_change, simulate
from tests.conftest import make_plan

RENT = [{"name": "rent", "amount": 2000}]


def payoff_plan() -> Plan:
    return make_plan(
        settings={"investment_return_pct": 0, "extra_debt_min_apr": 0},
        expenses=[{"name": "rent", "amount": 2800}],
        debts=[{"name": "loan", "balance": 1200, "apr": 0, "payment": 100}],
        priorities=["extra_debt"],
    )


def test_income_row_starts_with_the_plan_by_default() -> None:
    plan = make_plan()
    changed = apply_change(plan, Change(income=Decimal("500"), expense=Decimal("0")))
    added = changed.income[-1]
    assert (added.name, added.amount, added.start, added.end) == (
        "simulation",
        Decimal("500"),
        dt.date(2027, 1, 1),
        None,
    )
    assert changed.expenses == plan.expenses


def test_expense_row_carries_start_and_end() -> None:
    change = Change(
        income=Decimal("0"),
        expense=Decimal("400"),
        start=dt.date(2027, 3, 1),
        end=dt.date(2027, 5, 1),
    )
    changed = apply_change(make_plan(), change)
    added = changed.expenses[-1]
    assert (added.amount, added.start, added.end) == (
        Decimal("400"),
        dt.date(2027, 3, 1),
        dt.date(2027, 5, 1),
    )
    assert len(changed.income) == 1


def test_extra_income_adds_to_cash_every_month() -> None:
    result = simulate(make_plan(expenses=RENT), Change(Decimal("500"), Decimal("0")))
    assert result.simulated.rows[-1].cash - result.plan.rows[-1].cash == 6000


def test_extra_income_stops_after_end() -> None:
    change = Change(Decimal("500"), Decimal("0"), dt.date(2027, 3, 1), dt.date(2027, 5, 1))
    result = simulate(make_plan(expenses=RENT), change)
    assert result.simulated.rows[-1].cash - result.plan.rows[-1].cash == 1500


def test_extra_income_pays_debt_off_sooner() -> None:
    result = simulate(payoff_plan(), Change(Decimal("600"), Decimal("0")))
    assert result.plan.payoff["loan"] == dt.date(2027, 6, 1)
    assert result.simulated.payoff["loan"] == dt.date(2027, 2, 1)


def test_start_after_the_horizon_changes_nothing() -> None:
    result = simulate(make_plan(), Change(Decimal("500"), Decimal("0"), dt.date(2030, 1, 1)))
    assert result.simulated.rows == result.plan.rows


def test_start_before_the_plan_is_refused() -> None:
    with pytest.raises(PlanError, match="before the plan starts"):
        apply_change(make_plan(), Change(Decimal("500"), Decimal("0"), dt.date(2026, 12, 1)))


def test_end_before_the_default_start_is_refused() -> None:
    change = Change(Decimal("500"), Decimal("0"), end=dt.date(2026, 6, 1))
    with pytest.raises(PlanError, match="--end 2026-06 is before"):
        apply_change(make_plan(), change)


def test_parse_change_converts_options() -> None:
    change = parse_change(3000.1, None, "2027-03", None)
    assert change == Change(Decimal("3000.1"), Decimal("0"), dt.date(2027, 3, 1), None)


def test_parse_change_needs_an_amount() -> None:
    with pytest.raises(PlanError, match="--income, --expense or both"):
        parse_change(None, None, None, None)


def test_parse_change_refuses_a_negative_amount() -> None:
    with pytest.raises(PlanError, match="--income must be 0 or more"):
        parse_change(-1.0, None, None, None)


def test_parse_change_refuses_a_bad_month() -> None:
    with pytest.raises(PlanError, match="--start"):
        parse_change(100.0, None, "2027-13", None)


def test_parse_change_refuses_end_before_start() -> None:
    with pytest.raises(PlanError, match="--end 2027-01 is before --start 2027-03"):
        parse_change(100.0, None, "2027-03", "2027-01")


def test_describe_open_ended_income() -> None:
    change = Change(Decimal("3000"), Decimal("0"))
    assert describe_change(make_plan(), change) == "+$3,000/mo income from 2027-01"


def test_describe_income_and_expense_with_an_end() -> None:
    change = Change(Decimal("3000"), Decimal("400"), dt.date(2027, 3, 1), dt.date(2027, 12, 1))
    assert describe_change(make_plan(), change) == (
        "+$3,000/mo income, +$400/mo expense, 2027-03 to 2027-12"
    )
