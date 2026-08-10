"""Sanitize and present model-card status without filesystem paths or secrets."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ai.evaluation import majority_class_baseline_from_cm, strip_filesystem_paths
from fastapi_app.core.data_quality import resolve_model_version

_AI_DIR = Path(__file__).resolve().parents[2] / "ai"

MODEL_CARD_FILES: dict[str, Path] = {
    "water_shortage": _AI_DIR / "water_shortage_model.metadata.json",
    "groundwater": _AI_DIR / "groundwater_model.metadata.json",
    "water_demand": _AI_DIR / "water_demand_model.metadata.json",
    "leak_detection": _AI_DIR / "leak_detection_model.metadata.json",
}

# Map public /model-performance/* aliases onto card ids.
PERFORMANCE_ALIASES: dict[str, str] = {
    "reservoir": "water_shortage",
    "shortage": "water_shortage",
    "groundwater": "groundwater",
    "demand": "water_demand",
    "leak": "leak_detection",
}


def load_raw_metadata(model_id: str) -> dict[str, Any] | None:
    path = MODEL_CARD_FILES.get(model_id)
    if path is None or not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _feature_count(meta: dict[str, Any]) -> int:
    feats = meta.get("features")
    return len(feats) if isinstance(feats, list) else 0


def _loaded_flag(model_id: str) -> bool:
    try:
        from fastapi_app.services.model_service import model_service

        mapping = {
            "water_shortage": model_service.shortage_model,
            "groundwater": model_service.groundwater_model,
            "water_demand": model_service.demand_model,
            "leak_detection": model_service.leak_model,
        }
        return mapping.get(model_id) is not None
    except Exception:
        return False


def _stem_for_version(model_id: str) -> str:
    return {
        "water_shortage": "water_shortage_model",
        "groundwater": "groundwater_model",
        "water_demand": "water_demand_model",
        "leak_detection": "leak_detection_model",
    }[model_id]


def build_model_status(model_id: str) -> dict[str, Any]:
    """Consistent, path-free status card for dashboard / technical review."""
    from fastapi_app.core.ttl_cache import (
        MODEL_STATUS_TTL_SEC,
        model_status_cache,
        set_cache_status,
    )

    cache_key = f"model_status:{model_id}"
    cached = model_status_cache.get(cache_key)
    if cached is not None:
        set_cache_status("HIT")
        return cached

    raw = load_raw_metadata(model_id)
    if raw is None:
        result = {
            "model_id": model_id,
            "loaded": False,
            "artifact_available": False,
            "model_version": None,
            "feature_count": 0,
            "last_training_date": None,
            "validation_metrics": {},
            "test_metrics": {},
            "baseline_metrics": {},
            "known_limitations": [],
            "message": "Model metadata unavailable. Retrain with `py ai/train.py`.",
        }
        model_status_cache.set(cache_key, result, MODEL_STATUS_TTL_SEC)
        set_cache_status("MISS")
        return result

    safe = strip_filesystem_paths(raw)
    metrics = safe.get("metrics") or {}
    baseline = safe.get("baseline_comparison") or {}

    # Ensure leak majority baseline is present when CM exists (derived, not invented).
    if model_id == "leak_detection" and "majority_class_baseline" not in baseline:
        test_cm = (metrics.get("test") or {}).get("confusion_matrix")
        if test_cm:
            try:
                baseline = {
                    **baseline,
                    "majority_class_baseline": majority_class_baseline_from_cm(test_cm),
                    "model_beats_majority_f1": (
                        float((metrics.get("test") or {}).get("f1") or 0)
                        > float(majority_class_baseline_from_cm(test_cm)["f1"])
                    ),
                }
            except Exception:
                pass

    result = {
        "model_id": model_id,
        "model_name": safe.get("model_name") or model_id,
        "loaded": _loaded_flag(model_id),
        "artifact_available": True,
        "model_version": resolve_model_version(_stem_for_version(model_id)),
        "algorithm": safe.get("algorithm") or safe.get("model_type"),
        "feature_count": _feature_count(safe),
        "features": safe.get("features") if isinstance(safe.get("features"), list) else [],
        "target": safe.get("target"),
        "target_unit": safe.get("target_unit"),
        "last_training_date": safe.get("trained_at") or safe.get("training_date"),
        "random_seed": safe.get("random_seed") or safe.get("split_seed"),
        "split_strategy": safe.get("split_strategy") or safe.get("temporal_split") or safe.get("split_method"),
        "evaluation_period": safe.get("evaluation_period") or safe.get("source_coverage"),
        "training_dataset": safe.get("training_dataset")
        or safe.get("training_data")
        or safe.get("source"),
        "validation_metrics": metrics.get("validation") or {},
        "test_metrics": metrics.get("test") or {},
        "baseline_metrics": baseline,
        "known_limitations": safe.get("limitations") or safe.get("notes") or [],
        "field_validation_status": safe.get("field_validation_status"),
        "evaluation_scope": safe.get("evaluation_scope"),
        "message": "Ready" if _loaded_flag(model_id) else "Artifact present; model singleton not loaded",
    }
    model_status_cache.set(cache_key, result, MODEL_STATUS_TTL_SEC)
    set_cache_status("MISS")
    return result


def public_model_card(model_id: str) -> dict[str, Any]:
    """Full sanitized card for /model-performance/* (backward compatible wrapper)."""
    raw = load_raw_metadata(model_id)
    if raw is None:
        return {}
    safe = strip_filesystem_paths(raw)
    status = build_model_status(model_id)
    # Keep original keys for clients that already read metrics/limitations,
    # while attaching a consistent `status` block.
    return {**safe, "status": status}
