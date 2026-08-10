import io
import logging
from datetime import datetime
from typing import Optional, Tuple

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from fastapi_app.core.demo_mode import ProviderUnavailableError
from fastapi_app.core.rate_limit import limiter
from fastapi_app.core.security import get_current_user
from fastapi_app.database.connection import get_db
from fastapi_app.database.models import User
from fastapi_app.services import vision_history_service
from fastapi_app.services.vision_service import vision_service

logger = logging.getLogger("aquamind.vision")
router = APIRouter(tags=["AquaLens - Vision Intelligence"], dependencies=[Depends(get_current_user)])

# Upload safety limits — validated by decoding pixels, not filename alone.
MAX_UPLOAD_BYTES = 12 * 1024 * 1024  # 12 MB
MAX_IMAGE_PIXELS = 40_000_000  # ~40 MP
MAX_IMAGE_EDGE = 8_192
ALLOWED_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".tiff", ".tif", ".bmp")
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP", "TIFF", "BMP"}


def _validate_image_bytes(file_bytes: bytes) -> Tuple[int, int, str]:
    """Decode and bound-check an upload. Returns (width, height, format)."""
    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded image file is empty.",
        )
    if len(file_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Image exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB upload limit.",
        )
    try:
        from PIL import Image

        Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
        with Image.open(io.BytesIO(file_bytes)) as img:
            img.verify()
        with Image.open(io.BytesIO(file_bytes)) as img:
            width, height = img.size
            fmt = (img.format or "").upper()
            if fmt not in ALLOWED_FORMATS:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Unsupported or corrupt image content. Use JPG, PNG, WEBP, TIFF, or BMP.",
                )
            if width <= 0 or height <= 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Image has invalid dimensions.",
                )
            if width > MAX_IMAGE_EDGE or height > MAX_IMAGE_EDGE:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Image edges must be at most {MAX_IMAGE_EDGE}px.",
                )
            if width * height > MAX_IMAGE_PIXELS:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Image exceeds the maximum pixel budget.",
                )
            return width, height, fmt
    except HTTPException:
        raise
    except Exception:
        logger.info("[AquaLens] rejected upload that failed image decode")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Corrupt or unsupported image. Re-export as JPG or PNG and try again.",
        )


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
    if not filename.lower().endswith(ALLOWED_EXTENSIONS):
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
        file_bytes = await file.read(MAX_UPLOAD_BYTES + 1)
        if len(file_bytes) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Image exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB upload limit.",
            )
        _validate_image_bytes(file_bytes)

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
                db,
                asset_label=clean_label,
                vision_mode=vision_mode,
                user_id=current_user.id,
            )
            comparison = vision_history_service.build_comparison(
                previous,
                result_json,
                asset_label=clean_label,
                vision_mode=vision_mode,
            )
            vision_history_service.persist_analysis(
                db,
                user_id=current_user.id,
                asset_label=clean_label,
                vision_mode=vision_mode,
                result=result_json,
            )
            try:
                from fastapi_app.core.ttl_cache import vision_history_cache

                vision_history_cache.clear()
            except Exception:
                pass
            history_count = vision_history_service.count_history(
                db,
                asset_label=clean_label,
                vision_mode=vision_mode,
                user_id=current_user.id,
            )
        except Exception:
            # History is supporting evidence, not a hard dependency — never fail
            # the user's analysis because the trend/store step had a problem.
            comparison = None
            history_count = 0
            logger.exception("[AquaLens] history persistence/comparison failed")

        if result_json.get("analysis_mode") == "demo_fixture":
            msg = "Showing a captured reference analysis - no vision provider was reachable."
        elif vision_mode == "flood":
            msg = "AquaLens flood inundation analysis completed."
        else:
            msg = "AquaLens satellite visual analysis completed."

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
    except ProviderUnavailableError as e:
        logger.warning(
            "[AquaLens] vision providers unavailable: %s",
            "; ".join(e.provider_errors) or type(e).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AquaLens vision providers are temporarily unavailable. Retry shortly.",
        )
    except Exception:
        logger.exception("[AquaLens] image analysis failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AquaLens image analysis is temporarily unavailable.",
        )


@router.get(
    "/api/vision/history",
    status_code=status.HTTP_200_OK,
    summary="Recent AquaLens scans - trend data for a site or across all uploads",
)
@router.get("/vision/history", include_in_schema=False)
async def vision_history(
    asset_label: Optional[str] = Query(None, description="Filter to one tagged site/reservoir"),
    mode: Optional[str] = Query(None, alias="vision_mode", description="reservoir | flood"),
    limit: int = Query(20, ge=1, le=100),
    force_refresh: bool = Query(False, description="Bypass short-lived history cache"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from fastapi_app.core.ttl_cache import (
        VISION_HISTORY_TTL_SEC,
        set_cache_status,
        stable_key,
        vision_history_cache,
    )

    cache_key = f"vision_hist:{stable_key(str(current_user.id), asset_label, mode, limit)}"
    if not force_refresh:
        cached = vision_history_cache.get(cache_key)
        if cached is not None:
            set_cache_status("HIT")
            return cached

    rows = vision_history_service.list_history(
        db,
        asset_label=asset_label,
        vision_mode=mode,
        user_id=current_user.id,
        limit=limit,
    )
    payload = {
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
    vision_history_cache.set(cache_key, payload, VISION_HISTORY_TTL_SEC)
    set_cache_status("MISS")
    return payload
