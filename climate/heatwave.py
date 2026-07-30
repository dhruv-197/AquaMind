"""Heatwave detection from daily Tmax (IMD-style absolute threshold for India plains)."""
from __future__ import annotations

from typing import Any, Optional


def analyze_heatwave(
    dates: list[str],
    tmax: list[Optional[float]],
    threshold_c: float = 40.0,
    min_streak: int = 2,
) -> dict[str, Any]:
    """
    Flag consecutive days with Tmax >= threshold.
    Default 40°C is a common plains heatwave marker (not station-specific IMD criteria).
    """
    streak = 0
    max_streak = 0
    heat_days = 0
    active = False
    recent_tmax: list[dict[str, Any]] = []

    for d, t in zip(dates, tmax):
        if t is None:
            streak = 0
            continue
        recent_tmax.append({"date": d[:10], "tmax_c": round(float(t), 1)})
        if float(t) >= threshold_c:
            streak += 1
            heat_days += 1
            max_streak = max(max_streak, streak)
        else:
            streak = 0

    if recent_tmax:
        # active if last day(s) meet streak
        tail = recent_tmax[-min_streak:] if len(recent_tmax) >= min_streak else recent_tmax
        active = all(x["tmax_c"] >= threshold_c for x in tail) and len(tail) >= min_streak

    intensity = 0.0
    if recent_tmax:
        excess = [max(0.0, x["tmax_c"] - threshold_c) for x in recent_tmax[-7:]]
        intensity = round(sum(excess) / max(len(excess), 1), 2)

    return {
        "active": active,
        "threshold_c": threshold_c,
        "heat_days_in_window": heat_days,
        "max_streak_days": max_streak,
        "intensity_score": intensity,
        "leak_priority_multiplier": round(1.0 + min(intensity, 5.0) * 0.08, 2) if active or intensity > 0 else 1.0,
        "recent_tmax": recent_tmax[-14:],
        "method": (
            f"Heatwave: consecutive daily Tmax ≥ {threshold_c}°C for ≥{min_streak} days "
            "(Open-Meteo daily temperature_2m_max). Intensity = mean excess °C over last 7 days."
        ),
    }
