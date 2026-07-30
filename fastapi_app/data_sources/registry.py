"""Registry of data-source adapters (Open/Closed — add sources without rewriting callers)."""
from __future__ import annotations

from typing import Iterable

from fastapi_app.core.contracts import DataSourceType, RegionContext, TimeWindow
from fastapi_app.data_sources.base import DataRecordBatch, DataSource
from fastapi_app.data_sources.gis import GISDataSource
from fastapi_app.data_sources.historical_demand import HistoricalDemandDataSource
from fastapi_app.data_sources.historical_reservoir import HistoricalReservoirDataSource
from fastapi_app.data_sources.iot_sensors import IoTSensorDataSource
from fastapi_app.data_sources.maintenance_logs import MaintenanceLogsDataSource
from fastapi_app.data_sources.population import PopulationDataSource
from fastapi_app.data_sources.satellite import SatelliteDataSource
from fastapi_app.data_sources.weather_api import WeatherApiDataSource


class DataSourceRegistry:
    """Lookup + fan-out for all configured data sources."""

    def __init__(self, sources: Iterable[DataSource] | None = None) -> None:
        self._sources: dict[DataSourceType, DataSource] = {}
        if sources:
            for source in sources:
                self.register(source)

    def register(self, source: DataSource) -> None:
        self._sources[source.source_type] = source

    def get(self, source_type: DataSourceType) -> DataSource:
        if source_type not in self._sources:
            raise KeyError(f"Data source not registered: {source_type}")
        return self._sources[source_type]

    def list_types(self) -> list[DataSourceType]:
        return list(self._sources.keys())

    async def fetch_all(
        self,
        region: RegionContext,
        window: TimeWindow | None = None,
    ) -> dict[DataSourceType, DataRecordBatch]:
        results: dict[DataSourceType, DataRecordBatch] = {}
        for source_type, source in self._sources.items():
            results[source_type] = await source.fetch(region, window)
        return results

    async def health(self) -> list[dict]:
        return [await s.health_check() for s in self._sources.values()]


def build_default_registry() -> DataSourceRegistry:
    """Compose production-default adapters. DB-backed sources share SessionLocal."""
    from fastapi_app.database.connection import SessionLocal

    return DataSourceRegistry(
        [
            HistoricalReservoirDataSource(db_session_factory=SessionLocal),
            HistoricalDemandDataSource(db_session_factory=SessionLocal),
            WeatherApiDataSource(db_session_factory=SessionLocal),
            IoTSensorDataSource(db_session_factory=SessionLocal),
            GISDataSource(),
            MaintenanceLogsDataSource(),
            PopulationDataSource(),
            SatelliteDataSource(),
        ]
    )
