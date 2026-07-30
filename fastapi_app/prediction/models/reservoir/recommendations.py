"""Decision recommendations derived from reservoir prediction outputs."""
from __future__ import annotations

from typing import Any

from fastapi_app.core.contracts import PredictionType, RiskLevel
from fastapi_app.decision_engine.rules import recommendation_from_prediction
from fastapi_app.prediction.framework.adapters import to_decision_output
from fastapi_app.prediction.framework.schemas.output import UniversalPredictionOutput
from fastapi_app.prediction.models.reservoir.constants import CRITICAL_STORAGE_PCT
from fastapi_app.prediction.models.reservoir.risk import risk_display_label


def days_until_critical(forecast_points: list[dict[str, Any]]) -> int | None:
    """First forecast day where storage falls below critical threshold."""
    for p in forecast_points:
        val = p.get("forecast")
        if val is None:
            val = p.get("prediction")
        if val is None:
            continue
        if float(val) < CRITICAL_STORAGE_PCT:
            day = p.get("horizon_day") or p.get("period_index")
            return int(day) if day is not None else None
    return None


def recommendations_bundle(
    *,
    universal: UniversalPredictionOutput,
    forecast_points: list[dict[str, Any]],
    summary: dict[str, Any],
    reservoir_name: str | None = None,
) -> dict[str, Any]:
    """
    Generate operator-facing recommendations from prediction outputs.

    Also produces a Decision Engine Recommendation for integration.
    """
    payload = universal.prediction if isinstance(universal.prediction, dict) else {}
    risk = universal.risk_level
    label = risk_display_label(risk)
    name = (
        reservoir_name
        or payload.get("reservoir_name")
        or payload.get("reservoir_id")
        or "Reservoir"
    )
    days_crit = summary.get("days_to_critical")
    if days_crit is None:
        days_crit = days_until_critical(forecast_points)

    current_pct = float(
        payload.get("forecasted_storage_pct")
        or summary.get("forecasted_storage_pct")
        or 50
    )
    remaining = float(
        payload.get("remaining_usable_storage_mcm")
        or summary.get("remaining_usable_storage_mcm")
        or 0
    )

    texts: list[str] = []
    if days_crit is not None and int(days_crit) > 0:
        texts.append(
            f"{name} expected to reach critical level "
            f"(<{CRITICAL_STORAGE_PCT:.0f}%) in {int(days_crit)} days."
        )
    elif risk == RiskLevel.CRITICAL:
        texts.append(f"{name} is already at critical storage ({current_pct:.1f}%).")

    if risk in (RiskLevel.CRITICAL, RiskLevel.HIGH):
        cut = min(25, max(5, round((40.0 - current_pct) * 0.4)))
        texts.append(f"Reduce release by {cut}%.")
        texts.append("Increase groundwater utilization.")
        texts.append("Activate secondary reservoir.")
        texts.append("Issue conservation advisory.")
    elif risk == RiskLevel.MODERATE:
        texts.append("Tighten release scheduling and monitor inflows weekly.")
        texts.append("Prepare conservation advisory draft for municipal stakeholders.")
    else:
        texts.append(f"{name} operating in healthy band; maintain rule-curve releases.")
        texts.append(
            f"Remaining usable storage ≈ {remaining:.1f} MCM above critical threshold."
        )

    decision_po = to_decision_output(
        universal,
        summary=texts[0] if texts else str(universal.metadata.get("summary") or ""),
    )
    stress = max(0.0, 100.0 - current_pct)
    decision_po = decision_po.model_copy(
        update={
            "score": stress,
            "risk_level": risk,
            "is_placeholder": False,
            "summary": texts[0] if texts else decision_po.summary,
        }
    )
    engine_rec = recommendation_from_prediction(decision_po, risk)

    exec_recs = [
        {
            "id": f"exec-{i}",
            "text": t,
            "priority": (
                "immediate"
                if risk == RiskLevel.CRITICAL
                else "short_term"
                if risk == RiskLevel.HIGH
                else "monitor"
            ),
            "risk_level": risk.value,
            "risk_label": label,
        }
        for i, t in enumerate(texts, start=1)
    ]

    return {
        "executive_recommendations": exec_recs,
        "decision_engine": {
            "recommendation": engine_rec.model_dump(mode="json"),
            "prediction": decision_po.model_dump(mode="json"),
            "prediction_type": PredictionType.RESERVOIR.value,
        },
    }
