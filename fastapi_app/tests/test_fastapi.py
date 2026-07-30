"""FastAPI REST API smoke tests.

Previously this file defined `run_tests()` (no `test_` prefix), so pytest
silently collected zero tests from it — CI/local `pytest` runs reported
coverage for these endpoints that didn't actually exist. Renamed to proper
`test_*` functions, and switched to the authenticated fixture since these
endpoints now require a bearer token (see fastapi_app/core/security.py).
"""
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def test_health_check(api_client):
    res = api_client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "healthy"


def test_predict_shortage(auth_client):
    payload = {
        "reservoir_capacity_pct": 34.2,
        "rainfall_deficit_pct": -42.5,
        "temperature_c": 38.5,
        "daily_demand_mgd": 88.0,
    }
    res = auth_client.post("/predict-shortage", json=payload)
    assert res.status_code == 200
    assert res.json()["success"] is True


def test_predict_groundwater(auth_client):
    payload = {
        "initial_depth_m": 124.8,
        "annual_rainfall_mm": 580.0,
        "pumping_extraction_mld": 52.0,
        "aquifer_recharge_factor": 0.18,
        "soil_porosity_idx": 0.22,
    }
    res = auth_client.post("/predict-groundwater", json=payload)
    assert res.status_code == 200
    assert res.json()["success"] is True


def test_predict_demand(auth_client):
    payload = {
        "population_thousands": 1850.0,
        "temperature_c": 40.2,
        "industrial_activity_idx": 92.0,
        "is_weekend": 0,
        "is_heatwave": 1,
    }
    res = auth_client.post("/predict-demand", json=payload)
    assert res.status_code == 200
    assert res.json()["success"] is True


def test_detect_leak(auth_client):
    payload = {
        "pressure_bar": 1.6,
        "pressure_drop_bar": 2.8,
        "acoustic_vibration_db": 88.2,
        "flow_velocity_m_s": 4.1,
        "frequency_spike_hz": 2800.0,
    }
    res = auth_client.post("/detect-leak", json=payload)
    assert res.status_code == 200
    assert res.json()["success"] is True


def test_recommendation_get(auth_client):
    res = auth_client.get("/recommendation?region_id=REG-NORTH-01&shortage_stage=2")
    assert res.status_code == 200


def test_recommendation_post(auth_client):
    res = auth_client.post("/recommendation", json={"region_id": "REG-SOUTH-02"})
    assert res.status_code == 200


def test_weather_get(auth_client):
    res = auth_client.get("/weather?location=Central%20Watershed")
    assert res.status_code == 200


def test_reports_get(auth_client):
    res = auth_client.get("/reports?category=LEAKAGE")
    assert res.status_code == 200


def test_predictions_require_authentication(api_client):
    """Regression guard for the "every router except auth.py was open" finding."""
    res = api_client.post(
        "/predict-shortage",
        json={
            "reservoir_capacity_pct": 34.2,
            "rainfall_deficit_pct": -10.0,
            "temperature_c": 30.0,
            "daily_demand_mgd": 80.0,
        },
    )
    assert res.status_code in (401, 403)
