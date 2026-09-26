import datetime as dt
from decimal import Decimal
from pathlib import Path

import pytest

from cashpath.errors import PlanError
from cashpath.plan import Plan, dump_plan, load_plan, parse_plan
from tests.conftest import make_plan

FIXTURES = Path(__file__).parent / "fixtures"


def test_demo_plan_loads(demo_plan: Plan) -> None:
    assert demo_plan.name == "Sam (demo)"
    assert demo_plan.start == dt.date(2027, 1, 1)
    assert [debt.name for debt in demo_plan.debts] == ["credit card", "car loan", "student loans"]


def test_float_input_becomes_exact_decimal() -> None:
    plan = make_plan(debts=[{"name": "card", "balance": 1000, "apr": 23.9, "payment": 50}])
    assert plan.debts[0].apr == Decimal("23.9")


def test_month_accepts_string_and_first_of_month_date() -> None:
    plan = make_plan(start=dt.date(2027, 3, 1))
    assert plan.start == dt.date(2027, 3, 1)
    assert make_plan(start="2027-03").start == dt.date(2027, 3, 1)


def test_month_rejects_mid_month_date() -> None:
    with pytest.raises(PlanError, match="start: .*2027-03-15"):
        make_plan(start=dt.date(2027, 3, 15))


def test_month_rejects_bad_string() -> None:
    with pytest.raises(PlanError, match="expected a month like 2027-06"):
        make_plan(start="March 2027")


def test_unknown_field_is_rejected() -> None:
    with pytest.raises(PlanError, match="colour"):
        make_plan(colour="blue")


def test_boolean_amount_is_rejected() -> None:
    with pytest.raises(PlanError, match="boolean"):
        make_plan(income=[{"name": "paycheck", "amount": True}])


def test_end_before_start_is_rejected() -> None:
    with pytest.raises(PlanError, match="before start"):
        make_plan(expenses=[{"name": "rent", "amount": 1, "start": "2027-06", "end": "2027-05"}])


def test_duplicate_priority_is_rejected() -> None:
    with pytest.raises(PlanError, match="only once"):
        make_plan(priorities=["roth", "roth"])


def test_duplicate_debt_name_is_rejected() -> None:
    debt = {"name": "card", "balance": 100, "apr": 20, "payment": 10}
    with pytest.raises(PlanError, match="unique"):
        make_plan(debts=[debt, debt])


def test_plan_needs_income() -> None:
    with pytest.raises(PlanError, match="income"):
        make_plan(income=[])


def test_top_level_must_be_a_mapping() -> None:
    with pytest.raises(PlanError, match="mapping"):
        parse_plan("- just\n- a list\n")


def test_invalid_yaml_is_a_plan_error() -> None:
    with pytest.raises(PlanError, match="invalid YAML"):
        parse_plan("name: [unclosed\n")


def test_bad_fixture_reports_every_field_path() -> None:
    with pytest.raises(PlanError) as caught:
        load_plan(FIXTURES / "bad_plan.yaml")
    message = str(caught.value)
    assert "start: " in message
    assert "debts.0.apr: " in message
    assert "favourite_colour: " in message


def test_missing_file_is_a_plan_error(tmp_path: Path) -> None:
    with pytest.raises(PlanError, match="cannot read"):
        load_plan(tmp_path / "nope.yaml")


def test_dump_then_parse_round_trips(demo_plan: Plan) -> None:
    assert parse_plan(dump_plan(demo_plan)) == demo_plan


def test_dump_writes_months_and_whole_numbers_plainly(demo_plan: Plan) -> None:
    text = dump_plan(demo_plan)
    assert "start: 2027-01" in text
    assert "horizon_months: 60" in text
    assert "apr: 23.9" in text
