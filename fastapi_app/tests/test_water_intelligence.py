"""Unit tests for Water Intelligence fusion helpers (no model .pkl required)."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from fastapi_app.services.groundwater_metrics import (
    classify_trend,
    days_to_critical_threshold,
    depletion_rate_m_year,
    enrich_groundwater_prediction,
    metrics_from_series,
)
from fastapi_app.services.leak_loss_estimator import enrich_leak_result, estimate_leak_loss
from fastapi_app.services.water_stress_service import (
    DEFAULT_WEIGHTS,
    compute_water_stress_index,
    stage_from_score,
)


def test_leak_loss_suppressed_for_low_probability():
    out = estimate_leak_loss(0.05, is_leak_detected=False)
    assert out["estimated_water_loss_lpm"] == 0.0
    assert out["method"] == "heuristic_orifice"


def test_leak_loss_increases_with_probability_and_pressure():
    low = estimate_leak_loss(0.4, pressure_drop_bar=0.5, is_leak_detected=True)
    high = estimate_leak_loss(0.95, pressure_drop_bar=2.5, is_leak_detected=True)
    assert high["estimated_water_loss_lpm"] > low["estimated_water_loss_lpm"]
    assert high["daily_loss_mld"] > 0
    assert 0 < high["confidence"] <= 1


def test_leak_loss_capped():
    out = estimate_leak_loss(1.0, pressure_drop_bar=50.0, pipe_diameter_m=1.0, is_leak_detected=True)
    assert out["estimated_water_loss_lpm"] <= 5000.0


def test_enrich_leak_keeps_telemetry_loss():
    enriched = enrich_leak_result(
        {"is_leak_detected": True, "leak_probability": 0.9, "estimated_water_loss_lpm": 420.0}
    )
    assert enriched["estimated_water_loss_lpm"] == 420.0
    assert enriched["method"] == "telemetry_alert"


def test_depletion_rate_positive_when_depth_increases():
    rate = depletion_rate_m_year([10.0, 12.0, 14.0], timestamps_days=[0.0, 182.625, 365.25])
    assert rate == 4.0  # +4 m over one year


def test_depletion_trend_and_horizon():
    assert classify_trend(4.0) == "Accelerating depletion"
    assert classify_trend(0.0) == "Stable"
    assert days_to_critical_threshold(20.0, 4.0, critical_depth_m=40.0) == round(5.0 * 365.25, 1)
    assert days_to_critical_threshold(45.0, 2.0, critical_depth_m=40.0) == 0.0
    assert days_to_critical_threshold(20.0, 0.0) is None


def test_metrics_from_series():
    metrics = metrics_from_series([15.0, 16.0, 18.0], timestamps_days=[0.0, 100.0, 365.25])
    assert metrics["depletion_rate_m_year"] > 0
    assert metrics["samples"] == 3
    assert "depletion_trend" in metrics


def test_enrich_groundwater_adds_horizon():
    out = enrich_groundwater_prediction(
        {"projected_depth_m": 25.0, "drawdown_rate_m": 2.5, "aquifer_status": "test"}
    )
    assert out["days_to_critical_threshold"] is not None
    assert out["depletion_rate_m_year"] == 2.5


def test_wsi_weights_sum_to_one():
    assert abs(sum(DEFAULT_WEIGHTS.values()) - 1.0) < 1e-9


def test_wsi_stage_boundaries():
    assert stage_from_score(10) == "Low"
    assert stage_from_score(40) == "Moderate"
    assert stage_from_score(60) == "High"
    assert stage_from_score(80) == "Critical"


def test_wsi_high_stress_when_all_components_critical():
    result = compute_water_stress_index(
        shortage={"predicted_risk_score": 90, "predicted_risk_stage": 3, "reservoir_capacity_pct": 12},
        groundwater={"projected_depth_m": 45, "depletion_rate_m_year": 5.0, "aquifer_status": "Critical"},
        leak={"is_leak_detected": True, "leak_probability": 0.95, "estimated_water_loss_lpm": 900},
        demand={"forecasted_demand_mgd": 140, "peak_surge_risk": "Critical Surge"},
        climate={"spi3_proxy": -2.0, "rainfall_deficit_pct": -40, "heatwave_warning": True},
    )
    assert result["water_stress_index"] >= 70
    assert result["stage"] in ("High", "Critical")
    assert len(result["drivers"]) == 3
    assert abs(sum(result["weights"].values()) - 1.0) < 1e-6
    assert "shortage" in result["components"]


def test_wsi_low_stress_when_healthy():
    result = compute_water_stress_index(
        shortage={"predicted_risk_score": 15, "predicted_risk_stage": 0, "reservoir_capacity_pct": 85},
        groundwater={"projected_depth_m": 8, "depletion_rate_m_year": 0.1, "aquifer_status": "Stable"},
        leak={"is_leak_detected": False, "leak_probability": 0.05, "estimated_water_loss_lpm": 0},
        demand={"forecasted_demand_mgd": 40, "peak_surge_risk": "Normal Baseline"},
        climate={"spi3_proxy": 0.5, "rainfall_deficit_pct": 10, "heatwave_warning": False},
    )
    assert result["water_stress_index"] < 40
    assert result["stage"] in ("Low", "Moderate")


def test_wsi_climate_spi_raises_stress():
    dry = compute_water_stress_index(
        shortage={"predicted_risk_score": 40},
        groundwater={"projected_depth_m": 20, "depletion_rate_m_year": 1.0},
        leak={"leak_probability": 0.1},
        demand={"forecasted_demand_mgd": 80, "peak_surge_risk": "Normal Baseline"},
        climate={"spi3_proxy": -2.0, "rainfall_deficit_pct": -30, "heatwave_warning": True},
    )
    wet = compute_water_stress_index(
        shortage={"predicted_risk_score": 40},
        groundwater={"projected_depth_m": 20, "depletion_rate_m_year": 1.0},
        leak={"leak_probability": 0.1},
        demand={"forecasted_demand_mgd": 80, "peak_surge_risk": "Normal Baseline"},
        climate={"spi3_proxy": 1.5, "rainfall_deficit_pct": 20, "heatwave_warning": False},
    )
    assert dry["components"]["climate"]["score"] > wet["components"]["climate"]["score"]
    assert dry["water_stress_index"] > wet["water_stress_index"]


def test_water_intelligence_response_mapping():
    """Router helper shape used by /analytics/water-stress."""
    from fastapi_app.routers.water_intelligence import _to_response_data

    payload = {
        "water_stress": compute_water_stress_index(
            shortage={"predicted_risk_score": 55},
            climate={"spi3_proxy": -1.0},
        ),
        "shortage": {"predicted_risk_score": 55},
        "leak": {"leak_probability": 0.2, "demo": True},
        "groundwater": {"projected_depth_m": 22},
        "demand": {"forecasted_demand_mgd": 90},
        "climate": {"spi3_proxy": -1.0},
        "context": {"reservoirs_sampled": 3},
    }
    data = _to_response_data(payload)
    assert data.water_stress.water_stress_index >= 0
    assert data.context["reservoirs_sampled"] == 3


def test_wsi_demo_leak_is_muted():
    muted = compute_water_stress_index(
        shortage={"predicted_risk_score": 40},
        groundwater={"projected_depth_m": 20, "depletion_rate_m_year": 1.0},
        leak={
            "demo": True,
            "is_leak_detected": True,
            "leak_probability": 0.89,
            "estimated_water_loss_lpm": 670,
        },
        demand={"forecasted_demand_mgd": 50, "peak_surge_risk": "Normal Baseline"},
        climate={"spi3_proxy": 0.0},
    )
    live = compute_water_stress_index(
        shortage={"predicted_risk_score": 40},
        groundwater={"projected_depth_m": 20, "depletion_rate_m_year": 1.0},
        leak={
            "demo": False,
            "is_leak_detected": True,
            "leak_probability": 0.89,
            "estimated_water_loss_lpm": 670,
        },
        demand={"forecasted_demand_mgd": 50, "peak_surge_risk": "Normal Baseline"},
        climate={"spi3_proxy": 0.0},
    )
    assert muted["components"]["leakage"]["score"] < 40
    assert live["components"]["leakage"]["score"] > muted["components"]["leakage"]["score"]
    assert muted["water_stress_index"] < live["water_stress_index"]


if __name__ == "__main__":
    test_leak_loss_suppressed_for_low_probability()
    test_leak_loss_increases_with_probability_and_pressure()
    test_leak_loss_capped()
    test_enrich_leak_keeps_telemetry_loss()
    test_depletion_rate_positive_when_depth_increases()
    test_depletion_trend_and_horizon()
    test_metrics_from_series()
    test_enrich_groundwater_adds_horizon()
    test_wsi_weights_sum_to_one()
    test_wsi_stage_boundaries()
    test_wsi_high_stress_when_all_components_critical()
    test_wsi_low_stress_when_healthy()
    test_wsi_climate_spi_raises_stress()
    test_water_intelligence_response_mapping()
    test_wsi_demo_leak_is_muted()
    print("All water intelligence unit tests passed.")
