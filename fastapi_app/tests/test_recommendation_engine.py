import os
import sys

# Add workspace directory to path
SYS_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if SYS_PATH not in sys.path:
    sys.path.append(SYS_PATH)


def test_recommendation_engine_route(auth_client):
    """Exercise the authenticated recommendation-engine route over HTTP.

    Direct handler calls are not used — SlowAPI needs a real Request, and the
    router requires a bearer token.
    """
    payload = {
        "water_shortage_prediction": {
            "predicted_risk_score": 68.2,
            "predicted_risk_stage": 1,
            "risk_label": "Moderate Risk (Stage 1)",
            "confidence": 0.88,
            "reservoir_capacity_pct": 34.2,
        },
        "leak_detection": {
            "is_leak_detected": True,
            "leak_probability": 0.89,
            "estimated_water_loss_lpm": 624.0,
            "severity": "CRITICAL BURST",
            "zone": "Zone 3",
        },
        "groundwater_prediction": {
            "projected_depth_m": 128.0,
            "drawdown_rate_m": 3.2,
            "aquifer_status": "Critical Over-Exploited",
        },
        "water_demand": {
            "forecasted_demand_mgd": 120.5,
            "peak_surge_risk": "Critical Surge",
        },
    }

    response = auth_client.post("/ai/recommendation-engine", json=payload)
    assert response.status_code == 200, response.text
    dumped = response.json()

    assert dumped["success"] is True
    data = dumped["data"]
    assert "recommendations" in data
    assert "expected_saving" in data
    assert "text_summary" in data

    # Check the synthesis actually grounds itself in the request's inputs
    # rather than returning boilerplate. Exact wording isn't stable across
    # rules-fallback vs. Gemini synthesis, so assert on content, not phrasing.
    assert "Zone 3" in data["text_summary"]
    assert len(data["recommendations"]) > 0
    assert len(data["expected_saving"]) > 0
