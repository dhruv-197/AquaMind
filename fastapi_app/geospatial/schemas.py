"""Pydantic schemas for national water assets."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class AssetType(str, Enum):
    reservoir = "reservoir"
    dam = "dam"
    groundwater_station = "groundwater_station"
    demand_region = "demand_region"
    water_stress_region = "water_stress_region"
    leak_zone = "leak_zone"


class WaterAsset(BaseModel):
    id: str
    type: AssetType
    name: str
    state: str | None = None
    lat: float
    lng: float
    capacity_mcm: float | None = None
    current_storage_pct: float | None = None
    forecast_storage_pct: float | None = None
    risk_level: str | None = None
    confidence: float | None = None
    last_updated: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)


class WaterAssetsResponse(BaseModel):
    success: bool = True
    version: str
    updated_at: str | None = None
    counts: dict[str, int] = Field(default_factory=dict)
    total: int
    assets: list[WaterAsset]
    message: str = "ok"
