"""Deterministic rule helpers for the rules-based Decision Engine."""
from __future__ import annotations

from fastapi_app.core.contracts import PredictionType, RiskLevel
from fastapi_app.decision_engine.base import ActionPriority, Recommendation, SuggestedAction
from fastapi_app.prediction.base import PredictionOutput


_RISK_RANK = {
    RiskLevel.UNKNOWN: 0,
    RiskLevel.LOW: 1,
    RiskLevel.MODERATE: 2,
    RiskLevel.HIGH: 3,
    RiskLevel.CRITICAL: 4,
}


def max_risk(levels: list[RiskLevel]) -> RiskLevel:
    if not levels:
        return RiskLevel.UNKNOWN
    return max(levels, key=lambda r: _RISK_RANK[r])


def infer_risk_from_prediction(prediction: PredictionOutput) -> RiskLevel:
    """Map placeholder or scored predictions into a RiskLevel."""
    if prediction.risk_level != RiskLevel.UNKNOWN:
        return prediction.risk_level
    if prediction.score is None:
        return RiskLevel.UNKNOWN
    score = float(prediction.score)
    if score >= 80:
        return RiskLevel.CRITICAL
    if score >= 60:
        return RiskLevel.HIGH
    if score >= 35:
        return RiskLevel.MODERATE
    return RiskLevel.LOW


def default_actions_for(prediction: PredictionOutput, risk: RiskLevel) -> list[SuggestedAction]:
    """Policy templates keyed by prediction type — replaceable without ML."""
    pid = prediction.prediction_type.value
    templates: dict[PredictionType, list[tuple[str, str, ActionPriority]]] = {
        PredictionType.WATER_DEMAND: [
            ("Review allocation schedule", "Align supply releases with forecast demand peaks.", ActionPriority.SHORT_TERM),
            ("Demand-side messaging", "Trigger conservation advisories if surge risk rises.", ActionPriority.MONITOR),
        ],
        PredictionType.RESERVOIR: [
            ("Reduce dam release", "Cut releases to conserve storage against the forecast drawdown.", ActionPriority.IMMEDIATE),
            ("Increase groundwater utilization", "Shift a portion of municipal supply to groundwater wells.", ActionPriority.SHORT_TERM),
            ("Activate secondary reservoir", "Bring standby storage online to buffer primary reservoir stress.", ActionPriority.SHORT_TERM),
            ("Issue conservation advisory", "Publish public conservation guidance while storage risk remains elevated.", ActionPriority.MEDIUM_TERM),
        ],
        PredictionType.LEAKAGE_RISK: [
            ("Priority leak survey", "Dispatch DMA inspection to highest-risk zones.", ActionPriority.IMMEDIATE),
            ("Pressure management", "Reduce overnight pressure where risk is elevated.", ActionPriority.SHORT_TERM),
        ],
        PredictionType.WATER_STRESS: [
            ("Increase pumping capacity", "Raise emergency pumping while regional WSI remains elevated.", ActionPriority.IMMEDIATE),
            ("Reduce industrial allocation", "Cut industrial draw to relieve municipal pressure.", ActionPriority.IMMEDIATE),
            ("Increase reservoir release", "Boost releases from primary storage to meet peak demand.", ActionPriority.SHORT_TERM),
            ("Enable secondary reservoir", "Bring standby storage online for the affected service area.", ActionPriority.SHORT_TERM),
            ("Issue conservation advisory", "Publish public conservation guidance for at-risk wards.", ActionPriority.SHORT_TERM),
            ("Activate emergency supply plan", "Trigger contingency tankers / inter-basin transfer protocols.", ActionPriority.IMMEDIATE),
        ],
        PredictionType.FLOOD: [
            ("Flood readiness check", "Verify pump stations and drainage assets are operational.", ActionPriority.IMMEDIATE),
            ("Early warning notice", "Prepare public flood advisories for at-risk catchments.", ActionPriority.SHORT_TERM),
        ],
        PredictionType.DROUGHT: [
            ("Drought contingency activation", "Stage drought plan triggers against forecast index.", ActionPriority.SHORT_TERM),
            ("Source diversification", "Evaluate alternate supply options under prolonged deficit.", ActionPriority.MEDIUM_TERM),
        ],
    }

    selected = templates.get(prediction.prediction_type, [])
    soften = risk in (RiskLevel.UNKNOWN, RiskLevel.LOW)
    # Fusion water-stress outputs remain actionable at LOW (healthy band monitoring only).
    if prediction.prediction_type == PredictionType.WATER_STRESS and risk == RiskLevel.LOW and not prediction.is_placeholder:
        soften = False
        selected = [
            ("Continue monitoring", "WSI is healthy/low — maintain baseline telemetry review.", ActionPriority.MONITOR)
        ]
    if soften:
        # Soften to monitoring when models are not yet wired / risk unknown.
        selected = [
            (t, d, ActionPriority.MONITOR if p != ActionPriority.MONITOR else p)
            for t, d, p in selected[:1]
        ] or [
            (
                "Continue monitoring",
                f"Await trained model for {pid}; maintain baseline telemetry review.",
                ActionPriority.MONITOR,
            )
        ]

    actions: list[SuggestedAction] = []
    for i, (title, desc, priority) in enumerate(selected, start=1):
        actions.append(
            SuggestedAction(
                id=f"{pid}-act-{i}",
                title=title,
                description=desc,
                priority=priority,
                related_prediction=prediction.prediction_type,
                estimated_impact="pending_model_calibration"
                if prediction.is_placeholder
                else None,
            )
        )
    return actions


def recommendation_from_prediction(
    prediction: PredictionOutput, risk: RiskLevel
) -> Recommendation:
    actions = default_actions_for(prediction, risk)
    title_map = {
        PredictionType.WATER_DEMAND: "Demand outlook response",
        PredictionType.RESERVOIR: "Reservoir operations response",
        PredictionType.LEAKAGE_RISK: "Leakage risk response",
        PredictionType.WATER_STRESS: "Water stress response",
        PredictionType.FLOOD: "Flood risk response",
        PredictionType.DROUGHT: "Drought risk response",
    }
    return Recommendation(
        id=f"rec-{prediction.prediction_type.value}",
        title=title_map.get(prediction.prediction_type, "Operational response"),
        rationale=prediction.summary,
        risk_level=risk,
        actions=actions,
        related_predictions=[prediction.prediction_type],
    )
