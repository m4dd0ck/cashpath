import datetime as dt
from decimal import Decimal
from typing import Any

from cashpath.engine import forecast
from cashpath.plan import Plan
from tests.conftest import make_plan


def plan_with(cash: int, income: int = 0, **overrides: Any) -> Plan:
    settings = {"investment_return_pct": 0, **overrides.pop("settings", {})}
    return make_plan(
        balances={"cash": cash},
        income=[{"name": "paycheck", "amount": income}],
        settings=settings,
        **overrides,
    )


def test_cash_floor_is_never_spent() -> None:
    first = forecast(plan_with(5000, settings={"cash_floor": 2000}, priorities=["brokerage"])).rows[
        0
    ]
    assert (first.cash, first.to_brokerage) == (Decimal("2000"), Decimal("3000"))


def test_nothing_runs_until_cash_clears_the_floor() -> None:
    plan = plan_with(0, income=500, settings={"cash_floor": 1000}, priorities=["brokerage"])
    assert [row.to_brokerage for row in forecast(plan).rows[:3]] == [0, 0, 500]


def test_emergency_fund_first_holds_cash_back_from_debt() -> None:
    debts = [{"name": "card", "balance": 5000, "apr": 20, "payment": 100}]
    settings = {"cash_floor": 1000, "emergency_fund": 6000}
    fund_first = plan_with(
        10000, settings=settings, debts=debts, priorities=["emergency_fund", "extra_debt"]
    )
    debt_first = plan_with(
        10000, settings=settings, debts=debts, priorities=["extra_debt", "emergency_fund"]
    )
    assert forecast(fund_first).rows[0].to_extra_debt == Decimal("3900")
    # Whole card: 5000 + 83.33 interest - 100 scheduled payment.
    assert forecast(debt_first).rows[0].to_extra_debt == Decimal("4983.33")


def test_extra_debt_pays_highest_apr_first_and_skips_low_apr() -> None:
    debts = [
        {"name": "mid", "balance": 1000, "apr": 10, "payment": 10},
        {"name": "high", "balance": 1000, "apr": 25, "payment": 10},
        {"name": "low", "balance": 1000, "apr": 5, "payment": 10},
    ]
    result = forecast(
        plan_with(1500, settings={"extra_debt_min_apr": 8}, debts=debts, priorities=["extra_debt"])
    )
    first = result.rows[0]
    assert result.payoff["high"] == dt.date(2027, 1, 1)
    assert first.debts["mid"] == Decimal("539.16")  # 1008.33 - 10 - 459.17 left after "high"
    assert first.debts["low"] == Decimal("994.17")  # scheduled payment only
    assert first.to_extra_debt == Decimal("1470.00")


def test_roth_limit_resets_each_january() -> None:
    plan = plan_with(
        0, income=600, start="2027-07", settings={"roth_annual_limit": 1000}, priorities=["roth"]
    )
    to_roth = [row.to_roth for row in forecast(plan).rows]
    assert to_roth[:6] == [600, 400, 0, 0, 0, 0]
    # Cash piled up while the 2027 limit was used, so January fills the new limit at once.
    assert to_roth[6] == 1000


def test_brokerage_takes_what_the_roth_cannot() -> None:
    plan = plan_with(
        0, income=600, settings={"roth_annual_limit": 1000}, priorities=["roth", "brokerage"]
    )
    second = forecast(plan).rows[1]
    assert (second.to_roth, second.to_brokerage) == (Decimal("400"), Decimal("200"))


def test_without_priorities_cash_just_accumulates() -> None:
    rows = forecast(plan_with(0, income=3000)).rows
    assert [row.cash for row in rows[:2]] == [3000, 6000]


def test_negative_cash_month_skips_priorities() -> None:
    plan = plan_with(
        0, income=100, expenses=[{"name": "rent", "amount": 200}], priorities=["brokerage"]
    )
    first = forecast(plan).rows[0]
    assert (first.cash, first.to_brokerage) == (Decimal("-100"), Decimal("0"))
