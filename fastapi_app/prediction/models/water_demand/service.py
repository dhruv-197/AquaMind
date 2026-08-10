"""Application service for Water Demand Forecast HTTP API."""
from __future__ import annotations

from typing import Any

import pandas as pd

from fastapi_app.prediction.framework.datasets.base import PredictionDataset, TrainingDataset
from fastapi_app.prediction.framework.registry.model_registry import ModelRegistry
from fastapi_app.prediction.framework.schemas.config import TrainingConfiguration
from fastapi_app.prediction.models.water_demand.aggregation import (
    aggregate_daily_forecast,
    aggregate_history,
    default_history_lookback,
    reliability_for_horizon,
)
from fastapi_app.prediction.models.water_demand.constants import HORIZONS, MODEL_KEY
from fastapi_app.prediction.models.water_demand.dataset import (
    DemandDatasetLoader,
    generate_sample_dataset,
)
from fastapi_app.prediction.models.water_demand.horizon import (
    HorizonValidationError,
    resolve_horizon_days,
)
from fastapi_app.prediction.models.water_demand.model import WaterDemandForecastModel
from fastapi_app.prediction.models.water_demand.risk import demand_risk_level, risk_display_label


class WaterDemandForecastService:
    """Resolves the demand model exclusively via ModelRegistry (no direct instantiation)."""

    def __init__(self, registry: ModelRegistry) -> None:
        self.registry = registry
        self.loader = DemandDatasetLoader()

    def get_model(self) -> WaterDemandForecastModel:
        model = self.registry.get(MODEL_KEY)
        if not isinstance(model, WaterDemandForecastModel):
            raise TypeError(
                f"Registry key '{MODEL_KEY}' is not a WaterDemandForecastModel "
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
            "capacity_mgd": meta.get("capacity_mgd"),
            "supported_horizons": meta.get("supported_horizons") or list(HORIZONS),
            "training_rows": training_rows,
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
        capacity_mgd: float | None = None,
        training_parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        model = self.get_model()
        params = dict(training_parameters or {})
        if capacity_mgd is not None:
            params["capacity_mgd"] = capacity_mgd

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
            target_column="demand_mgd",
            name="water_demand_training",
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
            "message": "Water demand model trained successfully",
        }

    def predict(
        self,
        *,
        horizon_days: int = 7,
        horizons: list[int] | None = None,
        capacity_mgd: float | None = None,
        feature_overrides: dict[str, Any] | None = None,
        value: int | None = None,
        unit: str | None = None,
        include_history_days: int = 90,
    ) -> dict[str, Any]:
        model = self.get_model()
        if not model.is_trained():
            return {
                "trained": False,
                "message": "Model not trained",
                "model_name": model.model_name,
                "model_version": model.version(),
            }

        # Legacy multi-horizon bundle (fixed presets) — keep for older clients
        if horizons and value is None:
            return model.predict_horizons(
                horizons=horizons,
                capacity_mgd=capacity_mgd,
                feature_overrides=feature_overrides,
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
            capacity_mgd=capacity_mgd,
            feature_overrides=feature_overrides,
            include_history_days=include_history_days,
        )

    def _workspace_forecast(
        self,
        *,
        model: WaterDemandForecastModel,
        days: int,
        display_value: int,
        display_unit: str,
        capacity_mgd: float | None,
        feature_overrides: dict[str, Any] | None,
        include_history_days: int,
    ) -> dict[str, Any]:
        capacity = float(capacity_mgd or model.capacity_mgd)
        empty = model._history.tail(1) if not model._history.empty else pd.DataFrame()
        output = model.predict(
            PredictionDataset(empty if not empty.empty else None),
            prediction_horizon=days,
            capacity_mgd=capacity,
            feature_overrides=feature_overrides,
        )
        payload = output.prediction if isinstance(output.prediction, dict) else {}
        forecast_raw = list(payload.get("forecast") or [])
        rmse = float(model.last_metrics.get("rmse") or 2.5)
        base_conf = float(
            output.confidence_score or model.last_metrics.get("confidence_estimate") or 0.7
        )
        reliability = reliability_for_horizon(days, base_conf)

        # Build daily forecast points first (one per recursive day)
        daily_forecast: list[dict[str, Any]] = []
        preds: list[float] = []
        for i, p in enumerate(forecast_raw):
            step = int(p.get("horizon_day") or (i + 1))
            pred = float(p["prediction"])
            preds.append(pred)
            band = rmse * (1.0 + 0.085 * step) * 1.28
            conf = float(p.get("confidence") or max(0.25, base_conf * (0.985 ** (step - 1))))
            conf *= reliability["confidence_factor"]
            risk = demand_risk_level(pred, capacity)
            daily_forecast.append(
                {
                    "date": p["date"],
                    "forecast": round(pred, 3),
                    "lower": round(max(0.0, pred - band), 3),
                    "upper": round(pred + band, 3),
                    "confidence": round(max(0.25, min(0.98, conf)), 4),
                    "risk": risk_display_label(risk),
                }
            )

        unit = display_unit  # days|weeks|months|years
        forecast_points = aggregate_daily_forecast(
            daily_forecast,
            unit=unit,  # type: ignore[arg-type]
            value=display_value,
            capacity_mgd=capacity,
            rmse=rmse,
            confidence_factor=float(reliability["confidence_factor"]),
        )

        # History aligned to same granularity
        hist_days = max(include_history_days, days)
        raw_history = self._history_series(model, hist_days)
        lookback = default_history_lookback(unit, display_value)  # type: ignore[arg-type]
        history_points = aggregate_history(
            raw_history,
            unit=unit,  # type: ignore[arg-type]
            lookback_periods=lookback,
        )
        chart_series = history_points + forecast_points

        summary = self._build_summary(
            forecast_points,
            capacity,
            float(reliability["confidence"]),
            unit=unit,
            periods=display_value,
        )
        insights = self._build_insights(
            forecast_points,
            summary,
            unit=unit,
            periods=display_value,
            reliability=reliability,
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
            "risk_label": summary.get("expected_shortage_risk"),
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
            "capacity_mgd": capacity,
            "today_predicted_demand_mgd": forecast_points[0]["forecast"]
            if forecast_points
            else None,
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
            "chart_series": legacy_chart,
            "forecast_series": forecast_points,
            "series": chart_series,
            "prediction": payload,
            "universal": output.model_dump(mode="json"),
        }

    def _history_series(self, model: WaterDemandForecastModel, days: int) -> list[dict[str, Any]]:
        hist = model._history
        if hist is None or hist.empty or "demand_mgd" not in hist.columns:
            return []
        frame = hist.sort_values("date").tail(int(days)).copy()
        demands = frame["demand_mgd"].astype(float).tolist()
        points: list[dict[str, Any]] = []
        for i, (_, row) in enumerate(frame.iterrows()):
            d = float(row["demand_mgd"])
            date_val = pd.to_datetime(row["date"]).date().isoformat()
            prev = demands[i - 1] if i > 0 else None
            window = demands[max(0, i - 6) : i + 1]
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
        capacity: float,
        confidence: float,
        *,
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
        growth = ((last - first) / first * 100.0) if first else 0.0
        util = (peak / capacity * 100.0) if capacity else None
        peak_idx = vals.index(peak)
        risk = demand_risk_level(peak, capacity)
        shortage_date = None
        for p in forecast:
            if (p.get("risk") or "").upper() == "HIGH":
                shortage_date = p.get("date")
                break
        return {
            "predicted_peak_demand_mgd": round(peak, 3),
            "predicted_minimum_mgd": round(trough, 3),
            "average_forecast_mgd": round(avg, 3),
            "growth_pct": round(growth, 2),
            "capacity_utilization_pct": round(util, 2) if util is not None else None,
            "expected_shortage_risk": risk_display_label(risk),
            "expected_shortage_date": shortage_date,
            "confidence": round(confidence, 4),
            "peak_date": forecast[peak_idx]["date"],
            "horizon_periods": periods,
            "horizon_unit": unit,
            "point_count": len(forecast),
        }

    def _build_insights(
        self,
        forecast: list[dict[str, Any]],
        summary: dict[str, Any],
        *,
        unit: str,
        periods: int,
        reliability: dict[str, Any],
    ) -> list[str]:
        if not forecast or not summary:
            return ["Insufficient forecast data to generate insights."]

        unit_label = {"days": "day", "weeks": "week", "months": "month", "years": "year"}.get(
            unit, "period"
        )
        unit_plural = unit if periods != 1 else unit_label
        insights: list[str] = []

        growth = float(summary.get("growth_pct") or 0.0)
        direction = "increase" if growth >= 0 else "decrease"
        insights.append(
            f"Demand expected to {direction} {abs(growth):.1f}% across the next "
            f"{periods} {unit_plural}."
        )

        peak_date = summary.get("peak_date")
        peak = summary.get("predicted_peak_demand_mgd")
        if peak_date and peak is not None:
            insights.append(f"Peak demand of {float(peak):.1f} MGD expected at {peak_date}.")

        util = summary.get("capacity_utilization_pct")
        if util is not None:
            insights.append(f"Capacity utilisation expected to reach {float(util):.1f}%.")

        shortage = summary.get("expected_shortage_date")
        if shortage:
            insights.append(f"HIGH shortage risk first appears at {shortage}.")
        else:
            insights.append("No HIGH shortage-risk periods detected within this horizon.")

        avg_conf = sum(float(p["confidence"]) for p in forecast if p.get("confidence") is not None)
        n_conf = sum(1 for p in forecast if p.get("confidence") is not None)
        if n_conf:
            insights.append(
                f"Average period confidence is {avg_conf / n_conf * 100:.0f}% "
                f"({reliability.get('reliability_tier', 'unknown')} reliability tier)."
            )

        if reliability.get("warning"):
            insights.append(str(reliability["warning"]))
        else:
            insights.append(
                "Forecast confidence decreases as horizon increases; "
                "near-term periods are more actionable than distant ones."
            )
        return insights
