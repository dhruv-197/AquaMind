"""Reusable training configuration (Pydantic v2)."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TrainingConfiguration(BaseModel):
    """
    Shared training knobs for every future model.

    Models may extend this class; they must not bury config in free-form dicts.
    """

    model_name: str = Field(..., description="Registry key this config trains")
    model_version: str = Field(
        default="0.1.0",
        description="Version stamp written into metadata / artifacts",
    )
    feature_list: list[str] = Field(
        default_factory=list,
        description="Ordered feature columns expected by the model",
    )
    target_column: Optional[str] = Field(
        default=None,
        description="Label column for supervised training",
    )
    forecast_horizon: int = Field(
        default=7,
        ge=1,
        description="Default prediction horizon (days unless overridden)",
    )
    validation_split: float = Field(
        default=0.2,
        ge=0.0,
        lt=1.0,
        description="Fraction of data held out for validation",
    )
    random_seed: int = Field(default=42, description="Reproducibility seed")
    training_parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Algorithm hyperparameters (opaque to the framework)",
    )
    max_epochs: Optional[int] = Field(default=None, ge=1)
    batch_size: Optional[int] = Field(default=None, ge=1)
    early_stopping: bool = False
    notes: Optional[str] = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("feature_list")
    @classmethod
    def _dedupe_features(cls, value: list[str]) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for item in value:
            if item not in seen:
                seen.add(item)
                ordered.append(item)
        return ordered
