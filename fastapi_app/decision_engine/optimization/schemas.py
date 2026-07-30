"""Schemas for Decision Optimization APIs."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


DecisionType = Literal[
    "water_allocation",
    "pump_scheduling",
    "reservoir_release",
    "conservation_advisory",
    "emergency_response",
    "infrastructure_priority",
    "maintenance_priority",
]

TimelineBucket = Literal["today", "next_7_days", "next_30_days", "next_6_months"]


class DecisionRecommendRequest(BaseModel):
    region_id: Optional[str] = Field(default=None, description="Optional stress/GIS region id")
    reservoir_id: Optional[str] = None
    horizon_days: int = Field(default=30, ge=1, le=365)
    max_actions: int = Field(default=12, ge=1, le=30)
    include_upstream: bool = True


class DecisionCompareRequest(BaseModel):
    region_id: Optional[str] = None
    reservoir_id: Optional[str] = None
    horizon_days: int = Field(default=30, ge=1, le=365)
    max_actions: int = Field(default=8, ge=1, le=20)
    # Optional strategy knobs for the "optimized" side
    aggressiveness: float = Field(
        default=1.0,
        ge=0.5,
        le=1.5,
        description="Scale estimated benefits of the optimized strategy",
    )


class DecisionRecommendResponse(BaseModel):
    success: bool = True
    message: str
    data: dict[str, Any]


class DecisionCompareResponse(BaseModel):
    success: bool = True
    message: str
    data: dict[str, Any]


class DecisionStatusResponse(BaseModel):
    success: bool = True
    ready: bool
    module: str
    module_version: str
    upstream: dict[str, Any] = Field(default_factory=dict)
    message: str = ""
