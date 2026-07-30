"""Concrete evaluation metrics for the reservoir model (framework interfaces only)."""
from __future__ import annotations

from typing import Any, Sequence

import numpy as np

from fastapi_app.prediction.framework.evaluation.metrics import (
    EvaluationSuite,
    MAE,
    MAPE,
    MetricResult,
    R2,
    RMSE,
)


class ReservoirMAE(MAE):
    def compute(
        self,
        y_true: Sequence[float],
        y_pred: Sequence[float],
        **kwargs: Any,
    ) -> MetricResult:
        yt = np.asarray(y_true, dtype=float)
        yp = np.asarray(y_pred, dtype=float)
        value = float(np.mean(np.abs(yt - yp))) if len(yt) else None
        return MetricResult(name=self.name, value=value)


class ReservoirRMSE(RMSE):
    def compute(
        self,
        y_true: Sequence[float],
        y_pred: Sequence[float],
        **kwargs: Any,
    ) -> MetricResult:
        yt = np.asarray(y_true, dtype=float)
        yp = np.asarray(y_pred, dtype=float)
        value = float(np.sqrt(np.mean((yt - yp) ** 2))) if len(yt) else None
        return MetricResult(name=self.name, value=value)


class ReservoirMAPE(MAPE):
    def compute(
        self,
        y_true: Sequence[float],
        y_pred: Sequence[float],
        **kwargs: Any,
    ) -> MetricResult:
        yt = np.asarray(y_true, dtype=float)
        yp = np.asarray(y_pred, dtype=float)
        mask = yt != 0
        if not np.any(mask):
            return MetricResult(name=self.name, value=None, details={"warning": "all_zero_targets"})
        value = float(np.mean(np.abs((yt[mask] - yp[mask]) / yt[mask])) * 100.0)
        return MetricResult(name=self.name, value=value, details={"unit": "percent"})


class ReservoirR2(R2):
    def compute(
        self,
        y_true: Sequence[float],
        y_pred: Sequence[float],
        **kwargs: Any,
    ) -> MetricResult:
        yt = np.asarray(y_true, dtype=float)
        yp = np.asarray(y_pred, dtype=float)
        if len(yt) < 2:
            return MetricResult(name=self.name, value=None)
        ss_res = float(np.sum((yt - yp) ** 2))
        ss_tot = float(np.sum((yt - np.mean(yt)) ** 2))
        value = None if ss_tot == 0 else 1.0 - (ss_res / ss_tot)
        return MetricResult(name=self.name, value=value)


def build_reservoir_evaluation_suite() -> EvaluationSuite:
    return EvaluationSuite([ReservoirMAE(), ReservoirRMSE(), ReservoirMAPE(), ReservoirR2()])
