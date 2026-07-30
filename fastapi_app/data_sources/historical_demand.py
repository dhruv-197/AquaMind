"""Historical municipal / industrial water demand series."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from fastapi_app.core.contracts import DataSourceType, RegionContext, TimeWindow
from fastapi_app.data_sources.base import DataRecordBatch, DataSource


class HistoricalDemandDataSource(DataSource):
    """Reads demand (MGD) time series used by forecast feature pipelines."""

    source_type = DataSourceType.HISTORICAL_DEMAND

    def __init__(self, db_session_factory=None) -> None:
        self._db_session_factory = db_session_factory

    async def fetch(
        self,
        region: RegionContext,
        window: Optional[TimeWindow] = None,
        **kwargs: Any,
    ) -> DataRecordBatch:
        records: list[dict[str, Any]] = []
        metadata: dict[str, Any] = {"adapter": "HistoricalDemandDataSource"}

        if self._db_session_factory is not None:
            db: Session = self._db_session_factory()
            try:
                from fastapi_app.database.models import ConsumptionSeries

                query = db.query(ConsumptionSeries).filter(
                    ConsumptionSeries.region_id == region.region_id
                )
                if window is not None:
                    query = query.filter(
                        ConsumptionSeries.observed_date >= window.start.date(),
                        ConsumptionSeries.observed_date <= window.end.date(),
                    )
                rows = query.order_by(ConsumptionSeries.observed_date.asc()).all()
                for row in rows:
                    records.append(
                        {
                            "id": str(row.id),
                            "region_id": row.region_id,
                            "observed_date": row.observed_date.isoformat()
                            if row.observed_date
                            else None,
                            "demand_mgd": row.demand_mgd,
                            "population_thousands": row.population_thousands,
                            "source": row.source,
                        }
                    )
                metadata["row_count"] = len(records)
            except Exception as exc:
                metadata["error"] = str(exc)
                metadata["fallback"] = "empty_batch"
            finally:
                db.close()
        else:
            metadata["note"] = "No DB session factory bound; returning empty demand batch."

        return DataRecordBatch(
            source_type=self.source_type,
            region_id=region.region_id,
            records=records,
            metadata=metadata,
            is_placeholder=len(records) == 0,
        )

    async def health_check(self) -> dict[str, Any]:
        return {
            "source": self.source_type.value,
            "status": "ready",
            "checked_at": datetime.utcnow().isoformat(),
        }
