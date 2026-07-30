"""Persist model inferences to the Prediction audit table."""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session


def persist_prediction(
    db: Optional[Session],
    *,
    model_name: str,
    inputs: dict[str, Any],
    results: dict[str, Any],
    confidence: float | None = None,
    user_id=None,
) -> None:
    """Best-effort write; never raises into the inference path."""
    if db is None:
        return
    try:
        from fastapi_app.database.models import Prediction

        conf = confidence
        if conf is None:
            conf = float(results.get("confidence") or results.get("loss_confidence") or 0.0)
        row = Prediction(
            model_name=model_name,
            input_parameters=inputs,
            prediction_results=results,
            confidence_score=max(0.0, min(1.0, float(conf))),
            run_by_user_id=user_id,
        )
        db.add(row)
        db.commit()
    except Exception as exc:
        try:
            db.rollback()
        except Exception:
            pass
        print(f"[PredictionStore] persist skipped: {exc}")
