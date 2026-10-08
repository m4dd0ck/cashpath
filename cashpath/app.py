"""Streamlit app: forecast a plan and compare it with a what-if built in the sidebar."""

import csv
import hashlib
import io
import os
from decimal import Decimal
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from cashpath.charts import Mode, debt_chart, net_worth_chart
from cashpath.engine import Forecast, forecast
from cashpath.errors import PlanError
from cashpath.plan import (
    DEMO_PLAN,
    PLAN_ENV,
    PRIORITIES,
    Plan,
    Priority,
    dump_plan,
    parse_plan,
)
from cashpath.report import debt_free_date, ledger_records, snapshots
from cashpath.units import format_month
from cashpath.whatif import Controls, build_whatif

DEMO_SOURCE = "Demo plan"
UPLOAD_SOURCE = "Upload YAML"
SHORTFALL_BACKGROUND = "background-color: rgba(208, 59, 59, 0.18)"


def main() -> None:
    """Render the whole page."""
    st.set_page_config(page_title="cashpath", layout="wide")
    loaded = choose_plan()
    if loaded is None:
        return
    saved, digest = loaded
    prefix = f"{digest}-{st.session_state.get('reset_count', 0)}-"
    controls = sidebar_controls(saved, prefix)

    forecast_tab, ledger_tab = st.tabs(["Forecast", "Month by month"])
    whatif = whatif_or_saved(saved, controls)
    saved_result, whatif_result = forecast(saved), forecast(whatif)
    changed = whatif != saved

    st.sidebar.download_button(
        "Download what-if as YAML",
        dump_plan(whatif),
        file_name="cashpath-plan.yaml",
        mime="application/x-yaml",
    )
    with forecast_tab:
        show_forecast(saved_result, whatif_result, changed)
    with ledger_tab:
        show_ledger(whatif_result)


def choose_plan() -> tuple[Plan, str] | None:
    """Pick the plan source in the sidebar and parse it; None while waiting for an upload."""
    st.sidebar.title("cashpath")
    local_path = os.environ.get(PLAN_ENV)
    sources = [DEMO_SOURCE, UPLOAD_SOURCE]
    if local_path:
        sources.insert(0, f"Local file: {Path(local_path).name}")
    source = st.sidebar.radio("Plan", sources)
    if source == UPLOAD_SOURCE:
        upload = st.sidebar.file_uploader("Plan file", type=["yaml", "yml"])
        if upload is None:
            st.info("Upload a plan YAML file. It stays in memory and is never stored.")
            return None
        raw = upload.getvalue()
    elif source == DEMO_SOURCE:
        raw = DEMO_PLAN.read_bytes()
    else:
        raw = Path(str(local_path)).read_bytes()
    try:
        plan = parse_plan(raw.decode("utf-8"))
    except (PlanError, UnicodeDecodeError) as error:
        st.error(f"This plan can't be used: {error}")
        return None
    return plan, hashlib.sha256(raw).hexdigest()[:12]


def _reset() -> None:
    st.session_state["reset_count"] = st.session_state.get("reset_count", 0) + 1


def _percent_slider(label: str, value: Decimal, top: float, key: str) -> Decimal:
    chosen = st.sidebar.slider(label, 0.0, max(top, float(value)), float(value), step=0.5, key=key)
    return Decimal(str(chosen))


def _dollar_input(label: str, value: Decimal, key: str) -> Decimal:
    chosen = st.sidebar.number_input(
        label, min_value=0.0, value=float(value), step=500.0, format="%.0f", key=key
    )
    return Decimal(str(chosen))


def priority_label(plan: Plan, step: Priority) -> str:
    """Human label for a priority step."""
    labels = {
        "extra_debt": f"Extra debt payments (APR ≥ {plan.settings.extra_debt_min_apr}%)",
        "emergency_fund": "Emergency fund",
        "roth": "Roth IRA",
        "brokerage": "Brokerage",
    }
    return labels[step]


def sidebar_controls(saved: Plan, prefix: str) -> Controls:
    """What-if settings, prefilled from the saved plan."""
    st.sidebar.header("What-if")
    settings = saved.settings
    contribution = None
    if saved.retirement is not None:
        contribution = _percent_slider(
            "401k contribution (% of salary)",
            saved.retirement.contribution_pct,
            30.0,
            prefix + "contribution",
        )
    investment_return = _percent_slider(
        "Investment return (% a year)", settings.investment_return_pct, 12.0, prefix + "return"
    )
    annual_raise = _percent_slider(
        "Annual raise (%)", settings.annual_raise_pct, 10.0, prefix + "raise"
    )
    cash_floor = _dollar_input("Cash floor ($)", settings.cash_floor, prefix + "floor")
    emergency_fund = _dollar_input(
        "Emergency fund target ($, floor included)", settings.emergency_fund, prefix + "fund"
    )
    priorities = st.sidebar.multiselect(
        "Where leftover cash goes, in order",
        PRIORITIES,
        default=saved.priorities,
        format_func=lambda step: priority_label(saved, step),
        help="Steps run top to bottom. Remove a step to turn it off; remove and re-add it "
        "to move it to the end. Cash no step takes stays in cash.",
        key=prefix + "priorities",
    )
    st.sidebar.button("Reset to saved plan", on_click=_reset)
    return Controls(
        contribution_pct=contribution,
        investment_return_pct=investment_return,
        annual_raise_pct=annual_raise,
        cash_floor=cash_floor,
        emergency_fund=emergency_fund,
        priorities=priorities,
    )


