"""Demo resilience: configuration gating, fixture contracts, and fallback order.

The property under test throughout is that an unavailable optional provider
degrades predictably — to local rules, then (only in demo mode) to a validated
fixture, and otherwise to a clear typed error. Nothing here should be able to
put a fabricated result in front of a user with demo mode off.
"""
from __future__ import annotations

import asyncio
import inspect
import json
import os
import time
from contextlib import contextmanager

import pytest

from fastapi_app.core import ai_fallback, demo_mode
from fastapi_app.core.ai_fallback import (
    SynthesisContractError,
    normalize_recommendation_result,
    recommendation_fixture_result,
    vision_fixture_result,
)
from fastapi_app.core.config import get_settings
from fastapi_app.core.demo_mode import (
    FIXTURE_REQUIRED_FIELDS,
    SOURCE_DEMO_FIXTURE,
    SOURCE_REMOTE_AI,
    SOURCE_RULES_FALLBACK,
    FixtureValidationError,
    ProviderUnavailableError,
    load_fixture,
    should_use_fixture,
    validate_fixture,
)


@contextmanager
def env(**overrides: str | None):
    """Apply env vars and rebuild the cached Settings for the duration."""
    previous = {key: os.environ.get(key) for key in overrides}
    for key, value in overrides.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    get_settings.cache_clear()
    try:
        yield get_settings()
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()


# ---------------------------------------------------------------------------
# 1. Demo mode configuration
# ---------------------------------------------------------------------------


def test_demo_mode_defaults_off_when_setting_is_omitted():
    with env(AQUAMIND_DEMO_MODE=None, AQUAMIND_DEMO_FORCE_FIXTURES=None) as settings:
        assert settings.demo_mode is False
        assert settings.fixtures_enabled is False
        assert settings.fixtures_forced is False


@pytest.mark.parametrize("raw", ["true", "TRUE", "1", "yes", "on"])
def test_demo_mode_enabled_by_truthy_flag(raw: str):
    with env(AQUAMIND_DEMO_MODE=raw) as settings:
        assert settings.demo_mode is True


@pytest.mark.parametrize("raw", ["false", "0", "no", "", "   "])
def test_demo_mode_disabled_by_falsy_flag(raw: str):
    with env(AQUAMIND_DEMO_MODE=raw) as settings:
        assert settings.demo_mode is False


def test_force_fixtures_requires_demo_mode():
    """Forcing fixtures must never take effect on its own."""
    with env(AQUAMIND_DEMO_MODE="false", AQUAMIND_DEMO_FORCE_FIXTURES="true") as settings:
        assert settings.fixtures_forced is False
    with env(AQUAMIND_DEMO_MODE="true", AQUAMIND_DEMO_FORCE_FIXTURES="true") as settings:
        assert settings.fixtures_forced is True


def test_should_use_fixture_is_the_single_gate():
    with env(AQUAMIND_DEMO_MODE="false"):
        assert should_use_fixture(provider_failed=True) is False
    with env(AQUAMIND_DEMO_MODE="true", AQUAMIND_DEMO_FORCE_FIXTURES="false"):
        assert should_use_fixture(provider_failed=False) is False
        assert should_use_fixture(provider_failed=True) is True
    with env(AQUAMIND_DEMO_MODE="true", AQUAMIND_DEMO_FORCE_FIXTURES="true"):
        assert should_use_fixture(provider_failed=False) is True


# ---------------------------------------------------------------------------
# 2. Fixture schema validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(FIXTURE_REQUIRED_FIELDS))
def test_every_checked_in_fixture_satisfies_its_schema(name: str):
    payload = load_fixture(name)
    for field in FIXTURE_REQUIRED_FIELDS[name]:
        assert field in payload, f"{name} fixture is missing {field}"


def test_fixture_validation_rejects_a_drifted_payload():
    with pytest.raises(FixtureValidationError, match="missing required field"):
        validate_fixture("recommendations", {"recommendations": ["a"]})
    with pytest.raises(FixtureValidationError):
        validate_fixture("recommendations", ["not", "an", "object"])
    with pytest.raises(FixtureValidationError, match="Unknown demo fixture"):
        validate_fixture("no_such_fixture", {})


def test_fixture_loads_are_isolated_copies():
    first = load_fixture("recommendations")
    first["recommendations"] = []
    assert load_fixture("recommendations")["recommendations"], "cache was mutated by a caller"


