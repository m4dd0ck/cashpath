"""Command-line interface: print a forecast, or open the Streamlit app, for a plan file."""

import os
import subprocess
import sys
from decimal import Decimal
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.markup import escape
from rich.table import Table

from cashpath.engine import Forecast, forecast
from cashpath.errors import PlanError
from cashpath.plan import DEMO_PLAN, PLAN_ENV, Plan, load_plan
from cashpath.report import snapshots
from cashpath.simulate import Simulation, describe_change, parse_change, simulate
from cashpath.units import format_month

app = typer.Typer(help="Budget forecasts from one YAML plan.", add_completion=False)
console = Console()
error_console = Console(stderr=True)
NET_WORTH_NOTE = "Net worth counts cash and investments minus debt, not cars or homes.\n"
# Streamlit runs the module as a script; it is inside the package so installed copies have it.
APP_SCRIPT = Path(__file__).resolve().with_name("app.py")

PlanPath = Annotated[
    Path | None,
    typer.Argument(help="Plan YAML file. Defaults to the demo plan.", show_default=False),
]


@app.callback()
def main() -> None:
    """Budget forecasts from one YAML plan."""


@app.command("forecast")
def forecast_command(plan_path: PlanPath = None) -> None:
    """Print debt-free dates, balance snapshots and warnings for a plan."""
    result = forecast(load_plan_or_exit(plan_path or DEMO_PLAN))
    print_forecast(result)


@app.command("simulate")
def simulate_command(
    plan_path: PlanPath = None,
    income: Annotated[
        float | None,
        typer.Option(help="Extra take-home income per month (gets the annual raise)."),
    ] = None,
    expense: Annotated[float | None, typer.Option(help="Extra spending per month.")] = None,
    start: Annotated[
        str | None, typer.Option(help="First month, YYYY-MM. Defaults to the plan's start.")
    ] = None,
    end: Annotated[
        str | None, typer.Option(help="Last month, YYYY-MM. Defaults to no end.")
    ] = None,
) -> None:
    """Compare a plan with and without a recurring monthly income or expense change."""
    plan = load_plan_or_exit(plan_path or DEMO_PLAN)
    try:
        result = simulate(plan, parse_change(income, expense, start, end))
    except PlanError as error:
        error_console.print(f"[red]error:[/red] {escape(str(error))}")
        raise typer.Exit(code=2) from None
    print_simulation(result)


@app.command("app")
def app_command(plan_path: PlanPath = None) -> None:
    """Open the Streamlit app on a plan. Your plan file is read locally and never uploaded."""
    env = dict(os.environ)
    if plan_path is not None:
        load_plan_or_exit(plan_path)
        env[PLAN_ENV] = str(plan_path.resolve())
    command = [sys.executable, "-m", "streamlit", "run", str(APP_SCRIPT)]
    completed = subprocess.run(command, env=env, check=False)
    raise typer.Exit(code=completed.returncode)


def load_plan_or_exit(path: Path) -> Plan:
    """Load a plan, or print the validation errors and exit with status 2."""
    try:
        return load_plan(path)
    except PlanError as error:
        error_console.print(f"[red]error:[/red] {escape(str(error))}")
        raise typer.Exit(code=2) from None


def _dollars(value: Decimal) -> str:
    return f"{value:,.0f}"


def _paid_off(result: Forecast, debt_name: str) -> str:
    month = result.payoff[debt_name]
    if month:
        return format_month(month)
    left = result.rows[-1].debts[debt_name]
    return f"after {format_month(result.rows[-1].month)} ({_dollars(left)} left)"


def _print_header(result: Forecast) -> None:
    console.print(
        f"[bold]cashpath: {escape(result.plan.name)}[/bold]   "
        f"{format_month(result.plan.start)} to {format_month(result.rows[-1].month)}"
    )


def _print_warnings(warnings: tuple[str, ...], title: str = "Warnings") -> None:
    if not warnings:
        console.print(f"{title}: none")
        return
    console.print(f"[yellow]{title}[/yellow]")
    for warning in warnings:
        console.print(f"  {escape(warning)}")


def print_forecast(result: Forecast) -> None:
    """Render a forecast as text tables."""
    _print_header(result)
    console.print()
    if result.plan.debts:
        debts = Table(title="Debt-free dates", title_justify="left")
        for column in ("debt", "APR", "paid off"):
            debts.add_column(column, justify="left" if column == "debt" else "right")
        for debt in result.plan.debts:
            debts.add_row(escape(debt.name), f"{debt.apr}%", _paid_off(result, debt.name))
        console.print(debts)

    balances = Table(title="Balances", title_justify="left")
    for column in ("", "cash", "debt", "401k", "roth", "brokerage", "net worth"):
        balances.add_column(column, justify="left" if not column else "right")
    for label, row in snapshots(result):
        balances.add_row(
            label,
            *map(
                _dollars,
                (row.cash, row.total_debt, row.retirement, row.roth, row.brokerage, row.net_worth),
            ),
        )
    console.print(balances)
    console.print(NET_WORTH_NOTE)
    _print_warnings(result.warnings)


def print_simulation(result: Simulation) -> None:
    """Render the plan and the simulation side by side."""
    base, simulated = result.plan, result.simulated
    _print_header(base)
    console.print(f"Simulation: {escape(describe_change(base.plan, result.change))}\n")
    if base.plan.debts:
        debts = Table(title="Debt-free dates", title_justify="left")
        for column in ("debt", "APR", "plan", "simulation"):
            debts.add_column(column, justify="left" if column == "debt" else "right")
        for debt in base.plan.debts:
            debts.add_row(
                escape(debt.name),
                f"{debt.apr}%",
                _paid_off(base, debt.name),
                _paid_off(simulated, debt.name),
            )
        console.print(debts)

    net_worth = Table(title="Net worth", title_justify="left")
    for column in ("", "plan", "simulation", "change"):
        net_worth.add_column(column, justify="left" if not column else "right")
    for (label, row), (_, simulated_row) in zip(snapshots(base), snapshots(simulated), strict=True):
        change = simulated_row.net_worth - row.net_worth
        net_worth.add_row(
            label,
            _dollars(row.net_worth),
            _dollars(simulated_row.net_worth),
            f"{change:+,.0f}" if round(change) else "0",
        )
    console.print(net_worth)
    console.print(NET_WORTH_NOTE)
    _print_warnings(simulated.warnings, "Warnings (simulation)")
