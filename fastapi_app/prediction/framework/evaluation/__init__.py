"""Evaluation metric interfaces only — no numeric implementations."""
from fastapi_app.prediction.framework.evaluation.metrics import (
    CustomMetric,
    EvaluationMetric,
    EvaluationSuite,
    MAE,
    MAPE,
    RMSE,
    R2,
)

__all__ = [
    "EvaluationMetric",
    "MAE",
    "RMSE",
    "MAPE",
    "R2",
    "CustomMetric",
    "EvaluationSuite",
]
