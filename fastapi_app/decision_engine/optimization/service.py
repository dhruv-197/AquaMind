"""Application service for Decision Optimization HTTP API."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi_app.decision_engine.optimization.constants import MODULE_KEY, MODULE_VERSION
from fastapi_app.decision_engine.optimization.engine import DecisionOptimizationEngine
from fastapi_app.prediction.framework.registry.model_registry import ModelRegistry
from fastapi_app.prediction.models.reservoir.service import ReservoirLevelForecastService
from fastapi_app.prediction.models.water_demand.service import WaterDemandForecastService
from fastapi_app.prediction.models.water_stress.service import WaterStressIntelligenceService


class DecisionOptimizationService:
    """Fetches upstream predictions and runs the optimization engine."""

    def __init__(self, registry: ModelRegistry) -> None:
        self.registry = registry
        self.demand_service = WaterDemandForecastService(registry)
        self.reservoir_service = ReservoirLevelForecastService(registry)
        self.stress_service = WaterStressIntelligenceService(registry)
        self.engine = DecisionOptimizationEngine()

    def status(self) -> dict[str, Any]:
        demand = self._safe(lambda: self.demand_service.status())
        reservoir = self._safe(lambda: self.reservoir_service.status())
        stress = self._safe(lambda: self.stress_service.status())
        ready = bool(
            demand.get("trained") or reservoir.get("trained") or stress.get("ready")
        )
        return {
            "ready": ready,
            "module": MODULE_KEY,
            "module_version": MODULE_VERSION,
            "upstream": {
                "water_demand": demand,
                "reservoir_forecast": reservoir,
                "water_stress": {
                    "ready": stress.get("ready"),
                    "message": stress.get("message"),
                    "module_version": stress.get("module_version"),
                },
            },
            "message": (
                "Ready — optimization can consume upstream prediction outputs"
                if ready
                else "Upstream models not ready; baseline infrastructure actions still available"
            ),
        }

    def recommend(
        self,
        *,
        region_id: str | None = None,
        reservoir_id: str | None = None,
        horizon_days: int = 30,
        max_actions: int = 12,
        include_upstream: bool = True,
    ) -> dict[str, Any]:
        demand, reservoir, stress = self._fetch_upstream(
            region_id=region_id,
            reservoir_id=reservoir_id,
            horizon_days=horizon_days,
        )
        pack = self.engine.optimize(
            demand=demand,
            reservoir=reservoir,
            stress=stress,
            max_actions=max_actions,
        )
        return self._envelope(
            pack,
            demand=demand,
            reservoir=reservoir,
            stress=stress,
            region_id=region_id,
            horizon_days=horizon_days,
            include_upstream=include_upstream,
            mode="recommend",
        )

    def compare(
        self,
        *,
        region_id: str | None = None,
        reservoir_id: str | None = None,
        horizon_days: int = 30,
        max_actions: int = 8,
        aggressiveness: float = 1.0,
    ) -> dict[str, Any]:
        demand, reservoir, stress = self._fetch_upstream(
            region_id=region_id,
            reservoir_id=reservoir_id,
            horizon_days=horizon_days,
        )
        pack = self.engine.compare(
            demand=demand,
            reservoir=reservoir,
            stress=stress,
            max_actions=max_actions,
            aggressiveness=aggressiveness,
        )
        return self._envelope(
            pack,
            demand=demand,
            reservoir=reservoir,
            stress=stress,
            region_id=region_id,
            horizon_days=horizon_days,
            include_upstream=True,
            mode="compare",
        )

    def _fetch_upstream(
        self,
        *,
        region_id: str | None,
        reservoir_id: str | None,
        horizon_days: int,
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        days = min(int(horizon_days), 90)
        demand = self._safe(
            lambda: self.demand_service.predict(
                value=days, unit="days", include_history_days=90
            )
        )
        # Prefer reservoir linked to stress region when available
        stress = self._safe(
            lambda: self.stress_service.predict(
                region_id=region_id,
                horizon_days=days,
                reservoir_id=reservoir_id,
                include_all_regions=False,
            )
        )
        rid = (
            reservoir_id
            or (stress.get("region") or {}).get("reservoir_id")
            or None
        )
        reservoir = self._safe(
            lambda: self.reservoir_service.predict(
                value=days,
                unit="days",
                reservoir_id=rid,
                include_history_days=90,
            )
        )
        return demand, reservoir, stress

    def _envelope(
        self,
        pack: dict[str, Any],
        *,
        demand: dict[str, Any],
        reservoir: dict[str, Any],
        stress: dict[str, Any],
        region_id: str | None,
        horizon_days: int,
        include_upstream: bool,
        mode: str,
    ) -> dict[str, Any]:
        overall_priority = "monitor"
        if pack.get("recommendations"):
            overall_priority = str(pack["recommendations"][0].get("priority_level") or "monitor")
        data: dict[str, Any] = {
            "mode": mode,
            "generated_at": datetime.utcnow().isoformat(),
            "module": MODULE_KEY,
            "module_version": MODULE_VERSION,
            "region_id": region_id or (stress.get("region") or {}).get("region_id"),
            "horizon_days": horizon_days,
            "priority_level": overall_priority,
            "recommended_actions": pack.get("recommendations") or [],
            "top_recommendations": pack.get("top_recommendations") or [],
            "priority_queue": pack.get("priority_queue") or [],
            "operational_timeline": pack.get("operational_timeline") or [],
            "expected_outcomes": pack.get("expected_outcomes") or {},
            "ai_reasoning": pack.get("ai_reasoning_summary") or [],
            "scenario_comparison": pack.get("scenario_comparison"),
            "message": "Decision optimization complete",
            "upstream_ready": {
                "demand": bool(demand.get("trained")),
                "reservoir": bool(reservoir.get("trained")),
                "stress": stress.get("water_stress_index") is not None,
            },
        }
        if include_upstream:
            data["upstream_snapshots"] = {
                "demand": _slim_demand(demand),
                "reservoir": _slim_reservoir(reservoir),
                "stress": _slim_stress(stress),
            }
        return data

    @staticmethod
    def _safe(fn) -> dict[str, Any]:
        try:
            result = fn()
            return result if isinstance(result, dict) else {"trained": False}
        except Exception as exc:
            return {"trained": False, "message": str(exc)}


def _slim_demand(d: dict[str, Any]) -> dict[str, Any]:
    return {
        "trained": d.get("trained"),
        "today_predicted_demand_mgd": d.get("today_predicted_demand_mgd"),
        "risk_label": d.get("risk_label"),
        "confidence_score": d.get("confidence_score"),
        "summary": d.get("summary"),
    }


def _slim_reservoir(r: dict[str, Any]) -> dict[str, Any]:
    return {
        "trained": r.get("trained"),
        "reservoir_id": r.get("reservoir_id"),
        "reservoir_name": r.get("reservoir_name"),
        "forecasted_storage_pct": r.get("forecasted_storage_pct"),
        "risk_label": r.get("risk_label"),
        "confidence_score": r.get("confidence_score"),
        "summary": r.get("summary"),
    }


def _slim_stress(s: dict[str, Any]) -> dict[str, Any]:
    return {
        "water_stress_index": s.get("water_stress_index"),
        "risk_label": s.get("risk_label"),
        "confidence": s.get("confidence"),
        "population_impact": s.get("population_impact"),
        "expected_stress_date": s.get("expected_stress_date"),
        "region": s.get("region"),
        "summary": s.get("summary"),
    }
