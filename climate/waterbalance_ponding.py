"""Indicative pluvial waterlogging from excess rainfall + soil moisture (not hydrodynamic)."""
from __future__ import annotations

from typing import Any, Optional

# Assumed drain/infiltration rates (mm/h) by coarse land class — disclosed assumptions
INFILTRATION_MM_H = {
    "urban": 2.0,
    "peri_urban": 4.0,
    "agricultural": 8.0,
    "rural": 10.0,
}

# Approximate plant-available / pore storage for top ~28 cm (mm) when SM is dry→wet
# volumetric m3/m3 * depth_mm ≈ storage; we use remaining capacity from observed SM
TOP_SOIL_DEPTH_MM = 280.0  # 0–28 cm
POROSITY = 0.45


def _mean_sm(values: list[Optional[float]]) -> Optional[float]:
    nums = [float(v) for v in values if v is not None]
    if not nums:
        return None
    return sum(nums) / len(nums)


def estimate_waterlogging(
    hourly_precip: list[Optional[float]],
    hourly_sm_0_7: list[Optional[float]],
    hourly_sm_7_28: list[Optional[float]],
    land_class: str = "urban",
) -> dict[str, Any]:
    """
    Potential ponding depth ≈ max(0, event_precip − remaining_soil_storage).
    Duration ≈ excess_mm / infiltration_rate (banded).
    """
    land = land_class if land_class in INFILTRATION_MM_H else "urban"
    infil = INFILTRATION_MM_H[land]

    precip_vals = [float(p) for p in hourly_precip if p is not None]
    event_precip = sum(precip_vals) if precip_vals else 0.0

    # Use last 24h of soil moisture if available, else all
    sm0 = hourly_sm_0_7[-24:] if hourly_sm_0_7 else []
    sm1 = hourly_sm_7_28[-24:] if hourly_sm_7_28 else []
    sm_avg = _mean_sm(sm0 + sm1)

    if sm_avg is None:
        # conservative: assume half-full
        remaining_storage_mm = TOP_SOIL_DEPTH_MM * POROSITY * 0.5
        sm_note = "soil moisture unavailable; assumed 50% storage remaining"
    else:
        # remaining = (porosity - sm) * depth, clamped
        remaining_frac = max(0.0, min(POROSITY, POROSITY - sm_avg))
        remaining_storage_mm = remaining_frac * TOP_SOIL_DEPTH_MM
        sm_note = f"mean volumetric SM≈{sm_avg:.3f} m³/m³ over recent hours"

    # Focus on peak 24h precip for "event"
    if len(precip_vals) >= 24:
        # rolling 24h max
        best = 0.0
        for i in range(len(precip_vals) - 23):
            best = max(best, sum(precip_vals[i : i + 24]))
        event_24h = best
    else:
        event_24h = event_precip

    excess_mm = max(0.0, event_24h - remaining_storage_mm)
    potential_depth_mm = round(excess_mm, 1)

    if infil <= 0:
        duration_h = None
    else:
        duration_h = round(excess_mm / infil, 1) if excess_mm > 0 else 0.0

    if duration_h is None or excess_mm <= 0:
        band = "none"
    elif duration_h < 6:
        band = "<6h"
    elif duration_h < 24:
        band = "6-24h"
    elif duration_h < 72:
        band = "1-3d"
    else:
        band = ">3d"

    return {
        "excess_mm": round(excess_mm, 1),
        "potential_depth_mm": potential_depth_mm,
        "event_precip_24h_mm": round(event_24h, 1),
        "remaining_soil_storage_mm": round(remaining_storage_mm, 1),
        "duration_hours_est": duration_h,
        "duration_band": band,
        "land_class": land,
        "infiltration_mm_h": infil,
        "exposure_radius_km": 5.0,
        "assumptions": [
            sm_note,
            f"Top-soil storage uses depth {TOP_SOIL_DEPTH_MM:.0f} mm × porosity {POROSITY}",
            f"Drain/infiltration rate assumed {infil} mm/h for land_class={land}",
            "Potential ponding depth is excess rainfall (mm), not surveyed inundation depth",
            "Indicative exposure within ~5 km of the query point (not a flood polygon)",
            "Not a hydrodynamic / DEM flood-fill model",
        ],
        "method": (
            "Water-balance ponding: excess_mm = max(0, peak_24h_precip − remaining_soil_storage); "
            "duration_h ≈ excess_mm / infiltration_mm_h by land class. "
            "Inputs: Open-Meteo hourly precipitation + soil_moisture."
        ),
    }
