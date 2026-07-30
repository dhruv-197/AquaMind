"""Factory for DI — builds a reservoir model and optionally loads artifacts."""
from __future__ import annotations

from pathlib import Path

from fastapi_app.prediction.framework.logging.hooks import PredictionLogger
from fastapi_app.prediction.models.reservoir.constants import (
    ARTIFACTS_DIR,
    MODEL_KEY,
    MODEL_VERSION,
)
from fastapi_app.prediction.models.reservoir.model import ReservoirLevelForecastModel
from fastapi_app.prediction.models.reservoir.persistence import JoblibModelPersistence
from fastapi_app.prediction.models.reservoir.regressor import XGBoostReservoirRegressor


def build_reservoir_forecast_model(
    *,
    artifacts_dir: Path | None = None,
    autoload: bool = True,
    model_version: str = MODEL_VERSION,
) -> ReservoirLevelForecastModel:
    """
    Compose ReservoirLevelForecastModel with XGBoost + joblib persistence.

    Swap the regressor argument later to replace XGBoost without touching the framework.
    """
    persistence = JoblibModelPersistence(base_dir=artifacts_dir or ARTIFACTS_DIR)
    model = ReservoirLevelForecastModel(
        regressor=XGBoostReservoirRegressor(),
        persistence=persistence,
        logger=PredictionLogger(model_name=MODEL_KEY),
        model_version=model_version,
    )
    if autoload and persistence.exists(model_name=MODEL_KEY, model_version=model_version):
        try:
            model.load(version=model_version)
        except Exception as exc:
            model.logger.error(
                operation="load",
                message=str(exc),
                model_name=MODEL_KEY,
                model_version=model_version,
            )
    return model
