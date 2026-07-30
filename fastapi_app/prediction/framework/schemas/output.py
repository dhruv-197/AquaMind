"""Universal prediction output — every future model must return this object."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

from fastapi_app.core.contracts import RiskLevel


PredictionValue = Union[float, int, str, list[Any], dict[str, Any]]


class UniversalPredictionOutput(BaseModel):
    """
    Canonical ML prediction envelope.

    Decision Engine / Dashboard adapters map from this schema; models never
    invent their own response shapes.
    """

    prediction_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique id for this prediction event",
    )
    model_name: str = Field(..., description="Registered model key, e.g. reservoir_forecast")
    model_version: str = Field(..., description="Semantic or build version of the model")
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    prediction_horizon: int = Field(
        ...,
        ge=0,
        description="Forecast horizon in the model's native unit (typically days)",
    )
    confidence_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Model confidence in [0, 1] when available",
    )
    prediction: PredictionValue = Field(
        ...,
        description="Primary prediction payload (scalar, series, or structured dict)",
    )
    risk_level: RiskLevel = Field(default=RiskLevel.UNKNOWN)
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "prediction_id": "3f2a9c1e-....",
                "model_name": "reservoir_forecast",
                "model_version": "0.0.0-untrained",
                "generated_at": "2026-07-27T06:00:00Z",
                "prediction_horizon": 7,
                "confidence_score": None,
                "prediction": {"storage_pct": 42.1},
                "risk_level": "unknown",
                "metadata": {"backend": "framework_stub"},
            }
        },
    )
