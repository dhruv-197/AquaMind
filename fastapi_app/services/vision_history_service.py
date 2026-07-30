"""AquaLens history — persistence, trend, and before/after comparison.

Previously every AquaLens analysis was fully stateless: the model returned
a JSON blob and nothing was stored, so the module could never say "this
reservoir is degrading" or "here's how this site has changed since your
last scan" — a real gap for a hydrology decision-support tool where a
single snapshot is far less useful than a trend.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from fastapi_app.database.models import VisionAnalysis

NUMERIC_FIELDS = ("reservoir_health", "turbidity_index", "shoreline_exposure_pct", "confidence")


def find_previous_analysis(
    db: Session, *, asset_label: Optional[str], vision_mode: str
) -> Optional[VisionAnalysis]:
    """Most recent prior scan for this asset (or, with no label, the most
    recent scan of the same mode from any asset) to diff the new one against."""
    query = db.query(VisionAnalysis).filter(VisionAnalysis.vision_mode == vision_mode)
    if asset_label:
        query = query.filter(VisionAnalysis.asset_label == asset_label)
    return query.order_by(desc(VisionAnalysis.created_at)).first()


def persist_analysis(
    db: Session,
    *,
    user_id,
    asset_label: Optional[str],
    vision_mode: str,
    result: dict[str, Any],
) -> VisionAnalysis:
    """`user_id` must be the User.id value as-is (a uuid.UUID from the ORM),
    not str(user.id) — the column is a native UUID type and SQLAlchemy's UUID
    processor calls .hex on it, which raises AttributeError on a plain str
    and previously made every persisted scan silently fail (caught by the
    router's broad except, so analysis still "succeeded" but history/trend/
    comparison never worked)."""
    row = VisionAnalysis(
        user_id=user_id,
        asset_label=asset_label,
        vision_mode=vision_mode,
        provider=result.get("provider"),
        reservoir_health=_safe_int(result.get("reservoir_health")),
        water_spread=result.get("water_spread"),
        vegetation=result.get("vegetation"),
        sedimentation=result.get("sedimentation"),
        dry_shoreline=result.get("dry_shoreline"),
        encroachment=result.get("encroachment"),
        water_stress=result.get("water_stress"),
        overall_risk=result.get("overall_risk") or result.get("overall_flood_risk"),
        turbidity_index=_safe_float(result.get("turbidity_index")),
        algae_bloom_risk=result.get("algae_bloom_risk"),
        shoreline_exposure_pct=_safe_float(result.get("shoreline_exposure_pct")),
        confidence=_safe_float(result.get("confidence")),
        summary=result.get("summary"),
        recommendations=result.get("recommendations"),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def build_comparison(previous: Optional[VisionAnalysis], current: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Deltas vs the previous scan of the same asset — the "what changed" view."""
    if previous is None:
        return None

    def _delta(prev_val, cur_val):
        if prev_val is None or cur_val is None:
            return None
        try:
            return round(float(cur_val) - float(prev_val), 2)
        except (TypeError, ValueError):
            return None

    health_delta = _delta(previous.reservoir_health, current.get("reservoir_health"))
    turbidity_delta = _delta(previous.turbidity_index, current.get("turbidity_index"))
    shoreline_delta = _delta(previous.shoreline_exposure_pct, current.get("shoreline_exposure_pct"))

    trend = "stable"
    if health_delta is not None:
        if health_delta >= 5:
            trend = "improving"
        elif health_delta <= -5:
            trend = "degrading"

    return {
        "previous_analyzed_at": previous.created_at.isoformat() if previous.created_at else None,
        "previous_reservoir_health": previous.reservoir_health,
        "reservoir_health_delta": health_delta,
        "turbidity_index_delta": turbidity_delta,
        "shoreline_exposure_pct_delta": shoreline_delta,
        "trend": trend,
        "note": (
            f"Compared against the previous scan on "
            f"{previous.created_at.strftime('%Y-%m-%d') if previous.created_at else 'an earlier date'}"
            + (f" for '{previous.asset_label}'." if previous.asset_label else " (no asset label set — compared against the most recent scan of any site).")
        ),
    }


def list_history(
    db: Session, *, asset_label: Optional[str] = None, vision_mode: Optional[str] = None, limit: int = 20
) -> list[VisionAnalysis]:
    query = db.query(VisionAnalysis)
    if asset_label:
        query = query.filter(VisionAnalysis.asset_label == asset_label)
    if vision_mode:
        query = query.filter(VisionAnalysis.vision_mode == vision_mode)
    return query.order_by(desc(VisionAnalysis.created_at)).limit(min(limit, 100)).all()


def _safe_int(value: Any) -> Optional[int]:
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def _safe_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
