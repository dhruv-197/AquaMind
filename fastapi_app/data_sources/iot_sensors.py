"""IoT sensor telemetry adapter — one of several inputs, not the product center."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from fastapi_app.core.contracts import DataSourceType, RegionContext, TimeWindow
from fastapi_app.data_sources.base import DataRecordBatch, DataSource


class IoTSensorDataSource(DataSource):
    source_type = DataSourceType.IOT_SENSORS

    def __init__(self, db_session_factory=None) -> None:
        self._db_session_factory = db_session_factory

    async def fetch(
        self,
        region: RegionContext,
        window: Optional[TimeWindow] = None,
        **kwargs: Any,
    ) -> DataRecordBatch:
        records: list[dict[str, Any]] = []
        metadata: dict[str, Any] = {"adapter": "IoTSensorDataSource"}

        if self._db_session_factory is not None:
            db: Session = self._db_session_factory()
            try:
                from fastapi_app.database.models import SensorData

                rows = db.query(SensorData).all()
                for row in rows:
                    records.append(
                        {
                            "id": row.id,
                            "name": row.name,
                            "type": row.type,
                            "status": row.status,
                            "value": row.value,
                            "unit": row.unit,
                            "zone": row.zone,
                            "lat": row.lat,
                            "lng": row.lng,
                            "last_updated": row.last_updated.isoformat()
                            if row.last_updated
                            else None,
                        }
                    )
                metadata["row_count"] = len(records)
            except Exception as exc:
                metadata["error"] = str(exc)
            finally:
                db.close()

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
