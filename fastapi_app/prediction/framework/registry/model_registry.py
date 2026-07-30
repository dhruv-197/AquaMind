"""
Model Registry — dynamic registration of BaseModelPredictor instances.

Example:
    registry.register("reservoir_forecast", predictor)
    registry.register("water_demand", predictor)

The Dashboard / Decision stack resolves models via this registry (DI),
never by constructing predictors inline.
"""
from __future__ import annotations

from typing import Iterable

from fastapi_app.prediction.framework.lifecycle.predictor import BaseModelPredictor


class ModelRegistryError(KeyError):
    """Raised when a model key is missing or already registered (strict mode)."""


class ModelRegistry:
    """
    String-keyed registry of lifecycle-aware predictors.

    Keys are stable product names (e.g. "reservoir_forecast"), independent of
    class names so implementations can be swapped without API churn.
    """

    def __init__(
        self,
        predictors: Iterable[tuple[str, BaseModelPredictor]] | None = None,
        *,
        allow_override: bool = True,
    ) -> None:
        self._models: dict[str, BaseModelPredictor] = {}
        self._allow_override = allow_override
        if predictors:
            for key, predictor in predictors:
                self.register(key, predictor)

    def register(self, name: str, predictor: BaseModelPredictor) -> None:
        """Register (or replace) a predictor under a stable string key."""
        key = self._normalize(name)
        if not key:
            raise ValueError("Model registry key must be a non-empty string")
        if not self._allow_override and key in self._models:
            raise ModelRegistryError(f"Model already registered: {key}")
        if predictor.model_name != key:
            # Keep identity aligned with registry key for UniversalPredictionOutput.
            predictor.model_name = key
        self._models[key] = predictor

    def unregister(self, name: str) -> None:
        key = self._normalize(name)
        if key in self._models:
            del self._models[key]

    def get(self, name: str) -> BaseModelPredictor:
        key = self._normalize(name)
        if key not in self._models:
            raise ModelRegistryError(f"Model not registered: {key}")
        return self._models[key]

    def has(self, name: str) -> bool:
        return self._normalize(name) in self._models

    def list_models(self) -> list[str]:
        return sorted(self._models.keys())

    def metadata(self) -> dict[str, dict]:
        return {name: model.metadata() for name, model in self._models.items()}

    def readiness(self) -> dict[str, bool]:
        return {name: model.is_trained() for name, model in self._models.items()}

    @staticmethod
    def _normalize(name: str) -> str:
        return str(name).strip().lower().replace(" ", "_")


def build_empty_model_registry() -> ModelRegistry:
    """
    Default DI factory: empty registry ready for dynamic registration.

    Stub service-layer predictors remain in prediction.registry.PredictionRegistry.
    Lifecycle models are registered here as they are implemented.
    """
    return ModelRegistry()


def build_default_model_registry() -> ModelRegistry:
    """
    Registry pre-seeded with untrained placeholders for known product keys.

    Algorithms are NOT implemented — entries exist so the dashboard can resolve
    model names via DI without instantiating classes inline.
    """
    from fastapi_app.prediction.framework.placeholders import build_untrained_placeholders

    return ModelRegistry(build_untrained_placeholders())
