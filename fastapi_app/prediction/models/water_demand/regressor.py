"""Isolated regressor backend — XGBoost today, swappable later."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import numpy as np


class DemandRegressorBackend(ABC):
    """Abstraction so WaterDemandForecastModel does not hardcode XGBoost."""

    name: str

    @abstractmethod
    def fit(self, x: np.ndarray, y: np.ndarray, **kwargs: Any) -> DemandRegressorBackend:
        ...

    @abstractmethod
    def predict(self, x: np.ndarray) -> np.ndarray:
        ...

    @abstractmethod
    def get_params(self) -> dict[str, Any]:
        ...


class XGBoostDemandRegressor(DemandRegressorBackend):
    """XGBoost Regressor backend for water demand."""

    name = "xgboost_regressor"

    def __init__(
        self,
        *,
        n_estimators: int = 200,
        max_depth: int = 6,
        learning_rate: float = 0.08,
        subsample: float = 0.9,
        colsample_bytree: float = 0.9,
        random_state: int = 42,
        objective: str = "reg:squarederror",
        n_jobs: int = 2,
        **extra: Any,
    ) -> None:
        self.params = {
            "n_estimators": n_estimators,
            "max_depth": max_depth,
            "learning_rate": learning_rate,
            "subsample": subsample,
            "colsample_bytree": colsample_bytree,
            "random_state": random_state,
            "objective": objective,
            "n_jobs": n_jobs,
            **extra,
        }
        self._model = None

    def _ensure_xgb(self):
        try:
            from xgboost import XGBRegressor
        except ImportError as exc:
            raise ImportError(
                "xgboost is required for Water Demand Forecast. "
                "Install with: pip install xgboost"
            ) from exc
        return XGBRegressor

    def fit(self, x: np.ndarray, y: np.ndarray, **kwargs: Any) -> XGBoostDemandRegressor:
        XGBRegressor = self._ensure_xgb()
        self._model = XGBRegressor(**self.params)
        self._model.fit(x, y, **kwargs)
        return self

    def predict(self, x: np.ndarray) -> np.ndarray:
        if self._model is None:
            raise RuntimeError("XGBoostDemandRegressor is not fitted")
        return np.asarray(self._model.predict(x), dtype=float)

    def get_params(self) -> dict[str, Any]:
        return dict(self.params)

    def __getstate__(self) -> dict[str, Any]:
        return {"params": self.params, "model": self._model, "name": self.name}

    def __setstate__(self, state: dict[str, Any]) -> None:
        self.params = dict(state.get("params") or {})
        self._model = state.get("model")
        self.name = state.get("name", "xgboost_regressor")
