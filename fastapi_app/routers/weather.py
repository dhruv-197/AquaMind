"""Hydro-meteorological weather API — DB snapshot + Open-Meteo 5-day forecast."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from fastapi_app.core.security import get_current_user
from fastapi_app.core.ttl_cache import (
    WEATHER_TTL_SEC,
    cached_threaded,
    stable_key,
    weather_cache,
)
from fastapi_app.database.connection import SessionLocal, get_db
from fastapi_app.database.models import Weather
from fastapi_app.schemas import WeatherData, WeatherResponse

router = APIRouter(tags=["Hydro-Meteorological Telemetry"], dependencies=[Depends(get_current_user)])


def _open_meteo_forecast(lat: float = 28.614, lon: float = 77.209) -> list[dict]:
    try:
        from climate.wsi_climate import forecast_5_day_from_open_meteo

        days = forecast_5_day_from_open_meteo(lat, lon)
        if days:
            return days
    except Exception as exc:
        print(f"[weather] Open-Meteo forecast unavailable: {exc}")
    return [
        {
            "day": "n/a",
            "high_c": None,
            "low_c": None,
            "precipitation_prob": 0,
            "condition": "Forecast unavailable — check Open-Meteo connectivity",
            "source": "fallback",
        }
    ]


def _build_weather_payload(location: Optional[str], lat: float, lon: float) -> dict[str, Any]:
    """Sync builder with its own DB session (safe for worker threads)."""
    db = SessionLocal()
    try:
        db_weather = None
        if location:
            db_weather = db.query(Weather).filter(Weather.location == location).first()
        if not db_weather:
            db_weather = db.query(Weather).order_by(Weather.recorded_at.desc()).first()

        if not db_weather:
            data = WeatherData(
                location=location or "Metropolitan Watershed Region A",
                temperature_c=38.5,
                humidity_pct=34.0,
                precipitation_mm=0.2,
                rainfall_deficit_pct=-42.5,
                heatwave_warning=True,
                uv_index=9.4,
                evapotranspiration_rate_mm=6.8,
                forecast_5_day=_open_meteo_forecast(lat, lon),
            )
        else:
            data = WeatherData(
                location=db_weather.location,
                temperature_c=db_weather.temperature_c,
                humidity_pct=db_weather.humidity_pct,
                precipitation_mm=db_weather.precipitation_mm,
                rainfall_deficit_pct=db_weather.rainfall_deficit_pct,
                heatwave_warning=db_weather.heatwave_warning,
                uv_index=db_weather.uv_index,
                evapotranspiration_rate_mm=db_weather.evapotranspiration_rate_mm,
                forecast_5_day=_open_meteo_forecast(lat, lon),
            )
        return data.model_dump()
    finally:
        db.close()


@router.get(
    "/weather",
    response_model=WeatherResponse,
    status_code=status.HTTP_200_OK,
    summary="Get watershed weather + Open-Meteo 5-day forecast",
    description="Cached briefly (~120s). Open-Meteo also has a separate disk TTL cache.",
)
async def get_weather(
    location: Optional[str] = Query("Metropolitan Watershed Region A", description="Location name"),
    lat: float = Query(28.614, description="Latitude for Open-Meteo forecast"),
    lon: float = Query(77.209, description="Longitude for Open-Meteo forecast"),
    force_refresh: bool = Query(False, description="Bypass short-lived weather cache"),
    _db: Session = Depends(get_db),
):
    key = f"weather:{stable_key(location, round(lat, 3), round(lon, 3))}"
    payload = await cached_threaded(
        weather_cache,
        key,
        lambda: _build_weather_payload(location, lat, lon),
        ttl_seconds=WEATHER_TTL_SEC,
        force_refresh=force_refresh,
    )
    return WeatherResponse(data=WeatherData.model_validate(payload))
