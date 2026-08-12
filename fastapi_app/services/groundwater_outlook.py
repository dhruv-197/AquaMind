"""Climate-linked groundwater depth outlook (pilot projection).

Builds a past + future depth-to-water series from the nearest DB aquifer
(or a disclosed default), then modulates the depletion rate using rainfall
deficit, heatwave, and climate GW-stress scores from Climate Risk analyze.

This is NOT a CMIP / hydrogeological aquifer simulation.
"""
from __future__ import annotations

import math
from datetime import date
from typing import Any, Optional

from fastapi_app.services.groundwater_metrics import classify_trend

# Disclosed clamps for demo stability (m/year). Positive = table falling (deeper).
_MIN_RATE = -2.0
_MAX_RATE = 12.0
_DEFAULT_DEPTH_M = 28.0
_DEFAULT_RATE = 1.4
_PAST_MONTHS = 30
_FUTURE_MONTHS = 18


def climate_adjusted_rate(
    base_rate_m_year: float,
    *,
    rainfall_deficit_pct: float | None = None,
    heatwave_active: bool = False,
    gw_climate_stress_0_100: float | None = None,
) -> float:
    """Scale a depletion rate using climate anomaly + GW climate stress."""
    rate = float(base_rate_m_year)
    if rainfall_deficit_pct is not None:
        d = max(-50.0, min(80.0, float(rainfall_deficit_pct)))
        if d > 0:
            # Drier than normal → faster depletion (up to ~+40% at 80% deficit).
            rate *= 1.0 + d / 200.0
        else:
            # Wetter than normal → mild relief.
            rate *= 1.0 + d / 250.0
    if heatwave_active:
        rate *= 1.12
    if gw_climate_stress_0_100 is not None:
        s = max(0.0, min(100.0, float(gw_climate_stress_0_100)))
        rate *= 1.0 + s / 400.0  # up to +25% at stress 100
    return round(max(_MIN_RATE, min(_MAX_RATE, rate)), 3)


def _month_add(d: date, months: int) -> date:
    y = d.year
    m = d.month + months
    while m > 12:
        m -= 12
        y += 1
    while m < 1:
        m += 12
        y -= 1
    day = min(d.day, 28)
    return date(y, m, day)


def build_depth_series(
    *,
    current_depth_m: float,
    historical_rate_m_year: float,
    forecast_rate_m_year: float,
    as_of: date | None = None,
    past_months: int = _PAST_MONTHS,
    future_months: int = _FUTURE_MONTHS,
) -> list[dict[str, Any]]:
    """Monthly depth series with historical + forecast keys (join at as_of)."""
    anchor = as_of or date.today()
    hist_step = float(historical_rate_m_year) / 12.0
    fut_step = float(forecast_rate_m_year) / 12.0
    depth0 = float(current_depth_m)

    series: list[dict[str, Any]] = []
    for i in range(past_months, 0, -1):
        d = _month_add(anchor, -i)
        depth = max(0.5, depth0 - hist_step * i)
        series.append(
            {
                "date": d.isoformat()[:7],
                "historical": round(depth, 2),
                "forecast": None,
            }
        )

    series.append(
        {
            "date": anchor.isoformat()[:7],
            "historical": round(depth0, 2),
            "forecast": round(depth0, 2),
        }
    )

    for i in range(1, future_months + 1):
        d = _month_add(anchor, i)
        depth = max(0.5, depth0 + fut_step * i)
        series.append(
            {
                "date": d.isoformat()[:7],
                "historical": None,
                "forecast": round(depth, 2),
            }
        )
    return series


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def _pick_aquifer(lat: float, lon: float) -> Optional[Any]:
    """Nearest groundwater row with coordinates, if any."""
    try:
        from fastapi_app.database.connection import SessionLocal
        from fastapi_app.database.models import Groundwater
    except Exception:
        return None

    db = SessionLocal()
    try:
        rows = (
            db.query(Groundwater)
            .filter(Groundwater.location_lat.isnot(None), Groundwater.location_lng.isnot(None))
            .all()
        )
        if not rows:
            rows = db.query(Groundwater).all()
            return rows[0] if rows else None

        best = None
        best_d = float("inf")
        for row in rows:
            try:
                d = _haversine_km(lat, lon, float(row.location_lat), float(row.location_lng))
            except (TypeError, ValueError):
                continue
            if d < best_d:
                best_d = d
                best = row
        return best
    except Exception:
        return None
    finally:
        db.close()


def build_groundwater_outlook(
    *,
    lat: float,
    lon: float,
    rainfall_deficit_pct: float | None = None,
    heatwave_active: bool = False,
    gw_climate_stress_0_100: float | None = None,
    water_stress_index: float | None = None,
) -> dict[str, Any]:
    """Return chart-ready GW outlook for Climate Risk analyze."""
    aquifer = _pick_aquifer(lat, lon)
    station_name = None
    station_id = None
    distance_km = None
    source = "default_prior"

    if aquifer is not None:
        try:
            current = float(aquifer.depth_to_water_m)
            base_rate = float(aquifer.depletion_rate_m_year)
            station_name = aquifer.name
            station_id = str(aquifer.id)
            source = "groundwater_table"
            if aquifer.location_lat is not None and aquifer.location_lng is not None:
                distance_km = round(
                    _haversine_km(
                        lat, lon, float(aquifer.location_lat), float(aquifer.location_lng)
                    ),
                    1,
                )
        except (TypeError, ValueError):
            current, base_rate = _DEFAULT_DEPTH_M, _DEFAULT_RATE
            source = "default_prior"
    else:
        current, base_rate = _DEFAULT_DEPTH_M, _DEFAULT_RATE

    # Mild extra lift when system WSI is elevated (optional stress context).
    stress_boost = 0.0
    if water_stress_index is not None:
        w = max(0.0, min(100.0, float(water_stress_index)))
        stress_boost = w / 500.0  # up to +20%

    adjusted = climate_adjusted_rate(
        base_rate * (1.0 + stress_boost),
        rainfall_deficit_pct=rainfall_deficit_pct,
        heatwave_active=heatwave_active,
        gw_climate_stress_0_100=gw_climate_stress_0_100,
    )

    series = build_depth_series(
        current_depth_m=current,
        historical_rate_m_year=base_rate,
        forecast_rate_m_year=adjusted,
    )
    future_pts = [p for p in series if p.get("forecast") is not None and p.get("historical") is None]
    depth_12m = future_pts[min(11, len(future_pts) - 1)]["forecast"] if future_pts else current
    delta_12m = round(float(depth_12m) - float(current), 2)

    note = (
        "Pilot outlook: past depths are reconstructed from the station depletion rate; "
        "future depths apply a climate-adjusted rate (rainfall deficit, heat, GW climate stress). "
        "Not a hydrogeological or CMIP aquifer simulation."
    )
    if source == "default_prior":
        note = (
            "No nearby groundwater station with coordinates — using a disclosed default prior "
            f"({_DEFAULT_DEPTH_M} m, {_DEFAULT_RATE} m/yr), then climate-adjusted. " + note
        )

    return {
        "available": True,
        "unit": "metres_below_ground",
        "station_id": station_id,
        "station_name": station_name,
        "distance_km": distance_km,
        "source": source,
        "current_depth_m": round(float(current), 2),
        "depletion_rate_m_year": round(float(base_rate), 3),
        "climate_adjusted_rate_m_year": adjusted,
        "depletion_trend": classify_trend(adjusted),
        "projected_depth_12m": round(float(depth_12m), 2),
        "delta_depth_12m": delta_12m,
        "series": series,
        "note": note,
    }
