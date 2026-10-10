import datetime as dt
import math
from decimal import Decimal

from cashpath.engine import forecast
from tests.conftest import make_plan

JAN = dt.date(2027, 1, 1)


def debt(name: str, balance: int, apr: float, payment: int) -> dict[str, object]:
    return {"name": name, "balance": balance, "apr": apr, "payment": payment}


def test_payoff_month_matches_closed_form_amortization() -> None:
    plan = make_plan(horizon_months=36, debts=[debt("loan", 8400, 18.9, 380)])
    rate = 0.189 / 12
    payments = math.ceil(-math.log(1 - rate * 8400 / 380) / math.log(1 + rate))
    result = forecast(plan)
    assert payments == 28
    assert result.payoff["loan"] == dt.date(2029, 4, 1)  # payment 28 lands in month index 27


def test_last_payment_is_capped_at_balance_plus_interest() -> None:
    result = forecast(make_plan(debts=[debt("loan", 240, 18, 400)]))
    first = result.rows[0]
    assert first.spending == Decimal("243.60")
    assert first.debts["loan"] == Decimal("0.00")
    assert result.payoff["loan"] == JAN


def test_paid_off_debt_stops_costing_money() -> None:
    result = forecast(make_plan(debts=[debt("loan", 240, 18, 400)]))
    assert result.rows[1].spending == 0
    assert result.rows[1].cash - result.rows[0].cash == 3000


def test_zero_interest_loan_ends_after_balance_over_payment_months() -> None:
    result = forecast(make_plan(debts=[debt("loan", 360, 0, 120)]))
    assert result.payoff["loan"] == dt.date(2027, 3, 1)


def test_unpaid_debt_has_no_payoff_month() -> None:
    result = forecast(make_plan(debts=[debt("loan", 50000, 5, 100)]))
    assert result.payoff["loan"] is None


def test_expense_applies_only_between_start_and_end() -> None:
    expense = {"name": "gym", "amount": 100, "start": "2027-03", "end": "2027-04"}
    result = forecast(make_plan(expenses=[expense]))
    assert [row.spending for row in result.rows[:6]] == [0, 0, 100, 100, 0, 0]


def test_one_time_item_lands_in_its_month_only() -> None:
    item = {"name": "trip", "month": "2027-02", "amount": -500}
    result = forecast(make_plan(one_time=[item]))
    assert [row.one_time for row in result.rows[:3]] == [0, -500, 0]
    assert result.rows[1].cash == Decimal("5500")


def test_raise_applies_from_the_first_january_after_start() -> None:
    plan = make_plan(
        start="2027-07",
        settings={"investment_return_pct": 0, "annual_raise_pct": 10},
        income=[{"name": "paycheck", "amount": 1000}],
    )
    take_home = [row.take_home for row in forecast(plan).rows]
    assert take_home[5] == 1000  # December 2027
    assert take_home[6] == 1100  # January 2028


def test_retirement_contribution_match_and_take_home_cost() -> None:
    plan = make_plan(
        income=[{"name": "paycheck", "amount": 4900}],
        retirement={
            "gross_salary": 79000,
            "contribution_pct": 6,
            "match_pct": 50,
            "match_up_to_pct": 6,
            "marginal_tax_pct": 25,
        },
    )
    first = forecast(plan).rows[0]
    assert first.take_home == Decimal("4603.75")  # 4900 - 395.00 * 0.75
    assert first.retirement == Decimal("592.50")  # 395.00 contribution + 197.50 match


def test_match_is_capped_at_match_up_to_pct() -> None:
    plan = make_plan(
        retirement={
            "gross_salary": 120000,
            "contribution_pct": 10,
            "match_pct": 100,
            "match_up_to_pct": 4,
        },
    )
    assert forecast(plan).rows[0].retirement == Decimal("1400.00")  # 1000 + 400 match


def test_investments_grow_monthly() -> None:
    plan = make_plan(
        settings={"investment_return_pct": 12},
        balances={"brokerage": 1200, "roth": 100, "retirement": 1000},
    )
    first = forecast(plan).rows[0]
    assert (first.brokerage, first.roth, first.retirement) == (
        Decimal("1212.00"),
        Decimal("101.00"),
        Decimal("1010.00"),
    )


def test_cash_earns_yield_only_when_positive() -> None:
    plan = make_plan(
        settings={"investment_return_pct": 0, "cash_yield_pct": 12},
        balances={"cash": 1200},
    )
    assert forecast(plan).rows[0].cash == Decimal("4212.00")
    overspent = make_plan(
        settings={"investment_return_pct": 0, "cash_yield_pct": 12},
        expenses=[{"name": "rent", "amount": 3500}],
    )
    assert forecast(overspent).rows[1].cash == Decimal("-1000")


def test_negative_cash_month_is_flagged() -> None:
    plan = make_plan(horizon_months=2, expenses=[{"name": "rent", "amount": 3500}])
    assert forecast(plan).warnings == (
        "2027-01: cash short by $500.00",
        "2027-02: cash short by $1,000.00",
    )


def test_payment_below_interest_is_flagged_once() -> None:
    result = forecast(make_plan(debts=[debt("card", 10000, 24, 100)]))
    assert result.warnings == ("card: the $100.00 scheduled payment does not cover the interest",)
    assert result.rows[-1].debts["card"] > 10000


def test_net_worth_is_cash_plus_investments_minus_debt() -> None:
    result = forecast(make_plan(balances={"cash": 500}, debts=[debt("loan", 1000, 0, 100)]))
    assert result.opening.net_worth == Decimal("-500")
    first = result.rows[0]
    assert first.net_worth == first.cash - first.debts["loan"]
