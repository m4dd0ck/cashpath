"""Run a plan with and without one recurring monthly change, for side-by-side comparison."""

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from cashpath.engine import Forecast, forecast
from cashpath.errors import PlanError
from cashpath.plan import Plan, plan_from_data
from cashpath.units import format_month, parse_month, to_decimal

ZERO = Decimal("0")
ROW_NAME = "simulation"


@dataclass(frozen=True)
class Change:
    """Extra take-home income and/or spending each month from `start` to `end` inclusive.

    `start` None means the plan's first month; `end` None means no end.
    """

    income: Decimal
    expense: Decimal
    start: dt.date | None = None
    end: dt.date | None = None


@dataclass(frozen=True)
class Simulation:
    """The plan's forecast next to the forecast with the change applied."""

    change: Change
    plan: Forecast
    simulated: Forecast


def parse_change(
    income: float | None, expense: float | None, start: str | None, end: str | None
) -> Change:
    """Build a change from command-line options.

    Raises:
        PlanError: If no amount is given, an amount is negative, or a month is invalid.
    """
    amounts = {
        option: _amount(option, value)
        for option, value in (("--income", income), ("--expense", expense))
    }
    if all(value == 0 for value in amounts.values()):
        raise PlanError("give --income, --expense or both")
    first, last = _month("--start", start), _month("--end", end)
    if first is not None and last is not None and last < first:
        raise PlanError(f"--end {format_month(last)} is before --start {format_month(first)}")
    return Change(amounts["--income"], amounts["--expense"], first, last)


def _amount(option: str, value: float | None) -> Decimal:
    amount = ZERO if value is None else Decimal(to_decimal(value))
    if amount < 0:
        raise PlanError(f"{option} must be 0 or more")
    return amount


def _month(option: str, value: str | None) -> dt.date | None:
    if value is None:
        return None
    try:
        month: dt.date = parse_month(value)
    except ValueError as error:
        raise PlanError(f"{option}: {error}") from None
    return month


def apply_change(plan: Plan, change: Change) -> Plan:
    """Return a copy of the plan with the change added as `simulation` income and expense rows.

    Raises:
        PlanError: If the change starts before the plan or ends before it starts.
    """
    start = change.start or plan.start
    if start < plan.start:
        raise PlanError(
            f"--start {format_month(start)} is before the plan starts ({format_month(plan.start)})"
        )
    if change.end is not None and change.end < start:
        raise PlanError(f"--end {format_month(change.end)} is before {format_month(start)}")
    data = plan.model_dump(mode="python")
    row: dict[str, Any] = {"name": ROW_NAME, "start": start}
    if change.end is not None:
        row["end"] = change.end
    if change.income > 0:
        data["income"].append({**row, "amount": change.income})
    if change.expense > 0:
        data["expenses"].append({**row, "amount": change.expense})
    return plan_from_data(data)


def describe_change(plan: Plan, change: Change) -> str:
    """One line for the report header, e.g. "+$3,000/mo income from 2027-01"."""
    parts = [
        f"+${_whole_or_cents(amount)}/mo {label}"
        for label, amount in (("income", change.income), ("expense", change.expense))
        if amount > 0
    ]
    start = format_month(change.start or plan.start)
    if change.end is None:
        return f"{', '.join(parts)} from {start}"
    return f"{', '.join(parts)}, {start} to {format_month(change.end)}"


def _whole_or_cents(amount: Decimal) -> str:
    return f"{amount:,.0f}" if amount == amount.to_integral_value() else f"{amount:,.2f}"


def simulate(plan: Plan, change: Change) -> Simulation:
    """Forecast the plan as it is and with the change applied.

    Raises:
        PlanError: If the change does not fit the plan.
    """
    return Simulation(change, forecast(plan), forecast(apply_change(plan, change)))
