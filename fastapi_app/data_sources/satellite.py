"""Satellite / remote-sensing adapter — future data source."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from fastapi_app.core.contracts import DataSourceType, RegionContext, TimeWindow
from fastapi_app.data_sources.base import DataRecordBatch, DataSource


class SatelliteDataSource(DataSource):
    """Reserved for NDWI / surface-water extent / soil-moisture feeds."""

    source_type = DataSourceType.SATELLITE

    async def fetch(
        self,
        region: RegionContext,
        window: Optional[TimeWindow] = None,
        **kwargs: Any,
    ) -> DataRecordBatch:
        return DataRecordBatch(
            source_type=self.source_type,
            region_id=region.region_id,
            records=[],
            metadata={
                "adapter": "SatelliteDataSource",
                "status": "future",
                "planned_products": [
                    "surface_water_extent",
                    "ndwi",
                    "soil_moisture",
                    "land_surface_temperature",
                ],
            },
            is_placeholder=True,
        )

    async def health_check(self) -> dict[str, Any]:
        return {
            "source": self.source_type.value,
            "status": "future",
            "checked_at": datetime.utcnow().isoformat(),
        }
