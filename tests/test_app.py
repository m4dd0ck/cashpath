from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from cashpath.plan import PLAN_ENV

ROOT = Path(__file__).resolve().parent.parent
APP = str(ROOT / "streamlit_app.py")


def run_app() -> AppTest:
    return AppTest.from_file(APP, default_timeout=30).run()


def metric_value(app: AppTest, label: str) -> str:
    return next(metric.value for metric in app.metric if metric.label == label)


def test_demo_plan_renders_without_errors() -> None:
    app = run_app()
    assert not app.exception
    assert not app.error
    assert metric_value(app, "Net worth in 5 years").startswith("$")


def test_changing_the_401k_slider_changes_the_forecast() -> None:
    app = run_app()
    before = metric_value(app, "Net worth in 5 years")
    slider = next(s for s in app.sidebar.slider if s.label.startswith("401k contribution"))
    slider.set_value(15.0).run()
    assert not app.exception
    assert metric_value(app, "Net worth in 5 years") != before
    assert any("vs saved" in str(metric.delta) for metric in app.metric)


def test_emptying_priorities_keeps_the_page_working() -> None:
    app = run_app()
    app.sidebar.multiselect[0].set_value([]).run()
    assert not app.exception


def test_local_plan_from_environment_is_offered(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    plan = tmp_path / "mine.yaml"
    plan.write_text(
        "name: Local test\nstart: 2027-01\nhorizon_months: 12\n"
        "income: [{name: pay, amount: 1000}]\n",
        encoding="utf-8",
    )
    monkeypatch.setenv(PLAN_ENV, str(plan))
    app = run_app()
    assert not app.exception
    assert app.sidebar.radio[0].value == "Local file: mine.yaml"
    assert metric_value(app, "Net worth in 1 year") == "$12,000"


def test_untouched_editors_leave_the_what_if_equal_to_the_saved_plan() -> None:
    app = run_app()
    assert len(app.tabs) == 3
    assert all(not metric.delta for metric in app.metric)