def test_vision_fixture_matches_the_vlm_response_contract():
    result = vision_fixture_result("reservoir")
    assert result["vision_mode"] == "reservoir"
    assert isinstance(result["confidence"], (int, float))
    assert isinstance(result["recommendations"], list) and result["recommendations"]
    assert result["summary"]
    assert result["segmentation"]["available"] is False
    assert result["metadata"]["source"] == SOURCE_DEMO_FIXTURE


def test_no_vision_fixture_is_invented_for_flood_mode():
    with pytest.raises(FixtureValidationError):
        vision_fixture_result("flood")


def test_fixture_is_never_presented_as_current_telemetry():
    """A fixture must be distinguishable from a live reading by its metadata."""
    water = load_fixture("water_intelligence")
    assert water["leak"]["source"] == SOURCE_DEMO_FIXTURE
    assert water["climate"]["climate_source"] == SOURCE_DEMO_FIXTURE

    meta = vision_fixture_result("reservoir")["metadata"]
    assert meta["source"] == SOURCE_DEMO_FIXTURE
    assert meta["data_quality"] == "low"
    assert meta["is_stale"] is True


# ---------------------------------------------------------------------------
# 3. Consistent envelope + metadata across every synthesis path
# ---------------------------------------------------------------------------


def _remote_payload() -> dict:
    return {
        "recommendations": ["Trim municipal supply by 10%."],
        "expected_saving": "1.2 Million Liters",
        "text_summary": "Storage is falling.",
        "source": "gemini",
        "provider": "gemini-2.0-flash-lite",
    }


def _rules_payload() -> dict:
    return {
        "recommendations": ["Run acoustic spot-checks on the highest-loss corridors."],
        "expected_saving": "0.4 Million Liters",
        "text_summary": "Rules synthesis.",
        "source": "rules_fallback",
        "provider": "local-rules",
    }


def test_every_path_returns_the_same_envelope():
    with env(AQUAMIND_DEMO_MODE="true"):
        results = [
            normalize_recommendation_result(_remote_payload()),
            normalize_recommendation_result(_rules_payload()),
            recommendation_fixture_result(),
        ]
    required = ("recommendations", "expected_saving", "text_summary", "source", "provider", "metadata")
    for result in results:
        assert all(field in result for field in required)
        assert result["source"] in (SOURCE_REMOTE_AI, SOURCE_RULES_FALLBACK, SOURCE_DEMO_FIXTURE)
        assert result["metadata"]["source"] == result["source"]
        assert result["metadata"]["generated_at"]


def test_metadata_never_contradicts_the_path_that_ran():
    remote = normalize_recommendation_result(_remote_payload())
    assert remote["source"] == SOURCE_REMOTE_AI
    assert remote["metadata"]["method"] == "remote_ai"
    assert remote["metadata"]["model_version"] == "gemini-2.0-flash-lite"

    rules = normalize_recommendation_result(_rules_payload())
    assert rules["source"] == SOURCE_RULES_FALLBACK
    assert rules["metadata"]["method"] == "rules_engine"
    assert rules["metadata"]["model_version"] == "local-rules"

    with env(AQUAMIND_DEMO_MODE="true"):
        fixture = recommendation_fixture_result()
    assert fixture["source"] == SOURCE_DEMO_FIXTURE
    assert fixture["metadata"]["method"] == "fallback"


def test_cache_hits_keep_the_provenance_of_whatever_produced_them():
    from_remote = normalize_recommendation_result(
        {**_remote_payload(), "source": "cache", "provider": "gemini-2.0-flash-lite"}
    )
    assert from_remote["source"] == SOURCE_REMOTE_AI
    assert from_remote["metadata"]["cached"] is True

    from_rules = normalize_recommendation_result(
        {**_rules_payload(), "source": "cache", "provider": "local-rules"}
    )
    assert from_rules["source"] == SOURCE_RULES_FALLBACK
    assert from_rules["metadata"]["cached"] is True


