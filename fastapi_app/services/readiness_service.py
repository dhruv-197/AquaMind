"""Non-sensitive readiness snapshot for operators and pre-demo checks.

Reports whether each dependency is usable, never why in a way that leaks a
secret: API keys are reduced to a configured/absent boolean and are never echoed
back in any form. Probing is deliberately cheap and side-effect free - in
particular, asking about CLIPSeg must not trigger a model download, and no
remote weather or AI call is made from this module.
"""
from __future__ import annotations

import importlib.util
import time
from pathlib import Path
from typing import Any

from fastapi_app.core.config import get_settings
from fastapi_app.core.data_quality import isoformat, resolve_model_version, utc_now

_AI_DIR = Path(__file__).resolve().parents[2] / "ai"

#: Required sklearn artifacts for a "ready" local prediction stack.
REQUIRED_MODELS: dict[str, str] = {
    "water_shortage": "water_shortage_model",
    "groundwater": "groundwater_model",
    "water_demand": "water_demand_model",
    "leak_detection": "leak_detection_model",
}

_PLACEHOLDER_KEYS = frozenset(
    {
        "",
        "MY_GEMINI_API_KEY",
        "replace-with-a-long-random-secret",
        "your-api-key",
        "changeme",
    }
)


def _configured(*env_names: str) -> bool:
    import os

    for name in env_names:
        raw = (os.getenv(name) or "").strip().strip('"').strip("'")
        if raw and raw not in _PLACEHOLDER_KEYS:
            return True
    return False


def _error_category(exc: BaseException | None = None, *, missing_artifact: bool = False) -> str:
    if missing_artifact:
        return "missing_artifact"
    if exc is None:
        return "unavailable"
    name = type(exc).__name__
    if "Import" in name or "Module" in name:
        return "import_error"
    return "load_error"


def database_status() -> dict[str, Any]:
    """Lightweight connectivity probe. Never returns connection strings or traces."""
    started = time.perf_counter()
    try:
        from sqlalchemy import text

        from fastapi_app.database.connection import engine

        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        latency_ms = round((time.perf_counter() - started) * 1000.0, 2)
        return {"status": "ready", "latency_ms": latency_ms}
    except Exception:
        latency_ms = round((time.perf_counter() - started) * 1000.0, 2)
        return {"status": "failed", "latency_ms": latency_ms}


def _artifact_on_disk(stem: str) -> bool:
    return (_AI_DIR / f"{stem}.pkl").is_file() or (_AI_DIR / f"{stem}.metadata.json").is_file()


def model_artifacts_status() -> dict[str, Any]:
    """Per-model availability without exposing filesystem paths."""
    models: dict[str, dict[str, Any]] = {}
    try:
        from fastapi_app.services.model_service import model_service

        loaded_map = {
            "water_shortage": model_service.shortage_model is not None,
            "groundwater": model_service.groundwater_model is not None,
            "water_demand": model_service.demand_model is not None,
            "leak_detection": model_service.leak_model is not None,
        }
    except Exception as exc:
        for key, stem in REQUIRED_MODELS.items():
            on_disk = _artifact_on_disk(stem)
            models[key] = {
                "available": on_disk,
                "loaded": False,
                "model_version": resolve_model_version(stem) if on_disk else None,
                "error_category": _error_category(exc, missing_artifact=not on_disk),
            }
        return {"status": "failed", "models": models}

    for key, stem in REQUIRED_MODELS.items():
        loaded = bool(loaded_map.get(key))
        on_disk = _artifact_on_disk(stem)
        available = loaded or on_disk
        entry: dict[str, Any] = {
            "available": available,
            "loaded": loaded,
            "model_version": resolve_model_version(stem) if available else None,
        }
        if not available:
            entry["error_category"] = _error_category(missing_artifact=True)
        elif not loaded:
            # Artifact exists on disk but the singleton did not load it.
            entry["error_category"] = "not_loaded"
        models[key] = entry

    loaded_count = sum(1 for m in models.values() if m["loaded"])
    available_count = sum(1 for m in models.values() if m["available"])
    expected = len(REQUIRED_MODELS)

    if loaded_count == expected:
        status = "ready"
    elif available_count == 0:
        status = "failed"
    else:
        status = "partial"

    return {"status": status, "models": models}


def weather_provider_status() -> dict[str, Any]:
    """Open-Meteo needs no key; report whether the local climate module imports."""
    try:
        if importlib.util.find_spec("climate") is None:
            return {"status": "fallback", "provider": "defaults"}
        # Import the package root only - never call a remote weather endpoint here.
        import climate  # noqa: F401

        return {"status": "configured", "provider": "open-meteo"}
    except Exception:
        return {"status": "fallback", "provider": "defaults"}


def vision_provider_status() -> dict[str, Any]:
    """Configuration-only check for AquaLens providers. No remote calls."""
    providers = {
        "gemini": "configured" if _configured("GEMINI_API_KEY") else "unavailable",
        "openrouter": "configured" if _configured("OPENROUTER_API_KEY") else "unavailable",
        "dashscope": (
            "configured"
            if _configured("DASHSCOPE_API_KEY", "QWEN_API_KEY")
            else "unavailable"
        ),
    }
    configured = sum(1 for status in providers.values() if status == "configured")
    if configured:
        status = "configured"
    else:
        status = "unavailable"
    return {"status": status, "providers": providers}


def clipseg_status() -> dict[str, Any]:
    """Report CLIPSeg state without importing torch or fetching weights."""
    from fastapi_app.services import clipseg_service

    deps_present = bool(
        importlib.util.find_spec("torch") and importlib.util.find_spec("transformers")
    )
    if getattr(clipseg_service, "_MODEL", None) is not None:
        status = "loaded"
    elif getattr(clipseg_service, "_LOAD_ERROR", None):
        status = "unavailable"
    elif deps_present:
        status = "not_loaded"
    else:
        status = "unavailable"
    return {
        "status": status,
        "dependencies_installed": deps_present,
        "note": "Weights load lazily on the first AquaLens upload, never at startup.",
    }


def _overall_status(database: dict[str, Any], models: dict[str, Any]) -> str:
    """Apply the ready / degraded / not_ready contract."""
    if database.get("status") != "ready":
        return "not_ready"
    model_status = models.get("status")
    if model_status == "failed":
        return "not_ready"
    if model_status == "ready":
        return "ready"
    # partial models, or ready models with optional provider gaps handled by caller
    return "degraded"


def build_readiness() -> dict[str, Any]:
    settings = get_settings()
    database = database_status()
    models = model_artifacts_status()
    weather = weather_provider_status()
    vision = vision_provider_status()
    clipseg = clipseg_status()

    status = _overall_status(database, models)
    # Optional-provider gaps never flip the system to not_ready, but they do
    # mark an otherwise ready core as degraded so operators see the gap.
    if status == "ready" and (
        weather.get("status") in {"unavailable", "fallback"}
        or vision.get("status") == "unavailable"
        or clipseg.get("status") == "unavailable"
    ):
        status = "degraded"

    return {
        "status": status,
        "environment": settings.environment,
        "timestamp": isoformat(utc_now()),
        "checks": {
            "database": database,
            "model_artifacts": models,
            "weather_provider": weather,
            "vision_provider": vision,
            "clipseg": clipseg,
            "demo_mode": {
                "enabled": bool(settings.demo_mode),
                "force_fixtures": bool(settings.fixtures_forced),
            },
        },
    }
