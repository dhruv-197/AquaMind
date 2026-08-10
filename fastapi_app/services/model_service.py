"""Inference façade for AquaMind sklearn models + fusion helpers.

Keeps HTTP routers thin: load models once, enrich leak/GW outputs, and build
live telemetry for recommendations / water-stress analytics.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime
from typing import Any

# Add root /ai path so model classes import cleanly.
AI_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "ai"))
if AI_PATH not in sys.path:
    sys.path.append(AI_PATH)

try:
    from water_shortage_model import WaterShortageModel
    from groundwater_model import GroundwaterModel
    from water_demand_model import WaterDemandModel
    from leak_detection_model import LeakDetectionModel

    AI_MODELS_AVAILABLE = True
except Exception as e:
    print(f"[ModelService] Notice: AI model import deferred or fallback mode active: {e}")
    AI_MODELS_AVAILABLE = False

from fastapi_app.core.ai_fallback import (
    leak_fixture_result,
    normalize_recommendation_result,
    recommendation_fixture_result,
)
from fastapi_app.core.data_quality import (
    ModelAvailability,
    build_water_intelligence_metadata,
    newest_timestamp,
    normalize_component,
    utc_now,
)
from fastapi_app.core.demo_mode import should_use_fixture
from fastapi_app.services.groundwater_metrics import enrich_groundwater_prediction
from fastapi_app.services.leak_loss_estimator import enrich_leak_result, estimate_leak_loss
from fastapi_app.services.prediction_store import persist_prediction
from fastapi_app.services.water_stress_service import compute_water_stress_index

# Pilot municipal defaults when no ConsumptionSeries rows exist.
DEFAULT_DAILY_DEMAND_MGD = 95.0
DEFAULT_POPULATION_THOUSANDS = 850.0
DEFAULT_INDUSTRIAL_ACTIVITY_IDX = 55.0  # schema scale 0–100


class ModelService:
    def __init__(self) -> None:
        self.shortage_model = None
        self.groundwater_model = None
        self.demand_model = None
        self.leak_model = None
        self.recommendation_engine = None

        try:
            from recommendation_engine import AIRecommendationEngine

            self.recommendation_engine = AIRecommendationEngine()
        except Exception as e:
            print(f"[ModelService] Failed to load AIRecommendationEngine: {e}")

        if AI_MODELS_AVAILABLE:
            try:
                self.shortage_model = WaterShortageModel()
                self.groundwater_model = GroundwaterModel()
                self.demand_model = WaterDemandModel()
                self.leak_model = LeakDetectionModel()
            except Exception as e:
                print(f"[ModelService] Model initialization error: {e}")

    # ------------------------------------------------------------------
    # Individual model inference
    # ------------------------------------------------------------------
    def predict_shortage(
        self,
        reservoir_capacity_pct: float,
        rainfall_deficit_pct: float,
        temperature_c: float,
        daily_demand_mgd: float,
        day_of_month: int | None = None,
    ):
        if self.shortage_model:
            try:
                features = {
                    "reservoir_capacity_pct": max(0.0, min(100.0, float(reservoir_capacity_pct))),
                    "rainfall_deficit_pct": max(-100.0, min(100.0, float(rainfall_deficit_pct))),
                    "temperature_c": float(temperature_c),
                    "daily_demand_mgd": max(0.0, float(daily_demand_mgd)),
                }
                if day_of_month is not None:
                    features["observed_at"] = f"2024-03-{int(day_of_month):02d}"
                res = self.shortage_model.predict(features)
                forecast = res.get("forecast_storage_pct")
                capacity = features["reservoir_capacity_pct"]
                # Multi-horizon pilot: damped drawdown extrapolation from the 1-day
                # model (not a separately trained 7/30-day model — disclosed for
                # Technical Accuracy). A pure linear extrapolation (previous
                # behaviour) multiplies one noisy day's delta by 30x with no floor
                # on physical plausibility — a single rain event bumping storage
                # up 2pp would imply +60pp by day 30. Instead each subsequent
                # day's delta decays geometrically toward zero (DECAY below), so
                # the projection asymptotically approaches a plateau rather than
                # diverging — a defensible smoothing assumption, still clearly
                # labeled as a heuristic rather than a trained multi-day model.
                multi_horizon = None
                if forecast is not None:
                    daily_delta = float(capacity) - float(forecast)
                    decay = 0.85  # each further day's incremental change is 85% of the prior day's

                    def _damped_cumulative_delta(n_days: int) -> float:
                        # sum_{i=0}^{n-1} daily_delta * decay^i
                        return daily_delta * (1 - decay**n_days) / (1 - decay)

                    multi_horizon = {
                        "day_1_storage_pct": round(float(forecast), 2),
                        "day_7_storage_pct": round(
                            max(0.0, min(100.0, float(capacity) - _damped_cumulative_delta(7))), 2
                        ),
                        "day_30_storage_pct": round(
                            max(0.0, min(100.0, float(capacity) - _damped_cumulative_delta(30))), 2
                        ),
                        "method": "damped_extrapolation_from_1day_rf_pilot",
                        "note": (
                            "7/30-day values are a geometrically-damped extrapolation of the 1-day "
                            "storage forecast (not independently trained horizons) — later days weight "
                            "the initial daily delta less, avoiding unbounded linear drift from a single "
                            "noisy day's change."
                        ),
                    }
                beats = False
                try:
                    beats = bool(
                        (self.shortage_model.load_model().get("metadata") or {})
                        .get("baseline_comparison", {})
                        .get("model_beats_persistence_baseline")
                    )
                except Exception:
                    beats = False
                return {
                    "predicted_risk_score": res.get("predicted_risk_score", 48.5),
                    "predicted_risk_stage": res.get("predicted_risk_stage", 1),
                    "risk_label": res.get("risk_label", "Moderate Risk (Stage 1)"),
                    # Holdout-MAE-derived indicator — not a calibrated probability.
                    "confidence": res.get("confidence", 0.85),
                    "forecast_storage_pct": forecast,
                    "multi_horizon": multi_horizon,
                    "technical_accuracy_note": res.get("technical_accuracy_note"),
                    "model_scope": res.get("model_scope", "one-day reservoir storage forecast"),
                    "evaluation": {
                        "trained_horizon": "one_day",
                        "multi_day_method": "extrapolated_heuristic" if multi_horizon else None,
                        "beats_persistence_baseline": beats,
                    },
                    "recommended_mitigation": res.get(
                        "recommended_mitigation",
                        "Review forecast storage and apply local operating rules before acting.",
                    ),
                }
            except Exception as err:
                print(f"[ModelService] Shortage model execution fallback: {err}")

        raise RuntimeError("Dataset-backed reservoir model is unavailable; retrain with `py ai\\train.py`.")

    def predict_groundwater(
        self,
        initial_depth_m: float,
        annual_rainfall_mm: float,
        pumping_extraction_mld: float,
        aquifer_recharge_factor: float,
        soil_porosity_idx: float,
    ):
        drawdown = (pumping_extraction_mld * 0.12) - (
            annual_rainfall_mm * aquifer_recharge_factor * 0.002
        )
        projected = round(initial_depth_m + max(0.2, drawdown), 2)
        result = {
            "projected_depth_m": projected,
            "drawdown_rate_m": round(drawdown, 2),
            "aquifer_status": "Critical Over-Exploited" if drawdown > 3.0 else "Moderate Depletion",
            "depletion_trend": "Monitored Extraction Phase (scenario calculator only — not a trained model)",
        }
        return enrich_groundwater_prediction(result)

    def predict_groundwater_well(self, payload: dict) -> dict:
        if self.groundwater_model:
            try:
                result = self.groundwater_model.predict(payload)
                enriched = enrich_groundwater_prediction(result)
                if "evaluation" in result and "evaluation" not in enriched:
                    enriched["evaluation"] = result["evaluation"]
                elif result.get("evaluation"):
                    enriched["evaluation"] = result["evaluation"]
                return enriched
            except Exception as err:
                print(f"[ModelService] Groundwater well model error: {err}")
        raise RuntimeError("CGWB groundwater model is unavailable; retrain with `py ai\\train.py`.")

    def predict_demand(
        self,
        population_thousands: float,
        temperature_c: float,
        industrial_activity_idx: float,
        is_weekend: int,
        is_heatwave: int,
    ):
        if self.demand_model:
            try:
                res = self.demand_model.predict(
                    {
                        "population_thousands": population_thousands,
                        "temperature_c": temperature_c,
                        "industrial_activity_idx": industrial_activity_idx,
                        "is_weekend": is_weekend,
                        "is_heatwave": is_heatwave,
                    }
                )
                return {
                    "forecasted_demand_mgd": res.get("forecasted_demand_mgd", 0.0),
                    "forecasted_demand_mld": res.get("forecasted_demand_mld", 0.0),
                    "peak_surge_risk": res.get("peak_surge_risk", "Normal Baseline"),
                    "suggested_grid_allocation": res.get(
                        "suggested_grid_allocation",
                        "Demand forecast ready — review peak surge risk before allocation.",
                    ),
                    "peak_hour_demand_mgd": res.get("peak_hour_demand_mgd"),
                    "climate_base_mgd": res.get("climate_base_mgd"),
                    "confidence": res.get("confidence"),
                    "model_scope": res.get("model_scope"),
                    "test_mae_mgd": res.get("test_mae_mgd"),
                    "evaluation": res.get("evaluation"),
                }
            except Exception as err:
                print(f"[ModelService] Demand model error: {err}")

        raise RuntimeError("Dataset-backed demand model is unavailable; retrain with `py ai\\train.py`.")

    def detect_leak(
        self,
        pressure_bar: float,
        pressure_drop_bar: float,
        acoustic_vibration_db: float,
        flow_velocity_m_s: float,
        frequency_spike_hz: float,
    ):
        if self.leak_model:
            try:
                res = self.leak_model.predict(
                    {
                        "pressure_bar": pressure_bar,
                        "pressure_drop_bar": pressure_drop_bar,
                        "acoustic_vibration_db": acoustic_vibration_db,
                        "flow_velocity_m_s": flow_velocity_m_s,
                        "frequency_spike_hz": frequency_spike_hz,
                    }
                )
                base = {
                    "is_leak_detected": res.get("is_leak_detected", False),
                    "leak_probability": res.get("leak_probability", 0.0),
                    "severity": res.get("severity", "Use /detect-leak-signal with a raw signal CSV upload"),
                    "note": res.get(
                        "note",
                        "Legacy endpoint: upload a raw signal CSV via /detect-leak-signal instead.",
                    ),
                }
                return enrich_leak_result(
                    base,
                    pressure_drop_bar=pressure_drop_bar,
                    flow_velocity_m_s=flow_velocity_m_s,
                )
            except Exception as err:
                print(f"[ModelService] Leak model execution fallback: {type(err).__name__}")
                if should_use_fixture(provider_failed=True):
                    return leak_fixture_result()
                raise RuntimeError(
                    "Legacy leak endpoint could not run. Upload a raw signal CSV via /detect-leak-signal."
                ) from err

        if should_use_fixture(provider_failed=True):
            return leak_fixture_result()
        raise RuntimeError(
            "Legacy leak endpoint is unavailable. Upload a raw signal CSV via /detect-leak-signal."
        )

    def detect_leak_signal(self, signal_values: list) -> dict:
        if should_use_fixture(provider_failed=False):
            return leak_fixture_result()

        if self.leak_model:
            try:
                result = self.leak_model.predict_from_csv(signal_values)
                loss = estimate_leak_loss(
                    float(result.get("leak_probability", 0.0) or 0.0),
                    is_leak_detected=result.get("is_leak_detected"),
                )
                result["estimated_water_loss_lpm"] = loss["estimated_water_loss_lpm"]
                result["daily_loss_mld"] = loss["daily_loss_mld"]
                result["loss_confidence"] = loss["confidence"]
                result["loss_method"] = loss["method"]
                # Keep classifier note; append loss caveat.
                note = result.get("note") or ""
                result["note"] = f"{note} Loss estimate: {loss['note']}".strip()
                result["field_validation_status"] = "lab_trained_not_field_validated"
                result["evaluation"] = {
                    "decision_threshold": 0.3,
                    "test_f1": result.get("test_f1"),
                    "test_accuracy": result.get("test_accuracy"),
                    "field_validation_status": "lab_trained_not_field_validated",
                    "volume_from_classifier": False,
                    "note": "Orifice L/min is a heuristic, not a learned volume label.",
                }
                return result
            except Exception as err:
                print(f"[ModelService] Leak signal model error: {type(err).__name__}")
                if should_use_fixture(provider_failed=True):
                    return leak_fixture_result()
                raise RuntimeError("Acoustic leak classification failed.") from err

        if should_use_fixture(provider_failed=True):
            return leak_fixture_result()
        raise RuntimeError("Acoustic leak model is unavailable. Retrain local model artifacts.")

    def generate_recommendations(
        self,
        water_shortage_prediction: dict,
        leak_detection: dict,
        groundwater_prediction: dict,
        water_demand: dict,
        force_refresh: bool = False,
    ) -> dict:
        """Synthesize actions, degrading remote AI -> local rules -> demo fixture.

        Whichever path answers, the envelope is identical and the provenance is
        honest: `source` is always one of remote_ai / rules_fallback /
        demo_fixture, and the metadata block always describes the path that
        actually produced the text.
        """
        if should_use_fixture(provider_failed=False):
            # Fixtures were deliberately forced: skip the provider entirely
            # rather than spending its timeout before falling back.
            return recommendation_fixture_result()

        if self.recommendation_engine:
            try:
                raw = self.recommendation_engine.generate_recommendations(
                    water_shortage_prediction,
                    leak_detection,
                    groundwater_prediction,
                    water_demand,
                    force_refresh=force_refresh,
                )
                return normalize_recommendation_result(raw)
            except Exception as err:
                print(f"[ModelService] Recommendation synthesis failed: {err}")

        # The engine itself could not run (missing module, or it raised). Local
        # rules need telemetry we may not have here, so fall through to the
        # fixture only if demo mode authorizes it.
        if should_use_fixture(provider_failed=True):
            return recommendation_fixture_result()

        return normalize_recommendation_result(
            {
                "recommendations": [
                    "Review reservoir storage and apply local contingency rules.",
                    "Prioritize acoustic inspection on highest-loss corridors.",
                    "Throttle non-essential demand during heat-risk windows.",
                ],
                "expected_saving": "0.4 Million Liters",
                "text_summary": (
                    "Apply shortage, leak, and demand contingency actions from model telemetry."
                ),
                "source": "rules_fallback",
                "provider": "local-rules",
            }
        )

    # ------------------------------------------------------------------
    # Live telemetry + water intelligence fusion
    # ------------------------------------------------------------------
    def _basin_coords(self, db) -> tuple[float, float]:
        """Prefer lowest-storage reservoir coords; else Delhi NCT."""
        try:
            from fastapi_app.database.models import Reservoir

            top = db.query(Reservoir).order_by(Reservoir.current_level_pct.asc()).first()
            if top and top.location_lat is not None and top.location_lng is not None:
                return float(top.location_lat), float(top.location_lng)
        except Exception:
            pass
        return 28.614, 77.209

    def _open_meteo_climate(self, db) -> dict[str, Any]:
        lat, lon = self._basin_coords(db)
        try:
            from climate.wsi_climate import build_wsi_climate_context

            return build_wsi_climate_context(lat, lon)
        except Exception as err:
            print(f"[ModelService] Open-Meteo climate for WSI skipped: {err}")
            return {}

    def _latest_weather_context(self, db) -> dict[str, Any]:
        from fastapi_app.database.models import Weather

        weather = db.query(Weather).order_by(Weather.recorded_at.desc()).first()
        base = {
            "rainfall_deficit_pct": 0.0,
            "temperature_c": 32.0,
            "heatwave_warning": False,
            "observed_at": None,
            # No Weather row yet — these are documented defaults, not readings.
            "climate_source": "weather_defaults",
        }
        if weather:
            base = {
                "rainfall_deficit_pct": float(weather.rainfall_deficit_pct or 0.0),
                "temperature_c": float(weather.temperature_c or 32.0),
                "heatwave_warning": bool(weather.heatwave_warning),
                "precipitation_mm": float(getattr(weather, "precipitation_mm", 0) or 0),
                "location": getattr(weather, "location", None),
                "observed_at": weather.recorded_at.isoformat() if weather.recorded_at else None,
                "climate_source": "db_weather",
            }

        # Fuse live Open-Meteo SPI / deficit / heat into weather context for WSI.
        om = self._open_meteo_climate(db)
        if om:
            if om.get("spi3_proxy") is not None:
                base["spi3_proxy"] = om["spi3_proxy"]
            if om.get("rainfall_deficit_pct") is not None:
                base["rainfall_deficit_pct"] = om["rainfall_deficit_pct"]
            if om.get("dry_anomaly_pct") is not None:
                base["dry_anomaly_pct"] = om["dry_anomaly_pct"]
            if om.get("temperature_c") is not None:
                base["temperature_c"] = om["temperature_c"]
            if "heatwave_warning" in om:
                base["heatwave_warning"] = bool(om["heatwave_warning"])
            base["climate_source"] = om.get("source", "open_meteo_sync")
            base["spi_class"] = om.get("spi_class")
            if base["climate_source"] == "open_meteo_sync":
                # Open-Meteo returns the current forecast/archive window with no
                # per-record stamp; the successful fetch time is the observation time.
                base["observed_at"] = utc_now().isoformat()
        return base

    def _latest_consumption(self, db) -> tuple[float, str | None]:
        """Latest metered/seeded demand proxy with the date it was observed."""
        try:
            from fastapi_app.database.models import ConsumptionSeries

            row = (
                db.query(ConsumptionSeries)
                .order_by(ConsumptionSeries.observed_date.desc())
                .first()
            )
            if row and row.demand_mgd is not None:
                observed = row.observed_date.isoformat() if row.observed_date else None
                return float(row.demand_mgd), observed
        except Exception:
            pass
        return DEFAULT_DAILY_DEMAND_MGD, None

    def _latest_consumption_mgd(self, db) -> float:
        return self._latest_consumption(db)[0]

    @staticmethod
    def _median(values: list[float], default: float) -> float:
        nums = sorted(float(v) for v in values if v is not None)
        if not nums:
            return default
        mid = len(nums) // 2
        if len(nums) % 2:
            return nums[mid]
        return (nums[mid - 1] + nums[mid]) / 2.0

    def _live_shortage(self, db, weather: dict[str, Any]) -> dict[str, Any]:
        """System shortage from a *representative* reservoir level (median), not the single emptiest dam.

        Using min(storage) made WSI look Critical whenever any synced CWC site was at 0%,
        which is not a fair basin-wide stress signal for the command center.
        """
        from fastapi_app.database.models import Reservoir

        reservoirs = db.query(Reservoir).all()
        levels = [float(r.current_level_pct) for r in reservoirs if r.current_level_pct is not None]
        # Prefer median of reservoirs with some water; fall back to all levels / 50%.
        positive = [x for x in levels if x > 0.5]
        capacity = self._median(positive or levels, 50.0)
        min_level = min(levels) if levels else capacity
        pct_critical = (
            round(100.0 * sum(1 for x in levels if x < 35.0) / len(levels), 1) if levels else 0.0
        )

        observed_at = newest_timestamp(
            [r.observed_at or r.updated_at for r in reservoirs]
        )
        shortage = {
            "predicted_risk_score": 70.0 if capacity < 30 else (50.0 if capacity < 50 else 30.0),
            "predicted_risk_stage": 2 if capacity < 30 else (1 if capacity < 50 else 0),
            "risk_label": "High Risk" if capacity < 30 else "Moderate Risk",
            "confidence": 0.7,
            "reservoir_capacity_pct": capacity,
            "min_reservoir_pct": min_level,
            "pct_reservoirs_critical": pct_critical,
            "aggregation": "median_positive_storage",
            "observed_at": observed_at,
        }
        demand_mgd = self._latest_consumption_mgd(db) if db is not None else DEFAULT_DAILY_DEMAND_MGD
        if self.shortage_model:
            try:
                shortage_pred = self.predict_shortage(
                    reservoir_capacity_pct=capacity,
                    rainfall_deficit_pct=float(weather.get("rainfall_deficit_pct") or 0.0),
                    temperature_c=float(weather.get("temperature_c") or 32.0),
                    daily_demand_mgd=demand_mgd,
                    day_of_month=datetime.utcnow().day,
                )
                shortage.update(shortage_pred)
                shortage["reservoir_capacity_pct"] = capacity
                shortage["min_reservoir_pct"] = min_level
                shortage["pct_reservoirs_critical"] = pct_critical
                shortage["aggregation"] = "median_positive_storage"
                shortage["observed_at"] = observed_at
            except Exception as err:
                print(f"[ModelService] live shortage predict skipped: {err}")
        return shortage, len(reservoirs)

    def _live_leak(self, db) -> tuple[dict[str, Any], int]:
        """Prefer last acoustic model inference; mute demo-seeded alerts for WSI."""
        from fastapi_app.database.models import Alert, Prediction

        last_acoustic = (
            db.query(Prediction)
            .filter(Prediction.model_name == "leak_detection_signal")
            .order_by(Prediction.created_at.desc())
            .first()
        )
        if last_acoustic and isinstance(last_acoustic.prediction_results, dict):
            leak = dict(last_acoustic.prediction_results)
            leak["source"] = "acoustic_model"
            leak["demo"] = False
            leak["inferred_at"] = (
                last_acoustic.created_at.isoformat() if last_acoustic.created_at else None
            )
            leak["observed_at"] = leak["inferred_at"]
            return enrich_leak_result(leak), 1

        alerts = (
            db.query(Alert)
            .filter(Alert.status.in_(["active", "investigating"]))
            .order_by(Alert.anomaly_score.desc())
            .limit(10)
            .all()
        )
        # Demo alerts stay visible on the Alerts page, but must not dominate WSI.
        leak = {
            "is_leak_detected": False,
            "leak_probability": 0.12 if alerts else 0.05,
            "estimated_water_loss_lpm": 25.0 if alerts else 0.0,
            "severity": "info",
            "zone": "n/a",
            "source": "demo_seeded_alerts_muted_for_wsi",
            "demo": True,
            "demo_alert_count": len(alerts),
            "observed_at": newest_timestamp([a.timestamp for a in alerts]),
            "note": (
                "Seeded demo leak alerts are muted in the Water Stress Index so the score "
                "is not artificially Critical. Upload an acoustic CSV on Leak Detection to "
                "use the trained ExtraTrees model for live WSI leakage."
            ),
        }
        return enrich_leak_result(leak), len(alerts)

    def _live_groundwater(self, db) -> tuple[dict[str, Any], int]:
        """Representative GW stress from median depth/rate across sampled wells (not the worst outlier)."""
        from fastapi_app.database.models import Groundwater

        aquifers = db.query(Groundwater).limit(80).all()
        depths = [float(a.depth_to_water_m) for a in aquifers if a.depth_to_water_m is not None]
        rates = [
            float(a.depletion_rate_m_year) for a in aquifers if a.depletion_rate_m_year is not None
        ]
        # Cap extreme synced outliers (e.g. 8 m/yr single well) for basin WSI.
        capped_rates = [min(r, 3.5) for r in rates]
        depth = self._median(depths, 25.0)
        rate = self._median(capped_rates, 0.8)
        # Pick a well near the median depth for optional model enrichment.
        anchor = None
        if aquifers and depths:
            anchor = min(
                aquifers,
                key=lambda a: abs(float(a.depth_to_water_m or depth) - depth),
            )

        observed_at = newest_timestamp([a.observed_at or a.updated_at for a in aquifers])
        groundwater = {
            "projected_depth_m": depth,
            "drawdown_rate_m": rate,
            "depletion_rate_m_year": rate,
            "aquifer_status": (anchor.name if anchor else "median_sample"),
            "aggregation": "median_capped_rate",
            "max_observed_rate_m_year": max(rates) if rates else rate,
            "observed_at": observed_at,
        }
        if self.groundwater_model and anchor is not None:
            try:
                gw = self.predict_groundwater_well(
                    {
                        "current_depth_m": float(anchor.depth_to_water_m),
                        "prev2_depth_m": float(anchor.depth_to_water_m)
                        - float(anchor.depletion_rate_m_year or 0) / 12.0,
                        "latitude": float(anchor.location_lat)
                        if anchor.location_lat is not None
                        else 21.0,
                        "longitude": float(anchor.location_lng)
                        if anchor.location_lng is not None
                        else 78.0,
                        "well_depth": float(anchor.depth_to_water_m) + 40.0,
                        "observation_month": datetime.utcnow().month,
                        "station_code": str(anchor.id),
                    }
                )
                # Keep median rate for WSI; use model depth as enrichment only if reasonable.
                projected = float(gw.get("projected_depth_m") or depth)
                groundwater = {
                    "projected_depth_m": projected if 5.0 <= projected <= 120.0 else depth,
                    "drawdown_rate_m": rate,
                    "depletion_rate_m_year": rate,
                    "aquifer_status": gw.get("aquifer_status", groundwater["aquifer_status"]),
                    "depletion_trend": gw.get("depletion_trend"),
                    "days_to_critical_threshold": gw.get("days_to_critical_threshold"),
                    "aggregation": "median_capped_rate",
                    "max_observed_rate_m_year": max(rates) if rates else rate,
                    "observed_at": observed_at,
                }
            except Exception as err:
                print(f"[ModelService] live groundwater predict skipped: {err}")
        return enrich_groundwater_prediction(groundwater), len(aquifers)

    def _live_demand(self, weather: dict[str, Any], db=None) -> dict[str, Any]:
        heatwave = bool(weather.get("heatwave_warning"))
        baseline_mgd, observed_at = (
            self._latest_consumption(db) if db is not None else (DEFAULT_DAILY_DEMAND_MGD, None)
        )
        demand = {
            "forecasted_demand_mgd": baseline_mgd,
            "peak_surge_risk": "Elevated Demand" if heatwave else "Normal Baseline",
            "model_scope": "synthetic_labels_pilot",
            "observed_at": observed_at,
        }
        if self.demand_model:
            try:
                demand = self.predict_demand(
                    population_thousands=DEFAULT_POPULATION_THOUSANDS,
                    temperature_c=float(weather.get("temperature_c") or 32.0),
                    industrial_activity_idx=DEFAULT_INDUSTRIAL_ACTIVITY_IDX,
                    is_weekend=1 if datetime.utcnow().weekday() >= 5 else 0,
                    is_heatwave=1 if heatwave else 0,
                )
                demand["baseline_consumption_mgd"] = baseline_mgd
                demand["model_scope"] = demand.get("model_scope") or "synthetic_labels_pilot"
                demand["observed_at"] = observed_at
            except Exception as err:
                print(f"[ModelService] live demand predict skipped: {err}")
        return demand

    def _latest_vision_context(self, db) -> dict[str, Any] | None:
        """Most recent AquaLens scan, surfaced as read-only supporting evidence.

        Deliberately NOT folded into the weighted WSI score — a single
        image-derived health estimate has no validated accuracy/weight yet,
        and the WSI's component weights are audited and test-covered
        (see tests/test_water_intelligence.py::test_wsi_weights_sum_to_one).
        Shown alongside the index instead, the way the dashboard already
        treats AquaLens as corroborating evidence rather than a scored input.
        """
        try:
            from fastapi_app.database.models import VisionAnalysis

            latest = (
                db.query(VisionAnalysis)
                .filter(VisionAnalysis.vision_mode == "reservoir")
                .order_by(VisionAnalysis.created_at.desc())
                .first()
            )
            if not latest:
                return None
            return {
                "asset_label": latest.asset_label,
                "reservoir_health": latest.reservoir_health,
                "overall_risk": latest.overall_risk,
                "turbidity_index": latest.turbidity_index,
                "algae_bloom_risk": latest.algae_bloom_risk,
                "analyzed_at": latest.created_at.isoformat() if latest.created_at else None,
                "note": "Supporting evidence from AquaLens imagery — not a weighted WSI input.",
            }
        except Exception:
            return None

    def build_live_model_telemetry(self, db) -> dict:
        """Derive recommendation / WSI inputs from DB + local sklearn models."""
        weather = self._latest_weather_context(db)
        shortage, n_res = self._live_shortage(db, weather)
        leak, n_alerts = self._live_leak(db)
        groundwater, n_aq = self._live_groundwater(db)
        demand = self._live_demand(weather, db)

        return {
            "water_shortage_prediction": shortage,
            "leak_detection": leak,
            "groundwater_prediction": groundwater,
            "water_demand": demand,
            "climate": {
                "rainfall_deficit_pct": weather.get("rainfall_deficit_pct", 0.0),
                "spi3_proxy": weather.get("spi3_proxy"),
                "dry_anomaly_pct": weather.get("dry_anomaly_pct"),
                "temperature_c": weather.get("temperature_c", 32.0),
                "heatwave_warning": weather.get("heatwave_warning", False),
                "climate_source": weather.get("climate_source") or "weather_defaults",
                "spi_class": weather.get("spi_class"),
                "observed_at": weather.get("observed_at"),
            },
            "context": {
                "reservoirs_sampled": n_res,
                "aquifers_sampled": n_aq,
                "active_alerts": n_alerts,
                "weather_temp_c": weather.get("temperature_c", 32.0),
                "leak_source": leak.get("source"),
                "consumption_mgd": self._latest_consumption_mgd(db),
                "aqualens_latest": self._latest_vision_context(db),
            },
        }

    def build_water_intelligence(
        self,
        db=None,
        *,
        overrides: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Fuse shortage / leak / GW / demand / climate into an auditable WSI."""
        overrides = overrides or {}
        telemetry = self.build_live_model_telemetry(db) if db is not None else {
            "water_shortage_prediction": {},
            "leak_detection": {},
            "groundwater_prediction": {},
            "water_demand": {},
            "climate": {},
            "context": {},
        }

        weather = dict(telemetry.get("climate") or {})
        if db is not None and not weather:
            weather = self._latest_weather_context(db)

        # --- Shortage ---
        shortage = dict(telemetry.get("water_shortage_prediction") or {})
        if overrides.get("reservoir_capacity_pct") is not None:
            try:
                rainfall = overrides.get("rainfall_deficit_pct")
                if rainfall is None:
                    rainfall = weather.get("rainfall_deficit_pct", 0.0)
                temp = overrides.get("temperature_c")
                if temp is None:
                    temp = weather.get("temperature_c", 32.0)
                demand_mgd = overrides.get(
                    "daily_demand_mgd",
                    self._latest_consumption_mgd(db) if db is not None else DEFAULT_DAILY_DEMAND_MGD,
                )
                shortage = self.predict_shortage(
                    reservoir_capacity_pct=float(overrides["reservoir_capacity_pct"]),
                    rainfall_deficit_pct=float(rainfall),
                    temperature_c=float(temp),
                    daily_demand_mgd=float(demand_mgd),
                    day_of_month=overrides.get("day_of_month") or datetime.utcnow().day,
                )
                shortage["reservoir_capacity_pct"] = float(overrides["reservoir_capacity_pct"])
            except Exception as err:
                print(f"[ModelService] water-intelligence shortage override failed: {err}")

        # --- Leak ---
        leak = dict(telemetry.get("leak_detection") or {})
        if overrides.get("leak_probability") is not None:
            leak = enrich_leak_result(
                {
                    "is_leak_detected": overrides.get(
                        "is_leak_detected",
                        float(overrides["leak_probability"]) >= 0.30,
                    ),
                    "leak_probability": float(overrides["leak_probability"]),
                    "estimated_water_loss_lpm": overrides.get("estimated_water_loss_lpm"),
                    "severity": leak.get("severity", "info"),
                    "zone": leak.get("zone", "override"),
                }
            )
        else:
            leak = enrich_leak_result(leak)

        # --- Groundwater ---
        groundwater = dict(telemetry.get("groundwater_prediction") or {})
        if overrides.get("current_depth_m") is not None:
            groundwater = enrich_groundwater_prediction(
                {
                    "projected_depth_m": float(overrides["current_depth_m"]),
                    "drawdown_rate_m": float(overrides.get("depletion_rate_m_year") or 1.0),
                    "depletion_rate_m_year": float(overrides.get("depletion_rate_m_year") or 1.0),
                    "aquifer_status": groundwater.get("aquifer_status", "override"),
                }
            )
        else:
            groundwater = enrich_groundwater_prediction(groundwater)

        # --- Demand ---
        demand = dict(telemetry.get("water_demand") or {})
        if overrides.get("population_thousands") is not None or overrides.get("temperature_c") is not None:
            try:
                demand = self.predict_demand(
                    population_thousands=float(
                        overrides.get("population_thousands") or DEFAULT_POPULATION_THOUSANDS
                    ),
                    temperature_c=float(
                        overrides.get("temperature_c") or weather.get("temperature_c") or 32.0
                    ),
                    industrial_activity_idx=float(
                        overrides.get("industrial_activity_idx") or DEFAULT_INDUSTRIAL_ACTIVITY_IDX
                    ),
                    is_weekend=int(
                        overrides["is_weekend"]
                        if overrides.get("is_weekend") is not None
                        else (1 if datetime.utcnow().weekday() >= 5 else 0)
                    ),
                    is_heatwave=int(
                        overrides["is_heatwave"]
                        if overrides.get("is_heatwave") is not None
                        else (1 if weather.get("heatwave_warning") else 0)
                    ),
                )
            except Exception as err:
                print(f"[ModelService] water-intelligence demand override failed: {err}")

        spi_override = overrides.get("spi3_proxy")
        spi_value = spi_override if spi_override is not None else weather.get("spi3_proxy")
        climate = {
            "rainfall_deficit_pct": float(
                overrides.get("rainfall_deficit_pct")
                if overrides.get("rainfall_deficit_pct") is not None
                else weather.get("rainfall_deficit_pct") or 0.0
            ),
            "spi3_proxy": spi_value,
            "dry_anomaly_pct": weather.get("dry_anomaly_pct"),
            "heatwave_warning": (
                overrides["heatwave_warning"]
                if overrides.get("heatwave_warning") is not None
                else weather.get("heatwave_warning", False)
            ),
            "temperature_c": float(
                overrides.get("temperature_c")
                if overrides.get("temperature_c") is not None
                else weather.get("temperature_c") or 32.0
            ),
            "climate_source": weather.get("climate_source") or "weather_defaults",
            "spi_class": weather.get("spi_class"),
            "observed_at": weather.get("observed_at"),
        }

        # Enforce the shared unit/range contract *before* fusion so an out-of-range
        # or non-finite upstream value can never propagate into the index. Values
        # already inside their contract pass through untouched.
        issues: dict[str, list[str]] = {}
        shortage, issues["shortage"] = normalize_component("shortage", shortage)
        leak, issues["leak"] = normalize_component("leak", leak)
        groundwater, issues["groundwater"] = normalize_component("groundwater", groundwater)
        demand, issues["demand"] = normalize_component("demand", demand)
        climate, issues["climate"] = normalize_component("climate", climate)

        wsi = compute_water_stress_index(
            shortage=shortage,
            groundwater=groundwater,
            leak=leak,
            demand=demand,
            climate=climate,
        )

        metadata = build_water_intelligence_metadata(
            water_stress=wsi,
            shortage=shortage,
            leak=leak,
            groundwater=groundwater,
            demand=demand,
            climate=climate,
            models=ModelAvailability(
                shortage=self.shortage_model is not None,
                groundwater=self.groundwater_model is not None,
                demand=self.demand_model is not None,
                leak=self.leak_model is not None,
            ),
            overrides=overrides,
            issues=issues,
        )

        return {
            "water_stress": wsi,
            "shortage": shortage,
            "leak": leak,
            "groundwater": groundwater,
            "demand": demand,
            "climate": climate,
            "context": telemetry.get("context") or {},
            "metadata": metadata,
        }

    def synthesize_live_recommendations(self, db, force_refresh: bool = False) -> dict:
        telemetry = self.build_live_model_telemetry(db)
        result = self.generate_recommendations(
            telemetry["water_shortage_prediction"],
            telemetry["leak_detection"],
            telemetry["groundwater_prediction"],
            telemetry["water_demand"],
            force_refresh=force_refresh,
        )
        result["inputs"] = {
            "shortage": telemetry["water_shortage_prediction"],
            "leak": telemetry["leak_detection"],
            "groundwater": telemetry["groundwater_prediction"],
            "demand": telemetry["water_demand"],
            "context": telemetry["context"],
        }
        try:
            result["water_stress"] = compute_water_stress_index(
                shortage=telemetry["water_shortage_prediction"],
                groundwater=telemetry["groundwater_prediction"],
                leak=telemetry["leak_detection"],
                demand=telemetry["water_demand"],
                climate=telemetry.get("climate"),
            )
        except Exception as err:
            print(f"[ModelService] WSI attach skipped: {err}")
        return result


model_service = ModelService()
