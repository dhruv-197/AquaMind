"""External weather API adapter (Open-Meteo / local Weather table)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from fastapi_app.core.contracts import DataSourceType, RegionContext, TimeWindow
from fastapi_app.data_sources.base import DataRecordBatch, DataSource


class WeatherApiDataSource(DataSource):
    """Weather is an input to prediction — not the product center."""

    source_type = DataSourceType.WEATHER_API

    def __init__(self, db_session_factory=None) -> None:
        self._db_session_factory = db_session_factory

    async def fetch(
        self,
        region: RegionContext,
        window: Optional[TimeWindow] = None,
        **kwargs: Any,
    ) -> DataRecordBatch:
        records: list[dict[str, Any]] = []
        metadata: dict[str, Any] = {
            "adapter": "WeatherApiDataSource",
            "live_client": "deferred",  # climate/ Open-Meteo client plugs in here
        }

        if self._db_session_factory is not None:
            db: Session = self._db_session_factory()
            try:
                from fastapi_app.database.models import Weather

                rows = db.query(Weather).order_by(Weather.recorded_at.desc()).limit(50).all()
                for row in rows:
                    records.append(
                        {
                            "id": str(row.id),
                            "location": row.location,
                            "temperature_c": row.temperature_c,
                            "humidity_pct": row.humidity_pct,
                            "precipitation_mm": row.precipitation_mm,
                            "rainfall_deficit_pct": row.rainfall_deficit_pct,
                            "heatwave_warning": row.heatwave_warning,
                            "evapotranspiration_rate_mm": row.evapotranspiration_rate_mm,
                            "recorded_at": row.recorded_at.isoformat()
                            if row.recorded_at
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
