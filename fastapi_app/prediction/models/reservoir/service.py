"""Application service for Reservoir Level Forecast HTTP API."""
from __future__ import annotations

from typing import Any

import pandas as pd

from fastapi_app.prediction.framework.datasets.base import PredictionDataset, TrainingDataset
from fastapi_app.prediction.framework.registry.model_registry import ModelRegistry
from fastapi_app.prediction.framework.schemas.config import TrainingConfiguration
from fastapi_app.prediction.models.reservoir.aggregation import (
    aggregate_daily_forecast,
    aggregate_history,
    default_history_lookback,
    reliability_for_horizon,
)
from fastapi_app.prediction.models.reservoir.constants import HORIZONS, MODEL_KEY
from fastapi_app.prediction.models.reservoir.dataset import (
    ReservoirDatasetLoader,
    generate_sample_dataset,
)
from fastapi_app.prediction.models.reservoir.model import ReservoirLevelForecastModel
from fastapi_app.prediction.models.reservoir.recommendations import recommendations_bundle
from fastapi_app.prediction.models.reservoir.risk import (
    remaining_usable_mcm,
    reservoir_risk_level,
    risk_display_label,
    storage_mcm_from_pct,
)
from fastapi_app.prediction.models.water_demand.horizon import (
    HorizonValidationError,
    resolve_horizon_days,
)


