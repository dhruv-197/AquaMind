"""Risk rules for water demand vs system capacity."""
from __future__ import annotations

from fastapi_app.core.contracts import RiskLevel


def demand_risk_level(predicted_demand_mgd: float, capacity_mgd: float) -> RiskLevel:
    """
    Demand > 95% capacity → HIGH
    Demand 80–95% capacity → MEDIUM (mapped to RiskLevel.MODERATE)
    Else → LOW
    """
    if capacity_mgd <= 0:
        return RiskLevel.UNKNOWN
    ratio = float(predicted_demand_mgd) / float(capacity_mgd)
    if ratio > 0.95:
        return RiskLevel.HIGH
    if ratio >= 0.80:
        return RiskLevel.MODERATE
    return RiskLevel.LOW


def risk_display_label(level: RiskLevel) -> str:
    if level == RiskLevel.MODERATE:
        return "MEDIUM"
    return level.value.upper()
