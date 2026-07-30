"""HTTP API for Reservoir Level Forecast."""
from __future__ import annotations

from typing import Annotated

import anyio
from fastapi import APIRouter, Depends, HTTPException, Request, status

from fastapi_app.core.dependencies import ModelRegistryDep
from fastapi_app.core.rate_limit import limiter
from fastapi_app.core.safe_paths import resolve_dataset_path
from fastapi_app.core.security import get_current_user, require_role
from fastapi_app.prediction.models.reservoir.schemas import (
    ReservoirMetricsResponse,
    ReservoirPredictRequest,
    ReservoirPredictResponse,
    ReservoirStatusResponse,
    ReservoirTrainRequest,
    ReservoirTrainResponse,
)
from fastapi_app.prediction.models.reservoir.service import ReservoirLevelForecastService

router = APIRouter(
    prefix="/api/v1/predictions/reservoir",
    tags=["Reservoir Level Forecast"],
    dependencies=[Depends(get_current_user)],
)


def get_reservoir_service(registry: ModelRegistryDep) -> ReservoirLevelForecastService:
    return ReservoirLevelForecastService(registry)


ReservoirServiceDep = Annotated[ReservoirLevelForecastService, Depends(get_reservoir_service)]


@router.post(
    "/train",
    response_model=ReservoirTrainResponse,
    status_code=status.HTTP_200_OK,
    summary="[Admin only] Train the Reservoir Level Forecast model",
    dependencies=[require_role(["admin"])],
)
@limiter.limit("5/minute")
async def train_reservoir_model(
    request: Request,
    payload: ReservoirTrainRequest,
    service: ReservoirServiceDep,
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
                capacity_mcm=payload.capacity_mcm,
                training_parameters=payload.training_parameters,
            )
        )
        return ReservoirTrainResponse(
            message=result["message"],
            trained=result["trained"],
            model_version=result["model_version"],
            metrics=result.get("metrics") or {},
            artifact_uri=result.get("artifact_uri"),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Reservoir model training failed: {exc}",
        ) from exc


@router.post(
    "/predict",
    response_model=ReservoirPredictResponse,
    status_code=status.HTTP_200_OK,
    summary="Predict reservoir storage for a custom horizon (days|weeks|months|years)",
)
async def predict_reservoir(
    payload: ReservoirPredictRequest,
    service: ReservoirServiceDep,
):
    try:
        from fastapi_app.geospatial.service import GeospatialService

        geo = GeospatialService()
        national_asset = None
        ml_reservoir_id = payload.reservoir_id

        if payload.asset_id:
            national_asset, proxy = geo.resolve_forecast_proxy(payload.asset_id)
            if national_asset is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Unknown geospatial asset: {payload.asset_id}",
                )
            ml_reservoir_id = proxy or ml_reservoir_id

        capacity = payload.capacity_mcm
        if capacity is None and national_asset and national_asset.capacity_mcm is not None:
            capacity = float(national_asset.capacity_mcm)

        data = service.predict(
            horizon_days=payload.horizon_days,
            horizons=payload.horizons,
            capacity_mcm=capacity,
            feature_overrides=payload.feature_overrides,
            value=payload.value,
            unit=payload.unit,
            include_history_days=payload.include_history_days,
            reservoir_id=ml_reservoir_id,
        )

        # Overlay national asset identity so UI can stay geospatial-first
        if national_asset is not None:
            data["asset_id"] = national_asset.id
            data["reservoir_id"] = national_asset.id
            data["reservoir_name"] = national_asset.name
            data["state"] = national_asset.state
            data["location_lat"] = national_asset.lat
            data["location_lng"] = national_asset.lng
            data["forecast_proxy_id"] = ml_reservoir_id
            if national_asset.capacity_mcm is not None:
                data["capacity_mcm"] = national_asset.capacity_mcm
            if national_asset.current_storage_pct is not None:
                data["current_storage_pct"] = national_asset.current_storage_pct
                if isinstance(data.get("summary"), dict):
                    data["summary"]["current_storage_pct"] = national_asset.current_storage_pct
            if national_asset.confidence is not None and data.get("confidence_score") is None:
                data["confidence_score"] = national_asset.confidence
            if national_asset.risk_level:
                data["risk_label"] = national_asset.risk_level
                data["risk_level"] = national_asset.risk_level
            data["last_updated"] = national_asset.last_updated

        if not data.get("trained", True) and data.get("message") == "Model not trained":
            return ReservoirPredictResponse(
                success=True,
                message="Model not trained",
                data=data,
            )
        return ReservoirPredictResponse(
            message=data.get("message", "Forecast generated"),
            data=data,
        )
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Reservoir prediction failed: {exc}",
        ) from exc


@router.get(
    "/status",
    response_model=ReservoirStatusResponse,
    summary="Reservoir model training status",
)
async def reservoir_status(service: ReservoirServiceDep):
    data = service.status()
    return ReservoirStatusResponse(
        trained=data["trained"],
        model_name=data["model_name"],
        model_version=data["model_version"],
        last_trained_at=data.get("last_trained_at"),
        backend=data.get("backend"),
        capacity_mcm=data.get("capacity_mcm"),
        supported_horizons=data.get("supported_horizons") or [],
        training_rows=data.get("training_rows"),
        reservoirs=data.get("reservoirs") or [],
        message=data.get("message") or "",
    )


@router.get(
    "/metrics",
    response_model=ReservoirMetricsResponse,
    summary="Last evaluation metrics for the reservoir model",
)
async def reservoir_metrics(service: ReservoirServiceDep):
    data = service.metrics()
    return ReservoirMetricsResponse(
        trained=data["trained"],
        metrics=data.get("metrics") or {},
        message=data.get("message") or "",
    )
