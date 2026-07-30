"""Composite Water Stress Index (WSI) fusion layer.

Combines shortage, groundwater, leak, demand (consumption), and climate signals
into a single auditable 0–100 index. Weights are transparent and returned with
every response for Technical Accuracy scoring.
"""
from __future__ import annotations

from typing import Any


# Explicit, documented component weights (must sum to 1.0).
DEFAULT_WEIGHTS: dict[str, float] = {
    "shortage": 0.30,
    "groundwater": 0.25,
    "leakage": 0.20,
    "demand": 0.15,
    "climate": 0.10,
}


def _clip(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, float(value)))


def _shortage_component(shortage: dict[str, Any] | None) -> tuple[float, str]:
    if not shortage:
        return 40.0, "No shortage telemetry — neutral prior."
    score = shortage.get("predicted_risk_score")
    if score is not None:
        return _clip(float(score)), f"Shortage risk score={round(float(score), 1)}"
    stage = int(shortage.get("predicted_risk_stage") or 0)
    mapped = {0: 18.0, 1: 45.0, 2: 70.0, 3: 92.0}.get(stage, 45.0)
    storage = shortage.get("reservoir_capacity_pct") or shortage.get("forecast_storage_pct")
    detail = f"Stage {stage}"
    if storage is not None:
        detail += f", storage={round(float(storage), 1)}%"
        # Low storage bumps stress even if stage is missing nuance.
        mapped = _clip(mapped + max(0.0, 55.0 - float(storage)) * 0.35)
    return mapped, detail


def _groundwater_component(groundwater: dict[str, Any] | None) -> tuple[float, str]:
    if not groundwater:
        return 35.0, "No groundwater telemetry — neutral prior."
    rate = float(
        groundwater.get("depletion_rate_m_year")
        or groundwater.get("drawdown_rate_m")
        or 0.0
    )
    depth = float(groundwater.get("projected_depth_m") or 20.0)
    # Softer mapping so a few extreme wells don't max the basin WSI.
    # 2 m/yr ≈ 48, 3.5 m/yr ≈ 84 (rates are already capped upstream for live WSI).
    rate_score = _clip(rate * 24.0)
    depth_score = _clip((min(depth, 60.0) / 60.0) * 100.0)
    score = _clip(0.65 * rate_score + 0.35 * depth_score)
    status = groundwater.get("aquifer_status") or "n/a"
    return score, f"Drawdown={round(rate, 2)} m/yr, depth={round(depth, 1)} m ({status})"


def _leakage_component(leak: dict[str, Any] | None) -> tuple[float, str]:
    if not leak:
        return 20.0, "No leak telemetry — low prior."
    # Demo-seeded alerts must not push WSI to Critical on their own.
    if leak.get("demo"):
        score = _clip(float(leak.get("leak_probability") or 0.12) * 100.0 * 0.35)
        return score, (
            f"Demo leak alerts muted for WSI (P≈{round(float(leak.get('leak_probability') or 0), 2)}; "
            "upload acoustic CSV for live leak stress)"
        )
    prob = float(leak.get("leak_probability") or 0.0)
    loss = float(leak.get("estimated_water_loss_lpm") or 0.0)
    detected = bool(leak.get("is_leak_detected"))
    prob_score = _clip(prob * 100.0)
    # 1000 L/min ≈ severe distribution loss for pilot scoring.
    loss_score = _clip((loss / 1000.0) * 100.0)
    score = _clip(0.55 * prob_score + 0.45 * loss_score)
    if detected:
        score = max(score, 55.0)
    return score, f"P(leak)={round(prob, 2)}, loss≈{round(loss, 1)} L/min"


def _demand_component(demand: dict[str, Any] | None) -> tuple[float, str]:
    if not demand:
        return 30.0, "No demand forecast — neutral prior."
    mgd = float(demand.get("forecasted_demand_mgd") or 0.0)
    surge = str(demand.get("peak_surge_risk") or "").lower()
    # Normalize municipal MGD into a soft stress curve (pilot scale ~50–150 MGD).
    volume_score = _clip((mgd / 150.0) * 100.0)
    surge_bump = 0.0
    if "critical" in surge:
        surge_bump = 35.0
    elif "elevated" in surge or "high" in surge:
        surge_bump = 20.0
    elif "normal" in surge:
        surge_bump = 0.0
    score = _clip(0.7 * volume_score + surge_bump)
    return score, f"Demand={round(mgd, 1)} MGD, surge={demand.get('peak_surge_risk', 'n/a')}"


