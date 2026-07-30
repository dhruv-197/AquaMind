"""API schemas for Reservoir Level Forecast endpoints."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, model_validator


class ReservoirTrainRequest(BaseModel):
    dataset_path: Optional[str] = Field(
        default=None,
        description="Path to CSV/Parquet. Defaults to bundled sample dataset.",
    )
    use_sample: bool = Field(default=True, description="Train on sample dataset when path omitted")
    validation_split: float = Field(default=0.2, ge=0.05, lt=0.5)
    random_seed: int = 42
    model_version: str = "1.0.0"
    capacity_mcm: Optional[float] = Field(
        default=None,
        description="Optional default capacity when rows omit capacity_mcm",
    )
    training_parameters: dict[str, Any] = Field(default_factory=dict)


class ReservoirTrainResponse(BaseModel):
    success: bool = True
    message: str
    trained: bool
    model_version: str
    metrics: dict[str, Any] = Field(default_factory=dict)
    artifact_uri: Optional[str] = None


class ReservoirPredictRequest(BaseModel):
    """
    Preferred (workspace):
      { "value": 30, "unit": "days", "reservoir_id": "RES-A" }

    Legacy:
      { "horizon_days": 7, "horizons": [1,7,15,30] }
    """

    value: Optional[int] = Field(default=None, ge=1, description="Forecast length in unit")
    unit: Optional[Literal["days", "weeks", "months", "years"]] = Field(
        default=None,
        description="Forecast unit",
    )
    horizon_days: int = Field(default=7, description="Legacy: forecast horizon in days")
    horizons: Optional[list[int]] = Field(
        default=None,
        description="Legacy: optional list of horizons for bundled response",
    )
    reservoir_id: Optional[str] = Field(
        default=None,
        description="ML catalog reservoir id (RES-A/B/C). Prefer asset_id for national map selections.",
    )
    asset_id: Optional[str] = Field(
        default=None,
        description="National geospatial asset id (e.g. RSV-IND-017). Resolved to a forecast proxy.",
    )
    capacity_mcm: Optional[float] = None
    feature_overrides: dict[str, Any] = Field(default_factory=dict)
    include_history_days: int = Field(default=90, ge=7, le=730)

    @model_validator(mode="after")
    def _require_pair_or_legacy(self) -> ReservoirPredictRequest:
        if self.value is not None and self.unit is None:
            raise ValueError("unit is required when value is provided")
        if self.unit is not None and self.value is None:
            raise ValueError("value is required when unit is provided")
        return self


class ReservoirPredictResponse(BaseModel):
    success: bool = True
    message: str
    data: dict[str, Any]


class ReservoirStatusResponse(BaseModel):
    success: bool = True
    trained: bool
    model_name: str
    model_version: str
    last_trained_at: Optional[str] = None
    backend: Optional[str] = None
    capacity_mcm: Optional[float] = None
    supported_horizons: list[int] = Field(default_factory=list)
    training_rows: Optional[int] = None
    reservoirs: list[dict[str, Any]] = Field(default_factory=list)
    message: str = ""


class ReservoirMetricsResponse(BaseModel):
    success: bool = True
    trained: bool
    metrics: dict[str, Any] = Field(default_factory=dict)
    message: str = ""
