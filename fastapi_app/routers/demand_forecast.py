"""HTTP API for Water Demand Forecast."""
from __future__ import annotations

from typing import Annotated

import anyio
from fastapi import APIRouter, Depends, HTTPException, Request, status

from fastapi_app.core.dependencies import ModelRegistryDep
from fastapi_app.core.rate_limit import limiter
from fastapi_app.core.safe_paths import resolve_dataset_path
from fastapi_app.core.security import get_current_user, require_role
from fastapi_app.prediction.models.water_demand.schemas import (
    DemandMetricsResponse,
    DemandPredictRequest,
    DemandPredictResponse,
    DemandStatusResponse,
    DemandTrainRequest,
    DemandTrainResponse,
)
from fastapi_app.prediction.models.water_demand.service import WaterDemandForecastService

router = APIRouter(
    prefix="/api/v1/predictions/demand",
    tags=["Water Demand Forecast"],
    dependencies=[Depends(get_current_user)],
)


def get_demand_service(registry: ModelRegistryDep) -> WaterDemandForecastService:
    return WaterDemandForecastService(registry)


DemandServiceDep = Annotated[WaterDemandForecastService, Depends(get_demand_service)]


@router.post(
    "/train",
    response_model=DemandTrainResponse,
    status_code=status.HTTP_200_OK,
    summary="[Admin only] Train the Water Demand Forecast model",
    dependencies=[require_role(["admin"])],
)
@limiter.limit("5/minute")
async def train_demand_model(
    request: Request,
    payload: DemandTrainRequest,
    service: DemandServiceDep,
):
    try:
        # Sandbox any caller-supplied path to data/imports/ before it reaches
        # the loader — a training endpoint must never be able to read
        # arbitrary server files (e.g. .env.local).
        safe_dataset_path = (
            str(resolve_dataset_path(payload.dataset_path)) if payload.dataset_path else None
        )
        result = await anyio.to_thread.run_sync(
            lambda: service.train(
                dataset_path=safe_dataset_path,
                use_sample=payload.use_sample,
                validation_split=payload.validation_split,
                random_seed=payload.random_seed,
                model_version=payload.model_version,
                capacity_mgd=payload.capacity_mgd,
                training_parameters=payload.training_parameters,
            )
        )
        return DemandTrainResponse(
            message=result["message"],
            trained=result["trained"],
            model_version=result["model_version"],
            metrics=result.get("metrics") or {},
            artifact_uri=result.get("artifact_uri"),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Demand model training failed: {exc}",
        ) from exc


@router.post(
    "/predict",
    response_model=DemandPredictResponse,
    status_code=status.HTTP_200_OK,
    summary="Predict water demand for a custom horizon (days|weeks|months|years)",
)
async def predict_demand(
    payload: DemandPredictRequest,
    service: DemandServiceDep,
):
    try:
        data = service.predict(
            horizon_days=payload.horizon_days,
            horizons=payload.horizons,
            capacity_mgd=payload.capacity_mgd,
            feature_overrides=payload.feature_overrides,
            value=payload.value,
            unit=payload.unit,
            include_history_days=payload.include_history_days,
        )
        if not data.get("trained", True) and data.get("message") == "Model not trained":
            return DemandPredictResponse(
                success=True,
                message="Model not trained",
                data=data,
            )
        return DemandPredictResponse(message=data.get("message", "Forecast generated"), data=data)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Demand prediction failed: {exc}",
        ) from exc


@router.get(
    "/status",
    response_model=DemandStatusResponse,
    summary="Demand model training status",
)
async def demand_status(service: DemandServiceDep):
    data = service.status()
    return DemandStatusResponse(
        trained=data["trained"],
        model_name=data["model_name"],
        model_version=data["model_version"],
        last_trained_at=data.get("last_trained_at"),
        backend=data.get("backend"),
        capacity_mgd=data.get("capacity_mgd"),
        supported_horizons=data.get("supported_horizons") or [],
        training_rows=data.get("training_rows"),
        message=data.get("message") or "",
    )


@router.get(
    "/metrics",
    response_model=DemandMetricsResponse,
    summary="Last evaluation metrics for the demand model",
)
async def demand_metrics(service: DemandServiceDep):
    data = service.metrics()
    return DemandMetricsResponse(
        trained=data["trained"],
        metrics=data.get("metrics") or {},
        message=data.get("message") or "",
    )