@pytest.mark.parametrize(
    "payload",
    [
        {"expected_saving": "1 ML", "text_summary": "x"},
        {"recommendations": [], "expected_saving": "1 ML", "text_summary": "x"},
        {"recommendations": ["a"], "expected_saving": "", "text_summary": "x"},
        {"recommendations": ["  "], "expected_saving": "1 ML", "text_summary": "x"},
        "not a dict",
    ],
)
def test_incomplete_synthesis_is_rejected_rather_than_returned(payload):
    with pytest.raises(SynthesisContractError):
        normalize_recommendation_result(payload)


# ---------------------------------------------------------------------------
# 4. Recommendation fallback when remote AI is slow or unavailable
# ---------------------------------------------------------------------------


def test_remote_ai_timeout_falls_back_to_rules_without_retrying_the_provider(monkeypatch, tmp_path):
    import recommendation_engine as engine_module

    attempts: list[str] = []

    def slow_urlopen(req, timeout=None):
        attempts.append(req.full_url)
        raise TimeoutError("simulated hang")

    monkeypatch.setattr(engine_module.urllib.request, "urlopen", slow_urlopen)
    monkeypatch.setattr(engine_module, "CACHE_DIR", tmp_path / "rec_cache")

    engine = engine_module.AIRecommendationEngine()
    engine.api_key = "test-key-not-a-real-secret"

    started = time.monotonic()
    result = engine.generate_recommendations(
        {"predicted_risk_score": 68.0, "predicted_risk_stage": 2, "reservoir_capacity_pct": 30.0},
        {"is_leak_detected": True, "leak_probability": 0.9, "estimated_water_loss_lpm": 600.0, "zone": "Zone 3"},
        {"projected_depth_m": 120.0, "drawdown_rate_m": 3.1},
        {"forecasted_demand_mgd": 110.0, "peak_surge_risk": "Critical Surge"},
        force_refresh=True,
    )
    elapsed = time.monotonic() - started

    assert len(attempts) == 1, "a hung endpoint was retried with another model id"
    assert elapsed < 5, "the fallback did not return promptly"
    assert result["source"] == "rules_fallback"
    assert result["recommendations"], "the rules fallback produced nothing actionable"


def test_rules_fallback_is_operationally_specific():
    import recommendation_engine as engine_module

    stats = engine_module._compact_stats(
        {"predicted_risk_score": 80.0, "predicted_risk_stage": 3, "reservoir_capacity_pct": 22.0},
        {"is_leak_detected": True, "leak_probability": 0.91, "estimated_water_loss_lpm": 640.0, "zone": "DMA-7"},
        {"projected_depth_m": 130.0, "drawdown_rate_m": 3.4},
        {"forecasted_demand_mgd": 118.0, "peak_surge_risk": "Critical Surge"},
    )
    result = engine_module._rules_fallback(stats, "0.9 Million Liters")
    text = " ".join(result["recommendations"])
    assert "DMA-7" in text, "the fallback did not name the affected zone"
    assert "22%" in text, "the fallback did not cite the storage level"
    assert "20%" in text, "the fallback did not scale the supply cut to Stage 3 risk"


def test_gemini_model_list_stops_at_the_total_budget(monkeypatch, tmp_path):
    """A slow-but-responsive endpoint must not consume timeout x model-count."""
    import recommendation_engine as engine_module

    attempts: list[float] = []

    def sluggish_urlopen(req, timeout=None):
        attempts.append(time.monotonic())
        time.sleep(0.3)
        raise ValueError("bad gateway")

    monkeypatch.setattr(engine_module.urllib.request, "urlopen", sluggish_urlopen)
    monkeypatch.setattr(engine_module, "CACHE_DIR", tmp_path / "rec_cache")
    monkeypatch.setenv("AQUAMIND_REMOTE_AI_BUDGET_SEC", "0.5")

    engine = engine_module.AIRecommendationEngine()
    engine.api_key = "test-key-not-a-real-secret"
    with pytest.raises(Exception):
        engine._call_gemini({**engine_module._compact_stats({}, {}, {}, {})}, "0.4 Million Liters")

    assert len(attempts) < len(engine_module.GEMINI_MODELS), "the budget did not cut the model loop short"


def test_recommendation_route_returns_a_complete_payload_on_fallback(auth_client, monkeypatch):
    """The report modal can only finish if the backend always answers 200."""
    from fastapi_app.services.model_service import model_service

    def exploding_engine(*args, **kwargs):
        raise RuntimeError("simulated synthesis outage")

    monkeypatch.setattr(
        model_service.recommendation_engine, "generate_recommendations", exploding_engine
    )

    response = auth_client.get("/ai/recommendation-engine/live?force_refresh=true")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["recommendations"], "fallback response had no actions for the modal to render"
    assert data["expected_saving"]
    assert data["text_summary"]
    assert data["source"] in (SOURCE_RULES_FALLBACK, SOURCE_DEMO_FIXTURE)


