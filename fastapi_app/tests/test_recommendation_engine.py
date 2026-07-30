import os
import sys
import asyncio

# Add workspace directory to path
SYS_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if SYS_PATH not in sys.path:
    sys.path.append(SYS_PATH)

from fastapi_app.routers.recommendations import generate_ai_recommendations
from fastapi_app.schemas import AIRecommendationEngineRequest

async def _run_recommendation_engine_check():
    print("Constructing AIRecommendationEngineRequest request payload...")
    payload = AIRecommendationEngineRequest(
        water_shortage_prediction={
            "predicted_risk_score": 68.2,
            "predicted_risk_stage": 1,
            "risk_label": "Moderate Risk (Stage 1)",
            "confidence": 0.88,
            "reservoir_capacity_pct": 34.2
        },
        leak_detection={
            "is_leak_detected": True,
            "leak_probability": 0.89,
            "estimated_water_loss_lpm": 624.0,
            "severity": "CRITICAL BURST",
            "zone": "Zone 3"
        },
        groundwater_prediction={
            "projected_depth_m": 128.0,
            "drawdown_rate_m": 3.2,
            "aquifer_status": "Critical Over-Exploited"
        },
        water_demand={
            "forecasted_demand_mgd": 120.5,
            "peak_surge_risk": "Critical Surge"
        }
    )

    print("Triggering generate_ai_recommendations route handler directly...")
    response = await generate_ai_recommendations(payload)
    
    print("\nAssertion check on response output data:")
    dumped = response.model_dump()
    print(dumped)
    
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
    
    print("\nALL RECOMMENDATION ENGINE ROUTE TESTS PASSED!")


def test_recommendation_engine_route():
    """pytest entry point — was previously named run_test() so pytest never
    collected it (0 tests silently reported as coverage that didn't exist)."""
    asyncio.run(_run_recommendation_engine_check())


if __name__ == "__main__":
    asyncio.run(_run_recommendation_engine_check())
