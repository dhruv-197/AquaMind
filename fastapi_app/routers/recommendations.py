from fastapi import APIRouter, Depends, Query, HTTPException, Request, status
from sqlalchemy.orm import Session
from typing import Any, Optional

from fastapi_app.core.ai_fallback import recommendation_fixture_result
from fastapi_app.core.demo_mode import should_use_fixture
from fastapi_app.core.rate_limit import limiter
from fastapi_app.core.security import get_current_user
from fastapi_app.core.ttl_cache import (
    RECOMMENDATION_TTL_SEC,
    cached_threaded,
    recommendation_cache,
    run_in_thread,
)
from fastapi_app.database.connection import SessionLocal, get_db
from fastapi_app.schemas import (
    RecommendationRequest, RecommendationResponse, RecommendationData, RecommendationItem,
    AIRecommendationEngineRequest, AIRecommendationEngineResponse, AIRecommendationEngineData
)
from fastapi_app.services.model_service import model_service

router = APIRouter(tags=["Executive AI Policy Recommendations"], dependencies=[Depends(get_current_user)])


def _synthesize_live(force_refresh: bool = False) -> dict[str, Any]:
    """Dedicated session — safe to run off the event loop."""
    db = SessionLocal()
    try:
        return model_service.synthesize_live_recommendations(db, force_refresh=force_refresh)
    finally:
        db.close()


async def _cached_live_recommendations(force_refresh: bool = False) -> dict[str, Any]:
    return await cached_threaded(
        recommendation_cache,
        "rec:live",
        lambda: _synthesize_live(force_refresh=force_refresh),
        ttl_seconds=RECOMMENDATION_TTL_SEC,
        force_refresh=force_refresh,
    )


def _items_from_engine(result: dict, region_id: str) -> list[RecommendationItem]:
    """Map Gemini/rules bullet list into RecommendationItem cards."""
    bullets = result.get("recommendations") or []
    priorities = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    categories = ["EMERGENCY", "INFRASTRUCTURE", "ALLOCATION", "CONSERVATION"]
    items: list[RecommendationItem] = []
    for i, text in enumerate(bullets[:6]):
        title = str(text).split(".")[0][:72] or f"Action {i + 1}"
        items.append(
            RecommendationItem(
                id=f"AI-REC-{region_id}-{i + 1}",
                priority=priorities[min(i, len(priorities) - 1)],
                category=categories[min(i, len(categories) - 1)],
                title=title,
                action_description=str(text),
                estimated_impact=str(result.get("expected_saving") or "n/a"),
                target_sector="Municipal Operations",
            )
        )
    return items


def _policy_from_result(result: dict) -> list[str]:
    source = result.get("source") or "unknown"
    provider = result.get("provider") or "n/a"
    return [
        f"Synthesis source: {source} ({provider}).",
        "Actions derived from shortage, leak, groundwater, and demand model telemetry.",
        "Gemini calls are cached (~1h) to conserve API quota; Refresh bypasses cache.",
    ]


@router.get(
    "/recommendation",
    response_model=RecommendationResponse,
    status_code=status.HTTP_200_OK,
    summary="Live Gemini/model recommendations (cached)",
)
@limiter.limit("30/minute")
async def get_recommendation(
    request: Request,
    region_id: Optional[str] = Query("REG-1", description="Region ID filter"),
    shortage_stage: Optional[int] = Query(1, ge=0, le=3, description="Shortage stage level"),
    force_refresh: bool = Query(False, description="Bypass recommendation cache"),
    _db: Session = Depends(get_db),
):
    try:
        result = await _cached_live_recommendations(force_refresh=force_refresh)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Recommendation synthesis failed.",
        )

    items = _items_from_engine(result, region_id or "REG-1")
    risk = float(
        (result.get("inputs") or {})
        .get("shortage", {})
        .get("predicted_risk_score", 50)
    )
    health = max(15.0, min(95.0, 100.0 - risk))
    if shortage_stage and shortage_stage >= 2:
        health = min(health, 48.0)

    return RecommendationResponse(
        data=RecommendationData(
            region_id=region_id or "REG-1",
            overall_health_index=round(health, 1),
            recommendations=items,
            policy_guidelines=_policy_from_result(result),
        )
    )


@router.post(
    "/recommendation",
    response_model=RecommendationResponse,
    status_code=status.HTTP_200_OK,
    summary="Live Gemini/model recommendations (POST)",
)
@limiter.limit("30/minute")
async def post_recommendation(
    request: Request,
    payload: RecommendationRequest,
    _db: Session = Depends(get_db),
):
    region_id = payload.region_id or "REG-1"
    force = bool(getattr(payload, "force_refresh", False))
    try:
        result = await _cached_live_recommendations(force_refresh=force)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Recommendation synthesis failed.",
        )

    risk = float(
        (result.get("inputs") or {})
        .get("shortage", {})
        .get("predicted_risk_score", 50)
    )
    wsi = (result.get("water_stress") or {}).get("water_stress_index")
    if wsi is not None:
        health = max(15.0, min(95.0, 100.0 - float(wsi)))
    else:
        health = max(15.0, min(95.0, 100.0 - risk))

    return RecommendationResponse(
        data=RecommendationData(
            region_id=region_id,
            overall_health_index=round(health, 1),
            recommendations=_items_from_engine(result, region_id),
            policy_guidelines=_policy_from_result(result),
        )
    )


@router.post(
    "/ai/recommendation-engine",
    response_model=AIRecommendationEngineResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate AI recommendations from prediction telemetry",
)
@limiter.limit("20/minute")
async def generate_ai_recommendations(request: Request, payload: AIRecommendationEngineRequest):
    try:
        result = await run_in_thread(
            model_service.generate_recommendations,
            payload.water_shortage_prediction,
            payload.leak_detection,
            payload.groundwater_prediction,
            payload.water_demand,
            bool(getattr(payload, "force_refresh", False)),
        )
        return AIRecommendationEngineResponse(
            data=AIRecommendationEngineData(
                recommendations=result.get("recommendations", []),
                expected_saving=result.get("expected_saving", "0.0 Liters"),
                text_summary=result.get("text_summary", ""),
                source=result.get("source"),
                provider=result.get("provider"),
                metadata=result.get("metadata"),
            )
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI recommendation generation failed.",
        ) from e


@router.get(
    "/ai/recommendation-engine/live",
    response_model=AIRecommendationEngineResponse,
    status_code=status.HTTP_200_OK,
    summary="Auto-build telemetry from models/DB then synthesize with Gemini",
)
@limiter.limit("20/minute")
async def live_ai_recommendations(
    request: Request,
    force_refresh: bool = Query(False, description="Bypass cache and call Gemini again"),
    _db: Session = Depends(get_db),
):
    try:
        try:
            result = await _cached_live_recommendations(force_refresh=force_refresh)
        except Exception:
            # Telemetry itself could not be built (no DB, no models), so even the
            # rules engine has nothing to work from. The report modal is waiting
            # on this call, so in demo mode answer with the captured set.
            if not should_use_fixture(provider_failed=True):
                raise
            result = recommendation_fixture_result()
        return AIRecommendationEngineResponse(
            data=AIRecommendationEngineData(
                recommendations=result.get("recommendations", []),
                expected_saving=result.get("expected_saving", "0.0 Liters"),
                text_summary=result.get("text_summary", ""),
                source=result.get("source"),
                provider=result.get("provider"),
                inputs=result.get("inputs"),
                metadata=result.get("metadata"),
            )
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Live recommendation synthesis failed.",
        ) from e
