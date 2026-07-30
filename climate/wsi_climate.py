"""Sync Open-Meteo climate context for Water Stress Index fusion.

Uses the same disk cache as the async climate clients so dashboard WSI
requests do not hammer upstream APIs.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Optional

import httpx

from climate.cache import read_cache, write_cache
from climate.heatwave import analyze_heatwave
from climate.spi_proxy import rainfall_deficit_pct, spi3_proxy

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
TIMEOUT = 30.0

# Default basin anchor (Delhi NCT) when no reservoir coords are available.
DEFAULT_LAT = 28.614
DEFAULT_LON = 77.209


def _round_coord(v: float) -> float:
    return round(float(v), 3)


def _get_json(url: str, params: dict[str, Any], namespace: str) -> dict[str, Any]:
    cached = read_cache(namespace, params)
    if cached is not None:
        return cached
    with httpx.Client(timeout=TIMEOUT) as client:
        res = client.get(url, params=params)
        res.raise_for_status()
        body = res.json()
    write_cache(namespace, params, body)
    return body


def fetch_forecast_sync(lat: float, lon: float) -> dict[str, Any]:
    lat, lon = _round_coord(lat), _round_coord(lon)
    params = {
        "latitude": lat,
        "longitude": lon,
        "timezone": "auto",
        "forecast_days": 7,
        "past_days": 7,
        "daily": ",".join(
            [
                "precipitation_sum",
                "temperature_2m_max",
                "temperature_2m_min",
                "et0_fao_evapotranspiration",
                "rain_sum",
            ]
        ),
        "hourly": "relative_humidity_2m,precipitation",
    }
    return _get_json(FORECAST_URL, params, "forecast")


def fetch_archive_sync(lat: float, lon: float, years: int = 12) -> dict[str, Any]:
    lat, lon = _round_coord(lat), _round_coord(lon)
    end = date.today() - timedelta(days=5)
    start = date(end.year - years, end.month, 1)
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "timezone": "auto",
        "daily": "precipitation_sum,temperature_2m_max,temperature_2m_min,et0_fao_evapotranspiration",
    }
    return _get_json(ARCHIVE_URL, params, "archive")


def build_wsi_climate_context(
    lat: float = DEFAULT_LAT,
    lon: float = DEFAULT_LON,
) -> dict[str, Any]:
    """Return SPI / deficit / heat fields ready for compute_water_stress_index."""
    try:
        forecast = fetch_forecast_sync(lat, lon)
        archive = fetch_archive_sync(lat, lon)
    except Exception as exc:
        return {
            "spi3_proxy": None,
            "rainfall_deficit_pct": 0.0,
            "heatwave_warning": False,
            "temperature_c": 32.0,
            "source": "open_meteo_unavailable",
            "error": str(exc),
        }

    a_daily = archive.get("daily") or {}
    f_daily = forecast.get("daily") or {}
    a_dates = a_daily.get("time") or []
    a_precip = a_daily.get("precipitation_sum") or []
    f_dates = f_daily.get("time") or []
    f_tmax = f_daily.get("temperature_2m_max") or []

    spi = spi3_proxy(a_dates, a_precip)
    deficit = rainfall_deficit_pct(a_dates, a_precip, season_days=90)
    heat = analyze_heatwave(f_dates, f_tmax)

    # Climate module deficit_pct: positive = drier than normal.
    # Shortage model rainfall_deficit_pct: negative = drier. Bridge both.
    deficit_pct = deficit.get("deficit_pct")
    rainfall_anomaly = -float(deficit_pct) if deficit_pct is not None else 0.0

    tmax_vals = [float(x) for x in f_tmax if x is not None]
    temp_c = tmax_vals[0] if tmax_vals else 32.0

    return {
        "spi3_proxy": spi.get("spi3_proxy"),
        "spi_class": spi.get("class"),
        "rainfall_deficit_pct": rainfall_anomaly,
        "dry_anomaly_pct": float(deficit_pct) if deficit_pct is not None else None,
        "heatwave_warning": bool(heat.get("active")),
        "temperature_c": round(temp_c, 1),
        "lat": _round_coord(lat),
        "lon": _round_coord(lon),
        "source": "open_meteo_sync",
        "method": "SPI-3 z-score proxy + 90d rainfall deficit + heatwave streak",
    }


def forecast_5_day_from_open_meteo(
    lat: float = DEFAULT_LAT,
    lon: float = DEFAULT_LON,
) -> list[dict[str, Any]]:
    """Build a 5-day forecast list for the /weather API response."""
    try:
        forecast = fetch_forecast_sync(lat, lon)
    except Exception:
        return []

    daily = forecast.get("daily") or {}
    times = daily.get("time") or []
    highs = daily.get("temperature_2m_max") or []
    lows = daily.get("temperature_2m_min") or []
    precip = daily.get("precipitation_sum") or []

    out: list[dict[str, Any]] = []
    for i, day in enumerate(times[:5]):
        high = highs[i] if i < len(highs) else None
        low = lows[i] if i < len(lows) else None
        rain = precip[i] if i < len(precip) else 0.0
        try:
            weekday = date.fromisoformat(str(day)[:10]).strftime("%a")
        except ValueError:
            weekday = f"D{i + 1}"
        rain_f = float(rain or 0.0)
        if rain_f >= 10:
            condition = "Heavy rain likely"
        elif rain_f >= 2:
            condition = "Showers"
        elif high is not None and float(high) >= 40:
            condition = "Excessive heat"
        elif high is not None and float(high) >= 36:
            condition = "Hot / dry"
        else:
            condition = "Fair"
        out.append(
            {
                "day": weekday,
                "date": str(day)[:10],
                "high_c": round(float(high), 1) if high is not None else None,
                "low_c": round(float(low), 1) if low is not None else None,
                "precipitation_mm": round(rain_f, 1),
                "precipitation_prob": min(95, int(rain_f * 8)),
                "condition": condition,
                "source": "open_meteo",
            }
        )
    return out
