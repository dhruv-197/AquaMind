"""Feature engineering — builds model-ready feature rows from cleaned batches."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi_app.core.contracts import DataSourceType, RegionContext
from fastapi_app.data_sources.base import DataRecordBatch
from fastapi_app.processing.base import FeatureSet


class FeatureEngineeringService:
    """
    Produces a FeatureSet for prediction interfaces.

    Does NOT train or infer models — only prepares tabular features.
    """

    async def build(
        self,
        region: RegionContext,
        batches: dict[DataSourceType, DataRecordBatch],
        horizon_days: int = 7,
    ) -> FeatureSet:
        features: dict[str, Any] = {
            "region_id": region.region_id,
            "horizon_days": horizon_days,
            "as_of": datetime.utcnow().isoformat(),
        }
        feature_names = ["region_id", "horizon_days", "as_of"]

        reservoir = batches.get(DataSourceType.HISTORICAL_RESERVOIR)
        if reservoir and reservoir.records:
            levels = [
                float(r["current_level_pct"])
                for r in reservoir.records
                if r.get("current_level_pct") is not None
            ]
            capacities = [
                float(r["capacity_mcm"])
                for r in reservoir.records
                if r.get("capacity_mcm") is not None
            ]
            if levels:
                features["reservoir_level_pct_mean"] = sum(levels) / len(levels)
                features["reservoir_level_pct_min"] = min(levels)
                feature_names.extend(["reservoir_level_pct_mean", "reservoir_level_pct_min"])
            if capacities:
                features["reservoir_capacity_mcm_sum"] = sum(capacities)
                feature_names.append("reservoir_capacity_mcm_sum")

        demand = batches.get(DataSourceType.HISTORICAL_DEMAND)
        if demand and demand.records:
            demands = [
                float(r["demand_mgd"])
                for r in demand.records
                if r.get("demand_mgd") is not None
            ]
            if demands:
                features["demand_mgd_mean"] = sum(demands) / len(demands)
                features["demand_mgd_latest"] = demands[-1]
                features["demand_sample_count"] = len(demands)
                feature_names.extend(
                    ["demand_mgd_mean", "demand_mgd_latest", "demand_sample_count"]
                )

        weather = batches.get(DataSourceType.WEATHER_API)
        if weather and weather.records:
            latest = weather.records[0]
            for key in (
                "temperature_c",
                "humidity_pct",
                "precipitation_mm",
                "rainfall_deficit_pct",
                "evapotranspiration_rate_mm",
            ):
                if latest.get(key) is not None:
                    features[key] = float(latest[key])
                    feature_names.append(key)

        sensors = batches.get(DataSourceType.IOT_SENSORS)
        if sensors and sensors.records:
            features["iot_sensor_count"] = len(sensors.records)
            offline = sum(1 for r in sensors.records if str(r.get("status", "")).lower() != "online")
            features["iot_offline_count"] = offline
            feature_names.extend(["iot_sensor_count", "iot_offline_count"])

        return FeatureSet(
            region_id=region.region_id,
            feature_names=feature_names,
            rows=[features],
            metadata={
                "sources_used": [s.value for s in batches.keys() if batches[s].records],
                "placeholder_sources": [
                    s.value for s in batches.keys() if batches[s].is_placeholder
                ],
            },
        )
