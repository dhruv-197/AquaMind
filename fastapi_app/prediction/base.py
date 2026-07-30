"""Prediction DTOs and abstract predictor contract."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from fastapi_app.core.contracts import PredictionType, RiskLevel, RegionContext
from fastapi_app.processing.base import FeatureSet


class ForecastPoint(BaseModel):
    timestamp: str
    value: float
    unit: str
    lower_bound: Optional[float] = None
    upper_bound: Optional[float] = None


class PredictionOutput(BaseModel):
    """Normalized prediction payload consumed by the Decision Engine."""

    prediction_type: PredictionType
    region_id: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    horizon_days: int = 7
    risk_level: RiskLevel = RiskLevel.UNKNOWN
    score: Optional[float] = Field(
        default=None,
        description="0–100 risk/intensity score when available",
    )
    confidence: Optional[float] = Field(
        default=None,
        description="Model confidence 0–1 when a trained backend is wired",
    )
    summary: str
    forecast: list[ForecastPoint] = Field(default_factory=list)
    drivers: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    is_placeholder: bool = True


class Predictor(ABC):
    """Interface for a single prediction capability."""

    prediction_type: PredictionType

    @abstractmethod
    async def predict(
        self,
        region: RegionContext,
        features: FeatureSet,
        horizon_days: int = 7,
        **kwargs: Any,
    ) -> PredictionOutput:
        """Run inference. Stub implementations return structured placeholders."""

    @abstractmethod
    async def is_ready(self) -> bool:
        """True when a real model backend is loaded and healthy."""
