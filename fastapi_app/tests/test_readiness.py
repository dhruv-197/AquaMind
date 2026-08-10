"""Technical readiness endpoint: semantics, auth, and no-secret contract."""
from __future__ import annotations

import json
import os
from contextlib import contextmanager
from typing import Any

import pytest

from fastapi_app.core.config import get_settings
from fastapi_app.services import readiness_service


@contextmanager
def env(**overrides: str | None):
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


def _assert_no_secrets(payload: Any) -> None:
    serialized = json.dumps(payload)
    forbidden_fragments = [
        "sk-",
        "Bearer ",
        "BEGIN PRIVATE",
        "sqlite:///",
        "postgresql://",
        str(readiness_service._AI_DIR),
    ]
    for fragment in forbidden_fragments:
        assert fragment not in serialized, f"secret-like fragment leaked: {fragment!r}"

    for secret_name in ("GEMINI_API_KEY", "JWT_SECRET_KEY", "OPENROUTER_API_KEY", "DASHSCOPE_API_KEY"):
        secret = os.getenv(secret_name)
        if secret and len(secret) > 8:
            assert secret not in serialized


def test_readiness_requires_authentication(api_client):
    response = api_client.get("/readiness")
    assert response.status_code in (401, 403)


def test_health_remains_public_and_lightweight(api_client):
    response = api_client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert "checks" not in body
    assert "model_artifacts" not in body


def test_successful_readiness_response_shape(auth_client):
    response = auth_client.get("/readiness")
    assert response.status_code == 200
    body = response.json()

    assert body["status"] in ("ready", "degraded", "not_ready")
    assert body["environment"]
    assert body["timestamp"]
    checks = body["checks"]
    assert checks["database"]["status"] in ("ready", "failed")
    assert "latency_ms" in checks["database"]
    assert checks["model_artifacts"]["status"] in ("ready", "partial", "failed")
    assert set(checks["model_artifacts"]["models"]) == set(readiness_service.REQUIRED_MODELS)
    for model in checks["model_artifacts"]["models"].values():
        assert "available" in model
        assert "loaded" in model
        assert "model_version" in model
    assert checks["weather_provider"]["status"] in ("configured", "fallback", "unavailable")
    assert checks["vision_provider"]["status"] in ("configured", "fallback", "unavailable")
    assert set(checks["vision_provider"]["providers"]) == {"gemini", "openrouter", "dashscope"}
    assert checks["clipseg"]["status"] in ("loaded", "available", "not_loaded", "unavailable")
    assert "enabled" in checks["demo_mode"]
    _assert_no_secrets(body)


def test_ready_alias_matches_readiness(auth_client):
    a = auth_client.get("/readiness").json()
    b = auth_client.get("/ready").json()
    assert a["status"] == b["status"]
    assert set(a["checks"]) == set(b["checks"])


def test_database_failure_marks_not_ready(monkeypatch):
    monkeypatch.setattr(
        readiness_service,
        "database_status",
        lambda: {"status": "failed", "latency_ms": 1.2},
    )
    monkeypatch.setattr(
        readiness_service,
        "model_artifacts_status",
        lambda: {
            "status": "ready",
            "models": {
                key: {"available": True, "loaded": True, "model_version": "v"}
                for key in readiness_service.REQUIRED_MODELS
            },
        },
    )
    body = readiness_service.build_readiness()
    assert body["status"] == "not_ready"
    assert body["checks"]["database"]["status"] == "failed"
    _assert_no_secrets(body)


def test_missing_required_models_marks_not_ready(monkeypatch):
    monkeypatch.setattr(
        readiness_service,
        "database_status",
        lambda: {"status": "ready", "latency_ms": 0.5},
    )
    monkeypatch.setattr(
        readiness_service,
        "model_artifacts_status",
        lambda: {
            "status": "failed",
            "models": {
                key: {
                    "available": False,
                    "loaded": False,
                    "model_version": None,
                    "error_category": "missing_artifact",
                }
                for key in readiness_service.REQUIRED_MODELS
            },
        },
    )
    body = readiness_service.build_readiness()
    assert body["status"] == "not_ready"


