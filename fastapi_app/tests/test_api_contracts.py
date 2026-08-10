"""API contract tests — shared Pydantic schemas and validation rules.

These tests pin the response shapes that the dashboard and prediction pages
depend on. They deliberately do not hit live models; fixtures and constructed
payloads exercise validation, null semantics, and backward-compatible extras.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from fastapi_app.core.data_quality import Method, build_metadata
from fastapi_app.prediction.models.water_demand.schemas import DemandPredictRequest
from fastapi_app.schemas import (
    ClimateRiskAnalyzeBody,
    DataQualityMetadata,
    GroundwaterWellRequest,
    LeakDetectionData,
    RecommendationData,
    RecommendationItem,
    ShortagePredictionRequest,
    VisionAnalysisData,
    VisionAnalysisResponse,
    WaterIntelligenceData,
    WaterIntelligenceRequest,
    WaterIntelligenceResponse,
)

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_WI = ROOT / "fastapi_app" / "demo_fixtures" / "water_intelligence.json"
FIXTURE_REC = ROOT / "fastapi_app" / "demo_fixtures" / "recommendations.json"
FIXTURE_VISION = ROOT / "fastapi_app" / "demo_fixtures" / "vision_reservoir.json"


def _load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.pop("_fixture", None)
    return payload


# ----------------------------------------------------------------------
# Water intelligence
# ----------------------------------------------------------------------


def test_water_intelligence_fixture_validates():
    raw = _load_json(FIXTURE_WI)
    data = WaterIntelligenceData.model_validate(
        {
            "water_stress": raw["water_stress"],
            "shortage": raw.get("shortage") or {},
            "leak": raw.get("leak") or {},
            "groundwater": raw.get("groundwater") or {},
            "demand": raw.get("demand") or {},
            "climate": raw.get("climate") or {},
            "context": raw.get("context"),
            "metadata": raw.get("metadata") or {},
        }
    )
    assert 0.0 <= data.water_stress.water_stress_index <= 100.0
    assert data.shortage.predicted_risk_score is not None
    dumped = data.shortage.model_dump()
    assert "aggregation" in dumped or raw["shortage"].get("aggregation") is None


def test_water_intelligence_optional_components_default():
    minimal = {
        "water_stress": _load_json(FIXTURE_WI)["water_stress"],
    }
    data = WaterIntelligenceData.model_validate(minimal)
    assert data.shortage.model_dump() is not None
    assert data.leak.is_leak_detected is None
    assert data.metadata == {}


def test_water_intelligence_null_measurements_accepted():
    base = _load_json(FIXTURE_WI)
    base["leak"] = {
        "is_leak_detected": None,
        "leak_probability": None,
        "estimated_water_loss_lpm": None,
        "daily_loss_mld": None,
    }
    base["demand"] = {
        "forecasted_demand_mgd": None,
        "daily_demand_mgd": None,
        "confidence": None,
    }
    data = WaterIntelligenceData.model_validate(
        {
            "water_stress": base["water_stress"],
            "shortage": base.get("shortage") or {},
            "leak": base["leak"],
            "groundwater": base.get("groundwater") or {},
            "demand": base["demand"],
            "climate": base.get("climate") or {},
            "metadata": {},
        }
    )
    assert data.leak.leak_probability is None
    assert data.demand.forecasted_demand_mgd is None
    assert data.leak.estimated_water_loss_lpm is None


def test_water_intelligence_response_envelope():
    raw = _load_json(FIXTURE_WI)
    data = WaterIntelligenceData.model_validate(
        {
            "water_stress": raw["water_stress"],
            "shortage": raw.get("shortage") or {},
            "leak": raw.get("leak") or {},
            "groundwater": raw.get("groundwater") or {},
            "demand": raw.get("demand") or {},
            "climate": raw.get("climate") or {},
            "metadata": raw.get("metadata") or {},
        }
    )
    envelope = WaterIntelligenceResponse(data=data)
    dumped = envelope.model_dump()
    assert dumped["success"] is True
    assert "timestamp" in dumped
    assert "message" in dumped
    assert dumped["data"]["water_stress"]["water_stress_index"] is not None


def test_legacy_shortage_fields_preserved():
    """New frontend prefers typed fields; legacy keys remain via extra=allow."""
    raw = _load_json(FIXTURE_WI)
    data = WaterIntelligenceData.model_validate(
        {
            "water_stress": raw["water_stress"],
            "shortage": {
                **raw["shortage"],
                "legacy_custom_flag": True,
                "pct_reservoirs_critical": 28.6,
            },
            "leak": raw.get("leak") or {},
            "groundwater": raw.get("groundwater") or {},
            "demand": raw.get("demand") or {},
            "climate": raw.get("climate") or {},
        }
    )
    dumped = data.shortage.model_dump()
    assert dumped.get("legacy_custom_flag") is True
    assert dumped.get("pct_reservoirs_critical") == 28.6


# ----------------------------------------------------------------------
# Request validation (reject impossible client input)
# ----------------------------------------------------------------------


def test_reject_invalid_percentage_override():
    with pytest.raises(ValidationError):
        WaterIntelligenceRequest(reservoir_capacity_pct=150.0)


def test_reject_invalid_probability_override():
    with pytest.raises(ValidationError):
        WaterIntelligenceRequest(leak_probability=1.5)


def test_reject_negative_demand_override():
    with pytest.raises(ValidationError):
        WaterIntelligenceRequest(daily_demand_mgd=-2.0)


def test_reject_negative_leak_loss_override():
    with pytest.raises(ValidationError):
        WaterIntelligenceRequest(estimated_water_loss_lpm=-1.0)


def test_reject_negative_groundwater_depth_override():
    with pytest.raises(ValidationError):
        WaterIntelligenceRequest(current_depth_m=-5.0)


def test_reject_invalid_coordinates():
    with pytest.raises(ValidationError):
        GroundwaterWellRequest(current_depth_m=10.0, latitude=120.0, longitude=77.0)
    with pytest.raises(ValidationError):
        GroundwaterWellRequest(current_depth_m=10.0, latitude=28.0, longitude=200.0)
    with pytest.raises(ValidationError):
        ClimateRiskAnalyzeBody(lat=95.0, lon=77.0)


def test_reject_invalid_shortage_request_percentage():
    with pytest.raises(ValidationError):
        ShortagePredictionRequest(
            reservoir_capacity_pct=-1.0,
            rainfall_deficit_pct=-20.0,
            temperature_c=32.0,
            daily_demand_mgd=88.0,
        )


def test_reject_invalid_forecast_horizon():
    with pytest.raises(ValidationError):
        DemandPredictRequest(horizon_days=0)
    with pytest.raises(ValidationError):
        DemandPredictRequest(horizon_days=400)
    with pytest.raises(ValidationError):
        DemandPredictRequest(value=-1, unit="days")


def test_reject_out_of_range_component_confidence():
    raw = _load_json(FIXTURE_WI)
    with pytest.raises(ValidationError):
        WaterIntelligenceData.model_validate(
            {
                "water_stress": raw["water_stress"],
                "shortage": {**raw["shortage"], "confidence": 2.5},
                "leak": raw.get("leak") or {},
                "groundwater": raw.get("groundwater") or {},
                "demand": raw.get("demand") or {},
                "climate": raw.get("climate") or {},
            }
        )


# ----------------------------------------------------------------------
# Recommendations, vision, metadata
# ----------------------------------------------------------------------


def test_recommendation_response_shape():
    item = RecommendationItem(
        id="rec-1",
        priority="high",
        category="leak",
        title="Inspect DMA corridor",
        action_description="Dispatch crew to highest-loss DMA.",
        estimated_impact="Reduce non-revenue water",
        target_sector="utility",
    )
    data = RecommendationData(
        region_id="IN-GJ",
        overall_health_index=72.0,
        recommendations=[item],
        policy_guidelines=["Prioritize non-revenue water reduction."],
    )
    dumped = data.model_dump()
    assert dumped["recommendations"][0]["id"] == "rec-1"
    assert dumped["overall_health_index"] == 72.0


def test_recommendation_fixture_engine_shape():
    """AI engine fixture uses string list recommendations — not RecommendationItem."""
    raw = _load_json(FIXTURE_REC)
    assert isinstance(raw["recommendations"], list)
    assert all(isinstance(x, str) for x in raw["recommendations"])
    assert "text_summary" in raw
    assert "expected_saving" in raw


def test_vision_response_shape_from_fixture():
    raw = _load_json(FIXTURE_VISION)
    body = VisionAnalysisData.model_validate(raw)
    assert body.reservoir_health is not None
    assert 0.0 <= body.confidence <= 1.0
    envelope = VisionAnalysisResponse(
        success=True,
        message="AquaLens analysis completed.",
        vision_mode="reservoir",
        data=body,
    )
    dumped = envelope.model_dump()
    assert dumped["success"] is True
    assert dumped["data"]["shoreline_exposure_pct"] == 22


def test_vision_rejects_invalid_confidence():
    with pytest.raises(ValidationError):
        VisionAnalysisData(confidence=1.4, reservoir_health=50)


def test_model_metadata_serialization():
    meta = build_metadata(
        source="water_demand_model + consumption_series",
        method=Method.TRAINED_MODEL,
        confidence=0.93,
        observed_at="2026-07-26T00:00:00+00:00",
        model_version="water_demand_model:RandomForestRegressor@2026-07-26",
        unit="million_gallons_per_day",
    )
    typed = DataQualityMetadata.model_validate(meta)
    dumped = typed.model_dump()
    for key in (
        "source",
        "method",
        "confidence",
        "data_quality",
        "observed_at",
        "generated_at",
        "data_age_seconds",
        "model_version",
    ):
        assert key in dumped
    assert dumped["confidence"] == 0.93
    assert dumped["method"] == "trained_model"


def test_leak_detection_rejects_negative_loss():
    with pytest.raises(ValidationError):
        LeakDetectionData(
            is_leak_detected=True,
            leak_probability=0.8,
            severity="high",
            note="test",
            estimated_water_loss_lpm=-3.0,
        )
