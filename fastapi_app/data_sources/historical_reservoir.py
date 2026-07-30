"""Historical reservoir storage / level observations."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from fastapi_app.core.contracts import DataSourceType, RegionContext, TimeWindow
from fastapi_app.data_sources.base import DataRecordBatch, DataSource


class HistoricalReservoirDataSource(DataSource):
    """Reads reservoir history from the operational DB (real-time is one slice)."""

    source_type = DataSourceType.HISTORICAL_RESERVOIR

    def __init__(self, db_session_factory=None) -> None:
        self._db_session_factory = db_session_factory

    async def fetch(
        self,
        region: RegionContext,
        window: Optional[TimeWindow] = None,
        **kwargs: Any,
    ) -> DataRecordBatch:
        records: list[dict[str, Any]] = []
        metadata: dict[str, Any] = {"adapter": "HistoricalReservoirDataSource"}

        if self._db_session_factory is not None:
            db: Session = self._db_session_factory()
            try:
                from fastapi_app.database.models import Reservoir

                rows = db.query(Reservoir).all()
                for row in rows:
                    records.append(
                        {
                            "id": str(row.id),
                            "name": row.name,
                            "capacity_mcm": row.capacity_mcm,
                            "current_level_pct": row.current_level_pct,
                            "location_lat": row.location_lat,
                            "location_lng": row.location_lng,
                            "data_source": getattr(row, "data_source", None),
                            "observed_at": getattr(row, "observed_at", None),
                        }
                    )
                metadata["row_count"] = len(records)
            except Exception as exc:
                metadata["error"] = str(exc)
                metadata["fallback"] = "empty_batch"
            finally:
                db.close()
        else:
            metadata["note"] = "No DB session factory bound; returning empty historical batch."

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
