import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from fastapi_app.core.rate_limit import limiter
from fastapi_app.core.security import get_current_user
from fastapi_app.database.connection import get_db
from fastapi_app.database.models import User
from fastapi_app.services import vision_history_service
from fastapi_app.services.vision_service import vision_service

logger = logging.getLogger("aquamind.vision")
router = APIRouter(tags=["AquaLens - Vision Intelligence"], dependencies=[Depends(get_current_user)])


@router.post(
    "/api/vision/analyze",
    status_code=status.HTTP_200_OK,
    summary="Analyze satellite / drone image (reservoir or flood mode)",
    description=(
        "Upload a satellite or drone image. "
        "mode=reservoir (default): reservoir health + shoreline CLIPSeg. "
        "mode=flood: permanent water bodies vs flood inundation (exclusive CLIPSeg masks) "
        "to guide humans away from labelling lakes/rivers as flood. "
        "Optional asset_label tags the scan (e.g. a reservoir name) so future uploads of the "
        "same site are compared against it and a health trend can be tracked over time."
    ),
)
@router.post(
    "/vision/analyze",
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
@limiter.limit("10/minute")
async def analyze_vision_image(
    request: Request,
    file: UploadFile = File(...),
    mode: Optional[str] = Form("reservoir"),
    asset_label: Optional[str] = Form(None, description="Optional site/reservoir name to track over time"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not file:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No image file uploaded.",
        )

    filename = file.filename or "reservoir_image.jpg"
    valid_extensions = (".jpg", ".jpeg", ".png", ".webp", ".tiff", ".bmp")
    if not filename.lower().endswith(valid_extensions):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid image format. Supported formats: JPG, PNG, WEBP, TIFF, BMP.",
        )

    vision_mode = (mode or "reservoir").lower().strip()
    if vision_mode not in {"reservoir", "flood"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid mode. Use 'reservoir' or 'flood'.",
        )
    clean_label = (asset_label or "").strip()[:255] or None

    try:
        file_bytes = await file.read()
        if len(file_bytes) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded image file is empty.",
            )

        result_json = await vision_service.analyze_reservoir_image(
            file_bytes, filename, mode=vision_mode
        )

        # Before/after comparison against this asset's last scan (if any),
        # computed before persisting the new row so it diffs against the
        # prior state, not itself.
        comparison = None
        history_count = 0
        try:
            previous = vision_history_service.find_previous_analysis(
                db, asset_label=clean_label, vision_mode=vision_mode
            )
            comparison = vision_history_service.build_comparison(previous, result_json)
            vision_history_service.persist_analysis(
                db,
                user_id=current_user.id,
                asset_label=clean_label,
                vision_mode=vision_mode,
                result=result_json,
            )
            history_count = len(
                vision_history_service.list_history(
                    db, asset_label=clean_label, vision_mode=vision_mode, limit=100
                )
            )
        except Exception:
            # History is supporting evidence, not a hard dependency — never fail
            # the user's analysis because the trend/store step had a problem.
            # Logged at ERROR (not swallowed as a stray print) — a persistence
            # bug here previously went unnoticed because it never surfaced.
            comparison = None
            history_count = 0
            logger.exception("[AquaLens] history persistence/comparison failed")

        msg = (
            "AquaLens flood inundation analysis completed."
            if vision_mode == "flood"
            else "AquaLens satellite visual analysis completed."
        )

        response_payload = {
            "success": True,
            "message": msg,
            "timestamp": datetime.utcnow().isoformat(),
            "provider": result_json.get("provider", "AquaLens"),
            "analysis_mode": result_json.get("analysis_mode", "vlm"),
            "vision_mode": vision_mode,
            "asset_label": clean_label,
            "comparison": comparison,
            "history_count": history_count,
            **result_json,
            "data": result_json,
        }

        return JSONResponse(content=response_payload, status_code=status.HTTP_200_OK)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e) or "AquaLens image analysis is temporarily unavailable.",
        )


@router.get(
    "/api/vision/history",
    status_code=status.HTTP_200_OK,
    summary="Recent AquaLens scans — trend data for a site or across all uploads",
)
async def vision_history(
    asset_label: Optional[str] = Query(None, description="Filter to one tagged site/reservoir"),
    mode: Optional[str] = Query(None, description="Filter to 'reservoir' or 'flood'"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    rows = vision_history_service.list_history(
        db, asset_label=asset_label, vision_mode=mode, limit=limit
    )
    return {
        "success": True,
        "total": len(rows),
        "history": [
            {
                "id": str(r.id),
                "asset_label": r.asset_label,
                "vision_mode": r.vision_mode,
                "provider": r.provider,
                "reservoir_health": r.reservoir_health,
                "overall_risk": r.overall_risk,
                "turbidity_index": r.turbidity_index,
                "algae_bloom_risk": r.algae_bloom_risk,
                "shoreline_exposure_pct": r.shoreline_exposure_pct,
                "confidence": r.confidence,
                "analyzed_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    }
