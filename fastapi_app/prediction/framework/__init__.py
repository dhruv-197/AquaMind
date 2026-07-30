"""
Shared ML Prediction Framework.

Framework-level contracts only — no algorithms, no TensorFlow/PyTorch/XGBoost.
Future models subclass these interfaces and register via ModelRegistry.
"""
from fastapi_app.prediction.framework.datasets.base import (
    Dataset,
    PredictionDataset,
    TrainingDataset,
)
from fastapi_app.prediction.framework.features.pipeline import FeaturePipeline
from fastapi_app.prediction.framework.lifecycle.predictor import BaseModelPredictor
from fastapi_app.prediction.framework.logging.hooks import PredictionLogger
from fastapi_app.prediction.framework.persistence.store import ModelPersistence
from fastapi_app.prediction.framework.registry.model_registry import (
    ModelRegistry,
    build_default_model_registry,
)
from fastapi_app.prediction.framework.schemas.config import TrainingConfiguration
from fastapi_app.prediction.framework.schemas.output import UniversalPredictionOutput

__all__ = [
    "Dataset",
    "TrainingDataset",
    "PredictionDataset",
    "FeaturePipeline",
    "BaseModelPredictor",
    "ModelRegistry",
    "build_default_model_registry",
    "TrainingConfiguration",
    "UniversalPredictionOutput",
    "ModelPersistence",
    "PredictionLogger",
]
