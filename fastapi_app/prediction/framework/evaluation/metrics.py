"""
Evaluation framework interfaces.

Concrete metric classes must implement `compute`. No formulas live here.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Sequence

from pydantic import BaseModel, Field


class MetricResult(BaseModel):
    name: str
    value: float | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class EvaluationMetric(ABC):
    """Base contract for a single evaluation metric."""

    name: str

    @abstractmethod
    def compute(
        self,
        y_true: Sequence[float],
        y_pred: Sequence[float],
        **kwargs: Any,
    ) -> MetricResult:
        """Compute the metric. Implementations provide the formula."""


class MAE(EvaluationMetric):
    """Mean Absolute Error interface."""

    name = "mae"

    def compute(
        self,
        y_true: Sequence[float],
        y_pred: Sequence[float],
        **kwargs: Any,
    ) -> MetricResult:
        raise NotImplementedError("MAE.compute is not implemented (interface only)")


class RMSE(EvaluationMetric):
    """Root Mean Squared Error interface."""

    name = "rmse"

    def compute(
        self,
        y_true: Sequence[float],
        y_pred: Sequence[float],
        **kwargs: Any,
    ) -> MetricResult:
        raise NotImplementedError("RMSE.compute is not implemented (interface only)")


class MAPE(EvaluationMetric):
    """Mean Absolute Percentage Error interface."""

    name = "mape"

    def compute(
        self,
        y_true: Sequence[float],
        y_pred: Sequence[float],
        **kwargs: Any,
    ) -> MetricResult:
        raise NotImplementedError("MAPE.compute is not implemented (interface only)")


class R2(EvaluationMetric):
    """Coefficient of determination (R²) interface."""

    name = "r2"

    def compute(
        self,
        y_true: Sequence[float],
        y_pred: Sequence[float],
        **kwargs: Any,
    ) -> MetricResult:
        raise NotImplementedError("R2.compute is not implemented (interface only)")


class CustomMetric(EvaluationMetric):
    """
    Extension point for domain-specific metrics.

    Subclass and set `name`; implement `compute`.
    """

    name = "custom"

    def compute(
        self,
        y_true: Sequence[float],
        y_pred: Sequence[float],
        **kwargs: Any,
    ) -> MetricResult:
        raise NotImplementedError("CustomMetric.compute is not implemented (interface only)")


class EvaluationSuite:
    """
    Injectable collection of metrics.

    Does not compute anything itself beyond delegating to registered metrics.
    """

    def __init__(self, metrics: Sequence[EvaluationMetric] | None = None) -> None:
        self._metrics: list[EvaluationMetric] = list(metrics or [])

    def register(self, metric: EvaluationMetric) -> None:
        self._metrics.append(metric)

    def list_metrics(self) -> list[str]:
        return [m.name for m in self._metrics]

    def evaluate(
        self,
        y_true: Sequence[float],
        y_pred: Sequence[float],
        **kwargs: Any,
    ) -> list[MetricResult]:
        return [m.compute(y_true, y_pred, **kwargs) for m in self._metrics]
