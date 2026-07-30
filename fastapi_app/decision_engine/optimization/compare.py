"""Current vs Optimized strategy comparison."""
from __future__ import annotations

from typing import Any


def build_strategy_comparison(
    *,
    optimized_actions: list[dict[str, Any]],
    demand: dict[str, Any] | None,
    reservoir: dict[str, Any] | None,
    stress: dict[str, Any] | None,
    aggressiveness: float = 1.0,
) -> dict[str, Any]:
    """
    Current strategy = status quo (no new interventions).
    Optimized strategy = implement top ranked actions.
    """
    agg = max(0.5, min(1.5, float(aggressiveness)))

    # Current risk / stress snapshot
    current_wsi = float((stress or {}).get("water_stress_index") or 45.0)
    current_risk = str((stress or {}).get("risk_label") or "MODERATE")
    current_pop_at_risk = int(
        (stress or {}).get("population_impact")
        or ((stress or {}).get("summary") or {}).get("population_affected")
        or 0
    )
    storage = float(
        (reservoir or {}).get("forecasted_storage_pct")
        or ((reservoir or {}).get("summary") or {}).get("forecasted_storage_pct")
        or 50.0
    )

    water_saved = sum(float(a.get("estimated_water_saved_mcm") or 0) for a in optimized_actions) * agg
    pop_protected = int(
        sum(int(a.get("population_protected") or 0) for a in optimized_actions) / max(1, len(optimized_actions) or 1)
        * min(1.0, 0.35 + 0.08 * len(optimized_actions))
        * agg
    )
    # Cap population protected
    if current_pop_at_risk:
        pop_protected = min(pop_protected, current_pop_at_risk)
    cost = sum(float(a.get("estimated_cost_inr") or 0) for a in optimized_actions) * agg
    benefit = sum(float(a.get("estimated_benefit_inr") or 0) for a in optimized_actions) * agg
    risk_reduction = min(
        45.0,
        sum(float(a.get("risk_reduction_score") or 0) for a in optimized_actions[:5]) / 5.0 * 0.55 * agg,
    )
    optimized_wsi = max(5.0, current_wsi - risk_reduction * 0.55)

    current = {
        "strategy": "current",
        "label": "Current Strategy",
        "description": "Maintain existing operating rules without new interventions.",
        "water_saved_mcm": 0.0,
        "risk_reduction": 0.0,
        "population_protected": 0,
        "estimated_cost_inr": 0.0,
        "estimated_benefit_inr": 0.0,
        "projected_wsi": round(current_wsi, 2),
        "risk_label": current_risk,
        "projected_storage_pct": round(storage, 2),
        "population_at_risk": current_pop_at_risk,
    }
    optimized = {
        "strategy": "optimized",
        "label": "Optimized Strategy",
        "description": f"Implement top {len(optimized_actions)} ranked operational decisions.",
        "water_saved_mcm": round(water_saved, 2),
        "risk_reduction": round(risk_reduction, 2),
        "population_protected": int(pop_protected),
        "estimated_cost_inr": round(cost, 0),
        "estimated_benefit_inr": round(benefit, 0),
        "projected_wsi": round(optimized_wsi, 2),
        "risk_label": _wsi_label(optimized_wsi),
        "projected_storage_pct": round(min(100.0, storage + water_saved * 0.15), 2),
        "population_at_risk": max(0, current_pop_at_risk - int(pop_protected)),
        "actions_applied": [a.get("id") for a in optimized_actions],
    }
    delta = {
        "water_saved_mcm": optimized["water_saved_mcm"],
        "risk_reduction": optimized["risk_reduction"],
        "population_protected": optimized["population_protected"],
        "estimated_cost_inr": optimized["estimated_cost_inr"],
        "wsi_improvement": round(current_wsi - optimized_wsi, 2),
        "net_benefit_inr": round(benefit - cost, 0),
    }
    return {
        "current": current,
        "optimized": optimized,
        "delta": delta,
        "demand_peak_mgd": (demand or {}).get("today_predicted_demand_mgd")
        or ((demand or {}).get("summary") or {}).get("predicted_peak_demand_mgd"),
        "aggressiveness": agg,
    }


def _wsi_label(wsi: float) -> str:
    if wsi >= 81:
        return "CRITICAL"
    if wsi >= 61:
        return "HIGH"
    if wsi >= 41:
        return "MODERATE"
    if wsi >= 21:
        return "LOW"
    return "HEALTHY"
