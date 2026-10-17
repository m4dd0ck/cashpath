import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from cashpath.cli import APP_SCRIPT, app
from cashpath.plan import DEMO_PLAN, PLAN_ENV

FIXTURES = Path(__file__).parent / "fixtures"
runner = CliRunner()


def test_forecast_defaults_to_the_demo_plan() -> None:
    result = runner.invoke(app, ["forecast"])
    assert result.exit_code == 0
    assert "cashpath: Sam (demo)" in result.output
    assert "Debt-free dates" in result.output
    assert "5 years" in result.output


def test_bad_plan_exits_2_with_field_paths() -> None:
    result = runner.invoke(app, ["forecast", str(FIXTURES / "bad_plan.yaml")])
    assert result.exit_code == 2
    assert "debts.0.apr" in result.output


def test_unpaid_debt_shows_what_is_left(tmp_path: Path) -> None:
    plan = tmp_path / "plan.yaml"
    plan.write_text(
        "name: Slow\nstart: 2027-01\nhorizon_months: 3\n"
        "income: [{name: pay, amount: 1000}]\n"
        "debts: [{name: loan, balance: 1000, apr: 0, payment: 100}]\n",
        encoding="utf-8",
    )
    result = runner.invoke(app, ["forecast", str(plan)])
    assert "after 2027-03 (700 left)" in result.output


def test_app_command_runs_streamlit_with_the_plan_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[list[str], dict[str, str]]] = []

    def fake_run(command: list[str], env: dict[str, str], check: bool) -> SimpleNamespace:
        calls.append((command, env))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = runner.invoke(app, ["app", str(DEMO_PLAN)])
    assert result.exit_code == 0
    command, env = calls[0]
    assert command[1:4] == ["-m", "streamlit", "run"]
    assert command[4] == str(APP_SCRIPT)
    assert env[PLAN_ENV] == str(DEMO_PLAN)


def test_app_command_refuses_a_bad_plan() -> None:
    result = runner.invoke(app, ["app", str(FIXTURES / "bad_plan.yaml")])
    assert result.exit_code == 2
