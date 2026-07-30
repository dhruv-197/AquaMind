"""Risk rules for reservoir storage percentage."""
from __future__ import annotations

from fastapi_app.core.contracts import RiskLevel
from fastapi_app.prediction.models.reservoir.constants import (
    CRITICAL_STORAGE_PCT,
    HIGH_STORAGE_PCT,
    MODERATE_STORAGE_PCT,
)


def reservoir_risk_level(storage_pct: float) -> RiskLevel:
    """
    Critical  < 20%
    High      20–40%
    Moderate  40–60%
    Healthy   > 60%  → RiskLevel.LOW
    """
    pct = float(storage_pct)
    if pct < CRITICAL_STORAGE_PCT:
        return RiskLevel.CRITICAL
    if pct < HIGH_STORAGE_PCT:
        return RiskLevel.HIGH
    if pct < MODERATE_STORAGE_PCT:
        return RiskLevel.MODERATE
    return RiskLevel.LOW


def risk_display_label(level: RiskLevel) -> str:
    if level == RiskLevel.LOW:
        return "HEALTHY"
    if level == RiskLevel.MODERATE:
        return "MODERATE"
    if level == RiskLevel.HIGH:
        return "HIGH"
    if level == RiskLevel.CRITICAL:
        return "CRITICAL"
    return level.value.upper()


def storage_mcm_from_pct(storage_pct: float, capacity_mcm: float) -> float:
    return max(0.0, float(storage_pct) / 100.0 * float(capacity_mcm))


def remaining_usable_mcm(storage_pct: float, capacity_mcm: float) -> float:
    """Usable volume above the critical threshold."""
    usable_pct = max(0.0, float(storage_pct) - CRITICAL_STORAGE_PCT)
    return storage_mcm_from_pct(usable_pct, capacity_mcm)
