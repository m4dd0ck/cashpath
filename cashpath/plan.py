"""The budget plan: Pydantic models plus YAML load and dump."""

import datetime as dt
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from cashpath.errors import PlanError
from cashpath.units import (
    Money,
    Month,
    NonNegativeMoney,
    Pct,
    PositiveMoney,
    TaxPct,
    format_month,
)

# The demo ships inside the package so an installed copy finds it too.
DEMO_PLAN = Path(__file__).resolve().with_name("demo.yaml")
# The app reads its plan path from here; `cashpath app PLAN` sets it.
PLAN_ENV = "CASHPATH_PLAN"

Priority = Literal["extra_debt", "emergency_fund", "roth", "brokerage"]
PRIORITIES: tuple[Priority, ...] = ("extra_debt", "emergency_fund", "roth", "brokerage")


class _Model(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)


class Settings(_Model):
    """Assumptions and cash rules. Rates are percents; amounts are dollars."""

    investment_return_pct: Pct = Decimal("7")
    cash_yield_pct: Pct = Decimal("0")
    annual_raise_pct: Pct = Decimal("0")
    cash_floor: NonNegativeMoney = Decimal("0")
    emergency_fund: NonNegativeMoney = Decimal("0")
    roth_annual_limit: NonNegativeMoney = Decimal("7500")
    extra_debt_min_apr: Pct = Decimal("8")


class Balances(_Model):
    """Opening balances at the start of the first month."""

    cash: NonNegativeMoney = Decimal("0")
    retirement: NonNegativeMoney = Decimal("0")
    roth: NonNegativeMoney = Decimal("0")
    brokerage: NonNegativeMoney = Decimal("0")


class Retirement(_Model):
    """A pre-tax workplace plan (401k or similar) with an employer match."""

    gross_salary: PositiveMoney
    contribution_pct: Pct
    match_pct: Pct = Decimal("0")
    match_up_to_pct: Pct = Decimal("0")
    marginal_tax_pct: TaxPct = Decimal("0")


class Recurring(_Model):
    """A monthly income or expense line, active from `start` to `end` inclusive."""

    name: str = Field(min_length=1)
    amount: NonNegativeMoney
    start: Month | None = None
    end: Month | None = None

    @model_validator(mode="after")
    def _end_not_before_start(self) -> Self:
        if self.start is not None and self.end is not None and self.end < self.start:
            raise ValueError(
                f"end {format_month(self.end)} is before start {format_month(self.start)}"
            )
        return self

    def is_active(self, month: dt.date) -> bool:
        """Return whether this line applies in `month`."""
        after_start = self.start is None or self.start <= month
        before_end = self.end is None or month <= self.end
        return after_start and before_end


class Debt(_Model):
    """A debt paid monthly. `apr` is a percent; `payment` is the scheduled monthly payment."""

    name: str = Field(min_length=1)
    balance: PositiveMoney
    apr: Pct
    payment: PositiveMoney


class OneTime(_Model):
    """A single amount in one month: positive is money in, negative is money out."""

    name: str = Field(min_length=1)
    month: Month
    amount: Money


class Plan(_Model):
    """A whole budget plan, as written in YAML."""

    name: str = Field(min_length=1)
    start: Month
    horizon_months: int = Field(ge=1, le=600)
    settings: Settings = Settings()
    balances: Balances = Balances()
    retirement: Retirement | None = None
    income: list[Recurring] = Field(min_length=1)
    expenses: list[Recurring] = []
    debts: list[Debt] = []
    one_time: list[OneTime] = []
    priorities: list[Priority] = []

    @model_validator(mode="after")
    def _unique_names_and_priorities(self) -> Self:
        debt_names = [debt.name for debt in self.debts]
        if len(set(debt_names)) != len(debt_names):
            raise ValueError("debt names must be unique")
        if len(set(self.priorities)) != len(self.priorities):
            raise ValueError("each priority can appear only once")
        return self


def _format_errors(error: ValidationError) -> str:
    parts = []
    for item in error.errors():
        location = ".".join(str(part) for part in item["loc"]) or "plan"
        parts.append(f"{location}: {item['msg']}")
    return "; ".join(parts)


def plan_from_data(data: Any) -> Plan:
    """Validate already-parsed plan data.

    Raises:
        PlanError: If the data is not a mapping or fails validation.
    """
    if not isinstance(data, dict):
        raise PlanError("a plan must be a mapping of fields (name, start, income, ...)")
    try:
        return Plan.model_validate(data)
    except ValidationError as error:
        raise PlanError(_format_errors(error)) from None


def parse_plan(text: str) -> Plan:
    """Parse and validate a plan from YAML text.

    Raises:
        PlanError: If the YAML is invalid or the plan fails validation.
    """
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as error:
        raise PlanError(f"invalid YAML: {error}") from None
    return plan_from_data(data)


def load_plan(path: Path) -> Plan:
    """Read, parse and validate a plan file.

    Raises:
        PlanError: If the file cannot be read or the plan is invalid.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise PlanError(f"cannot read {path}: {error.strerror}") from None
    try:
        return parse_plan(text)
    except PlanError as error:
        raise PlanError(f"{path}: {error}") from None


def _to_yaml_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, dt.date):
        return format_month(value)
    if isinstance(value, dict):
        return {key: _to_yaml_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_yaml_value(item) for item in value]
    return value


def dump_plan(plan: Plan) -> str:
    """Serialize a plan back to YAML that `parse_plan` reads to an equal plan."""
    data = _to_yaml_value(plan.model_dump(mode="python", exclude_none=True))
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
