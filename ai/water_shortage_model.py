"""Dataset-backed, short-horizon reservoir availability model.

Trains on CWC March 2024 daily reservoir storage and joins NASA POWER Delhi
weather by calendar date (temperature + precipitation) as a climate proxy.
Demand is applied as a transparent post-model risk adjustment, not as an RF feature.

Limitations are recorded in model metadata — this remains a pilot, not a
multi-week drought or SCADA control system.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error

AI_DIR = Path(__file__).resolve().parent
PROJECT_DIR = AI_DIR.parent
DEFAULT_DATA_PATH = (
    PROJECT_DIR
    / "Aqua Dataset"
    / "Reservoir level datase"
    / "Daily_data_of_reservoir_level_of_Central_Water_Commission_(CWC)_Agency_during_March_2024.csv"
)
WEATHER_PATH = (
    PROJECT_DIR
    / "Aqua Dataset"
    / "Historical India weather CSV"
    / "POWER_Point_Daily_20100101_20251231_028d61N_077d21E_LST.csv"
)
IMPORTED_DATA_PATH = PROJECT_DIR / "data" / "imports" / "reservoir_latest.csv"
MODEL_PATH = AI_DIR / "water_shortage_model.pkl"
METADATA_PATH = AI_DIR / "water_shortage_model.metadata.json"
FEATURES = ["storage_pct", "day_of_month", "temperature_c", "rainfall_deficit_pct"]


class WaterShortageModel:
    """Predict one-day-ahead reservoir storage percentage from CWC + weather."""

    def _load_weather(self) -> pd.DataFrame:
        if not WEATHER_PATH.exists():
            raise FileNotFoundError(f"NASA POWER weather file not found: {WEATHER_PATH}")
        # Skip NASA POWER preamble until the YEAR header row.
        header_row = 0
        with WEATHER_PATH.open("r", encoding="utf-8", errors="ignore") as handle:
            for idx, line in enumerate(handle):
                if line.startswith("YEAR"):
                    header_row = idx
                    break
        raw = pd.read_csv(WEATHER_PATH, skiprows=header_row)
        cols = {str(c).strip().upper(): c for c in raw.columns}
        year_col = cols.get("YEAR")
        mo_col = cols.get("MO")
        dy_col = cols.get("DY")
        t_col = cols.get("T2M")
        p_col = cols.get("PRECTOTCORR")
        if not all([year_col, mo_col, dy_col, t_col, p_col]):
            raise ValueError("Weather CSV missing YEAR/MO/DY/T2M/PRECTOTCORR columns.")
        weather = pd.DataFrame(
            {
                "Date": pd.to_datetime(
                    dict(year=raw[year_col], month=raw[mo_col], day=raw[dy_col]),
                    errors="coerce",
                ),
                "temperature_c": pd.to_numeric(raw[t_col], errors="coerce"),
                "precip_mm": pd.to_numeric(raw[p_col], errors="coerce"),
            }
        ).dropna(subset=["Date"])
        weather.loc[weather["temperature_c"] < -50, "temperature_c"] = np.nan
        weather.loc[weather["precip_mm"] < 0, "precip_mm"] = np.nan
        weather = weather.dropna(subset=["temperature_c", "precip_mm"])
        weather = weather.sort_values("Date")
        weather["precip_mean_30"] = weather["precip_mm"].rolling(30, min_periods=7).mean()
        weather["rainfall_deficit_pct"] = np.where(
            weather["precip_mean_30"] > 0.05,
            100.0 * (weather["precip_mm"] - weather["precip_mean_30"]) / weather["precip_mean_30"],
            0.0,
        )
        weather["rainfall_deficit_pct"] = weather["rainfall_deficit_pct"].clip(-100, 100)
        return weather[["Date", "temperature_c", "rainfall_deficit_pct", "precip_mm"]]

    def _prepared_rows(self) -> pd.DataFrame:
        data_path = IMPORTED_DATA_PATH if IMPORTED_DATA_PATH.exists() else DEFAULT_DATA_PATH
        if not data_path.exists():
            raise FileNotFoundError(f"CWC reservoir data not found: {data_path}")
        self.data_path = data_path
        data = pd.read_csv(data_path)
        data["Date"] = pd.to_datetime(data["Date"], errors="coerce")
        data["Storage"] = pd.to_numeric(data["Storage"], errors="coerce")
        data["Live_capacity_FRL"] = pd.to_numeric(data["Live_capacity_FRL"], errors="coerce")
        data["storage_pct"] = 100 * data["Storage"] / data["Live_capacity_FRL"]
        data.loc[
            ~np.isfinite(data["storage_pct"])
            | (data["storage_pct"] < 0)
            | (data["storage_pct"] > 100),
            "storage_pct",
        ] = np.nan
        data = data.dropna(subset=["Reservoir_name", "Date", "storage_pct"]).copy()
        data = data.sort_values(["Reservoir_name", "Date"])
        data["next_date"] = data.groupby("Reservoir_name")["Date"].shift(-1)
        data["next_storage_pct"] = data.groupby("Reservoir_name")["storage_pct"].shift(-1)
        data = data[(data["next_date"] - data["Date"]).dt.days.eq(1)].copy()
        data["day_of_month"] = data["Date"].dt.day

        weather = self._load_weather()
        data["Date"] = data["Date"].dt.normalize()
        weather["Date"] = weather["Date"].dt.normalize()
        data = data.merge(weather, on="Date", how="inner")
        self.weather_joined = True
        return data.dropna(subset=["next_storage_pct", "temperature_c", "rainfall_deficit_pct"])

    def train(self) -> dict:
        rows = self._prepared_rows()
        if len(rows) < 30:
            raise ValueError("Not enough consecutive CWC+weather observations to train a pilot model.")

        unique_dates = sorted(rows["Date"].unique())
        train_end = unique_dates[max(1, int(len(unique_dates) * 0.70)) - 1]
        validation_end = unique_dates[max(1, int(len(unique_dates) * 0.85)) - 1]
        train = rows[rows["Date"] <= train_end]
        validation = rows[(rows["Date"] > train_end) & (rows["Date"] <= validation_end)]
        test = rows[rows["Date"] > validation_end]
        if min(len(train), len(validation), len(test)) == 0:
            raise ValueError("Temporal split produced an empty partition.")

        model = RandomForestRegressor(n_estimators=150, min_samples_leaf=3, random_state=42, n_jobs=1)
        model.fit(train[FEATURES], train["next_storage_pct"])

        def metrics(frame: pd.DataFrame) -> dict:
            predicted = model.predict(frame[FEATURES])
            return {
                "mae_percentage_points": round(float(mean_absolute_error(frame["next_storage_pct"], predicted)), 4),
                "rmse_percentage_points": round(
                    float(mean_squared_error(frame["next_storage_pct"], predicted) ** 0.5), 4
                ),
                "rows": int(len(frame)),
            }

        def baseline_metrics(frame: pd.DataFrame) -> dict:
            """Naive 'tomorrow = today' persistence baseline.

            Reported alongside the model's own metrics rather than only in
            docs: with 30 days of source data at daily granularity, a next-
            day storage forecast can be dominated by autocorrelation, so a
            model that doesn't beat this baseline isn't demonstrating
            learned signal — that should be visible in the metadata itself,
            not just discovered by re-deriving it later.
            """
            predicted = frame["storage_pct"]
            return {
                "mae_percentage_points": round(float(mean_absolute_error(frame["next_storage_pct"], predicted)), 4),
                "rmse_percentage_points": round(
                    float(mean_squared_error(frame["next_storage_pct"], predicted) ** 0.5), 4
                ),
                "method": "persistence (predicted next_storage_pct = today's storage_pct)",
            }

        test_metrics = metrics(test)
        test_baseline = baseline_metrics(test)
        beats_baseline = test_metrics["mae_percentage_points"] < test_baseline["mae_percentage_points"]

        metadata = {
            "model_type": "RandomForestRegressor",
            "task": "one-day-ahead reservoir storage percentage forecast",
            "source": str(self.data_path.relative_to(PROJECT_DIR)),
            "weather_source": str(WEATHER_PATH.relative_to(PROJECT_DIR)),
            "weather_join": "Delhi NASA POWER joined by calendar date (climate proxy, not reservoir-station matched)",
            "source_coverage": {
                "start": str(rows["Date"].min().date()),
                "end": str(rows["Date"].max().date()),
            },
            "features": FEATURES,
            "target": "next_storage_pct",
            "demand_handling": "daily_demand_mgd adjusts risk score after forecast (not an RF feature)",
            "temporal_split": {
                "train_through": str(pd.Timestamp(train_end).date()),
                "validation_through": str(pd.Timestamp(validation_end).date()),
                "test_from": str(test["Date"].min().date()),
            },
            "metrics": {"validation": metrics(validation), "test": test_metrics},
            "baseline_comparison": {
                "test_persistence_baseline": test_baseline,
                "seasonal_naive": {
                    "status": "unsupported_insufficient_history",
                    "reason": (
                        "Source coverage is a single short calendar window — "
                        "prior-year same-calendar-day values are not available."
                    ),
                },
                "model_beats_persistence_baseline": beats_baseline,
                "note": (
                    "Model beats the naive 'no change' baseline on held-out test MAE."
                    if beats_baseline
                    else (
                        "Model does NOT beat the naive 'no change' baseline on held-out test MAE — "
                        "with only ~30 days of source data the 1-day-ahead task is dominated by "
                        "storage autocorrelation. Treat predicted_risk_score as directionally useful "
                        "only, not as evidence of learned weather/demand signal, until trained on a "
                        "longer multi-season dataset."
                    )
                ),
            },
            "model_name": "water_shortage_model",
            "algorithm": "RandomForestRegressor",
            "target_unit": "percentage_points (live storage fill %)",
            "random_seed": 42,
            "split_strategy": "chronological_by_unique_date (70% / 15% / 15%)",
            "multi_day_horizon": {
                "trained_output": "one_day",
                "day_7_and_day_30": "extrapolated_heuristic",
            },
            "limitations": [
                "Trained from a single March 2024 CWC extract; not a long-term drought model.",
                "Weather is Delhi NASA POWER joined by date — a climate proxy, not per-reservoir station weather.",
                "Demand stress is a transparent post-model adjustment, not learned from metered consumption labels.",
                "Risk bands are operational display rules based on the forecast, not observed shortage labels.",
                "Test partition spans only a handful of unique calendar days shared across all reservoirs; "
                "treat the reported row count as inflated relative to independent temporal observations.",
                "Does not claim geographic generalization beyond reservoirs present in the training extract.",
            ],
        }
        joblib.dump({"model": model, "features": FEATURES, "metadata": metadata}, MODEL_PATH)
        METADATA_PATH.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        self._cached_payload = {"model": model, "features": FEATURES, "metadata": metadata}
        return metadata

    def load_model(self) -> dict:
        cached = getattr(self, "_cached_payload", None)
        if cached is not None:
            return cached
        if MODEL_PATH.exists():
            payload = joblib.load(MODEL_PATH)
            if (
                isinstance(payload, dict)
                and "model" in payload
                and payload.get("features") == FEATURES
            ):
                self._cached_payload = payload
                return payload
        payload = {"model": None, "features": FEATURES, "metadata": self.train()}
        self._cached_payload = payload
        return payload

    def predict(self, input_features: dict) -> dict:
        payload = self.load_model()
        if payload.get("model") is None:
            payload = self.load_model()
        current_pct = float(input_features["reservoir_capacity_pct"])
        temperature_c = float(input_features.get("temperature_c", 30.0))
        rainfall_deficit_pct = float(input_features.get("rainfall_deficit_pct", 0.0))
        daily_demand_mgd = float(input_features.get("daily_demand_mgd", 80.0))
        observed_at = input_features.get("observed_at")
        try:
            day = pd.Timestamp(observed_at).day if observed_at else date.today().day
        except (TypeError, ValueError):
            day = date.today().day

        frame = pd.DataFrame(
            [[current_pct, day, temperature_c, rainfall_deficit_pct]],
            columns=FEATURES,
        )
        forecast_pct = float(payload["model"].predict(frame)[0])
        forecast_pct = max(0.0, min(100.0, forecast_pct))

        # Base risk from forecasted storage; demand adds transparent stress above a 80 MGD baseline.
        risk = 100.0 - forecast_pct
        demand_stress = max(0.0, (daily_demand_mgd - 80.0) * 0.12)
        risk = round(min(100.0, risk + demand_stress), 2)

        stage = 3 if forecast_pct < 15 or risk >= 85 else 2 if forecast_pct < 30 or risk >= 70 else 1 if forecast_pct < 50 or risk >= 50 else 0
        labels = ["Normal availability", "Watch", "High shortage risk", "Critical shortage risk"]
        test_mae = payload["metadata"]["metrics"]["test"]["mae_percentage_points"]
        reliability = round(max(0.0, min(1.0, 1 - test_mae / 100)), 2)
        baseline_note = (
            payload["metadata"].get("baseline_comparison", {}).get("note")
            or "Baseline comparison unavailable — retrain with `py ai\\train.py` to compute it."
        )
        return {
            "predicted_risk_score": risk,
            "predicted_risk_stage": stage,
            "risk_label": labels[stage],
            "confidence": reliability,
            "forecast_storage_pct": round(forecast_pct, 2),
            "demand_stress_added": round(demand_stress, 2),
            "weather_features_used": {
                "temperature_c": temperature_c,
                "rainfall_deficit_pct": rainfall_deficit_pct,
            },
            "model_scope": "one-day reservoir storage forecast with weather and demand inputs",
            "technical_accuracy_note": baseline_note,
            "recommended_mitigation": (
                "Review the forecast storage percentage and apply local operating rules before acting."
            ),
        }
