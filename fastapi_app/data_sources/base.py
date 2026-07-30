"""Abstract data-source contract (Dependency Inversion)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from fastapi_app.core.contracts import DataSourceType, RegionContext, TimeWindow


class DataRecordBatch(BaseModel):
    """Normalized batch returned by every data-source adapter."""

    source_type: DataSourceType
    region_id: str
    fetched_at: datetime = Field(default_factory=datetime.utcnow)
    records: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    is_placeholder: bool = False


class DataSource(ABC):
    """Interface every data source must implement."""

    source_type: DataSourceType

    @abstractmethod
    async def fetch(
        self,
        region: RegionContext,
        window: Optional[TimeWindow] = None,
        **kwargs: Any,
    ) -> DataRecordBatch:
        """Pull raw records for a region / time window."""

    @abstractmethod
    async def health_check(self) -> dict[str, Any]:
        """Lightweight availability probe for ops / dashboard status."""
