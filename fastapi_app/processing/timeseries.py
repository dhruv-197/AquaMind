"""Time-series preparation helpers for forecast pipelines."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from fastapi_app.core.contracts import DataSourceType
from fastapi_app.data_sources.base import DataRecordBatch
from fastapi_app.processing.base import ProcessingStage


class TimeSeriesPreparationStage(ProcessingStage):
    """
    Sorts chronological series and builds simple lag / rolling placeholders.

    Algorithmic forecasting models will consume this structure later.
    """

    name = "timeseries_preparation"

    def __init__(self, date_field: str = "observed_date", value_field: str = "demand_mgd") -> None:
        self.date_field = date_field
        self.value_field = value_field

    async def apply(
        self, batches: dict[DataSourceType, DataRecordBatch]
    ) -> dict[DataSourceType, DataRecordBatch]:
        prepared = dict(batches)
        demand = batches.get(DataSourceType.HISTORICAL_DEMAND)
        if not demand or not demand.records:
            return prepared

        sorted_rows = sorted(
            [r for r in demand.records if r.get(self.date_field)],
            key=lambda r: str(r[self.date_field]),
        )
        enriched: list[dict[str, Any]] = []
        values: list[float] = []
        for row in sorted_rows:
            item = dict(row)
            try:
                value = float(row[self.value_field])
            except (KeyError, TypeError, ValueError):
                enriched.append(item)
                continue
            values.append(value)
            item["lag_1"] = values[-2] if len(values) >= 2 else None
            item["rolling_mean_7"] = (
                sum(values[-7:]) / min(7, len(values)) if values else None
            )
            enriched.append(item)

        meta = dict(demand.metadata)
        meta["timeseries"] = {
            "sorted": True,
            "lag_features": ["lag_1"],
            "rolling_features": ["rolling_mean_7"],
            "points": len(enriched),
        }
        prepared[DataSourceType.HISTORICAL_DEMAND] = demand.model_copy(
            update={"records": enriched, "metadata": meta}
        )
        return prepared


def build_forecast_index(horizon_days: int, start: datetime | None = None) -> list[str]:
    """Return ISO dates for a forecast horizon (utility for future models)."""
    origin = start or datetime.utcnow()
    return [(origin + timedelta(days=i + 1)).date().isoformat() for i in range(horizon_days)]
