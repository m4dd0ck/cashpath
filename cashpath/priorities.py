"""Send leftover cash through the plan's priority list.

A reserve starts at the cash floor. Steps run in the plan's order and each may spend only
cash above the reserve:
- `emergency_fund` raises the reserve to the emergency-fund target (floor included);
- `extra_debt` prepays debts at or above the APR threshold, highest APR first;
- `roth` fills what is left of this calendar year's limit;
- `brokerage` takes everything above the reserve.
Whatever no step takes stays in cash.
"""

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal

from cashpath.plan import Plan
from cashpath.state import State

ZERO = Decimal("0")


@dataclass(frozen=True)
class Allocation:
    """Where leftover cash went in one month."""

    to_extra_debt: Decimal = ZERO
    to_roth: Decimal = ZERO
    to_brokerage: Decimal = ZERO


def apply_priorities(plan: Plan, state: State, month: dt.date) -> Allocation:
    """Move cash above the reserve into the plan's priorities, in order."""
    reserve = plan.settings.cash_floor
    to_extra_debt = to_roth = to_brokerage = ZERO
    for step in plan.priorities:
        if step == "emergency_fund":
            reserve = max(reserve, plan.settings.emergency_fund)
            continue
        available = state.cash - reserve
        if available <= 0:
            continue
        if step == "extra_debt":
            to_extra_debt += _prepay_debts(plan, state, month, available)
        elif step == "roth":
            to_roth += _fund_roth(plan, state, month, available)
        else:
            state.brokerage += available
            state.cash -= available
            to_brokerage += available
    return Allocation(to_extra_debt, to_roth, to_brokerage)


def _prepay_debts(plan: Plan, state: State, month: dt.date, available: Decimal) -> Decimal:
    eligible = [
        debt
        for debt in plan.debts
        if debt.apr >= plan.settings.extra_debt_min_apr and state.debts[debt.name] > 0
    ]
    paid = ZERO
    # Reason: sorted() is stable, so equal APRs keep the order they were listed in.
    for debt in sorted(eligible, key=lambda item: item.apr, reverse=True):
        payment = min(available - paid, state.debts[debt.name])
        if payment <= 0:
            break
        state.debts[debt.name] -= payment
        paid += payment
        if state.debts[debt.name] == 0:
            state.payoff[debt.name] = month
    state.cash -= paid
    return paid


def _fund_roth(plan: Plan, state: State, month: dt.date, available: Decimal) -> Decimal:
    already = state.roth_by_year.get(month.year, ZERO)
    payment = min(available, plan.settings.roth_annual_limit - already)
    if payment <= 0:
        return ZERO
    state.roth_by_year[month.year] = already + payment
    state.roth += payment
    state.cash -= payment
    return payment
