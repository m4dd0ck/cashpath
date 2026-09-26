"""Money, percent and month types shared by the plan and the engine."""

import datetime as dt
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Annotated, Any

from pydantic import BeforeValidator, Field

CENT = Decimal("0.01")


def cents(value: Decimal) -> Decimal:
    """Round an amount to whole cents, halves away from zero."""
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def to_decimal(value: Any) -> Any:
    """Turn a YAML or widget number into an exact Decimal.

    Raises:
        ValueError: For booleans, non-numeric strings, NaN and infinity.
    """
    # Reason: bool is an int subclass, so `True` would otherwise become 1.
    if isinstance(value, bool):
        raise ValueError("expected a number, got a boolean")
    if isinstance(value, int | float | str):
        try:
            # Reason: Decimal(23.9) carries the float's binary error; str() keeps what was written.
            number = Decimal(str(value).strip())
        except InvalidOperation:
            raise ValueError(f"expected a number, got {value!r}") from None
        if not number.is_finite():
            raise ValueError(f"expected a finite number, got {value!r}")
        return number
    return value


def parse_month(value: Any) -> Any:
    """Accept "YYYY-MM" or a date on the 1st, return the date of the month's first day.

    Raises:
        ValueError: For any other string or a date that is not the 1st.
    """
    if isinstance(value, dt.datetime):
        raise ValueError("expected a month like 2027-06, got a timestamp")
    if isinstance(value, dt.date):
        if value.day != 1:
            raise ValueError(f"expected a month like 2027-06, got the date {value.isoformat()}")
        return value
    if isinstance(value, str):
        try:
            return dt.datetime.strptime(value.strip(), "%Y-%m").date()
        except ValueError:
            raise ValueError(f"expected a month like 2027-06, got {value!r}") from None
    return value


Money = Annotated[Decimal, BeforeValidator(to_decimal)]
NonNegativeMoney = Annotated[Decimal, BeforeValidator(to_decimal), Field(ge=0)]
PositiveMoney = Annotated[Decimal, BeforeValidator(to_decimal), Field(gt=0)]
Pct = Annotated[Decimal, BeforeValidator(to_decimal), Field(ge=0, le=100)]
# Reason: a 100% marginal rate would make a pre-tax contribution free, which is never real.
TaxPct = Annotated[Decimal, BeforeValidator(to_decimal), Field(ge=0, lt=100)]
Month = Annotated[dt.date, BeforeValidator(parse_month)]


def add_months(month: dt.date, count: int) -> dt.date:
    """Return the first day of the month `count` months after `month`."""
    years, index = divmod(month.month - 1 + count, 12)
    return dt.date(month.year + years, index + 1, 1)


def format_month(month: dt.date) -> str:
    """Format a month as YYYY-MM."""
    return f"{month:%Y-%m}"
