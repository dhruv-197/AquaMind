"""
Untrained placeholder predictors for registry scaffolding.

These satisfy BaseModelPredictor so keys can be reserved before algorithms exist.
All lifecycle methods raise NotImplementedError (via _train / _predict).
"""
from __future__ import annotations

from typing import Any

from fastapi_app.prediction.framework.datasets.base import (
    PredictionDataset,
    TrainingDataset,
)
from fastapi_app.prediction.framework.lifecycle.predictor import BaseModelPredictor
from fastapi_app.prediction.framework.schemas.config import TrainingConfiguration
from fastapi_app.prediction.framework.schemas.output import UniversalPredictionOutput


class UntrainedModelPredictor(BaseModelPredictor):
    """
    Reserved registry entry for a future model.

    register("reservoir_forecast", UntrainedModelPredictor(model_name="reservoir_forecast"))
    """

    def _train(self, dataset: TrainingDataset, config: TrainingConfiguration) -> Any:
        raise NotImplementedError(
            f"{self.model_name}: train() is framework-only — algorithm not implemented yet"
        )

    def _predict(
        self,
        dataset: PredictionDataset,
        *,
        prediction_horizon: int,
        **kwargs: Any,
    ) -> UniversalPredictionOutput:
        raise NotImplementedError(
            f"{self.model_name}: predict() is framework-only — algorithm not implemented yet"
        )

    def _evaluate(self, dataset: TrainingDataset, **kwargs: Any) -> dict[str, Any]:
        raise NotImplementedError(
            f"{self.model_name}: evaluate() is framework-only — algorithm not implemented yet"
        )


# Stable product keys reserved for future ML integration.
RESERVED_MODEL_KEYS: tuple[str, ...] = (
    "water_demand",
    "reservoir_forecast",
    "leakage_risk",
    "water_stress",
    "flood",
    "drought",
)


def build_untrained_placeholders() -> list[tuple[str, BaseModelPredictor]]:
    """Create reserved untrained predictors for all product model keys."""
    return [
        (key, UntrainedModelPredictor(model_name=key, model_version="0.0.0-untrained"))
        for key in RESERVED_MODEL_KEYS
    ]
