"""GIS / spatial context adapter (zones, catchments, infrastructure geometry)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from fastapi_app.core.contracts import DataSourceType, RegionContext, TimeWindow
from fastapi_app.data_sources.base import DataRecordBatch, DataSource


class GISDataSource(DataSource):
    """Placeholder for GIS layers; ready for PostGIS / GeoJSON backends."""

    source_type = DataSourceType.GIS

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
                "adapter": "GISDataSource",
                "status": "not_connected",
                "planned_layers": [
                    "dma_boundaries",
                    "pipe_network",
                    "catchment_polygons",
                    "flood_plain_zones",
                ],
            },
            is_placeholder=True,
        )

    async def health_check(self) -> dict[str, Any]:
        return {
            "source": self.source_type.value,
            "status": "placeholder",
            "checked_at": datetime.utcnow().isoformat(),
        }