def test_live_route_serves_the_fixture_only_in_demo_mode(auth_client, monkeypatch):
    """A total telemetry outage: 200 + fixture in demo mode, 500 otherwise."""
    from fastapi_app.core.ttl_cache import recommendation_cache
    from fastapi_app.services.model_service import model_service

    recommendation_cache.clear()

    def outage(*args, **kwargs):
        raise RuntimeError("simulated telemetry outage")

    monkeypatch.setattr(model_service, "synthesize_live_recommendations", outage)

    with env(AQUAMIND_DEMO_MODE="false"):
        assert auth_client.get("/ai/recommendation-engine/live").status_code == 500

    recommendation_cache.clear()
    with env(AQUAMIND_DEMO_MODE="true"):
        response = auth_client.get("/ai/recommendation-engine/live")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["source"] == SOURCE_DEMO_FIXTURE
    assert data["metadata"]["source"] == SOURCE_DEMO_FIXTURE
    assert data["recommendations"]


def test_forced_fixtures_skip_the_provider_entirely(monkeypatch):
    """The flag must mean the same thing on every surface, not just vision."""
    from fastapi_app.services.model_service import model_service

    called = []

    def tracked(*args, **kwargs):
        called.append(True)
        return {
            "recommendations": ["live"],
            "expected_saving": "1 ML",
            "text_summary": "live",
            "source": "gemini",
            "provider": "gemini-2.0-flash-lite",
        }

    monkeypatch.setattr(model_service.recommendation_engine, "generate_recommendations", tracked)

    with env(AQUAMIND_DEMO_MODE="true", AQUAMIND_DEMO_FORCE_FIXTURES="true"):
        result = model_service.generate_recommendations({}, {}, {}, {})
    assert result["source"] == SOURCE_DEMO_FIXTURE
    assert not called, "the provider was called despite forced fixtures"

    with env(AQUAMIND_DEMO_MODE="true", AQUAMIND_DEMO_FORCE_FIXTURES="false"):
        result = model_service.generate_recommendations({}, {}, {}, {})
    assert result["source"] == SOURCE_REMOTE_AI
    assert called, "demo mode alone should not bypass a working provider"


def test_force_refresh_does_not_return_a_stale_cache_entry(monkeypatch, tmp_path):
    """A Re-synthesize click must never resurrect a previous Gemini/rules payload."""
    import recommendation_engine as engine_module

    monkeypatch.setattr(engine_module, "CACHE_DIR", tmp_path / "rec_cache")
    engine = engine_module.AIRecommendationEngine()
    engine.api_key = ""  # force the rules path so we don't need a network

    stats_inputs = (
        {"predicted_risk_score": 55.0, "predicted_risk_stage": 1, "reservoir_capacity_pct": 48.0},
        {"is_leak_detected": False, "leak_probability": 0.1, "estimated_water_loss_lpm": 0.0, "zone": "n/a"},
        {"projected_depth_m": 90.0, "drawdown_rate_m": 1.0},
        {"forecasted_demand_mgd": 80.0, "peak_surge_risk": "Normal"},
    )
    first = engine.generate_recommendations(*stats_inputs, force_refresh=False)
    first["recommendations"] = ["STALE — must not resurface"]
    # Overwrite the cache entry with a deliberately stale payload.
    key = engine_module._cache_key(engine_module._compact_stats(*stats_inputs))
    engine_module._write_cache(key, first, "local-rules")

    refreshed = engine.generate_recommendations(*stats_inputs, force_refresh=True)
    assert "STALE" not in " ".join(refreshed["recommendations"])
    assert refreshed["source"] == "rules_fallback"


