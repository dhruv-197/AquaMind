"""Application settings for the Water Decision Intelligence Platform."""
from __future__ import annotations

import os
from functools import lru_cache

from pydantic import BaseModel, Field


class Settings(BaseModel):
    """Runtime configuration. ML backends plug in via env without code changes."""

    app_name: str = "AquaMind Water Decision Intelligence Platform"
    app_version: str = "2.0.0"
    environment: str = Field(default="development", description="development | staging | production")

    # Prediction layer: "stub" returns structured placeholders; "ml" will wire trained models.
    prediction_backend: str = Field(
        default="stub",
        description="Active prediction backend identifier (stub | ml).",
    )

    # Decision engine: rule-based today; scoring models can replace later.
    decision_engine_backend: str = Field(
        default="rules",
        description="Active decision engine backend (rules | ml).",
    )

    default_region_id: str = "REG-1"
    default_forecast_horizon_days: int = 7


@lru_cache
def get_settings() -> Settings:
    return Settings(
        environment=os.getenv("AQUAMIND_ENVIRONMENT", "development"),
        prediction_backend=os.getenv("AQUAMIND_PREDICTION_BACKEND", "stub"),
        decision_engine_backend=os.getenv("AQUAMIND_DECISION_ENGINE_BACKEND", "rules"),
        default_region_id=os.getenv("AQUAMIND_DEFAULT_REGION_ID", "REG-1"),
        default_forecast_horizon_days=int(os.getenv("AQUAMIND_DEFAULT_FORECAST_HORIZON_DAYS", "7")),
    )
