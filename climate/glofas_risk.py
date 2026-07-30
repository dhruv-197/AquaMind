"""GloFAS river discharge flood risk via Open-Meteo Flood API percentiles."""
from __future__ import annotations

from typing import Any, Optional


def _finite(vals: list[Optional[float]]) -> list[float]:
    out: list[float] = []
    for v in vals:
        if v is None:
            continue
        try:
            fv = float(v)
        except (TypeError, ValueError):
            continue
        if fv == fv:  # not NaN
            out.append(fv)
    return out


def percentile_rank(value: float, sample: list[float]) -> float:
    if not sample:
        return 50.0
    below = sum(1 for x in sample if x <= value)
    return 100.0 * below / len(sample)


def analyze_glofas_flood(flood_payload: dict[str, Any]) -> dict[str, Any]:
    daily = flood_payload.get("daily") or {}
    dates = daily.get("time") or []
    discharge = daily.get("river_discharge") or []

    values = _finite(discharge)
    if len(values) < 10:
        return {
            "risk_class": "unknown",
            "percentile": None,
            "peak_m3s": None,
            "latest_m3s": None,
            "series": [],
            "forecast_window_days": 0,
            "exposure_radius_km": 5.0,
            "method": "Insufficient GloFAS river_discharge samples from Open-Meteo Flood API",
            "note": "GloFAS returns discharge for the largest river within ~5 km — not inundation area/depth",
        }

    # Split: Open-Meteo returns past then forecast in one series; use last 30 as "forecast-ish"
    # Better: use past_days portion as climatology and last forecast_days as forecast.
    # Without explicit split, treat all but last 30 as history when long enough.
    if len(values) > 40:
        history = values[:-30]
        forecast = values[-30:]
        forecast_dates = dates[-30:] if len(dates) >= 30 else dates
    else:
        history = values[: max(len(values) // 2, 1)]
        forecast = values[len(history) :]
        forecast_dates = dates[len(history) :]

    peak = max(forecast) if forecast else max(values)
    latest = forecast[-1] if forecast else values[-1]
    pct = percentile_rank(peak, history if history else values)

    if pct >= 98:
        risk = "extreme"
    elif pct >= 95:
        risk = "high"
    elif pct >= 90:
        risk = "elevated"
    elif pct >= 75:
        risk = "watch"
    else:
        risk = "low"

    series = []
    for d, q in zip(forecast_dates, forecast):
        if q is None:
            continue
        try:
            series.append({"date": str(d)[:10], "river_discharge_m3s": round(float(q), 2)})
        except (TypeError, ValueError):
            continue

    return {
        "risk_class": risk,
        "percentile": round(pct, 1),
        "peak_m3s": round(peak, 2),
        "latest_m3s": round(latest, 2),
        "history_samples": len(history),
        "series": series,
        "forecast_window_days": len(forecast),
        "exposure_radius_km": 5.0,
        "latitude": flood_payload.get("latitude"),
        "longitude": flood_payload.get("longitude"),
        "method": (
            "Fluvial flood risk from GloFAS river_discharge (Open-Meteo Flood API). "
            "Risk class from peak forecast discharge percentile vs recent local discharge history. "
            "Does NOT provide inundated area (km²) or water depth maps."
        ),
        "note": (
            "Indicative exposure ~5 km GloFAS cell around the query point. "
            "Not a DEM-based flood extent polygon."
        ),
    }