def test_recommendation_fixture_is_never_written_to_the_disk_cache(monkeypatch, tmp_path):
    """A fixture must stay out of the shared cache so a later live call cannot inherit it."""
    import recommendation_engine as engine_module
    from fastapi_app.services.model_service import model_service

    monkeypatch.setattr(engine_module, "CACHE_DIR", tmp_path / "rec_cache")
    cache_dir = tmp_path / "rec_cache"

    with env(AQUAMIND_DEMO_MODE="true", AQUAMIND_DEMO_FORCE_FIXTURES="true"):
        result = model_service.generate_recommendations({}, {}, {}, {})
    assert result["source"] == SOURCE_DEMO_FIXTURE
    assert not list(cache_dir.glob("*.json")) if cache_dir.exists() else True


def test_water_stress_route_serves_the_fixture_only_in_demo_mode(auth_client, monkeypatch):
    from fastapi_app.services.model_service import model_service

    def outage(*args, **kwargs):
        raise RuntimeError("simulated fusion outage")

    monkeypatch.setattr(model_service, "build_water_intelligence", outage)

    with env(AQUAMIND_DEMO_MODE="false"):
        assert auth_client.get("/analytics/water-stress").status_code == 500

    with env(AQUAMIND_DEMO_MODE="true"):
        response = auth_client.get("/analytics/water-stress")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["water_stress"]["water_stress_index"] is not None
    for component in ("water_stress", "shortage", "leak", "groundwater", "demand", "climate"):
        assert data["metadata"][component]["source"] == SOURCE_DEMO_FIXTURE


# ---------------------------------------------------------------------------
# 5. AquaLens resilience
# ---------------------------------------------------------------------------


def _failing_vision_service(monkeypatch):
    from fastapi_app.services.vision_service import vision_service

    async def boom(*args, **kwargs):
        raise RuntimeError("provider unreachable")

    monkeypatch.setattr(vision_service, "_refresh_keys", lambda: None)
    monkeypatch.setattr(vision_service, "gemini_key", "test-key")
    monkeypatch.setattr(vision_service, "openrouter_key", "test-key")
    monkeypatch.setattr(vision_service, "dashscope_key", "test-key")
    monkeypatch.setattr(vision_service, "_analyze_with_gemini", boom)
    monkeypatch.setattr(vision_service, "_analyze_with_qwen_openrouter", boom)
    monkeypatch.setattr(vision_service, "_analyze_with_qwen_dashscope", boom)
    return vision_service


def test_aqualens_falls_back_to_the_fixture_when_every_provider_fails(monkeypatch):
    service = _failing_vision_service(monkeypatch)
    with env(AQUAMIND_DEMO_MODE="true"):
        result = asyncio.run(service.analyze_reservoir_image(b"not-an-image", "demo.jpg"))
    assert result["metadata"]["source"] == SOURCE_DEMO_FIXTURE
    assert result["analysis_mode"] == "demo_fixture"
    assert result["summary"]
    assert result["recommendations"]


def test_aqualens_raises_a_typed_error_when_demo_mode_is_disabled(monkeypatch):
    service = _failing_vision_service(monkeypatch)
    with env(AQUAMIND_DEMO_MODE="false"):
        with pytest.raises(ProviderUnavailableError) as excinfo:
            asyncio.run(service.analyze_reservoir_image(b"not-an-image", "demo.jpg"))
    assert excinfo.value.provider_errors, "the typed error dropped the provider diagnostics"
    assert "demo" not in str(excinfo.value).lower()


def test_aqualens_reports_missing_configuration_distinctly(monkeypatch):
    from fastapi_app.services.vision_service import vision_service

    monkeypatch.setattr(vision_service, "_refresh_keys", lambda: None)
    monkeypatch.setattr(vision_service, "gemini_key", "")
    monkeypatch.setattr(vision_service, "openrouter_key", "")
    monkeypatch.setattr(vision_service, "dashscope_key", "")

    with env(AQUAMIND_DEMO_MODE="false"):
        with pytest.raises(ProviderUnavailableError, match="not configured"):
            asyncio.run(vision_service.analyze_reservoir_image(b"bytes", "demo.jpg"))


