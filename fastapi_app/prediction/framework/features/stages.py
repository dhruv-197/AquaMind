"""Feature pipeline stage interfaces — no algorithms, no model-specific code."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import pandas as pd
from pydantic import BaseModel, Field


class FeatureStageResult(BaseModel):
    """Envelope returned by a stage for observability."""

    stage_name: str
    rows_in: int
    rows_out: int
    columns_out: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class FeatureStage(ABC):
    """Single transform in a feature pipeline."""

    name: str

    @abstractmethod
    def transform(self, frame: pd.DataFrame) -> pd.DataFrame:
        """Apply the stage. Implementations must not mutate the input frame."""

    def describe(self) -> dict[str, Any]:
        return {"name": self.name, "type": type(self).__name__}


class FeatureExtractionStage(FeatureStage):
    """Extract raw / derived features from source columns."""

    name = "feature_extraction"

    def transform(self, frame: pd.DataFrame) -> pd.DataFrame:
        raise NotImplementedError(
            "FeatureExtractionStage.transform must be implemented by a concrete stage"
        )


class FeatureNormalizationStage(FeatureStage):
    """Scale / normalize numeric features (fit params live on the concrete stage)."""

    name = "feature_normalization"

    def fit(self, frame: pd.DataFrame) -> FeatureNormalizationStage:
        """Learn normalization parameters from training data."""
        raise NotImplementedError(
            "FeatureNormalizationStage.fit must be implemented by a concrete stage"
        )

    def transform(self, frame: pd.DataFrame) -> pd.DataFrame:
        raise NotImplementedError(
            "FeatureNormalizationStage.transform must be implemented by a concrete stage"
        )


class MissingValueStage(FeatureStage):
    """Handle missing values (impute / drop / flag)."""

    name = "missing_value_handling"

    def transform(self, frame: pd.DataFrame) -> pd.DataFrame:
        raise NotImplementedError(
            "MissingValueStage.transform must be implemented by a concrete stage"
        )


class TimeSeriesWindowStage(FeatureStage):
    """Create lag / rolling / lookback windows for time-series features."""

    name = "timeseries_window"

    def transform(self, frame: pd.DataFrame) -> pd.DataFrame:
        raise NotImplementedError(
            "TimeSeriesWindowStage.transform must be implemented by a concrete stage"
        )


class FeatureValidationStage(FeatureStage):
    """Validate feature schema, dtypes, and ranges before model I/O."""

    name = "feature_validation"

    def transform(self, frame: pd.DataFrame) -> pd.DataFrame:
        raise NotImplementedError(
            "FeatureValidationStage.transform must be implemented by a concrete stage"
        )

    def validate(self, frame: pd.DataFrame) -> list[str]:
        """Return validation issues without mutating data."""
        raise NotImplementedError(
            "FeatureValidationStage.validate must be implemented by a concrete stage"
        )
