"""
Abstract predictor lifecycle for all AquaMind ML models.

Concrete models implement these methods. The framework never trains or infers.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional

from fastapi_app.prediction.framework.datasets.base import (
    PredictionDataset,
    TrainingDataset,
)
from fastapi_app.prediction.framework.features.pipeline import FeaturePipeline
from fastapi_app.prediction.framework.logging.hooks import PredictionLogger
from fastapi_app.prediction.framework.persistence.store import ModelPersistence
from fastapi_app.prediction.framework.schemas.config import TrainingConfiguration
from fastapi_app.prediction.framework.schemas.output import UniversalPredictionOutput


class BaseModelPredictor(ABC):
    """
    Lifecycle contract every registered prediction model must eventually satisfy.

    Dependency injection:
      - feature_pipeline: reusable feature transforms
      - persistence: backend-agnostic artifact store
      - logger: structured training / prediction hooks
    """

    model_name: str
    model_version: str = "0.0.0-untrained"

    def __init__(
        self,
        *,
        model_name: str,
        model_version: str = "0.0.0-untrained",
        config: TrainingConfiguration | None = None,
        feature_pipeline: FeaturePipeline | None = None,
        persistence: ModelPersistence | None = None,
        logger: PredictionLogger | None = None,
    ) -> None:
        self.model_name = model_name
        self.model_version = model_version
        self.config = config or TrainingConfiguration(
            model_name=model_name,
            model_version=model_version,
        )
        self.feature_pipeline = feature_pipeline or FeaturePipeline()
        self.persistence = persistence
        self.logger = logger or PredictionLogger(model_name=model_name)
        self._is_trained: bool = False
        self._artifact: Any = None

    # ------------------------------------------------------------------
    # Lifecycle API
    # ------------------------------------------------------------------
    def train(self, dataset: TrainingDataset, config: TrainingConfiguration | None = None) -> Any:
        """Fit the model. Framework default raises — subclasses implement."""
        cfg = config or self.config
        self.logger.training_started(
            model_name=self.model_name,
            model_version=cfg.model_version,
            details={"rows": len(dataset), "features": cfg.feature_list},
        )
        try:
            result = self._train(dataset, cfg)
            self._is_trained = True
            self.model_version = cfg.model_version
            self.config = cfg
            self.logger.training_completed(
                model_name=self.model_name,
                model_version=self.model_version,
                details={"status": "ok"},
            )
            return result
        except NotImplementedError:
            self.logger.error(
                operation="train",
                message="train() not implemented",
                model_name=self.model_name,
            )
            raise
        except Exception as exc:
            self.logger.error(
                operation="train",
                message=str(exc),
                model_name=self.model_name,
            )
            raise

    def predict(
        self,
        dataset: PredictionDataset,
        *,
        prediction_horizon: int | None = None,
        **kwargs: Any,
    ) -> UniversalPredictionOutput:
        """Run inference and return the universal output schema."""
        horizon = prediction_horizon if prediction_horizon is not None else self.config.forecast_horizon
        try:
            output = self._predict(dataset, prediction_horizon=horizon, **kwargs)
            self.logger.prediction_completed(
                model_name=self.model_name,
                model_version=self.model_version,
                details={
                    "prediction_id": output.prediction_id,
                    "horizon": output.prediction_horizon,
                },
            )
            return output
        except NotImplementedError:
            self.logger.error(
                operation="predict",
                message="predict() not implemented",
                model_name=self.model_name,
            )
            raise
        except Exception as exc:
            self.logger.error(
                operation="predict",
                message=str(exc),
                model_name=self.model_name,
            )
            raise

    def evaluate(self, dataset: TrainingDataset, **kwargs: Any) -> dict[str, Any]:
        """Score the model against labeled data. Returns metric name → value."""
        try:
            metrics = self._evaluate(dataset, **kwargs)
            self.logger.evaluation_completed(
                model_name=self.model_name,
                model_version=self.model_version,
                details={"metrics": list(metrics.keys())},
            )
            return metrics
        except NotImplementedError:
            self.logger.error(
                operation="evaluate",
                message="evaluate() not implemented",
                model_name=self.model_name,
            )
            raise
        except Exception as exc:
            self.logger.error(
                operation="evaluate",
                message=str(exc),
                model_name=self.model_name,
            )
            raise

    def save(self, path: str | None = None, **kwargs: Any) -> str:
        """Persist model artifact via injected ModelPersistence backend."""
        if self.persistence is None:
            raise NotImplementedError(
                "No ModelPersistence backend injected. "
                "Provide one via DI before calling save()."
            )
        uri = self.persistence.save(
            model_name=self.model_name,
            model_version=self.model_version,
            artifact=self._artifact,
            path=path,
            metadata=self.metadata(),
            **kwargs,
        )
        return uri

    def load(self, path: str | None = None, *, version: str | None = None, **kwargs: Any) -> None:
        """Load model artifact via injected ModelPersistence backend."""
        if self.persistence is None:
            raise NotImplementedError(
                "No ModelPersistence backend injected. "
                "Provide one via DI before calling load()."
            )
        artifact = self.persistence.load(
            model_name=self.model_name,
            model_version=version or self.model_version,
            path=path,
            **kwargs,
        )
        self._artifact = artifact
        self._is_trained = True
        if version:
            self.model_version = version

    def metadata(self) -> dict[str, Any]:
        """Return model metadata for registries, dashboards, and audits."""
        return {
            "model_name": self.model_name,
            "model_version": self.model_version,
            "is_trained": self.is_trained(),
            "feature_list": list(self.config.feature_list),
            "forecast_horizon": self.config.forecast_horizon,
            "feature_pipeline_stages": self.feature_pipeline.describe(),
            "training_parameters": dict(self.config.training_parameters),
        }

    def version(self) -> str:
        return self.model_version

    def is_trained(self) -> bool:
        return self._is_trained

    # ------------------------------------------------------------------
    # Subclass hooks (raise by default)
    # ------------------------------------------------------------------
    @abstractmethod
    def _train(self, dataset: TrainingDataset, config: TrainingConfiguration) -> Any:
        raise NotImplementedError(f"{type(self).__name__}._train is not implemented")

    @abstractmethod
    def _predict(
        self,
        dataset: PredictionDataset,
        *,
        prediction_horizon: int,
        **kwargs: Any,
    ) -> UniversalPredictionOutput:
        raise NotImplementedError(f"{type(self).__name__}._predict is not implemented")

    def _evaluate(self, dataset: TrainingDataset, **kwargs: Any) -> dict[str, Any]:
        raise NotImplementedError(f"{type(self).__name__}._evaluate is not implemented")
