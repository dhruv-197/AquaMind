"""
Water Demand Forecast model — BaseModelPredictor implementation.

Uses an injected DemandRegressorBackend (XGBoost by default).
Does not modify the prediction framework.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Optional

import numpy as np
import pandas as pd

from fastapi_app.core.contracts import RiskLevel
from fastapi_app.prediction.framework.datasets.base import (
    PredictionDataset,
    TrainingDataset,
)
from fastapi_app.prediction.framework.lifecycle.predictor import BaseModelPredictor
from fastapi_app.prediction.framework.logging.hooks import PredictionLogger
from fastapi_app.prediction.framework.persistence.store import ModelPersistence
from fastapi_app.prediction.framework.schemas.config import TrainingConfiguration
from fastapi_app.prediction.framework.schemas.output import UniversalPredictionOutput
from fastapi_app.prediction.models.water_demand.constants import (
    DEFAULT_CAPACITY_MGD,
    HORIZONS,
    MODEL_KEY,
    MODEL_VERSION,
)
from fastapi_app.prediction.models.water_demand.dataset import DemandDatasetLoader
from fastapi_app.prediction.models.water_demand.features import DemandFeaturePipelineBuilder
from fastapi_app.prediction.models.water_demand.metrics import build_demand_evaluation_suite
from fastapi_app.prediction.models.water_demand.regressor import (
    DemandRegressorBackend,
    XGBoostDemandRegressor,
)
from fastapi_app.prediction.models.water_demand.risk import demand_risk_level, risk_display_label


class WaterDemandForecastModel(BaseModelPredictor):
    """Production water-demand forecaster plugged into ModelRegistry as `water_demand`."""

    def __init__(
        self,
        *,
        regressor: DemandRegressorBackend | None = None,
        persistence: ModelPersistence | None = None,
        logger: PredictionLogger | None = None,
        capacity_mgd: float = DEFAULT_CAPACITY_MGD,
        model_version: str = MODEL_VERSION,
        config: TrainingConfiguration | None = None,
    ) -> None:
        cfg = config or TrainingConfiguration(
            model_name=MODEL_KEY,
            model_version=model_version,
            forecast_horizon=7,
            validation_split=0.2,
            random_seed=42,
            feature_list=[],
            training_parameters={},
        )
        super().__init__(
            model_name=MODEL_KEY,
            model_version=model_version,
            config=cfg,
            feature_pipeline=None,
            persistence=persistence,
            logger=logger or PredictionLogger(model_name=MODEL_KEY),
        )
        self.regressor: DemandRegressorBackend = regressor or XGBoostDemandRegressor(
            random_state=cfg.random_seed
        )
        self.feature_builder = DemandFeaturePipelineBuilder()
        self.dataset_loader = DemandDatasetLoader()
        self.capacity_mgd = float(capacity_mgd)
        self.last_trained_at: datetime | None = None
        self.last_metrics: dict[str, Any] = {}
        self._history: pd.DataFrame = pd.DataFrame()
        self._active_features: list[str] = []

    # ------------------------------------------------------------------
    # Framework hooks
    # ------------------------------------------------------------------
    def _train(self, dataset: TrainingDataset, config: TrainingConfiguration) -> dict[str, Any]:
        raw = dataset.frame.copy()
        if "date" not in raw.columns or "demand_mgd" not in raw.columns:
            # Allow TrainingDataset built from already-cleaned demand frames
            raise ValueError("Training data must include 'date' and 'demand_mgd' columns")

        cleaned = self.dataset_loader.validate_and_clean(raw, source=dataset.metadata.source or "training")
        pipeline = self.feature_builder.fit(cleaned)
        self.feature_pipeline = pipeline
        featured = pipeline.transform(cleaned)

        active = list(self.feature_builder.active_features)
        if not active:
            raise RuntimeError("No usable features after pipeline fit")

        # Drop rows with NaN in active features (early lags)
        model_frame = featured.dropna(subset=active + ["demand_mgd"]).reset_index(drop=True)
        if len(model_frame) < 30:
            raise RuntimeError(f"Insufficient rows after feature engineering: {len(model_frame)}")

        x = model_frame[active].astype(float).to_numpy()
        y = model_frame["demand_mgd"].astype(float).to_numpy()

        split = float(config.validation_split)
        split = min(max(split, 0.05), 0.4)
        cut = int(len(model_frame) * (1.0 - split))
        cut = max(cut, 20)
        cut = min(cut, len(model_frame) - 5)

        x_train, x_val = x[:cut], x[cut:]
        y_train, y_val = y[:cut], y[cut:]

        # Align regressor seed with config when XGBoost backend
        if isinstance(self.regressor, XGBoostDemandRegressor):
            self.regressor.params["random_state"] = config.random_seed
            self.regressor.params.update(config.training_parameters or {})

        self.regressor.fit(x_train, y_train)
        y_pred = self.regressor.predict(x_val)

        suite = build_demand_evaluation_suite()
        metric_results = suite.evaluate(y_val.tolist(), y_pred.tolist())
        metrics = {m.name: m.value for m in metric_results}

        # Confidence heuristic from validation MAPE (lower error → higher confidence)
        mape = metrics.get("mape")
        if mape is None:
            confidence = 0.7
        else:
            confidence = float(max(0.35, min(0.98, 1.0 - (float(mape) / 100.0))))

        self._active_features = active
        self._history = cleaned.copy()
        self.capacity_mgd = float(
            config.training_parameters.get("capacity_mgd", self.capacity_mgd)
            if config.training_parameters
            else self.capacity_mgd
        )
        # Prefer p99 of demand * 1.05 as soft capacity if not overridden
        if "capacity_mgd" not in (config.training_parameters or {}):
            self.capacity_mgd = float(max(self.capacity_mgd, np.quantile(y, 0.99) * 1.05))

        self.config = config.model_copy(
            update={
                "feature_list": active,
                "model_version": config.model_version,
                "forecast_horizon": config.forecast_horizon,
            }
        )
        self.last_trained_at = datetime.utcnow()
        self.last_metrics = {
            **metrics,
            "validation_rows": int(len(y_val)),
            "train_rows": int(len(y_train)),
            "confidence_estimate": confidence,
            "active_features": active,
            "backend": self.regressor.name,
        }

        self._artifact = {
            "regressor": self.regressor,
            "feature_state": self.feature_builder.state_dict(),
            "active_features": active,
            "capacity_mgd": self.capacity_mgd,
            "last_trained_at": self.last_trained_at.isoformat(),
            "last_metrics": self.last_metrics,
            "history_tail": cleaned.tail(90).to_dict(orient="records"),
            "model_version": config.model_version,
            "config": config.model_dump(),
        }

        # Persist when backend available
        if self.persistence is not None:
            try:
                uri = self.save()
                self.last_metrics["artifact_uri"] = uri
            except Exception as exc:
                self.logger.error(
                    operation="save",
                    message=str(exc),
                    model_name=self.model_name,
                    model_version=self.model_version,
                )

        return {"metrics": self.last_metrics, "rows": len(model_frame)}

    def _evaluate(self, dataset: TrainingDataset, **kwargs: Any) -> dict[str, Any]:
        if not self.is_trained():
            raise RuntimeError("Model not trained")

        raw = dataset.frame.copy()
        cleaned = self.dataset_loader.validate_and_clean(raw, source="evaluate")
        featured = self.feature_pipeline.transform(cleaned)
        active = self._active_features or list(self.config.feature_list)
        model_frame = featured.dropna(subset=active + ["demand_mgd"]).reset_index(drop=True)
        x = model_frame[active].astype(float).to_numpy()
        y = model_frame["demand_mgd"].astype(float).to_numpy()
        y_pred = self.regressor.predict(x)

        suite = build_demand_evaluation_suite()
        results = suite.evaluate(y.tolist(), y_pred.tolist())
        report = {
            "metrics": {m.name: m.value for m in results},
            "rows": len(y),
            "model_version": self.model_version,
            "backend": self.regressor.name,
            "evaluated_at": datetime.utcnow().isoformat(),
        }
        self.last_metrics = {**self.last_metrics, **report["metrics"], "last_eval_rows": len(y)}
        return report

    def _predict(
        self,
        dataset: PredictionDataset,
        *,
        prediction_horizon: int,
        **kwargs: Any,
    ) -> UniversalPredictionOutput:
        if not self.is_trained():
            raise RuntimeError("Model not trained")

        horizon = int(prediction_horizon)
        if horizon not in HORIZONS:
            # Allow any positive horizon but warn via metadata
            if horizon < 1:
                raise ValueError("prediction_horizon must be >= 1")

        capacity = float(kwargs.get("capacity_mgd", self.capacity_mgd))
        history = self._history.copy()
        if history.empty and not dataset.empty():
            history = self.dataset_loader.validate_and_clean(dataset.frame, source="predict")

        if history.empty:
            raise RuntimeError("No demand history available for recursive forecast")

        # Optional overrides appended as the "current" context row
        overrides = kwargs.get("feature_overrides") or {}
        forecast_points = self._recursive_forecast(history, horizon=horizon, overrides=overrides)

        primary = forecast_points[0]["prediction"] if horizon == 1 else forecast_points[-1]["prediction"]
        # For multi-day, "today/tomorrow" style: first step is tomorrow
        tomorrow = forecast_points[0]["prediction"]
        day7 = forecast_points[min(6, len(forecast_points) - 1)]["prediction"]
        day30 = forecast_points[-1]["prediction"] if horizon >= 30 else None

        conf = float(
            kwargs.get(
                "confidence_score",
                self.last_metrics.get("confidence_estimate", 0.7),
            )
        )
        # Mild confidence decay with horizon
        conf = float(max(0.3, conf * (0.98 ** max(0, horizon - 1))))

        risk = demand_risk_level(tomorrow if horizon == 1 else primary, capacity)

        prediction_payload = {
            "unit": "mgd",
            "horizon_days": horizon,
            "tomorrow_mgd": round(float(tomorrow), 3),
            "predicted_demand_mgd": round(float(primary), 3),
            "day7_mgd": round(float(day7), 3),
            "day30_mgd": round(float(day30), 3) if day30 is not None else None,
            "forecast": forecast_points,
            "capacity_mgd": capacity,
            "utilization_pct": round(100.0 * float(primary) / capacity, 2) if capacity else None,
        }

        return UniversalPredictionOutput(
            model_name=self.model_name,
            model_version=self.model_version,
            prediction_horizon=horizon,
            confidence_score=round(conf, 4),
            prediction=prediction_payload,
            risk_level=risk,
            metadata={
                "risk_label": risk_display_label(risk),
                "backend": self.regressor.name,
                "active_features": self._active_features,
                "last_trained_at": self.last_trained_at.isoformat() if self.last_trained_at else None,
                "metrics": {
                    k: self.last_metrics.get(k)
                    for k in ("mae", "rmse", "mape", "r2", "confidence_estimate")
                },
                "is_placeholder": False,
                "summary": (
                    f"Water demand forecast ({horizon}d): "
                    f"{prediction_payload['predicted_demand_mgd']} MGD "
                    f"[{risk_display_label(risk)}]"
                ),
            },
        )

    def predict_horizons(
        self,
        *,
        horizons: list[int] | None = None,
        capacity_mgd: float | None = None,
        feature_overrides: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Convenience API for dashboard: 1/7/15/30 day bundle + Recharts series."""
        if not self.is_trained():
            return {
                "trained": False,
                "message": "Model not trained",
                "model_name": self.model_name,
                "model_version": self.model_version,
            }

        hs = horizons or list(HORIZONS)
        max_h = max(hs)
        # One recursive run to max horizon, then slice
        empty = PredictionDataset(self._history.tail(1) if not self._history.empty else None)
        full = self.predict(
            empty,
            prediction_horizon=max_h,
            capacity_mgd=capacity_mgd or self.capacity_mgd,
            feature_overrides=feature_overrides,
        )
        payload = full.prediction if isinstance(full.prediction, dict) else {}
        series = list(payload.get("forecast") or [])

        by_horizon = {}
        for h in hs:
            idx = min(h, len(series)) - 1
            point = series[idx] if series else None
            by_horizon[str(h)] = point

        return {
            "trained": True,
            "model_name": self.model_name,
            "model_version": self.model_version,
            "generated_at": full.generated_at.isoformat(),
            "confidence_score": full.confidence_score,
            "risk_level": full.risk_level.value,
            "risk_label": full.metadata.get("risk_label"),
            "last_trained_at": self.last_trained_at.isoformat() if self.last_trained_at else None,
            "metrics": full.metadata.get("metrics") or {},
            "capacity_mgd": payload.get("capacity_mgd"),
            "today_predicted_demand_mgd": payload.get("tomorrow_mgd"),
            "horizons": by_horizon,
            "forecast_7d": series[:7],
            "forecast_30d": series[:30] if len(series) >= 30 else series,
            "chart_series": [
                {
                    "date": p["date"],
                    "prediction": p["prediction"],
                    "confidence": p["confidence"],
                }
                for p in series
            ],
            "universal": full.model_dump(mode="json"),
        }

    # ------------------------------------------------------------------
    # Persistence overrides to restore internal state
    # ------------------------------------------------------------------
    def load(self, path: str | None = None, *, version: str | None = None, **kwargs: Any) -> None:
        if self.persistence is None:
            raise NotImplementedError("No ModelPersistence backend injected")
        artifact = self.persistence.load(
            model_name=self.model_name,
            model_version=version or self.model_version,
            path=path,
            **kwargs,
        )
        self._restore_artifact(artifact)
        from fastapi_app.prediction.framework.logging.hooks import LifecycleLogEvent

        self.logger._emit(
            LifecycleLogEvent(
                event="model_loaded",
                model_name=self.model_name,
                model_version=self.model_version,
                details={"path": path or "default"},
            )
        )

    def _restore_artifact(self, artifact: Any) -> None:
        if not isinstance(artifact, dict):
            raise ValueError("Invalid demand model artifact")
        self.regressor = artifact["regressor"]
        self.feature_pipeline = self.feature_builder.load_state(artifact.get("feature_state") or {})
        self._active_features = list(artifact.get("active_features") or [])
        self.capacity_mgd = float(artifact.get("capacity_mgd") or DEFAULT_CAPACITY_MGD)
        self.last_metrics = dict(artifact.get("last_metrics") or {})
        self.model_version = str(artifact.get("model_version") or self.model_version)
        trained_at = artifact.get("last_trained_at")
        self.last_trained_at = (
            datetime.fromisoformat(trained_at) if isinstance(trained_at, str) else None
        )
        history_tail = artifact.get("history_tail") or []
        if history_tail:
            self._history = pd.DataFrame(history_tail)
            if "date" in self._history.columns:
                self._history["date"] = pd.to_datetime(self._history["date"])
        cfg = artifact.get("config")
        if isinstance(cfg, dict):
            self.config = TrainingConfiguration(**cfg)
        self._artifact = artifact
        self._is_trained = True

    def metadata(self) -> dict[str, Any]:
        base = super().metadata()
        base.update(
            {
                "backend": self.regressor.name,
                "last_trained_at": self.last_trained_at.isoformat() if self.last_trained_at else None,
                "last_metrics": self.last_metrics,
                "capacity_mgd": self.capacity_mgd,
                "supported_horizons": list(HORIZONS),
            }
        )
        return base

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _recursive_forecast(
        self,
        history: pd.DataFrame,
        *,
        horizon: int,
        overrides: dict[str, Any],
    ) -> list[dict[str, Any]]:
        working = history.sort_values("date").reset_index(drop=True).copy()
        conf_base = float(self.last_metrics.get("confidence_estimate", 0.75))
        points: list[dict[str, Any]] = []

        for step in range(1, horizon + 1):
            last_date = pd.to_datetime(working["date"].iloc[-1])
            next_date = last_date + timedelta(days=1)
            row = {col: working.iloc[-1].get(col) for col in working.columns}
            row["date"] = next_date
            # Calendar features for the forecast day
            row["day_of_week"] = int(next_date.dayofweek)
            row["month"] = int(next_date.month)
            for key, value in overrides.items():
                row[key] = value
            # Placeholder demand for lag engineering (overwritten after predict)
            row["demand_mgd"] = working["demand_mgd"].iloc[-1]

            step_frame = pd.concat([working, pd.DataFrame([row])], ignore_index=True)
            featured = self.feature_pipeline.transform(step_frame)
            feature_row = featured.iloc[[-1]]
            active = self._active_features
            x = feature_row[active].astype(float).to_numpy()
            # Impute any residual NaNs with 0
            x = np.nan_to_num(x, nan=0.0)
            y_hat = float(self.regressor.predict(x)[0])
            y_hat = max(0.0, y_hat)

            conf = float(max(0.3, conf_base * (0.98 ** (step - 1))))
            points.append(
                {
                    "date": next_date.date().isoformat(),
                    "prediction": round(y_hat, 3),
                    "confidence": round(conf, 4),
                    "horizon_day": step,
                }
            )

            # Append prediction into history for next recursion
            row["demand_mgd"] = y_hat
            working = pd.concat([working, pd.DataFrame([row])], ignore_index=True)

        return points
