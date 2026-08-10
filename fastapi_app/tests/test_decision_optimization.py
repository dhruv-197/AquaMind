"""Tests for AI Decision Optimization Engine."""
from __future__ import annotations

import pytest

from fastapi_app.decision_engine.optimization.compare import build_strategy_comparison
from fastapi_app.decision_engine.optimization.engine import DecisionOptimizationEngine
from fastapi_app.decision_engine.optimization.generators import (
    generate_from_demand,
    generate_from_reservoir,
    generate_from_stress,
)
from fastapi_app.decision_engine.optimization.scoring import rank_actions
from fastapi_app.decision_engine.optimization.service import DecisionOptimizationService
from fastapi_app.prediction.framework.datasets.base import TrainingDataset
from fastapi_app.prediction.framework.registry.model_registry import ModelRegistry
from fastapi_app.prediction.framework.schemas.config import TrainingConfiguration
from fastapi_app.prediction.models.reservoir.dataset import (
    ReservoirDatasetLoader,
    generate_sample_dataset as gen_reservoir,
)
from fastapi_app.prediction.models.reservoir.factory import build_reservoir_forecast_model
from fastapi_app.prediction.models.water_demand.dataset import (
    DemandDatasetLoader,
    generate_sample_dataset as gen_demand,
)
from fastapi_app.prediction.models.water_demand.factory import build_water_demand_model


@pytest.fixture(scope="module")
def trained_registry(tmp_path_factory) -> ModelRegistry:
    pytest.importorskip("xgboost")
    root = tmp_path_factory.mktemp("decision_opt")
    demand_csv = root / "demand.csv"
    res_csv = root / "reservoir.csv"
    gen_demand(demand_csv, days=280, seed=9)
    gen_reservoir(res_csv, days=280, seed=13)

    demand = build_water_demand_model(artifacts_dir=root / "d", autoload=False, model_version="d-1")
    reservoir = build_reservoir_forecast_model(
        artifacts_dir=root / "r", autoload=False, model_version="r-1"
    )
    demand.train(
        TrainingDataset(
            DemandDatasetLoader().load_csv(demand_csv),
            feature_columns=[],
            target_column="demand_mgd",
        ),
        TrainingConfiguration(model_name="water_demand", model_version="d-1", random_seed=9),
    )
    reservoir.train(
        TrainingDataset(
            ReservoirDatasetLoader().load_csv(res_csv),
            feature_columns=[],
            target_column="storage_pct",
        ),
        TrainingConfiguration(
            model_name="reservoir_forecast", model_version="r-1", random_seed=13
        ),
    )
    registry = ModelRegistry()
    registry.register("water_demand", demand)
    registry.register("reservoir_forecast", reservoir)
    return registry


def test_generator_from_reservoir_critical():
    actions = generate_from_reservoir(
        {
            "trained": True,
            "forecasted_storage_pct": 22.0,
            "capacity_mcm": 300.0,
            "reservoir_name": "Reservoir A",
            "confidence_score": 0.8,
            "summary": {"days_to_critical": 35, "forecasted_storage_pct": 22.0, "capacity_mcm": 300.0},
        }
    )
    titles = " ".join(a["title"].lower() for a in actions)
    assert "reduce release" in titles
    assert any(a["decision_type"] == "reservoir_release" for a in actions)
    assert any(a.get("estimated_water_saved_mcm", 0) > 0 for a in actions)


def test_generator_from_demand_growth():
    actions = generate_from_demand(
        {
            "trained": True,
            "today_predicted_demand_mgd": 120.0,
            "confidence_score": 0.75,
            "risk_label": "HIGH",
            "summary": {
                "growth_pct": 16.0,
                "predicted_peak_demand_mgd": 130.0,
                "capacity_utilization_pct": 92.0,
                "expected_shortage_risk": "HIGH",
            },
        }
    )
    titles = " ".join(a["title"].lower() for a in actions)
    assert "pump" in titles
    assert any(a["decision_type"] == "pump_scheduling" for a in actions)


def test_ranking_orders_by_score():
    raw = [
        {
            "id": "a",
            "impact_score": 40,
            "risk_reduction_score": 20,
            "estimated_water_saved_mcm": 1,
            "population_protected": 1000,
            "estimated_cost_inr": 1_000_000,
            "implementation_priority": "monitor",
        },
        {
            "id": "b",
            "impact_score": 90,
            "risk_reduction_score": 80,
            "estimated_water_saved_mcm": 10,
            "population_protected": 100_000,
            "estimated_cost_inr": 100_000,
            "implementation_priority": "immediate",
        },
    ]
    ranked = rank_actions(raw)
    assert ranked[0]["id"] == "b"
    assert ranked[0]["rank"] == 1
    assert ranked[0]["optimization_score"] >= ranked[1]["optimization_score"]


