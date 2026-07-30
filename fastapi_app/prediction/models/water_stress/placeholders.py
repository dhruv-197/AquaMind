"""Placeholder inputs for weather, groundwater, population, rainfall, historical stress.

These are NOT ML models and do not touch the prediction framework.
They provide graceful defaults when upstream forecasts are unavailable.
"""
from __future__ import annotations

from typing import Any


def weather_placeholder(*, temperature_c: float = 32.0, rainfall_mm: float = 4.5) -> dict[str, Any]:
    return {
        "source": "placeholder",
        "available": False,
        "temperature_c": temperature_c,
        "rainfall_mm": rainfall_mm,
        "note": "Weather forecast placeholder — live weather API not fused yet.",
    }


def groundwater_placeholder(*, depletion_rate_m_year: float = 1.4, projected_depth_m: float = 28.0) -> dict[str, Any]:
    return {
        "source": "placeholder",
        "available": False,
        "depletion_rate_m_year": depletion_rate_m_year,
        "projected_depth_m": projected_depth_m,
        "aquifer_status": "moderate",
        "note": "Groundwater forecast placeholder — use dedicated GW module when ready.",
    }


def rainfall_placeholder(*, rainfall_mm: float = 4.5, deficit_pct: float = 12.0) -> dict[str, Any]:
    return {
        "source": "placeholder",
        "available": False,
        "rainfall_mm": rainfall_mm,
        "deficit_pct": deficit_pct,
        "note": "Rainfall forecast placeholder.",
    }


def population_placeholder(*, population: int, growth_pct: float = 1.8) -> dict[str, Any]:
    return {
        "source": "regional_catalog",
        "available": True,
        "population": int(population),
        "growth_pct": float(growth_pct),
        "note": "Population from regional GIS sample catalog.",
    }


def historical_stress_placeholder(*, baseline_stress: float) -> dict[str, Any]:
    return {
        "source": "regional_baseline",
        "available": True,
        "historical_wsi": float(baseline_stress),
        "note": "Historical stress index prior from regional baseline.",
    }
