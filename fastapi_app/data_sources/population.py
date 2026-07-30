"""Population / demographic drivers for demand forecasting."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from fastapi_app.core.contracts import DataSourceType, RegionContext, TimeWindow
from fastapi_app.data_sources.base import DataRecordBatch, DataSource


class PopulationDataSource(DataSource):
    source_type = DataSourceType.POPULATION

    async def fetch(
        self,
        region: RegionContext,
        window: Optional[TimeWindow] = None,
        **kwargs: Any,
    ) -> DataRecordBatch:
        # Seed-aware placeholder: consumption_series may carry population_thousands.
        return DataRecordBatch(
            source_type=self.source_type,
            region_id=region.region_id,
            records=[],
            metadata={
                "adapter": "PopulationDataSource",
                "status": "not_connected",
                "planned_fields": [
                    "population_thousands",
                    "growth_rate_pct",
                    "household_count",
                    "census_year",
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