def test_a_hung_provider_does_not_hold_the_whole_chain(monkeypatch):
    from fastapi_app.services.vision_service import vision_service

    async def hang(*args, **kwargs):
        await asyncio.sleep(30)

    async def works(*args, **kwargs):
        return {"reservoir_health": 61, "overall_risk": "Moderate", "water_spread": "Moderate"}

    monkeypatch.setattr(vision_service, "_refresh_keys", lambda: None)
    monkeypatch.setattr(vision_service, "gemini_key", "test-key")
    monkeypatch.setattr(vision_service, "openrouter_key", "test-key")
    monkeypatch.setattr(vision_service, "dashscope_key", "")
    monkeypatch.setattr(vision_service, "_analyze_with_gemini", hang)
    monkeypatch.setattr(vision_service, "_analyze_with_qwen_openrouter", works)
    monkeypatch.setattr(
        "fastapi_app.services.clipseg_service.segment_image",
        lambda *a, **k: {"available": False, "classes": [], "overlay_base64": None},
    )

    with env(AQUAMIND_DEMO_MODE="false", AQUAMIND_VISION_TIMEOUT_SEC="0.5"):
        started = time.monotonic()
        result = asyncio.run(vision_service.analyze_reservoir_image(b"bytes", "demo.jpg"))
        elapsed = time.monotonic() - started

    assert result["provider"] == "Qwen2.5-VL (OpenRouter)"
    assert elapsed < 10, "the timed-out provider blocked the next one"


def test_clipseg_failure_does_not_invalidate_the_vlm_analysis(monkeypatch):
    from fastapi_app.services.vision_service import vision_service

    async def works(*args, **kwargs):
        return {
            "reservoir_health": 61,
            "overall_risk": "Moderate",
            "water_spread": "Moderate",
            "summary": "A partially drawn-down reservoir.",
            "recommendations": ["Survey the exposed bank."],
        }

    def explode(*args, **kwargs):
        raise RuntimeError("CLIPSeg weights unavailable")

    monkeypatch.setattr(vision_service, "_refresh_keys", lambda: None)
    monkeypatch.setattr(vision_service, "gemini_key", "test-key")
    monkeypatch.setattr(vision_service, "openrouter_key", "")
    monkeypatch.setattr(vision_service, "dashscope_key", "")
    monkeypatch.setattr(vision_service, "_analyze_with_gemini", works)
    monkeypatch.setattr("fastapi_app.services.clipseg_service.segment_image", explode)

    with env(AQUAMIND_DEMO_MODE="false"):
        result = asyncio.run(vision_service.analyze_reservoir_image(b"bytes", "demo.jpg"))

    assert result["reservoir_health"] == 61
    assert result["analysis_mode"] == "vlm", "a failed overlay downgraded a successful analysis"
    assert result["segmentation"]["available"] is False
    assert "CLIPSeg" in result["segmentation"]["error"]
    assert result["metadata"]["source"] == "vision_provider"
    assert result["metadata"]["method"] == "vision_model"


def test_clipseg_overlay_timeout_still_returns_the_analysis(monkeypatch):
    from fastapi_app.services.vision_service import vision_service

    async def works(*args, **kwargs):
        return {"reservoir_health": 55, "overall_risk": "Moderate", "water_spread": "Moderate"}

    def slow(*args, **kwargs):
        time.sleep(5)
        return {"available": True, "classes": []}

    monkeypatch.setattr(vision_service, "_refresh_keys", lambda: None)
    monkeypatch.setattr(vision_service, "gemini_key", "test-key")
    monkeypatch.setattr(vision_service, "openrouter_key", "")
    monkeypatch.setattr(vision_service, "dashscope_key", "")
    monkeypatch.setattr(vision_service, "_analyze_with_gemini", works)
    monkeypatch.setattr("fastapi_app.services.clipseg_service.segment_image", slow)

    with env(AQUAMIND_DEMO_MODE="false", AQUAMIND_CLIPSEG_TIMEOUT_SEC="0.3"):
        result = asyncio.run(vision_service.analyze_reservoir_image(b"bytes", "demo.jpg"))

    assert result["reservoir_health"] == 55
    assert result["segmentation"]["available"] is False


def test_vision_route_labels_a_fixture_response_honestly(auth_client, monkeypatch):
    from fastapi_app.tests.conftest import TINY_PNG

    _failing_vision_service(monkeypatch)
    payload = {"file": ("demo.png", TINY_PNG, "image/png")}

    with env(AQUAMIND_DEMO_MODE="true"):
        response = auth_client.post("/api/vision/analyze", files=payload, data={"mode": "reservoir"})

    assert response.status_code == 200
    body = response.json()
    assert body["analysis_mode"] == "demo_fixture"
    assert "reference analysis" in body["message"].lower()
    assert "no vision provider" in body["message"].lower()
    assert body["metadata"]["source"] == SOURCE_DEMO_FIXTURE


