"""Orchestrates cleaning → validation → time-series → feature engineering."""
from __future__ import annotations

from fastapi_app.core.contracts import DataSourceType, RegionContext
from fastapi_app.data_sources.base import DataRecordBatch
from fastapi_app.processing.base import FeatureSet
from fastapi_app.processing.cleaning import CleaningStage
from fastapi_app.processing.feature_engineering import FeatureEngineeringService
from fastapi_app.processing.timeseries import TimeSeriesPreparationStage
from fastapi_app.processing.validation import ValidationStage


class DataProcessingPipeline:
    """
    Single entry point for the Data Processing Layer.

    Stages are injectable for tests / alternate pipelines (Open/Closed).
    """

    def __init__(
        self,
        cleaning: CleaningStage | None = None,
        validation: ValidationStage | None = None,
        timeseries: TimeSeriesPreparationStage | None = None,
        features: FeatureEngineeringService | None = None,
    ) -> None:
        self.cleaning = cleaning or CleaningStage()
        self.validation = validation or ValidationStage()
        self.timeseries = timeseries or TimeSeriesPreparationStage()
        self.features = features or FeatureEngineeringService()

    async def run(
        self,
        region: RegionContext,
        batches: dict[DataSourceType, DataRecordBatch],
        horizon_days: int = 7,
    ) -> tuple[dict[DataSourceType, DataRecordBatch], FeatureSet]:
        cleaned = await self.cleaning.apply(batches)
        validated = await self.validation.apply(cleaned)
        ts_ready = await self.timeseries.apply(validated)
        feature_set = await self.features.build(region, ts_ready, horizon_days=horizon_days)
        return ts_ready, feature_set
