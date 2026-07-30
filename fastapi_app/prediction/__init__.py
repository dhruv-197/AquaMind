"""
Prediction package.

- `base.py` — shared PredictionOutput/ForecastPoint contract consumed by the
  Decision Engine and the reservoir/water-demand model adapters.
- `framework/` — shared ML lifecycle framework (registry, persistence,
  feature pipeline) backing the real trained models under `models/`.
- `models/` — real, trained predictors (reservoir, water_demand, water_stress).
"""
from fastapi_app.prediction.base import ForecastPoint, PredictionOutput, Predictor
from fastapi_app.prediction.framework import (
    BaseModelPredictor,
    Dataset,
    ModelRegistry,
    PredictionDataset,
    TrainingConfiguration,
    TrainingDataset,
    UniversalPredictionOutput,
)

__all__ = [
    "Predictor",
    "PredictionOutput",
    "ForecastPoint",
    # ML framework
    "Dataset",
    "TrainingDataset",
    "PredictionDataset",
    "BaseModelPredictor",
    "ModelRegistry",
    "TrainingConfiguration",
    "UniversalPredictionOutput",
]