def _climate_component(climate: dict[str, Any] | None) -> tuple[float, str]:
    if not climate:
        return 30.0, "No climate context — neutral prior."
    spi = climate.get("spi3_proxy")
    if isinstance(spi, dict):
        spi_z = spi.get("spi3_proxy")
    else:
        spi_z = spi
    deficit = climate.get("rainfall_deficit_pct")
    if deficit is None and isinstance(climate.get("rainfall_deficit"), dict):
        deficit = climate["rainfall_deficit"].get("deficit_pct")

    parts: list[str] = []
    score = 30.0
    if spi_z is not None:
        # SPI ≤ -2 extreme drought → high stress; SPI ≥ 1 → low stress.
        z = float(spi_z)
        score = _clip(50.0 - z * 25.0)
        parts.append(f"SPI-3 proxy={round(z, 2)}")
    if deficit is not None:
        d = float(deficit)
        # Positive deficit_pct in climate rules = drier than normal.
        # Shortage model uses rainfall_deficit_pct as anomaly (negative = drier).
        # Accept both conventions via climate.dry_anomaly_pct when provided.
        dry = climate.get("dry_anomaly_pct")
        if dry is not None:
            d_stress = float(dry)
        elif d < 0:
            # NASA POWER-style anomaly: negative = drier.
            d_stress = -d
        else:
            d_stress = d
        score = _clip(0.6 * score + 0.4 * _clip(d_stress))
        parts.append(f"rainfall stress≈{round(d_stress, 1)}%")
    heat = climate.get("heatwave_warning") or climate.get("heat_active")
    if heat:
        score = _clip(score + 10.0)
        parts.append("heat risk")
    return score, (", ".join(parts) if parts else "Climate inputs present")


def stage_from_score(score: float) -> str:
    if score >= 75:
        return "Critical"
    if score >= 55:
        return "High"
    if score >= 35:
        return "Moderate"
    return "Low"


def compute_water_stress_index(
    *,
    shortage: dict[str, Any] | None = None,
    groundwater: dict[str, Any] | None = None,
    leak: dict[str, Any] | None = None,
    demand: dict[str, Any] | None = None,
    climate: dict[str, Any] | None = None,
    weights: dict[str, float] | None = None,
    data_sources: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Return auditable WSI with component scores, weights, and top drivers."""
    w = dict(DEFAULT_WEIGHTS)
    if weights:
        w.update({k: float(v) for k, v in weights.items() if k in w})
    total_w = sum(w.values()) or 1.0
    w = {k: v / total_w for k, v in w.items()}

    components: dict[str, dict[str, Any]] = {}
    s_score, s_detail = _shortage_component(shortage)
    g_score, g_detail = _groundwater_component(groundwater)
    l_score, l_detail = _leakage_component(leak)
    d_score, d_detail = _demand_component(demand)
    c_score, c_detail = _climate_component(climate)

    raw = {
        "shortage": s_score,
        "groundwater": g_score,
        "leakage": l_score,
        "demand": d_score,
        "climate": c_score,
    }
    details = {
        "shortage": s_detail,
        "groundwater": g_detail,
        "leakage": l_detail,
        "demand": d_detail,
        "climate": c_detail,
    }

    index = 0.0
    for key, score in raw.items():
        contribution = score * w[key]
        index += contribution
        components[key] = {
            "score": round(score, 2),
            "weight": round(w[key], 4),
            "contribution": round(contribution, 2),
            "detail": details[key],
        }

    index = round(_clip(index), 2)
    drivers = sorted(
        (
            {"component": k, "contribution": v["contribution"], "detail": v["detail"]}
            for k, v in components.items()
        ),
        key=lambda row: row["contribution"],
        reverse=True,
    )

    sources = {
        "shortage": "sklearn_water_shortage_model + reservoir telemetry",
        "groundwater": "sklearn_groundwater_model + CGWB / GWL metrics",
        "leakage": "acoustic_extra_trees + orifice_loss_heuristic",
        "demand": "sklearn_water_demand_model (consumption proxy)",
        "climate": "Open-Meteo SPI proxy / rainfall anomaly / heat",
    }
    if data_sources:
        sources.update(data_sources)

    return {
        "water_stress_index": index,
        "stage": stage_from_score(index),
        "components": components,
        "weights": {k: round(v, 4) for k, v in w.items()},
        "drivers": drivers[:3],
        "data_sources": sources,
        "method": "weighted_multi_source_wsi_v1",
        "note": (
            "Pilot composite index for operations prioritization. "
            "Not a regulatory Water Stress Index substitute."
        ),
    }
