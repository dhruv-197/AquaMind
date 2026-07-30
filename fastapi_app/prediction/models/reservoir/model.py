"""
Reservoir Level Forecast model — BaseModelPredictor implementation.

Uses an injected ReservoirRegressorBackend (XGBoost by default).
Does not modify the prediction framework.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd

from fastapi_app.prediction.framework.datasets.base import (
    PredictionDataset,
    TrainingDataset,
)
from fastapi_app.prediction.framework.lifecycle.predictor import BaseModelPredictor
from fastapi_app.prediction.framework.logging.hooks import PredictionLogger
from fastapi_app.prediction.framework.persistence.store import ModelPersistence
from fastapi_app.prediction.framework.schemas.config import TrainingConfiguration
from fastapi_app.prediction.framework.schemas.output import UniversalPredictionOutput
from fastapi_app.prediction.models.reservoir.constants import (
    DEFAULT_CAPACITY_MCM,
    HORIZONS,
    MODEL_KEY,
    MODEL_VERSION,
)
from fastapi_app.prediction.models.reservoir.dataset import ReservoirDatasetLoader
from fastapi_app.prediction.models.reservoir.features import ReservoirFeaturePipelineBuilder
from fastapi_app.prediction.models.reservoir.metrics import build_reservoir_evaluation_suite
from fastapi_app.prediction.models.reservoir.regressor import (
    ReservoirRegressorBackend,
    XGBoostReservoirRegressor,
)
from fastapi_app.prediction.models.reservoir.risk import (
    remaining_usable_mcm,
    reservoir_risk_level,
    risk_display_label,
    storage_mcm_from_pct,
)


class ReservoirLevelForecastModel(BaseModelPredictor):
    """Production reservoir-level forecaster plugged into ModelRegistry as `reservoir_forecast`."""

    def __init__(
        self,
        *,
        regressor: ReservoirRegressorBackend | None = None,
        persistence: ModelPersistence | None = None,
        logger: PredictionLogger | None = None,
        capacity_mcm: float = DEFAULT_CAPACITY_MCM,
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
        self.regressor: ReservoirRegressorBackend = regressor or XGBoostReservoirRegressor(
            random_state=cfg.random_seed
        )
        self.feature_builder = ReservoirFeaturePipelineBuilder()
        self.dataset_loader = ReservoirDatasetLoader()
        self.capacity_mcm = float(capacity_mcm)
        self.last_trained_at: datetime | None = None
        self.last_metrics: dict[str, Any] = {}
        self._history: pd.DataFrame = pd.DataFrame()
        self._active_features: list[str] = []
        self._catalog: list[dict[str, Any]] = []

    def _train(self, dataset: TrainingDataset, config: TrainingConfiguration) -> dict[str, Any]:
        raw = dataset.frame.copy()
        if "date" not in raw.columns or "storage_pct" not in raw.columns:
            raise ValueError("Training data must include 'date' and 'storage_pct' columns")

        cleaned = self.dataset_loader.validate_and_clean(
            raw, source=dataset.metadata.source or "training"
        )
        pipeline = self.feature_builder.fit(cleaned)
        self.feature_pipeline = pipeline
        featured = pipeline.transform(cleaned)

        active = list(self.feature_builder.active_features)
        if not active:
            raise RuntimeError("No usable features after pipeline fit")

        model_frame = featured.dropna(subset=active + ["storage_pct"]).reset_index(drop=True)
        if len(model_frame) < 30:
            raise RuntimeError(f"Insufficient rows after feature engineering: {len(model_frame)}")

        x = model_frame[active].astype(float).to_numpy()
        y = model_frame["storage_pct"].astype(float).to_numpy()

        split = float(config.validation_split)
        split = min(max(split, 0.05), 0.4)
        cut = int(len(model_frame) * (1.0 - split))
        cut = max(cut, 20)
        cut = min(cut, len(model_frame) - 5)

        x_train, x_val = x[:cut], x[cut:]
        y_train, y_val = y[:cut], y[cut:]

        if isinstance(self.regressor, XGBoostReservoirRegressor):
            self.regressor.params["random_state"] = config.random_seed
            self.regressor.params.update(config.training_parameters or {})

        self.regressor.fit(x_train, y_train)
        y_pred = self.regressor.predict(x_val)

        suite = build_reservoir_evaluation_suite()
        metric_results = suite.evaluate(y_val.tolist(), y_pred.tolist())
        metrics = {m.name: m.value for m in metric_results}

        mape = metrics.get("mape")
        if mape is None:
            confidence = 0.7
        else:
            confidence = float(max(0.35, min(0.98, 1.0 - (float(mape) / 100.0))))

        self._active_features = active
        self._history = cleaned.copy()
        self._catalog = ReservoirDatasetLoader.catalog_from_frame(cleaned)

        params = config.training_parameters or {}
        if "capacity_mcm" in params:
            self.capacity_mcm = float(params["capacity_mcm"])
        elif self._catalog and self._catalog[0].get("capacity_mcm"):
            self.capacity_mcm = float(self._catalog[0]["capacity_mcm"])

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
            "reservoir_count": len(self._catalog),
        }

        self._artifact = {
            "regressor": self.regressor,
            "feature_state": self.feature_builder.state_dict(),
            "active_features": active,
            "capacity_mcm": self.capacity_mcm,
            "last_trained_at": self.last_trained_at.isoformat(),
            "last_metrics": self.last_metrics,
            "history_tail": pd.concat(
                [g.tail(120) for _, g in cleaned.groupby("reservoir_id", sort=False)],
                ignore_index=True,
            ).to_dict(orient="records"),
            "catalog": self._catalog,
            "model_version": config.model_version,
            "config": config.model_dump(),
        }

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
        model_frame = featured.dropna(subset=active + ["storage_pct"]).reset_index(drop=True)
        x = model_frame[active].astype(float).to_numpy()
        y = model_frame["storage_pct"].astype(float).to_numpy()
        y_pred = self.regressor.predict(x)

        suite = build_reservoir_evaluation_suite()
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
        if horizon < 1:
            raise ValueError("prediction_horizon must be >= 1")

        reservoir_id = kwargs.get("reservoir_id")
        history = self._history_for(reservoir_id)
        if history.empty and not dataset.empty():
            history = self.dataset_loader.validate_and_clean(dataset.frame, source="predict")
            if reservoir_id:
                history = history[history["reservoir_id"].astype(str) == str(reservoir_id)]

        if history.empty:
            raise RuntimeError("No reservoir history available for recursive forecast")

        meta = self._resolve_reservoir_meta(history, reservoir_id)
        capacity = float(kwargs.get("capacity_mcm") or meta.get("capacity_mcm") or self.capacity_mcm)
        overrides = kwargs.get("feature_overrides") or {}
        forecast_points = self._recursive_forecast(
            history,
            horizon=horizon,
            overrides=overrides,
            capacity_mcm=capacity,
        )

        primary = forecast_points[0]["prediction"] if horizon == 1 else forecast_points[-1]["prediction"]
        tomorrow = forecast_points[0]["prediction"]
        focus = tomorrow if horizon == 1 else primary

        conf = float(
            kwargs.get(
                "confidence_score",
                self.last_metrics.get("confidence_estimate", 0.7),
            )
        )
        conf = float(max(0.3, conf * (0.98 ** max(0, horizon - 1))))

        risk = reservoir_risk_level(focus)
        storage_mcm = storage_mcm_from_pct(focus, capacity)
        remaining = remaining_usable_mcm(focus, capacity)

        prediction_payload = {
            "unit": "storage_pct",
            "horizon_days": horizon,
            "reservoir_id": meta.get("reservoir_id"),
            "reservoir_name": meta.get("reservoir_name"),
            "forecasted_storage_pct": round(float(focus), 3),
            "forecasted_storage_mcm": round(float(storage_mcm), 3),
            "remaining_usable_storage_mcm": round(float(remaining), 3),
            "tomorrow_storage_pct": round(float(tomorrow), 3),
            "forecast": forecast_points,
            "capacity_mcm": capacity,
            "current_storage_pct": round(float(history["storage_pct"].iloc[-1]), 3),
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
                "region_id": meta.get("reservoir_id") or "REG-1",
                "summary": (
                    f"Reservoir forecast ({horizon}d) for {meta.get('reservoir_name') or meta.get('reservoir_id')}: "
                    f"{prediction_payload['forecasted_storage_pct']}% "
                    f"({prediction_payload['forecasted_storage_mcm']} MCM) "
                    f"[{risk_display_label(risk)}]"
                ),
            },
        )

    def predict_horizons(
        self,
        *,
        horizons: list[int] | None = None,
        capacity_mcm: float | None = None,
        feature_overrides: dict[str, Any] | None = None,
        reservoir_id: str | None = None,
    ) -> dict[str, Any]:
        if not self.is_trained():
            return {
                "trained": False,
                "message": "Model not trained",
                "model_name": self.model_name,
                "model_version": self.model_version,
            }

        hs = horizons or list(HORIZONS)
        max_h = max(hs)
        empty = PredictionDataset(self._history.tail(1) if not self._history.empty else None)
        full = self.predict(
            empty,
            prediction_horizon=max_h,
            capacity_mcm=capacity_mcm or self.capacity_mcm,
            feature_overrides=feature_overrides,
            reservoir_id=reservoir_id,
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
            "capacity_mcm": payload.get("capacity_mcm"),
            "reservoir_id": payload.get("reservoir_id"),
            "forecasted_storage_pct": payload.get("forecasted_storage_pct"),
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
            raise ValueError("Invalid reservoir model artifact")
        self.regressor = artifact["regressor"]
        self.feature_pipeline = self.feature_builder.load_state(artifact.get("feature_state") or {})
        self._active_features = list(artifact.get("active_features") or [])
        self.capacity_mcm = float(artifact.get("capacity_mcm") or DEFAULT_CAPACITY_MCM)
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
        self._catalog = list(artifact.get("catalog") or [])
        if not self._catalog and not self._history.empty:
            self._catalog = ReservoirDatasetLoader.catalog_from_frame(self._history)
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
                "capacity_mcm": self.capacity_mcm,
                "supported_horizons": list(HORIZONS),
                "reservoirs": self._catalog,
            }
        )
        return base

    def _history_for(self, reservoir_id: str | None) -> pd.DataFrame:
        hist = self._history.copy()
        if hist.empty:
            return hist
        if reservoir_id:
            subset = hist[hist["reservoir_id"].astype(str) == str(reservoir_id)]
            if not subset.empty:
                return subset.sort_values("date").reset_index(drop=True)
        # Default: first reservoir in catalog / history
        first_id = None
        if self._catalog:
            first_id = self._catalog[0].get("reservoir_id")
        if first_id is None and "reservoir_id" in hist.columns:
            first_id = hist["reservoir_id"].astype(str).iloc[0]
        if first_id is not None:
            return hist[hist["reservoir_id"].astype(str) == str(first_id)].sort_values("date").reset_index(drop=True)
        return hist.sort_values("date").reset_index(drop=True)

    def _resolve_reservoir_meta(
        self, history: pd.DataFrame, reservoir_id: str | None
    ) -> dict[str, Any]:
        rid = str(reservoir_id) if reservoir_id else None
        if not rid and "reservoir_id" in history.columns and not history.empty:
            rid = str(history["reservoir_id"].iloc[-1])
        for item in self._catalog:
            if str(item.get("reservoir_id")) == str(rid):
                return item
        capacity = None
        name = rid
        if not history.empty:
            if "capacity_mcm" in history.columns and history["capacity_mcm"].notna().any():
                capacity = float(history["capacity_mcm"].dropna().iloc[-1])
            if "reservoir_name" in history.columns and history["reservoir_name"].notna().any():
                name = str(history["reservoir_name"].dropna().iloc[-1])
        return {
            "reservoir_id": rid,
            "reservoir_name": name,
            "capacity_mcm": capacity or self.capacity_mcm,
        }

    def _recursive_forecast(
        self,
        history: pd.DataFrame,
        *,
        horizon: int,
        overrides: dict[str, Any],
        capacity_mcm: float,
    ) -> list[dict[str, Any]]:
        working = history.sort_values("date").reset_index(drop=True).copy()
        conf_base = float(self.last_metrics.get("confidence_estimate", 0.75))
        points: list[dict[str, Any]] = []

        for step in range(1, horizon + 1):
            last_date = pd.to_datetime(working["date"].iloc[-1])
            next_date = last_date + timedelta(days=1)
            row = {col: working.iloc[-1].get(col) for col in working.columns}
            row["date"] = next_date
            row["month"] = int(next_date.month)
            row["capacity_mcm"] = capacity_mcm
            for key, value in overrides.items():
                row[key] = value
            row["storage_pct"] = working["storage_pct"].iloc[-1]

            step_frame = pd.concat([working, pd.DataFrame([row])], ignore_index=True)
            featured = self.feature_pipeline.transform(step_frame)
            feature_row = featured.iloc[[-1]]
            active = self._active_features
            x = feature_row[active].astype(float).to_numpy()
            x = np.nan_to_num(x, nan=0.0)
            y_hat = float(self.regressor.predict(x)[0])
            y_hat = float(max(0.0, min(100.0, y_hat)))

            conf = float(max(0.3, conf_base * (0.98 ** (step - 1))))
            points.append(
                {
                    "date": next_date.date().isoformat(),
                    "prediction": round(y_hat, 3),
                    "confidence": round(conf, 4),
                    "horizon_day": step,
                    "storage_mcm": round(storage_mcm_from_pct(y_hat, capacity_mcm), 3),
                }
            )

            row["storage_pct"] = y_hat
            working = pd.concat([working, pd.DataFrame([row])], ignore_index=True)

        return points
