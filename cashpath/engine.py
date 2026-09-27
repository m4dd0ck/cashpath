"""Month-by-month forecast of cash, debts and investment balances.

Each month runs in a fixed order:
1. growth on the 401k, Roth and brokerage, and yield on positive cash;
2. income in, after the pre-tax retirement contribution; the 401k gets contribution plus match;
3. active expenses out and one-time items in or out;
4. interest on each debt, then its scheduled payment (never more than what is owed);
5. if cash is negative the month is flagged; otherwise leftover cash goes through the priorities.
"""

import datetime as dt
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

from cashpath.plan import Plan
from cashpath.state import State
from cashpath.units import add_months, cents, format_month

ZERO = Decimal("0")


@dataclass(frozen=True)
class MonthRow:
    """End-of-month balances and the month's flows."""

    month: dt.date
    take_home: Decimal
    spending: Decimal
    one_time: Decimal
    to_extra_debt: Decimal
    to_roth: Decimal
    to_brokerage: Decimal
    cash: Decimal
    retirement: Decimal
    roth: Decimal
    brokerage: Decimal
    debts: Mapping[str, Decimal]

    @property
    def total_debt(self) -> Decimal:
        """Sum of every debt balance."""
        return sum(self.debts.values(), ZERO)

    @property
    def net_worth(self) -> Decimal:
        """Cash plus investments minus debt. Cars, homes and other assets are not counted."""
        return self.cash + self.retirement + self.roth + self.brokerage - self.total_debt


@dataclass(frozen=True)
class Forecast:
    """The result of running a plan: opening balances, one row per month, payoffs, warnings."""

    plan: Plan
    opening: MonthRow
    rows: tuple[MonthRow, ...]
    payoff: Mapping[str, dt.date | None]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class Allocation:
    """Where leftover cash went in one month."""

    to_extra_debt: Decimal = ZERO
    to_roth: Decimal = ZERO
    to_brokerage: Decimal = ZERO


def forecast(plan: Plan) -> Forecast:
    """Run the plan month by month over its horizon."""
    state = State.from_plan(plan)
    opening = _row(plan.start, state, ZERO, ZERO, ZERO, Allocation())
    warnings: list[str] = []
    rows = tuple(
        _run_month(plan, state, add_months(plan.start, index), warnings)
        for index in range(plan.horizon_months)
    )
    return Forecast(plan, opening, rows, dict(state.payoff), tuple(warnings))


def _run_month(plan: Plan, state: State, month: dt.date, warnings: list[str]) -> MonthRow:
    _grow(plan, state)
    take_home = _take_home(plan, state, month)
    expenses = sum((row.amount for row in plan.expenses if row.is_active(month)), ZERO)
    one_time = sum((item.amount for item in plan.one_time if item.month == month), ZERO)
    state.cash += take_home - expenses + one_time
    debt_payments = _pay_debts(plan, state, month, warnings)
    allocation = Allocation()
    if state.cash < 0:
        warnings.append(f"{format_month(month)}: cash short by ${-state.cash:,.2f}")
    return _row(month, state, take_home, expenses + debt_payments, one_time, allocation)


def _grow(plan: Plan, state: State) -> None:
    monthly_return = plan.settings.investment_return_pct / 1200
    state.retirement += cents(state.retirement * monthly_return)
    state.roth += cents(state.roth * monthly_return)
    state.brokerage += cents(state.brokerage * monthly_return)
    if state.cash > 0:
        state.cash += cents(state.cash * plan.settings.cash_yield_pct / 1200)


def _take_home(plan: Plan, state: State, month: dt.date) -> Decimal:
    """Income for the month after the retirement contribution; credits the 401k."""
    # Reason: raises land each January, so the factor depends only on calendar years elapsed.
    raise_factor = (1 + plan.settings.annual_raise_pct / 100) ** (month.year - plan.start.year)
    take_home = sum(
        (cents(row.amount * raise_factor) for row in plan.income if row.is_active(month)), ZERO
    )
    retirement = plan.retirement
    if retirement is None:
        return take_home
    gross_month = cents(retirement.gross_salary * raise_factor / 12)
    contribution = cents(gross_month * retirement.contribution_pct / 100)
    matched_pct = min(retirement.contribution_pct, retirement.match_up_to_pct)
    match = cents(gross_month * retirement.match_pct / 100 * matched_pct / 100)
    state.retirement += contribution + match
    # Reason: the contribution is pre-tax, so take-home only drops by its after-tax cost.
    return take_home - cents(contribution * (100 - retirement.marginal_tax_pct) / 100)


def _pay_debts(plan: Plan, state: State, month: dt.date, warnings: list[str]) -> Decimal:
    """Accrue interest and make each scheduled payment; return the total paid."""
    paid = ZERO
    for debt in plan.debts:
        balance = state.debts[debt.name]
        if balance == 0:
            continue
        owed = balance + cents(balance * debt.apr / 1200)
        payment = min(debt.payment, owed)
        state.debts[debt.name] = owed - payment
        state.cash -= payment
        paid += payment
        if owed == payment:
            state.payoff[debt.name] = month
        elif owed - payment > balance and debt.name not in state.growing_debts:
            state.growing_debts.add(debt.name)
            warnings.append(
                f"{debt.name}: the ${debt.payment:,.2f} payment does not cover interest, "
                "so the balance grows"
            )
    return paid


def _row(
    month: dt.date,
    state: State,
    take_home: Decimal,
    spending: Decimal,
    one_time: Decimal,
    allocation: Allocation,
) -> MonthRow:
    return MonthRow(
        month=month,
        take_home=take_home,
        spending=spending,
        one_time=one_time,
        to_extra_debt=allocation.to_extra_debt,
        to_roth=allocation.to_roth,
        to_brokerage=allocation.to_brokerage,
        cash=state.cash,
        retirement=state.retirement,
        roth=state.roth,
        brokerage=state.brokerage,
        debts=dict(state.debts),
    )
