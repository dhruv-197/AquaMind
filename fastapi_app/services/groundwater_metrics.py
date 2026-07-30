"""Groundwater depletion metrics for ops dashboards and the Water Stress Index.

Works on CGWB well forecasts and optional 6-hourly telemetry samples. Does not
retrain the RandomForest groundwater model.
"""
from __future__ import annotations

from typing import Any, Sequence


CRITICAL_DEPTH_M = 40.0  # indicative ops threshold for deep urban wells


def depletion_rate_m_year(
    depth_series_m: Sequence[float],
    *,
    timestamps_days: Sequence[float] | None = None,
) -> float:
    """Linear depletion rate (m/year). Positive = water table falling (deeper).

    If timestamps_days is omitted, assumes evenly spaced observations spanning
    the series length in days equal to len-1 (caller should pass real spans).
    """
    depths = [float(d) for d in depth_series_m if d is not None]
    if len(depths) < 2:
        return 0.0

    if timestamps_days is not None and len(timestamps_days) == len(depths):
        t0 = float(timestamps_days[0])
        t1 = float(timestamps_days[-1])
        span_days = max(1.0, t1 - t0)
    else:
        span_days = float(max(1, len(depths) - 1))

    delta_m = depths[-1] - depths[0]
    return round(delta_m * (365.25 / span_days), 3)


def classify_trend(rate_m_year: float) -> str:
    if rate_m_year >= 3.0:
        return "Accelerating depletion"
    if rate_m_year >= 1.0:
        return "Moderate depletion"
    if rate_m_year >= 0.2:
        return "Slow decline"
    if rate_m_year > -0.2:
        return "Stable"
    return "Recharging"


def days_to_critical_threshold(
    current_depth_m: float,
    depletion_rate_m_year: float,
    *,
    critical_depth_m: float = CRITICAL_DEPTH_M,
) -> float | None:
    """Projected days until depth reaches critical threshold (None if not depleting toward it)."""
    current = float(current_depth_m)
    rate = float(depletion_rate_m_year)
    critical = float(critical_depth_m)
    if rate <= 0.05:
        return None
    if current >= critical:
        return 0.0
    remaining_m = critical - current
    years = remaining_m / rate
    return round(max(0.0, years * 365.25), 1)


def enrich_groundwater_prediction(
    groundwater: dict[str, Any],
    *,
    critical_depth_m: float = CRITICAL_DEPTH_M,
) -> dict[str, Any]:
    """Attach depletion horizon and trend fields to a GW prediction dict."""
    out = dict(groundwater)
    depth = float(out.get("projected_depth_m") or out.get("current_depth_m") or 25.0)
    # Prefer annual drawdown when present; model drawdown_rate_m may be observation-to-observation.
    rate = float(out.get("drawdown_rate_m") or out.get("depletion_rate_m_year") or 0.0)
    # If rate looks like a short-horizon delta (<0.5 m and labeled as observation change),
    # leave trend classification but still compute horizon conservatively.
    trend = out.get("depletion_trend") or classify_trend(rate)
    horizon = days_to_critical_threshold(depth, rate, critical_depth_m=critical_depth_m)

    out["depletion_rate_m_year"] = rate
    out["depletion_trend"] = trend
    out["days_to_critical_threshold"] = horizon
    out["critical_depth_m"] = critical_depth_m
    out["metrics_note"] = (
        "Depletion horizon is an indicative linear projection — not a hydrogeological simulation."
    )
    return out


def metrics_from_series(
    depth_series_m: Sequence[float],
    *,
    timestamps_days: Sequence[float] | None = None,
    critical_depth_m: float = CRITICAL_DEPTH_M,
) -> dict[str, Any]:
    """Build a metrics bundle from a raw depth time series."""
    depths = [float(d) for d in depth_series_m]
    rate = depletion_rate_m_year(depths, timestamps_days=timestamps_days)
    current = depths[-1] if depths else 0.0
    return {
        "projected_depth_m": round(current, 2),
        "depletion_rate_m_year": rate,
        "drawdown_rate_m": rate,
        "depletion_trend": classify_trend(rate),
        "days_to_critical_threshold": days_to_critical_threshold(
            current, rate, critical_depth_m=critical_depth_m
        ),
        "critical_depth_m": critical_depth_m,
        "samples": len(depths),
        "aquifer_status": (
            "Critical Over-Exploited"
            if rate >= 3.0 or current >= critical_depth_m
            else "Moderate Depletion"
            if rate >= 1.0
            else "Stable / Monitored"
        ),
    }
