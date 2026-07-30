"""Processing stage contracts."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from fastapi_app.core.contracts import DataSourceType
from fastapi_app.data_sources.base import DataRecordBatch


class ProcessingIssue(BaseModel):
    severity: str  # info | warning | error
    code: str
    message: str
    source_type: DataSourceType | None = None


class FeatureSet(BaseModel):
    """ML-ready feature matrix envelope (no model training here)."""

    region_id: str
    prepared_at: datetime = Field(default_factory=datetime.utcnow)
    feature_names: list[str] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    issues: list[ProcessingIssue] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProcessingStage(ABC):
    name: str

    @abstractmethod
    async def apply(self, batches: dict[DataSourceType, DataRecordBatch]) -> dict[DataSourceType, DataRecordBatch]:
        """Transform or validate source batches in place / return new mapping."""
