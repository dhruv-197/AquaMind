"""Unit tests for Reservoir Level Forecast production model."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from fastapi_app.core.contracts import RiskLevel
from fastapi_app.decision_engine.rules import recommendation_from_prediction
from fastapi_app.prediction.framework.datasets.base import PredictionDataset, TrainingDataset
from fastapi_app.prediction.framework.registry.model_registry import ModelRegistry
from fastapi_app.prediction.framework.schemas.config import TrainingConfiguration
from fastapi_app.prediction.framework.schemas.output import UniversalPredictionOutput
from fastapi_app.prediction.models.reservoir.constants import MODEL_KEY
from fastapi_app.prediction.models.reservoir.dataset import (
    ReservoirDatasetLoader,
    ReservoirDatasetValidationError,
    generate_sample_dataset,
)
from fastapi_app.prediction.models.reservoir.factory import build_reservoir_forecast_model
from fastapi_app.prediction.models.reservoir.model import ReservoirLevelForecastModel
from fastapi_app.prediction.models.reservoir.persistence import JoblibModelPersistence
from fastapi_app.prediction.models.reservoir.recommendations import recommendations_bundle
from fastapi_app.prediction.models.reservoir.regressor import XGBoostReservoirRegressor
from fastapi_app.prediction.models.reservoir.risk import reservoir_risk_level
from fastapi_app.prediction.models.reservoir.service import ReservoirLevelForecastService


@pytest.fixture(scope="module")
def sample_csv(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("reservoir_data")
    path = root / "sample_reservoir.csv"
    generate_sample_dataset(path, days=400, seed=11)
    return path


@pytest.fixture
def artifacts_dir(tmp_path) -> Path:
    d = tmp_path / "artifacts"
    d.mkdir()
    return d


def test_dataset_loading_csv(sample_csv: Path):
    loader = ReservoirDatasetLoader()
    frame = loader.load_csv(sample_csv)
    assert "date" in frame.columns
    assert "storage_pct" in frame.columns
    assert "reservoir_id" in frame.columns
    assert len(frame) > 100
    catalog = ReservoirDatasetLoader.catalog_from_frame(frame)
    assert len(catalog) >= 3


def test_dataset_loading_dataframe_and_duplicates():
    loader = ReservoirDatasetLoader()
    frame = pd.DataFrame(
        {
            "date": ["2024-01-01", "2024-01-01", "2024-01-02"],
            "storage_pct": [55.0, 56.0, 54.0],
            "reservoir_id": ["RES-A", "RES-A", "RES-A"],
            "rainfall_mm": [1.0, 2.0, 0.5],
        }
    )
    cleaned = loader.load_dataframe(frame)
    assert len(cleaned) == 2


def test_dataset_rejects_bad_timestamps():
    loader = ReservoirDatasetLoader()
    with pytest.raises(ReservoirDatasetValidationError):
        loader.load_dataframe(
            pd.DataFrame({"date": ["not-a-date"], "storage_pct": [10.0]})
        )


def test_dataset_missing_required_column():
    loader = ReservoirDatasetLoader()
    with pytest.raises(ReservoirDatasetValidationError):
        loader.load_dataframe(pd.DataFrame({"date": ["2024-01-01"], "value": [1.0]}))


def test_risk_rules():
    assert reservoir_risk_level(15) == RiskLevel.CRITICAL
    assert reservoir_risk_level(30) == RiskLevel.HIGH
    assert reservoir_risk_level(50) == RiskLevel.MODERATE
    assert reservoir_risk_level(70) == RiskLevel.LOW


def test_training_prediction_and_serialization(sample_csv: Path, artifacts_dir: Path):
    pytest.importorskip("xgboost")
    model = ReservoirLevelForecastModel(
        regressor=XGBoostReservoirRegressor(n_estimators=40, max_depth=4, random_state=0),
        persistence=JoblibModelPersistence(base_dir=artifacts_dir),
        model_version="test-1.0.0",
    )
    assert model.is_trained() is False

    loader = ReservoirDatasetLoader()
    frame = loader.load_csv(sample_csv)
    dataset = TrainingDataset(
        frame,
        feature_columns=[],
        target_column="storage_pct",
        name="test",
        source=str(sample_csv),
    )
    config = TrainingConfiguration(
        model_name=MODEL_KEY,
        model_version="test-1.0.0",
        validation_split=0.2,
        random_seed=0,
        forecast_horizon=7,
    )
    result = model.train(dataset, config)
    assert model.is_trained() is True
    assert "mae" in (result.get("metrics") or {})
    assert len(model._catalog) >= 3

    output = model.predict(
        PredictionDataset(frame.tail(1)),
        prediction_horizon=7,
        reservoir_id="RES-A",
    )
    assert isinstance(output, UniversalPredictionOutput)
    assert output.model_name == MODEL_KEY
    assert output.prediction_horizon == 7
    assert output.confidence_score is not None
    assert isinstance(output.prediction, dict)
    assert "forecasted_storage_pct" in output.prediction
    assert "forecasted_storage_mcm" in output.prediction
    assert "remaining_usable_storage_mcm" in output.prediction
    assert len(output.prediction["forecast"]) == 7

    uri = model.save()
    assert Path(uri).exists()

    restored = ReservoirLevelForecastModel(
        regressor=XGBoostReservoirRegressor(),
        persistence=JoblibModelPersistence(base_dir=artifacts_dir),
        model_version="test-1.0.0",
    )
    restored.load(version="test-1.0.0")
    assert restored.is_trained() is True
    out2 = restored.predict(PredictionDataset(None), prediction_horizon=1, reservoir_id="RES-B")
    assert out2.prediction_horizon == 1
    assert out2.prediction["reservoir_id"] == "RES-B"


def test_evaluate_report(sample_csv: Path, artifacts_dir: Path):
    pytest.importorskip("xgboost")
    model = ReservoirLevelForecastModel(
        regressor=XGBoostReservoirRegressor(n_estimators=30, max_depth=3, random_state=1),
        persistence=JoblibModelPersistence(base_dir=artifacts_dir),
        model_version="eval-1",
    )
    frame = ReservoirDatasetLoader().load_csv(sample_csv)
    dataset = TrainingDataset(frame, feature_columns=[], target_column="storage_pct")
    model.train(
        dataset,
        TrainingConfiguration(
            model_name=MODEL_KEY,
            model_version="eval-1",
            validation_split=0.25,
            random_seed=1,
        ),
    )
    report = model.evaluate(dataset)
    for key in ("mae", "rmse", "mape", "r2"):
        assert key in report["metrics"]


def test_registry_integration(sample_csv: Path, artifacts_dir: Path):
    pytest.importorskip("xgboost")
    model = build_reservoir_forecast_model(
        artifacts_dir=artifacts_dir,
        autoload=False,
        model_version="reg-1.0.0",
    )
    registry = ModelRegistry()
    registry.register("reservoir_forecast", model)
    assert registry.has("reservoir_forecast")
    fetched = registry.get("reservoir_forecast")
    assert isinstance(fetched, ReservoirLevelForecastModel)
    assert fetched.is_trained() is False

    frame = ReservoirDatasetLoader().load_csv(sample_csv)
    fetched.train(
        TrainingDataset(frame, feature_columns=[], target_column="storage_pct"),
        TrainingConfiguration(model_name="reservoir_forecast", model_version="reg-1.0.0"),
    )
    assert registry.get("reservoir_forecast").is_trained() is True
    bundle = registry.get("reservoir_forecast").predict_horizons(
        horizons=[1, 7, 15, 30],
        reservoir_id="RES-C",
    )
    assert bundle["trained"] is True
    assert "chart_series" in bundle
    assert len(bundle["chart_series"]) == 30


def test_decision_engine_integration(sample_csv: Path, artifacts_dir: Path):
    pytest.importorskip("xgboost")
    model = ReservoirLevelForecastModel(
        regressor=XGBoostReservoirRegressor(n_estimators=30, max_depth=3, random_state=2),
        persistence=JoblibModelPersistence(base_dir=artifacts_dir),
        model_version="dec-1",
    )
    frame = ReservoirDatasetLoader().load_csv(sample_csv)
    model.train(
        TrainingDataset(frame, feature_columns=[], target_column="storage_pct"),
        TrainingConfiguration(model_name=MODEL_KEY, model_version="dec-1", random_seed=2),
    )
    output = model.predict(PredictionDataset(None), prediction_horizon=14, reservoir_id="RES-A")
    forecast = list((output.prediction or {}).get("forecast") or [])
    summary = {
        "forecasted_storage_pct": output.prediction.get("forecasted_storage_pct"),
        "remaining_usable_storage_mcm": output.prediction.get("remaining_usable_storage_mcm"),
        "days_to_critical": None,
    }
    bundle = recommendations_bundle(
        universal=output,
        forecast_points=[{"forecast": p["prediction"], "horizon_day": p["horizon_day"]} for p in forecast],
        summary=summary,
        reservoir_name="Reservoir A",
    )
    assert bundle["executive_recommendations"]
    assert bundle["decision_engine"]["prediction_type"] == "reservoir_forecast"
    from fastapi_app.prediction.base import PredictionOutput

    po = PredictionOutput(**bundle["decision_engine"]["prediction"])
    rec = recommendation_from_prediction(po, output.risk_level)
    assert rec.actions
    assert any("release" in a.title.lower() or "groundwater" in a.title.lower() or "reservoir" in a.title.lower() for a in rec.actions)


def test_service_workspace_predict(sample_csv: Path, artifacts_dir: Path):
    pytest.importorskip("xgboost")
    model = build_reservoir_forecast_model(
        artifacts_dir=artifacts_dir,
        autoload=False,
        model_version="svc-1.0.0",
    )
    registry = ModelRegistry()
    registry.register(MODEL_KEY, model)
    service = ReservoirLevelForecastService(registry)
    train_result = service.train(
        dataset_path=str(sample_csv),
        use_sample=False,
        model_version="svc-1.0.0",
    )
    assert train_result["trained"] is True
    data = service.predict(value=7, unit="days", reservoir_id="RES-A")
    assert data["trained"] is True
    assert data["horizon"]["point_count"] == 7
    assert data["executive_recommendations"]
    assert data["universal"]["prediction"]["forecasted_storage_pct"] is not None


def test_untrained_predict_horizons_safe(artifacts_dir: Path):
    model = build_reservoir_forecast_model(artifacts_dir=artifacts_dir, autoload=False)
    result = model.predict_horizons()
    assert result["trained"] is False
    assert result["message"] == "Model not trained"
