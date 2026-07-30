"""Water Stress Index → risk taxonomy (product bands)."""
from __future__ import annotations

from fastapi_app.core.contracts import RiskLevel


def stress_risk_level(wsi: float) -> RiskLevel:
    """
    0–20   Healthy  → LOW (display HEALTHY)
    21–40  Low      → LOW
    41–60  Moderate → MODERATE
    61–80  High     → HIGH
    81–100 Critical → CRITICAL
    """
    score = float(wsi)
    if score >= 81:
        return RiskLevel.CRITICAL
    if score >= 61:
        return RiskLevel.HIGH
    if score >= 41:
        return RiskLevel.MODERATE
    return RiskLevel.LOW


def risk_display_label(wsi: float) -> str:
    score = float(wsi)
    if score >= 81:
        return "CRITICAL"
    if score >= 61:
        return "HIGH"
    if score >= 41:
        return "MODERATE"
    if score >= 21:
        return "LOW"
    return "HEALTHY"


def map_color(wsi: float) -> str:
    """Green → Yellow → Orange → Red → Dark Red."""
    score = float(wsi)
    if score >= 81:
        return "#7f1d1d"  # dark red
    if score >= 61:
        return "#dc2626"  # red
    if score >= 41:
        return "#ea580c"  # orange
    if score >= 21:
        return "#eab308"  # yellow
    return "#16a34a"  # green