def whatif_or_saved(
    saved: Plan, controls: Controls, tables: dict[str, list[dict[str, Any]]] | None = None
) -> Plan:
    """The what-if plan, or the saved plan with an error shown if the edits are invalid."""
    try:
        return build_whatif(saved, controls, tables)
    except PlanError as error:
        st.error(f"The what-if edits are not valid, so the saved plan is shown: {error}")
        return saved


def theme_mode() -> Mode:
    """The viewer's light or dark theme, light when unknown."""
    return "dark" if st.context.theme.type == "dark" else "light"


def _money(value: Decimal) -> str:
    return f"${value:,.0f}"


def show_forecast(saved: Forecast, whatif: Forecast, changed: bool) -> None:
    """Headline numbers, charts, snapshot and debt tables, warnings."""
    end = format_month(whatif.rows[-1].month)
    debt_free = debt_free_date(whatif)
    saved_points = dict(snapshots(saved))
    whatif_points = dict(snapshots(whatif))
    last_label = next(reversed(whatif_points))

    columns = st.columns(4)
    columns[0].metric("Debt-free", format_month(debt_free) if debt_free else f"after {end}")
    for column, label in zip(columns[1:3], ("1 year", last_label), strict=True):
        if label not in whatif_points:
            continue
        value = whatif_points[label].net_worth
        delta = value - saved_points[label].net_worth
        column.metric(
            f"Net worth in {label}" if label != "start" else "Net worth now",
            _money(value),
            delta=f"{delta:+,.0f} vs saved" if changed else None,
        )
    columns[3].metric("Warnings", len(whatif.warnings))

    mode = theme_mode()
    st.altair_chart(net_worth_chart(saved, whatif if changed else None, mode))
    if whatif.plan.debts:
        st.altair_chart(debt_chart(whatif, mode))

    st.subheader("Balances")
    rows = []
    for label, row in whatif_points.items():
        record = {
            "": label,
            "cash": float(row.cash),
            "debt": float(row.total_debt),
            "401k": float(row.retirement),
            "roth": float(row.roth),
            "brokerage": float(row.brokerage),
            "net worth": float(row.net_worth),
        }
        if changed:
            record["net worth (saved plan)"] = float(saved_points[label].net_worth)
        rows.append(record)
    money_columns = {
        name: st.column_config.NumberColumn(format="dollar") for name in rows[0] if name
    }
    st.dataframe(rows, hide_index=True, column_config=money_columns)

    if whatif.plan.debts:
        st.subheader("Debt-free dates")
        st.dataframe(
            [
                {
                    "debt": debt.name,
                    "APR %": float(debt.apr),
                    "saved plan": _payoff(saved, debt.name),
                    "what-if": _payoff(whatif, debt.name),
                }
                for debt in whatif.plan.debts
            ],
            hide_index=True,
        )
    for warning in whatif.warnings:
        st.warning(warning, icon="⚠️")


def _payoff(result: Forecast, name: str) -> str:
    month = result.payoff.get(name)
    if name not in result.payoff:
        return "not in this plan"
    return format_month(month) if month else f"after {format_month(result.rows[-1].month)}"


def show_ledger(result: Forecast) -> None:
    """Every month as a table, shortfall months highlighted, with a CSV download."""
    records = ledger_records(result)
    frame = pd.DataFrame(
        [
            {key: float(value) if isinstance(value, Decimal) else value for key, value in r.items()}
            for r in records
        ]
    )
    styled = frame.style.apply(
        lambda row: [SHORTFALL_BACKGROUND if row["cash"] < 0 else ""] * len(row), axis=1
    ).format({column: "{:,.2f}" for column in frame.columns if column != "month"})
    st.caption("Months that end with negative cash are highlighted and listed under Warnings.")
    st.dataframe(styled, hide_index=True)
    st.download_button(
        "Download as CSV", ledger_csv(records), file_name="cashpath-ledger.csv", mime="text/csv"
    )


def ledger_csv(records: list[dict[str, str | Decimal]]) -> str:
    """Ledger records as CSV text, amounts written exactly."""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(records[0]))
    writer.writeheader()
    writer.writerows(records)
    return buffer.getvalue()
