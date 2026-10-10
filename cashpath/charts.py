"""Altair charts for the app: net worth (saved vs what-if) and debt balances.

Colors come from the dataviz reference palette: categorical slots in fixed order, the saved
plan in the muted neutral so the what-if line carries the emphasis.
"""

import datetime as dt
from collections.abc import Iterator
from typing import Literal

import altair as alt
import pandas as pd

from cashpath.engine import Forecast, MonthRow
from cashpath.units import add_months

Mode = Literal["light", "dark"]

SERIES = {
    "light": [
        "#2a78d6",
        "#eb6834",
        "#1baf7a",
        "#eda100",
        "#e87ba4",
        "#008300",
        "#6250d6",
        "#e34948",
    ],
    "dark": [
        "#3987e5",
        "#d95926",
        "#199e70",
        "#c98500",
        "#d55181",
        "#008300",
        "#9085e9",
        "#e66767",
    ],
}
MUTED = "#898781"
BASELINE = {"light": "#c3c2b7", "dark": "#383835"}
MONEY_FORMAT = "$,.0f"


def _dated_rows(result: Forecast) -> Iterator[tuple[str, MonthRow]]:
    """Opening balances on the first day, each month's row on its last day."""
    # Reason: opening and month-one rows share a month; plotting both there draws a false cliff.
    yield result.opening.month.isoformat(), result.opening
    for row in result.rows:
        yield (add_months(row.month, 1) - dt.timedelta(days=1)).isoformat(), row


def _hover_layers(frame: pd.DataFrame, series: list[str], mode: Mode) -> list[alt.Chart]:
    """Crosshair rule with a tooltip listing every series for the hovered month."""
    hover = alt.selection_point(fields=["month"], nearest=True, on="pointerover", empty=False)
    wide = alt.Chart(frame).transform_pivot("series", value="value", groupby=["month"])
    rule = (
        wide.mark_rule(color=BASELINE[mode], strokeWidth=1)
        .encode(
            x="month:T",
            opacity=alt.condition(hover, alt.value(1), alt.value(0)),
            tooltip=[alt.Tooltip("month:T", title="date", format="%b %-d, %Y")]
            + [
                # Reason: Vega reads dots in a field name as nesting, so escape them.
                alt.Tooltip(
                    field=name.replace(".", "\\."),
                    type="quantitative",
                    title=name,
                    format=MONEY_FORMAT,
                )
                for name in series
            ],
        )
        .add_params(hover)
    )
    points = (
        alt.Chart(frame)
        .mark_point(size=64, filled=True)
        .encode(
            x="month:T",
            y="value:Q",
            color=alt.Color("series:N", legend=None),
            opacity=alt.condition(hover, alt.value(1), alt.value(0)),
        )
        .transform_filter(hover)
    )
    return [rule, points]


def _line_chart(frame: pd.DataFrame, colors: list[str], title: str, mode: Mode) -> alt.LayerChart:
    series = list(dict.fromkeys(frame["series"]))
    legend = alt.Legend(title=None, orient="top") if len(series) > 1 else None
    lines = (
        alt.Chart(frame)
        .mark_line(strokeWidth=2, strokeCap="round", strokeJoin="round")
        .encode(
            x=alt.X("month:T", title=None, axis=alt.Axis(format="%Y", tickCount="year")),
            y=alt.Y("value:Q", title=None, axis=alt.Axis(format=MONEY_FORMAT)),
            color=alt.Color(
                "series:N", scale=alt.Scale(domain=series, range=colors), legend=legend
            ),
        )
    )
    zero = (
        alt.Chart(pd.DataFrame({"value": [0]}))
        .mark_rule(color=BASELINE[mode], strokeWidth=1)
        .encode(y="value:Q")
    )
    return alt.LayerChart(
        layer=[zero, lines, *_hover_layers(frame, series, mode)], title=title, height=320
    )


def net_worth_chart(saved: Forecast, whatif: Forecast | None, mode: Mode) -> alt.LayerChart:
    """Net worth by month; the what-if line only appears when it differs from the saved plan."""
    runs = [("Saved plan", saved)] + ([("What-if", whatif)] if whatif is not None else [])
    frame = pd.DataFrame(
        [
            {"month": date, "series": name, "value": float(row.net_worth)}
            for name, result in runs
            for date, row in _dated_rows(result)
        ]
    )
    colors = [MUTED, SERIES[mode][0]] if whatif is not None else [SERIES[mode][0]]
    return _line_chart(frame, colors, "Net worth (cash and investments minus debt)", mode)


def debt_chart(result: Forecast, mode: Mode) -> alt.LayerChart:
    """Each debt's balance by month, one categorical slot per debt in plan order."""
    names = [debt.name for debt in result.plan.debts]
    palette = SERIES[mode]
    # Reason: the palette has eight validated slots; never generate or cycle a ninth hue.
    shown, folded = names[: len(palette) - 1], names[len(palette) - 1 :]
    if len(folded) == 1:
        shown, folded = names, []
    records = []
    for month, row in _dated_rows(result):
        records += [
            {"month": month, "series": name, "value": float(row.debts[name])} for name in shown
        ]
        if folded:
            other = sum(float(row.debts[name]) for name in folded)
            records.append({"month": month, "series": "other debts", "value": other})
    frame = pd.DataFrame(records)
    count = len(shown) + (1 if folded else 0)
    return _line_chart(frame, palette[:count], "Debt balances", mode)
