"""Reservoir Level Forecast model package (XGBoost)."""
from fastapi_app.prediction.models.reservoir.factory import build_reservoir_forecast_model
from fastapi_app.prediction.models.reservoir.model import ReservoirLevelForecastModel

MODEL_KEY = "reservoir_forecast"
MODEL_VERSION = "1.0.0"

__all__ = [
    "ReservoirLevelForecastModel",
    "build_reservoir_forecast_model",
    "MODEL_KEY",
    "MODEL_VERSION",
]
