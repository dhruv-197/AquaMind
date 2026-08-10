"""Authenticated recommendation feedback (accept / reject / defer)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from fastapi_app.core.rate_limit import limiter
from fastapi_app.core.security import get_current_user
from fastapi_app.database.connection import get_db
from fastapi_app.database.models import RecommendationFeedback, User
from fastapi import Request

router = APIRouter(
    prefix="/api/v1/recommendations",
    tags=["Recommendation Feedback"],
    dependencies=[Depends(get_current_user)],
)

ALLOWED_ACTIONS = frozenset({"accepted", "rejected", "deferred"})


class FeedbackRequest(BaseModel):
    recommendation_id: str = Field(..., min_length=1, max_length=120)
    action: Literal["accepted", "rejected", "deferred"]
    note: Optional[str] = Field(None, max_length=1000)
    source: Optional[str] = Field(None, max_length=40)
    region_id: Optional[str] = Field(None, max_length=100)


class FeedbackItem(BaseModel):
    recommendation_id: str
    action: str
    note: Optional[str] = None
    source: Optional[str] = None
    region_id: Optional[str] = None
    updated_at: str
    persisted: bool = True


@router.post(
    "/feedback",
    status_code=status.HTTP_200_OK,
    summary="Record accept / reject / defer for a recommendation (idempotent upsert)",
)
@limiter.limit("60/minute")
async def upsert_feedback(
    request: Request,
    payload: FeedbackRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    action = payload.action.lower().strip()
    if action not in ALLOWED_ACTIONS:
        raise HTTPException(status_code=400, detail="Invalid feedback action.")

    rec_id = payload.recommendation_id.strip()
    if not rec_id:
        raise HTTPException(status_code=400, detail="recommendation_id is required.")

    note = (payload.note or "").strip() or None
    source = (payload.source or "").strip() or None
    region_id = (payload.region_id or "").strip() or None

    row = (
        db.query(RecommendationFeedback)
        .filter(
            RecommendationFeedback.user_id == current_user.id,
            RecommendationFeedback.recommendation_id == rec_id,
        )
        .first()
    )
    now = datetime.utcnow()
    if row is None:
        row = RecommendationFeedback(
            user_id=current_user.id,
            recommendation_id=rec_id,
            action=action,
            note=note,
            source=source,
            region_id=region_id,
            created_at=now,
            updated_at=now,
        )
        db.add(row)
        created = True
    else:
        row.action = action
        row.note = note
        row.source = source
        row.region_id = region_id
        row.updated_at = now
        created = False

    try:
        db.commit()
        db.refresh(row)
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to save recommendation feedback.",
        )

    return {
        "success": True,
        "message": "Feedback saved." if created else "Feedback updated.",
        "data": FeedbackItem(
            recommendation_id=row.recommendation_id,
            action=row.action,
            note=row.note,
            source=row.source,
            region_id=row.region_id,
            updated_at=row.updated_at.isoformat() if row.updated_at else now.isoformat(),
            persisted=True,
        ).model_dump(),
        # Explicit: recording intent is not a measured outcome.
        "disclaimer": "Feedback records operator intent only. Measured savings are not claimed.",
    }


@router.get(
    "/feedback",
    status_code=status.HTTP_200_OK,
    summary="List the current user's recommendation feedback",
)
async def list_feedback(
    recommendation_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(RecommendationFeedback).filter(
        RecommendationFeedback.user_id == current_user.id
    )
    if recommendation_id:
        query = query.filter(RecommendationFeedback.recommendation_id == recommendation_id.strip())
    rows = query.order_by(RecommendationFeedback.updated_at.desc()).limit(200).all()
    return {
        "success": True,
        "data": [
            FeedbackItem(
                recommendation_id=r.recommendation_id,
                action=r.action,
                note=r.note,
                source=r.source,
                region_id=r.region_id,
                updated_at=r.updated_at.isoformat() if r.updated_at else "",
                persisted=True,
            ).model_dump()
            for r in rows
        ],
    }