def test_vision_route_reports_unavailability_as_503(auth_client, monkeypatch):
    from fastapi_app.tests.conftest import TINY_PNG

    _failing_vision_service(monkeypatch)
    payload = {"file": ("demo.png", TINY_PNG, "image/png")}

    with env(AQUAMIND_DEMO_MODE="false"):
        response = auth_client.post("/api/vision/analyze", files=payload, data={"mode": "reservoir"})

    assert response.status_code == 503
    body = response.json()
    assert body["success"] is False
    assert "temporarily unavailable" in body["message"].lower() or "vision" in body["message"].lower()


# ---------------------------------------------------------------------------
# 5b. Acoustic leak fixture (optional demo path)
# ---------------------------------------------------------------------------


def test_leak_fixture_is_served_only_in_demo_mode(monkeypatch):
    from fastapi_app.core.ai_fallback import leak_fixture_result
    from fastapi_app.services.model_service import model_service

    monkeypatch.setattr(model_service, "leak_model", None)

    with env(AQUAMIND_DEMO_MODE="false"):
        with pytest.raises(RuntimeError, match="unavailable"):
            model_service.detect_leak_signal([0.1, 0.2, 0.3])

    with env(AQUAMIND_DEMO_MODE="true"):
        result = model_service.detect_leak_signal([0.1, 0.2, 0.3])
    assert result["source"] == SOURCE_DEMO_FIXTURE
    assert result["is_leak_detected"] is True
    assert result["estimated_water_loss_lpm"] >= 0
    assert result["metadata"]["source"] == SOURCE_DEMO_FIXTURE


def test_leak_fixture_matches_classifier_contract():
    from fastapi_app.core.ai_fallback import leak_fixture_result

    with env(AQUAMIND_DEMO_MODE="true"):
        result = leak_fixture_result()
    for field in FIXTURE_REQUIRED_FIELDS["leak_detection"]:
        assert field in result
    assert result["metadata"]["is_stale"] is True


# ---------------------------------------------------------------------------
# 6. Startup must not touch CLIPSeg
# ---------------------------------------------------------------------------


def test_startup_never_loads_clipseg_weights(api_client):
    """The app has already started via the TestClient fixture."""
    from fastapi_app import main
    from fastapi_app.services import clipseg_service

    assert clipseg_service._MODEL is None
    assert clipseg_service._PROCESSOR is None
    assert "clipseg" not in inspect.getsource(main.lifespan).lower()


# ---------------------------------------------------------------------------
# 7. Readiness reporting
# ---------------------------------------------------------------------------


def test_ready_endpoint_reports_dependencies_without_leaking_secrets(auth_client):
    with env(AQUAMIND_DEMO_MODE="false"):
        response = auth_client.get("/readiness")
    assert response.status_code == 200
    body = response.json()

    assert set(body["checks"]) >= {
        "database",
        "model_artifacts",
        "weather_provider",
        "vision_provider",
        "clipseg",
        "demo_mode",
    }
    assert body["checks"]["vision_provider"]["status"] in ("configured", "unavailable", "fallback")
    assert body["checks"]["clipseg"]["status"] in ("loaded", "available", "not_loaded", "unavailable")
    assert body["checks"]["demo_mode"]["enabled"] is False
    assert body["status"] in ("ready", "degraded", "not_ready")

    serialized = json.dumps(body)
    for secret in (os.getenv("GEMINI_API_KEY"), os.getenv("JWT_SECRET_KEY")):
        if secret and len(secret) > 8:
            assert secret not in serialized


def test_ready_endpoint_surfaces_demo_mode(auth_client):
    with env(AQUAMIND_DEMO_MODE="true", AQUAMIND_DEMO_FORCE_FIXTURES="true"):
        body = auth_client.get("/readiness").json()
    assert body["checks"]["demo_mode"]["enabled"] is True
    assert body["checks"]["demo_mode"]["force_fixtures"] is True


def test_readiness_probe_does_not_trigger_a_clipseg_download(auth_client):
    from fastapi_app.services import clipseg_service

    auth_client.get("/readiness")
    assert clipseg_service._MODEL is None, "the readiness probe loaded CLIPSeg weights"
