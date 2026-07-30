"""Rank optimized actions by multi-criteria score."""
from __future__ import annotations

from typing import Any

from fastapi_app.decision_engine.optimization.constants import RANK_WEIGHTS


def _clip01(v: float) -> float:
    return max(0.0, min(1.0, float(v)))


def score_action(action: dict[str, Any], *, max_water: float, max_pop: float) -> float:
    """
    Higher is better.

    Normalizes water saved / population against batch maxima; cost uses inverse efficiency.
    """
    impact = _clip01(float(action.get("impact_score") or 0) / 100.0)
    risk = _clip01(float(action.get("risk_reduction_score") or 0) / 100.0)
    water = float(action.get("estimated_water_saved_mcm") or 0.0)
    pop = float(action.get("population_protected") or 0.0)
    water_n = _clip01(water / max_water) if max_water > 0 else 0.0
    pop_n = _clip01(pop / max_pop) if max_pop > 0 else 0.0
    cost = float(action.get("estimated_cost_inr") or 0.0)
    # Cost efficiency: cheaper actions score higher for same impact
    cost_eff = _clip01(1.0 - min(cost, 5_000_000) / 5_000_000)

    w = RANK_WEIGHTS
    return round(
        100.0
        * (
            w["impact"] * impact
            + w["risk_reduction"] * risk
            + w["population_benefit"] * pop_n
            + w["water_saved"] * water_n
            + w["cost_efficiency"] * cost_eff
        ),
        2,
    )


def rank_actions(actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not actions:
        return []
    max_water = max((float(a.get("estimated_water_saved_mcm") or 0) for a in actions), default=1.0) or 1.0
    max_pop = max((float(a.get("population_protected") or 0) for a in actions), default=1.0) or 1.0
    scored: list[dict[str, Any]] = []
    for a in actions:
        row = dict(a)
        row["optimization_score"] = score_action(row, max_water=max_water, max_pop=max_pop)
        scored.append(row)
    scored.sort(
        key=lambda r: (
            -float(r["optimization_score"]),
            _priority_rank(str(r.get("implementation_priority") or "monitor")),
            -float(r.get("impact_score") or 0),
        )
    )
    for i, row in enumerate(scored, start=1):
        row["rank"] = i
    return scored


def _priority_rank(priority: str) -> int:
    order = {"immediate": 0, "short_term": 1, "medium_term": 2, "monitor": 3}
    return order.get(priority, 9)
