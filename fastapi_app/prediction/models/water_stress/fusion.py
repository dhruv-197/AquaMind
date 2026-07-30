"""Core fusion engine — combines upstream model outputs into a Water Stress Index.

Does NOT train ML. Does NOT duplicate demand/reservoir forecasting logic.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from fastapi_app.prediction.models.water_stress.constants import FUSION_WEIGHTS
from fastapi_app.prediction.models.water_stress.placeholders import (
    groundwater_placeholder,
    historical_stress_placeholder,
    population_placeholder,
    rainfall_placeholder,
    weather_placeholder,
)
from fastapi_app.prediction.models.water_stress.risk import (
    map_color,
    risk_display_label,
    stress_risk_level,
)


def _clip(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, float(value)))


def demand_stress_score(demand: dict[str, Any] | None, *, demand_share: float = 1.0) -> tuple[float, str]:
    if not demand or not demand.get("trained"):
        return 42.0, "Demand model unavailable — neutral prior."
    summary = demand.get("summary") or {}
    mgd = float(
        demand.get("today_predicted_demand_mgd")
        or summary.get("average_forecast_mgd")
        or 90.0
    )
    util = summary.get("capacity_utilization_pct")
    risk = str(summary.get("expected_shortage_risk") or demand.get("risk_label") or "").upper()
    # Regional demand share scales local pressure
    local_mgd = mgd * max(0.05, float(demand_share))
    volume_score = _clip((local_mgd / 40.0) * 100.0)  # ward-scale soft curve
    if util is not None:
        volume_score = _clip(0.55 * volume_score + 0.45 * float(util))
    bump = 0.0
    if risk in {"HIGH", "CRITICAL"}:
        bump = 22.0
    elif risk in {"MEDIUM", "MODERATE"}:
        bump = 10.0
    score = _clip(volume_score + bump)
    return score, f"Demand≈{round(local_mgd, 1)} MGD (share={demand_share:.0%}), util={util}, risk={risk or 'n/a'}"


def reservoir_stress_score(reservoir: dict[str, Any] | None) -> tuple[float, str]:
    if not reservoir or not reservoir.get("trained"):
        return 45.0, "Reservoir model unavailable — neutral prior."
    pct = float(
        reservoir.get("forecasted_storage_pct")
        or (reservoir.get("summary") or {}).get("forecasted_storage_pct")
        or 50.0
    )
    # Invert storage → stress (low storage = high stress)
    score = _clip(100.0 - pct)
    days = (reservoir.get("summary") or {}).get("days_to_critical")
    detail = f"Storage={round(pct, 1)}%"
    if days:
        detail += f", critical in {days}d"
        score = _clip(score + min(15.0, 90.0 / max(1, int(days))))
    return score, detail


def rainfall_stress_score(rainfall: dict[str, Any], *, rainfall_delta_pct: float = 0.0) -> tuple[float, str]:
    deficit = float(rainfall.get("deficit_pct") or 0.0)
    # Scenario: rainfall decreases by X% → increase deficit
    effective_deficit = deficit + max(0.0, -float(rainfall_delta_pct)) + max(0.0, float(rainfall_delta_pct) * -0.5 if rainfall_delta_pct < 0 else 0)
    if rainfall_delta_pct < 0:
        effective_deficit = deficit + abs(rainfall_delta_pct)
    else:
        effective_deficit = max(0.0, deficit - rainfall_delta_pct * 0.5)
    score = _clip(30.0 + effective_deficit * 0.7)
    return score, f"Rainfall deficit≈{round(effective_deficit, 1)}% (Δ rainfall={rainfall_delta_pct:+.0f}%)"


def groundwater_stress_score(gw: dict[str, Any]) -> tuple[float, str]:
    rate = float(gw.get("depletion_rate_m_year") or 1.0)
    depth = float(gw.get("projected_depth_m") or 25.0)
    score = _clip(0.65 * _clip(rate * 24.0) + 0.35 * _clip((min(depth, 60.0) / 60.0) * 100.0))
    return score, f"GW drawdown={round(rate, 2)} m/yr, depth={round(depth, 1)} m"


def population_stress_score(
    population: dict[str, Any],
    *,
    population_delta_pct: float = 0.0,
) -> tuple[float, str]:
    pop = float(population.get("population") or 100000)
    growth = float(population.get("growth_pct") or 1.5) + float(population_delta_pct)
    effective_pop = pop * (1.0 + max(-50.0, population_delta_pct) / 100.0)
    # Soft curve — denser / faster growth → higher stress contribution
    dens = _clip((effective_pop / 250000.0) * 55.0)
    growth_score = _clip(growth * 8.0)
    score = _clip(0.7 * dens + 0.3 * growth_score)
    return score, f"Population≈{int(effective_pop):,}, growth={growth:.1f}%"


def historical_stress_score(historical: dict[str, Any]) -> tuple[float, str]:
    base = float(historical.get("historical_wsi") or 40.0)
    return _clip(base), f"Historical WSI prior={round(base, 1)}"


def fuse_water_stress(
    *,
    region: dict[str, Any],
    demand: dict[str, Any] | None,
    reservoir: dict[str, Any] | None,
    scenario: dict[str, Any] | None = None,
    weights: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Fuse upstream predictions + placeholders into a regional Water Stress Index."""
    scenario = scenario or {}
    rainfall_delta = float(scenario.get("rainfall_delta_pct") or 0.0)
    population_delta = float(scenario.get("population_delta_pct") or 0.0)
    demand_delta = float(scenario.get("demand_delta_pct") or 0.0)
    temperature_delta = float(scenario.get("temperature_delta_c") or 0.0)
    reservoir_delta = float(scenario.get("reservoir_delta_pct") or 0.0)
    reservoir_override = scenario.get("reservoir_level_pct")

    # Apply demand scenario without re-running the ML model
    demand_adj = None
    if demand and demand.get("trained"):
        demand_adj = dict(demand)
        summary = dict(demand.get("summary") or {})
        base_mgd = float(
            demand.get("today_predicted_demand_mgd")
            or summary.get("average_forecast_mgd")
            or 90.0
        )
        # Temperature bump ≈ +1.5% demand per °C
        temp_factor = 1.0 + (temperature_delta * 0.015)
        adjusted = base_mgd * (1.0 + demand_delta / 100.0) * temp_factor
        demand_adj["today_predicted_demand_mgd"] = adjusted
        summary["average_forecast_mgd"] = adjusted
        if summary.get("capacity_utilization_pct") is not None and base_mgd > 0:
            summary["capacity_utilization_pct"] = float(summary["capacity_utilization_pct"]) * (
                adjusted / base_mgd
            )
        demand_adj["summary"] = summary

    reservoir_adj = None
    if reservoir and reservoir.get("trained"):
        reservoir_adj = dict(reservoir)
        summary = dict(reservoir.get("summary") or {})
        base_pct = float(
            reservoir.get("forecasted_storage_pct")
            or summary.get("forecasted_storage_pct")
            or 50.0
        )
        if reservoir_override is not None:
            adj_pct = float(reservoir_override)
        else:
            adj_pct = _clip(base_pct + reservoir_delta, 0, 100)
        reservoir_adj["forecasted_storage_pct"] = adj_pct
        summary["forecasted_storage_pct"] = adj_pct
        capacity = float(reservoir.get("capacity_mcm") or summary.get("capacity_mcm") or 250.0)
        reservoir_adj["forecasted_storage_mcm"] = round(adj_pct / 100.0 * capacity, 3)
        summary["forecasted_storage_mcm"] = reservoir_adj["forecasted_storage_mcm"]
        reservoir_adj["summary"] = summary
        reservoir_adj["capacity_mcm"] = capacity

    weather = weather_placeholder(temperature_c=32.0 + temperature_delta)
    rainfall = rainfall_placeholder()
    gw = groundwater_placeholder()
    # Hotter weather slightly worsens GW placeholder
    if temperature_delta > 0:
        gw = {
            **gw,
            "depletion_rate_m_year": float(gw["depletion_rate_m_year"]) + temperature_delta * 0.05,
        }
    population = population_placeholder(population=int(region.get("population") or 100000))
    historical = historical_stress_placeholder(baseline_stress=float(region.get("baseline_stress") or 40.0))

    d_score, d_detail = demand_stress_score(
        demand_adj or demand, demand_share=float(region.get("demand_share") or 1.0)
    )
    r_score, r_detail = reservoir_stress_score(reservoir_adj or reservoir)
    rf_score, rf_detail = rainfall_stress_score(rainfall, rainfall_delta_pct=rainfall_delta)
    g_score, g_detail = groundwater_stress_score(gw)
    p_score, p_detail = population_stress_score(population, population_delta_pct=population_delta)
    h_score, h_detail = historical_stress_score(historical)

    # Industrial intensity bump for high-industry wards
    industrial = float(region.get("industrial_share") or 0.0)
    industrial_bump = industrial * 8.0

    w = dict(FUSION_WEIGHTS)
    if weights:
        w.update({k: float(v) for k, v in weights.items() if k in w})
    total_w = sum(w.values()) or 1.0
    w = {k: v / total_w for k, v in w.items()}

    raw = {
        "demand": d_score,
        "reservoir": r_score,
        "rainfall": rf_score,
        "groundwater": g_score,
        "population": p_score,
        "historical": h_score,
    }
    details = {
        "demand": d_detail,
        "reservoir": r_detail,
        "rainfall": rf_detail,
        "groundwater": g_detail,
        "population": p_detail,
        "historical": h_detail,
    }

    index = 0.0
    components: dict[str, dict[str, Any]] = {}
    for key, score in raw.items():
        contribution = score * w[key]
        index += contribution
        components[key] = {
            "score": round(score, 2),
            "weight": round(w[key], 4),
            "contribution": round(contribution, 2),
            "detail": details[key],
        }

    index = _clip(index + industrial_bump)
    risk = stress_risk_level(index)
    label = risk_display_label(index)

    # Expected stress date: when forecast series would cross High (61) — heuristic from reservoir/demand
    expected_stress_date = _estimate_stress_date(demand_adj or demand, reservoir_adj or reservoir, index)
    pop = int(population.get("population") or 0) * (1.0 + population_delta / 100.0)
    # Population impact scales with risk severity
    impact_frac = { "HEALTHY": 0.05, "LOW": 0.12, "MODERATE": 0.28, "HIGH": 0.55, "CRITICAL": 0.85 }.get(label, 0.2)
    population_impact = int(pop * impact_frac)

    confidence = _fusion_confidence(demand_adj or demand, reservoir_adj or reservoir)

    return {
        "water_stress_index": round(index, 2),
        "risk_level": risk.value,
        "risk_label": label,
        "map_color": map_color(index),
        "confidence": confidence,
        "expected_stress_date": expected_stress_date,
        "population": int(pop),
        "population_impact": population_impact,
        "components": components,
        "weights": {k: round(v, 4) for k, v in w.items()},
        "inputs": {
            "demand": _slim_upstream(demand_adj or demand),
            "reservoir": _slim_upstream(reservoir_adj or reservoir),
            "weather": weather,
            "rainfall": rainfall,
            "groundwater": gw,
            "population": {**population, "population": int(pop), "delta_pct": population_delta},
            "historical": historical,
            "scenario": scenario,
        },
        "method": "multi_model_fusion_wsi_v1",
        "note": "Fusion intelligence layer — does not train a separate ML model.",
    }