def test_partial_models_mark_degraded(monkeypatch):
    monkeypatch.setattr(
        readiness_service,
        "database_status",
        lambda: {"status": "ready", "latency_ms": 0.4},
    )
    models = {
        key: {"available": True, "loaded": True, "model_version": "v"}
        for key in readiness_service.REQUIRED_MODELS
    }
    models["leak_detection"] = {
        "available": False,
        "loaded": False,
        "model_version": None,
        "error_category": "missing_artifact",
    }
    monkeypatch.setattr(
        readiness_service,
        "model_artifacts_status",
        lambda: {"status": "partial", "models": models},
    )
    body = readiness_service.build_readiness()
    assert body["status"] == "degraded"


def test_missing_optional_provider_keys_do_not_force_not_ready(monkeypatch):
    monkeypatch.setattr(
        readiness_service,
        "database_status",
        lambda: {"status": "ready", "latency_ms": 0.3},
    )
    monkeypatch.setattr(
        readiness_service,
        "model_artifacts_status",
        lambda: {
            "status": "ready",
            "models": {
                key: {"available": True, "loaded": True, "model_version": "v"}
                for key in readiness_service.REQUIRED_MODELS
            },
        },
    )
    monkeypatch.setattr(
        readiness_service,
        "vision_provider_status",
        lambda: {
            "status": "unavailable",
            "providers": {
                "gemini": "unavailable",
                "openrouter": "unavailable",
                "dashscope": "unavailable",
            },
        },
    )
    monkeypatch.setattr(
        readiness_service,
        "weather_provider_status",
        lambda: {"status": "fallback", "provider": "defaults"},
    )
    monkeypatch.setattr(
        readiness_service,
        "clipseg_status",
        lambda: {"status": "unavailable", "dependencies_installed": False},
    )

    with env(GEMINI_API_KEY=None, OPENROUTER_API_KEY=None, DASHSCOPE_API_KEY=None, QWEN_API_KEY=None):
        body = readiness_service.build_readiness()

    # Optional gaps degrade the overall status but must never force not_ready.
    assert body["status"] == "degraded"
    assert body["checks"]["vision_provider"]["status"] == "unavailable"
    _assert_no_secrets(body)


def test_fully_configured_stack_is_ready(monkeypatch):
    monkeypatch.setattr(
        readiness_service,
        "database_status",
        lambda: {"status": "ready", "latency_ms": 0.2},
    )
    monkeypatch.setattr(
        readiness_service,
        "model_artifacts_status",
        lambda: {
            "status": "ready",
            "models": {
                key: {"available": True, "loaded": True, "model_version": "v"}
                for key in readiness_service.REQUIRED_MODELS
            },
        },
    )
    monkeypatch.setattr(
        readiness_service,
        "vision_provider_status",
        lambda: {
            "status": "configured",
            "providers": {
                "gemini": "configured",
                "openrouter": "configured",
                "dashscope": "unavailable",
            },
        },
    )
    monkeypatch.setattr(
        readiness_service,
        "weather_provider_status",
        lambda: {"status": "configured", "provider": "open-meteo"},
    )
    monkeypatch.setattr(
        readiness_service,
        "clipseg_status",
        lambda: {"status": "not_loaded", "dependencies_installed": True},
    )
    body = readiness_service.build_readiness()
    assert body["status"] == "ready"
    _assert_no_secrets(body)


def test_vision_provider_reports_configuration_only(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-not-a-real-secret-value")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.delenv("QWEN_API_KEY", raising=False)
    get_settings.cache_clear()

    status = readiness_service.vision_provider_status()
    assert status["status"] == "configured"
    assert status["providers"]["gemini"] == "configured"
    assert status["providers"]["openrouter"] == "unavailable"
    assert "test-not-a-real-secret-value" not in json.dumps(status)


def test_clipseg_status_does_not_load_weights():
    from fastapi_app.services import clipseg_service

    before = clipseg_service._MODEL
    status = readiness_service.clipseg_status()
    assert status["status"] in ("loaded", "available", "not_loaded", "unavailable")
    assert clipseg_service._MODEL is before
