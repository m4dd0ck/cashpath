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
from cashpath.units import format_month

app = typer.Typer(help="Budget forecasts from one YAML plan.", add_completion=False)
console = Console()
error_console = Console(stderr=True)
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


def print_forecast(result: Forecast) -> None:
    """Render a forecast as text tables."""
    end = format_month(result.rows[-1].month)
    console.print(
        f"[bold]cashpath: {escape(result.plan.name)}[/bold]   "
        f"{format_month(result.plan.start)} to {end}\n"
    )
    if result.plan.debts:
        debts = Table(title="Debt-free dates", title_justify="left")
        for column in ("debt", "APR", "paid off"):
            debts.add_column(column, justify="left" if column == "debt" else "right")
        for debt in result.plan.debts:
            month = result.payoff[debt.name]
            left = result.rows[-1].debts[debt.name]
            paid_off = format_month(month) if month else f"after {end} ({_dollars(left)} left)"
            debts.add_row(escape(debt.name), f"{debt.apr}%", paid_off)
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
    console.print("Net worth counts cash and investments minus debt, not cars or homes.\n")

    if not result.warnings:
        console.print("Warnings: none")
        return
    console.print("[yellow]Warnings[/yellow]")
    for warning in result.warnings:
        console.print(f"  {escape(warning)}")
