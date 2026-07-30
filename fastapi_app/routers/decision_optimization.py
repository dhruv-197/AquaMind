"""HTTP API for AI Decision Optimization Engine."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from fastapi_app.core.dependencies import ModelRegistryDep
from fastapi_app.core.security import get_current_user
from fastapi_app.decision_engine.optimization.schemas import (
    DecisionCompareRequest,
    DecisionCompareResponse,
    DecisionRecommendRequest,
    DecisionRecommendResponse,
    DecisionStatusResponse,
)
from fastapi_app.decision_engine.optimization.service import DecisionOptimizationService

router = APIRouter(
    prefix="/api/v1/decision",
    tags=["Decision Optimization"],
    dependencies=[Depends(get_current_user)],
)


def get_decision_optimization_service(
    registry: ModelRegistryDep,
) -> DecisionOptimizationService:
    return DecisionOptimizationService(registry)


DecisionOptDep = Annotated[
    DecisionOptimizationService, Depends(get_decision_optimization_service)
]


@router.get(
    "/status",
    response_model=DecisionStatusResponse,
    summary="Decision optimization readiness and upstream model status",
)
async def decision_status(service: DecisionOptDep):
    data = service.status()
    return DecisionStatusResponse(
        ready=data["ready"],
        module=data["module"],
        module_version=data["module_version"],
        upstream=data.get("upstream") or {},
        message=data.get("message") or "",
    )


@router.post(
    "/recommend",
    response_model=DecisionRecommendResponse,
    summary="Generate ranked operational decisions from prediction outputs",
)
async def decision_recommend(payload: DecisionRecommendRequest, service: DecisionOptDep):
    try:
        data = service.recommend(
            region_id=payload.region_id,
            reservoir_id=payload.reservoir_id,
            horizon_days=payload.horizon_days,
            max_actions=payload.max_actions,
            include_upstream=payload.include_upstream,
        )
        return DecisionRecommendResponse(
            message=data.get("message", "Recommendations generated"),
            data=data,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Decision recommendation failed: {exc}",
        ) from exc


@router.post(
    "/compare",
    response_model=DecisionCompareResponse,
    summary="Compare current strategy vs optimized strategy",
)
async def decision_compare(payload: DecisionCompareRequest, service: DecisionOptDep):
    try:
        data = service.compare(
            region_id=payload.region_id,
            reservoir_id=payload.reservoir_id,
            horizon_days=payload.horizon_days,
            max_actions=payload.max_actions,
            aggressiveness=payload.aggressiveness,
        )
        return DecisionCompareResponse(
            message=data.get("message", "Strategy comparison generated"),
            data=data,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Decision comparison failed: {exc}",
        ) from exc
