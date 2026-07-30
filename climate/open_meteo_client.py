"""Live Open-Meteo clients: forecast, ERA5 archive, GloFAS flood discharge."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Optional

import httpx

from climate.cache import read_cache, write_cache

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
FLOOD_URL = "https://flood-api.open-meteo.com/v1/flood"
TIMEOUT = 45.0


def _round_coord(v: float) -> float:
    return round(float(v), 3)


async def fetch_forecast(lat: float, lon: float) -> dict[str, Any]:
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
        "hourly": ",".join(
            [
                "precipitation",
                "soil_moisture_0_to_7cm",
                "soil_moisture_7_to_28cm",
            ]
        ),
    }
    cached = read_cache("forecast", params)
    if cached is not None:
        cached["_from_cache"] = True
        return cached

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        res = await client.get(FORECAST_URL, params=params)
        res.raise_for_status()
        body = res.json()

    body["_from_cache"] = False
    write_cache("forecast", params, body)
    return body


async def fetch_archive(lat: float, lon: float, years: int = 12) -> dict[str, Any]:
    """Multi-year daily precip / temp / soil moisture for climatology."""
    lat, lon = _round_coord(lat), _round_coord(lon)
    end = date.today() - timedelta(days=5)  # archive lag
    start = date(end.year - years, end.month, 1)
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "timezone": "auto",
        "daily": ",".join(
            [
                "precipitation_sum",
                "temperature_2m_max",
                "temperature_2m_min",
                "et0_fao_evapotranspiration",
            ]
        ),
    }
    cached = read_cache("archive", params)
    if cached is not None:
        cached["_from_cache"] = True
        return cached

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        res = await client.get(ARCHIVE_URL, params=params)
        res.raise_for_status()
        body = res.json()

    body["_from_cache"] = False
    write_cache("archive", params, body)
    return body


async def fetch_flood(lat: float, lon: float, past_days: int = 90, forecast_days: int = 30) -> dict[str, Any]:
    lat, lon = _round_coord(lat), _round_coord(lon)
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "river_discharge",
        "past_days": past_days,
        "forecast_days": forecast_days,
    }
    cached = read_cache("flood", params)
    if cached is not None:
        cached["_from_cache"] = True
        return cached

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        res = await client.get(FLOOD_URL, params=params)
        res.raise_for_status()
        body = res.json()

    body["_from_cache"] = False
    write_cache("flood", params, body)
    return body


async def ping_upstreams() -> dict[str, Any]:
    """Lightweight reachability probe (Delhi coordinates)."""
    lat, lon = 28.6139, 77.2090
    results: dict[str, Any] = {}
    async with httpx.AsyncClient(timeout=15.0) as client:
        for name, url, params in [
            (
                "forecast",
                FORECAST_URL,
                {"latitude": lat, "longitude": lon, "daily": "precipitation_sum", "forecast_days": 1},
            ),
            (
                "flood",
                FLOOD_URL,
                {"latitude": lat, "longitude": lon, "daily": "river_discharge", "forecast_days": 1, "past_days": 1},
            ),
        ]:
            try:
                r = await client.get(url, params=params)
                results[name] = {"ok": r.status_code == 200, "status": r.status_code}
            except Exception as exc:  # noqa: BLE001
                results[name] = {"ok": False, "error": str(exc)}
    return results
