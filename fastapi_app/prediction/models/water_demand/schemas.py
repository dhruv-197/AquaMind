"""API schemas for Water Demand Forecast endpoints."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, model_validator


class DemandTrainRequest(BaseModel):
    dataset_path: Optional[str] = Field(
        default=None,
        description="Path to CSV/Parquet. Defaults to bundled sample dataset.",
    )
    use_sample: bool = Field(default=True, description="Train on sample dataset when path omitted")
    validation_split: float = Field(default=0.2, ge=0.05, lt=0.5)
    random_seed: int = 42
    model_version: str = "1.0.0"
    capacity_mgd: Optional[float] = Field(
        default=None,
        description="Optional system capacity for risk rules",
    )
    training_parameters: dict[str, Any] = Field(default_factory=dict)


class DemandTrainResponse(BaseModel):
    success: bool = True
    message: str
    trained: bool
    model_version: str
    metrics: dict[str, Any] = Field(default_factory=dict)
    artifact_uri: Optional[str] = None


class DemandPredictRequest(BaseModel):
    """
    Backward-compatible predict body.

    Preferred (workspace):
      { "value": 30, "unit": "days" }

    Legacy:
      { "horizon_days": 7, "horizons": [1,7,15,30] }
    """

    value: Optional[int] = Field(default=None, ge=1, le=3650, description="Forecast length in unit")
    unit: Optional[Literal["days", "weeks", "months", "years"]] = Field(
        default=None,
        description="Forecast unit",
    )
    horizon_days: int = Field(
        default=7,
        ge=1,
        le=365,
        description="Legacy: forecast horizon in days (1–365)",
    )
    horizons: Optional[list[int]] = Field(
        default=None,
        description="Legacy: optional list of horizons for bundled response",
    )
    capacity_mgd: Optional[float] = Field(default=None, ge=0.0)
    feature_overrides: dict[str, Any] = Field(default_factory=dict)
    include_history_days: int = Field(
        default=90,
        ge=7,
        le=730,
        description="Historical points to include alongside the forecast",
    )

    @model_validator(mode="after")
    def _require_pair_or_legacy(self) -> DemandPredictRequest:
        if self.value is not None and self.unit is None:
            raise ValueError("unit is required when value is provided")
        if self.unit is not None and self.value is None:
            raise ValueError("value is required when unit is provided")
        return self


class DemandPredictResponse(BaseModel):
    success: bool = True
    message: str
    data: dict[str, Any]


class DemandStatusResponse(BaseModel):
    success: bool = True
    trained: bool
    model_name: str
    model_version: str
    last_trained_at: Optional[str] = None
    backend: Optional[str] = None
    capacity_mgd: Optional[float] = None
    supported_horizons: list[int] = Field(default_factory=list)
    training_rows: Optional[int] = None
    message: str = ""


class DemandMetricsResponse(BaseModel):
    success: bool = True
    trained: bool
    metrics: dict[str, Any] = Field(default_factory=dict)
    message: str = ""
