"""Product hardening: scenarios, recommendation feedback, AquaLens comparison."""
from __future__ import annotations

from fastapi_app.prediction.models.water_stress.scenarios import (
    WHAT_IF_PRESETS,
    normalize_scenario,
    preset_catalog,
)
from fastapi_app.services import vision_history_service


REQUIRED_PRESET_IDS = {
    "baseline",
    "drought_rainfall_deficit",
    "heatwave",
    "increased_demand",
    "leakage_increase",
    "conservation",
}


def test_what_if_presets_cover_product_scenarios():
    ids = {p["id"] for p in WHAT_IF_PRESETS}
    assert REQUIRED_PRESET_IDS.issubset(ids)
    catalog = preset_catalog()
    assert all("description" in p for p in catalog)
    # Leakage must map through existing demand knob — no invented formula field.
    leakage = next(p for p in WHAT_IF_PRESETS if p["id"] == "leakage_increase")
    assert "demand_delta_pct" in leakage["scenario"]
    assert "leak_rate" not in leakage["scenario"]


def test_normalize_scenario_clamps_without_new_keys():
    out = normalize_scenario({"rainfall_delta_pct": -200, "demand_delta_pct": 5})
    assert out["rainfall_delta_pct"] == -80.0
    assert out["demand_delta_pct"] == 5.0
    assert "leakage_delta_pct" not in out


def test_vision_comparison_requires_same_asset_label():
    class Prev:
        asset_label = "Reservoir A"
        vision_mode = "reservoir"
        reservoir_health = 60
        turbidity_index = 1.2
        shoreline_exposure_pct = 10.0
        confidence = 0.8
        created_at = None

    skipped = vision_history_service.build_comparison(
        Prev(),
        {"reservoir_health": 70, "asset_label": "Reservoir B", "vision_mode": "reservoir"},
        asset_label="Reservoir B",
        vision_mode="reservoir",
    )
    assert skipped is not None
    assert skipped["comparable"] is False
    assert "asset label" in skipped["warning"].lower()

    ok = vision_history_service.build_comparison(
        Prev(),
        {"reservoir_health": 70, "vision_mode": "reservoir"},
        asset_label="Reservoir A",
        vision_mode="reservoir",
    )
    assert ok["comparable"] is True
    assert ok["reservoir_health_delta"] == 10


def test_vision_find_previous_ignores_unlabeled_scans():
    class FakeQuery:
        def filter(self, *args, **kwargs):
            return self

        def order_by(self, *args, **kwargs):
            return self

        def first(self):
            raise AssertionError("query should short-circuit when label missing")

    class FakeDb:
        def query(self, *args, **kwargs):
            return FakeQuery()

    assert (
        vision_history_service.find_previous_analysis(
            FakeDb(), asset_label=None, vision_mode="reservoir", user_id="x"
        )
        is None
    )
    assert (
        vision_history_service.find_previous_analysis(
            FakeDb(), asset_label="  ", vision_mode="reservoir"
        )
        is None
    )


def test_vision_metrics_match_for_dedupe():
    class Row:
        reservoir_health = 55
        overall_risk = "Moderate"
        shoreline_exposure_pct = 40.0
        confidence = 0.9

    assert vision_history_service._metrics_match(
        Row(),
        {
            "reservoir_health": 55,
            "overall_risk": "moderate",
            "shoreline_exposure_pct": 40.2,
            "confidence": 0.91,
        },
    )
    assert not vision_history_service._metrics_match(
        Row(),
        {"reservoir_health": 70, "overall_risk": "Moderate", "confidence": 0.9},
    )


def test_recommendation_feedback_requires_auth(api_client):
    response = api_client.post(
        "/api/v1/recommendations/feedback",
        json={"recommendation_id": "DEC-1", "action": "accepted"},
    )
    assert response.status_code == 401


def test_recommendation_feedback_idempotent_upsert(auth_client):
    payload = {
        "recommendation_id": "TEST-REC-FEEDBACK-1",
        "action": "accepted",
        "source": "decision",
        "note": "pilot review",
    }
    first = auth_client.post("/api/v1/recommendations/feedback", json=payload)
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["success"] is True
    assert body["data"]["action"] == "accepted"
    assert body["data"]["persisted"] is True
    assert "Measured savings" in body["disclaimer"] or "intent" in body["disclaimer"].lower()

    second = auth_client.post(
        "/api/v1/recommendations/feedback",
        json={**payload, "action": "deferred", "note": "wait for monsoon"},
    )
    assert second.status_code == 200
    assert second.json()["data"]["action"] == "deferred"

    listed = auth_client.get(
        "/api/v1/recommendations/feedback",
        params={"recommendation_id": "TEST-REC-FEEDBACK-1"},
    )
    assert listed.status_code == 200
    rows = listed.json()["data"]
    assert len(rows) == 1
    assert rows[0]["action"] == "deferred"


def test_recommendation_feedback_rejects_invalid_action(auth_client):
    response = auth_client.post(
        "/api/v1/recommendations/feedback",
        json={"recommendation_id": "TEST-REC-FEEDBACK-2", "action": "maybe"},
    )
    assert response.status_code == 422


def test_stress_status_exposes_new_presets(auth_client):
    response = auth_client.get("/api/v1/predictions/stress/status")
    assert response.status_code == 200
    presets = response.json().get("what_if_presets") or []
    ids = {p["id"] for p in presets}
    assert "drought_rainfall_deficit" in ids
    assert "conservation" in ids
