"""Model evaluation credibility: splits, baselines, metadata, status cards."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from ai.evaluation import (
    assert_no_future_leakage,
    chronological_date_split,
    chronological_year_split,
    majority_class_baseline_from_cm,
    mean_baseline_r2,
    strip_filesystem_paths,
)
from fastapi_app.services.model_card_service import (
    MODEL_CARD_FILES,
    build_model_status,
    public_model_card,
)

AI_DIR = Path(__file__).resolve().parents[2] / "ai"
REQUIRED_META_KEYS = {
    "features",
    "target",
    "metrics",
    "limitations",
}


def test_chronological_date_split_has_no_future_leakage():
    frame = pd.DataFrame(
        {
            "Date": pd.to_datetime(
                ["2024-03-01", "2024-03-02", "2024-03-03", "2024-03-04", "2024-03-05", "2024-03-06"]
                * 2
            ),
            "y": range(12),
        }
    )
    train, val, test = chronological_date_split(frame, date_col="Date", train_frac=0.5, val_frac=0.25)
    assert_no_future_leakage(train, val, test, time_col="Date")
    assert train["Date"].max() < val["Date"].min()
    assert val["Date"].max() < test["Date"].min()


def test_chronological_year_split_orders_partitions():
    frame = pd.DataFrame({"Year": [2018, 2019, 2020, 2021, 2023, 2024], "y": range(6)})
    train, val, test = chronological_year_split(frame)
    assert set(train["Year"]) <= {2018, 2019}
    assert set(val["Year"]) <= {2020, 2021, 2022}
    assert set(test["Year"]) <= {2023, 2024}
    assert train["Year"].max() < val["Year"].min()
    assert val["Year"].max() < test["Year"].min()


def test_assert_no_future_leakage_raises_on_overlap():
    train = pd.DataFrame({"t": pd.to_datetime(["2020-01-01", "2020-06-01"])})
    val = pd.DataFrame({"t": pd.to_datetime(["2020-03-01"])})
    test = pd.DataFrame({"t": pd.to_datetime(["2021-01-01"])})
    with pytest.raises(AssertionError, match="leakage"):
        assert_no_future_leakage(train, val, test, time_col="t")


def test_majority_baseline_from_leak_test_confusion_matrix():
    # Counts from committed leak metadata test CM [[2,22],[3,69]]
    baseline = majority_class_baseline_from_cm([[2, 22], [3, 69]])
    assert baseline["method"].startswith("always_predict_positive")
    assert baseline["accuracy"] == 0.75
    assert baseline["f1"] == 0.8571
    assert baseline["rows"] == 96


def test_mean_baseline_r2_is_zero_by_definition():
    assert mean_baseline_r2()["r2"] == 0.0


def test_strip_filesystem_paths_removes_user_dirs():
    dirty = {
        "source": r"C:\Users\alice\eaquamind-ai\Aqua Dataset\file.csv",
        "artifact_uri": r"D:\eaquamind-ai\ai\model.pkl",
        "metrics": {"test": {"mae": 1.0}},
    }
    clean = strip_filesystem_paths(dirty)
    assert "Users" not in json.dumps(clean)
    assert "artifact_uri" not in clean
    assert clean["source"].startswith("Aqua Dataset/")
    assert clean["metrics"]["test"]["mae"] == 1.0


def test_all_model_cards_have_required_fields_and_baselines():
    for model_id, path in MODEL_CARD_FILES.items():
        assert path.is_file(), model_id
        meta = json.loads(path.read_text(encoding="utf-8"))
        for key in REQUIRED_META_KEYS:
            assert key in meta or (key == "limitations" and "notes" in meta), f"{model_id} missing {key}"
        assert "features" in meta and isinstance(meta["features"], list) and meta["features"]
        assert "metrics" in meta and ("test" in meta["metrics"] or "validation" in meta["metrics"])
        if model_id == "water_shortage":
            assert meta["baseline_comparison"]["model_beats_persistence_baseline"] is False
            assert meta["baseline_comparison"]["seasonal_naive"]["status"] == "unsupported_insufficient_history"
        if model_id == "water_demand":
            assert meta.get("evaluation_scope") == "synthetic_label_validation"
            assert "synthetic" in json.dumps(meta).lower()
            assert meta["baseline_comparison"]["mean_baseline"]["r2"] == 0.0
        if model_id == "leak_detection":
            assert "confusion_matrix" in meta["metrics"]["test"]
            assert meta["field_validation_status"] == "lab_trained_not_field_validated"
            maj = meta["baseline_comparison"]["majority_class_baseline"]
            assert maj["f1"] == 0.8571


def test_model_status_endpoint_shape_and_no_paths(auth_client):
    for model_id in ("water_shortage", "groundwater", "water_demand", "leak_detection"):
        response = auth_client.get(f"/api/v1/models/{model_id}/status")
        assert response.status_code == 200, model_id
        body = response.json()
        data = body["data"]
        for key in (
            "loaded",
            "artifact_available",
            "model_version",
            "feature_count",
            "validation_metrics",
            "test_metrics",
            "baseline_metrics",
            "known_limitations",
        ):
            assert key in data, key
        serialized = json.dumps(data)
        assert "C:\\Users" not in serialized
        assert "/Users/" not in serialized
        assert "artifact_uri" not in serialized


def test_model_performance_is_sanitized(auth_client):
    response = auth_client.get("/model-performance/demand")
    assert response.status_code == 200
    text = response.text
    assert "C:\\Users" not in text
    model = response.json()["model"]
    assert model.get("evaluation_scope") == "synthetic_label_validation"
    assert "status" in model


def test_public_model_card_includes_status_block():
    card = public_model_card("water_shortage")
    assert card["status"]["feature_count"] == 4
    assert card["status"]["baseline_metrics"]["model_beats_persistence_baseline"] is False


def test_shortage_prediction_includes_technical_note(auth_client):
    response = auth_client.post(
        "/predict-shortage",
        json={
            "reservoir_capacity_pct": 40,
            "rainfall_deficit_pct": -10,
            "temperature_c": 32,
            "daily_demand_mgd": 80,
            "day_of_month": 15,
        },
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data.get("technical_accuracy_note")
    assert "baseline" in data["technical_accuracy_note"].lower() or "persistence" in data[
        "technical_accuracy_note"
    ].lower() or "not beat" in data["technical_accuracy_note"].lower()
    assert data.get("evaluation", {}).get("trained_horizon") == "one_day"
    assert data.get("evaluation", {}).get("multi_day_method") == "extrapolated_heuristic"


def test_build_model_status_demand_marks_synthetic():
    status = build_model_status("water_demand")
    joined = " ".join(status["known_limitations"]).lower()
    assert "synthetic" in joined
    assert status["feature_count"] == 8
