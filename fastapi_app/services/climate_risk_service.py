"""Orchestrate Open-Meteo fetches + climate/flood/waterlogging analytics."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from climate.glofas_risk import analyze_glofas_flood
from climate.heatwave import analyze_heatwave
from climate.open_meteo_client import fetch_archive, fetch_flood, fetch_forecast, ping_upstreams
from climate.rules import build_recommendations
from climate.spi_proxy import rainfall_deficit_pct, spi3_proxy
from climate.waterbalance_ponding import estimate_waterlogging
from fastapi_app.services.groundwater_outlook import build_groundwater_outlook

PRESETS: list[dict[str, Any]] = [
    {
        "id": "delhi",
        "label": "Delhi NCT",
        "lat": 28.6139,
        "lon": 77.2090,
        "land_class": "urban",
        "notes": "National Capital Region — urban heat + Yamuna corridor discharge",
    },
    {
        "id": "mumbai",
        "label": "Mumbai (H-West)",
        "lat": 19.0760,
        "lon": 72.8777,
        "land_class": "urban",
        "notes": "Coastal metro — intense monsoon pluvial risk",
    },
    {
        "id": "bengaluru",
        "label": "Bengaluru East",
        "lat": 12.9716,
        "lon": 77.5946,
        "land_class": "peri_urban",
        "notes": "Plateau city — lake / stormwater stress",
    },
    {
        "id": "latur",
        "label": "Latur, Maharashtra",
        "lat": 18.4088,
        "lon": 76.5604,
        "land_class": "agricultural",
        "notes": "Drought-prone district — shortage / GW stress focus",
    },
    {
        "id": "jaipur",
        "label": "Jaipur / Thar fringe",
        "lat": 26.9124,
        "lon": 75.7873,
        "land_class": "urban",
        "notes": "Semi-arid — heat and rainfall deficit sensitivity",
    },
    {
        "id": "bhakra",
        "label": "Bhakra reservoir area",
        "lat": 31.4100,
        "lon": 76.4330,
        "land_class": "rural",
        "notes": "Major reservoir corridor — storage + river discharge context",
    },
]


def list_presets() -> list[dict[str, Any]]:
    return PRESETS


async def health_check() -> dict[str, Any]:
    upstreams = await ping_upstreams()
    ok = all(v.get("ok") for v in upstreams.values())
    return {
        "ok": ok,
        "upstreams": upstreams,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


def _series_tail(dates: list, values: list, n: int = 90) -> list[dict[str, Any]]:
    out = []
    for d, v in zip(dates[-n:], values[-n:]):
        if v is None:
            continue
        try:
            out.append({"date": str(d)[:10], "value": round(float(v), 2)})
        except (TypeError, ValueError):
            continue
    return out


def _soil_moisture_anomaly(forecast: dict[str, Any], archive: dict[str, Any]) -> dict[str, Any]:
    """Compare recent forecast SM to archive mean if archive lacks hourly SM (daily only)."""
    hourly = forecast.get("hourly") or {}
    sm = hourly.get("soil_moisture_0_to_7cm") or []
    recent = [float(x) for x in sm[-48:] if x is not None]
    if not recent:
        return {
            "anomaly_z": None,
            "recent_m3m3": None,
            "method": "No hourly soil_moisture in forecast response",
        }
    recent_mean = sum(recent) / len(recent)
    # Without long hourly archive, use forecast window std as weak baseline
    if len(recent) > 2:
        mu = sum(recent) / len(recent)
        var = sum((x - mu) ** 2 for x in recent) / len(recent)
        sigma = var ** 0.5
    else:
        mu, sigma = recent_mean, 0.05
    # Prefer comparing last 24h vs earlier part of the hourly series
    earlier = [float(x) for x in sm[:-48] if x is not None] or recent
    base_mu = sum(earlier) / len(earlier)
    base_sigma = (
        (sum((x - base_mu) ** 2 for x in earlier) / len(earlier)) ** 0.5 if len(earlier) > 2 else 0.05
    )
    z = 0.0 if base_sigma < 1e-6 else (recent_mean - base_mu) / base_sigma
    return {
        "anomaly_z": round(z, 2),
        "recent_m3m3": round(recent_mean, 4),
        "baseline_m3m3": round(base_mu, 4),
        "method": (
            "Soil moisture anomaly z-score: recent 48h mean soil_moisture_0_to_7cm "
            "vs earlier hours in the Open-Meteo forecast/past window (ERA5-Land fields)."
        ),
    }


def _et_stress(forecast: dict[str, Any], archive: dict[str, Any]) -> dict[str, Any]:
    f_daily = forecast.get("daily") or {}
    a_daily = archive.get("daily") or {}
    f_et = [float(x) for x in (f_daily.get("et0_fao_evapotranspiration") or []) if x is not None]
    a_et = [float(x) for x in (a_daily.get("et0_fao_evapotranspiration") or []) if x is not None]
    if not f_et:
        return {"et0_recent_mm_day": None, "et0_anomaly_pct": None, "method": "ET₀ unavailable"}
    recent = sum(f_et[-7:]) / min(7, len(f_et))
    if len(a_et) < 30:
        return {
            "et0_recent_mm_day": round(recent, 2),
            "et0_anomaly_pct": None,
            "method": "FAO ET₀ from Open-Meteo forecast; archive too short for anomaly",
        }
    # Same DOY-ish: use overall archive mean as climatology
    clim = sum(a_et) / len(a_et)
    anom = ((recent - clim) / clim * 100.0) if clim > 1e-6 else 0.0
    return {
        "et0_recent_mm_day": round(recent, 2),
        "et0_climatology_mm_day": round(clim, 2),
        "et0_anomaly_pct": round(anom, 1),
        "method": "FAO-56 ET₀ (Open-Meteo et0_fao_evapotranspiration); anomaly vs archive mean",
    }


def _drought_implication(spi: dict, deficit: dict, et: dict, heat: dict) -> dict[str, Any]:
    drivers = []
    shortage_stress = 0.0
    gw_stress = 0.0
    z = spi.get("spi3_proxy")
    if z is not None:
        if z <= -1.5:
            shortage_stress += 35
            gw_stress += 30
            drivers.append(f"Dry SPI-3 proxy ({z})")
        elif z <= -1.0:
            shortage_stress += 20
            gw_stress += 15
            drivers.append(f"Moderately dry SPI-3 proxy ({z})")
    d = deficit.get("deficit_pct")
    if d is not None and d > 0:
        shortage_stress += min(30, d * 0.4)
        gw_stress += min(25, d * 0.35)
        drivers.append(f"Rainfall deficit {d}%")
    et_anom = et.get("et0_anomaly_pct")
    if et_anom is not None and et_anom > 10:
        shortage_stress += min(20, et_anom * 0.25)
        drivers.append(f"Elevated ET₀ (+{et_anom}%)")
    if heat.get("active"):
        shortage_stress += 10
        drivers.append("Active heatwave conditions")

    shortage_stress = round(min(100.0, shortage_stress), 1)
    gw_stress = round(min(100.0, gw_stress), 1)
    return {
        "shortage_climate_stress_0_100": shortage_stress,
        "groundwater_climate_stress_0_100": gw_stress,
        "drivers": drivers,
        "summary": (
            "Climate drivers for existing shortage / groundwater modules "
            "(display + rules only in v1 — models not retrained)."
        ),
    }


async def analyze_location(
    lat: float,
    lon: float,
    label: Optional[str] = None,
    land_class: str = "urban",
) -> dict[str, Any]:
    forecast, archive, flood_raw = await _gather(lat, lon)

    a_daily = archive.get("daily") or {}
    f_daily = forecast.get("daily") or {}
    f_hourly = forecast.get("hourly") or {}

    a_dates = a_daily.get("time") or []
    a_precip = a_daily.get("precipitation_sum") or []
    f_dates = f_daily.get("time") or []
    f_tmax = f_daily.get("temperature_2m_max") or []

    spi = spi3_proxy(a_dates, a_precip)
    deficit = rainfall_deficit_pct(a_dates, a_precip, season_days=90)
    heat = analyze_heatwave(f_dates, f_tmax)
    et = _et_stress(forecast, archive)
    sm = _soil_moisture_anomaly(forecast, archive)
    flood = analyze_glofas_flood(flood_raw)
    ponding = estimate_waterlogging(
        f_hourly.get("precipitation") or [],
        f_hourly.get("soil_moisture_0_to_7cm") or [],
        f_hourly.get("soil_moisture_7_to_28cm") or [],
        land_class=land_class,
    )

    climate = {
        "spi3_proxy": spi,
        "rainfall_deficit": deficit,
        "heatwave": heat,
        "evapotranspiration": et,
        "soil_moisture": sm,
        "precip_series_mm": _series_tail(a_dates, a_precip, 120),
        "forecast_precip_mm": _series_tail(
            f_dates, f_daily.get("precipitation_sum") or [], 14
        ),
        "forecast_tmax_c": _series_tail(f_dates, f_tmax, 14),
    }

    drought = _drought_implication(spi, deficit, et, heat)
    recommendations = build_recommendations(climate, flood, ponding, heat)

    deficit_pct = deficit.get("deficit_pct")
    try:
        deficit_pct_f = float(deficit_pct) if deficit_pct is not None else None
    except (TypeError, ValueError):
        deficit_pct_f = None
    gw_outlook = build_groundwater_outlook(
        lat=lat,
        lon=lon,
        rainfall_deficit_pct=deficit_pct_f,
        heatwave_active=bool(heat.get("active")),
        gw_climate_stress_0_100=drought.get("groundwater_climate_stress_0_100"),
    )

    provenance = {
        "queried_at": datetime.now(timezone.utc).isoformat(),
        "location": {"lat": lat, "lon": lon, "label": label},
        "sources": [
            {
                "name": "Open-Meteo Forecast",
                "url": "https://api.open-meteo.com/v1/forecast",
                "cached": bool(forecast.get("_from_cache")),
            },
            {
                "name": "Open-Meteo Historical Archive (ERA5)",
                "url": "https://archive-api.open-meteo.com/v1/archive",
                "cached": bool(archive.get("_from_cache")),
            },
            {
                "name": "Open-Meteo Flood API (GloFAS)",
                "url": "https://flood-api.open-meteo.com/v1/flood",
                "cached": bool(flood_raw.get("_from_cache")),
            },
        ],
        "methods": [
            spi.get("method"),
            deficit.get("method"),
            heat.get("method"),
            et.get("method"),
            sm.get("method"),
            flood.get("method"),
            ponding.get("method"),
        ],
        "limitations": [
            "SPI-3 is a z-score proxy, not full WMO gamma SPI",
            "Waterlogging depth/duration are water-balance estimates, not DEM inundation",
            "GloFAS provides river discharge risk, not flooded area polygons",
            "Climate stress scores do not retrain shortage/GW models in v1",
            "Groundwater outlook is a climate-adjusted linear pilot — not CMIP aquifer modeling",
        ],
    }

    return {
        "success": True,
        "provenance": provenance,
        "climate": climate,
        "drought_implication": drought,
        "groundwater_outlook": gw_outlook,
        "flood": flood,
        "waterlogging": ponding,
        "recommendations": recommendations,
        "priority_queue": [
            {
                "asset": label or f"{lat:.3f},{lon:.3f}",
                "type": r["module"],
                "score": r["queue_score"],
                "action": r["action"],
                "href": r["href"],
            }
            for r in recommendations
        ],
        "links": {
            "shortage": "/shortage",
            "groundwater": "/groundwater",
            "leak_detection": "/leak-detection",
            "map": "/map",
            "dashboard": "/dashboard",
        },
    }


async def _gather(lat: float, lon: float):
    """Fetch upstreams; tolerate partial flood failure."""
    import asyncio

    forecast_t = asyncio.create_task(fetch_forecast(lat, lon))
    archive_t = asyncio.create_task(fetch_archive(lat, lon, years=12))
    flood_t = asyncio.create_task(fetch_flood(lat, lon))

    forecast = await forecast_t
    archive = await archive_t
    try:
        flood_raw = await flood_t
    except Exception as exc:  # noqa: BLE001
        flood_raw = {
            "daily": {"time": [], "river_discharge": []},
            "_error": str(exc),
            "_from_cache": False,
        }
    return forecast, archive, flood_raw
