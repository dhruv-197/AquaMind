"""Factory for DI — builds a demand model and optionally loads artifacts."""
from __future__ import annotations

from pathlib import Path

from fastapi_app.prediction.framework.logging.hooks import PredictionLogger
from fastapi_app.prediction.models.water_demand.constants import (
    ARTIFACTS_DIR,
    MODEL_KEY,
    MODEL_VERSION,
)
from fastapi_app.prediction.models.water_demand.model import WaterDemandForecastModel
from fastapi_app.prediction.models.water_demand.persistence import JoblibModelPersistence
from fastapi_app.prediction.models.water_demand.regressor import XGBoostDemandRegressor


def build_water_demand_model(
    *,
    artifacts_dir: Path | None = None,
    autoload: bool = True,
    model_version: str = MODEL_VERSION,
) -> WaterDemandForecastModel:
    """
    Compose WaterDemandForecastModel with XGBoost + joblib persistence.

    Swap the regressor argument later to replace XGBoost without touching the framework.
    """
    persistence = JoblibModelPersistence(base_dir=artifacts_dir or ARTIFACTS_DIR)
    model = WaterDemandForecastModel(
        regressor=XGBoostDemandRegressor(),
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
