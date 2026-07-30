"""Climate Risk Intelligence API — grounded Open-Meteo / GloFAS analytics."""
from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from fastapi_app.core.security import get_current_user
from fastapi_app.services import climate_risk_service as svc

router = APIRouter(
    prefix="/climate-risk",
    tags=["Climate Risk Intelligence"],
    dependencies=[Depends(get_current_user)],
)


class ClimateRiskAnalyzeRequest(BaseModel):
    lat: float = Field(..., ge=-90, le=90, description="WGS84 latitude")
    lon: float = Field(..., ge=-180, le=180, description="WGS84 longitude")
    label: Optional[str] = Field(None, max_length=120)
    land_class: Literal["urban", "peri_urban", "agricultural", "rural"] = "urban"


@router.get("/presets", summary="Preset analysis locations")
async def presets():
    return {
        "success": True,
        "presets": svc.list_presets(),
        "notes": (
            "Coordinates are centroids for demo basins/cities. "
            "All climate/flood metrics are fetched live from Open-Meteo / GloFAS."
        ),
    }


@router.get("/health", summary="Upstream Open-Meteo reachability")
async def climate_health():
    result = await svc.health_check()
    return {"success": True, **result}


@router.post("/analyze", summary="Analyze climate + flood + waterlogging risk")
async def analyze(body: ClimateRiskAnalyzeRequest):
    try:
        return await svc.analyze_location(
            lat=body.lat,
            lon=body.lon,
            label=body.label,
            land_class=body.land_class,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Climate risk upstream failure: {exc}",
        ) from exc
