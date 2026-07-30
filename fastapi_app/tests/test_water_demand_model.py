"""Unit tests for Water Demand Forecast production model."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from fastapi_app.prediction.framework.datasets.base import TrainingDataset
from fastapi_app.prediction.framework.registry.model_registry import ModelRegistry
from fastapi_app.prediction.framework.schemas.config import TrainingConfiguration
from fastapi_app.prediction.framework.schemas.output import UniversalPredictionOutput
from fastapi_app.prediction.models.water_demand.constants import MODEL_KEY
from fastapi_app.prediction.models.water_demand.dataset import (
    DemandDatasetLoader,
    DemandDatasetValidationError,
    generate_sample_dataset,
)
from fastapi_app.prediction.models.water_demand.factory import build_water_demand_model
from fastapi_app.prediction.models.water_demand.model import WaterDemandForecastModel
from fastapi_app.prediction.models.water_demand.persistence import JoblibModelPersistence
from fastapi_app.prediction.models.water_demand.regressor import XGBoostDemandRegressor
from fastapi_app.prediction.models.water_demand.risk import demand_risk_level
from fastapi_app.core.contracts import RiskLevel


@pytest.fixture(scope="module")
def sample_csv(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("demand_data")
    path = root / "sample_demand.csv"
    generate_sample_dataset(path, days=400, seed=7)
    return path


@pytest.fixture
def artifacts_dir(tmp_path) -> Path:
    d = tmp_path / "artifacts"
    d.mkdir()
    return d


def test_dataset_loading_csv(sample_csv: Path):
    loader = DemandDatasetLoader()
    frame = loader.load_csv(sample_csv)
    assert "date" in frame.columns
    assert "demand_mgd" in frame.columns
    assert len(frame) > 100
    assert frame["date"].is_monotonic_increasing


def test_dataset_loading_dataframe_and_duplicates():
    loader = DemandDatasetLoader()
    frame = pd.DataFrame(
        {
            "date": ["2024-01-01", "2024-01-01", "2024-01-02"],
            "demand_mgd": [100.0, 101.0, 102.0],
            "temperature_c": [30.0, 31.0, 29.0],
        }
    )
    cleaned = loader.load_dataframe(frame)
    assert len(cleaned) == 2


def test_dataset_rejects_bad_timestamps():
    loader = DemandDatasetLoader()
    with pytest.raises(DemandDatasetValidationError):
        loader.load_dataframe(
            pd.DataFrame({"date": ["not-a-date"], "demand_mgd": [10.0]})
        )


def test_dataset_missing_required_column():
    loader = DemandDatasetLoader()
    with pytest.raises(DemandDatasetValidationError):
        loader.load_dataframe(pd.DataFrame({"date": ["2024-01-01"], "value": [1.0]}))


def test_risk_rules():
    assert demand_risk_level(96, 100) == RiskLevel.HIGH
    assert demand_risk_level(85, 100) == RiskLevel.MODERATE
    assert demand_risk_level(50, 100) == RiskLevel.LOW


def test_training_prediction_and_serialization(sample_csv: Path, artifacts_dir: Path):
    pytest.importorskip("xgboost")
    model = WaterDemandForecastModel(
        regressor=XGBoostDemandRegressor(n_estimators=40, max_depth=4, random_state=0),
        persistence=JoblibModelPersistence(base_dir=artifacts_dir),
        model_version="test-1.0.0",
    )
    assert model.is_trained() is False

    loader = DemandDatasetLoader()
    frame = loader.load_csv(sample_csv)
    dataset = TrainingDataset(
        frame,
        feature_columns=[],
        target_column="demand_mgd",
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

    from fastapi_app.prediction.framework.datasets.base import PredictionDataset

    output = model.predict(PredictionDataset(frame.tail(1)), prediction_horizon=7)
    assert isinstance(output, UniversalPredictionOutput)
    assert output.model_name == MODEL_KEY
    assert output.prediction_horizon == 7
    assert output.confidence_score is not None
    assert isinstance(output.prediction, dict)
    assert len(output.prediction["forecast"]) == 7

    uri = model.save()
    assert Path(uri).exists()

    restored = WaterDemandForecastModel(
        regressor=XGBoostDemandRegressor(),
        persistence=JoblibModelPersistence(base_dir=artifacts_dir),
        model_version="test-1.0.0",
    )
    restored.load(version="test-1.0.0")
    assert restored.is_trained() is True
    out2 = restored.predict(PredictionDataset(None), prediction_horizon=1)
    assert out2.prediction_horizon == 1


def test_evaluate_report(sample_csv: Path, artifacts_dir: Path):
    pytest.importorskip("xgboost")
    model = WaterDemandForecastModel(
        regressor=XGBoostDemandRegressor(n_estimators=30, max_depth=3, random_state=1),
        persistence=JoblibModelPersistence(base_dir=artifacts_dir),
        model_version="eval-1",
    )
    frame = DemandDatasetLoader().load_csv(sample_csv)
    dataset = TrainingDataset(frame, feature_columns=[], target_column="demand_mgd")
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
    model = build_water_demand_model(
        artifacts_dir=artifacts_dir,
        autoload=False,
        model_version="reg-1.0.0",
    )
    registry = ModelRegistry()
    registry.register("water_demand", model)
    assert registry.has("water_demand")
    fetched = registry.get("water_demand")
    assert isinstance(fetched, WaterDemandForecastModel)
    assert fetched.is_trained() is False

    frame = DemandDatasetLoader().load_csv(sample_csv)
    fetched.train(
        TrainingDataset(frame, feature_columns=[], target_column="demand_mgd"),
        TrainingConfiguration(model_name="water_demand", model_version="reg-1.0.0"),
    )
    assert registry.get("water_demand").is_trained() is True
    bundle = registry.get("water_demand").predict_horizons(horizons=[1, 7, 15, 30])
    assert bundle["trained"] is True
    assert "chart_series" in bundle
    assert len(bundle["chart_series"]) == 30


def test_untrained_predict_horizons_safe(artifacts_dir: Path):
    model = build_water_demand_model(artifacts_dir=artifacts_dir, autoload=False)
    result = model.predict_horizons()
    assert result["trained"] is False
    assert result["message"] == "Model not trained"
