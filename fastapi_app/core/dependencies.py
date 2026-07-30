"""FastAPI dependency injection wiring for the prediction stack.

Routers depend on abstractions (protocols/ABCs). Concrete implementations are
assembled here so ML backends can be swapped without touching HTTP handlers.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from fastapi_app.core.config import Settings, get_settings
from fastapi_app.decision_engine.base import DecisionEngine
from fastapi_app.decision_engine.engine import RulesDecisionEngine
from fastapi_app.prediction.framework.registry.model_registry import (
    ModelRegistry,
    build_default_model_registry,
)


@lru_cache
def get_model_registry() -> ModelRegistry:
    """
    Lifecycle-aware ML ModelRegistry (framework).

    Dashboard / services must resolve models through this dependency — never
    instantiate BaseModelPredictor subclasses directly in routers.
    """
    registry = build_default_model_registry()
    # Plug in production models (replace framework placeholders).
    from fastapi_app.prediction.models.water_demand.factory import build_water_demand_model
    from fastapi_app.prediction.models.reservoir.factory import build_reservoir_forecast_model

    registry.register("water_demand", build_water_demand_model(autoload=True))
    registry.register("reservoir_forecast", build_reservoir_forecast_model(autoload=True))
    return registry


@lru_cache
def get_decision_engine() -> DecisionEngine:
    settings = get_settings()
    if settings.decision_engine_backend == "rules":
        return RulesDecisionEngine()
    return RulesDecisionEngine()


# Typed aliases for router injection
SettingsDep = Annotated[Settings, Depends(get_settings)]
ModelRegistryDep = Annotated[ModelRegistry, Depends(get_model_registry)]
DecisionEngineDep = Annotated[DecisionEngine, Depends(get_decision_engine)]
