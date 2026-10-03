from pathlib import Path

from typer.testing import CliRunner

from cashpath.cli import app

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
