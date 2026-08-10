"""Climate Risk Intelligence API — grounded Open-Meteo / GloFAS analytics."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from fastapi_app.core.security import get_current_user
from fastapi_app.schemas import ClimateRiskAnalyzeBody, ClimateRiskResponse
from fastapi_app.services import climate_risk_service as svc

router = APIRouter(
    prefix="/climate-risk",
    tags=["Climate Risk Intelligence"],
    dependencies=[Depends(get_current_user)],
)


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


@router.post(
    "/analyze",
    summary="Analyze climate + flood + waterlogging risk",
    response_model=ClimateRiskResponse,
    response_model_exclude_none=False,
)
async def analyze(body: ClimateRiskAnalyzeBody):
    try:
        payload = await svc.analyze_location(
            lat=body.lat,
            lon=body.lon,
            label=body.label,
            land_class=body.land_class,
        )
        # Validate/normalize envelope without dropping unknown nested keys.
        return ClimateRiskResponse.model_validate({**payload, "success": True})
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Climate risk upstream is temporarily unavailable.",
        ) from exc
