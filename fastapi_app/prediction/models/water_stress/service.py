"""Water Stress Intelligence service — fuses Demand + Reservoir forecasts.

This is NOT an ML model. It consumes ModelRegistry upstream predictors.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi_app.prediction.framework.registry.model_registry import ModelRegistry
from fastapi_app.prediction.models.water_demand.service import WaterDemandForecastService
from fastapi_app.prediction.models.reservoir.service import ReservoirLevelForecastService
from fastapi_app.prediction.models.water_stress.constants import MODULE_KEY, MODULE_VERSION
from fastapi_app.prediction.models.water_stress.fusion import (
    build_stress_series,
    fuse_water_stress,
)
from fastapi_app.prediction.models.water_stress.recommendations import build_recommendations
from fastapi_app.prediction.models.water_stress.regions import get_region, load_regions
from fastapi_app.prediction.models.water_stress.scenarios import (
    WHAT_IF_PRESETS,
    normalize_scenario,
    preset_catalog,
)


class WaterStressIntelligenceService:
    """Central intelligence layer connecting demand + reservoir (+ placeholders)."""

    def __init__(self, registry: ModelRegistry) -> None:
        self.registry = registry
        self.demand_service = WaterDemandForecastService(registry)
        self.reservoir_service = ReservoirLevelForecastService(registry)

    def status(self) -> dict[str, Any]:
        demand_status = self._safe_status(self.demand_service)
        reservoir_status = self._safe_status(self.reservoir_service)
        regions = load_regions()
        ready = bool(demand_status.get("trained") or reservoir_status.get("trained"))
        return {
            "ready": ready,
            "module": MODULE_KEY,
            "module_version": MODULE_VERSION,
            "upstream": {
                "water_demand": demand_status,
                "reservoir_forecast": reservoir_status,
                "weather": {"available": False, "source": "placeholder"},
                "groundwater": {"available": False, "source": "placeholder"},
            },
            "regions": [
                {
                    "region_id": r["region_id"],
                    "name": r["name"],
                    "region_type": r["region_type"],
                    "population": r["population"],
                    "lat": r["lat"],
                    "lng": r["lng"],
                    "reservoir_id": r.get("reservoir_id"),
                }
                for r in regions
            ],
            "what_if_presets": preset_catalog(),
            "message": (
                "Ready — fusion uses trained upstream models"
                if ready
                else "Upstream models not trained; fusion will use placeholders / priors"
            ),
        }

    def predict(
        self,
        *,
        region_id: str | None = None,
        region_type: str | None = None,
        horizon_days: int = 30,
        reservoir_id: str | None = None,
        scenario: dict[str, Any] | None = None,
        include_all_regions: bool = True,
    ) -> dict[str, Any]:
        return self._run(
            region_id=region_id,
            region_type=region_type,
            horizon_days=horizon_days,
            reservoir_id=reservoir_id,
            scenario=normalize_scenario(scenario),
            include_all_regions=include_all_regions,
            mode="predict",
        )

    def simulate(
        self,
        *,
        region_id: str | None = None,
        horizon_days: int = 30,
        reservoir_id: str | None = None,
        scenario: dict[str, Any] | None = None,
        preset_id: str | None = None,
        include_all_regions: bool = True,
    ) -> dict[str, Any]:
        sc = dict(scenario or {})
        if preset_id:
            for preset in WHAT_IF_PRESETS:
                if preset["id"] == preset_id:
                    sc = {**preset["scenario"], **sc}
                    break
        return self._run(
            region_id=region_id,
            horizon_days=horizon_days,
            reservoir_id=reservoir_id or sc.get("reservoir_id"),
            scenario=normalize_scenario(sc),
            include_all_regions=include_all_regions,
            mode="simulate",
            preset_id=preset_id,
        )

    def _run(
        self,
        *,
        region_id: str | None,
        region_type: str | None = None,
        horizon_days: int,
        reservoir_id: str | None,
        scenario: dict[str, Any],
        include_all_regions: bool,
        mode: str,
        preset_id: str | None = None,
    ) -> dict[str, Any]:
        regions = load_regions()
        if region_type:
            typed = [r for r in regions if r.get("region_type") == region_type]
            if typed and not region_id:
                region_id = typed[0]["region_id"]

        region = get_region(region_id, regions)
        if not region:
            raise ValueError("No regions available in sample GIS catalog")

        rid = reservoir_id or scenario.get("reservoir_id") or region.get("reservoir_id")
        demand = self._fetch_demand(horizon_days)
        reservoir_cache: dict[str, dict[str, Any]] = {}
        cache_key = str(rid or "_default")
        reservoir_cache[cache_key] = self._fetch_reservoir(horizon_days, rid)
        reservoir = reservoir_cache[cache_key]

        baseline_fusion = fuse_water_stress(
            region=region, demand=demand, reservoir=reservoir, scenario=None
        )
        fusion = fuse_water_stress(
            region=region, demand=demand, reservoir=reservoir, scenario=scenario
        )
        recs = build_recommendations(
            fusion=fusion,
            region=region,
            baseline_wsi=float(baseline_fusion["water_stress_index"]) if scenario else None,
        )
        series = build_stress_series(
            region=region,
            demand=demand,
            reservoir=reservoir,
            horizon_days=horizon_days,
            scenario=scenario or None,
        )
        forecast_only = [p for p in series if p.get("forecast") is not None]
        peak = max((float(p["forecast"]) for p in forecast_only), default=fusion["water_stress_index"])
        trough = min((float(p["forecast"]) for p in forecast_only), default=fusion["water_stress_index"])

        map_regions = []
        regional_comparison = []
        if include_all_regions:
            for r in regions:
                r_key = str(r.get("reservoir_id") or "_default")
                if r_key not in reservoir_cache:
                    reservoir_cache[r_key] = self._fetch_reservoir(horizon_days, r.get("reservoir_id"))
                r_res = reservoir_cache[r_key]
                f_base = fuse_water_stress(
                    region=r, demand=demand, reservoir=r_res, scenario=None
                )
                f = fuse_water_stress(
                    region=r, demand=demand, reservoir=r_res, scenario=scenario or None
                )
                delta = round(f["water_stress_index"] - f_base["water_stress_index"], 2)
                entry = {
                    "region_id": r["region_id"],
                    "name": r["name"],
                    "region_type": r["region_type"],
                    "population": r["population"],
                    "lat": r["lat"],
                    "lng": r["lng"],
                    "polygon": r.get("polygon"),
                    "reservoir_id": r.get("reservoir_id"),
                    "water_stress_index": f["water_stress_index"],
                    "baseline_wsi": f_base["water_stress_index"],
                    "delta_wsi": delta,
                    "risk_label": f["risk_label"],
                    "map_color": f["map_color"],
                    "population_impact": f["population_impact"],
                    "confidence": f["confidence"],
                    "expected_stress_date": f["expected_stress_date"],
                }
                map_regions.append(entry)
                regional_comparison.append(
                    {
                        "region_id": r["region_id"],
                        "name": r["name"],
                        "region_type": r["region_type"],
                        "wsi": f["water_stress_index"],
                        "baseline_wsi": f_base["water_stress_index"],
                        "delta_wsi": delta,
                        "risk_label": f["risk_label"],
                        "population_impact": f["population_impact"],
                    }
                )

        # Baseline forecast series for chart overlay when a scenario is active
        baseline_series = build_stress_series(
            region=region,
            demand=demand,
            reservoir=reservoir,
            horizon_days=horizon_days,
            scenario=None,
        )
        baseline_forecast_by_date = {
            p["date"]: p.get("forecast")
            for p in baseline_series
            if p.get("forecast") is not None
        }
        series = [
            {
                **p,
                "baseline_forecast": baseline_forecast_by_date.get(p["date"])
                if p.get("forecast") is not None
                else None,
            }
            for p in series
        ]
        forecast_only = [p for p in series if p.get("forecast") is not None]
        has_scenario = bool(scenario)

        highest = max(map_regions, key=lambda x: x["water_stress_index"]) if map_regions else {
            "region_id": region["region_id"],
            "name": region["name"],
            "water_stress_index": fusion["water_stress_index"],
        }

        affected = [
            r for r in map_regions if r["water_stress_index"] >= 41
        ] or [m for m in map_regions if m["region_id"] == region["region_id"]]

        summary = {
            "current_stress": round(float(region.get("baseline_stress") or fusion["water_stress_index"] * 0.92), 2),
            "predicted_stress": fusion["water_stress_index"],
            "peak_forecast_stress": round(float(peak), 2),
            "minimum_forecast_stress": round(float(trough), 2),
            "highest_risk_region": highest.get("name"),
            "highest_risk_region_id": highest.get("region_id"),
            "highest_risk_wsi": highest.get("water_stress_index"),
            "population_affected": fusion["population_impact"],
            "expected_shortage_date": fusion.get("expected_stress_date"),
            "confidence": fusion["confidence"],
            "risk_label": fusion["risk_label"],
            "baseline_stress": baseline_fusion["water_stress_index"],
            "delta_vs_baseline": round(
                fusion["water_stress_index"] - baseline_fusion["water_stress_index"], 2
            ),
        }

        return {
            "mode": mode,
            "generated_at": datetime.utcnow().isoformat(),
            "module": MODULE_KEY,
            "module_version": MODULE_VERSION,
            "region": {
                "region_id": region["region_id"],
                "name": region["name"],
                "region_type": region["region_type"],
                "population": region["population"],
                "lat": region["lat"],
                "lng": region["lng"],
                "reservoir_id": region.get("reservoir_id"),
            },
            "horizon_days": horizon_days,
            "scenario": scenario,
            "preset_id": preset_id,
            "water_stress_index": fusion["water_stress_index"],
            "risk_level": fusion["risk_level"],
            "risk_label": fusion["risk_label"],
            "map_color": fusion["map_color"],
            "confidence": fusion["confidence"],
            "expected_stress_date": fusion.get("expected_stress_date"),
            "population_impact": fusion["population_impact"],
            "affected_regions": [
                {"region_id": a["region_id"], "name": a["name"], "wsi": a["water_stress_index"], "risk_label": a["risk_label"]}
                for a in affected
            ],
            "summary": summary,
            "components": fusion["components"],
            "baseline_components": baseline_fusion["components"] if has_scenario else None,
            "baseline_risk_label": baseline_fusion["risk_label"] if has_scenario else None,
            "baseline_expected_stress_date": (
                baseline_fusion.get("expected_stress_date") if has_scenario else None
            ),
            "weights": fusion["weights"],
            "inputs": fusion["inputs"],
            "recommended_actions": recs["recommended_actions"],
            "executive_insights": recs["executive_insights"],
            "decision_engine": recs["decision_engine"],
            "series": series,
            "forecast_series": forecast_only,
            "regional_comparison": regional_comparison,
            "map_regions": map_regions,
            "has_scenario": has_scenario,
            "projection_disclaimer": (
                "Scenario values are projections from the fusion model, not field observations."
                if has_scenario
                else None
            ),
            "what_if_presets": preset_catalog(),
            "upstream_status": {
                "demand_trained": bool(demand and demand.get("trained")),
                "reservoir_trained": bool(reservoir and reservoir.get("trained")),
            },
            "message": "Water stress fusion generated",
        }

    def _fetch_demand(self, horizon_days: int) -> dict[str, Any]:
        try:
            return self.demand_service.predict(
                value=min(horizon_days, 90),
                unit="days",
                include_history_days=90,
            )
        except Exception as exc:
            return {"trained": False, "message": str(exc)}

    def _fetch_reservoir(self, horizon_days: int, reservoir_id: str | None) -> dict[str, Any]:
        try:
            return self.reservoir_service.predict(
                value=min(horizon_days, 90),
                unit="days",
                reservoir_id=reservoir_id,
                include_history_days=90,
            )
        except Exception as exc:
            return {"trained": False, "message": str(exc)}

    @staticmethod
    def _safe_status(service: Any) -> dict[str, Any]:
        try:
            return service.status()
        except Exception as exc:
            return {"trained": False, "message": str(exc)}
