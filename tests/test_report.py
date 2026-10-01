import datetime as dt
from decimal import Decimal

from cashpath.engine import forecast
from cashpath.plan import Plan
from cashpath.report import debt_free_date, ledger_records, snapshots
from tests.conftest import make_plan


def test_snapshots_stop_at_the_horizon() -> None:
    result = forecast(make_plan(horizon_months=24))
    assert [label for label, _ in snapshots(result)] == [
        "start",
        "3 months",
        "6 months",
        "1 year",
        "2 years",
    ]


def test_snapshot_is_the_end_of_that_month() -> None:
    result = forecast(make_plan(horizon_months=12))
    assert dict(snapshots(result))["1 year"] is result.rows[11]


def test_demo_has_every_snapshot(demo_plan: Plan) -> None:
    assert [label for label, _ in snapshots(forecast(demo_plan))][-1] == "5 years"


def test_debt_free_date_is_the_last_payoff() -> None:
    debts = [
        {"name": "a", "balance": 100, "apr": 0, "payment": 100},
        {"name": "b", "balance": 300, "apr": 0, "payment": 100},
    ]
    assert debt_free_date(forecast(make_plan(debts=debts))) == dt.date(2027, 3, 1)


def test_debt_free_date_is_none_when_a_debt_outlives_the_horizon() -> None:
    debts = [{"name": "a", "balance": 50000, "apr": 5, "payment": 100}]
    assert debt_free_date(forecast(make_plan(debts=debts))) is None


def test_ledger_has_a_column_per_debt() -> None:
    debts = [{"name": "car", "balance": 1000, "apr": 0, "payment": 100}]
    first = ledger_records(forecast(make_plan(debts=debts)))[0]
    assert first["month"] == "2027-01"
    assert first["debt: car"] == Decimal("900")
    assert first["net_worth"] == Decimal("2000")
