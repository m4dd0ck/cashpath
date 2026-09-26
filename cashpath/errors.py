"""Exception hierarchy for cashpath."""


class CashpathError(Exception):
    """Base class for every error cashpath raises on purpose."""


class PlanError(CashpathError):
    """The budget plan could not be read or failed validation."""
