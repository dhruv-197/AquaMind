"""Water Intelligence fusion API — shortage, leak, groundwater, demand, climate → WSI."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from fastapi_app.core.ai_fallback import water_intelligence_fixture
from fastapi_app.core.data_quality import normalize_component
from fastapi_app.core.demo_mode import should_use_fixture
from fastapi_app.core.security import get_current_user
from fastapi_app.core.ttl_cache import (
    WI_TTL_SEC,
    cached_threaded,
    stable_key,
    wi_cache,
)
from fastapi_app.database.connection import SessionLocal, get_db
from fastapi_app.schemas import (
    WaterIntelligenceData,
    WaterIntelligenceRequest,
    WaterIntelligenceResponse,
    WaterStressAnalyticsResponse,
)
from fastapi_app.services.model_service import model_service

logger = logging.getLogger("aquamind.water_intelligence")
router = APIRouter(tags=["Water Intelligence Fusion"], dependencies=[Depends(get_current_user)])


def _to_response_data(payload: dict) -> WaterIntelligenceData:
    """Coerce fusion dict → typed contract (extra component keys preserved)."""
    shortage, _ = normalize_component("shortage", payload.get("shortage") or {})
    leak, _ = normalize_component("leak", payload.get("leak") or {})
    groundwater, _ = normalize_component("groundwater", payload.get("groundwater") or {})
    demand, _ = normalize_component("demand", payload.get("demand") or {})
    climate, _ = normalize_component("climate", payload.get("climate") or {})
    return WaterIntelligenceData.model_validate(
        {
            "water_stress": payload["water_stress"],
            "shortage": shortage,
            "leak": leak,
            "groundwater": groundwater,
            "demand": demand,
            "climate": climate,
            "context": payload.get("context"),
            "metadata": payload.get("metadata") or {},
        }
    )


def _build_live_payload() -> dict[str, Any]:
    db = SessionLocal()
    try:
        return model_service.build_water_intelligence(db)
    finally:
        db.close()


def _build_override_payload(overrides: dict[str, Any]) -> dict[str, Any]:
    db = SessionLocal()
    try:
        return model_service.build_water_intelligence(db, overrides=overrides)
    finally:
        db.close()


@router.get(
    "/analytics/water-stress",
    response_model=WaterStressAnalyticsResponse,
    status_code=status.HTTP_200_OK,
    summary="Live Water Stress Index from DB + local models",
    description=(
        "Builds shortage, leak, groundwater, and demand telemetry from SQLite + sklearn, "
        "then fuses them with weather context into an auditable Water Stress Index (0–100). "
        "Responses are cached briefly (~45s); pass force_refresh=true to bypass."
    ),
)
async def get_water_stress(
    force_refresh: bool = Query(False, description="Bypass short-lived WSI cache"),
    _db: Session = Depends(get_db),
):
    try:
        payload = await cached_threaded(
            wi_cache,
            "wi:live",
            _build_live_payload,
            ttl_seconds=WI_TTL_SEC,
            force_refresh=force_refresh,
        )
        return WaterStressAnalyticsResponse(data=_to_response_data(payload))
    except Exception as exc:
        if should_use_fixture(provider_failed=True):
            logger.warning("Water stress fusion failed (%s) — serving the demo fixture.", exc)
            return WaterStressAnalyticsResponse(
                message="Water stress snapshot (captured reference data).",
                data=_to_response_data(water_intelligence_fixture()),
            )
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
        "Missing fields are filled from live DB telemetry. Empty override bodies reuse the "
        "live WSI cache; scenario overrides are keyed separately (~45s TTL)."
    ),
)
async def predict_water_intelligence(payload: WaterIntelligenceRequest):
    try:
        overrides = {
            k: v for k, v in payload.model_dump(exclude_none=True).items() if v is not None
        }
        if not overrides:
            result = await cached_threaded(
                wi_cache,
                "wi:live",
                _build_live_payload,
                ttl_seconds=WI_TTL_SEC,
                force_refresh=False,
            )
        else:
            cache_key = f"wi:ov:{stable_key(overrides)}"
            result = await cached_threaded(
                wi_cache,
                cache_key,
                lambda: _build_override_payload(overrides),
                ttl_seconds=WI_TTL_SEC,
                force_refresh=False,
            )
        return WaterIntelligenceResponse(data=_to_response_data(result))
    except Exception as exc:
        if should_use_fixture(provider_failed=True):
            logger.warning("Water intelligence predict failed (%s) — serving demo fixture.", exc)
            return WaterIntelligenceResponse(
                message="Water intelligence snapshot (captured reference data).",
                data=_to_response_data(water_intelligence_fixture()),
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Water intelligence prediction failed: {exc}",
        ) from exc
