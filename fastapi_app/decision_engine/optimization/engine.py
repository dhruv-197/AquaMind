"""Core Decision Optimization Engine — ranks actions from prediction outputs."""
from __future__ import annotations

from typing import Any

from fastapi_app.decision_engine.optimization.compare import build_strategy_comparison
from fastapi_app.decision_engine.optimization.generators import (
    generate_from_demand,
    generate_from_reservoir,
    generate_from_stress,
    generate_infrastructure_baseline,
)
from fastapi_app.decision_engine.optimization.scoring import rank_actions
from fastapi_app.decision_engine.optimization.timeline import build_timeline


class DecisionOptimizationEngine:
    """
    Transforms prediction outputs into ranked operational decisions.

    Does NOT run forecasting — only consumes demand / reservoir / stress payloads.
    """

    def optimize(
        self,
        *,
        demand: dict[str, Any] | None,
        reservoir: dict[str, Any] | None,
        stress: dict[str, Any] | None,
        max_actions: int = 12,
    ) -> dict[str, Any]:
        candidates: list[dict[str, Any]] = []
        candidates.extend(generate_from_reservoir(reservoir))
        candidates.extend(generate_from_demand(demand))
        candidates.extend(generate_from_stress(stress))
        candidates.extend(generate_infrastructure_baseline())

        seen: set[str] = set()
        unique: list[dict[str, Any]] = []
        for a in candidates:
            aid = str(a.get("id"))
            if aid in seen:
                continue
            seen.add(aid)
            unique.append(a)

        ranked = rank_actions(unique)[: max(1, int(max_actions))]
        timeline = build_timeline(ranked)
        outcomes = self._expected_outcomes(ranked, stress)
        priority_queue = [
            {
                "rank": a["rank"],
                "id": a["id"],
                "title": a["title"],
                "priority_level": a["priority_level"],
                "decision_type": a["decision_type"],
                "optimization_score": a["optimization_score"],
                "timeline_bucket": a["timeline_bucket"],
            }
            for a in ranked
        ]

        return {
            "recommendations": ranked,
            "top_recommendations": ranked[:5],
            "priority_queue": priority_queue,
            "operational_timeline": timeline,
            "expected_outcomes": outcomes,
            "ai_reasoning_summary": self._reasoning_summary(ranked, demand, reservoir, stress),
            "candidate_count": len(unique),
        }

    def compare(
        self,
        *,
        demand: dict[str, Any] | None,
        reservoir: dict[str, Any] | None,
        stress: dict[str, Any] | None,
        max_actions: int = 8,
        aggressiveness: float = 1.0,
    ) -> dict[str, Any]:
        pack = self.optimize(
            demand=demand,
            reservoir=reservoir,
            stress=stress,
            max_actions=max_actions,
        )
        comparison = build_strategy_comparison(
            optimized_actions=pack["recommendations"],
            demand=demand,
            reservoir=reservoir,
            stress=stress,
            aggressiveness=aggressiveness,
        )
        return {**pack, "scenario_comparison": comparison}

    @staticmethod
    def _expected_outcomes(
        actions: list[dict[str, Any]], stress: dict[str, Any] | None
    ) -> dict[str, Any]:
        water = sum(float(a.get("estimated_water_saved_mcm") or 0) for a in actions)
        pop = max((int(a.get("population_protected") or 0) for a in actions), default=0)
        cost = sum(float(a.get("estimated_cost_inr") or 0) for a in actions)
        benefit = sum(float(a.get("estimated_benefit_inr") or 0) for a in actions)
        risk_drop = (
            sum(float(a.get("risk_reduction_score") or 0) for a in actions[:5])
            / max(1, min(5, len(actions)))
            if actions
            else 0
        )
        return {
            "estimated_water_saved_mcm": round(water, 2),
            "population_protected": pop,
            "estimated_cost_inr": round(cost, 0),
            "estimated_benefit_inr": round(benefit, 0),
            "net_benefit_inr": round(benefit - cost, 0),
            "average_risk_reduction": round(risk_drop, 1),
            "actions_count": len(actions),
            "baseline_wsi": (stress or {}).get("water_stress_index"),
        }

    @staticmethod
    def _reasoning_summary(
        actions: list[dict[str, Any]],
        demand: dict[str, Any] | None,
        reservoir: dict[str, Any] | None,
        stress: dict[str, Any] | None,
    ) -> list[str]:
        notes: list[str] = []
        if reservoir and reservoir.get("trained"):
            days = (reservoir.get("summary") or {}).get("days_to_critical")
            pct = reservoir.get("forecasted_storage_pct")
            if days:
                notes.append(
                    f"Reservoir forecast indicates critical risk in {days} days "
                    f"(storage {pct}%)."
                )
        if demand and demand.get("trained"):
            growth = (demand.get("summary") or {}).get("growth_pct")
            if growth is not None:
                notes.append(f"Demand forecast shows {growth}% change across the horizon.")
        if stress and stress.get("water_stress_index") is not None:
            notes.append(
                f"Water Stress Index is {stress['water_stress_index']} "
                f"({stress.get('risk_label')}) with population impact "
                f"{int(stress.get('population_impact') or 0):,}."
            )
        if actions:
            top = actions[0]
            notes.append(
                f"Top action '{top['title']}' ranked #{top.get('rank')} "
                f"(score {top.get('optimization_score')}) because: {top.get('why')}"
            )
        if not notes:
            notes.append(
                "Upstream models unavailable — returning infrastructure baseline actions."
            )
        return notes
