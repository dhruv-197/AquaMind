"""Shared domain contracts used across architecture layers."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    """Normalized risk taxonomy shared by prediction outputs and decisions."""

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class PredictionType(str, Enum):
    WATER_DEMAND = "water_demand_forecast"
    RESERVOIR = "reservoir_forecast"
    LEAKAGE_RISK = "leakage_risk"
    WATER_STRESS = "water_stress"
    FLOOD = "flood"
    DROUGHT = "drought"


class DataSourceType(str, Enum):
    HISTORICAL_RESERVOIR = "historical_reservoir"
    HISTORICAL_DEMAND = "historical_demand"
    WEATHER_API = "weather_api"
    IOT_SENSORS = "iot_sensors"
    GIS = "gis"
    MAINTENANCE_LOGS = "maintenance_logs"
    POPULATION = "population"
    SATELLITE = "satellite"


class TimeWindow(BaseModel):
    """Inclusive time window for historical pulls and forecast horizons."""

    start: datetime
    end: datetime


class RegionContext(BaseModel):
    """Geographic / operational scope for pipeline requests."""

    region_id: str = "REG-1"
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    zone: Optional[str] = None


class PipelineRequest(BaseModel):
    """Common request envelope flowing Data → Processing → Prediction → Decision."""

    region: RegionContext = Field(default_factory=RegionContext)
    horizon_days: int = Field(default=7, ge=1, le=365)
    as_of: datetime = Field(default_factory=datetime.utcnow)
    options: dict[str, Any] = Field(default_factory=dict)
