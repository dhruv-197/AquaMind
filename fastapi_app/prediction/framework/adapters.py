"""
Adapters between the ML framework and the Decision Intelligence service layer.

Keeps UniversalPredictionOutput as the model contract while Decision Engine
continues to consume prediction.base.PredictionOutput.
"""
from __future__ import annotations

from typing import Any

from fastapi_app.core.contracts import PredictionType, RegionContext, RiskLevel
from fastapi_app.prediction.base import ForecastPoint, PredictionOutput
from fastapi_app.prediction.framework.schemas.output import UniversalPredictionOutput


_MODEL_NAME_TO_TYPE: dict[str, PredictionType] = {
    "water_demand": PredictionType.WATER_DEMAND,
    "water_demand_forecast": PredictionType.WATER_DEMAND,
    "reservoir_forecast": PredictionType.RESERVOIR,
    "reservoir": PredictionType.RESERVOIR,
    "leakage_risk": PredictionType.LEAKAGE_RISK,
    "water_stress": PredictionType.WATER_STRESS,
    "flood": PredictionType.FLOOD,
    "flood_prediction": PredictionType.FLOOD,
    "drought": PredictionType.DROUGHT,
    "drought_prediction": PredictionType.DROUGHT,
}


def resolve_prediction_type(model_name: str) -> PredictionType:
    key = model_name.strip().lower().replace(" ", "_")
    if key in _MODEL_NAME_TO_TYPE:
        return _MODEL_NAME_TO_TYPE[key]
    # Fallback: try enum value match
    for ptype in PredictionType:
        if ptype.value == key or ptype.value.replace("_forecast", "") == key:
            return ptype
    raise KeyError(f"No PredictionType mapping for model_name={model_name!r}")


def to_decision_output(
    result: UniversalPredictionOutput,
    *,
    region: RegionContext | None = None,
    summary: str | None = None,
) -> PredictionOutput:
    """Map framework output → Decision Engine PredictionOutput."""
    region_id = (region.region_id if region else None) or str(
        result.metadata.get("region_id", "REG-1")
    )
    forecast: list[ForecastPoint] = []
    prediction = result.prediction
    if isinstance(prediction, list):
        for item in prediction:
            if isinstance(item, dict) and "timestamp" in item and "value" in item:
                forecast.append(
                    ForecastPoint(
                        timestamp=str(item["timestamp"]),
                        value=float(item["value"]),
                        unit=str(item.get("unit", "value")),
                        lower_bound=item.get("lower_bound"),
                        upper_bound=item.get("upper_bound"),
                    )
                )
    elif isinstance(prediction, dict) and "forecast" in prediction:
        for item in prediction.get("forecast") or []:
            if isinstance(item, dict):
                forecast.append(
                    ForecastPoint(
                        timestamp=str(item.get("timestamp", "")),
                        value=float(item.get("value", 0.0)),
                        unit=str(item.get("unit", "value")),
                    )
                )

    score: float | None = None
    if isinstance(prediction, (int, float)):
        score = float(prediction)
    elif isinstance(prediction, dict) and "score" in prediction:
        try:
            score = float(prediction["score"])
        except (TypeError, ValueError):
            score = None

    return PredictionOutput(
        prediction_type=resolve_prediction_type(result.model_name),
        region_id=region_id,
        generated_at=result.generated_at,
        horizon_days=result.prediction_horizon,
        risk_level=result.risk_level or RiskLevel.UNKNOWN,
        score=score,
        confidence=result.confidence_score,
        summary=summary
        or str(result.metadata.get("summary") or f"{result.model_name} prediction"),
        forecast=forecast,
        drivers=list(result.metadata.get("drivers") or []),
        metadata={
            "prediction_id": result.prediction_id,
            "model_name": result.model_name,
            "model_version": result.model_version,
            **dict(result.metadata),
        },
        is_placeholder=bool(result.metadata.get("is_placeholder", False)),
    )


def placeholder_universal_output(
    *,
    model_name: str,
    model_version: str = "0.0.0-untrained",
    prediction_horizon: int = 7,
    prediction: Any = None,
    risk_level: RiskLevel = RiskLevel.UNKNOWN,
    metadata: dict[str, Any] | None = None,
) -> UniversalPredictionOutput:
    """Helper for stubs — does not run any model."""
    return UniversalPredictionOutput(
        model_name=model_name,
        model_version=model_version,
        prediction_horizon=prediction_horizon,
        confidence_score=None,
        prediction=prediction if prediction is not None else {},
        risk_level=risk_level,
        metadata={
            "is_placeholder": True,
            "note": "Framework placeholder — ML algorithm not implemented.",
            **(metadata or {}),
        },
    )
