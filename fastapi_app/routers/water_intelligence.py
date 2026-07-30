"""Water Intelligence fusion API — shortage, leak, groundwater, demand, climate → WSI."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from fastapi_app.core.security import get_current_user
from fastapi_app.database.connection import get_db
from fastapi_app.schemas import (
    WaterIntelligenceData,
    WaterIntelligenceRequest,
    WaterIntelligenceResponse,
    WaterStressAnalyticsResponse,
    WaterStressIndexData,
)
from fastapi_app.services.model_service import model_service

router = APIRouter(tags=["Water Intelligence Fusion"], dependencies=[Depends(get_current_user)])


def _to_response_data(payload: dict) -> WaterIntelligenceData:
    return WaterIntelligenceData(
        water_stress=WaterStressIndexData(**payload["water_stress"]),
        shortage=payload.get("shortage") or {},
        leak=payload.get("leak") or {},
        groundwater=payload.get("groundwater") or {},
        demand=payload.get("demand") or {},
        climate=payload.get("climate") or {},
        context=payload.get("context"),
    )


@router.get(
    "/analytics/water-stress",
    response_model=WaterStressAnalyticsResponse,
    status_code=status.HTTP_200_OK,
    summary="Live Water Stress Index from DB + local models",
    description=(
        "Builds shortage, leak, groundwater, and demand telemetry from SQLite + sklearn, "
        "then fuses them with weather context into an auditable Water Stress Index (0–100)."
    ),
)
async def get_water_stress(db: Session = Depends(get_db)):
    try:
        payload = model_service.build_water_intelligence(db)
        return WaterStressAnalyticsResponse(data=_to_response_data(payload))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Water stress analytics failed: {exc}",
        ) from exc


@router.post(
    "/predict/water-intelligence",
    response_model=WaterIntelligenceResponse,
    status_code=status.HTTP_200_OK,
    summary="Fused water-intelligence prediction (WSI + component models)",
    description=(
        "Accepts optional overrides for reservoir, climate, leak, groundwater, and demand. "
        "Missing fields are filled from live DB telemetry. Returns component predictions plus "
        "the composite Water Stress Index with transparent weights and top drivers."
    ),
)
async def predict_water_intelligence(
    payload: WaterIntelligenceRequest,
    db: Session = Depends(get_db),
):
    try:
        overrides = {k: v for k, v in payload.model_dump().items() if v is not None}
        result = model_service.build_water_intelligence(db, overrides=overrides)
        return WaterIntelligenceResponse(data=_to_response_data(result))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Water intelligence fusion failed: {exc}",
        ) from exc
