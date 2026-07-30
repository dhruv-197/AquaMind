"""Horizon unit conversion and validation for demand forecasts."""
from __future__ import annotations

from typing import Literal

ForecastUnit = Literal["days", "weeks", "months", "years"]

MAX_BY_UNIT: dict[str, int] = {
    "days": 365,
    "weeks": 52,
    "months": 24,
    "years": 5,
}

UNIT_TO_DAYS: dict[str, int] = {
    "days": 1,
    "weeks": 7,
    "months": 30,
    "years": 365,
}


class HorizonValidationError(ValueError):
    pass


def resolve_horizon_days(
    *,
    value: int | None = None,
    unit: str | None = None,
    horizon_days: int | None = None,
) -> tuple[int, int, str]:
    """
    Resolve forecast length to days.

    Returns (days, display_value, unit).
    Prefers value+unit when provided; falls back to horizon_days.
    """
    if value is not None and unit is not None:
        unit_key = str(unit).strip().lower()
        if unit_key not in MAX_BY_UNIT:
            raise HorizonValidationError(
                f"Invalid unit '{unit}'. Expected days|weeks|months|years."
            )
        try:
            v = int(value)
        except (TypeError, ValueError) as exc:
            raise HorizonValidationError("Forecast value must be an integer.") from exc
        if v < 1:
            raise HorizonValidationError("Forecast value must be at least 1.")
        max_v = MAX_BY_UNIT[unit_key]
        if v > max_v:
            raise HorizonValidationError(
                f"Maximum forecast for {unit_key} is {max_v}. "
                "Forecast confidence decreases as horizon increases."
            )
        days = v * UNIT_TO_DAYS[unit_key]
        # Hard ceiling: 5 years
        days = min(days, 5 * 365)
        return days, v, unit_key

    days = int(horizon_days or 7)
    if days < 1:
        raise HorizonValidationError("horizon_days must be >= 1")
    if days > 5 * 365:
        raise HorizonValidationError("Maximum forecast horizon is 5 years (1825 days).")
    return days, days, "days"
