"""Tests for Water Stress Intelligence fusion layer."""
from __future__ import annotations

import pytest

from fastapi_app.core.contracts import RiskLevel
from fastapi_app.decision_engine.rules import recommendation_from_prediction
from fastapi_app.prediction.base import PredictionOutput
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
from fastapi_app.prediction.models.water_stress.fusion import fuse_water_stress
from fastapi_app.prediction.models.water_stress.regions import DEFAULT_REGIONS, load_regions
from fastapi_app.prediction.models.water_stress.risk import risk_display_label, stress_risk_level
from fastapi_app.prediction.models.water_stress.scenarios import normalize_scenario
from fastapi_app.prediction.models.water_stress.service import WaterStressIntelligenceService


@pytest.fixture(scope="module")
def trained_registry(tmp_path_factory) -> ModelRegistry:
    pytest.importorskip("xgboost")
    root = tmp_path_factory.mktemp("stress_upstream")
    demand_csv = root / "demand.csv"
    res_csv = root / "reservoir.csv"
    gen_demand(demand_csv, days=320, seed=3)
    gen_reservoir(res_csv, days=320, seed=5)

    demand = build_water_demand_model(artifacts_dir=root / "d_art", autoload=False, model_version="s-1")
    reservoir = build_reservoir_forecast_model(
        artifacts_dir=root / "r_art", autoload=False, model_version="s-1"
    )
    demand.train(
        TrainingDataset(
            DemandDatasetLoader().load_csv(demand_csv),
            feature_columns=[],
            target_column="demand_mgd",
        ),
        TrainingConfiguration(model_name="water_demand", model_version="s-1", random_seed=3),
    )
    reservoir.train(
        TrainingDataset(
            ReservoirDatasetLoader().load_csv(res_csv),
            feature_columns=[],
            target_column="storage_pct",
        ),
        TrainingConfiguration(model_name="reservoir_forecast", model_version="s-1", random_seed=5),
    )
    registry = ModelRegistry()
    registry.register("water_demand", demand)
    registry.register("reservoir_forecast", reservoir)
    return registry


def test_risk_bands():
    assert risk_display_label(10) == "HEALTHY"
    assert risk_display_label(30) == "LOW"
    assert risk_display_label(50) == "MODERATE"
    assert risk_display_label(70) == "HIGH"
    assert risk_display_label(90) == "CRITICAL"
    assert stress_risk_level(90) == RiskLevel.CRITICAL
    assert stress_risk_level(10) == RiskLevel.LOW


def test_regions_catalog():
    regions = load_regions()
    assert len(regions) >= 4
    types = {r["region_type"] for r in regions}
    assert "ward" in types
    assert "zone" in types


def test_fusion_without_upstream():
    region = DEFAULT_REGIONS[1]  # Ward 8
    result = fuse_water_stress(region=region, demand=None, reservoir=None)
    assert 0 <= result["water_stress_index"] <= 100
    assert result["risk_label"] in {"HEALTHY", "LOW", "MODERATE", "HIGH", "CRITICAL"}
    assert "components" in result
    assert result["population_impact"] >= 0


def test_scenario_worsens_with_dry_rainfall():
    region = DEFAULT_REGIONS[1]
    base = fuse_water_stress(region=region, demand=None, reservoir=None)
    dry = fuse_water_stress(
        region=region,
        demand=None,
        reservoir=None,
        scenario={"rainfall_delta_pct": -30, "demand_delta_pct": 20},
    )
    assert dry["water_stress_index"] >= base["water_stress_index"] - 0.5


def test_predict_and_simulate(trained_registry: ModelRegistry):
    service = WaterStressIntelligenceService(trained_registry)
    status = service.status()
    assert status["ready"] is True
    assert status["regions"]

    data = service.predict(region_id="WARD-08", horizon_days=14)
    assert data["water_stress_index"] is not None
    assert data["summary"]["predicted_stress"] == data["water_stress_index"]
    assert data["map_regions"]
    assert data["series"]
    assert data["recommended_actions"]
    assert data["executive_insights"]
    assert data["regional_comparison"]

    sim = service.simulate(
        region_id="WARD-08",
        horizon_days=14,
        scenario={"rainfall_delta_pct": -30},
        preset_id=None,
    )
    assert sim["mode"] == "simulate"
    assert sim["scenario"]["rainfall_delta_pct"] == -30
    assert sim["summary"]["delta_vs_baseline"] is not None


def test_what_if_preset(trained_registry: ModelRegistry):
    service = WaterStressIntelligenceService(trained_registry)
    sim = service.simulate(region_id="WARD-08", preset_id="increased_demand", horizon_days=10)
    assert sim["preset_id"] == "increased_demand"
    assert sim["scenario"].get("demand_delta_pct") == 20


def test_decision_engine_integration(trained_registry: ModelRegistry):
    service = WaterStressIntelligenceService(trained_registry)
    data = service.predict(region_id="WARD-08", horizon_days=10)
    po = PredictionOutput(**data["decision_engine"]["prediction"])
    rec = recommendation_from_prediction(po, RiskLevel(data["risk_level"]))
    assert rec.actions
    assert data["decision_engine"]["prediction_type"] == "water_stress"


def test_map_regions_have_colors(trained_registry: ModelRegistry):
    service = WaterStressIntelligenceService(trained_registry)
    data = service.predict(horizon_days=7, include_all_regions=True)
    for region in data["map_regions"]:
        assert region["map_color"].startswith("#")
        assert "polygon" in region or region.get("lat") is not None


def test_normalize_scenario_clamps():
    sc = normalize_scenario({"rainfall_delta_pct": -200, "demand_delta_pct": 500})
    assert sc["rainfall_delta_pct"] == -80
    assert sc["demand_delta_pct"] == 100
