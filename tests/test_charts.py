from cashpath.charts import debt_chart, net_worth_chart
from cashpath.engine import forecast
from cashpath.plan import Plan
from tests.conftest import make_plan


def _colors(spec: dict[str, object]) -> list[str]:
    for layer in spec["layer"]:  # type: ignore[attr-defined]
        color = layer.get("encoding", {}).get("color", {})
        if "scale" in color:
            return list(color["scale"]["range"])
    raise AssertionError("no colored layer")


def test_single_plan_chart_has_one_series(demo_plan: Plan) -> None:
    spec = net_worth_chart(forecast(demo_plan), None, "light").to_dict()
    assert _colors(spec) == ["#2a78d6"]


def test_comparison_chart_mutes_the_saved_plan(demo_plan: Plan) -> None:
    result = forecast(demo_plan)
    spec = net_worth_chart(result, result, "dark").to_dict()
    assert _colors(spec) == ["#898781", "#3987e5"]


def test_debts_past_eight_fold_into_other() -> None:
    debts = [{"name": f"debt {n}", "balance": 100, "apr": 0, "payment": 10} for n in range(10)]
    spec = debt_chart(forecast(make_plan(debts=debts)), "light").to_dict()
    assert len(_colors(spec)) == 8
