"""Asset maintenance / work-order logs for leakage & failure risk features."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from fastapi_app.core.contracts import DataSourceType, RegionContext, TimeWindow
from fastapi_app.data_sources.base import DataRecordBatch, DataSource


class MaintenanceLogsDataSource(DataSource):
    source_type = DataSourceType.MAINTENANCE_LOGS

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
                "adapter": "MaintenanceLogsDataSource",
                "status": "not_connected",
                "planned_fields": [
                    "asset_id",
                    "work_order_type",
                    "completed_at",
                    "pipe_age_years",
                    "material",
                    "failure_code",
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
