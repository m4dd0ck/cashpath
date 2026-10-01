"""Summaries of a forecast: snapshots, debt-free dates and flat ledger records."""

import datetime as dt
from decimal import Decimal

from cashpath.engine import Forecast, MonthRow
from cashpath.units import format_month

SNAPSHOT_MONTHS: tuple[tuple[int, str], ...] = (
    (3, "3 months"),
    (6, "6 months"),
    (12, "1 year"),
    (24, "2 years"),
    (36, "3 years"),
    (60, "5 years"),
)


def snapshots(result: Forecast) -> list[tuple[str, MonthRow]]:
    """Opening balances plus end-of-month balances at the standard checkpoints in the horizon."""
    checkpoints = [
        (label, result.rows[months - 1])
        for months, label in SNAPSHOT_MONTHS
        if months <= len(result.rows)
    ]
    return [("start", result.opening), *checkpoints]


def debt_free_date(result: Forecast) -> dt.date | None:
    """The month the last debt is paid off, or None if any debt outlives the horizon."""
    if not result.payoff:
        return result.plan.start
    if any(month is None for month in result.payoff.values()):
        return None
    return max(month for month in result.payoff.values() if month is not None)


def ledger_records(result: Forecast) -> list[dict[str, str | Decimal]]:
    """One flat record per month, with a column per debt, for tables and CSV export."""
    records: list[dict[str, str | Decimal]] = []
    for row in result.rows:
        record: dict[str, str | Decimal] = {
            "month": format_month(row.month),
            "take_home": row.take_home,
            "spending": row.spending,
            "one_time": row.one_time,
            "to_extra_debt": row.to_extra_debt,
            "to_roth": row.to_roth,
            "to_brokerage": row.to_brokerage,
            "cash": row.cash,
        }
        record.update({f"debt: {name}": balance for name, balance in row.debts.items()})
        record.update(
            {
                "total_debt": row.total_debt,
                "401k": row.retirement,
                "roth": row.roth,
                "brokerage": row.brokerage,
                "net_worth": row.net_worth,
            }
        )
        records.append(record)
    return records
