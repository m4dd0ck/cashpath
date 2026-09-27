"""Running balances the engine updates month by month."""

import datetime as dt
from dataclasses import dataclass, field
from decimal import Decimal

from cashpath.plan import Plan


@dataclass
class State:
    """Mutable account balances plus the bookkeeping the monthly steps share."""

    cash: Decimal
    retirement: Decimal
    roth: Decimal
    brokerage: Decimal
    debts: dict[str, Decimal]
    payoff: dict[str, dt.date | None]
    roth_by_year: dict[int, Decimal] = field(default_factory=dict)
    growing_debts: set[str] = field(default_factory=set)

    @classmethod
    def from_plan(cls, plan: Plan) -> "State":
        """Start from the plan's opening balances."""
        return cls(
            cash=plan.balances.cash,
            retirement=plan.balances.retirement,
            roth=plan.balances.roth,
            brokerage=plan.balances.brokerage,
            debts={debt.name: debt.balance for debt in plan.debts},
            payoff={debt.name: None for debt in plan.debts},
        )
