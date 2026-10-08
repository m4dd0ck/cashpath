"""Build a what-if plan from the saved plan plus edits made in the app."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from cashpath.plan import Plan, Priority, plan_from_data


@dataclass(frozen=True)
class Controls:
    """Values from the app's sidebar. `contribution_pct` is None when the plan has no 401k."""

    contribution_pct: Decimal | None
    investment_return_pct: Decimal
    annual_raise_pct: Decimal
    cash_floor: Decimal
    emergency_fund: Decimal
    priorities: Sequence[Priority]


def build_whatif(
    saved: Plan, controls: Controls, tables: Mapping[str, list[dict[str, Any]]] | None = None
) -> Plan:
    """Apply sidebar values and edited tables to a copy of the saved plan.

    Args:
        saved: The plan as loaded from YAML.
        controls: Sidebar values.
        tables: Edited rows keyed by plan field (income, expenses, debts, one_time).

    Returns:
        The validated what-if plan.

    Raises:
        PlanError: If the edits make the plan invalid.
    """
    data = saved.model_dump(mode="python")
    data["settings"].update(
        investment_return_pct=controls.investment_return_pct,
        annual_raise_pct=controls.annual_raise_pct,
        cash_floor=controls.cash_floor,
        emergency_fund=controls.emergency_fund,
    )
    if controls.contribution_pct is not None and data["retirement"] is not None:
        data["retirement"]["contribution_pct"] = controls.contribution_pct
    data["priorities"] = list(controls.priorities)
    if tables:
        data.update({field: clean_rows(rows) for field, rows in tables.items()})
    return plan_from_data(data)


def clean_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop blank cells so model defaults apply, and drop rows left with nothing in them."""
    cleaned = []
    for row in rows:
        kept = {
            key: value.strip() if isinstance(value, str) else value
            for key, value in row.items()
            if value is not None and not (isinstance(value, str) and not value.strip())
        }
        if kept:
            cleaned.append(kept)
    return cleaned