def _slim_upstream(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not payload:
        return {"trained": False, "available": False}
    return {
        "trained": bool(payload.get("trained")),
        "available": bool(payload.get("trained")),
        "model_name": payload.get("model_name"),
        "model_version": payload.get("model_version"),
        "confidence_score": payload.get("confidence_score"),
        "risk_label": payload.get("risk_label"),
        "summary": payload.get("summary"),
        "forecasted_storage_pct": payload.get("forecasted_storage_pct"),
        "today_predicted_demand_mgd": payload.get("today_predicted_demand_mgd"),
        "reservoir_id": payload.get("reservoir_id"),
    }


def _fusion_confidence(demand: dict[str, Any] | None, reservoir: dict[str, Any] | None) -> float:
    scores: list[float] = []
    if demand and demand.get("trained"):
        scores.append(float(demand.get("confidence_score") or 0.7))
    if reservoir and reservoir.get("trained"):
        scores.append(float(reservoir.get("confidence_score") or 0.7))
    if not scores:
        return 0.45  # placeholders only
    # Placeholder inputs dilute confidence
    base = sum(scores) / len(scores)
    return round(max(0.35, min(0.95, base * 0.9)), 4)


def _estimate_stress_date(
    demand: dict[str, Any] | None,
    reservoir: dict[str, Any] | None,
    current_wsi: float,
) -> str | None:
    if current_wsi >= 61:
        return date.today().isoformat()
    # Prefer reservoir days_to_critical
    if reservoir and reservoir.get("trained"):
        days = (reservoir.get("summary") or {}).get("days_to_critical") or (
            reservoir.get("summary") or {}
        ).get("remaining_days")
        if days:
            return (date.today() + timedelta(days=int(days))).isoformat()
    if demand and demand.get("trained"):
        shortage = (demand.get("summary") or {}).get("expected_shortage_date")
        if shortage:
            return str(shortage)
    # Project from current WSI growth heuristic
    if current_wsi >= 41:
        days_out = max(7, int((61 - current_wsi) * 2.5))
        return (date.today() + timedelta(days=days_out)).isoformat()
    return None


def build_stress_series(
    *,
    region: dict[str, Any],
    demand: dict[str, Any] | None,
    reservoir: dict[str, Any] | None,
    horizon_days: int,
    scenario: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Build historical + forecast WSI series for charts (no ML recursion)."""
    base = fuse_water_stress(region=region, demand=demand, reservoir=reservoir, scenario=scenario)
    current = float(base["water_stress_index"])
    hist_base = float(region.get("baseline_stress") or current * 0.9)

    history: list[dict[str, Any]] = []
    today = date.today()
    for i in range(30, 0, -1):
        # Mild oscillation around historical baseline
        wobble = ((i % 7) - 3) * 0.6
        val = _clip(hist_base + wobble + (30 - i) * 0.05)
        history.append(
            {
                "date": (today - timedelta(days=i)).isoformat(),
                "historical": round(val, 2),
                "forecast": None,
                "lower": None,
                "upper": None,
                "confidence": None,
                "risk": None,
            }
        )

    forecast: list[dict[str, Any]] = []
    # Trend toward higher stress if demand rising / storage falling
    daily_drift = 0.05
    if demand and demand.get("trained"):
        growth = float((demand.get("summary") or {}).get("growth_pct") or 0.0)
        daily_drift += growth / max(horizon_days, 1) * 0.15
    if reservoir and reservoir.get("trained"):
        change = float((reservoir.get("summary") or {}).get("storage_change_pct") or 0.0)
        daily_drift += max(0.0, -change) / max(horizon_days, 1) * 0.4
    # Scenario drifts
    sc = scenario or {}
    daily_drift += abs(float(sc.get("rainfall_delta_pct") or 0.0)) * 0.002
    daily_drift += float(sc.get("demand_delta_pct") or 0.0) * 0.003
    daily_drift += float(sc.get("population_delta_pct") or 0.0) * 0.002
    if sc.get("reservoir_level_pct") is not None:
        daily_drift += max(0.0, 40.0 - float(sc["reservoir_level_pct"])) * 0.01

    conf0 = float(base["confidence"])
    for step in range(1, horizon_days + 1):
        pred = _clip(current + daily_drift * step)
        band = 3.0 + 0.08 * step
        conf = max(0.3, conf0 * (0.985 ** (step - 1)))
        forecast.append(
            {
                "date": (today + timedelta(days=step)).isoformat(),
                "historical": None,
                "forecast": round(pred, 2),
                "lower": round(max(0.0, pred - band), 2),
                "upper": round(min(100.0, pred + band), 2),
                "confidence": round(conf, 4),
                "risk": risk_display_label(pred),
            }
        )
    return history + forecast
