"""Rules-based Decision Engine implementation."""
from __future__ import annotations

from typing import Any

from fastapi_app.core.contracts import RegionContext, RiskLevel
from fastapi_app.decision_engine.base import DecisionEngine, DecisionOutcome
from fastapi_app.decision_engine.rules import (
    infer_risk_from_prediction,
    max_risk,
    recommendation_from_prediction,
)
from fastapi_app.prediction.base import PredictionOutput


class RulesDecisionEngine(DecisionEngine):
    """
    Converts PredictionOutput → Recommendation → Risk Level → Suggested Actions.

    Completely separate from model inference. Scenario knobs can bias risk
    without changing predictors (what-if simulation support).
    """

    async def evaluate(
        self,
        region: RegionContext,
        predictions: list[PredictionOutput],
        scenario: dict[str, Any] | None = None,
    ) -> DecisionOutcome:
        scenario = scenario or {}
        risk_bias = float(scenario.get("risk_bias", 0.0))  # -20 .. +20 what-if shift

        per_prediction_risk: list[RiskLevel] = []
        recommendations = []
        all_actions = []
        summaries: list[dict[str, Any]] = []

        for prediction in predictions:
            risk = infer_risk_from_prediction(prediction)
            if risk_bias and prediction.score is not None:
                adjusted = max(0.0, min(100.0, float(prediction.score) + risk_bias))
                # Re-infer with temporary score
                tmp = prediction.model_copy(update={"score": adjusted, "risk_level": RiskLevel.UNKNOWN})
                risk = infer_risk_from_prediction(tmp)

            per_prediction_risk.append(risk)
            rec = recommendation_from_prediction(prediction, risk)
            recommendations.append(rec)
            all_actions.extend(rec.actions)
            summaries.append(
                {
                    "prediction_type": prediction.prediction_type.value,
                    "risk_level": risk.value,
                    "score": prediction.score,
                    "is_placeholder": prediction.is_placeholder,
                    "summary": prediction.summary,
                }
            )

        overall = max_risk(per_prediction_risk)
        scores = [p.score for p in predictions if p.score is not None]
        overall_score = (sum(scores) / len(scores)) if scores else None
        if overall_score is not None and risk_bias:
            overall_score = max(0.0, min(100.0, overall_score + risk_bias))

        return DecisionOutcome(
            region_id=region.region_id,
            overall_risk_level=overall,
            overall_risk_score=overall_score,
            recommendations=recommendations,
            suggested_actions=all_actions,
            prediction_summaries=summaries,
            metadata={
                "engine": "rules",
                "scenario": scenario,
                "prediction_count": len(predictions),
                "placeholder_count": sum(1 for p in predictions if p.is_placeholder),
            },
        )
