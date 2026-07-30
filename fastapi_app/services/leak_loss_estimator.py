"""Physics-informed volumetric leak-loss estimator.

The acoustic ExtraTrees classifier has no water-loss labels in training data,
so this module supplies a transparent orifice-style heuristic for ops dashboards.
It is not a calibrated DMA water-balance model.
"""
from __future__ import annotations

import math
from typing import Any


# Discharge coefficient for a rough orifice / crack approximation.
_CD = 0.61
# Gravity (m/s^2).
_G = 9.81
# Default crack area when pressure/flow context is weak (m^2) — ~5 mm equivalent diameter.
_DEFAULT_AREA_M2 = math.pi * (0.0025**2)
# Cap absurd values so a bad sensor reading cannot dominate WSI.
_MAX_LPM = 5000.0


def estimate_leak_loss(
    leak_probability: float,
    *,
    pressure_drop_bar: float | None = None,
    flow_velocity_m_s: float | None = None,
    pipe_diameter_m: float = 0.15,
    is_leak_detected: bool | None = None,
) -> dict[str, Any]:
    """Estimate volumetric loss from leak probability and optional hydraulics.

    Orifice approximation:
        Q (m3/s) = Cd * A * sqrt(2 * g * h)
    where head h is derived from pressure drop (1 bar ≈ 10.2 m water).

    When hydraulics are missing, scale a baseline orifice by probability only.
    """
    prob = max(0.0, min(1.0, float(leak_probability)))
    detected = bool(is_leak_detected) if is_leak_detected is not None else prob >= 0.30

    if not detected and prob < 0.15:
        return {
            "estimated_water_loss_lpm": 0.0,
            "daily_loss_mld": 0.0,
            "confidence": 0.55,
            "method": "heuristic_orifice",
            "note": "No significant leak signal — loss estimate suppressed.",
        }

    drop_bar = max(0.0, float(pressure_drop_bar)) if pressure_drop_bar is not None else None
    velocity = max(0.0, float(flow_velocity_m_s)) if flow_velocity_m_s is not None else None
    diameter = max(0.02, float(pipe_diameter_m))

    if drop_bar is not None and drop_bar > 0.05:
        head_m = drop_bar * 10.2
        # Effective leak area scales with pipe cross-section and severity.
        pipe_area = math.pi * (diameter / 2.0) ** 2
        leak_area = min(_DEFAULT_AREA_M2 * (1.0 + 4.0 * prob), pipe_area * 0.05)
        q_m3s = _CD * leak_area * math.sqrt(2.0 * _G * head_m)
        confidence = 0.62
        note = "Orifice estimate from pressure drop and leak probability."
    elif velocity is not None and velocity > 0.1:
        # Continuity residual proxy: assume a fraction of pipe flow escapes.
        pipe_area = math.pi * (diameter / 2.0) ** 2
        q_m3s = pipe_area * velocity * (0.02 + 0.08 * prob)
        confidence = 0.48
        note = "Flow-velocity residual proxy — verify with DMA metering."
    else:
        # Probability-only baseline (lab acoustic path has no hydraulics).
        head_m = 15.0  # ~1.5 bar typical distribution head
        leak_area = _DEFAULT_AREA_M2 * (0.5 + 1.5 * prob)
        q_m3s = _CD * leak_area * math.sqrt(2.0 * _G * head_m) * prob
        confidence = 0.40
        note = (
            "Probability-scaled orifice heuristic (no pressure/flow context). "
            "Not a calibrated volumetric water-balance."
        )

    lpm = q_m3s * 1000.0 * 60.0
    lpm = round(min(_MAX_LPM, max(0.0, lpm)), 1)
    daily_mld = round(lpm * 60.0 * 24.0 / 1_000_000.0, 4)

    return {
        "estimated_water_loss_lpm": lpm,
        "daily_loss_mld": daily_mld,
        "confidence": confidence,
        "method": "heuristic_orifice",
        "note": note,
    }


def enrich_leak_result(leak: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    """Attach loss fields onto an existing leak detection dict (in-place copy)."""
    out = dict(leak)
    existing = out.get("estimated_water_loss_lpm")
    if existing is not None and float(existing) > 0 and "method" in out:
        return out

    estimate = estimate_leak_loss(
        float(out.get("leak_probability", 0.0) or 0.0),
        pressure_drop_bar=kwargs.get("pressure_drop_bar"),
        flow_velocity_m_s=kwargs.get("flow_velocity_m_s"),
        pipe_diameter_m=float(kwargs.get("pipe_diameter_m") or 0.15),
        is_leak_detected=out.get("is_leak_detected"),
    )
    # Prefer DB-seeded loss if present and positive; still expose method metadata.
    if existing is not None and float(existing) > 0:
        estimate["estimated_water_loss_lpm"] = float(existing)
        estimate["daily_loss_mld"] = round(float(existing) * 60.0 * 24.0 / 1_000_000.0, 4)
        estimate["note"] = "Using telemetry alert loss; orifice heuristic available as cross-check."
        estimate["method"] = "telemetry_alert"
    out.update(estimate)
    return out