class ReservoirLevelForecastService:
    """Resolves the reservoir model exclusively via ModelRegistry (no direct instantiation)."""

    def __init__(self, registry: ModelRegistry) -> None:
        self.registry = registry
        self.loader = ReservoirDatasetLoader()

    def get_model(self) -> ReservoirLevelForecastModel:
        model = self.registry.get(MODEL_KEY)
        if not isinstance(model, ReservoirLevelForecastModel):
            raise TypeError(
                f"Registry key '{MODEL_KEY}' is not a ReservoirLevelForecastModel "
                f"(got {type(model).__name__}). Re-register the production model."
            )
        return model

    def status(self) -> dict[str, Any]:
        model = self.get_model()
        meta = model.metadata()
        trained = model.is_trained()
        metrics = model.last_metrics or {}
        training_rows = None
        if metrics.get("train_rows") is not None:
            training_rows = int(metrics.get("train_rows") or 0) + int(
                metrics.get("validation_rows") or 0
            )
        return {
            "trained": trained,
            "model_name": model.model_name,
            "model_version": model.version(),
            "last_trained_at": meta.get("last_trained_at"),
            "backend": meta.get("backend"),
            "capacity_mcm": meta.get("capacity_mcm"),
            "supported_horizons": meta.get("supported_horizons") or list(HORIZONS),
            "training_rows": training_rows,
            "reservoirs": meta.get("reservoirs") or [],
            "message": "Ready" if trained else "Model not trained",
        }

    def metrics(self) -> dict[str, Any]:
        from ai.evaluation import strip_filesystem_paths

        model = self.get_model()
        if not model.is_trained():
            return {
                "trained": False,
                "metrics": {},
                "message": "Model not trained",
            }
        return {
            "trained": True,
            "metrics": strip_filesystem_paths(model.last_metrics or {}),
            "message": "Evaluation metrics from last train/evaluate",
        }

    def train(
        self,
        *,
        dataset_path: str | None = None,
        use_sample: bool = True,
        validation_split: float = 0.2,
        random_seed: int = 42,
        model_version: str = "1.0.0",
        capacity_mcm: float | None = None,
        training_parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        model = self.get_model()
        params = dict(training_parameters or {})
        if capacity_mcm is not None:
            params["capacity_mcm"] = capacity_mcm

        if dataset_path:
            frame = self.loader.load_any(dataset_path)
        elif use_sample:
            generate_sample_dataset()
            frame = self.loader.load_sample()
        else:
            raise ValueError("Provide dataset_path or set use_sample=true")

        config = TrainingConfiguration(
            model_name=MODEL_KEY,
            model_version=model_version,
            validation_split=validation_split,
            random_seed=random_seed,
            forecast_horizon=7,
            feature_list=[],
            training_parameters=params,
        )
        dataset = TrainingDataset(
            frame,
            feature_columns=[],
            target_column="storage_pct",
            name="reservoir_training",
            source=dataset_path or "sample",
        )
        result = model.train(dataset, config)
        self.registry.register(MODEL_KEY, model)
        metrics = result.get("metrics") if isinstance(result, dict) else model.last_metrics
        return {
            "trained": model.is_trained(),
            "model_version": model.version(),
            "metrics": metrics or {},
            "artifact_uri": (metrics or {}).get("artifact_uri"),
            "message": "Reservoir level model trained successfully",
        }

    def predict(
        self,
        *,
        horizon_days: int = 7,
        horizons: list[int] | None = None,
        capacity_mcm: float | None = None,
        feature_overrides: dict[str, Any] | None = None,
        value: int | None = None,
        unit: str | None = None,
        include_history_days: int = 90,
        reservoir_id: str | None = None,
    ) -> dict[str, Any]:
        model = self.get_model()
        if not model.is_trained():
            return {
                "trained": False,
                "message": "Model not trained",
                "model_name": model.model_name,
                "model_version": model.version(),
                "reservoirs": model._catalog,
            }

        if horizons and value is None:
            return model.predict_horizons(
                horizons=horizons,
                capacity_mcm=capacity_mcm,
                feature_overrides=feature_overrides,
                reservoir_id=reservoir_id,
            )

        try:
            days, display_value, display_unit = resolve_horizon_days(
                value=value,
                unit=unit,
                horizon_days=horizon_days,
            )
        except HorizonValidationError as exc:
            raise ValueError(str(exc)) from exc

        return self._workspace_forecast(
            model=model,
            days=days,
            display_value=display_value,
            display_unit=display_unit,
            capacity_mcm=capacity_mcm,
            feature_overrides=feature_overrides,
            include_history_days=include_history_days,
            reservoir_id=reservoir_id,
        )

    def _workspace_forecast(
        self,
        *,
        model: ReservoirLevelForecastModel,
        days: int,
        display_value: int,
        display_unit: str,
        capacity_mcm: float | None,
        feature_overrides: dict[str, Any] | None,
        include_history_days: int,
        reservoir_id: str | None,
    ) -> dict[str, Any]:
        empty = model._history.tail(1) if not model._history.empty else pd.DataFrame()
        output = model.predict(
            PredictionDataset(empty if not empty.empty else None),
            prediction_horizon=days,
            capacity_mcm=capacity_mcm,
            feature_overrides=feature_overrides,
            reservoir_id=reservoir_id,
        )
        payload = output.prediction if isinstance(output.prediction, dict) else {}
        capacity = float(payload.get("capacity_mcm") or capacity_mcm or model.capacity_mcm)
        forecast_raw = list(payload.get("forecast") or [])
        rmse = float(model.last_metrics.get("rmse") or 2.5)
        base_conf = float(
            output.confidence_score or model.last_metrics.get("confidence_estimate") or 0.7
        )
        reliability = reliability_for_horizon(days, base_conf)

        daily_forecast: list[dict[str, Any]] = []
        for i, p in enumerate(forecast_raw):
            step = int(p.get("horizon_day") or (i + 1))
            pred = float(p["prediction"])
            band = rmse * (1.0 + 0.085 * step) * 1.28
            conf = float(p.get("confidence") or max(0.25, base_conf * (0.985 ** (step - 1))))
            conf *= reliability["confidence_factor"]
            risk = reservoir_risk_level(pred)
            daily_forecast.append(
                {
                    "date": p["date"],
                    "forecast": round(pred, 3),
                    "lower": round(max(0.0, pred - band), 3),
                    "upper": round(min(100.0, pred + band), 3),
                    "confidence": round(max(0.25, min(0.98, conf)), 4),
                    "risk": risk_display_label(risk),
                    "horizon_day": step,
                }
            )

        unit = display_unit
        forecast_points = aggregate_daily_forecast(
            daily_forecast,
            unit=unit,  # type: ignore[arg-type]
            value=display_value,
            rmse=rmse,
            confidence_factor=float(reliability["confidence_factor"]),
        )

        hist_days = max(include_history_days, days)
        raw_history = self._history_series(model, hist_days, payload.get("reservoir_id"))
        lookback = default_history_lookback(unit, display_value)  # type: ignore[arg-type]
        history_points = aggregate_history(
            raw_history,
            unit=unit,  # type: ignore[arg-type]
            lookback_periods=lookback,
        )
        chart_series = history_points + forecast_points

        summary = self._build_summary(
            forecast_points,
            daily_forecast,
            capacity,
            float(reliability["confidence"]),
            payload=payload,
            unit=unit,
            periods=display_value,
        )
        insights = self._build_insights(
            forecast_points,
            summary,
            unit=unit,
            periods=display_value,
            reliability=reliability,
            reservoir_name=payload.get("reservoir_name"),
        )
        recs = recommendations_bundle(
            universal=output,
            forecast_points=daily_forecast,
            summary=summary,
            reservoir_name=payload.get("reservoir_name"),
        )

        metrics = {
            k: model.last_metrics.get(k)
            for k in (
                "mae",
                "rmse",
                "mape",
                "r2",
                "train_rows",
                "validation_rows",
                "confidence_estimate",
            )
        }
        training_rows = int(metrics.get("train_rows") or 0) + int(
            metrics.get("validation_rows") or 0
        )

        legacy_chart = [
            {"date": p["date"], "prediction": p["forecast"], "confidence": p["confidence"]}
            for p in forecast_points
        ]

        return {
            "trained": True,
            "message": "Forecast generated",
            "model_name": output.model_name,
            "model_version": output.model_version,
            "generated_at": output.generated_at.isoformat(),
            "prediction_id": output.prediction_id,
            "confidence_score": reliability["confidence"],
            "risk_level": output.risk_level.value,
            "risk_label": summary.get("risk_label") or risk_display_label(output.risk_level),
            "prediction_horizon": days,
            "horizon": {
                "value": display_value,
                "unit": display_unit,
                "days": days,
                "point_count": len(forecast_points),
                "granularity": display_unit,
                "note": "Forecast confidence decreases as horizon increases.",
            },
            "reliability": reliability,
            "capacity_mcm": capacity,
            "reservoir_id": payload.get("reservoir_id"),
            "reservoir_name": payload.get("reservoir_name"),
            "current_storage_pct": payload.get("current_storage_pct"),
            "forecasted_storage_pct": payload.get("forecasted_storage_pct"),
            "forecasted_storage_mcm": payload.get("forecasted_storage_mcm"),
            "remaining_usable_storage_mcm": payload.get("remaining_usable_storage_mcm"),
            "last_trained_at": model.last_trained_at.isoformat()
            if model.last_trained_at
            else None,
            "metrics": metrics,
            "model": {
                "model_version": output.model_version,
                "last_trained_at": model.last_trained_at.isoformat()
                if model.last_trained_at
                else None,
                "training_dataset_size": training_rows or None,
                "backend": model.regressor.name,
            },
            "summary": summary,
            "insights": insights,
            "executive_recommendations": recs["executive_recommendations"],
            "decision_engine": recs["decision_engine"],
            "reservoirs": model._catalog,
            "chart_series": legacy_chart,
            "forecast_series": forecast_points,
            "series": chart_series,
            "prediction": payload,
            "universal": output.model_dump(mode="json"),
        }

    def _history_series(
        self,
        model: ReservoirLevelForecastModel,
        days: int,
        reservoir_id: str | None,
    ) -> list[dict[str, Any]]:
        hist = model._history_for(reservoir_id)
        if hist is None or hist.empty or "storage_pct" not in hist.columns:
            return []
        frame = hist.sort_values("date").tail(int(days)).copy()
        levels = frame["storage_pct"].astype(float).tolist()
        points: list[dict[str, Any]] = []
        for i, (_, row) in enumerate(frame.iterrows()):
            d = float(row["storage_pct"])
            date_val = pd.to_datetime(row["date"]).date().isoformat()
            prev = levels[i - 1] if i > 0 else None
            window = levels[max(0, i - 6) : i + 1]
            points.append(
                {
                    "date": date_val,
                    "historical": round(d, 3),
                    "forecast": None,
                    "lower": None,
                    "upper": None,
                    "confidence": None,
                    "risk": None,
                    "daily_change": None if prev is None else round(d - prev, 3),
                    "rolling_avg": round(sum(window) / len(window), 3),
                }
            )
        return points

    def _build_summary(
        self,
        forecast: list[dict[str, Any]],
        daily_forecast: list[dict[str, Any]],
        capacity: float,
        confidence: float,
        *,
        payload: dict[str, Any],
        unit: str,
        periods: int,
    ) -> dict[str, Any]:
        if not forecast:
            return {}
        vals = [float(p["forecast"]) for p in forecast if p.get("forecast") is not None]
        peak = max(vals)
        trough = min(vals)
        avg = sum(vals) / len(vals)
        first = vals[0]
        last = vals[-1]
        change = last - first
        peak_idx = vals.index(peak)
        trough_idx = vals.index(trough)
        focus = float(payload.get("forecasted_storage_pct") or last)
        risk = reservoir_risk_level(focus)
        days_to_critical = None
        for p in daily_forecast:
            if float(p["forecast"]) < 20.0:
                days_to_critical = int(p.get("horizon_day") or 0)
                break
        remaining_days = days_to_critical
        return {
            "current_storage_pct": payload.get("current_storage_pct"),
            "forecasted_storage_pct": round(focus, 3),
            "forecasted_storage_mcm": round(storage_mcm_from_pct(focus, capacity), 3),
            "remaining_usable_storage_mcm": round(remaining_usable_mcm(focus, capacity), 3),
            "peak_storage_pct": round(peak, 3),
            "minimum_storage_pct": round(trough, 3),
            "average_forecast_pct": round(avg, 3),
            "storage_change_pct": round(change, 2),
            "days_to_critical": remaining_days,
            "remaining_days": remaining_days,
            "risk_label": risk_display_label(risk),
            "confidence": round(confidence, 4),
            "peak_date": forecast[peak_idx]["date"],
            "minimum_date": forecast[trough_idx]["date"],
            "horizon_periods": periods,
            "horizon_unit": unit,
            "point_count": len(forecast),
            "capacity_mcm": capacity,
        }

    def _build_insights(
        self,
        forecast: list[dict[str, Any]],
        summary: dict[str, Any],
        *,
        unit: str,
        periods: int,
        reliability: dict[str, Any],
        reservoir_name: str | None,
    ) -> list[str]:
        if not forecast or not summary:
            return ["Insufficient forecast data to generate insights."]

        unit_label = {"days": "day", "weeks": "week", "months": "month", "years": "year"}.get(
            unit, "period"
        )
        unit_plural = unit if periods != 1 else unit_label
        name = reservoir_name or "Reservoir"
        insights: list[str] = []

        change = float(summary.get("storage_change_pct") or 0.0)
        direction = "rise" if change >= 0 else "decline"
        insights.append(
            f"{name} storage expected to {direction} {abs(change):.1f} pp across the next "
            f"{periods} {unit_plural}."
        )

        min_pct = summary.get("minimum_storage_pct")
        min_date = summary.get("minimum_date")
        if min_pct is not None and min_date:
            insights.append(f"Minimum storage of {float(min_pct):.1f}% expected at {min_date}.")

        days_crit = summary.get("days_to_critical")
        if days_crit:
            insights.append(f"Critical threshold (<20%) projected in {days_crit} days.")
        else:
            insights.append("No critical-level breach detected within this horizon.")

        insights.append(
            f"Risk classification: {summary.get('risk_label', 'UNKNOWN')} "
            f"with {float(summary.get('confidence') or 0) * 100:.0f}% confidence."
        )

        if reliability.get("warning"):
            insights.append(str(reliability["warning"]))
        else:
            insights.append(
                "Forecast confidence decreases as horizon increases; "
                "near-term periods are more actionable than distant ones."
            )
        return insights
