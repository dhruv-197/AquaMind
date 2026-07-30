"""API schemas for Water Stress Intelligence endpoints."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class StressScenario(BaseModel):
    rainfall_delta_pct: Optional[float] = Field(
        default=None, description="Rainfall change % (negative = drier)"
    )
    population_delta_pct: Optional[float] = Field(
        default=None, description="Population change %"
    )
    demand_delta_pct: Optional[float] = Field(
        default=None, description="Demand change %"
    )
    temperature_delta_c: Optional[float] = Field(
        default=None, description="Temperature change °C"
    )
    reservoir_delta_pct: Optional[float] = Field(
        default=None, description="Reservoir storage change in percentage points"
    )
    reservoir_level_pct: Optional[float] = Field(
        default=None, description="Absolute reservoir storage % override"
    )
    reservoir_id: Optional[str] = None


class StressPredictRequest(BaseModel):
    region_id: Optional[str] = Field(default=None, description="Target region id")
    region_type: Optional[Literal["ward", "district", "zone", "municipality"]] = None
    horizon_days: int = Field(default=30, ge=1, le=365)
    reservoir_id: Optional[str] = None
    scenario: Optional[StressScenario] = None
    include_all_regions: bool = Field(
        default=True, description="Include map payload for all regions"
    )


class StressSimulateRequest(BaseModel):
    region_id: Optional[str] = None
    horizon_days: int = Field(default=30, ge=1, le=365)
    reservoir_id: Optional[str] = None
    scenario: StressScenario = Field(default_factory=StressScenario)
    preset_id: Optional[str] = Field(
        default=None, description="Optional what-if preset id"
    )
    include_all_regions: bool = True


class StressPredictResponse(BaseModel):
    success: bool = True
    message: str
    data: dict[str, Any]


class StressStatusResponse(BaseModel):
    success: bool = True
    ready: bool
    module: str
    module_version: str
    upstream: dict[str, Any] = Field(default_factory=dict)
    regions: list[dict[str, Any]] = Field(default_factory=list)
    what_if_presets: list[dict[str, Any]] = Field(default_factory=list)
    message: str = ""