def test_engine_optimize_and_compare():
    engine = DecisionOptimizationEngine()
    demand = {
        "trained": True,
        "today_predicted_demand_mgd": 110,
        "confidence_score": 0.7,
        "summary": {"growth_pct": 12, "capacity_utilization_pct": 88, "predicted_peak_demand_mgd": 120},
    }
    reservoir = {
        "trained": True,
        "forecasted_storage_pct": 18,
        "capacity_mcm": 250,
        "confidence_score": 0.75,
        "summary": {"days_to_critical": 20, "capacity_mcm": 250},
    }
    stress = {
        "water_stress_index": 72,
        "risk_label": "HIGH",
        "confidence": 0.7,
        "population_impact": 210000,
        "region": {"name": "Ward 8", "region_id": "WARD-08"},
        "recommended_actions": [
            {"id": "x", "title": "Reduce industrial allocation", "description": "Cut 5%", "priority": "immediate"}
        ],
        "executive_insights": ["Population at risk exceeds 210,000."],
    }
    pack = engine.optimize(demand=demand, reservoir=reservoir, stress=stress, max_actions=10)
    assert pack["recommendations"]
    assert pack["priority_queue"]
    assert pack["operational_timeline"]
    assert pack["expected_outcomes"]["estimated_water_saved_mcm"] >= 0
    assert pack["ai_reasoning_summary"]

    cmp = engine.compare(
        demand=demand, reservoir=reservoir, stress=stress, max_actions=6, aggressiveness=1.0
    )
    sc = cmp["scenario_comparison"]
    assert sc["current"]["water_saved_mcm"] == 0
    assert sc["optimized"]["water_saved_mcm"] >= sc["current"]["water_saved_mcm"]
    assert sc["delta"]["population_protected"] >= 0


def test_strategy_comparison_delta():
    actions = [
        {
            "id": "1",
            "estimated_water_saved_mcm": 18,
            "population_protected": 100000,
            "estimated_cost_inr": 500000,
            "estimated_benefit_inr": 2_000_000,
            "risk_reduction_score": 70,
        }
    ]
    result = build_strategy_comparison(
        optimized_actions=actions,
        demand=None,
        reservoir={"forecasted_storage_pct": 25},
        stress={"water_stress_index": 70, "risk_label": "HIGH", "population_impact": 150000},
    )
    assert result["delta"]["water_saved_mcm"] == 18
    assert result["optimized"]["projected_wsi"] < result["current"]["projected_wsi"]


def test_service_integration(trained_registry: ModelRegistry):
    service = DecisionOptimizationService(trained_registry)
    status = service.status()
    assert status["module"] == "decision_optimization"
    assert status["ready"] is True

    data = service.recommend(region_id="WARD-08", horizon_days=14, max_actions=10)
    assert data["recommended_actions"]
    assert data["top_recommendations"]
    assert data["operational_timeline"]
    assert data["expected_outcomes"]
    assert data["ai_reasoning"]
    assert data["upstream_ready"]["demand"] is True
    assert data["upstream_ready"]["reservoir"] is True

    cmp = service.compare(region_id="WARD-08", horizon_days=14, max_actions=6)
    assert cmp["scenario_comparison"]["current"]["label"] == "Do nothing (baseline)"
    assert cmp["scenario_comparison"]["optimized"]["label"] == "Ranked Action Plan"
    assert "estimated impact" in cmp["scenario_comparison"]["optimized"]["description"].lower()
    disclaimer = (cmp["scenario_comparison"].get("disclaimer") or "").lower()
    assert "guaranteed" in disclaimer  # appears as "not ... guaranteed"
    assert "not a mathematically optimal" in disclaimer
    assert "guaranteed water savings" not in disclaimer
    assert "mathematically optimal allocation" not in disclaimer


def test_stress_generator_emergency():
    actions = generate_from_stress(
        {
            "water_stress_index": 85,
            "risk_label": "CRITICAL",
            "confidence": 0.8,
            "population_impact": 300000,
            "region": {"name": "East Zone"},
            "recommended_actions": [],
        }
    )
    assert any("emergency" in a["title"].lower() for a in actions)
