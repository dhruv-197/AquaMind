"""HTTP API for Water Stress Intelligence (multi-model fusion)."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from fastapi_app.core.dependencies import ModelRegistryDep
from fastapi_app.core.security import get_current_user
from fastapi_app.prediction.models.water_stress.schemas import (
    StressPredictRequest,
    StressPredictResponse,
    StressSimulateRequest,
    StressStatusResponse,
)
from fastapi_app.prediction.models.water_stress.service import WaterStressIntelligenceService

router = APIRouter(
    prefix="/api/v1/predictions/stress",
    tags=["Water Stress Intelligence"],
    dependencies=[Depends(get_current_user)],
)


def get_stress_service(registry: ModelRegistryDep) -> WaterStressIntelligenceService:
    return WaterStressIntelligenceService(registry)


StressServiceDep = Annotated[WaterStressIntelligenceService, Depends(get_stress_service)]


@router.get(
    "/status",
    response_model=StressStatusResponse,
    summary="Water Stress fusion readiness and upstream model status",
)
async def stress_status(service: StressServiceDep):
    data = service.status()
    return StressStatusResponse(
        ready=data["ready"],
        module=data["module"],
        module_version=data["module_version"],
        upstream=data.get("upstream") or {},
        regions=data.get("regions") or [],
        what_if_presets=data.get("what_if_presets") or [],
        message=data.get("message") or "",
    )


@router.post(
    "/predict",
    response_model=StressPredictResponse,
    summary="Fuse upstream forecasts into a regional Water Stress Index",
)
async def predict_stress(payload: StressPredictRequest, service: StressServiceDep):
    try:
        data = service.predict(
            region_id=payload.region_id,
            region_type=payload.region_type,
            horizon_days=payload.horizon_days,
            reservoir_id=payload.reservoir_id,
            scenario=payload.scenario.model_dump(exclude_none=True) if payload.scenario else None,
            include_all_regions=payload.include_all_regions,
        )
        return StressPredictResponse(message=data.get("message", "Forecast generated"), data=data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Water stress prediction failed: {exc}",
        ) from exc


@router.post(
    "/simulate",
    response_model=StressPredictResponse,
    summary="What-if scenario simulation for Water Stress Index",
)
async def simulate_stress(payload: StressSimulateRequest, service: StressServiceDep):
    try:
        data = service.simulate(
            region_id=payload.region_id,
            horizon_days=payload.horizon_days,
            reservoir_id=payload.reservoir_id,
            scenario=payload.scenario.model_dump(exclude_none=True),
            preset_id=payload.preset_id,
            include_all_regions=payload.include_all_regions,
        )
        return StressPredictResponse(message=data.get("message", "Scenario simulated"), data=data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Water stress simulation failed: {exc}",
        ) from exc
