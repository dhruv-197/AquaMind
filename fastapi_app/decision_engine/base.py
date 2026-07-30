"""Decision Engine contracts — intentionally separate from prediction models."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

from fastapi_app.core.contracts import PredictionType, RiskLevel, RegionContext
from fastapi_app.prediction.base import PredictionOutput


class ActionPriority(str, Enum):
    IMMEDIATE = "immediate"
    SHORT_TERM = "short_term"
    MEDIUM_TERM = "medium_term"
    MONITOR = "monitor"


class SuggestedAction(BaseModel):
    id: str
    title: str
    description: str
    priority: ActionPriority
    owner_role: str = "operations"
    estimated_impact: Optional[str] = None
    related_prediction: Optional[PredictionType] = None


class Recommendation(BaseModel):
    id: str
    title: str
    rationale: str
    risk_level: RiskLevel
    actions: list[SuggestedAction] = Field(default_factory=list)
    related_predictions: list[PredictionType] = Field(default_factory=list)


class DecisionOutcome(BaseModel):
    """
    Prediction → Recommendation → Risk Level → Suggested Actions

    This is the Decision Engine's public contract for the Dashboard API.
    """

    region_id: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    overall_risk_level: RiskLevel = RiskLevel.UNKNOWN
    overall_risk_score: Optional[float] = None
    recommendations: list[Recommendation] = Field(default_factory=list)
    suggested_actions: list[SuggestedAction] = Field(default_factory=list)
    prediction_summaries: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DecisionEngine(ABC):
    """Separate service: never embeds model math — only policy/decision logic."""

    @abstractmethod
    async def evaluate(
        self,
        region: RegionContext,
        predictions: list[PredictionOutput],
        scenario: dict[str, Any] | None = None,
    ) -> DecisionOutcome:
        """Convert prediction outputs into actionable decisions."""
